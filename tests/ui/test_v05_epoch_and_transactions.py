from datetime import datetime, timedelta
import numpy as np
import pytest
from PyQt6.QtCore import QDate

from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.system import SolarSystem
from nbodiesgravity.ui.main_window import MainWindow
from nbodiesgravity.ui.date_loader_worker import DateLoaderWorker


def test_successful_epoch_change_updates_active_state(qapp, monkeypatch):
    """Loading a date updates _last_epoch, initial epoch, and active system atomically."""
    window = MainWindow()
    try:
        new_epoch = datetime(2025, 6, 1)
        mock_body = CelestialBody(
            name="MockBody", mass=1e24, pos=np.array([1.0, 2.0, 3.0]),
            vel=np.zeros(3), radius=5000.0, color=(1.0, 0.0, 0.0),
        )
        mock_system = SolarSystem([mock_body])

        # Directly simulate on_load_finished
        window._requested_epoch = new_epoch
        window._on_load_finished(mock_system)

        assert window._last_epoch == new_epoch
        assert window._initial_epoch == new_epoch
        assert window._ctrl._date_edit.date() == QDate(2025, 6, 1)
        assert len(window._sim.system.bodies) == 1
        assert window._sim.system.bodies[0].name == "MockBody"
    finally:
        window.close()


def test_failed_epoch_change_rolls_back_ui(qapp, monkeypatch):
    """Failed date query leaves previous active system and active epoch untouched."""
    window = MainWindow()
    try:
        initial_epoch = window._last_epoch
        initial_body_count = len(window._sim.system.bodies)
        failed_epoch = datetime(2035, 1, 1)

        # Mock QMessageBox so warning dialog doesn't block headless execution
        from PyQt6.QtWidgets import QMessageBox
        monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)

        window._requested_epoch = failed_epoch
        window._on_load_error("Network timeout")

        assert window._last_epoch == initial_epoch
        assert window._requested_epoch is None
        assert window._ctrl._date_edit.date() == QDate(initial_epoch.year, initial_epoch.month, initial_epoch.day)
        assert len(window._sim.system.bodies) == initial_body_count
    finally:
        window.close()


def test_cancelled_epoch_change_rolls_back_ui(qapp):
    """Cancelled date loading leaves active simulation and epoch intact."""
    window = MainWindow()
    try:
        initial_epoch = window._last_epoch
        initial_bodies = [b.name for b in window._sim.system.bodies]
        cancelled_epoch = datetime(2030, 5, 1)

        window._requested_epoch = cancelled_epoch
        window._on_load_cancelled()

        assert window._last_epoch == initial_epoch
        assert window._requested_epoch is None
        assert window._ctrl._date_edit.date() == QDate(initial_epoch.year, initial_epoch.month, initial_epoch.day)
        assert [b.name for b in window._sim.system.bodies] == initial_bodies
    finally:
        window.close()


def test_worker_cancellation():
    """DateLoaderWorker stops when cancel() is invoked."""
    worker = DateLoaderWorker(datetime(2025, 1, 1))
    assert worker.is_cancelled is False
    worker.cancel()
    assert worker.is_cancelled is True


def test_new_system_resets_epoch_and_simulation(qapp):
    """New System resets active state, initial epoch, and elapsed time back to J2000."""
    window = MainWindow()
    try:
        # First load a different date/epoch
        custom_epoch = datetime(2015, 7, 14)
        mock_body = CelestialBody(
            name="PlutoProbe", mass=1e3, pos=np.array([30.0, 0.0, 0.0]),
            vel=np.zeros(3), radius=10.0, color=(1.0, 1.0, 1.0),
        )
        window._load_system(SolarSystem([mock_body]), epoch=custom_epoch)
        assert window._last_epoch == custom_epoch
        assert window._ctrl._date_edit.date() == QDate(2015, 7, 14)

        # Trigger New System
        window._new_system()

        assert window._last_epoch == datetime(2000, 1, 1)
        assert window._initial_epoch == datetime(2000, 1, 1)
        assert window._ctrl._date_edit.date() == QDate(2000, 1, 1)
        assert window._sim.elapsed_days == 0.0
        assert len(window._sim.system.bodies) == 39
    finally:
        window.close()


def test_restart_returns_to_loaded_epoch(qapp):
    """Restart resets to the specific epoch and initial bodies of the currently loaded system."""
    window = MainWindow()
    try:
        loaded_epoch = datetime(2010, 1, 1)
        b1 = CelestialBody(
            name="BodyA", mass=1e24, pos=np.array([1.0, 0.0, 0.0]),
            vel=np.array([0.0, 0.01, 0.0]), radius=5000.0, color=(1.0, 0.0, 0.0),
        )
        window._load_system(SolarSystem([b1]), epoch=loaded_epoch)

        # Advance physics simulation thread
        window._sim.system.step(10.0)
        window._sim._elapsed_days = 10.0
        assert np.linalg.norm(window._sim.system.bodies[0].pos - np.array([1.0, 0.0, 0.0])) > 0.05

        # Trigger restart
        window._on_restart()

        assert window._last_epoch == loaded_epoch
        assert window._initial_epoch == loaded_epoch
        assert window._sim.elapsed_days == 0.0
        assert np.allclose(window._sim.system.bodies[0].pos, [1.0, 0.0, 0.0])
    finally:
        window.close()
