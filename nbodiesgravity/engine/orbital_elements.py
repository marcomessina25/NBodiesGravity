"""Keplerian two-body orbital elements calculation from Cartesian state vectors.

Calculates semi-major axis, eccentricity, inclination, longitude of ascending node,
argument of periapsis, true anomaly, periapsis/apoapsis distances, and orbital period
relative to a central primary body.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence, Union
import numpy as np

from .body import CelestialBody, BodyState
from .integrator import G_AU_DAY


DAYS_PER_YEAR: float = 365.25


@dataclass(frozen=True)
class OrbitalElements:
    """Osculating Keplerian two-body orbital elements."""
    semi_major_axis: float              # AU (positive for ellipse, negative for hyperbola, inf for parabola)
    eccentricity: float                 # dimensionless (0 = circular, 0 < e < 1 = ellipse, 1 = parabola, > 1 = hyperbola)
    inclination: float                  # radians in [0, pi]
    inclination_deg: float              # degrees in [0, 180]
    longitude_ascending_node: float     # radians in [0, 2*pi)
    longitude_ascending_node_deg: float # degrees in [0, 360)
    argument_of_periapsis: float        # radians in [0, 2*pi)
    argument_of_periapsis_deg: float    # degrees in [0, 360)
    true_anomaly: float                 # radians in [0, 2*pi)
    true_anomaly_deg: float             # degrees in [0, 360)
    periapsis: float                    # AU (closest approach distance)
    apoapsis: float                     # AU (farthest approach distance, inf for unbound)
    period: float                       # days (inf for parabolic/hyperbolic)
    period_years: float                 # Julian years (365.25 days)
    specific_energy: float              # AU² day⁻² (v²/2 - mu/r)
    specific_angular_momentum: np.ndarray  # shape (3,) AU² day⁻¹
    eccentricity_vector: np.ndarray     # shape (3,) dimensionless
    is_bound: bool                      # True if e < 1.0 and specific_energy < 0


def compute_orbital_elements(
    r_vec: np.ndarray,
    v_vec: np.ndarray,
    mu: float,
) -> OrbitalElements:
    """Compute Keplerian orbital elements from relative position and velocity.

    Parameters
    ----------
    r_vec : np.ndarray
        Relative position vector (body - primary) in AU, shape (3,).
    v_vec : np.ndarray
        Relative velocity vector (body - primary) in AU/day, shape (3,).
    mu : float
        Standard gravitational parameter G * (M + m) in AU³ day⁻².

    Returns
    -------
    OrbitalElements
    """
    r = float(np.linalg.norm(r_vec))
    v = float(np.linalg.norm(v_vec))

    if r < 1e-12 or mu <= 0.0:
        return OrbitalElements(
            semi_major_axis=0.0,
            eccentricity=0.0,
            inclination=0.0,
            inclination_deg=0.0,
            longitude_ascending_node=0.0,
            longitude_ascending_node_deg=0.0,
            argument_of_periapsis=0.0,
            argument_of_periapsis_deg=0.0,
            true_anomaly=0.0,
            true_anomaly_deg=0.0,
            periapsis=0.0,
            apoapsis=0.0,
            period=0.0,
            period_years=0.0,
            specific_energy=0.0,
            specific_angular_momentum=np.zeros(3),
            eccentricity_vector=np.zeros(3),
            is_bound=False,
        )

    # Specific relative angular momentum: h = r x v
    h_vec = np.cross(r_vec, v_vec)
    h = float(np.linalg.norm(h_vec))

    # Specific orbital energy: epsilon = v²/2 - mu/r
    energy = 0.5 * (v ** 2) - (mu / r)

    # Semi-major axis: a = -mu / (2 * epsilon)
    if abs(energy) > 1e-15:
        a = -mu / (2.0 * energy)
    else:
        a = float("inf")

    # Eccentricity vector: e = (1/mu) * [(v² - mu/r)*r - (r·v)*v]
    r_dot_v = float(np.dot(r_vec, v_vec))
    e_vec = (1.0 / mu) * ((v ** 2 - mu / r) * r_vec - r_dot_v * v_vec)
    e = float(np.linalg.norm(e_vec))

    # Semi-latus rectum: p = h² / mu
    p = (h ** 2) / mu if mu > 0 else 0.0

    # Periapsis distance: r_p = p / (1 + e)
    r_p = p / (1.0 + e) if (1.0 + e) > 1e-15 else 0.0

    # Apoapsis distance: r_a = a * (1 + e) for ellipse, inf for unbound
    is_bound = (e < (1.0 - 1e-12)) and (energy < -1e-15)
    if is_bound:
        r_a = a * (1.0 + e)
        # Period: T = 2*pi * sqrt(a³ / mu)
        period = 2.0 * np.pi * np.sqrt(a ** 3 / mu) if a > 0 else float("inf")
    else:
        r_a = float("inf")
        period = float("inf")

    # Inclination: i = arccos(h_z / h)
    if h > 1e-14:
        cos_i = float(np.clip(h_vec[2] / h, -1.0, 1.0))
        inc = float(np.arccos(cos_i))
    else:
        inc = 0.0

    # Node vector: n = z_hat x h = (-h_y, h_x, 0)
    n_vec = np.array([-h_vec[1], h_vec[0], 0.0], dtype=float)
    n = float(np.linalg.norm(n_vec))

    # Longitude of Ascending Node: Omega
    if n > 1e-12:
        omega_node = float(np.arctan2(n_vec[1], n_vec[0]))
        if omega_node < 0.0:
            omega_node += 2.0 * np.pi
    else:
        omega_node = 0.0

    # Argument of Periapsis: omega
    if n > 1e-12 and e > 1e-12:
        cos_omega = float(np.clip(np.dot(n_vec, e_vec) / (n * e), -1.0, 1.0))
        arg_peri = float(np.arccos(cos_omega))
        if e_vec[2] < 0.0:
            arg_peri = 2.0 * np.pi - arg_peri
    elif e > 1e-12:
        # Equatorial orbit: angle from x-axis to periapsis
        arg_peri = float(np.arctan2(e_vec[1], e_vec[0]))
        if arg_peri < 0.0:
            arg_peri += 2.0 * np.pi
    else:
        arg_peri = 0.0

    # True Anomaly: nu
    if e > 1e-12:
        cos_nu = float(np.clip(np.dot(e_vec, r_vec) / (e * r), -1.0, 1.0))
        nu = float(np.arccos(cos_nu))
        if r_dot_v < 0.0:
            nu = 2.0 * np.pi - nu
    else:
        # Circular orbit: angle from node or x-axis
        if n > 1e-12:
            cos_u = float(np.clip(np.dot(n_vec, r_vec) / (n * r), -1.0, 1.0))
            nu = float(np.arccos(cos_u))
            if r_vec[2] < 0.0:
                nu = 2.0 * np.pi - nu
        else:
            nu = float(np.arctan2(r_vec[1], r_vec[0]))
            if nu < 0.0:
                nu += 2.0 * np.pi

    return OrbitalElements(
        semi_major_axis=a,
        eccentricity=e,
        inclination=inc,
        inclination_deg=float(np.degrees(inc)),
        longitude_ascending_node=omega_node,
        longitude_ascending_node_deg=float(np.degrees(omega_node)),
        argument_of_periapsis=arg_peri,
        argument_of_periapsis_deg=float(np.degrees(arg_peri)),
        true_anomaly=nu,
        true_anomaly_deg=float(np.degrees(nu)),
        periapsis=r_p,
        apoapsis=r_a,
        period=period,
        period_years=period / DAYS_PER_YEAR if np.isfinite(period) else float("inf"),
        specific_energy=energy,
        specific_angular_momentum=h_vec,
        eccentricity_vector=e_vec,
        is_bound=is_bound,
    )


def compute_elements_for_body(
    body: Union[CelestialBody, BodyState],
    primary: Union[CelestialBody, BodyState],
) -> OrbitalElements:
    """Compute orbital elements of a body orbiting a primary."""
    r_rel = np.asarray(body.pos, dtype=float) - np.asarray(primary.pos, dtype=float)
    v_rel = np.asarray(body.vel, dtype=float) - np.asarray(primary.vel, dtype=float)
    m_primary = float(getattr(primary, "mass", 0.0))
    m_body = float(getattr(body, "mass", 0.0))
    mu = G_AU_DAY * (m_primary + m_body)
    return compute_orbital_elements(r_rel, v_rel, mu)


def find_dominant_primary(
    body: Union[CelestialBody, BodyState],
    all_bodies: Sequence[Union[CelestialBody, BodyState]],
) -> Union[CelestialBody, BodyState, None]:
    """Find the dominant primary gravitational parent for a body.

    Considers planetary Hill spheres (e.g. Moon orbiting Earth, Jovian moons orbiting Jupiter)
    and falls back to the body exerting the maximum gravitational force G*M/r².
    """
    candidates = [b for b in all_bodies if b is not body and getattr(b, "active", True)]
    if not candidates:
        return None

    # Find the most massive body (the central star/Sun)
    central_star = max(candidates, key=lambda b: float(getattr(b, "mass", 0.0)))
    m_star = float(getattr(central_star, "mass", 0.0))

    body_pos = np.asarray(body.pos, dtype=float)

    # Check if inside any planet's Hill sphere
    if m_star > 0:
        star_pos = np.asarray(central_star.pos, dtype=float)
        for planet in candidates:
            if planet is central_star:
                continue
            m_planet = float(getattr(planet, "mass", 0.0))
            if m_planet <= 0.0 or m_planet >= m_star:
                continue
            p_pos = np.asarray(planet.pos, dtype=float)
            d_planet_star = float(np.linalg.norm(p_pos - star_pos))
            if d_planet_star <= 0:
                continue
            # Hill sphere radius: r_H = a * (m / 3M)^(1/3)
            r_hill = d_planet_star * ((m_planet / (3.0 * m_star)) ** (1.0 / 3.0))
            d_body_planet = float(np.linalg.norm(body_pos - p_pos))
            if d_body_planet < r_hill:
                return planet

    # Fallback: choose candidate maximizing G*M / r²
    best_primary = None
    best_acc = -1.0
    for cand in candidates:
        m_cand = float(getattr(cand, "mass", 0.0))
        if m_cand <= 0.0:
            continue
        cand_pos = np.asarray(cand.pos, dtype=float)
        dist_sq = float(np.sum((body_pos - cand_pos) ** 2))
        if dist_sq < 1e-20:
            continue
        acc = m_cand / dist_sq
        if acc > best_acc:
            best_acc = acc
            best_primary = cand

    return best_primary
