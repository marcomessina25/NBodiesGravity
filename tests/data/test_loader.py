import numpy as np
from datetime import datetime
import pytest
from nbodiesgravity.data.loader import load_default_system, load_system_at_date
from nbodiesgravity.engine.system import SolarSystem


def test_load_default_returns_solar_system():
    system = load_default_system()
    assert isinstance(system, SolarSystem)


def test_load_default_has_22_bodies():
    system = load_default_system()
    assert len(system.bodies) == 22


def test_load_default_contains_haumea_and_makemake():
    system = load_default_system()
    names = {b.name for b in system.bodies}
    assert "Haumea" in names
    assert "Makemake" in names


def test_load_default_contains_sun_earth_moon():
    system = load_default_system()
    names = {b.name for b in system.bodies}
    assert {"Sun", "Earth", "Moon"}.issubset(names)


def test_earth_near_1_au_at_j2000():
    system = load_default_system()
    earth = system.get_body("Earth")
    assert earth is not None
    assert 0.9 < np.linalg.norm(earth.pos) < 1.1


def test_load_at_date_uses_cache_on_second_call(tmp_path, monkeypatch):
    import nbodiesgravity.data.cache as cache_mod
    import nbodiesgravity.data.loader as loader_mod

    monkeypatch.setattr(cache_mod, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(cache_mod, "CACHE_FILE", tmp_path / "cache.json")

    calls = []

    def fake_fetch(body_id, epoch_date):
        calls.append(body_id)
        return {"pos_au": [1.0, 0.0, 0.0], "vel_au_per_day": [0.0, 0.017, 0.0]}

    monkeypatch.setattr(loader_mod, "_fetch_from_horizons", fake_fetch)

    epoch = datetime(2020, 6, 1)
    load_system_at_date(epoch, progress_cb=lambda _: None)
    n_first = len(calls)

    # Second call with same date — cache must serve all bodies, no new fetches
    load_system_at_date(epoch, progress_cb=lambda _: None)
    assert len(calls) == n_first   # no additional Horizons calls
