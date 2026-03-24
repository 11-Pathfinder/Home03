"""Deduplication and state management via data/seen.json."""

from __future__ import annotations

import json
from pathlib import Path

from models import Property

STATE_FILE = Path("data/seen.json")


def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_new_properties(scraped: list[Property], state: dict) -> list[Property]:
    """Return only properties not already in state."""
    return [p for p in scraped if p.id not in state]
