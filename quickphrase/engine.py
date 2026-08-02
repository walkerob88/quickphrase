"""Core expansion engine.

A pure state machine: feed it keystrokes, it tells you when to expand.
No keyboard hooks or OS dependencies here, so it's fully unit-testable.

Behavior:
- Typing the prefix character (default ";") arms the engine.
- Subsequent printable characters accumulate into a buffer.
- When the buffer exactly matches a trigger:
    * If no longer trigger could still match, expansion fires immediately.
    * If the trigger is a proper prefix of another trigger (";b" vs ";brb"),
      the match is held as *pending*. If the user keeps typing toward the
      longer trigger, we wait; if they type something that breaks all
      triggers, the pending match fires and the extra characters are
      re-typed after the replacement.
- Backspace edits the buffer naturally.
- Navigation/modifier keys (arrows, clicks, escape, etc.) reset the engine
  via `reset()`, called by the listener.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class Expansion:
    """Instruction for the injector: delete `backspaces` chars, type `text`."""

    backspaces: int
    text: str
    trigger: str


class ExpansionEngine:
    def __init__(self, phrases: Dict[str, str], prefix: str = ";"):
        if len(prefix) != 1:
            raise ValueError("prefix must be a single character")
        self.prefix = prefix
        self._phrases: Dict[str, str] = {}
        self.set_phrases(phrases)
        self._armed = False
        self._buffer = ""
        self._pending: Optional[str] = None  # trigger matched but extendable

    # -- configuration ------------------------------------------------------

    def set_phrases(self, phrases: Dict[str, str]) -> None:
        """Replace the trigger->replacement table. Triggers exclude the prefix."""
        cleaned = {}
        for trigger, replacement in phrases.items():
            trigger = trigger.strip()
            if trigger.startswith(self.prefix):
                trigger = trigger[len(self.prefix):]
            if trigger:
                cleaned[trigger] = replacement
        self._phrases = cleaned
        self.reset()

    # -- state --------------------------------------------------------------

    def reset(self) -> None:
        """Forget everything typed so far (focus change, arrow key, etc.)."""
        self._armed = False
        self._buffer = ""
        self._pending = None

    @property
    def armed(self) -> bool:
        return self._armed

    @property
    def buffer(self) -> str:
        return self._buffer

    # -- input --------------------------------------------------------------

    def feed_backspace(self) -> None:
        if not self._armed:
            return
        if self._buffer:
            self._buffer = self._buffer[:-1]
            if self._pending and len(self._buffer) < len(self._pending):
                self._pending = None
        else:
            # Backspaced over the prefix itself.
            self.reset()

    def feed_char(self, char: str) -> Optional[Expansion]:
        """Feed one printable character. Returns an Expansion when one fires."""
        if len(char) != 1:
            return None

        if not self._armed:
            if char == self.prefix:
                self._armed = True
                self._buffer = ""
                self._pending = None
            return None

        if char == self.prefix and not self._could_extend(self._buffer + char):
            # Re-arm: user typed the prefix again mid-trigger.
            fired = self._flush_pending(extra=char, rearm=True)
            if fired:
                return fired
            self._buffer = ""
            self._pending = None
            return None

        self._buffer += char

        if self._buffer in self._phrases:
            if self._is_proper_prefix(self._buffer):
                self._pending = self._buffer  # a longer trigger might follow
                return None
            return self._fire(self._buffer, tail="")

        if not self._could_extend(self._buffer):
            # Buffer can no longer become any trigger.
            fired = self._flush_pending(extra="", rearm=False)
            if fired:
                return fired
            # If the breaking char was the prefix, re-arm on it.
            if char == self.prefix:
                self._armed = True
                self._buffer = ""
                self._pending = None
            else:
                self.reset()
        return None

    # -- internals ----------------------------------------------------------

    def _fire(self, trigger: str, tail: str) -> Expansion:
        replacement = self._phrases[trigger]
        backspaces = len(self.prefix) + len(trigger) + len(tail)
        self.reset()
        return Expansion(backspaces=backspaces, text=replacement + tail, trigger=trigger)

    def _flush_pending(self, extra: str, rearm: bool) -> Optional[Expansion]:
        """Fire a held match, re-typing whatever was typed past the trigger."""
        if not self._pending:
            return None
        tail = self._buffer[len(self._pending):] + extra
        expansion = self._fire(self._pending, tail=tail)
        if rearm:
            # The extra char was the prefix: it stays on screen (retyped in
            # the tail), so arm a fresh trigger session.
            self._armed = True
        return expansion

    def _could_extend(self, buffer: str) -> bool:
        return any(t != buffer and t.startswith(buffer) for t in self._phrases)

    def _is_proper_prefix(self, buffer: str) -> bool:
        return self._could_extend(buffer)
