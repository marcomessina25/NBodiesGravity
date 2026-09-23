"""Assembles a SolarSystem from bundled snapshots, JPL Horizons, presets, or checkpoints.

Public API
----------
load_default_system() -> SolarSystem
    Reads j2000.json. Synchronous, no network required.

load_system_at_date(epoch, progress_cb) -> SolarSystem
    Checks local cache; falls back to JPL Horizons.
    Designed to run inside a QThread worker (DateLoaderWorker).

load_preset_system(preset_name, **kwargs) -> tuple[SolarSystem, datetime]
    Loads one of the analytical initial-condition presets.

load_checkpoint(path) -> tuple[SolarSystem, datetime, float, dict]
    Restores simulation state from a high-precision checkpoint file.
"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Callable, Any
import numpy as np

from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.system import SolarSystem
from nbodiesgravity.engine.presets import get_preset
from nbodiesgravity.engine.checkpoints import SimulationCheckpoint
import nbodiesgravity.data.cache as _cache
# Indirected name so tests can monkeypatch _fetch_from_horizons
from nbodiesgravity.data.horizons import fetch as _fetch_from_horizons  # noqa: F401

SNAPSHOT_PATH: Path = Path(__file__).parent / "snapshots" / "j2000.json"


def _read_snapshot() -> dict:
    with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _body_from_entry(
    entry: dict, pos_au: list[float], vel_au_per_day: list[float]
) -> CelestialBody:
    return CelestialBody(
        name=entry["name"],
        mass=entry["mass_kg"],
        pos=np.array(pos_au, dtype=float),
        vel=np.array(vel_au_per_day, dtype=float),
        radius=entry["radius_km"],
        color=tuple(entry["color"]),
        label=entry.get("label", "planet"),
        show_name=entry.get("show_name", True),
    )


def load_default_system() -> SolarSystem:
    """Build a SolarSystem from the bundled J2000 snapshot. Instant."""
    snapshot = _read_snapshot()
    bodies = [
        _body_from_entry(e, e["pos_au"], e["vel_au_per_day"])
        for e in snapshot["bodies"]
    ]
    return SolarSystem(bodies)


def load_preset_system(preset_name: str, **kwargs) -> tuple[SolarSystem, datetime]:
    """Load an analytical initial-condition preset and return (system, epoch)."""
    preset = get_preset(preset_name, **kwargs)
    return preset.create_system(), preset.epoch


def load_checkpoint(path: str | Path) -> tuple[SolarSystem, datetime, float, dict[str, Any]]:
    """Load a SimulationCheckpoint from JSON file and restore simulation state."""
    chk = SimulationCheckpoint.load(path)
    return chk.restore()


def load_system_at_date(
    epoch: datetime,
    progress_cb: Callable[[str], None],
    cancel_cb: Callable[[], bool] | None = None,
) -> SolarSystem | None:
    """Fetch state vectors for all default bodies at *epoch*.

    For each body: checks local cache first, then queries JPL Horizons.
    Calls progress_cb(body_name) after each body is resolved.
    If cancel_cb is provided and returns True, loading terminates early and returns None.
    Raises HorizonsError if any body cannot be fetched.
    """
    # Import here so monkeypatching the module-level name works in tests
    import nbodiesgravity.data.loader as _self
    fetch_fn = _self._fetch_from_horizons

    snapshot = _read_snapshot()
    epoch_date = epoch.date()
    bodies = []
    for entry in snapshot["bodies"]:
        if cancel_cb and cancel_cb():
            return None
        body_id = entry["id"]
        state = _cache.get(body_id, epoch_date)
        if state is None:
            if cancel_cb and cancel_cb():
                return None
            state = fetch_fn(body_id, epoch_date)
            _cache.store(body_id, epoch_date, state)
        bodies.append(_body_from_entry(entry, state["pos_au"], state["vel_au_per_day"]))
        progress_cb(entry["name"])
        if cancel_cb and cancel_cb():
            return None
    return SolarSystem(bodies)
