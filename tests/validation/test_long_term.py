"""Long-term orbital stability validation experiments over multi-year and multi-orbit timescales."""
import numpy as np
import pytest
from nbodiesgravity.engine.benchmarks import create_earth_sun, create_earth_moon
from nbodiesgravity.engine.diagnostics import ConservationTracker


def test_earth_sun_ten_year_stability():
    """Simulate Earth-Sun for 10 years (3,652.5 days) and measure stability and conservation."""
    system = create_earth_sun()
    tracker = ConservationTracker(system.bodies)

    total_days = 3652.5  # 10 Julian years
    dt_step = 1.0        # 1 day steps
    t = 0.0

    min_dist = float("inf")
    max_dist = 0.0

    while t < total_days - 1e-9:
        dt = min(dt_step, total_days - t)
        system.step(dt)
        t += dt

        d = float(np.linalg.norm(system.bodies[1].pos - system.bodies[0].pos))
        min_dist = min(min_dist, d)
        max_dist = max(max_dist, d)

    # 1. Earth radius remained stable within 1% of 1.0 AU over 10 years
    assert min_dist > 0.99
    assert max_dist < 1.01

    report = tracker.evaluate(system.bodies)
    # 2. Energy drift bounded < 1e-4 over 10 years (no secular energy explosion)
    assert abs(report.energy_drift.rel_drift) < 1e-4
    # 3. Momentum conservation conserved to machine precision
    assert report.normalized_momentum_drift < 1e-11
    # 4. Angular momentum conserved
    assert abs(report.angular_momentum_drift.rel_drift) < 1e-5


def test_earth_moon_multi_orbit_stability():
    """Simulate Earth-Moon system for 5 lunar months (~136.6 days) with adaptive stepping."""
    system = create_earth_moon()
    tracker = ConservationTracker(system.bodies)

    total_days = 136.6  # 5 lunar periods
    t = 0.0
    dt_step = 0.25      # 0.25 day steps
    
    r_initial = float(np.linalg.norm(system.bodies[1].pos - system.bodies[0].pos))
    min_dist = float("inf")
    max_dist = 0.0

    while t < total_days - 1e-9:
        dt = min(dt_step, total_days - t)
        system.step(dt)
        t += dt

        d = float(np.linalg.norm(system.bodies[1].pos - system.bodies[0].pos))
        min_dist = min(min_dist, d)
        max_dist = max(max_dist, d)

    # Moon stays tightly bound within 2% of initial separation
    assert min_dist > 0.98 * r_initial
    assert max_dist < 1.02 * r_initial

    report = tracker.evaluate(system.bodies)
    assert abs(report.energy_drift.rel_drift) < 1e-3
    assert report.normalized_momentum_drift < 1e-10
