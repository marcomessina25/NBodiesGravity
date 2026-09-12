"""Tests for TimeStepConfig, adaptive timestep calculation, and computational budget enforcement."""
import numpy as np
import pytest
from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.exceptions import ComputationalBudgetExceededError, NumericalIntegrityError
from nbodiesgravity.engine.system import SolarSystem, TimeStepConfig, compute_adaptive_dt


def test_timestep_config_defaults():
    config = TimeStepConfig()
    assert config.min_dt == 1e-5
    assert config.max_dt == 1.0
    assert config.safety_factor == 0.01
    assert config.max_substeps == 10_000


def test_timestep_config_validation():
    with pytest.raises(ValueError, match="min_dt must be positive"):
        TimeStepConfig(min_dt=0.0)
    with pytest.raises(ValueError, match="min_dt must be positive"):
        TimeStepConfig(min_dt=-1.0)
    with pytest.raises(ValueError, match="max_dt .* cannot be less than min_dt"):
        TimeStepConfig(min_dt=0.5, max_dt=0.1)
    with pytest.raises(ValueError, match="safety_factor must be positive"):
        TimeStepConfig(safety_factor=0.0)
    with pytest.raises(ValueError, match="max_substeps must be positive"):
        TimeStepConfig(max_substeps=0)


def test_compute_adaptive_dt_single_or_empty_body():
    config = TimeStepConfig(max_dt=2.5)
    # Empty
    dt = compute_adaptive_dt(np.zeros((0, 3)), np.zeros(0), config)
    assert dt == 2.5
    # Single body
    dt = compute_adaptive_dt(np.zeros((1, 3)), np.array([1.0]), config)
    assert dt == 2.5


def test_compute_adaptive_dt_bounds_and_determinism():
    config = TimeStepConfig(min_dt=1e-4, max_dt=0.5, safety_factor=0.01)
    pos = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    mass = np.array([1.989e30, 5.972e24])

    dt1 = compute_adaptive_dt(pos, mass, config)
    dt2 = compute_adaptive_dt(pos, mass, config)
    assert dt1 == dt2
    assert config.min_dt <= dt1 <= config.max_dt

    # Pathological close approach: distance very small
    pos_close = np.array([[0.0, 0.0, 0.0], [1e-8, 0.0, 0.0]])
    dt_close = compute_adaptive_dt(pos_close, mass, config)
    assert dt_close == config.min_dt

    # Wide separation: distance very large
    pos_wide = np.array([[0.0, 0.0, 0.0], [100.0, 0.0, 0.0]])
    dt_wide = compute_adaptive_dt(pos_wide, mass, config)
    assert dt_wide == config.max_dt


def test_max_substeps_budget_enforced():
    # Configure tiny min_dt and small max_substeps
    config = TimeStepConfig(min_dt=1e-4, max_dt=1.0, safety_factor=0.01, max_substeps=5)
    # Bodies placed very close to force min_dt (0.0001 days)
    b1 = CelestialBody("A", 1e30, np.zeros(3), np.zeros(3), 1.0, (1.0, 1.0, 1.0))
    b2 = CelestialBody("B", 1e24, np.array([1e-7, 0.0, 0.0]), np.zeros(3), 1.0, (1.0, 1.0, 1.0))
    system = SolarSystem([b1, b2], timestep_config=config)

    # dt = 1.0 day would require 10,000 substeps of 1e-4, but budget is 5
    with pytest.raises(ComputationalBudgetExceededError) as exc_info:
        system.step(1.0)

    assert "Maximum substeps (5) exceeded" in str(exc_info.value)


def test_state_preserved_when_budget_exceeded():
    config = TimeStepConfig(min_dt=1e-4, max_dt=1.0, safety_factor=0.01, max_substeps=2)
    pos_init_a = np.array([0.0, 0.0, 0.0])
    pos_init_b = np.array([1e-7, 0.0, 0.0])
    vel_init_b = np.array([0.0, 0.01, 0.0])

    b1 = CelestialBody("A", 1e30, pos_init_a.copy(), np.zeros(3), 1.0, (1.0, 1.0, 1.0))
    b2 = CelestialBody("B", 1e24, pos_init_b.copy(), vel_init_b.copy(), 1.0, (1.0, 1.0, 1.0))
    system = SolarSystem([b1, b2], timestep_config=config)

    with pytest.raises(ComputationalBudgetExceededError):
        system.step(1.0)

    # Initial states must remain untouched
    np.testing.assert_array_equal(system.bodies[0].pos, pos_init_a)
    np.testing.assert_array_equal(system.bodies[1].pos, pos_init_b)
    np.testing.assert_array_equal(system.bodies[1].vel, vel_init_b)


def test_invalid_dt_rejected():
    b = CelestialBody("A", 1e30, np.zeros(3), np.zeros(3), 1.0, (1.0, 1.0, 1.0))
    system = SolarSystem([b])

    with pytest.raises(NumericalIntegrityError, match="Step dt must be positive"):
        system.step(0.0)

    with pytest.raises(NumericalIntegrityError, match="Step dt must be positive"):
        system.step(-1.0)

    with pytest.raises(NumericalIntegrityError, match="Step dt must be finite"):
        system.step(float("nan"))

    with pytest.raises(NumericalIntegrityError, match="Step dt must be finite"):
        system.step(float("inf"))
