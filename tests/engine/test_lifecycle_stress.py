"""Threading and lifecycle stress tests for NBodiesGravity v1.0.

Verifies:
1. Rapid start -> pause -> resume -> pause -> reset -> close lifecycle.
2. Safe restart / system replacement while thread is running.
3. Clean thread shutdown without surviving worker threads.
4. Numerical failure containment in background thread.
"""
from __future__ import annotations
import time
import numpy as np
import pytest

from nbodiesgravity.engine import (
    CelestialBody,
    SolarSystem,
    TimeStepConfig,
    PhysicsConfig,
    VelocityVerletIntegrator,
    get_preset,
)
from nbodiesgravity.engine.simulation_thread import SimulationThread


def test_simulation_thread_rapid_lifecycle(qapp):
    """Stress test rapid start -> pause -> resume -> pause -> reset -> close sequence."""
    preset = get_preset("circular_two_body")
    sys = preset.create_system()
    thread = SimulationThread(sys)
    thread.set_timescale(100.0)

    # 1. Start & play
    thread.start()
    thread.resume()
    time.sleep(0.02)
    qapp.processEvents()
    assert thread.isRunning()
    assert thread.is_playing

    # 2. Pause
    thread.pause()
    time.sleep(0.01)
    qapp.processEvents()
    assert not thread.is_playing

    # 3. Resume
    thread.resume()
    time.sleep(0.02)
    qapp.processEvents()
    assert thread.is_playing

    # 4. Rapid pause / resume toggling
    for _ in range(5):
        thread.pause()
        qapp.processEvents()
        thread.resume()
        qapp.processEvents()

    # 5. Reset with a fresh system
    fresh_sys = get_preset("binary_star").create_system()
    thread.reset(fresh_sys)
    qapp.processEvents()
    assert thread.system.bodies[0].name == fresh_sys.bodies[0].name
    assert thread.elapsed_days == 0.0

    # 6. Stop and join
    thread.stop_thread()
    for _ in range(5):
        qapp.processEvents()
    assert not thread.isRunning()


def test_simulation_thread_clean_shutdown(qapp):
    """Verify that stop_thread guarantees the thread terminates and releases resources."""
    preset = get_preset("earth_moon")
    sys = preset.create_system()
    thread = SimulationThread(sys)

    thread.start()
    thread.resume()
    time.sleep(0.02)
    qapp.processEvents()

    thread.stop_thread()
    # Wait for thread termination
    stopped = thread.wait(2000)  # up to 2 seconds
    assert stopped
    assert not thread.isRunning()


def test_simulation_thread_numerical_blow_up_containment(qapp):
    """Verify that pathological distance expansion triggers blow_up_detected without crashing."""
    # Place two bodies, one starting beyond 1000 AU
    b1 = CelestialBody("Origin", 1e30, np.zeros(3), np.zeros(3), 1000.0, (1.0, 1.0, 1.0))
    b2 = CelestialBody("Escaped", 1e20, np.array([1005.0, 0.0, 0.0]), np.zeros(3), 100.0, (1.0, 1.0, 1.0))
    sys = SolarSystem([b1, b2])

    thread = SimulationThread(sys)
    thread.set_timescale(10.0)

    blow_up_detected = False

    def on_blow_up():
        nonlocal blow_up_detected
        blow_up_detected = True

    thread.blow_up_detected.connect(on_blow_up)

    thread.start()
    thread.resume()

    start_wait = time.perf_counter()
    while not blow_up_detected and time.perf_counter() - start_wait < 2.0:
        qapp.processEvents()
        time.sleep(0.01)

    thread.stop_thread()
    thread.wait(1000)

    assert blow_up_detected
    # Thread must be safely paused
    assert not thread.is_playing
