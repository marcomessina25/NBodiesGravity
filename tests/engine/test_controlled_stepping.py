"""Unit tests for controlled stepping, advance, max_simulation_time, and collision configs."""
from __future__ import annotations
import numpy as np
import pytest

from nbodiesgravity.engine.presets import get_preset
from nbodiesgravity.engine.system import SolarSystem
from nbodiesgravity.engine.simulation_thread import SimulationThread
from nbodiesgravity.engine.physics import PhysicsConfig, CollisionConfig
from nbodiesgravity.engine.body import CelestialBody


def test_system_step_once():
    preset = get_preset("circular_two_body")
    sys = preset.create_system()

    assert sys.cumulative_substeps == 0
    events = sys.step_once()
    assert sys.cumulative_substeps == 1
    assert sys.last_substeps == 1
    assert sys.last_adaptive_dt > 0.0

    # Step once with explicit dt
    events2 = sys.step_once(dt=0.01)
    assert sys.cumulative_substeps == 2
    assert sys.last_adaptive_dt == 0.01


def test_system_advance_duration():
    preset = get_preset("circular_two_body")
    sys = preset.create_system()

    sys.advance(5.0)
    assert sys.cumulative_substeps > 0


def test_collision_config_ignore_disables_merging():
    """Verify that setting collision_config.model='ignore' or enabled=False prevents merges."""
    b1 = CelestialBody("B1", 1e20, np.array([0.0, 0.0, 0.0]), np.array([0.0, 0.0, 0.0]), 1000.0, (255, 0, 0))
    b2 = CelestialBody("B2", 1e20, np.array([0.0, 0.0, 0.0]), np.array([0.0, 0.0, 0.0]), 1000.0, (0, 255, 0))

    sys = SolarSystem([b1, b2], collision_config=CollisionConfig(model="ignore"))
    events = sys.step(0.1)
    assert len(events) == 0
    assert len(sys.bodies) == 2

    sys_disabled = SolarSystem([b1, b2], collision_config=CollisionConfig(enabled=False))
    events_dis = sys_disabled.step(0.1)
    assert len(events_dis) == 0
    assert len(sys_disabled.bodies) == 2


def test_simulation_thread_controlled_stepping(qapp):
    preset = get_preset("circular_two_body")
    sys = preset.create_system()
    thread = SimulationThread(sys)

    assert thread.elapsed_days == 0.0
    thread.step_once()
    assert thread.elapsed_days > 0.0

    prev_days = thread.elapsed_days
    thread.advance(2.0)
    assert np.isclose(thread.elapsed_days, prev_days + 2.0)


def test_simulation_thread_max_simulation_time(qapp):
    """Verify that max_simulation_time halts the physics loop and emits target_time_reached."""
    import time
    preset = get_preset("circular_two_body")
    sys = preset.create_system()
    thread = SimulationThread(sys)
    thread.max_simulation_time = 0.2
    thread.set_timescale(50.0)

    target_times = []
    thread.target_time_reached.connect(target_times.append)

    thread.start()
    thread.resume()

    # Wait up to 3 seconds for target time to be reached
    start_wait = time.perf_counter()
    while thread.is_playing and time.perf_counter() - start_wait < 3.0:
        qapp.processEvents()
        time.sleep(0.01)

    thread.stop_thread()
    for _ in range(5):
        qapp.processEvents()

    assert not thread.is_playing
    assert len(target_times) >= 1
    assert np.isclose(thread.elapsed_days, 0.2, atol=1e-3)
    assert np.isclose(target_times[0], 0.2, atol=1e-3)


def test_simulation_thread_max_simulation_time_small_remainder(qapp):
    """Verify that a limit smaller than the natural frame step clamps cleanly without overshoot."""
    import time
    preset = get_preset("circular_two_body")
    sys = preset.create_system()
    thread = SimulationThread(sys)
    # A tiny limit: 0.002 days
    thread.max_simulation_time = 0.002
    thread.set_timescale(100.0)

    target_times = []
    thread.target_time_reached.connect(target_times.append)

    thread.start()
    thread.resume()

    start_wait = time.perf_counter()
    while thread.is_playing and time.perf_counter() - start_wait < 3.0:
        qapp.processEvents()
        time.sleep(0.01)

    thread.stop_thread()
    for _ in range(5):
        qapp.processEvents()

    assert not thread.is_playing
    assert len(target_times) >= 1
    assert np.isclose(thread.elapsed_days, 0.002, atol=1e-4)
    assert thread.elapsed_days <= 0.00201  # No overshoot


