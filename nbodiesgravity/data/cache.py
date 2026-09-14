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

_MEMORY_CACHE: dict | None = None
_CACHE_PATH: Path | None = None
_CACHE_MTIME: float | None = None


def _load() -> dict:
    global _MEMORY_CACHE, _CACHE_PATH, _CACHE_MTIME
    if not CACHE_FILE.exists():
        _MEMORY_CACHE = {}
        _CACHE_PATH = CACHE_FILE
        _CACHE_MTIME = None
        return _MEMORY_CACHE
    try:
        mtime = CACHE_FILE.stat().st_mtime
        if _MEMORY_CACHE is not None and _CACHE_PATH == CACHE_FILE and _CACHE_MTIME == mtime:
            return _MEMORY_CACHE
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            _MEMORY_CACHE = json.load(f)
            _CACHE_PATH = CACHE_FILE
            _CACHE_MTIME = mtime
            return _MEMORY_CACHE
    except Exception:
        return {}


def _save(data: dict) -> None:
    global _MEMORY_CACHE, _CACHE_PATH, _CACHE_MTIME
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    _MEMORY_CACHE = data
    _CACHE_PATH = CACHE_FILE
    try:
        _CACHE_MTIME = CACHE_FILE.stat().st_mtime
    except Exception:
        _CACHE_MTIME = None


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
    global _MEMORY_CACHE, _CACHE_PATH, _CACHE_MTIME
    _MEMORY_CACHE = {}
    _CACHE_PATH = CACHE_FILE
    _CACHE_MTIME = None
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()
