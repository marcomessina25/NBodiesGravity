import numpy as np
import pytest
from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.system import SolarSystem
from nbodiesgravity.engine.simulation_thread import SimulationThread


def _one_body_system() -> SolarSystem:
    body = CelestialBody(
        name="Earth", mass=5.972e24,
        pos=np.array([1.0, 0.0, 0.0]),
        vel=np.array([0.0, 0.01720, 0.0]),
        radius=6371.0, color=(0.2, 0.5, 1.0),
    )
    return SolarSystem([body])


def test_elapsed_days_zero_on_construction(qapp):
    thread = SimulationThread(_one_body_system())
    assert thread.elapsed_days == 0.0


def test_elapsed_days_property_reflects_internal_state(qapp):
    thread = SimulationThread(_one_body_system())
    thread._elapsed_days = 42.5
    assert thread.elapsed_days == 42.5


def test_elapsed_days_tracks_real_time(qapp):
    """Simulation must advance at ~timescale days per real second, not faster."""
    import time as _time
    thread = SimulationThread(_one_body_system())
    thread.set_timescale(1.0)   # 1 simulated day per real second
    thread.resume()
    thread.start()
    _time.sleep(0.15)           # run for ~150 ms
    thread.pause()
    thread.stop_thread()
    # Expected: ~0.15 days. Generous bounds accommodate CI scheduling jitter.
    assert 0.03 <= thread.elapsed_days <= 0.35, (
        f"elapsed_days={thread.elapsed_days:.4f} — loop is not real-time-bounded"
    )


def test_refresh_snapshot_updates_latest_snapshot(qapp):
    """Verify that calling refresh_snapshot() instantly updates the thread's latest_snapshot."""
    sys = _one_body_system()
    thread = SimulationThread(sys)
    assert len(thread.latest_snapshot) == 1
    assert thread.latest_snapshot[0].name == "Earth"

    # Add a new body to system while paused
    new_body = CelestialBody("Mars", 6e23, np.array([1.5, 0.0, 0.0]), np.zeros(3), 1.0, (1.0, 0.0, 0.0))
    sys.add_body(new_body)

    # Prior to refresh, snapshot should still be old
    assert len(thread.latest_snapshot) == 1

    # Force refresh
    thread.refresh_snapshot()
    assert len(thread.latest_snapshot) == 2
    assert thread.latest_snapshot[1].name == "Mars"


import time as _time


def test_collisions_detected_signal_emitted(qapp):
    from nbodiesgravity.engine.body import CelestialBody
    from nbodiesgravity.engine.system import SolarSystem
    from nbodiesgravity.engine.simulation_thread import SimulationThread

    a = CelestialBody("A", 2.0e30, np.zeros(3), np.zeros(3), 695700.0, (1.0, 1.0, 1.0))
    b = CelestialBody("B", 1.0e24, np.array([1e-4, 0.0, 0.0]), np.zeros(3), 6371.0, (0.0, 0.0, 1.0))
    system = SolarSystem([a, b])

    thread = SimulationThread(system)
    recorded: list = []
    thread.collisions_detected.connect(lambda evs: recorded.extend(evs))
    thread.set_timescale(1.0)
    thread.resume()
    thread.start()
    try:
        deadline = _time.time() + 5.0
        while not recorded and _time.time() < deadline:
            qapp.processEvents()
            _time.sleep(0.01)
    finally:
        thread.stop_thread()

    assert recorded, "collisions_detected was not emitted"
    assert recorded[0].absorbed == "B"
    assert recorded[0].survivor == "A"

