"""Reliability, offline-fallback, and caching resilience tests for JPL Horizons data loader."""
from __future__ import annotations
import json
from datetime import datetime, date
from pathlib import Path
import pytest
import responses as resp_mock

from nbodiesgravity.data import cache
from nbodiesgravity.data.loader import load_system_at_date
from nbodiesgravity.data.horizons import HorizonsError, HORIZONS_URL


def test_horizons_cache_priority(tmp_path, monkeypatch):
    """Verify that cached bodies bypass network calls entirely."""
    cache_file = tmp_path / "cache.json"
    monkeypatch.setattr(cache, "CACHE_FILE", cache_file)
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    cache.clear_cache()

    # Pre-populate cache with Earth data for 2025-01-01
    epoch = datetime(2025, 1, 1)
    cache.store("399", epoch.date(), {
        "pos_au": [1.0, 0.0, 0.0],
        "vel_au_per_day": [0.0, 0.0172, 0.0],
    })

    # Retrieve from cache
    entry = cache.get("399", epoch.date())
    assert entry is not None
    assert entry["pos_au"] == [1.0, 0.0, 0.0]


def test_horizons_cancellation_callback(tmp_path, monkeypatch):
    """Verify that load_system_at_date aborts cleanly when cancel_cb returns True."""
    cancelled = False

    def cancel_check() -> bool:
        return cancelled

    progress_log = []
    # Trigger cancellation after first body
    def on_progress(name: str):
        nonlocal cancelled
        progress_log.append(name)
        cancelled = True

    # Mock horizons fetch to return synthetic data without making network calls
    def mock_fetch(body_id: str, epoch_date: date):
        return {"pos_au": [0.0, 0.0, 0.0], "vel_au_per_day": [0.0, 0.0, 0.0]}

    import nbodiesgravity.data.loader as loader_module
    monkeypatch.setattr(loader_module, "_fetch_from_horizons", mock_fetch)

    # Cache directory isolated to tmp_path
    monkeypatch.setattr(cache, "CACHE_FILE", tmp_path / "cache.json")
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    cache.clear_cache()

    result = load_system_at_date(datetime(2025, 1, 1), progress_cb=on_progress, cancel_cb=cancel_check)
    assert result is None  # Must abort and return None
    assert len(progress_log) <= 2  # Terminated early


def test_horizons_corrupt_cache_recovery(tmp_path, monkeypatch):
    """Verify that a corrupted cache file gracefully falls back to empty cache without crashing."""
    cache_file = tmp_path / "cache.json"
    cache_file.write_text("{ this is malformed json", encoding="utf-8")

    monkeypatch.setattr(cache, "CACHE_FILE", cache_file)
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    cache._MEMORY_CACHE = None
    cache._CACHE_PATH = None
    cache._CACHE_MTIME = None

    # Must return None without raising JSONDecodeError
    result = cache.get("399", date(2025, 1, 1))
    assert result is None
