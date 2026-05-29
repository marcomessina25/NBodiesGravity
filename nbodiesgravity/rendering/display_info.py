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
        """Physical display radius in AU (camera-independent).

        Log-scale so moons and giants are proportionally distinguishable.
        Maps log10(radius_km) from [2, 6] → [0.0003, 0.003] AU.

        This keeps bodies smaller than typical moon orbital distances
        (e.g. Earth/Moon gap: ~0.00257 AU, Earth radius here: ~0.00165 AU)
        so moons are visible outside their parent planet when zoomed in.
        A camera-distance floor is applied in GLWidget to keep bodies
        visible when zoomed out to the full solar-system view.
        """
        log_r = math.log10(max(self.radius_km, 1.0))
        t = max(0.0, min(1.0, (log_r - 2.0) / (6.0 - 2.0)))
        return 0.0001 + t * (0.001 - 0.0001)
