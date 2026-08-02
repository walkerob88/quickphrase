"""Phrase + settings storage: a JSON file in the user-config directory.

File format (v2):
{
  "version": 2,
  "settings": {"dark": false},
  "phrases": {
    "brb": {"text": "be right back", "category": "General"}
  }
}

v1 files (flat {"trigger": "text"}) are migrated automatically.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from typing import Dict, Tuple

APP_NAME = "QuickPhrase"
DEFAULT_CATEGORY = "General"

Phrases = Dict[str, Dict[str, str]]  # trigger -> {"text": ..., "category": ...}
Settings = Dict[str, object]

DEFAULT_PHRASES: Phrases = {
    "brb": {"text": "be right back", "category": "General"},
    "omw": {"text": "on my way!", "category": "General"},
    "sig": {"text": "Best,\nRob", "category": "Email"},
    "intro": {
        "text": "Hi {{blank}},\n\nThanks for reaching out about {{blank}}. "
                "I'll get back to you by {{blank}}.\n\nBest,\nRob",
        "category": "Email",
    },
    "date": {"text": "{{date}}", "category": "Utilities"},
    "time": {"text": "{{time}}", "category": "Utilities"},
}

DEFAULT_SETTINGS: Settings = {"dark": False}


def config_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, APP_NAME)
    if sys.platform == "darwin":
        return os.path.expanduser(f"~/Library/Application Support/{APP_NAME}")
    base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return os.path.join(base, APP_NAME.lower())


class PhraseStore:
    """Thread-safe load/save of phrases and settings."""

    def __init__(self, path: str | None = None):
        self.path = path or os.path.join(config_dir(), "phrases.json")
        self._lock = threading.Lock()

    def load(self) -> Tuple[Phrases, Settings]:
        with self._lock:
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except FileNotFoundError:
                self._write(DEFAULT_PHRASES, DEFAULT_SETTINGS)
                return dict(DEFAULT_PHRASES), dict(DEFAULT_SETTINGS)
            except (json.JSONDecodeError, OSError):
                return {}, dict(DEFAULT_SETTINGS)

            if not isinstance(data, dict):
                return {}, dict(DEFAULT_SETTINGS)

            if "phrases" not in data:
                # v1 flat format: {"trigger": "text"} -> migrate.
                phrases = {
                    str(t): {"text": str(x), "category": DEFAULT_CATEGORY}
                    for t, x in data.items() if isinstance(x, str)
                }
                settings = dict(DEFAULT_SETTINGS)
                self._write(phrases, settings)
                return phrases, settings

            phrases: Phrases = {}
            for trigger, entry in data.get("phrases", {}).items():
                if isinstance(entry, str):
                    entry = {"text": entry}
                if isinstance(entry, dict) and "text" in entry:
                    phrases[str(trigger)] = {
                        "text": str(entry["text"]),
                        "category": str(entry.get("category", DEFAULT_CATEGORY))
                                    or DEFAULT_CATEGORY,
                    }
            settings = dict(DEFAULT_SETTINGS)
            if isinstance(data.get("settings"), dict):
                settings.update(data["settings"])
            return phrases, settings

    def save(self, phrases: Phrases, settings: Settings) -> None:
        with self._lock:
            self._write(phrases, settings)

    def _write(self, phrases: Phrases, settings: Settings) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        payload = {"version": 2, "settings": settings, "phrases": phrases}
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)
