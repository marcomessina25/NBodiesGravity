"""Backward compatibility tests across historical save formats (v0.5 to v0.9)."""
from __future__ import annotations
import json
import tempfile
from pathlib import Path
from datetime import datetime
import numpy as np
import pytest
from PyQt6.QtWidgets import QFileDialog

from nbodiesgravity.ui.main_window import MainWindow


def test_load_legacy_v05_file(qapp, monkeypatch):
    """v0.5 file without integrator_config or physics_config must load with default Velocity Verlet."""
    data = {
        "epoch": "2015-06-01",
        "bodies": [
            {
                "name": "Sun",
                "mass": 1.989e30,
                "position": [0.0, 0.0, 0.0],
                "velocity": [0.0, 0.0, 0.0],
                "radius": 696340.0,
                "color": [255, 255, 0],
            },
            {
                "name": "Earth",
                "mass": 5.972e24,
                "position": [1.0, 0.0, 0.0],
                "velocity": [0.0, 0.0172, 0.0],
                "radius": 6371.0,
                "color": [0, 100, 255],
            },
        ],
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "v05_save.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        window = MainWindow()
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: (str(path), "JSON (*.json)"))
        window._load_from_file()

        assert len(window._sim.system.bodies) == 2
        assert window._sim.system.integrator.name == "velocity_verlet"
        assert window._last_epoch == datetime(2015, 6, 1)
        window.close()


def test_load_v08_file(qapp, monkeypatch):
    """v0.8 file with format_version=1 must load with default physics and Velocity Verlet."""
    data = {
        "format_version": 1,
        "epoch": "2024-01-01",
        "bodies": [
            {
                "name": "Sun",
                "label": "star",
                "mass_kg": 1.989e30,
                "radius_km": 696340.0,
                "color": [255, 255, 0],
                "pos_au": [0.0, 0.0, 0.0],
                "vel_au_per_day": [0.0, 0.0, 0.0],
                "active": True,
                "show_trail": False,
                "show_name": True,
            }
        ],
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "v08_save.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        window = MainWindow()
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: (str(path), "JSON (*.json)"))
        window._load_from_file()

        assert len(window._sim.system.bodies) == 1
        assert window._sim.system.integrator.name == "velocity_verlet"
        window.close()


def test_load_v09_file_with_custom_integrator_and_physics(qapp, monkeypatch):
    """v0.9 file with Leapfrog and custom softening must restore those configurations."""
    data = {
        "format_version": 1,
        "epoch": "2030-01-01",
        "integrator_config": {
            "name": "leapfrog",
            "softening": 2e-4,
            "max_displacement": 50.0,
            "parameters": {},
        },
        "physics_config": {
            "gravitational_constant": 0.0002959122082855911,
            "softening_length": 2e-4,
            "gravity_model": "newtonian",
            "softening_model": "plummer",
        },
        "collision_config": {
            "enabled": True,
            "model": "merge",
        },
        "bodies": [
            {
                "name": "TestBody",
                "label": "planet",
                "mass_kg": 1e24,
                "radius_km": 5000.0,
                "color": [200, 200, 200],
                "pos_au": [2.0, 0.0, 0.0],
                "vel_au_per_day": [0.0, 0.01, 0.0],
                "active": True,
                "show_trail": True,
                "show_name": True,
            }
        ],
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "v09_save.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        window = MainWindow()
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: (str(path), "JSON (*.json)"))
        window._load_from_file()

        assert window._sim.system.integrator.name == "leapfrog"
        assert window._sim.system.softening == 2e-4
        assert "Experimental" in window.windowTitle()
        window.close()
