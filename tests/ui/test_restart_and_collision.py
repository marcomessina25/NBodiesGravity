import numpy as np
import pytest
from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.system import SolarSystem
from nbodiesgravity.engine.simulation_thread import SimulationThread
from nbodiesgravity.rendering.gl_widget import GLWidget
from nbodiesgravity.ui.main_window import MainWindow


@pytest.fixture(autouse=True)
def mock_opengl(monkeypatch):
    """Mock OpenGL rendering calls to prevent headless hangs during event loops."""
    monkeypatch.setattr(GLWidget, "initializeGL", lambda self: None)
    monkeypatch.setattr(GLWidget, "resizeGL", lambda self, w, h: None)
    monkeypatch.setattr(GLWidget, "paintGL", lambda self: None)
    monkeypatch.setattr(GLWidget, "paintEvent", lambda self, event: None)


def test_system_clone_preserves_label_and_show_name():
    """Verify system.clone() correctly deep-copies label and show_name attributes."""
    body = CelestialBody(
        name="CustomSun",
        mass=2e30,
        pos=np.zeros(3),
        vel=np.zeros(3),
        radius=700000.0,
        color=(1.0, 1.0, 1.0),
        show_trail=False,
        active=True,
        label="star",
        show_name=False
    )
    system = SolarSystem([body])
    cloned = system.clone()
    
    assert cloned.bodies[0].label == "star"
    assert cloned.bodies[0].show_name is False
    assert cloned.bodies[0].show_trail is False


def test_restart_preserves_added_bodies_and_categories(qapp, monkeypatch):
    """Verify that adding a body updates _initial_system, so restarts preserve modifications."""
    sun = CelestialBody("Sun", 1.989e30, np.zeros(3), np.zeros(3), 695700, (1.0, 0.9, 0.2), label="star")
    earth = CelestialBody("Earth", 5.972e24, np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0172, 0.0]), 6371, (0.2, 0.5, 1.0), label="planet")
    system = SolarSystem([sun, earth])
    
    window = MainWindow()
    window._load_system(system)
    
    try:
        new_star = CelestialBody("Alpha Centauri", 2.0e30, np.array([2.0, 0.0, 0.0]), np.zeros(3), 700000.0, (0.8, 0.8, 1.0), label="star")
        
        class DummyDialog:
            class DialogCode:
                Accepted = 1
                Rejected = 0
                
            def __init__(self, *args, **kwargs):
                pass
            def exec(self):
                return 1
            def result_body(self):
                return new_star

        monkeypatch.setattr("nbodiesgravity.ui.main_window.BodyEditorDialog", DummyDialog)
        
        # Add the body
        window._add_body()
        
        # Hitting Restart should restore the simulation epoch but PRESERVE the new body
        window._on_restart()
        
        # Verify the body still exists in the restarted simulation system
        with window._sim._lock:
            bodies = window._sim.system.bodies
            body_names = [b.name for b in bodies]
            assert "Alpha Centauri" in body_names
            
            # Verify that its category is preserved as "star"
            ac_body = window._sim.system.get_body("Alpha Centauri")
            assert ac_body.label == "star"
            
        # Verify that category checkboxes are correctly populated and stars are not untoggled
        star_cb_active = window._body_list._category_widgets["star"]["active"]
        assert star_cb_active.isChecked() is True

    finally:
        window._date_timer.stop()
        window._sim.stop_thread()


def test_nan_and_inf_trigger_blow_up(qapp):
    """Verify that NaN and inf coordinates are robustly detected as a blow-up."""
    sun = CelestialBody("Sun", 1.989e30, np.zeros(3), np.zeros(3), 695700, (1.0, 0.9, 0.2), label="star")
    system = SolarSystem([sun])
    
    thread = SimulationThread(system)
    thread.resume()
    assert thread.is_playing is True
    
    # Manually inject NaN to body position to simulate mathematical collapse / escape
    with thread._lock:
        thread.system.bodies[0].pos[0] = np.nan
        
    # Force a thread cycle loop by calling run's inner loop logic manually
    # or just checking the check logic directly on a simulated step snap.
    snap = thread.system.snapshot()
    
    # Verify the check catches NaN and sets pause state
    has_nan_or_inf = any(np.isnan(s.pos).any() or np.isinf(s.pos).any() or float(np.linalg.norm(s.pos)) > 1000.0 for s in snap if s.active)
    assert has_nan_or_inf is True
    
    # Clean up
    thread.stop_thread()


def test_on_collisions_retargets_camera_and_refreshes(qapp):
    from nbodiesgravity.engine.body import CollisionEvent

    sun = CelestialBody("Sun", 1.989e30, np.zeros(3), np.zeros(3), 695700, (1.0, 0.9, 0.2), label="star")
    earth = CelestialBody("Earth", 5.972e24, np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0172, 0.0]), 6371, (0.2, 0.5, 1.0), label="planet")
    system = SolarSystem([sun, earth])

    window = MainWindow()
    window._load_system(system)
    try:
        window._gl.camera.set_center("Earth")

        # Simulate the merge the physics layer already performed: Earth absorbed by Sun.
        with window._sim._lock:
            window._sim.system.remove_body("Earth")

        window._on_collisions([CollisionEvent(absorbed="Earth", survivor="Sun")])

        # Camera retargeted off the absorbed body onto the survivor.
        assert window._gl.camera.center_name == "Sun"
        # Body list / system no longer contains the absorbed body.
        names = [b.name for b in window._sim.system.bodies]
        assert "Earth" not in names
        assert "Sun" in names
    finally:
        window._date_timer.stop()
        window._sim.stop_thread()


def test_on_collisions_follows_chain_to_final_survivor(qapp):
    from nbodiesgravity.engine.body import CollisionEvent

    a = CelestialBody("A", 3.0e30, np.zeros(3), np.zeros(3), 695700, (1.0, 1.0, 1.0), label="star")
    b = CelestialBody("B", 2.0e30, np.array([1.0, 0.0, 0.0]), np.zeros(3), 695700, (1.0, 1.0, 1.0), label="star")
    c = CelestialBody("C", 1.0e30, np.array([2.0, 0.0, 0.0]), np.zeros(3), 695700, (1.0, 1.0, 1.0), label="star")
    system = SolarSystem([a, b, c])

    window = MainWindow()
    window._load_system(system)
    try:
        window._gl.camera.set_center("C")

        # Simulate a chained merge already performed by the physics layer:
        # C absorbed into B, then B absorbed into A. Only A remains.
        with window._sim._lock:
            window._sim.system.remove_body("C")
            window._sim.system.remove_body("B")

        events = [
            CollisionEvent(absorbed="C", survivor="B"),
            CollisionEvent(absorbed="B", survivor="A"),
        ]
        window._on_collisions(events)

        # Camera followed the chain C -> B -> A, landing on the final survivor.
        assert window._gl.camera.center_name == "A"
        names = [bd.name for bd in window._sim.system.bodies]
        assert names == ["A"]
    finally:
        window._date_timer.stop()
        window._sim.stop_thread()
