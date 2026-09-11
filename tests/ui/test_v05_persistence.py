import json
from datetime import datetime
from pathlib import Path
import numpy as np
from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import QFileDialog

from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.system import SolarSystem
from nbodiesgravity.ui.main_window import MainWindow


def test_save_and_load_roundtrip_preserves_all_properties(qapp, tmp_path, monkeypatch):
    """Saving and reloading a system must preserve physical and UI state completely."""
    save_file = tmp_path / "test_system.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(save_file), "JSON (*.json)"))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: (str(save_file), "JSON (*.json)"))

    window = MainWindow()
    try:
        # Create a system with diverse properties
        b1 = CelestialBody(
            name="PrimaryStar", mass=2e30, pos=np.array([0.1, 0.2, 0.3]),
            vel=np.array([0.001, -0.002, 0.003]), radius=700000.0,
            color=(1.0, 0.8, 0.2), label="star", active=True,
            show_trail=False, show_name=True,
        )
        b2 = CelestialBody(
            name="InactiveMoon", mass=7e22, pos=np.array([1.0, 0.0, 0.0]),
            vel=np.array([0.0, 0.017, 0.0]), radius=1737.0,
            color=(0.7, 0.7, 0.7), label="moon", active=False,
            show_trail=True, show_name=False,
        )
        loaded_epoch = datetime(2030, 4, 15)
        window._load_system(SolarSystem([b1, b2]), epoch=loaded_epoch)

        # Save system
        window._save_to_file()

        # Check raw JSON
        with open(save_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data.get("format_version") == 1
        assert data.get("epoch") == "2030-04-15"
        assert len(data["bodies"]) == 2

        star_entry = next(e for e in data["bodies"] if e["name"] == "PrimaryStar")
        assert star_entry["label"] == "star"
        assert star_entry["active"] is True
        assert star_entry["show_trail"] is False
        assert star_entry["show_name"] is True
        assert np.allclose(star_entry["pos_au"], [0.1, 0.2, 0.3])
        assert np.allclose(star_entry["vel_au_per_day"], [0.001, -0.002, 0.003])

        moon_entry = next(e for e in data["bodies"] if e["name"] == "InactiveMoon")
        assert moon_entry["label"] == "moon"
        assert moon_entry["active"] is False
        assert moon_entry["show_trail"] is True
        assert moon_entry["show_name"] is False

        # Load it back into MainWindow
        window._load_from_file()

        assert window._last_epoch == loaded_epoch
        assert window._ctrl._date_edit.date() == QDate(2030, 4, 15)
        assert len(window._sim.system.bodies) == 2

        restored_star = window._sim.system.get_body("PrimaryStar")
        assert restored_star is not None
        assert restored_star.label == "star"
        assert restored_star.active is True
        assert restored_star.show_trail is False
        assert restored_star.show_name is True
        assert np.allclose(restored_star.pos, [0.1, 0.2, 0.3])

        restored_moon = window._sim.system.get_body("InactiveMoon")
        assert restored_moon is not None
        assert restored_moon.label == "moon"
        assert restored_moon.active is False
        assert restored_moon.show_trail is True
        assert restored_moon.show_name is False
    finally:
        window.close()


def test_load_legacy_format_backward_compatibility(qapp, tmp_path, monkeypatch):
    """Loading older JSON files without format_version, epoch, or UI flags succeeds with defaults."""
    legacy_file = tmp_path / "legacy.json"
    legacy_data = {
        "bodies": [
            {
                "name": "Sun",
                "mass_kg": 1.989e30,
                "radius_km": 696340.0,
                "color": [1.0, 1.0, 0.0],
                "pos_au": [0.0, 0.0, 0.0],
                "vel_au_per_day": [0.0, 0.0, 0.0],
            },
            {
                "name": "Earth",
                "mass_kg": 5.972e24,
                "radius_km": 6371.0,
                "color": [0.2, 0.4, 1.0],
                "pos_au": [1.0, 0.0, 0.0],
                "vel_au_per_day": [0.0, 0.017, 0.0],
            }
        ]
    }
    with open(legacy_file, "w", encoding="utf-8") as f:
        json.dump(legacy_data, f)

    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: (str(legacy_file), "JSON (*.json)"))

    window = MainWindow()
    try:
        window._load_from_file()

        assert window._last_epoch == datetime(2000, 1, 1)
        assert len(window._sim.system.bodies) == 2

        sun = window._sim.system.get_body("Sun")
        assert sun.label == "star"
        assert sun.active is True
        assert sun.show_trail is True
        assert sun.show_name is True

        earth = window._sim.system.get_body("Earth")
        assert earth.label == "planet"
        assert earth.active is True
        assert earth.show_trail is True
        assert earth.show_name is True
    finally:
        window.close()
