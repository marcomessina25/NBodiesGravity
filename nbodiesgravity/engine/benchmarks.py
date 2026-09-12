"""Canonical deterministic benchmark systems for numerical validation.

Provides factory functions returning configured SolarSystem instances:
- Benchmark A: Free particle (uniform linear motion, zero force)
- Benchmark B: Two-body circular orbit (analytical solution, constant separation)
- Benchmark C: Two-body eccentric orbit (analytical periapsis/apoapsis)
- Benchmark D: Earth-Sun (controlled 1-year planetary orbit)
- Benchmark E: Earth-Moon (short orbital timescale ~27.3 days)
- Benchmark F: Three-body system (Lagrange equilateral periodic solution)
"""
from __future__ import annotations
import numpy as np

from .body import CelestialBody
from .integrator import G_AU_DAY, SOFTENING
from .system import SolarSystem, TimeStepConfig


def create_free_particle(
    mass: float = 1.0e24,
    pos: Sequence[float] = (0.0, 0.0, 0.0),
    vel: Sequence[float] = (0.01, 0.02, 0.005),
) -> SolarSystem:
    """Benchmark A — Free particle with zero interacting gravity."""
    body = CelestialBody(
        name="FreeParticle",
        mass=float(mass),
        pos=np.array(pos, dtype=float),
        vel=np.array(vel, dtype=float),
        radius=1000.0,
        color=(0.9, 0.9, 0.9),
    )
    return SolarSystem([body])


def create_circular_two_body(
    m1: float = 1.989e30,
    m2: float = 5.972e24,
    r: float = 1.0,
    softening: float = SOFTENING,
) -> SolarSystem:
    """Benchmark B — Analytically defined circular two-body orbit centered on barycenter."""
    total_m = m1 + m2
    # Speed including softening correction so orbit remains strictly circular
    # a = G * total_m * r / (r² + ε²)^1.5, v² / r = a => v = sqrt(G * total_m * r² / (r² + ε²)^1.5)
    v_rel = float(np.sqrt(G_AU_DAY * total_m * (r ** 2) / ((r ** 2 + softening ** 2) ** 1.5)))

    r1 = float(- (m2 / total_m) * r)
    r2 = float((m1 / total_m) * r)
    v1 = float(- (m2 / total_m) * v_rel)
    v2 = float((m1 / total_m) * v_rel)

    b1 = CelestialBody(
        name="Primary",
        mass=float(m1),
        pos=np.array([r1, 0.0, 0.0]),
        vel=np.array([0.0, v1, 0.0]),
        radius=695700.0,
        color=(1.0, 0.8, 0.2),
        label="star",
    )
    b2 = CelestialBody(
        name="Secondary",
        mass=float(m2),
        pos=np.array([r2, 0.0, 0.0]),
        vel=np.array([0.0, v2, 0.0]),
        radius=6371.0,
        color=(0.2, 0.5, 1.0),
        label="planet",
    )
    return SolarSystem([b1, b2], softening=softening)


def create_eccentric_two_body(
    m1: float = 1.989e30,
    m2: float = 5.972e24,
    a: float = 1.0,
    e: float = 0.5,
    softening: float = SOFTENING,
) -> SolarSystem:
    """Benchmark C — Analytically defined eccentric two-body orbit (at periapsis)."""
    if not (0.0 <= e < 1.0):
        raise ValueError(f"Eccentricity e must satisfy 0 <= e < 1, got {e}")
    total_m = m1 + m2
    r_p = a * (1.0 - e)
    # Velocity at periapsis from vis-viva equation: v_p² = G * total_m * (2/r_p - 1/a)
    v_rel = float(np.sqrt(G_AU_DAY * total_m * (2.0 / r_p - 1.0 / a)))

    r1 = float(- (m2 / total_m) * r_p)
    r2 = float((m1 / total_m) * r_p)
    v1 = float(- (m2 / total_m) * v_rel)
    v2 = float((m1 / total_m) * v_rel)

    b1 = CelestialBody(
        name="Primary",
        mass=float(m1),
        pos=np.array([r1, 0.0, 0.0]),
        vel=np.array([0.0, v1, 0.0]),
        radius=695700.0,
        color=(1.0, 0.8, 0.2),
        label="star",
    )
    b2 = CelestialBody(
        name="Secondary",
        mass=float(m2),
        pos=np.array([r2, 0.0, 0.0]),
        vel=np.array([0.0, v2, 0.0]),
        radius=6371.0,
        color=(0.2, 0.5, 1.0),
        label="planet",
    )
    return SolarSystem([b1, b2], softening=softening)


def create_earth_sun() -> SolarSystem:
    """Benchmark D — Earth-Sun system with controlled 1-year orbit in barycentric frame."""
    m_sun = 1.9885e30
    m_earth = 5.972e24
    r = 1.0   # 1 AU

    return create_circular_two_body(m1=m_sun, m2=m_earth, r=r)


def create_earth_moon() -> SolarSystem:
    """Benchmark E — Earth-Moon system stressing adaptive timestepping on short orbital timescales."""
    m_earth = 5.972e24
    m_moon = 7.342e22
    # 384,400 km in AU
    r_km = 384400.0
    r_au = r_km / 1.495978707e8

    # Use higher resolution timestep configuration suitable for lunar orbital period (~27.3 days)
    config = TimeStepConfig(
        min_dt=1e-5,
        max_dt=0.25,
        safety_factor=0.01,
        max_substeps=20_000,
    )
    system = create_circular_two_body(m1=m_earth, m2=m_moon, r=r_au)
    system.bodies[0].name = "Earth"
    system.bodies[0].radius = 6371.0
    system.bodies[0].label = "planet"
    system.bodies[1].name = "Moon"
    system.bodies[1].radius = 1737.4
    system.bodies[1].label = "moon"
    system.timestep_config = config
    return system


def create_three_body_lagrange(
    mass: float = 1.0e30,
    side: float = 1.0,
    softening: float = SOFTENING,
) -> SolarSystem:
    """Benchmark F — Planar equilateral Lagrange three-body solution.

    Three equal-mass bodies rotate around their common barycenter preserving an
    equilateral triangle with exact analytic period and circular trajectories.
    """
    m = float(mass)
    l = float(side)
    # Radius from barycenter to each vertex: R = L / sqrt(3)
    radius = l / np.sqrt(3.0)
    # Gravitational force from other two bodies at separation L:
    # F_net = sqrt(3) * G * m² / L² towards center.
    # a = F_net / m = sqrt(3) * G * m / L²
    # a = omega² * R = omega² * L / sqrt(3) => omega² = 3 * G * m / L³
    omega = float(np.sqrt(3.0 * G_AU_DAY * m / (l ** 3)))
    v_mag = omega * radius

    angles = [0.0, 2.0 * np.pi / 3.0, 4.0 * np.pi / 3.0]
    bodies = []
    names = ["BodyA", "BodyB", "BodyC"]
    colors = [(1.0, 0.3, 0.3), (0.3, 1.0, 0.3), (0.3, 0.3, 1.0)]

    for i, (name, theta, col) in enumerate(zip(names, angles, colors)):
        pos = np.array([radius * np.cos(theta), radius * np.sin(theta), 0.0])
        vel = np.array([- v_mag * np.sin(theta), v_mag * np.cos(theta), 0.0])
        bodies.append(
            CelestialBody(
                name=name,
                mass=m,
                pos=pos,
                vel=vel,
                radius=10000.0,
                color=col,
            )
        )

    return SolarSystem(bodies, softening=softening)
