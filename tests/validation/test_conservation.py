"""Validation suite for mechanical conservation laws across canonical and Solar System configurations."""
import numpy as np
import pytest
from nbodiesgravity.data.loader import load_default_system
from nbodiesgravity.engine.benchmarks import (
    create_circular_two_body,
    create_eccentric_two_body,
    create_three_body_lagrange,
    create_earth_sun,
)
from nbodiesgravity.engine.diagnostics import (
    ConservationTracker,
    compute_potential_energy,
    compute_total_energy,
)
from nbodiesgravity.engine.integrator import G_AU_DAY, SOFTENING


def test_energy_conservation_circular_orbit():
    """Verify energy drift is bounded < 1e-4 over a full orbit for circular 2-body."""
    system = create_circular_two_body(m1=1.989e30, m2=5.972e24, r=1.0)
    tracker = ConservationTracker(system.bodies)

    # 1 full year in 0.5 day steps
    for _ in range(730):
        system.step(0.5)

    report = tracker.evaluate(system.bodies)
    assert abs(report.energy_drift.rel_drift) < 1e-4
    assert report.normalized_momentum_drift < 1e-12
    assert report.center_of_mass_drift.abs_drift < 1e-12


def test_energy_conservation_eccentric_orbit():
    """Verify energy drift is bounded < 5e-4 over an eccentric orbit (e=0.5)."""
    system = create_eccentric_two_body(m1=1.989e30, m2=5.972e24, a=1.0, e=0.5)
    tracker = ConservationTracker(system.bodies)

    for _ in range(730):
        system.step(0.5)

    report = tracker.evaluate(system.bodies)
    assert abs(report.energy_drift.rel_drift) < 5e-4
    assert report.normalized_momentum_drift < 1e-12


def test_angular_momentum_conservation():
    """Verify angular momentum is conserved for isolated 3-body system."""
    system = create_three_body_lagrange(mass=1.0e30, side=1.0)
    tracker = ConservationTracker(system.bodies)

    for _ in range(100):
        system.step(1.0)

    report = tracker.evaluate(system.bodies)
    assert abs(report.angular_momentum_drift.rel_drift) < 1e-4
    assert report.normalized_momentum_drift < 1e-12


def test_solar_system_conservation_short_horizon():
    """Verify full 39-body Solar System maintains momentum and energy conservation over 30 days."""
    system = load_default_system()
    tracker = ConservationTracker(system.bodies)

    for _ in range(30):
        system.step(1.0)

    report = tracker.evaluate(system.bodies)
    # Energy drift for 39 real Solar System bodies over 30 days is < 1e-4
    assert abs(report.energy_drift.rel_drift) < 1e-4
    # Center of mass remains fixed in barycentric frame
    assert report.center_of_mass_drift.abs_drift < 1e-6
    # Normalized momentum drift is near floating point precision
    assert report.normalized_momentum_drift < 1e-10


def test_softened_potential_consistency_with_force():
    """Verify numerical gradient of softened potential equals negative force."""
    m1 = 1.989e30
    m2 = 5.972e24
    masses = np.array([m1, m2])
    softening = 1e-4
    r0 = 1.0
    h = 1e-7

    # Potential at r0 - h and r0 + h
    pos_minus = np.array([[0.0, 0.0, 0.0], [r0 - h, 0.0, 0.0]])
    pos_plus = np.array([[0.0, 0.0, 0.0], [r0 + h, 0.0, 0.0]])
    u_minus = compute_potential_energy(pos_minus, masses, softening=softening)
    u_plus = compute_potential_energy(pos_plus, masses, softening=softening)

    # dU/dr via central differences
    du_dr = (u_plus - u_minus) / (2.0 * h)

    # Analytical force magnitude F = G * m1 * m2 * r / (r² + ε²)^1.5
    # F = - dU/dr, so du_dr should equal + F_magnitude
    f_expected = G_AU_DAY * m1 * m2 * r0 / ((r0 ** 2 + softening ** 2) ** 1.5)

    assert du_dr == pytest.approx(f_expected, rel=1e-6)
