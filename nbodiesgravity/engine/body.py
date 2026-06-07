from __future__ import annotations
from dataclasses import dataclass
from typing import NamedTuple
import numpy as np


class BodyState(NamedTuple):
    """Thread-safe snapshot of a body's kinematic state.

    Use NamedTuple so the object is immutable at the Python level.
    Array *contents* can still be mutated, so snapshot() copies them.
    """
    name: str
    pos: np.ndarray   # AU, shape (3,)
    vel: np.ndarray   # AU/day, shape (3,)
    active: bool = True   # False = excluded from integrator, invisible in render


class CollisionEvent(NamedTuple):
    """Record of one merge: `absorbed` was removed into `survivor`."""
    absorbed: str   # name of the body that was removed
    survivor: str   # name of the body that absorbed it


@dataclass
class CelestialBody:
    """A gravitationally interacting body.

    Positions and velocities are always stored in the Solar System
    Barycenter (SSB) frame, in units of AU and AU/day.
    """
    name: str
    mass: float                         # kg
    pos: np.ndarray                     # AU, shape (3,)
    vel: np.ndarray                     # AU/day, shape (3,)
    radius: float                       # km — for rendering only
    color: tuple[float, float, float]   # RGB 0–1
    show_trail: bool = True
    active: bool = True                 # False = excluded from integrator, invisible in render
    label: str = "planet"               # star, planet, moon, dwarf planet, asteroid
    show_name: bool = True

    def snapshot(self) -> BodyState:
        """Return a thread-safe copy of kinematic state."""
        return BodyState(
            name=self.name,
            pos=self.pos.copy(),
            vel=self.vel.copy(),
            active=self.active,
        )
