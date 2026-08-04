"""Global keyboard listener: bridges OS key events to the ExpansionEngine.

Runs pynput listeners on background threads. Expansions are performed on a
worker thread so the OS event callback returns quickly. While injecting, all
incoming events are ignored so the app doesn't react to its own keystrokes.

Fill-in sessions: when an expanded phrase contained {{blank}} placeholders,
the caret is left on the first blank and a session begins. Pressing Tab
jumps the caret to the next blank (the literal tab character the app
received is backspaced away first). Arrow keys, clicks or Esc end the
session; typing inside a blank is just normal typing.
"""

from __future__ import annotations

import contextlib
import queue
import sys
import threading
import time
from typing import Callable, List, Optional, Tuple

from pynput import keyboard, mouse


def _patch_darwin_layout_cache() -> None:
    """Work around a macOS crash (pynput issues #511/#512).

    pynput's listener thread reads the keyboard layout via Apple's TIS/TSM
    APIs, but modern macOS requires those calls to happen on the main
    thread — off-main-thread calls die in dispatch_assert_queue
    (EXC_BAD_INSTRUCTION in HIToolbox). This module is imported on the main
    thread, so we capture the layout context once HERE and monkeypatch
    pynput to serve the cached value to every later caller, keeping the
    listener thread away from the forbidden APIs entirely.

    Trade-off: switching keyboard layouts/input sources on macOS requires an
    app restart to be picked up. Wrapped in try/except so a future pynput
    that fixes this internally (or any API change) degrades gracefully.
    """
    if sys.platform != "darwin":
        return
    try:
        from pynput._util import darwin as _du
        cm = _du.keycode_context()
        cached = cm.__enter__()  # intentionally never exited; app-lifetime
        @contextlib.contextmanager
        def _cached_keycode_context():
            yield cached
        _du.keycode_context = _cached_keycode_context
        try:  # also rebind any direct import in the darwin keyboard backend
            from pynput.keyboard import _darwin as _kbd
            if hasattr(_kbd, "keycode_context"):
                _kbd.keycode_context = _cached_keycode_context
        except Exception:
            pass
    except Exception:
        pass  # never block startup over the workaround itself


_patch_darwin_layout_cache()

from .engine import Expansion, ExpansionEngine
from .injector import Injector

# Keys that mean "the caret moved / context changed": forget the buffer.
RESET_KEYS = {
    keyboard.Key.esc, keyboard.Key.left, keyboard.Key.right, keyboard.Key.up,
    keyboard.Key.down, keyboard.Key.home, keyboard.Key.end,
    keyboard.Key.page_up, keyboard.Key.page_down, keyboard.Key.delete,
    keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r,
    keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr,
    keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r,
}

CHAR_KEYS = {
    keyboard.Key.space: " ",
    keyboard.Key.enter: "\n",
    keyboard.Key.tab: "\t",
}

# Grace period after injecting before we trust incoming events again.
POST_INJECT_GRACE = 0.08


class ExpanderService:
    """Owns the engine, the listeners, the injection worker, fill sessions."""

    def __init__(self, engine: ExpansionEngine,
                 on_expansion: Optional[Callable[[Expansion], None]] = None):
        self.engine = engine
        self.injector = Injector()
        self.on_expansion = on_expansion
        self._injecting = threading.Event()
        self._queue: "queue.Queue[Tuple[str, object]]" = queue.Queue()
        self._tab_stops: List[int] = []          # pending {{blank}} jumps
        self._kb_listener: Optional[keyboard.Listener] = None
        self._mouse_listener: Optional[mouse.Listener] = None
        self._worker: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
        if self._worker is None:
            self._worker = threading.Thread(target=self._drain, daemon=True)
            self._worker.start()
        self._kb_listener = keyboard.Listener(on_press=self._on_press)
        self._kb_listener.start()
        self._mouse_listener = mouse.Listener(on_click=self._on_click)
        self._mouse_listener.start()

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False
        for listener in (self._kb_listener, self._mouse_listener):
            if listener:
                listener.stop()
        self._kb_listener = None
        self._mouse_listener = None
        self._tab_stops = []
        self.engine.reset()

    @property
    def running(self) -> bool:
        return self._running

    @property
    def in_fill_session(self) -> bool:
        return bool(self._tab_stops)

    # -- event handlers -----------------------------------------------------

    def _on_press(self, key) -> None:
        if self._injecting.is_set() or not self._running:
            return
        try:
            if key == keyboard.Key.tab and self._tab_stops:
                # Jump to the next blank instead of typing a tab.
                self._queue.put(("jump", self._tab_stops.pop(0)))
                self.engine.reset()
                return
            if key == keyboard.Key.backspace:
                self.engine.feed_backspace()
                return
            if key in RESET_KEYS:
                self._tab_stops = []          # caret moved: end fill session
                self.engine.reset()
                return
            char = CHAR_KEYS.get(key)
            if char is None:
                char = getattr(key, "char", None)
            if char:
                expansion = self.engine.feed_char(char)
                if expansion:
                    self._queue.put(("expand", expansion))
        except Exception:
            self.engine.reset()  # never let a bug kill the hook

    def _on_click(self, x, y, button, pressed) -> None:
        if pressed and not self._injecting.is_set():
            self._tab_stops = []
            self.engine.reset()

    # -- injection worker ---------------------------------------------------

    def _drain(self) -> None:
        while True:
            kind, payload = self._queue.get()
            if not self._running:
                continue
            self._injecting.set()
            try:
                if kind == "expand":
                    expansion: Expansion = payload  # type: ignore[assignment]
                    stops = self.injector.expand(expansion.backspaces,
                                                 expansion.text)
                    self._tab_stops = stops
                elif kind == "jump":
                    self.injector.jump_right(int(payload))
                time.sleep(POST_INJECT_GRACE)
            finally:
                self._injecting.clear()
            if kind == "expand" and self.on_expansion:
                try:
                    self.on_expansion(payload)
                except Exception:
                    pass
