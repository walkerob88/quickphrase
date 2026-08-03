"""Phrase packs: shareable JSON bundles of phrases.

A pack file looks like:
{
  "format": "quickphrase-pack",
  "version": 1,
  "name": "Orthopedics starter",
  "description": "...",
  "phrases": {"trigger": {"text": "...", "category": "..."}}
}

Pure logic (no GUI) so it's unit-testable. The GUI wires these functions to
file dialogs.
"""

from __future__ import annotations

import json
import os
from typing import Dict, Tuple

FORMAT = "quickphrase-pack"

Phrases = Dict[str, Dict[str, str]]


class PackError(ValueError):
    pass


def builtin_pack_path(name: str = "orthopedics") -> str:
    return os.path.join(os.path.dirname(__file__), "packs", f"{name}.json")


def load_pack(path: str) -> Tuple[str, Phrases]:
    """Read a pack file. Returns (pack_name, phrases). Raises PackError."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise PackError(f"Couldn't read pack file: {exc}") from exc
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise PackError("Not a QuickPhrase pack file.")
    raw = data.get("phrases")
    if not isinstance(raw, dict) or not raw:
        raise PackError("Pack contains no phrases.")
    phrases: Phrases = {}
    for trigger, entry in raw.items():
        if isinstance(entry, str):
            entry = {"text": entry}
        if not isinstance(entry, dict) or not entry.get("text"):
            continue
        trigger = str(trigger).strip().lstrip(";")
        if not trigger or any(c.isspace() for c in trigger):
            continue
        phrases[trigger] = {
            "text": str(entry["text"]),
            "category": str(entry.get("category", "General")) or "General",
            "favorite": bool(entry.get("favorite", False)),
        }
    if not phrases:
        raise PackError("Pack contains no valid phrases.")
    return str(data.get("name", os.path.basename(path))), phrases


def save_pack(path: str, name: str, phrases: Phrases,
              description: str = "") -> None:
    payload = {
        "format": FORMAT,
        "version": 1,
        "name": name,
        "description": description,
        "phrases": {
            t: {"text": e["text"], "category": e.get("category", "General")}
            for t, e in phrases.items()
        },
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def merge(existing: Phrases, incoming: Phrases,
          overwrite: bool) -> Tuple[Phrases, int, int]:
    """Merge incoming into a copy of existing.

    Returns (merged, added_or_updated_count, conflict_count). A conflict is
    an incoming trigger that already exists with different text; conflicts
    are applied only when overwrite is True (existing favorites are kept).
    """
    merged = {t: dict(e) for t, e in existing.items()}
    applied = 0
    conflicts = 0
    for trigger, entry in incoming.items():
        if trigger in merged:
            if merged[trigger]["text"] == entry["text"]:
                continue
            conflicts += 1
            if not overwrite:
                continue
            favorite = merged[trigger].get("favorite", False)
            merged[trigger] = dict(entry)
            merged[trigger]["favorite"] = favorite
            applied += 1
        else:
            merged[trigger] = dict(entry)
            applied += 1
    return merged, applied, conflicts
