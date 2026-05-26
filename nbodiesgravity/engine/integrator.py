"""Velocity Verlet integrator for N-body gravitational simulation.

Units throughout: AU (position), AU/day (velocity), AU³ kg⁻¹ day⁻² (G).
The integrator is fully stateless: arrays in, arrays out.
"""
from __future__ import annotations
import numpy as np

# Convert G from SI to AU³ kg⁻¹ day⁻²
# G_SI = 6.674e-11 m³ kg⁻¹ s⁻²
# 1 AU = 1.495978707e11 m,  1 day = 86400 s
G_AU_DAY: float = 6.674e-11 * (86400.0 ** 2) / (1.495978707e11 ** 3)

#: Softening length (AU) — prevents force singularities at close approach
SOFTENING: float = 1e-4


class VelocityVerletIntegrator:
    """Symplectic Velocity Verlet integrator.

    Conserves orbital energy far better than plain Euler integration
    over long time spans, making it suitable for multi-year simulations.
    """

    def __init__(self, softening: float = SOFTENING) -> None:
        self.softening = softening

    def _accelerations(
        self, positions: np.ndarray, masses: np.ndarray
    ) -> np.ndarray:
        """Return gravitational accelerations for all bodies.

        Parameters
        ----------
        positions : (N, 3) ndarray — body positions in AU
        masses    : (N,)   ndarray — body masses in kg

        Returns
        -------
        (N, 3) ndarray — accelerations in AU day⁻²
        """
        # diff[i, j] = r_j - r_i, shape (N, N, 3)
        diff = positions[np.newaxis, :, :] - positions[:, np.newaxis, :]
        # Squared distance with softening, shape (N, N)
        dist_sq = np.einsum("ijk,ijk->ij", diff, diff) + self.softening ** 2
        dist_cubed = dist_sq ** 1.5
        # factor[i, j] = G * m_j / |r_j - r_i|³
        factor = G_AU_DAY * masses[np.newaxis, :] / dist_cubed
        np.fill_diagonal(factor, 0.0)   # zero out self-interaction
        # acc[i] = Σ_j factor[i,j] * diff[i,j]
        return np.einsum("ij,ijk->ik", factor, diff)

    def step(
        self,
        positions: np.ndarray,
        velocities: np.ndarray,
        masses: np.ndarray,
        dt: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Advance by one timestep dt (days).

        Returns new (positions, velocities), both (N, 3).
        """
        a0 = self._accelerations(positions, masses)
        new_pos = positions + velocities * dt + 0.5 * a0 * dt ** 2
        a1 = self._accelerations(new_pos, masses)
        new_vel = velocities + 0.5 * (a0 + a1) * dt
        return new_pos, new_vel
