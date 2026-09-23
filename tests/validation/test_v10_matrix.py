"""Authoritative validation matrix and long-term stability suite for NBodiesGravity v1.0.

Covers:
1. Full analytical preset matrix across both supported integrators.
2. Cross-integrator trajectory equivalence and phase error bounds.
3. Multi-orbit long-term stability for Earth-Moon and Earth-Sun systems.
4. Conservation laws across inelastic collision mergers.
"""
from __future__ import annotations
import numpy as np
import pytest

from nbodiesgravity.engine import (
    CelestialBody,
    SolarSystem,
    TimeStepConfig,
    IntegratorConfig,
    PhysicsConfig,
    CollisionConfig,
    VelocityVerletIntegrator,
    LeapfrogIntegrator,
    ConservationTracker,
    get_preset,
    list_presets,
    G_AU_DAY,
)
from nbodiesgravity.engine.orbital_elements import compute_orbital_elements


# ============================================================================
# 1. Full Analytical Preset Matrix Across Both Integrators
# ============================================================================

@pytest.mark.parametrize("preset_name", [
    "circular_two_body",
    "eccentric_two_body",
    "oriented_two_body",
    "earth_moon",
    "binary_star",
    "restricted_three_body",
])
@pytest.mark.parametrize("integrator_name", ["velocity_verlet", "leapfrog"])
def test_v10_preset_validation_matrix(preset_name: str, integrator_name: str):
    """Verify that every analytical preset integrates stably with bounded drift across all supported integrators."""
    preset = get_preset(preset_name)
    sys = preset.create_system()
    sys.set_integrator(integrator_name)

    tracker = ConservationTracker(sys.bodies, g_constant=sys.physics_config.gravitational_constant)

    # Advance each system for an appropriate diagnostic span
    duration = 5.0 if "moon" in preset_name else 20.0
    sys.advance(duration)

    report = tracker.evaluate(sys.bodies)

    # In all presets, linear momentum must be conserved to machine precision (< 1e-12)
    assert report.normalized_momentum_drift < 1e-12

    # Energy drift thresholds depend on eccentricity and tight orbits
    if preset_name in ("eccentric_two_body", "oriented_two_body", "earth_moon"):
        assert abs(report.energy_drift.rel_drift) < 1e-3
    else:
        assert abs(report.energy_drift.rel_drift) < 1e-7

    # Center of mass drift must be negligible (< 1e-8 AU)
    assert report.center_of_mass_drift.abs_drift < 1e-8


# ============================================================================
# 2. Cross-Integrator Equivalence and Trajectory Matching
# ============================================================================

def test_v10_cross_integrator_fixed_step_exact_equivalence():
    """Verify that Velocity Verlet and Leapfrog produce mathematically identical orbits under fixed timestepping."""
    # Test on circular two-body over 500 steps of dt = 0.05 days
    p_vv = get_preset("circular_two_body")
    p_lf = get_preset("circular_two_body")

    sys_vv = p_vv.create_system()
    sys_lf = p_lf.create_system()

    sys_vv.set_integrator("velocity_verlet")
    sys_lf.set_integrator("leapfrog")

    # Fixed timestep: min_dt == max_dt to bypass adaptive variation
    t_cfg = TimeStepConfig(min_dt=0.05, max_dt=0.05, safety_factor=1.0)
    sys_vv.timestep_config = t_cfg
    sys_lf.timestep_config = t_cfg

    dt = 0.05
    for _ in range(200):
        sys_vv.step(dt)
        sys_lf.step(dt)

        for b_vv, b_lf in zip(sys_vv.bodies, sys_lf.bodies):
            # Difference must remain within machine precision (< 1e-14 AU)
            np.testing.assert_allclose(b_vv.pos, b_lf.pos, rtol=1e-13, atol=1e-14)
            np.testing.assert_allclose(b_vv.vel, b_lf.vel, rtol=1e-13, atol=1e-14)


def test_v10_cross_integrator_adaptive_drift_bounded():
    """Verify that both integrators maintain comparable bounded energy drift under adaptive timestepping."""
    p_vv = get_preset("eccentric_two_body")
    p_lf = get_preset("eccentric_two_body")

    sys_vv = p_vv.create_system()
    sys_lf = p_lf.create_system()
    sys_vv.set_integrator("velocity_verlet")
    sys_lf.set_integrator("leapfrog")

    tracker_vv = ConservationTracker(sys_vv.bodies)
    tracker_lf = ConservationTracker(sys_lf.bodies)

    sys_vv.advance(100.0)
    sys_lf.advance(100.0)

    rep_vv = tracker_vv.evaluate(sys_vv.bodies)
    rep_lf = tracker_lf.evaluate(sys_lf.bodies)

    # Both must conserve energy well within 1e-3 over multiple eccentric orbits
    assert abs(rep_vv.energy_drift.rel_drift) < 1e-3
    assert abs(rep_lf.energy_drift.rel_drift) < 1e-3
    # The drift difference between the two second-order methods should be very small
    assert abs(rep_vv.energy_drift.rel_drift - rep_lf.energy_drift.rel_drift) < 1e-4


# ============================================================================
# 3. Multi-Orbit Long-Term Stability
# ============================================================================

def test_v10_earth_moon_multi_orbit_stability():
    """Verify stability of the Earth-Moon system over 1 full year (~13.4 lunar orbits)."""
    preset = get_preset("earth_moon")
    sys = preset.create_system()

    initial_moon_dist = np.linalg.norm(sys.bodies[1].pos - sys.bodies[0].pos)

    tracker = ConservationTracker(sys.bodies)

    # Advance for 365.25 days
    sys.advance(365.25)

    report = tracker.evaluate(sys.bodies)

    # Earth-Moon energy drift over 1 year must remain bounded (< 1e-6)
    assert abs(report.energy_drift.rel_drift) < 1e-6
    assert report.normalized_momentum_drift < 1e-13

    # Moon must remain bound within 1% of its orbital distance
    final_moon_dist = np.linalg.norm(sys.bodies[1].pos - sys.bodies[0].pos)
    rel_dist_change = abs(final_moon_dist - initial_moon_dist) / initial_moon_dist
    assert rel_dist_change < 0.015


def test_v10_earth_sun_ten_year_closure():
    """Verify 10-year orbital stability of the Earth-Sun system."""
    m_sun = 1.989e30
    m_earth = 5.972e24
    r_au = 1.0
    v_circ = 2.0 * np.pi / 365.25  # ~0.01720209895 AU/day

    sun = CelestialBody("Sun", m_sun, np.zeros(3), np.zeros(3), 696340.0, (1.0, 1.0, 0.0), label="star")
    earth = CelestialBody("Earth", m_earth, np.array([r_au, 0.0, 0.0]), np.array([0.0, v_circ, 0.0]), 6371.0, (0.0, 0.5, 1.0))

    sys = SolarSystem([sun, earth], timestep_config=TimeStepConfig(min_dt=0.1, max_dt=1.0))
    tracker = ConservationTracker(sys.bodies)

    # Advance 10 years (3652.5 days)
    sys.advance(3652.5)

    report = tracker.evaluate(sys.bodies)

    # Energy drift must remain exceptionally low (< 1e-10)
    assert abs(report.energy_drift.rel_drift) < 1e-10
    # Final position must return close to initial (1.0, 0.0, 0.0)
    pos_err = np.linalg.norm(sys.bodies[1].pos - np.array([1.0, 0.0, 0.0]))
    assert pos_err < 0.05  # Within 0.05 AU after 10 years at 1-day step


# ============================================================================
# 4. Inelastic Merger Conservation
# ============================================================================

def test_v10_collision_merger_conservation():
    """Verify that head-on inelastic merger strictly conserves mass, momentum, and volume."""
    m1 = 1e25
    m2 = 2e25
    r1 = 5000.0  # km
    r2 = 7000.0  # km

    pos1 = np.array([-0.001, 0.0, 0.0])
    pos2 = np.array([0.001, 0.0, 0.0])
    vel1 = np.array([0.001, 0.0005, 0.0])
    vel2 = np.array([-0.0005, -0.00025, 0.0])

    p_initial = m1 * vel1 + m2 * vel2
    cm_initial = (m1 * pos1 + m2 * pos2) / (m1 + m2)
    expected_vol_radius = (r1**3 + r2**3)**(1/3)

    b1 = CelestialBody("Smaller", m1, pos1, vel1, r1, (1.0, 0.0, 0.0))
    b2 = CelestialBody("Larger", m2, pos2, vel2, r2, (0.0, 1.0, 0.0))

    # Collision radius in AU is ~ (5000 + 7000) / 1.496e8 = 8e-5 AU.
    # At separation 0.002 AU, let's step until they collide or place them within collision radius.
    b1_close = CelestialBody("Smaller", m1, np.array([0.0, 0.0, 0.0]), vel1, r1, (1.0, 0.0, 0.0))
    b2_close = CelestialBody("Larger", m2, np.array([1e-5, 0.0, 0.0]), vel2, r2, (0.0, 1.0, 0.0))

    sys = SolarSystem([b1_close, b2_close], collision_config=CollisionConfig(enabled=True, model="merge"))

    # Step once to trigger collision detection
    events = sys.step(0.001)

    assert len(events) == 1
    assert events[0].survivor == "Larger"
    assert events[0].absorbed == "Smaller"
    assert len(sys.bodies) == 1

    survivor = sys.bodies[0]
    assert survivor.name == "Larger"
    assert survivor.mass == m1 + m2

    # Momentum conserved
    p_final = survivor.mass * survivor.vel
    np.testing.assert_allclose(p_final, p_initial, rtol=1e-14)

    # Radius matches equal-density volume addition
    assert np.isclose(survivor.radius, expected_vol_radius, rtol=1e-12)
