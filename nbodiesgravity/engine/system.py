from __future__ import annotations
import numpy as np
from .body import CelestialBody, BodyState
from .integrator import VelocityVerletIntegrator


class SolarSystem:
    """Owns a collection of CelestialBody objects and advances them in time.

    add_body / remove_body must only be called while the SimulationThread
    is paused — they are not thread-safe.
    """

    def __init__(self, bodies: list[CelestialBody]) -> None:
        self._bodies: list[CelestialBody] = list(bodies)
        self._integrator = VelocityVerletIntegrator()

    @property
    def bodies(self) -> list[CelestialBody]:
        """Shallow copy — callers cannot mutate the internal list."""
        return list(self._bodies)

    def step(self, dt: float) -> None:
        """Advance all *active* bodies by dt days using Velocity Verlet.

        Inactive bodies (body.active is False) are skipped entirely —
        their pos/vel remain frozen at their last integrated values.
        """
        active = [b for b in self._bodies if b.active]
        if not active:
            return
        positions  = np.array([b.pos for b in active])
        velocities = np.array([b.vel for b in active])
        masses     = np.array([b.mass for b in active])
        new_pos, new_vel = self._integrator.step(positions, velocities, masses, dt)
        for i, body in enumerate(active):
            body.pos = new_pos[i]
            body.vel = new_vel[i]

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
