"""Placeholder rendering and blank parsing. Pure functions, no OS deps.

Supported placeholders:
    {{date}}   -> today's date
    {{time}}   -> current time
    {{cursor}} -> caret lands here after expansion (single position)
    {{blank}}  -> fill-in stop; caret lands on the first blank, Tab jumps
                  to each following blank. Overrides {{cursor}} if both used.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import List

BLANK = "{{blank}}"
CURSOR = "{{cursor}}"


@dataclass(frozen=True)
class InjectionPlan:
    """What the injector should physically do.

    text        - the literal text to type
    left_moves  - left-arrow presses after typing (to reach cursor/first blank)
    tab_stops   - for each subsequent Tab press, how many right-arrow presses
                  move the caret to the next blank (last entry reaches the end
                  of the snippet)
    """

    text: str
    left_moves: int = 0
    tab_stops: List[int] = field(default_factory=list)


def render_dynamic(text: str) -> str:
    now = _dt.datetime.now()
    return (
        text.replace("{{date}}", now.strftime("%Y-%m-%d"))
        .replace("{{time}}", now.strftime("%H:%M"))
    )


def plan(raw_text: str) -> InjectionPlan:
    text = render_dynamic(raw_text)

    if BLANK in text:
        parts = text.split(BLANK)
        typed = "".join(parts).replace(CURSOR, "")
        # Caret goes to the first blank (right after parts[0]):
        left = sum(len(p.replace(CURSOR, "")) for p in parts[1:])
        stops = [len(p.replace(CURSOR, "")) for p in parts[1:]]
        return InjectionPlan(text=typed, left_moves=left, tab_stops=stops)

    if CURSOR in text:
        before, _, after = text.partition(CURSOR)
        after = after.replace(CURSOR, "")
        return InjectionPlan(text=before + after, left_moves=len(after))

    return InjectionPlan(text=text)
