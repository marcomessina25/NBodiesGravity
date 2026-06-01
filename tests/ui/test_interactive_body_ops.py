import numpy as np
import pytest
from PyQt6.QtWidgets import QMessageBox
from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.system import SolarSystem
from nbodiesgravity.rendering.gl_widget import GLWidget
from nbodiesgravity.ui.main_window import MainWindow


@pytest.fixture(autouse=True)
def mock_opengl(monkeypatch):
    """Mock OpenGL rendering calls to prevent headless hangs during event loops."""
    monkeypatch.setattr(GLWidget, "initializeGL", lambda self: None)
    monkeypatch.setattr(GLWidget, "resizeGL", lambda self, w, h: None)
    monkeypatch.setattr(GLWidget, "paintGL", lambda self: None)
    monkeypatch.setattr(GLWidget, "paintEvent", lambda self, event: None)


def test_add_body_pauses_and_modifies_thread_safely(qapp, monkeypatch):
    # Setup a small system
    sun = CelestialBody("Sun", 1.989e30, np.zeros(3), np.zeros(3), 695700, (1.0, 0.9, 0.2))
    earth = CelestialBody("Earth", 5.972e24, np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0172, 0.0]), 6371, (0.2, 0.5, 1.0))
    system = SolarSystem([sun, earth])
    
    # Instantiate MainWindow
    window = MainWindow()
    
    # Load our test system
    window._load_system(system)
    
    try:
        # Start the simulation thread
        window._sim.resume()
        window._ctrl.set_playing(True)
        assert window._sim.is_playing is True
        assert window._ctrl._playing is True
        
        # Mock the dialog execution to return Accepted and a new body "Mars"
        new_body = CelestialBody("Mars", 6.39e23, np.array([1.5, 0.0, 0.0]), np.zeros(3), 3389, (1.0, 0.0, 0.0))
        
        class DummyDialog:
            class DialogCode:
                Accepted = 1
                Rejected = 0
                
            def __init__(self, *args, **kwargs):
                pass
            def exec(self):
                return 1  # Accepted (BodyEditorDialog.DialogCode.Accepted)
            def result_body(self):
                return new_body

        monkeypatch.setattr("nbodiesgravity.ui.main_window.BodyEditorDialog", DummyDialog)
        
        # Execute _add_body. It should pause the simulation, update the UI, add the body, and NOT resume.
        window._add_body()
        
        # Verify that the simulation is paused in both thread and UI control panel
        assert window._sim.is_playing is False
        assert window._ctrl._playing is False
        
        # Verify that Mars was added to the system and is present in the latest snapshot
        with window._sim._lock:
            bodies = window._sim.system.bodies
            body_names = [b.name for b in bodies]
            assert "Mars" in body_names
            
        snap_names = [s.name for s in window._sim.latest_snapshot]
        assert "Mars" in snap_names

    finally:
        # Clean up the thread
        window._date_timer.stop()
        window._sim.stop_thread()


def test_edit_body_pauses_and_updates_thread_safely(qapp, monkeypatch):
    sun = CelestialBody("Sun", 1.989e30, np.zeros(3), np.zeros(3), 695700, (1.0, 0.9, 0.2))
    earth = CelestialBody("Earth", 5.972e24, np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0172, 0.0]), 6371, (0.2, 0.5, 1.0))
    system = SolarSystem([sun, earth])
    
    window = MainWindow()
    window._load_system(system)
    
    try:
        window._sim.resume()
        window._ctrl.set_playing(True)
        assert window._sim.is_playing is True
        
        updated_body = CelestialBody("Earth", 5.972e24, np.array([1.1, 0.0, 0.0]), np.array([0.0, 0.0172, 0.0]), 6371, (0.2, 0.5, 1.0))
        
        class DummyDialog:
            class DialogCode:
                Accepted = 1
                Rejected = 0
                
            def __init__(self, *args, **kwargs):
                pass
            def exec(self):
                return 1  # Accepted
            def result_body(self):
                return updated_body

        monkeypatch.setattr("nbodiesgravity.ui.main_window.BodyEditorDialog", DummyDialog)
        
        # Execute _edit_body
        window._edit_body("Earth")
        
        # Verify paused state
        assert window._sim.is_playing is False
        assert window._ctrl._playing is False
        
        # Verify that Earth's position was updated
        with window._sim._lock:
            earth_ref = window._sim.system.get_body("Earth")
            assert np.allclose(earth_ref.pos, [1.1, 0.0, 0.0])
            
    finally:
        window._date_timer.stop()
        window._sim.stop_thread()


def test_remove_body_pauses_and_updates_thread_safely(qapp, monkeypatch):
    sun = CelestialBody("Sun", 1.989e30, np.zeros(3), np.zeros(3), 695700, (1.0, 0.9, 0.2))
    earth = CelestialBody("Earth", 5.972e24, np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0172, 0.0]), 6371, (0.2, 0.5, 1.0))
    system = SolarSystem([sun, earth])
    
    window = MainWindow()
    window._load_system(system)
    
    try:
        window._sim.resume()
        window._ctrl.set_playing(True)
        assert window._sim.is_playing is True
        
        # Mock QMessageBox.question to return Yes
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
        
        # Execute _remove_selected after selecting Earth in list
        window._body_list._list.setCurrentRow(1) # earth is index 1
        window._remove_selected()
        
        # Verify paused state
        assert window._sim.is_playing is False
        assert window._ctrl._playing is False
        
        # Verify Earth removed
        with window._sim._lock:
            bodies = window._sim.system.bodies
            body_names = [b.name for b in bodies]
            assert "Earth" not in body_names
            
    finally:
        window._date_timer.stop()
        window._sim.stop_thread()
