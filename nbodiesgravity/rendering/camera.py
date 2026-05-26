"""3D camera that orbits a tracked body.

Physics always runs in SSB coordinates.  The renderer subtracts
center_pos from every body position before passing to OpenGL — the
physics engine is never modified by view changes.
"""
from __future__ import annotations
import numpy as np
from nbodiesgravity.engine.body import BodyState


class Camera:
    def __init__(self) -> None:
        self.center_pos: np.ndarray = np.zeros(3, dtype=np.float32)
        self.azimuth: float = 0.3       # radians
        self.elevation: float = 0.5     # radians
        self.distance: float = 6.0      # AU
        self._center_name: str = "Sun"

    @property
    def center_name(self) -> str:
        return self._center_name

    def set_center(self, name: str) -> None:
        self._center_name = name

    def update_center_pos(self, snapshot: list[BodyState]) -> None:
        for state in snapshot:
            if state.name == self._center_name:
                self.center_pos = state.pos.astype(np.float32)
                return

    def view_matrix(self) -> np.ndarray:
        """Return column-major 4×4 lookAt matrix (float32)."""
        eye = np.array([
            self.distance * np.cos(self.elevation) * np.sin(self.azimuth),
            self.distance * np.sin(self.elevation),
            self.distance * np.cos(self.elevation) * np.cos(self.azimuth),
        ], dtype=np.float32)
        return _look_at(eye, np.zeros(3, dtype=np.float32),
                        np.array([0.0, 1.0, 0.0], dtype=np.float32))

    def rotate(self, d_az: float, d_el: float) -> None:
        self.azimuth += d_az
        self.elevation = float(np.clip(
            self.elevation + d_el, -np.pi / 2 + 0.01, np.pi / 2 - 0.01
        ))

    def zoom(self, factor: float) -> None:
        self.distance = max(0.001, self.distance * factor)


def _look_at(
    eye: np.ndarray, target: np.ndarray, up: np.ndarray
) -> np.ndarray:
    f = target - eye
    f /= np.linalg.norm(f)
    r = np.cross(f, up)
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    m = np.eye(4, dtype=np.float32)
    m[0, :3] = r
    m[1, :3] = u
    m[2, :3] = -f
    m[0, 3] = float(-np.dot(r, eye))
    m[1, 3] = float(-np.dot(u, eye))
    m[2, 3] = float(np.dot(f, eye))
    return m
