"""Local JSON cache for JPL Horizons query results.

Cache file: ~/.nbodiesgravity/cache.json
Key format: "{body_id}_{YYYY-MM-DD}"
Entries never expire — orbital mechanics are deterministic.
"""
from __future__ import annotations
import json
from datetime import date
from pathlib import Path

CACHE_DIR: Path = Path.home() / ".nbodiesgravity"
CACHE_FILE: Path = CACHE_DIR / "cache.json"


def _load() -> dict:
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save(data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _key(body_id: str, epoch_date: date) -> str:
    return f"{body_id}_{epoch_date.strftime('%Y-%m-%d')}"


def get(body_id: str, epoch_date: date) -> dict | None:
    """Return cached state dict, or None if not present."""
    return _load().get(_key(body_id, epoch_date))


def store(body_id: str, epoch_date: date, state: dict) -> None:
    """Persist a state dict keyed by body_id and date."""
    data = _load()
    data[_key(body_id, epoch_date)] = state
    _save(data)


def clear_cache() -> None:
    """Delete the cache file. No-op if it does not exist."""
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()
