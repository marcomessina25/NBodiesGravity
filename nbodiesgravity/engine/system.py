from __future__ import annotations
from dataclasses import dataclass
import numpy as np

from .body import CelestialBody, BodyState, CollisionEvent
from .exceptions import NumericalIntegrityError, ComputationalBudgetExceededError
from .integrator import (
    Integrator,
    IntegratorConfig,
    VelocityVerletIntegrator,
    create_integrator,
    G_AU_DAY,
    SOFTENING,
)
from .physics import PhysicsConfig, CollisionConfig

#: Kilometres per Astronomical Unit — converts km radii to AU for collision tests.
KM_PER_AU: float = 1.495978707e8


@dataclass(frozen=True)
class TimeStepConfig:
    """Configuration parameters for adaptive timestep selection.

    Parameters
    ----------
    min_dt : float
        Minimum permitted integration substep in days. Default is 1e-5 days (~0.864 s).
    max_dt : float
        Maximum permitted integration substep in days. Default is 1.0 day.
    safety_factor : float
        Fraction of minimum estimated pairwise orbital timescale to target per step.
        Default is 0.01 (~100 steps per orbit).
    max_substeps : int
        Maximum substeps permitted within a single step() call before raising
        ComputationalBudgetExceededError. Default is 10,000.
    """
    min_dt: float = 1e-5
    max_dt: float = 1.0
    safety_factor: float = 0.01
    max_substeps: int = 10_000

    def __post_init__(self) -> None:
        if self.min_dt <= 0:
            raise ValueError(f"min_dt must be positive, got {self.min_dt}")
        if self.max_dt < self.min_dt:
            raise ValueError(f"max_dt ({self.max_dt}) cannot be less than min_dt ({self.min_dt})")
        if self.safety_factor <= 0:
            raise ValueError(f"safety_factor must be positive, got {self.safety_factor}")
        if self.max_substeps <= 0:
            raise ValueError(f"max_substeps must be positive, got {self.max_substeps}")

    def to_dict(self) -> dict:
        return {
            "min_dt": float(self.min_dt),
            "max_dt": float(self.max_dt),
            "safety_factor": float(self.safety_factor),
            "max_substeps": int(self.max_substeps),
        }

    @classmethod
    def from_dict(cls, data: dict) -> TimeStepConfig:
        return cls(
            min_dt=float(data.get("min_dt", 1e-5)),
            max_dt=float(data.get("max_dt", 1.0)),
            safety_factor=float(data.get("safety_factor", 0.01)),
            max_substeps=int(data.get("max_substeps", 10_000)),
        )


def compute_adaptive_dt(
    positions: np.ndarray,
    masses: np.ndarray,
    config: TimeStepConfig | None = None,
    g_constant: float = G_AU_DAY,
) -> float:
    """Compute adaptive timestep (in days) based on shortest orbital timescale.

    Calculates pairwise orbital periods using Keplerian 2-body approximations
    and scales the minimum period by config.safety_factor, clamped between
    config.min_dt and config.max_dt.
    """
    if config is None:
        config = TimeStepConfig()

    n = len(positions)
    if n < 2:
        return config.max_dt

    # Upper-triangle pairs (i < j) avoid redundant comparisons and diagonal infinities
    i_idx, j_idx = np.triu_indices(n, k=1)
    diff = positions[i_idx] - positions[j_idx]
    dist_sq = np.sum(diff * diff, axis=-1)
    dist_cb = dist_sq * np.sqrt(dist_sq)
    mass_sum = masses[i_idx] + masses[j_idx]

    with np.errstate(divide='ignore', invalid='ignore'):
        t_orb = 2.0 * np.pi * np.sqrt(dist_cb / (g_constant * mass_sum + 1e-30))

    min_t_orb = np.nanmin(t_orb)
    if np.isfinite(min_t_orb):
        # Target safety_factor * min_t_orb, bounded between min_dt and max_dt
        return float(max(config.min_dt, min(config.max_dt, config.safety_factor * min_t_orb)))

    return config.max_dt


class SolarSystem:
    """Owns a collection of CelestialBody objects and advances them in time.

    Supports pluggable integrators, configurable physical models, adaptive timestepping,
    and center-of-mass conserving collisions.

    add_body / remove_body must only be called while the SimulationThread
    is paused — they are not thread-safe.

    body.active may be toggled from the UI thread at any time; it is read
    once per tick inside step() and any change takes effect within one tick.
    """

    def __init__(
        self,
        bodies: list[CelestialBody],
        timestep_config: TimeStepConfig | None = None,
        softening: float | None = None,
        integrator: Integrator | None = None,
        integrator_config: IntegratorConfig | None = None,
        physics_config: PhysicsConfig | None = None,
        collision_config: CollisionConfig | None = None,
    ) -> None:
        self._bodies: list[CelestialBody] = list(bodies)
        self._timestep_config = timestep_config if timestep_config is not None else TimeStepConfig()

        # Physics configuration
        if physics_config is not None:
            self._physics_config = physics_config
        else:
            soft_val = softening if softening is not None else SOFTENING
            self._physics_config = PhysicsConfig(softening_length=soft_val)

        g_val = self._physics_config.gravitational_constant
        soft_val = self._physics_config.softening_length

        # Collision configuration
        self._collision_config = collision_config if collision_config is not None else CollisionConfig()

        # Integrator initialization
        if integrator is not None:
            self._integrator = integrator
            if hasattr(integrator, "g_constant") and physics_config is not None:
                try:
                    integrator.g_constant = g_val
                except (AttributeError, TypeError):
                    pass
            self._integrator_config = IntegratorConfig(
                name=getattr(integrator, "name", "velocity_verlet"),
                softening=integrator.softening,
                max_displacement=integrator.max_displacement,
                g_constant=getattr(integrator, "g_constant", g_val),
            )
        elif integrator_config is not None:
            if physics_config is not None and integrator_config.g_constant != g_val:
                integrator_config = IntegratorConfig(
                    name=integrator_config.name,
                    softening=integrator_config.softening,
                    max_displacement=integrator_config.max_displacement,
                    g_constant=g_val,
                    parameters=integrator_config.parameters,
                )
            self._integrator_config = integrator_config
            self._integrator = create_integrator(integrator_config)
        else:
            self._integrator_config = IntegratorConfig(
                name="velocity_verlet",
                softening=soft_val,
                g_constant=g_val,
            )
            self._integrator = VelocityVerletIntegrator(softening=soft_val, g_constant=g_val)

        self._last_substeps: int = 0
        self._cumulative_substeps: int = 0
        self._last_adaptive_dt: float = 0.0
        self._collision_history: list[CollisionEvent] = []

    @property
    def softening(self) -> float:
        return self._integrator.softening

    @property
    def integrator(self) -> Integrator:
        return self._integrator

    @property
    def integrator_config(self) -> IntegratorConfig:
        return self._integrator_config

    def set_integrator(
        self, integrator_or_config: Integrator | IntegratorConfig | str
    ) -> None:
        """Switch active integrator cleanly without modifying body states."""
        g_val = self._physics_config.gravitational_constant
        if isinstance(integrator_or_config, Integrator):
            self._integrator = integrator_or_config
            if hasattr(integrator_or_config, "g_constant"):
                try:
                    integrator_or_config.g_constant = g_val
                except (AttributeError, TypeError):
                    pass
            self._integrator_config = IntegratorConfig(
                name=getattr(integrator_or_config, "name", "velocity_verlet"),
                softening=integrator_or_config.softening,
                max_displacement=integrator_or_config.max_displacement,
                g_constant=getattr(integrator_or_config, "g_constant", g_val),
            )
        elif isinstance(integrator_or_config, IntegratorConfig):
            if integrator_or_config.g_constant != g_val:
                integrator_or_config = IntegratorConfig(
                    name=integrator_or_config.name,
                    softening=integrator_or_config.softening,
                    max_displacement=integrator_or_config.max_displacement,
                    g_constant=g_val,
                    parameters=integrator_or_config.parameters,
                )
            self._integrator_config = integrator_or_config
            self._integrator = create_integrator(integrator_or_config)
        elif isinstance(integrator_or_config, str):
            self._integrator_config = IntegratorConfig(
                name=integrator_or_config,
                softening=self.softening,
                g_constant=g_val,
            )
            self._integrator = create_integrator(self._integrator_config)
        else:
            raise TypeError(f"Invalid integrator specification type: {type(integrator_or_config)}")

    @property
    def physics_config(self) -> PhysicsConfig:
        return self._physics_config

    @physics_config.setter
    def physics_config(self, config: PhysicsConfig) -> None:
        self._physics_config = config
        # Update integrator softening and g_constant if altered in physics config
        self.set_integrator(
            IntegratorConfig(
                name=self._integrator_config.name,
                softening=config.softening_length,
                max_displacement=self._integrator_config.max_displacement,
                g_constant=config.gravitational_constant,
                parameters=self._integrator_config.parameters,
            )
        )

    @property
    def collision_config(self) -> CollisionConfig:
        return self._collision_config

    @collision_config.setter
    def collision_config(self, config: CollisionConfig) -> None:
        self._collision_config = config

    @property
    def collision_history(self) -> list[CollisionEvent]:
        return list(self._collision_history)

    @property
    def last_substeps(self) -> int:
        return self._last_substeps

    @property
    def cumulative_substeps(self) -> int:
        return self._cumulative_substeps

    @property
    def last_adaptive_dt(self) -> float:
        return self._last_adaptive_dt

    def reset_stats(self) -> None:
        self._last_substeps = 0
        self._cumulative_substeps = 0
        self._last_adaptive_dt = 0.0

    @property
    def timestep_config(self) -> TimeStepConfig:
        return self._timestep_config

    @timestep_config.setter
    def timestep_config(self, config: TimeStepConfig) -> None:
        self._timestep_config = config

    def clone(self) -> SolarSystem:
        """Return a deep copy of the system, bodies, and configuration."""
        bodies = [
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
            for b in self._bodies
        ]
        return SolarSystem(
            bodies,
            timestep_config=self._timestep_config,
            integrator=create_integrator(self._integrator_config),
            physics_config=self._physics_config,
            collision_config=self._collision_config,
        )

    @property
    def bodies(self) -> list[CelestialBody]:
        """Shallow copy — callers cannot mutate the internal list."""
        return list(self._bodies)

    def step(self, dt: float) -> list[CollisionEvent]:
        """Advance all *active* bodies by dt days using active integrator.

        Handles high-velocity / tight orbits (like moons) by dynamically
        sub-stepping the integration step to maintain accuracy.

        Returns a list of CollisionEvent for any merges that occurred.
        """
        active = [b for b in self._bodies if b.active]
        if not active:
            self._last_substeps = 0
            self._last_adaptive_dt = 0.0
            return []

        if dt <= 0:
            raise NumericalIntegrityError(f"Step dt must be positive, got {dt}")
        if not np.isfinite(dt):
            raise NumericalIntegrityError(f"Step dt must be finite, got {dt}")

        positions  = np.array([b.pos for b in active], dtype=float)
        velocities = np.array([b.vel for b in active], dtype=float)
        masses     = np.array([b.mass for b in active], dtype=float)

        max_step = compute_adaptive_dt(
            positions, masses, self._timestep_config, g_constant=self._physics_config.gravitational_constant
        )

        remaining = dt
        substeps = 0
        eps_dt = min(1e-9, 1e-4 * max_step)
        a0 = None
        while remaining > eps_dt:
            substeps += 1
            if substeps > self._timestep_config.max_substeps:
                raise ComputationalBudgetExceededError(
                    f"Maximum substeps ({self._timestep_config.max_substeps}) exceeded for step dt={dt}. "
                    f"Selected substep dt={max_step:.6e} days."
                )
            step_dt = min(remaining, max_step)
            positions, velocities, a0 = self._integrator.step(
                positions, velocities, masses, step_dt, a0=a0, return_acc=True
            )
            remaining -= step_dt

        self._last_substeps = substeps
        self._cumulative_substeps += substeps
        self._last_adaptive_dt = max_step

        for i, body in enumerate(active):
            body.pos = positions[i]
            body.vel = velocities[i]

        events = self._resolve_collisions()
        self._collision_history.extend(events)
        return events

    def step_once(self, dt: float | None = None) -> list[CollisionEvent]:
        """Advance all active bodies by exactly one substep.

        If dt is None, evaluates adaptive dt from orbital timescales.
        """
        active = [b for b in self._bodies if b.active]
        if not active:
            self._last_substeps = 0
            self._last_adaptive_dt = 0.0
            return []

        positions  = np.array([b.pos for b in active], dtype=float)
        velocities = np.array([b.vel for b in active], dtype=float)
        masses     = np.array([b.mass for b in active], dtype=float)

        step_dt = dt if dt is not None else compute_adaptive_dt(
            positions, masses, self._timestep_config, g_constant=self._physics_config.gravitational_constant
        )
        if step_dt <= 0 or not np.isfinite(step_dt):
            raise NumericalIntegrityError(f"Step dt must be positive and finite, got {step_dt}")

        positions, velocities = self._integrator.step(
            positions, velocities, masses, step_dt
        )
        self._last_substeps = 1
        self._cumulative_substeps += 1
        self._last_adaptive_dt = step_dt

        for i, body in enumerate(active):
            body.pos = positions[i]
            body.vel = velocities[i]

        events = self._resolve_collisions()
        self._collision_history.extend(events)
        return events

    def advance(self, duration: float) -> list[CollisionEvent]:
        """Advance simulation by a total duration in days using adaptive stepping."""
        if duration < 0 or not np.isfinite(duration):
            raise NumericalIntegrityError(f"Advance duration must be non-negative and finite, got {duration}")
        if duration == 0:
            return []
        return self.step(duration)

    def _resolve_collisions(self) -> list[CollisionEvent]:
        """Merge any active bodies whose centres overlap (sum of physical radii).

        Survivor = larger mass (ties broken by the alphabetically-first name).
        Center of mass, mass, and linear momentum are conserved; the survivor's
        radius grows by equal-density volume. Loops until no overlapping pair remains so
        chains collapse in a single call. Returns one CollisionEvent per merge performed.
        """
        if not self._collision_config.enabled or self._collision_config.model == "ignore":
            return []

        # Vectorized candidate pre-check: if no active bodies overlap, return immediately
        active = [b for b in self._bodies if b.active]
        n = len(active)
        if n < 2:
            return []

        pos_arr = np.array([b.pos for b in active], dtype=float)
        rad_arr = np.array([b.radius for b in active], dtype=float) / KM_PER_AU
        i_idx, j_idx = np.triu_indices(n, k=1)
        diff_c = pos_arr[i_idx] - pos_arr[j_idx]
        dist_sq = np.sum(diff_c * diff_c, axis=-1)
        thresh_sq = (rad_arr[i_idx] + rad_arr[j_idx]) ** 2
        if not np.any(dist_sq < thresh_sq):
            return []

        events: list[CollisionEvent] = []
        while True:
            active = [b for b in self._bodies if b.active]
            if len(active) < 2:
                break

            closest = None   # (dist, body_i, body_j)
            for i in range(len(active)):
                for j in range(i + 1, len(active)):
                    bi, bj = active[i], active[j]
                    dist = float(np.linalg.norm(bi.pos - bj.pos))
                    threshold = (bi.radius + bj.radius) / KM_PER_AU
                    if dist < threshold and (closest is None or dist < closest[0]):
                        closest = (dist, bi, bj)

            if closest is None:
                break

            _, ba, bb = closest
            if ba.mass > bb.mass or (ba.mass == bb.mass and ba.name < bb.name):
                survivor, absorbed = ba, bb
            else:
                survivor, absorbed = bb, ba

            total_mass = survivor.mass + absorbed.mass
            survivor.pos = (
                survivor.mass * survivor.pos + absorbed.mass * absorbed.pos
            ) / total_mass
            survivor.vel = (
                survivor.mass * survivor.vel + absorbed.mass * absorbed.vel
            ) / total_mass
            survivor.radius = (survivor.radius ** 3 + absorbed.radius ** 3) ** (1.0 / 3.0)
            survivor.mass = total_mass

            self._bodies = [b for b in self._bodies if b is not absorbed]
            events.append(CollisionEvent(absorbed=absorbed.name, survivor=survivor.name))

        return events

    def snapshot(self) -> list[BodyState]:
        """Return a thread-safe copy of all body states."""
        return [b.snapshot() for b in self._bodies]

    def add_body(self, body: CelestialBody) -> None:
        """Append a body. Call only while simulation is paused."""
        self._bodies.append(body)

    def remove_body(self, name: str) -> None:
        """Remove the named body. No-op if not found."""
        self._bodies = [b for b in self._bodies if b.name != name]

    def get_body(self, name: str) -> CelestialBody | None:
        """Return the body with the given name, or None if not found."""
        for b in self._bodies:
            if b.name == name:
                return b
        return None
