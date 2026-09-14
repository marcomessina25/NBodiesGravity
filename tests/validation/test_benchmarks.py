"""Tests validating the canonical benchmark systems A through F."""
import numpy as np
import pytest
from nbodiesgravity.engine.benchmarks import (
    create_free_particle,
    create_circular_two_body,
    create_eccentric_two_body,
    create_earth_sun,
    create_earth_moon,
    create_three_body_lagrange,
)
from nbodiesgravity.engine.diagnostics import ConservationTracker
from nbodiesgravity.engine.integrator import G_AU_DAY, VelocityVerletIntegrator


def test_benchmark_a_free_particle():
    """Benchmark A: Free particle moves at constant velocity with zero acceleration."""
    system = create_free_particle(pos=(1.0, 2.0, 3.0), vel=(0.1, -0.05, 0.02))
    p0 = system.bodies[0].pos.copy()
    v0 = system.bodies[0].vel.copy()

    dt = 10.0  # 10 days
    system.step(dt)

    expected_pos = p0 + v0 * dt
    np.testing.assert_allclose(system.bodies[0].pos, expected_pos, rtol=1e-12)
    np.testing.assert_allclose(system.bodies[0].vel, v0, rtol=1e-12)


def test_benchmark_b_circular_two_body():
    """Benchmark B: Two-body circular orbit maintains radius and bounded energy drift."""
    system = create_circular_two_body(m1=1.989e30, m2=5.972e24, r=1.0)
    tracker = ConservationTracker(system.bodies)

    # 1 orbital period: T = 2 * pi * sqrt(r^3 / (G * M))
    period = 2.0 * np.pi * np.sqrt(1.0 / (G_AU_DAY * (1.989e30 + 5.972e24)))
    assert 360.0 < period < 370.0

    # Advance by 1 full period in steps of 1 day
    days_elapsed = 0.0
    while days_elapsed < period:
        step_dt = min(1.0, period - days_elapsed)
        system.step(step_dt)
        days_elapsed += step_dt

    # Distance between bodies should still be ~1.0 AU
    dist = float(np.linalg.norm(system.bodies[1].pos - system.bodies[0].pos))
    assert dist == pytest.approx(1.0, rel=1e-3)

    report = tracker.evaluate(system.bodies)
    assert abs(report.energy_drift.rel_drift) < 1e-4
    assert report.normalized_momentum_drift < 1e-12


def test_benchmark_c_eccentric_two_body():
    """Benchmark C: Eccentric two-body orbit (e=0.5) reaches predicted apoapsis and conserves energy."""
    system = create_eccentric_two_body(m1=1.989e30, m2=5.972e24, a=1.0, e=0.5)
    tracker = ConservationTracker(system.bodies)

    period = 2.0 * np.pi * np.sqrt(1.0 / (G_AU_DAY * (1.989e30 + 5.972e24)))
    
    # Track min and max distance across one full orbit
    min_dist = float("inf")
    max_dist = 0.0
    t = 0.0
    while t < period:
        system.step(0.5)
        t += 0.5
        d = float(np.linalg.norm(system.bodies[1].pos - system.bodies[0].pos))
        min_dist = min(min_dist, d)
        max_dist = max(max_dist, d)

    # Periapsis r_p = a*(1-e) = 0.5 AU, Apoapsis r_a = a*(1+e) = 1.5 AU
    assert min_dist == pytest.approx(0.5, rel=1e-2)
    assert max_dist == pytest.approx(1.5, rel=1e-2)

    report = tracker.evaluate(system.bodies)
    assert abs(report.energy_drift.rel_drift) < 1e-3


def test_benchmark_d_earth_sun():
    """Benchmark D: Controlled Earth-Sun system completes 1 year and returns near start."""
    system = create_earth_sun()
    tracker = ConservationTracker(system.bodies)

    init_pos = system.bodies[1].pos.copy()
    # Advance 365.25 days
    days = 365.25
    t = 0.0
    while t < days:
        dt = min(1.0, days - t)
        system.step(dt)
        t += dt

    final_pos = system.bodies[1].pos
    # Earth returns near starting position (within 0.01 AU)
    assert np.linalg.norm(final_pos - init_pos) < 0.01

    report = tracker.evaluate(system.bodies)
    assert abs(report.energy_drift.rel_drift) < 1e-4


def test_benchmark_e_earth_moon():
    """Benchmark E: High-resolution Earth-Moon system completes ~1 orbit (~27.3 days)."""
    system = create_earth_moon()
    tracker = ConservationTracker(system.bodies)

    r_init = float(np.linalg.norm(system.bodies[1].pos - system.bodies[0].pos))

    # Advance 27.32 days
    period = 27.32
    t = 0.0
    while t < period:
        dt = min(0.25, period - t)
        system.step(dt)
        t += dt

    r_final = float(np.linalg.norm(system.bodies[1].pos - system.bodies[0].pos))
    assert r_final == pytest.approx(r_init, rel=5e-3)

    report = tracker.evaluate(system.bodies)
    assert abs(report.energy_drift.rel_drift) < 1e-3


def test_benchmark_f_three_body_lagrange():
    """Benchmark F: Lagrange equilateral triangle 3-body system rotates with preserved separation."""
    system = create_three_body_lagrange(mass=1.0e30, side=1.0)
    tracker = ConservationTracker(system.bodies)

    # Softened period T = 2 * pi / omega = 2 * pi * sqrt((L² + ε²)^1.5 / (3 * G * m))
    eps = system._integrator.softening
    omega = float(np.sqrt(3.0 * G_AU_DAY * 1.0e30 / ((1.0 + eps ** 2) ** 1.5)))
    period = 2.0 * np.pi / omega

    # Advance for half a period
    t = 0.0
    target = period * 0.5
    while t < target:
        dt = min(1.0, target - t)
        system.step(dt)
        t += dt

    # Check pairwise separations: all should remain 1.0 AU
    p0, p1, p2 = [b.pos for b in system.bodies]
    d01 = float(np.linalg.norm(p0 - p1))
    d12 = float(np.linalg.norm(p1 - p2))
    d20 = float(np.linalg.norm(p2 - p0))

    assert d01 == pytest.approx(1.0, rel=1e-3)
    assert d12 == pytest.approx(1.0, rel=1e-3)
    assert d20 == pytest.approx(1.0, rel=1e-3)

    report = tracker.evaluate(system.bodies)
    assert abs(report.energy_drift.rel_drift) < 1e-4
    assert report.normalized_momentum_drift < 1e-12


def test_benchmark_f_exact_softened_equilibrium():
    """Verify that Benchmark F initializes in exact centripetal equilibrium under softened gravity."""
    system = create_three_body_lagrange(mass=1.0e30, side=1.0, softening=1e-4)
    pos = np.array([b.pos for b in system.bodies])
    masses = np.array([b.mass for b in system.bodies])
    eps = system._integrator.softening
    integrator = VelocityVerletIntegrator(softening=eps)
    acc = integrator._accelerations(pos, masses)

    omega_sq = 3.0 * G_AU_DAY * 1.0e30 / ((1.0 + eps ** 2) ** 1.5)
    expected_acc = - omega_sq * pos

    assert np.allclose(acc, expected_acc, rtol=1e-12, atol=1e-15)

