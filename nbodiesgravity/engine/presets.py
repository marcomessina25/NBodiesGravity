"""Analytical initial-condition presets and configuration registry for NBodiesGravity.

Provides deterministic initial conditions for analytical Keplerian orbits,
hierarchical binaries, Earth-Moon models, and restricted three-body equilibria.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Callable
import numpy as np

from .body import CelestialBody
from .integrator import G_AU_DAY, SOFTENING, IntegratorConfig
from .physics import PhysicsConfig, CollisionConfig
from .system import SolarSystem, TimeStepConfig

KM_PER_AU: float = 1.495978707e8

# Solar mass and Earth mass constants (kg)
M_SUN: float = 1.98847e30
M_EARTH: float = 5.9722e24
M_MOON: float = 7.342e22


@dataclass(frozen=True)
class InitialConditionSet:
    """Serializable initial conditions and simulation configuration for an experiment."""
    name: str
    description: str
    epoch: datetime
    bodies: list[CelestialBody]
    physics_config: PhysicsConfig = PhysicsConfig()
    timestep_config: TimeStepConfig = TimeStepConfig()
    integrator_config: IntegratorConfig = IntegratorConfig()
    collision_config: CollisionConfig = CollisionConfig()

    def create_system(self) -> SolarSystem:
        """Instantiate a ready-to-simulate SolarSystem configured with these initial conditions."""
        return SolarSystem(
            bodies=[
                CelestialBody(
                    name=b.name,
                    mass=b.mass,
                    pos=b.pos.copy(),
                    vel=b.vel.copy(),
                    radius=b.radius,
                    color=b.color,
                    show_trail=b.show_trail,
                    active=b.active,
                    label=b.label,
                    show_name=b.show_name,
                )
                for b in self.bodies
            ],
            timestep_config=self.timestep_config,
            integrator_config=self.integrator_config,
            physics_config=self.physics_config,
            collision_config=self.collision_config,
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "epoch": self.epoch.strftime("%Y-%m-%d"),
            "physics_config": self.physics_config.to_dict(),
            "timestep_config": self.timestep_config.to_dict(),
            "integrator_config": self.integrator_config.to_dict(),
            "collision_config": self.collision_config.to_dict(),
            "bodies": [
                {
                    "name": b.name,
                    "label": b.label,
                    "mass_kg": float(b.mass),
                    "radius_km": float(b.radius),
                    "color": list(b.color),
                    "pos_au": b.pos.tolist(),
                    "vel_au_per_day": b.vel.tolist(),
                    "active": bool(b.active),
                    "show_trail": bool(b.show_trail),
                    "show_name": bool(b.show_name),
                }
                for b in self.bodies
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> InitialConditionSet:
        epoch_str = data.get("epoch", "2000-01-01")
        try:
            epoch = datetime.fromisoformat(epoch_str)
        except ValueError:
            epoch = datetime.strptime(epoch_str, "%Y-%m-%d")

        bodies = [
            CelestialBody(
                name=e["name"],
                mass=float(e["mass_kg"]),
                pos=np.array(e["pos_au"], dtype=float),
                vel=np.array(e["vel_au_per_day"], dtype=float),
                radius=float(e.get("radius_km", 1000.0)),
                color=tuple(e.get("color", [255, 255, 255])),
                label=e.get("label", "planet"),
                active=bool(e.get("active", True)),
                show_trail=bool(e.get("show_trail", True)),
                show_name=bool(e.get("show_name", True)),
            )
            for e in data.get("bodies", [])
        ]

        return cls(
            name=str(data.get("name", "Custom Preset")),
            description=str(data.get("description", "")),
            epoch=epoch,
            bodies=bodies,
            physics_config=PhysicsConfig.from_dict(data.get("physics_config", {})),
            timestep_config=TimeStepConfig.from_dict(data.get("timestep_config", {})),
            integrator_config=IntegratorConfig.from_dict(data.get("integrator_config", {})),
            collision_config=CollisionConfig.from_dict(data.get("collision_config", {})),
        )


# ---------------------------------------------------------------------------
# Analytical Preset Builders
# ---------------------------------------------------------------------------

def create_circular_two_body(
    m1: float = M_SUN,
    m2: float = M_EARTH,
    r: float = 1.0,
    name: str = "Circular Two-Body",
    physics_config: PhysicsConfig | None = None,
) -> InitialConditionSet:
    """Generate circular 2-body orbit in the barycentric frame using configured G."""
    if r <= 0:
        raise ValueError(f"Separation r must be positive, got {r}")
    if m1 <= 0 or m2 <= 0:
        raise ValueError("Masses must be positive.")

    p_cfg = physics_config if physics_config is not None else PhysicsConfig()
    g = p_cfg.gravitational_constant
    mu = g * (m1 + m2)
    v_orb = float(np.sqrt(mu / r))

    mu1 = m2 / (m1 + m2)
    mu2 = m1 / (m1 + m2)

    pos1 = np.array([-mu1 * r, 0.0, 0.0], dtype=float)
    vel1 = np.array([0.0, -mu1 * v_orb, 0.0], dtype=float)

    pos2 = np.array([mu2 * r, 0.0, 0.0], dtype=float)
    vel2 = np.array([0.0, mu2 * v_orb, 0.0], dtype=float)

    bodies = [
        CelestialBody("Primary", m1, pos1, vel1, 696340.0, (255, 230, 70), label="star"),
        CelestialBody("Secondary", m2, pos2, vel2, 6371.0, (100, 180, 255), label="planet"),
    ]

    return InitialConditionSet(
        name=name,
        description=f"Circular two-body system (r = {r:.2f} AU, m1 = {m1:.2e} kg, m2 = {m2:.2e} kg)",
        epoch=datetime(2000, 1, 1),
        bodies=bodies,
        physics_config=p_cfg,
    )


def create_eccentric_two_body(
    m1: float = M_SUN,
    m2: float = M_EARTH,
    a: float = 1.0,
    e: float = 0.5,
    name: str = "Eccentric Two-Body",
    physics_config: PhysicsConfig | None = None,
) -> InitialConditionSet:
    """Generate eccentric 2-body orbit initialized at periapsis using configured G."""
    if a <= 0:
        raise ValueError(f"Semi-major axis a must be positive, got {a}")
    if not (0.0 <= e < 1.0):
        raise ValueError(f"Eccentricity e must be in [0, 1), got {e}")
    if m1 <= 0 or m2 <= 0:
        raise ValueError("Masses must be positive.")

    p_cfg = physics_config if physics_config is not None else PhysicsConfig()
    g = p_cfg.gravitational_constant
    r_peri = a * (1.0 - e)
    mu = g * (m1 + m2)
    # Vis-viva at periapsis: v_p = sqrt(mu * (2/r_p - 1/a)) = sqrt(mu * (1 + e) / (a * (1 - e)))
    v_peri = float(np.sqrt(mu * (1.0 + e) / (a * (1.0 - e))))

    mu1 = m2 / (m1 + m2)
    mu2 = m1 / (m1 + m2)

    pos1 = np.array([-mu1 * r_peri, 0.0, 0.0], dtype=float)
    vel1 = np.array([0.0, -mu1 * v_peri, 0.0], dtype=float)

    pos2 = np.array([mu2 * r_peri, 0.0, 0.0], dtype=float)
    vel2 = np.array([0.0, mu2 * v_peri, 0.0], dtype=float)

    bodies = [
        CelestialBody("Primary", m1, pos1, vel1, 696340.0, (255, 230, 70), label="star"),
        CelestialBody("Secondary", m2, pos2, vel2, 6371.0, (100, 180, 255), label="planet"),
    ]

    return InitialConditionSet(
        name=name,
        description=f"Eccentric two-body system (a = {a:.2f} AU, e = {e:.2f})",
        epoch=datetime(2000, 1, 1),
        bodies=bodies,
        physics_config=p_cfg,
    )


def create_oriented_two_body(
    m1: float = M_SUN,
    m2: float = M_EARTH,
    a: float = 1.0,
    e: float = 0.2,
    inc_deg: float = 30.0,
    lan_deg: float = 45.0,
    arg_pe_deg: float = 60.0,
    true_anom_deg: float = 0.0,
    name: str = "Oriented Two-Body",
    physics_config: PhysicsConfig | None = None,
) -> InitialConditionSet:
    """Generate 3D oriented two-body system from Keplerian orbital elements using configured G."""
    if a <= 0:
        raise ValueError(f"Semi-major axis a must be positive, got {a}")
    if not (0.0 <= e < 1.0):
        raise ValueError(f"Eccentricity e must be in [0, 1), got {e}")

    p_cfg = physics_config if physics_config is not None else PhysicsConfig()
    g = p_cfg.gravitational_constant

    inc = np.radians(inc_deg)
    lan = np.radians(lan_deg)
    arg_pe = np.radians(arg_pe_deg)
    nu = np.radians(true_anom_deg)

    mu = g * (m1 + m2)
    p = a * (1.0 - e ** 2)
    r = p / (1.0 + e * np.cos(nu))

    # Perifocal coordinates
    r_pqw = np.array([r * np.cos(nu), r * np.sin(nu), 0.0], dtype=float)
    v_coeff = np.sqrt(mu / p)
    v_pqw = np.array([-v_coeff * np.sin(nu), v_coeff * (e + np.cos(nu)), 0.0], dtype=float)

    # Direction cosine transformation matrix P_x, P_y, etc.
    cos_o, sin_o = np.cos(lan), np.sin(lan)
    cos_w, sin_w = np.cos(arg_pe), np.sin(arg_pe)
    cos_i, sin_i = np.cos(inc), np.sin(inc)

    P = np.array([
        cos_o * cos_w - sin_o * sin_w * cos_i,
        sin_o * cos_w + cos_o * sin_w * cos_i,
        sin_w * sin_i,
    ])
    Q = np.array([
        -cos_o * sin_w - sin_o * cos_w * cos_i,
        -sin_o * sin_w + cos_o * cos_w * cos_i,
        cos_w * sin_i,
    ])

    rel_pos = r_pqw[0] * P + r_pqw[1] * Q
    rel_vel = v_pqw[0] * P + v_pqw[1] * Q

    mu1 = m2 / (m1 + m2)
    mu2 = m1 / (m1 + m2)

    pos1 = -mu1 * rel_pos
    vel1 = -mu1 * rel_vel
    pos2 = mu2 * rel_pos
    vel2 = mu2 * rel_vel

    bodies = [
        CelestialBody("Primary", m1, pos1, vel1, 696340.0, (255, 230, 70), label="star"),
        CelestialBody("Secondary", m2, pos2, vel2, 6371.0, (100, 180, 255), label="planet"),
    ]

    return InitialConditionSet(
        name=name,
        description=f"Oriented two-body orbit (i = {inc_deg}°, Ω = {lan_deg}°, ω = {arg_pe_deg}°)",
        epoch=datetime(2000, 1, 1),
        bodies=bodies,
        physics_config=p_cfg,
    )


def create_earth_moon_preset(
    name: str = "Earth-Moon System",
    physics_config: PhysicsConfig | None = None,
) -> InitialConditionSet:
    """Generate high-precision Earth-Moon analytical system using configured G."""
    p_cfg = physics_config if physics_config is not None else PhysicsConfig()
    g = p_cfg.gravitational_constant

    m_earth = M_EARTH
    m_moon = M_MOON
    r_km = 384400.0
    r_au = r_km / KM_PER_AU

    mu = g * (m_earth + m_moon)
    v_circ = float(np.sqrt(mu / r_au))

    mu1 = m_moon / (m_earth + m_moon)
    mu2 = m_earth / (m_earth + m_moon)

    pos_earth = np.array([-mu1 * r_au, 0.0, 0.0], dtype=float)
    vel_earth = np.array([0.0, -mu1 * v_circ, 0.0], dtype=float)

    pos_moon = np.array([mu2 * r_au, 0.0, 0.0], dtype=float)
    vel_moon = np.array([0.0, mu2 * v_circ, 0.0], dtype=float)

    bodies = [
        CelestialBody("Earth", m_earth, pos_earth, vel_earth, 6371.0, (80, 140, 240), label="planet"),
        CelestialBody("Moon", m_moon, pos_moon, vel_moon, 1737.4, (200, 200, 200), label="moon"),
    ]

    # Moon orbit has short period (~27.3 days), use tight max_dt
    t_cfg = TimeStepConfig(min_dt=1e-5, max_dt=0.05, safety_factor=0.01)

    return InitialConditionSet(
        name=name,
        description="Isolated Earth-Moon barycentric system",
        epoch=datetime(2000, 1, 1),
        bodies=bodies,
        timestep_config=t_cfg,
        physics_config=p_cfg,
    )


def create_binary_star_preset(
    m1: float = M_SUN,
    m2: float = M_SUN,
    separation: float = 2.0,
    name: str = "Equal-Mass Binary Star",
    physics_config: PhysicsConfig | None = None,
) -> InitialConditionSet:
    """Generate symmetric binary star system with comparable stellar masses using configured G."""
    if separation <= 0:
        raise ValueError(f"Separation must be positive, got {separation}")

    p_cfg = physics_config if physics_config is not None else PhysicsConfig()
    g = p_cfg.gravitational_constant

    mu = g * (m1 + m2)
    v_orb = float(np.sqrt(mu / separation))

    r1 = separation * (m2 / (m1 + m2))
    r2 = separation * (m1 / (m1 + m2))

    v1 = v_orb * (m2 / (m1 + m2))
    v2 = v_orb * (m1 / (m1 + m2))

    pos1 = np.array([-r1, 0.0, 0.0], dtype=float)
    vel1 = np.array([0.0, -v1, 0.0], dtype=float)

    pos2 = np.array([r2, 0.0, 0.0], dtype=float)
    vel2 = np.array([0.0, v2, 0.0], dtype=float)

    bodies = [
        CelestialBody("Star Alpha", m1, pos1, vel1, 696340.0, (255, 180, 50), label="star"),
        CelestialBody("Star Beta", m2, pos2, vel2, 696340.0, (200, 220, 255), label="star"),
    ]

    return InitialConditionSet(
        name=name,
        description=f"Binary star system (separation = {separation:.2f} AU)",
        epoch=datetime(2000, 1, 1),
        bodies=bodies,
        physics_config=p_cfg,
    )


def create_restricted_three_body_preset(
    m1: float = M_SUN,
    m2: float = 1.898e27,  # Jupiter-mass
    r: float = 5.2,         # 5.2 AU
    lagrange_point: str = "L4",
    name: str = "Restricted Three-Body (Lagrange)",
    physics_config: PhysicsConfig | None = None,
) -> InitialConditionSet:
    """Generate restricted-three-body-like system with a numerically negligible test particle.

    Provides an analytical L4/L5 initial configuration for the idealized circular
    restricted three-body model.
    """
    if lagrange_point.upper() not in ("L4", "L5"):
        raise ValueError(f"lagrange_point must be 'L4' or 'L5', got '{lagrange_point}'")

    p_cfg = physics_config if physics_config is not None else PhysicsConfig()
    g = p_cfg.gravitational_constant

    mu = g * (m1 + m2)
    omega = np.sqrt(mu / (r ** 3))  # angular velocity
    v_circ = omega * r

    mu1 = m2 / (m1 + m2)
    mu2 = m1 / (m1 + m2)

    # Barycentric positions of primaries on X axis
    x1 = -mu1 * r
    x2 = mu2 * r

    pos1 = np.array([x1, 0.0, 0.0], dtype=float)
    vel1 = np.array([0.0, omega * x1, 0.0], dtype=float)

    pos2 = np.array([x2, 0.0, 0.0], dtype=float)
    vel2 = np.array([0.0, omega * x2, 0.0], dtype=float)

    # L4 / L5 form equilateral triangles with the primaries
    sign_y = 1.0 if lagrange_point.upper() == "L4" else -1.0
    x_L = (x1 + x2) * 0.5 + (mu2 - mu1) * 0.5 * r  # x = 0.5 * r - mu1 * r
    x_L = r * (0.5 - mu1)
    y_L = sign_y * r * (np.sqrt(3.0) / 2.0)

    pos_trojan = np.array([x_L, y_L, 0.0], dtype=float)
    # Velocity in inertial frame corresponds to rigid rotation with angular velocity omega:
    # v = omega x r = (-omega * y, omega * x, 0)
    vel_trojan = np.array([-omega * y_L, omega * x_L, 0.0], dtype=float)

    bodies = [
        CelestialBody("Primary Star", m1, pos1, vel1, 696340.0, (255, 230, 70), label="star"),
        CelestialBody("Secondary Planet", m2, pos2, vel2, 69911.0, (230, 160, 110), label="planet"),
        CelestialBody(f"Trojan Particle ({lagrange_point})", 1.0e10, pos_trojan, vel_trojan, 500.0, (180, 180, 220), label="asteroid"),
    ]

    return InitialConditionSet(
        name=name,
        description=f"Restricted-three-body-like system with a numerically negligible test particle at {lagrange_point} (analytical L4/L5 initial configuration for idealized circular model)",
        epoch=datetime(2000, 1, 1),
        bodies=bodies,
        physics_config=p_cfg,
    )


# ---------------------------------------------------------------------------
# Preset Registry
# ---------------------------------------------------------------------------

PRESET_REGISTRY: dict[str, Callable[[], InitialConditionSet]] = {
    "circular_two_body": create_circular_two_body,
    "eccentric_two_body": create_eccentric_two_body,
    "oriented_two_body": create_oriented_two_body,
    "earth_moon": create_earth_moon_preset,
    "binary_star": create_binary_star_preset,
    "restricted_three_body": create_restricted_three_body_preset,
}


def list_presets() -> list[str]:
    """Return sorted identifiers of all available initial-condition presets."""
    return sorted(list(PRESET_REGISTRY.keys()))


def get_preset(name: str, **kwargs) -> InitialConditionSet:
    """Retrieve and instantiate a preset by name.

    Parameters
    ----------
    name : str
        Preset identifier (case-insensitive).
    kwargs : dict
        Optional parameter overrides passed to the builder function.
    """
    key = name.lower().strip()
    if key not in PRESET_REGISTRY:
        raise ValueError(
            f"Unknown preset '{name}'. Available presets: {list_presets()}"
        )
    factory = PRESET_REGISTRY[key]
    return factory(**kwargs)
