"""Scientific verification tests for dynamical stability assessment and ejection detection."""
import numpy as np
import pytest

from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.integrator import G_AU_DAY
from nbodiesgravity.engine.stability import (
    EscapeConfig,
    EjectionEvent,
    StabilityStatus,
    assess_stability,
    find_ejected_index,
    _holman_wiegert_s,
    _holman_wiegert_p,
    HILL_UNSTABLE_DELTA,
)
from nbodiesgravity.engine.system import SolarSystem


def test_escape_config_validation():
    cfg = EscapeConfig(min_distance_au=500.0, extent_factor=3.0)
    assert cfg.min_distance_au == 500.0
    assert cfg.extent_factor == 3.0

    with pytest.raises(ValueError):
        EscapeConfig(min_distance_au=-10.0)

    with pytest.raises(ValueError):
        EscapeConfig(extent_factor=0.5)


def test_find_ejected_index_cases_a_through_f():
    """Verify that being far away is NOT the same as being ejected.

    An object is ejected if and only if:
    (r > min_dist) AND (r > extent_factor * extent) AND (rad_vel > 0) AND (specific_energy >= 0).
    """
    cfg = EscapeConfig(min_distance_au=1000.0, extent_factor=5.0)
    m_sun = 1.989e30
    m_planet = 1e24

    # Two-body system: Sun at origin, planet tested at various distances/velocities
    # System extent is defined by the remaining bodies (Sun at origin, extent = 0; if multiple, actual extent)
    # We add an inner planet at 1.0 AU so the remaining system extent is 1.0 AU.
    pos_sun = np.array([0.0, 0.0, 0.0])
    vel_sun = np.array([0.0, 0.0, 0.0])
    pos_earth = np.array([1.0, 0.0, 0.0])
    vel_earth = np.array([0.0, 0.0172, 0.0])
    m_earth = 5.972e24

    # Escape velocity at 1005 AU is v_esc = sqrt(2 * G * M / r) ~ 7.67e-4 AU/day
    v_esc_1005 = np.sqrt(2.0 * G_AU_DAY * (m_sun + m_earth) / 1005.0)

    # Case A: Distant but bound (r > 1000 AU, rad_vel >= 0, specific_energy < 0)
    # Subcase A1: v = 0 (bound, v < v_esc) -> NOT EJECTED
    pos_a1 = np.array([pos_sun, pos_earth, [1005.0, 0.0, 0.0]])
    vel_a1 = np.array([vel_sun, vel_earth, [0.0, 0.0, 0.0]])
    masses = np.array([m_sun, m_earth, m_planet])
    assert find_ejected_index(pos_a1, vel_a1, masses, cfg) is None

    # Subcase A2: v > 0 outward but v < v_esc (e.g. 0.5 * v_esc) -> bound, NOT EJECTED
    vel_a2 = np.array([vel_sun, vel_earth, [0.5 * v_esc_1005, 0.0, 0.0]])
    assert find_ejected_index(pos_a1, vel_a2, masses, cfg) is None

    # Case B: Distant, bound and moving inward (r > 1000 AU, rad_vel < 0, specific_energy < 0)
    vel_b = np.array([vel_sun, vel_earth, [-0.5 * v_esc_1005, 0.0, 0.0]])
    assert find_ejected_index(pos_a1, vel_b, masses, cfg) is None

    # Case C: Distant, unbound but moving inward (r > 1000 AU, rad_vel < 0, specific_energy >= 0)
    # High inward speed (e.g. 0.02 AU/day) -> unbound trajectory, but heading inward -> NOT EJECTED
    vel_c = np.array([vel_sun, vel_earth, [-0.02, 0.0, 0.0]])
    assert find_ejected_index(pos_a1, vel_c, masses, cfg) is None

    # Case D: Genuine ejection (r > 1000 AU, outside extent, rad_vel > 0, specific_energy >= 0)
    vel_d = np.array([vel_sun, vel_earth, [0.02, 0.0, 0.0]])  # ~34.7 km/s outward
    res_d = find_ejected_index(pos_a1, vel_d, masses, cfg)
    assert res_d is not None
    assert res_d[0] == 2  # index of the ejected planet
    assert res_d[1] > 1000.0  # distance
    assert res_d[3] > 0.0  # positive v_infinity

    # Case E: Unbound but not far enough (r < 1000 AU, rad_vel > 0, specific_energy >= 0)
    pos_e = np.array([pos_sun, pos_earth, [500.0, 0.0, 0.0]])  # 500 AU < 1000 AU
    vel_e = np.array([vel_sun, vel_earth, [0.02, 0.0, 0.0]])
    assert find_ejected_index(pos_e, vel_e, masses, cfg) is None

    # Case F: Far away but still bound (r = 5000 AU, v = 0 or v < v_esc) -> NOT EJECTED
    # Protects against distance-only threshold reintroduction
    pos_f = np.array([pos_sun, pos_earth, [5000.0, 0.0, 0.0]])
    vel_f = np.array([vel_sun, vel_earth, [0.0, 0.0, 0.0]])
    assert find_ejected_index(pos_f, vel_f, masses, cfg) is None


def test_gladman_hill_stability():
    """Verify that Gladman (1993) mutual Hill radius criterion discriminates stable vs unstable."""
    m_star = 1.989e30
    m_p1 = 1e27
    m_p2 = 1e27
    names = ["Star", "Planet1", "Planet2"]

    # Wide separation: a1=1.0 AU, a2=2.0 AU -> Hill radius ~ 0.09 AU -> Delta ~ 11 >> 3.46 -> STABLE
    pos_stable = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]])
    v1 = np.sqrt(G_AU_DAY * m_star / 1.0)
    v2 = np.sqrt(G_AU_DAY * m_star / 2.0)
    vel_stable = np.array([[0.0, 0.0, 0.0], [0.0, v1, 0.0], [0.0, v2, 0.0]])
    masses = np.array([m_star, m_p1, m_p2])

    rep_stable = assess_stability(names, pos_stable, vel_stable, masses)
    assert rep_stable.status == StabilityStatus.STABLE
    assert rep_stable.min_hill_delta is not None
    assert rep_stable.min_hill_delta > HILL_UNSTABLE_DELTA

    # Very tight separation: a1=1.0 AU, a2=1.05 AU -> Delta ~ 0.05 / 0.07 ~ 0.7 << 3.46 -> UNSTABLE
    pos_tight = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.05, 0.0, 0.0]])
    v2_tight = np.sqrt(G_AU_DAY * m_star / 1.05)
    vel_tight = np.array([[0.0, 0.0, 0.0], [0.0, v1, 0.0], [0.0, v2_tight, 0.0]])

    rep_tight = assess_stability(names, pos_tight, vel_tight, masses)
    assert rep_tight.status == StabilityStatus.UNSTABLE
    assert rep_tight.min_hill_delta < HILL_UNSTABLE_DELTA
    assert any("Hill" in r for r in rep_tight.reasons)


def test_orbit_crossing_criterion():
    """Verify that intersecting eccentric orbits trigger instability."""
    m_star = 1.989e30
    names = ["Star", "Planet1", "Planet2"]
    # Inner planet highly eccentric with apoapsis Q = 2.5 AU
    # Outer planet circular at a = 2.0 AU
    # Since Q1 (2.5) > q2 (2.0), orbits cross!
    r1 = np.array([0.5, 0.0, 0.0])  # periapsis at 0.5 AU
    # Velocity at periapsis for a=1.5, e=0.667 -> Q=2.5 AU
    # v^2 = mu * (2/r - 1/a)
    mu = G_AU_DAY * m_star
    v1_mag = np.sqrt(mu * (2.0 / 0.5 - 1.0 / 1.5))
    v1 = np.array([0.0, v1_mag, 0.0])

    r2 = np.array([2.0, 0.0, 0.0])
    v2 = np.array([0.0, np.sqrt(mu / 2.0), 0.0])

    pos = np.array([[0.0, 0.0, 0.0], r1, r2])
    vel = np.array([[0.0, 0.0, 0.0], v1, v2])
    masses = np.array([m_star, 1e24, 1e24])

    rep = assess_stability(names, pos, vel, masses)
    assert rep.status == StabilityStatus.UNSTABLE
    assert any("cross" in r for r in rep.reasons)


def test_holman_wiegert_binary_star_critical_radius():
    """Verify that adding a second star evaluates Holman & Wiegert (1999) stability."""
    m_primary = 1.989e30
    m_companion = 1.989e30  # equal mass binary (mu = 0.5)
    a_binary = 20.0        # binary semi-major axis = 20 AU
    e_binary = 0.1

    # Check critical S-type radius formula
    a_crit_s = _holman_wiegert_s(a_binary, e_binary, 0.5)
    # HW99 for mu=0.5, e=0.1 gives ~ 0.22 * a_b ~ 4.4 AU
    assert 3.0 < a_crit_s < 6.0

    # Planet at a = 8 AU (> a_crit_s) around primary should be flagged UNSTABLE
    names = ["Sun", "Planet", "Star2"]
    mu_sys = G_AU_DAY * (m_primary + m_companion)
    v_b = np.sqrt(mu_sys / a_binary)

    pos = np.array([
        [0.0, 0.0, 0.0],
        [8.0, 0.0, 0.0],
        [a_binary, 0.0, 0.0],
    ])
    vel = np.array([
        [0.0, 0.0, 0.0],
        [0.0, np.sqrt(G_AU_DAY * m_primary / 8.0), 0.0],
        [0.0, v_b, 0.0],
    ])
    masses = np.array([m_primary, 1e25, m_companion])

    rep = assess_stability(names, pos, vel, masses)
    assert rep.status == StabilityStatus.UNSTABLE
    assert any("exceeds S-type critical radius" in r or "companion" in r for r in rep.reasons)


def test_ejections_affect_stability_verdict():
    """Verify that past ejections render the system unstable or marginal."""
    names = ["Sun", "Earth"]
    pos = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    vel = np.array([[0.0, 0.0, 0.0], [0.0, 0.0172, 0.0]])
    masses = np.array([1.989e30, 5.972e24])

    # No ejections -> stable
    assert assess_stability(names, pos, vel, masses).status == StabilityStatus.STABLE

    # With significant ejection -> unstable
    ejected_event = EjectionEvent(
        name="Jupiter2",
        mass=1.898e27,
        distance_au=1020.0,
        speed_au_day=0.03,
        v_infinity_km_s=50.0,
    )
    rep = assess_stability(names, pos, vel, masses, ejected=[ejected_event])
    assert rep.status == StabilityStatus.UNSTABLE
    assert rep.n_ejected == 1
    assert any("ejected" in r for r in rep.reasons)


def test_system_ejection_lifecycle():
    """Verify that SolarSystem detects, isolates, and records ejected bodies."""
    sun = CelestialBody("Sun", 1.989e30, np.zeros(3), np.zeros(3), 695700, (1.0, 0.9, 0.2), label="star")
    earth = CelestialBody("Earth", 5.972e24, np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0172, 0.0]), 6371, (0.2, 0.5, 1.0))
    # Hyperbolic rogue asteroid launched outward past 1000 AU
    asteroid = CelestialBody(
        "RogueAsteroid",
        1e15,
        np.array([1010.0, 0.0, 0.0]),
        np.array([0.02, 0.0, 0.0]),  # moving outward, unbound
        50.0,
        (0.5, 0.5, 0.5),
    )

    sys = SolarSystem([sun, earth, asteroid])
    assert len(sys.bodies) == 3
    assert len(sys.ejected_bodies) == 0

    # Step once: asteroid should be detected as ejected
    sys.step(0.1)

    # Asteroid must be excluded from active bodies
    assert len(sys.bodies) == 2
    active_names = [b.name for b in sys.bodies]
    assert "Sun" in active_names
    assert "Earth" in active_names
    assert "RogueAsteroid" not in active_names

    # But preserved in ejected collections
    assert len(sys.ejected_bodies) == 1
    assert sys.ejected_bodies[0].name == "RogueAsteroid"
    assert sys.ejected_bodies[0].active is False
    assert len(sys.ejection_history) == 1
    assert sys.ejection_history[0].name == "RogueAsteroid"
    assert sys.ejection_history[0].v_infinity_km_s > 0

    # pop_recent_ejections must return the event and clear staging
    recent = sys.pop_recent_ejections()
    assert len(recent) == 1
    assert recent[0].name == "RogueAsteroid"
    assert len(sys.pop_recent_ejections()) == 0

    # get_body must find both active and ejected bodies
    assert sys.get_body("Earth") is not None
    assert sys.get_body("RogueAsteroid") is not None
    assert sys.get_body("NonExistent") is None
