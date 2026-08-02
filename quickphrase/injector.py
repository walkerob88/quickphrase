"""Text injection: delete the typed trigger, type the replacement.

Placeholder parsing lives in placeholders.py (pure, testable); this module
just performs the physical keystrokes and reports back the tab stops for
any {{blank}} fill-in session.
"""

from __future__ import annotations

import time
from typing import List

from pynput.keyboard import Controller, Key

from .placeholders import plan

# Small pause between injection steps; some apps drop events typed too fast.
STEP_DELAY = 0.005


class Injector:
    def __init__(self, controller: Controller | None = None):
        self.kb = controller or Controller()

    def expand(self, backspaces: int, raw_text: str) -> List[int]:
        """Perform the expansion. Returns tab stops for a fill-in session
        (empty list when the phrase has no {{blank}} placeholders)."""
        p = plan(raw_text)

        for _ in range(backspaces):
            self.kb.tap(Key.backspace)
            time.sleep(STEP_DELAY)

        self.kb.type(p.text)

        for _ in range(p.left_moves):
            time.sleep(STEP_DELAY)
            self.kb.tap(Key.left)

        return list(p.tab_stops)

    def jump_right(self, count: int, remove_tab: bool = True) -> None:
        """Move the caret to the next blank: undo the literal tab character
        the app just received, then arrow right past the intervening text."""
        if remove_tab:
            self.kb.tap(Key.backspace)
            time.sleep(STEP_DELAY)
        for _ in range(count):
            self.kb.tap(Key.right)
            time.sleep(STEP_DELAY)
