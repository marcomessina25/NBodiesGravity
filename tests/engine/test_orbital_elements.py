"""Tests for Keplerian orbital elements calculation and dominant primary detection."""
import numpy as np
import pytest
from nbodiesgravity.engine.body import CelestialBody, BodyState
from nbodiesgravity.engine.integrator import G_AU_DAY
from nbodiesgravity.engine.orbital_elements import (
    OrbitalElements,
    compute_orbital_elements,
    compute_elements_for_body,
    find_dominant_primary,
)


def test_circular_equatorial_orbit():
    mu = 2.959122082855911e-4  # G * M_sun in AU³ day⁻²
    r0 = 1.0  # 1 AU
    v_circ = np.sqrt(mu / r0)

    r_vec = np.array([r0, 0.0, 0.0])
    v_vec = np.array([0.0, v_circ, 0.0])

    elem = compute_orbital_elements(r_vec, v_vec, mu)

    assert elem.is_bound is True
    assert pytest.approx(elem.semi_major_axis, rel=1e-6) == 1.0
    assert pytest.approx(elem.eccentricity, abs=1e-7) == 0.0
    assert pytest.approx(elem.inclination_deg, abs=1e-7) == 0.0
    assert pytest.approx(elem.periapsis, rel=1e-6) == 1.0
    assert pytest.approx(elem.apoapsis, rel=1e-6) == 1.0
    expected_period = 2.0 * np.pi * np.sqrt(r0**3 / mu)
    assert pytest.approx(elem.period, rel=1e-6) == expected_period
    assert pytest.approx(elem.period_years, rel=1e-4) == 1.0


def test_eccentric_orbit():
    mu = 2.959122082855911e-4
    target_e = 0.5
    r_p = 1.0  # Periapsis at 1 AU -> a = r_p / (1 - e) = 2.0 AU
    target_a = r_p / (1.0 - target_e)
    # Vis-viva equation: v² = mu * (2/r - 1/a)
    v_peri = np.sqrt(mu * (2.0 / r_p - 1.0 / target_a))

    r_vec = np.array([r_p, 0.0, 0.0])
    v_vec = np.array([0.0, v_peri, 0.0])

    elem = compute_orbital_elements(r_vec, v_vec, mu)

    assert elem.is_bound is True
    assert pytest.approx(elem.semi_major_axis, rel=1e-6) == target_a
    assert pytest.approx(elem.eccentricity, rel=1e-6) == target_e
    assert pytest.approx(elem.periapsis, rel=1e-6) == r_p
    assert pytest.approx(elem.apoapsis, rel=1e-6) == 3.0
    assert pytest.approx(elem.inclination_deg, abs=1e-7) == 0.0


def test_inclined_orbit():
    mu = 2.959122082855911e-4
    r0 = 1.0
    v_circ = np.sqrt(mu / r0)
    inc_angle = np.radians(45.0)

    r_vec = np.array([r0, 0.0, 0.0])
    # Velocity tilted into +z by 45 degrees
    v_vec = np.array([0.0, v_circ * np.cos(inc_angle), v_circ * np.sin(inc_angle)])

    elem = compute_orbital_elements(r_vec, v_vec, mu)

    assert elem.is_bound is True
    assert pytest.approx(elem.semi_major_axis, rel=1e-6) == 1.0
    assert pytest.approx(elem.eccentricity, abs=1e-7) == 0.0
    assert pytest.approx(elem.inclination_deg, rel=1e-5) == 45.0


def test_hyperbolic_orbit():
    mu = 2.959122082855911e-4
    r0 = 1.0
    # Escape velocity is sqrt(2*mu/r). Set speed greater than escape speed.
    v_hyp = 1.5 * np.sqrt(2.0 * mu / r0)

    r_vec = np.array([r0, 0.0, 0.0])
    v_vec = np.array([0.0, v_hyp, 0.0])

    elem = compute_orbital_elements(r_vec, v_vec, mu)

    assert elem.is_bound is False
    assert elem.eccentricity > 1.0
    assert elem.semi_major_axis < 0.0
    assert np.isinf(elem.apoapsis)
    assert np.isinf(elem.period)
    assert elem.periapsis > 0.0


def test_degenerate_zero_inputs():
    elem = compute_orbital_elements(np.zeros(3), np.zeros(3), 0.0)
    assert elem.semi_major_axis == 0.0
    assert elem.eccentricity == 0.0
    assert elem.is_bound is False


def test_compute_elements_for_body_and_bodystate():
    sun_m = 1.989e30
    earth_m = 5.972e24
    mu = G_AU_DAY * (sun_m + earth_m)
    v_circ = np.sqrt(mu / 1.0)

    sun = CelestialBody("Sun", sun_m, np.zeros(3), np.zeros(3), 696340.0, (1.0, 1.0, 0.0))
    earth = CelestialBody("Earth", earth_m, np.array([1.0, 0.0, 0.0]), np.array([0.0, v_circ, 0.0]), 6371.0, (0.0, 0.5, 1.0))

    elem1 = compute_elements_for_body(earth, sun)
    assert pytest.approx(elem1.semi_major_axis, rel=1e-6) == 1.0
    assert elem1.is_bound is True

    # Test with BodyState snapshot
    snap_sun = sun.snapshot()
    snap_earth = earth.snapshot()
    elem2 = compute_elements_for_body(snap_earth, snap_sun)
    assert elem1.semi_major_axis == elem2.semi_major_axis
    assert elem1.period == elem2.period


def test_find_dominant_primary_solar_system_hierarchy():
    sun = CelestialBody("Sun", 1.989e30, np.zeros(3), np.zeros(3), 7e5, (1, 1, 0))
    earth = CelestialBody("Earth", 5.972e24, np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0172, 0.0]), 6371, (0, 0, 1))
    # Moon in Earth orbit: distance 384,400 km = ~0.00257 AU
    moon = CelestialBody("Moon", 7.348e22, np.array([1.00257, 0.0, 0.0]), np.array([0.0, 0.0172 + 0.00059, 0.0]), 1737, (0.7, 0.7, 0.7))
    mars = CelestialBody("Mars", 6.417e23, np.array([1.52, 0.0, 0.0]), np.array([0.0, 0.014, 0.0]), 3389, (1, 0, 0))

    all_bodies = [sun, earth, moon, mars]

    # Earth orbits the Sun
    assert find_dominant_primary(earth, all_bodies) == sun
    # Mars orbits the Sun
    assert find_dominant_primary(mars, all_bodies) == sun
    # Moon is inside Earth's Hill sphere (~0.01 AU), so its primary is Earth!
    assert find_dominant_primary(moon, all_bodies) == earth
    # Sun primary among planets
    assert find_dominant_primary(sun, [earth, mars]) == earth  # largest gravitational pull on Sun among candidates
    # Single body case
    assert find_dominant_primary(earth, [earth]) is None


def test_inclined_orbit_30_degrees():
    mu = 2.959122082855911e-4
    r0 = 1.2
    v_circ = np.sqrt(mu / r0)
    inc_rad = np.radians(30.0)

    r_vec = np.array([r0, 0.0, 0.0])
    v_vec = np.array([0.0, v_circ * np.cos(inc_rad), v_circ * np.sin(inc_rad)])

    elem = compute_orbital_elements(r_vec, v_vec, mu)

    assert elem.is_bound is True
    assert pytest.approx(elem.semi_major_axis, rel=1e-7) == 1.2
    assert pytest.approx(elem.eccentricity, abs=1e-7) == 0.0
    assert pytest.approx(elem.inclination_deg, rel=1e-7) == 30.0
    assert pytest.approx(elem.inclination, rel=1e-7) == inc_rad


def test_full_keplerian_elements_analytical_recovery():
    """Verify analytical recovery of all 6 orbital elements: a, e, i, Omega, omega, nu."""
    mu = 2.959122082855911e-4

    target_a = 1.5
    target_e = 0.25
    target_i_deg = 30.0
    target_omega_node_deg = 45.0
    target_arg_peri_deg = 60.0
    target_nu_deg = 35.0

    i = np.radians(target_i_deg)
    Omega = np.radians(target_omega_node_deg)
    omega = np.radians(target_arg_peri_deg)
    nu = np.radians(target_nu_deg)

    # 1. Perifocal coordinates
    p = target_a * (1.0 - target_e ** 2)
    r_mag = p / (1.0 + target_e * np.cos(nu))

    r_perifocal = np.array([r_mag * np.cos(nu), r_mag * np.sin(nu), 0.0])
    v_perifocal = np.sqrt(mu / p) * np.array([-np.sin(nu), target_e + np.cos(nu), 0.0])

    # 2. Rotation matrix from perifocal to inertial (equatorial)
    P_vec = np.array([
        np.cos(Omega) * np.cos(omega) - np.sin(Omega) * np.sin(omega) * np.cos(i),
        np.sin(Omega) * np.cos(omega) + np.cos(Omega) * np.sin(omega) * np.cos(i),
        np.sin(omega) * np.sin(i),
    ])
    Q_vec = np.array([
        -np.cos(Omega) * np.sin(omega) - np.sin(Omega) * np.cos(omega) * np.cos(i),
        -np.sin(Omega) * np.sin(omega) + np.cos(Omega) * np.cos(omega) * np.cos(i),
        np.cos(omega) * np.sin(i),
    ])

    r_inertial = r_perifocal[0] * P_vec + r_perifocal[1] * Q_vec
    v_inertial = v_perifocal[0] * P_vec + v_perifocal[1] * Q_vec

    elem = compute_orbital_elements(r_inertial, v_inertial, mu)

    assert elem.is_bound is True
    assert pytest.approx(elem.semi_major_axis, rel=1e-7) == target_a
    assert pytest.approx(elem.eccentricity, rel=1e-7) == target_e
    assert pytest.approx(elem.inclination_deg, rel=1e-7) == target_i_deg
    assert pytest.approx(elem.longitude_ascending_node_deg, rel=1e-7) == target_omega_node_deg
    assert pytest.approx(elem.argument_of_periapsis_deg, rel=1e-7) == target_arg_peri_deg
    assert pytest.approx(elem.true_anomaly_deg, rel=1e-7) == target_nu_deg
    assert pytest.approx(elem.periapsis, rel=1e-7) == target_a * (1.0 - target_e)
    assert pytest.approx(elem.apoapsis, rel=1e-7) == target_a * (1.0 + target_e)
    expected_period = 2.0 * np.pi * np.sqrt(target_a ** 3 / mu)
    assert pytest.approx(elem.period, rel=1e-7) == expected_period


def test_parabolic_boundary_orbit():
    """Verify behavior at the parabolic escape boundary (e = 1.0, epsilon = 0.0)."""
    mu = 2.959122082855911e-4
    r_p = 1.0  # Periapsis distance
    # Exact escape speed at periapsis: v_esc = sqrt(2 * mu / r_p)
    v_esc = np.sqrt(2.0 * mu / r_p)

    r_vec = np.array([r_p, 0.0, 0.0])
    v_vec = np.array([0.0, v_esc, 0.0])

    elem = compute_orbital_elements(r_vec, v_vec, mu)

    assert elem.is_bound is False
    assert pytest.approx(elem.eccentricity, rel=1e-7) == 1.0
    assert pytest.approx(elem.periapsis, rel=1e-7) == r_p
    assert np.isinf(elem.apoapsis)
    assert np.isinf(elem.period)
    assert np.isinf(elem.semi_major_axis)
    assert pytest.approx(elem.specific_energy, abs=1e-15) == 0.0

