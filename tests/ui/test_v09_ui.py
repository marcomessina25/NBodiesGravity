"""UI tests for v0.9 capabilities: presets, step-once, integrator selection, checkpoints."""
from __future__ import annotations
import tempfile
from pathlib import Path
from datetime import datetime
import numpy as np
import pytest

from nbodiesgravity.ui.main_window import MainWindow
from nbodiesgravity.engine.presets import get_preset
from nbodiesgravity.engine.checkpoints import SimulationCheckpoint


def test_main_window_step_once(qapp):
    win = MainWindow()
    win.show()

    initial_days = win._sim.elapsed_days
    assert initial_days == 0.0

    win._on_step_once()
    assert win._sim.elapsed_days > 0.0
    win.close()


def test_main_window_load_preset(qapp):
    win = MainWindow()
    win.show()

    # Load Circular Two-Body preset
    win._on_load_preset("circular_two_body")
    assert len(win._sim.system.bodies) == 2
    assert win._sim.system.bodies[0].name == "Primary"
    assert win._sim.system.bodies[1].name == "Secondary"

    # Load Earth-Moon preset
    win._on_load_preset("earth_moon")
    assert len(win._sim.system.bodies) == 2
    names = [b.name for b in win._sim.system.bodies]
    assert "Earth" in names
    assert "Moon" in names

    win.close()


def test_main_window_set_integrator(qapp):
    win = MainWindow()
    win.show()

    assert win._sim.system.integrator.name == "velocity_verlet"
    assert "Experimental" not in win.windowTitle()

    # Switch to Leapfrog
    win._set_integrator("leapfrog")
    assert win._sim.system.integrator.name == "leapfrog"
    assert "Experimental" in win.windowTitle()

    # Switch back to Velocity Verlet
    win._set_integrator("velocity_verlet")
    assert win._sim.system.integrator.name == "velocity_verlet"
    assert "Experimental" not in win.windowTitle()

    win.close()


def test_main_window_save_load_checkpoint(qapp, monkeypatch):
    win = MainWindow()
    win.show()

    win._on_step_once()
    elapsed = win._sim.elapsed_days
    assert elapsed > 0.0

    with tempfile.TemporaryDirectory() as tmpdir:
        path = str(Path(tmpdir) / "test_chk.json")
        monkeypatch.setattr(
            "PyQt6.QtWidgets.QFileDialog.getSaveFileName",
            lambda *args, **kwargs: (path, "JSON (*.json)"),
        )
        win._save_checkpoint()
        assert Path(path).exists()

        # Reset simulation to default
        win._new_system()
        assert win._sim.elapsed_days == 0.0

        # Load checkpoint back
        monkeypatch.setattr(
            "PyQt6.QtWidgets.QFileDialog.getOpenFileName",
            lambda *args, **kwargs: (path, "JSON (*.json)"),
        )
        win._load_checkpoint()
        assert np.isclose(win._sim.elapsed_days, elapsed)

    win.close()
