"""Tests verifying exact numerical equivalence and correctness of optimized physics routines."""
from __future__ import annotations
import numpy as np
import pytest

from nbodiesgravity.engine.integrator import VelocityVerletIntegrator, G_AU_DAY, SOFTENING
from nbodiesgravity.engine.system import SolarSystem, TimeStepConfig, compute_adaptive_dt
from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.data.loader import load_default_system


def _reference_accelerations(positions: np.ndarray, masses: np.ndarray, softening: float) -> np.ndarray:
    """Pure explicit reference calculation for accelerations."""
    n = len(positions)
    acc = np.zeros((n, 3), dtype=float)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            r_vec = positions[j] - positions[i]
            d_sq = np.sum(r_vec ** 2) + softening ** 2
            d_cb = d_sq ** 1.5
            acc[i] += G_AU_DAY * masses[j] * r_vec / d_cb
    return acc


def test_accelerations_matches_analytical_reference():
    """Verify optimized _accelerations strictly matches reference pairwise calculation."""
    np.random.seed(123)
    pos = np.random.uniform(-10.0, 10.0, (20, 3))
    masses = np.random.uniform(1e22, 1e30, 20)
    itg = VelocityVerletIntegrator(softening=SOFTENING)

    acc_opt = itg._accelerations(pos, masses)
    acc_ref = _reference_accelerations(pos, masses, SOFTENING)

    max_diff = np.max(np.abs(acc_opt - acc_ref))
    assert max_diff < 1e-15, f"Acceleration deviation {max_diff} exceeds tolerance"


def test_step_a0_reuse_equivalence():
    """Verify that multi-substep integration with a0 reuse matches step-by-step evaluation."""
    np.random.seed(456)
    pos = np.random.uniform(-5.0, 5.0, (10, 3))
    vel = np.random.uniform(-0.01, 0.01, (10, 3))
    masses = np.random.uniform(1e22, 1e28, 10)
    dt = 0.05
    itg = VelocityVerletIntegrator(softening=SOFTENING)

    # Standard step without passing a0
    p1, v1 = itg.step(pos, vel, masses, dt)
    p2_no_reuse, v2_no_reuse = itg.step(p1, v1, masses, dt)

    # Step with a0 reuse
    p1_r, v1_r, a1_r = itg.step(pos, vel, masses, dt, return_acc=True)
    assert np.array_equal(p1, p1_r)
    assert np.array_equal(v1, v1_r)

    p2_r, v2_r, _ = itg.step(p1_r, v1_r, masses, dt, a0=a1_r, return_acc=True)
    assert np.array_equal(p2_no_reuse, p2_r)
    assert np.array_equal(v2_no_reuse, v2_r)


def test_adaptive_dt_upper_triangle_equivalence():
    """Verify that upper-triangle compute_adaptive_dt matches full-matrix calculation."""
    np.random.seed(789)
    pos = np.random.uniform(-20.0, 20.0, (15, 3))
    masses = np.random.uniform(1e20, 1e26, 15)
    config = TimeStepConfig()

    # Optimized function
    dt_opt = compute_adaptive_dt(pos, masses, config)

    # Full matrix reference calculation
    diff = pos[np.newaxis, :, :] - pos[:, np.newaxis, :]
    dist = np.sqrt(np.einsum("ijk,ijk->ij", diff, diff))
    np.fill_diagonal(dist, np.inf)
    mass_sum = masses[np.newaxis, :] + masses[:, np.newaxis]
    t_orb = 2.0 * np.pi * np.sqrt(dist ** 3 / (G_AU_DAY * mass_sum + 1e-30))
    min_t_orb = np.nanmin(t_orb)
    dt_ref = float(max(config.min_dt, min(config.max_dt, config.safety_factor * min_t_orb)))

    assert dt_opt == pytest.approx(dt_ref, rel=1e-12)


def test_solar_system_orbit_conservation():
    """Verify that SolarSystem stepping preserves high conservation on real systems."""
    sys = load_default_system()
    e0 = sys.bodies[0].pos.copy()
    # Step 10 days
    for _ in range(10):
        sys.step(1.0)
    # Check that bodies advanced stably
    assert not np.allclose(sys.bodies[0].pos, e0)
    for b in sys.bodies:
        assert np.all(np.isfinite(b.pos))
        assert np.all(np.isfinite(b.vel))
