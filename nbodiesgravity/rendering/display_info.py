"""Rendering metadata for a celestial body.

Kept entirely separate from physics (engine/) — the rendering layer has
zero physics imports.  main.py bridges the two by converting CelestialBody
fields into BodyDisplayInfo when a system is loaded.
"""
from __future__ import annotations
import math
from dataclasses import dataclass


@dataclass
class BodyDisplayInfo:
    name: str
    radius_km: float
    color: tuple[float, float, float]   # RGB 0–1
    is_star: bool = False

    @property
    def display_radius(self) -> float:
        """Visible radius in AU.

        Applies a log scale so tiny moons and giant planets are both
        legible without dominating the view.
        Maps log10(radius_km) from [2, 6] → [0.01, 0.25] AU.
        """
        log_r = math.log10(max(self.radius_km, 1.0))
        t = max(0.0, min(1.0, (log_r - 2.0) / (6.0 - 2.0)))
        return 0.01 + t * (0.25 - 0.01)
