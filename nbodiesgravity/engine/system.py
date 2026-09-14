from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from .body import CelestialBody, BodyState, CollisionEvent
from .exceptions import NumericalIntegrityError, ComputationalBudgetExceededError
from .integrator import VelocityVerletIntegrator, SOFTENING

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


def compute_adaptive_dt(
    positions: np.ndarray, masses: np.ndarray, config: TimeStepConfig | None = None
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

    # pairwise coordinate difference, shape (N, N, 3)
    diff = positions[np.newaxis, :, :] - positions[:, np.newaxis, :]
    dist = np.sqrt(np.einsum("ijk,ijk->ij", diff, diff))
    np.fill_diagonal(dist, np.inf)

    mass_sum = masses[np.newaxis, :] + masses[:, np.newaxis]

    from .integrator import G_AU_DAY
    
    with np.errstate(divide='ignore', invalid='ignore'):
        t_orb = 2.0 * np.pi * np.sqrt(dist**3 / (G_AU_DAY * mass_sum + 1e-30))

    min_t_orb = np.nanmin(t_orb)
    if np.isfinite(min_t_orb):
        # Target safety_factor * min_t_orb, bounded between min_dt and max_dt
        return float(max(config.min_dt, min(config.max_dt, config.safety_factor * min_t_orb)))

    return config.max_dt


class SolarSystem:
    """Owns a collection of CelestialBody objects and advances them in time.

    add_body / remove_body must only be called while the SimulationThread
    is paused — they are not thread-safe.

    body.active may be toggled from the UI thread at any time; it is read
    once per tick inside step() and any change takes effect within one tick.
    """

    def __init__(
        self,
        bodies: list[CelestialBody],
        timestep_config: TimeStepConfig | None = None,
        softening: float = SOFTENING,
    ) -> None:
        self._bodies: list[CelestialBody] = list(bodies)
        self._timestep_config = timestep_config if timestep_config is not None else TimeStepConfig()
        self._integrator = VelocityVerletIntegrator(softening=softening)
        self._last_substeps: int = 0
        self._cumulative_substeps: int = 0
        self._last_adaptive_dt: float = 0.0

    @property
    def softening(self) -> float:
        return self._integrator.softening

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
        """Return a deep copy of the system and its bodies."""
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
            softening=self._integrator.softening,
        )

    @property
    def bodies(self) -> list[CelestialBody]:
        """Shallow copy — callers cannot mutate the internal list."""
        return list(self._bodies)

    def step(self, dt: float) -> list[CollisionEvent]:
        """Advance all *active* bodies by dt days using Velocity Verlet.

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

        max_step = compute_adaptive_dt(positions, masses, self._timestep_config)

        remaining = dt
        substeps = 0
        eps_dt = min(1e-9, 1e-4 * max_step)
        while remaining > eps_dt:
            substeps += 1
            if substeps > self._timestep_config.max_substeps:
                raise ComputationalBudgetExceededError(
                    f"Maximum substeps ({self._timestep_config.max_substeps}) exceeded for step dt={dt}. "
                    f"Selected substep dt={max_step:.6e} days."
                )
            step_dt = min(remaining, max_step)
            positions, velocities = self._integrator.step(positions, velocities, masses, step_dt)
            remaining -= step_dt

        self._last_substeps = substeps
        self._cumulative_substeps += substeps
        self._last_adaptive_dt = max_step

        for i, body in enumerate(active):
            body.pos = positions[i]
            body.vel = velocities[i]

        return self._resolve_collisions()

    def _resolve_collisions(self) -> list[CollisionEvent]:
        """Merge any active bodies whose centres overlap (sum of physical radii).

        Survivor = larger mass (ties broken by the alphabetically-first name).
        Center of mass, mass, and linear momentum are conserved; the survivor's
        radius grows by equal-density volume. Loops until no overlapping pair remains so
        chains collapse in a single call. Returns one CollisionEvent per merge performed.
        """
        events: list[CollisionEvent] = []
        while True:
            active = [b for b in self._bodies if b.active]
            if len(active) < 2:
                break

            closest = None   # (dist, body_i, body_j)
            for i in range(len(active)):
                for j in range(i + 1, len(active)):
                    bi, bj = active[i], active[j]
                    # NaN/inf positions (blown-up bodies) are intentionally not handled here:
                    # a NaN distance makes `dist < threshold` False, so they are silently skipped.
                    # Blow-up is detected and reported separately by SimulationThread.blow_up_detected.
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
