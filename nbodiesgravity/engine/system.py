from __future__ import annotations
import numpy as np
from .body import CelestialBody, BodyState, CollisionEvent
from .integrator import VelocityVerletIntegrator

#: Kilometres per Astronomical Unit — converts km radii to AU for collision tests.
KM_PER_AU: float = 1.495978707e8


class SolarSystem:
    """Owns a collection of CelestialBody objects and advances them in time.

    add_body / remove_body must only be called while the SimulationThread
    is paused — they are not thread-safe.

    body.active may be toggled from the UI thread at any time; it is read
    once per tick inside step() and any change takes effect within one tick.
    """

    def __init__(self, bodies: list[CelestialBody]) -> None:
        self._bodies: list[CelestialBody] = list(bodies)
        self._integrator = VelocityVerletIntegrator()

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
        return SolarSystem(bodies)

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
            return []

        positions  = np.array([b.pos for b in active])
        velocities = np.array([b.vel for b in active])
        masses     = np.array([b.mass for b in active])

        # Compute adaptive maximum step size based on minimum pairwise orbital timescale
        max_step = 1.0
        if len(active) >= 2:
            # pairwise coordinate difference, shape (N, N, 3)
            diff = positions[np.newaxis, :, :] - positions[:, np.newaxis, :]
            dist = np.sqrt(np.einsum("ijk,ijk->ij", diff, diff))
            np.fill_diagonal(dist, np.inf)

            # pairwise mass sums, shape (N, N)
            mass_sum = masses[np.newaxis, :] + masses[:, np.newaxis]

            from .integrator import G_AU_DAY
            
            # orbital period proxy: T_ij = 2 * pi * sqrt(d_ij^3 / (G * (M_i + M_j)))
            with np.errstate(divide='ignore', invalid='ignore'):
                t_orb = 2.0 * np.pi * np.sqrt(dist**3 / (G_AU_DAY * mass_sum + 1e-30))
            
            min_t_orb = np.nanmin(t_orb)
            if np.isfinite(min_t_orb):
                # Target ~100 steps per orbit (0.01 * T) capped at 1.0 day max, with a floor of 1e-5 to prevent infinite loops
                max_step = max(1e-5, min(1.0, 0.01 * min_t_orb))

        remaining = dt
        while remaining > 0:
            step_dt = min(remaining, max_step)
            positions, velocities = self._integrator.step(positions, velocities, masses, step_dt)
            remaining -= step_dt

        for i, body in enumerate(active):
            body.pos = positions[i]
            body.vel = velocities[i]

        return self._resolve_collisions()

    def _resolve_collisions(self) -> list[CollisionEvent]:
        """Merge any active bodies whose centres overlap (sum of physical radii).

        Survivor = larger mass (ties broken by the alphabetically-first name).
        Momentum is conserved; the survivor's radius grows by equal-density
        volume. Loops until no overlapping pair remains so chains collapse in a
        single call. Returns one CollisionEvent per merge performed.
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
