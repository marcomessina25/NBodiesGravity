"""Unit tests for LeapfrogIntegrator (Kick-Drift-Kick formulation)."""
from __future__ import annotations
import numpy as np
import pytest

from nbodiesgravity.engine.integrator import (
    LeapfrogIntegrator,
    SOFTENING,
    MAX_DISPLACEMENT_PER_STEP,
    G_AU_DAY,
)
from nbodiesgravity.engine.exceptions import NumericalIntegrityError


def test_leapfrog_creation_defaults():
    itg = LeapfrogIntegrator()
    assert itg.name == "leapfrog"
    assert itg.softening == SOFTENING
    assert itg.max_displacement == MAX_DISPLACEMENT_PER_STEP


def test_leapfrog_invalid_parameters():
    with pytest.raises(ValueError, match="softening"):
        LeapfrogIntegrator(softening=-1.0)
    with pytest.raises(ValueError, match="max_displacement"):
        LeapfrogIntegrator(max_displacement=0.0)


def test_leapfrog_single_step():
    itg = LeapfrogIntegrator()
    pos = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], dtype=float)
    vel = np.array([[0.0, 0.0, 0.0], [0.0, 0.017, 0.0]], dtype=float)
    masses = np.array([1.989e30, 5.972e24], dtype=float)

    new_pos, new_vel = itg.step(pos, vel, masses, dt=0.1)
    assert new_pos.shape == (2, 3)
    assert new_vel.shape == (2, 3)
    assert np.all(np.isfinite(new_pos))
    assert np.all(np.isfinite(new_vel))


def test_leapfrog_acceleration_reuse():
    itg = LeapfrogIntegrator()
    pos = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], dtype=float)
    vel = np.array([[0.0, 0.0, 0.0], [0.0, 0.017, 0.0]], dtype=float)
    masses = np.array([1.989e30, 5.972e24], dtype=float)

    # Step 1 without pre-computed a0
    p1, v1, a1 = itg.step(pos, vel, masses, dt=0.05, return_acc=True)

    # Step 2 using a1 as a0
    p2_reused, v2_reused = itg.step(p1, v1, masses, dt=0.05, a0=a1)

    # Step 2 without providing a0
    p2_direct, v2_direct = itg.step(p1, v1, masses, dt=0.05, a0=None)

    np.testing.assert_allclose(p2_reused, p2_direct, atol=1e-15, rtol=1e-15)
    np.testing.assert_allclose(v2_reused, v2_direct, atol=1e-15, rtol=1e-15)


def test_leapfrog_displacement_guard():
    itg = LeapfrogIntegrator(max_displacement=1.0)
    pos = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], dtype=float)
    vel = np.array([[0.0, 0.0, 0.0], [100.0, 0.0, 0.0]], dtype=float)   # 100 AU/day
    masses = np.array([1.0, 1.0], dtype=float)

    with pytest.raises(NumericalIntegrityError, match="Extreme displacement"):
        itg.step(pos, vel, masses, dt=1.0)


def test_leapfrog_numerical_failure():
    itg = LeapfrogIntegrator()
    pos = np.array([[0.0, 0.0, 0.0], [np.nan, 0.0, 0.0]], dtype=float)
    vel = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]], dtype=float)
    masses = np.array([1.0, 1.0], dtype=float)

    with pytest.raises(NumericalIntegrityError):
        itg.step(pos, vel, masses, dt=0.1)

    with pytest.raises(NumericalIntegrityError, match="positive and finite"):
        itg.step(np.zeros((2, 3)), np.zeros((2, 3)), masses, dt=-0.1)
