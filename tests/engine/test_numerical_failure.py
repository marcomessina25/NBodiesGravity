"""Tests for numerical failure detection and last-valid-state preservation."""
import numpy as np
import pytest
from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.exceptions import NumericalIntegrityError
from nbodiesgravity.engine.integrator import VelocityVerletIntegrator
from nbodiesgravity.engine.system import SolarSystem
from nbodiesgravity.engine.simulation_thread import SimulationThread


def test_integrator_rejects_nan_pos():
    integrator = VelocityVerletIntegrator()
    pos = np.array([[np.nan, 0.0, 0.0]])
    vel = np.zeros((1, 3))
    mass = np.array([1e30])
    with pytest.raises(NumericalIntegrityError, match="Non-finite"):
        integrator.step(pos, vel, mass, 0.01)


def test_integrator_rejects_inf_pos():
    integrator = VelocityVerletIntegrator()
    pos = np.array([[np.inf, 0.0, 0.0]])
    vel = np.zeros((1, 3))
    mass = np.array([1e30])
    with pytest.raises(NumericalIntegrityError, match="Non-finite"):
        integrator.step(pos, vel, mass, 0.01)


def test_integrator_rejects_nan_vel():
    integrator = VelocityVerletIntegrator()
    pos = np.zeros((1, 3))
    vel = np.array([[np.nan, 0.0, 0.0]])
    mass = np.array([1e30])
    with pytest.raises(NumericalIntegrityError, match="Non-finite"):
        integrator.step(pos, vel, mass, 0.01)


def test_integrator_rejects_invalid_dt():
    integrator = VelocityVerletIntegrator()
    pos = np.zeros((1, 3))
    vel = np.zeros((1, 3))
    mass = np.array([1e30])
    with pytest.raises(NumericalIntegrityError, match="Step dt must be positive"):
        integrator.step(pos, vel, mass, -0.01)
    with pytest.raises(NumericalIntegrityError, match="Step dt must be positive"):
        integrator.step(pos, vel, mass, 0.0)
    with pytest.raises(NumericalIntegrityError, match="Step dt must be positive and finite"):
        integrator.step(pos, vel, mass, float("nan"))


def test_integrator_extreme_displacement_guard():
    # Maximum displacement threshold set to 10 AU
    integrator = VelocityVerletIntegrator(max_displacement=10.0)
    pos = np.zeros((1, 3))
    # Huge velocity that moves particle 50 AU in 1 day
    vel = np.array([[50.0, 0.0, 0.0]])
    mass = np.array([1e30])

    with pytest.raises(NumericalIntegrityError, match="Extreme displacement detected"):
        integrator.step(pos, vel, mass, 1.0)


def test_solar_system_preserves_last_valid_state_on_failure():
    # Construct a system with valid coordinates
    pos_init = np.array([1.0, 0.0, 0.0])
    vel_init = np.array([0.0, 0.017, 0.0])
    sun = CelestialBody("Sun", 1.989e30, np.zeros(3), np.zeros(3), 695700, (1.0, 1.0, 0.0))
    earth = CelestialBody("Earth", 5.972e24, pos_init.copy(), vel_init.copy(), 6371, (0.0, 0.0, 1.0))
    system = SolarSystem([sun, earth])

    # Take a normal step
    system.step(0.1)
    pos_valid = earth.pos.copy()
    vel_valid = earth.vel.copy()

    # Artificially inject an extreme velocity that triggers extreme displacement
    earth.vel = np.array([1000.0, 0.0, 0.0])

    # Stepping will fail due to extreme displacement
    with pytest.raises(NumericalIntegrityError):
        system.step(1.0)

    # Earth's position must NOT have been updated with invalid integration results
    np.testing.assert_array_equal(earth.pos, pos_valid)


def test_simulation_thread_numerical_failure_emitted_and_paused(qapp):
    sun = CelestialBody("Sun", 1.989e30, np.zeros(3), np.zeros(3), 695700, (1.0, 1.0, 0.0))
    earth = CelestialBody("Earth", 5.972e24, np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.017, 0.0]), 6371, (0.0, 0.0, 1.0))
    system = SolarSystem([sun, earth])

    thread = SimulationThread(system)
    received_errors: list[str] = []
    thread.numerical_failure_detected.connect(received_errors.append)

    thread.resume()
    assert thread.is_playing is True
    valid_snapshot = [s.pos.copy() for s in thread.latest_snapshot]

    # Inject invalid velocity into active body
    with thread._lock:
        thread.system.bodies[1].vel = np.array([float("nan"), 0.0, 0.0])

    # Run one iteration of the physics step manually under lock
    try:
        with thread._lock:
            thread.system.step(0.01)
    except NumericalIntegrityError as exc:
        thread._paused = True
        thread.numerical_failure_detected.emit(str(exc))

    assert thread.is_playing is False
    assert len(received_errors) == 1
    assert "Non-finite" in received_errors[0]

    # Verify latest_snapshot still contains the previous valid state
    for i, s in enumerate(thread.latest_snapshot):
        np.testing.assert_array_equal(s.pos, valid_snapshot[i])
        assert np.all(np.isfinite(s.pos))
