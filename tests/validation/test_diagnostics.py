"""Tests for engine conservation diagnostics module."""
import numpy as np
import pytest
from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.diagnostics import (
    compute_kinetic_energy,
    compute_potential_energy,
    compute_total_energy,
    compute_linear_momentum,
    compute_angular_momentum,
    compute_center_of_mass,
    compute_snapshot,
    compute_drift,
    ConservationTracker,
)
from nbodiesgravity.engine.integrator import G_AU_DAY


def test_kinetic_energy_analytic():
    masses = np.array([2.0, 3.0])
    vels = np.array([[1.0, 0.0, 0.0], [0.0, 2.0, 0.0]])
    # KE = 0.5 * (2.0 * 1.0^2 + 3.0 * 2.0^2) = 0.5 * (2 + 12) = 7.0
    ke = compute_kinetic_energy(masses, vels)
    assert ke == pytest.approx(7.0)


def test_potential_energy_analytic():
    m1, m2 = 1e30, 2e30
    masses = np.array([m1, m2])
    positions = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    softening = 1e-4

    expected = - (G_AU_DAY * m1 * m2) / np.sqrt(1.0**2 + softening**2)
    pe = compute_potential_energy(positions, masses, softening=softening)
    assert pe == pytest.approx(expected, rel=1e-12)


def test_linear_momentum_analytic():
    masses = np.array([10.0, 20.0])
    vels = np.array([[1.0, 2.0, 3.0], [-1.0, 0.0, 1.0]])
    # P = 10*[1, 2, 3] + 20*[-1, 0, 1] = [-10, 20, 50]
    p = compute_linear_momentum(masses, vels)
    np.testing.assert_allclose(p, np.array([-10.0, 20.0, 50.0]))


def test_angular_momentum_analytic():
    mass = np.array([2.0])
    pos = np.array([[1.0, 0.0, 0.0]])
    vel = np.array([[0.0, 3.0, 0.0]])
    # L = 2.0 * ([1, 0, 0] x [0, 3, 0]) = 2.0 * [0, 0, 3] = [0, 0, 6]
    l = compute_angular_momentum(pos, vel, mass)
    np.testing.assert_allclose(l, np.array([0.0, 0.0, 6.0]))


def test_center_of_mass_analytic():
    masses = np.array([1.0, 3.0])
    pos = np.array([[0.0, 0.0, 0.0], [4.0, 0.0, 0.0]])
    # R_cm = (1*0 + 3*4) / 4 = 12 / 4 = 3.0
    cm = compute_center_of_mass(pos, masses)
    np.testing.assert_allclose(cm, np.array([3.0, 0.0, 0.0]))


def test_drift_calculation():
    # Scalar drift
    drift = compute_drift(100.0, 101.0)
    assert drift.initial == 100.0
    assert drift.current == 101.0
    assert drift.abs_drift == pytest.approx(1.0)
    assert drift.rel_drift == pytest.approx(0.01)

    # Vector drift
    init_v = np.array([1.0, 0.0, 0.0])
    curr_v = np.array([1.0, 0.1, 0.0])
    drift_v = compute_drift(init_v, curr_v)
    assert drift_v.abs_drift[1] == pytest.approx(0.1)
    assert drift_v.rel_drift == pytest.approx(0.1)


def test_conservation_tracker_with_bodies():
    b1 = CelestialBody("A", 1e30, np.zeros(3), np.zeros(3), 1.0, (1.0, 1.0, 1.0))
    b2 = CelestialBody("B", 1e24, np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.017, 0.0]), 1.0, (1.0, 1.0, 1.0))

    tracker = ConservationTracker([b1, b2])
    # Evaluating identical state gives zero drifts
    report = tracker.evaluate([b1, b2])
    assert report.energy_drift.rel_drift == pytest.approx(0.0)
    assert report.linear_momentum_drift.rel_drift == pytest.approx(0.0)
    assert report.angular_momentum_drift.rel_drift == pytest.approx(0.0)
    assert report.center_of_mass_drift.rel_drift == pytest.approx(0.0)
