"""Numerical integrators for N-body gravitational simulation.

Units throughout: AU (position), AU/day (velocity), AU³ kg⁻¹ day⁻² (G).
The integrators are fully stateless: arrays in, arrays out.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable
import numpy as np
from .exceptions import NumericalIntegrityError

# Convert G from SI to AU³ kg⁻¹ day⁻²
# G_SI = 6.674e-11 m³ kg⁻¹ s⁻²
# 1 AU = 1.495978707e11 m,  1 day = 86400 s
G_AU_DAY: float = 6.674e-11 * (86400.0 ** 2) / (1.495978707e11 ** 3)

#: Softening length (AU) — prevents force singularities at close approach
SOFTENING: float = 1e-4

#: Maximum permitted displacement (AU) for a single sub-step
MAX_DISPLACEMENT_PER_STEP: float = 100.0


def compute_accelerations(
    positions: np.ndarray,
    masses: np.ndarray,
    softening: float = SOFTENING,
    g_constant: float = G_AU_DAY,
) -> np.ndarray:
    """Return gravitational accelerations for all bodies using Plummer softening.

    Parameters
    ----------
    positions : (N, 3) ndarray — body positions in AU
    masses    : (N,)   ndarray — body masses in kg
    softening : float   — softening length in AU
    g_constant: float   — gravitational constant in AU³ kg⁻¹ day⁻²

    Returns
    -------
    (N, 3) ndarray — accelerations in AU day⁻²
    """
    if not np.all(np.isfinite(positions)):
        raise NumericalIntegrityError("Non-finite coordinates encountered in acceleration calculation.")
    if not np.all(np.isfinite(masses)):
        raise NumericalIntegrityError("Non-finite masses encountered in acceleration calculation.")

    # diff[i, j] = r_j - r_i, shape (N, N, 3)
    diff = positions[np.newaxis, :, :] - positions[:, np.newaxis, :]
    # Squared distance with softening, shape (N, N)
    dist_sq = np.einsum("ijk,ijk->ij", diff, diff)
    dist_sq += softening ** 2
    # In-place distance cubed: dist_sq * sqrt(dist_sq) eliminates temporary allocation
    dist_sq *= np.sqrt(dist_sq)
    # factor[i, j] = G * m_j / |r_j - r_i|³
    factor = (g_constant * masses[np.newaxis, :]) / dist_sq
    np.fill_diagonal(factor, 0.0)   # zero out self-interaction
    acc = np.einsum("ij,ijk->ik", factor, diff)
    if not np.all(np.isfinite(acc)):
        raise NumericalIntegrityError("Non-finite accelerations computed.")
    return acc


@dataclass(frozen=True)
class IntegratorConfig:
    """Configuration specification for numerical integrators.

    Parameters
    ----------
    name : str
        Integrator identifier (e.g., "velocity_verlet", "leapfrog").
    softening : float
        Plummer softening length in AU.
    max_displacement : float
        Safety displacement bound in AU.
    parameters : dict
        Additional algorithm-specific parameters.
    """
    name: str = "velocity_verlet"
    softening: float = SOFTENING
    max_displacement: float = MAX_DISPLACEMENT_PER_STEP
    parameters: dict[str, float | int | str | bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.softening < 0 or not np.isfinite(self.softening):
            raise ValueError(f"softening must be non-negative and finite, got {self.softening}")
        if self.max_displacement <= 0 or not np.isfinite(self.max_displacement):
            raise ValueError(f"max_displacement must be positive and finite, got {self.max_displacement}")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "softening": float(self.softening),
            "max_displacement": float(self.max_displacement),
            "parameters": dict(self.parameters),
        }

    @classmethod
    def from_dict(cls, data: dict) -> IntegratorConfig:
        return cls(
            name=str(data.get("name", "velocity_verlet")),
            softening=float(data.get("softening", SOFTENING)),
            max_displacement=float(data.get("max_displacement", MAX_DISPLACEMENT_PER_STEP)),
            parameters=dict(data.get("parameters", {})),
        )


@runtime_checkable
class Integrator(Protocol):
    """Protocol defining the standard interface for N-body numerical integrators."""
    name: str
    softening: float
    max_displacement: float

    def step(
        self,
        positions: np.ndarray,
        velocities: np.ndarray,
        masses: np.ndarray,
        dt: float,
        a0: np.ndarray | None = None,
        return_acc: bool = False,
    ) -> tuple[np.ndarray, np.ndarray] | tuple[np.ndarray, np.ndarray, np.ndarray]:
        ...

    def reset(self) -> None:
        ...


class VelocityVerletIntegrator:
    """Symplectic Velocity Verlet integrator (validated reference baseline).

    Conserves orbital energy far better than plain Euler integration
    over long time spans, making it suitable for multi-year simulations.
    Second-order symplectic method with substep acceleration reuse support.
    """
    name: str = "velocity_verlet"

    def __init__(
        self,
        softening: float = SOFTENING,
        max_displacement: float = MAX_DISPLACEMENT_PER_STEP,
    ) -> None:
        if softening < 0 or not np.isfinite(softening):
            raise ValueError(f"softening must be non-negative and finite, got {softening}")
        if max_displacement <= 0 or not np.isfinite(max_displacement):
            raise ValueError(f"max_displacement must be positive and finite, got {max_displacement}")
        self.softening = float(softening)
        self.max_displacement = float(max_displacement)

    def _accelerations(
        self, positions: np.ndarray, masses: np.ndarray
    ) -> np.ndarray:
        """Return gravitational accelerations for all bodies."""
        return compute_accelerations(positions, masses, softening=self.softening)

    def reset(self) -> None:
        """Reset internal integrator state (stateless for Velocity Verlet)."""
        pass

    def step(
        self,
        positions: np.ndarray,
        velocities: np.ndarray,
        masses: np.ndarray,
        dt: float,
        a0: np.ndarray | None = None,
        return_acc: bool = False,
    ) -> tuple[np.ndarray, np.ndarray] | tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Advance by one timestep dt (days).

        Parameters
        ----------
        positions : (N, 3) ndarray
        velocities : (N, 3) ndarray
        masses : (N,) ndarray
        dt : float (days)
        a0 : (N, 3) ndarray or None
            If provided, reuses previously computed initial acceleration.
        return_acc : bool
            If True, returns (new_pos, new_vel, a1) allowing consecutive substeps
            to reuse the final acceleration without redundant re-evaluation.

        Returns
        -------
        (new_pos, new_vel) or (new_pos, new_vel, a1)
        """
        if dt <= 0 or not np.isfinite(dt):
            raise NumericalIntegrityError(f"Step dt must be positive and finite, got {dt}")
        if not np.all(np.isfinite(positions)):
            raise NumericalIntegrityError("Non-finite positions in step input.")
        if not np.all(np.isfinite(velocities)):
            raise NumericalIntegrityError("Non-finite velocities in step input.")

        if a0 is None:
            a0 = self._accelerations(positions, masses)
        new_pos = positions + velocities * dt + 0.5 * a0 * (dt ** 2)

        # Extreme displacement guard
        if len(positions) > 0:
            disp = np.linalg.norm(new_pos - positions, axis=1)
            if np.any(disp > self.max_displacement):
                max_disp = float(np.max(disp))
                raise NumericalIntegrityError(
                    f"Extreme displacement detected in single step: {max_disp:.2e} AU "
                    f"(limit: {self.max_displacement:.2e} AU)"
                )

        a1 = self._accelerations(new_pos, masses)
        new_vel = velocities + 0.5 * (a0 + a1) * dt

        if not np.all(np.isfinite(new_pos)) or not np.all(np.isfinite(new_vel)):
            raise NumericalIntegrityError("Non-finite state generated by integration step.")

        if return_acc:
            return new_pos, new_vel, a1
        return new_pos, new_vel


class LeapfrogIntegrator:
    """Second-order symplectic Leapfrog integrator (Kick-Drift-Kick formulation).

    Coordinates and velocities are evaluated synchronously at integer timesteps:
        v(t + dt/2) = v(t) + 0.5 * a(t) * dt       [Kick 1]
        x(t + dt)   = x(t) + v(t + dt/2) * dt      [Drift]
        a(t + dt)   = a(x(t + dt))                 [Force evaluation]
        v(t + dt)   = v(t + dt/2) + 0.5 * a(t + dt)* dt  [Kick 2]

    Supports acceleration reuse across consecutive substeps when return_acc=True.
    """
    name: str = "leapfrog"

    def __init__(
        self,
        softening: float = SOFTENING,
        max_displacement: float = MAX_DISPLACEMENT_PER_STEP,
    ) -> None:
        if softening < 0 or not np.isfinite(softening):
            raise ValueError(f"softening must be non-negative and finite, got {softening}")
        if max_displacement <= 0 or not np.isfinite(max_displacement):
            raise ValueError(f"max_displacement must be positive and finite, got {max_displacement}")
        self.softening = float(softening)
        self.max_displacement = float(max_displacement)

    def _accelerations(
        self, positions: np.ndarray, masses: np.ndarray
    ) -> np.ndarray:
        """Return gravitational accelerations for all bodies."""
        return compute_accelerations(positions, masses, softening=self.softening)

    def reset(self) -> None:
        """Reset internal integrator state (stateless for synchronous KDK)."""
        pass

    def step(
        self,
        positions: np.ndarray,
        velocities: np.ndarray,
        masses: np.ndarray,
        dt: float,
        a0: np.ndarray | None = None,
        return_acc: bool = False,
    ) -> tuple[np.ndarray, np.ndarray] | tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Advance system by one timestep dt using Kick-Drift-Kick Leapfrog.

        Parameters
        ----------
        positions : (N, 3) ndarray
        velocities : (N, 3) ndarray
        masses : (N,) ndarray
        dt : float (days)
        a0 : (N, 3) ndarray or None
            Reused initial acceleration at t.
        return_acc : bool
            If True, returns final acceleration a1 at t + dt.

        Returns
        -------
        (new_pos, new_vel) or (new_pos, new_vel, a1)
        """
        if dt <= 0 or not np.isfinite(dt):
            raise NumericalIntegrityError(f"Step dt must be positive and finite, got {dt}")
        if not np.all(np.isfinite(positions)):
            raise NumericalIntegrityError("Non-finite positions in step input.")
        if not np.all(np.isfinite(velocities)):
            raise NumericalIntegrityError("Non-finite velocities in step input.")

        # Kick 1: advance velocities by half-step
        if a0 is None:
            a0 = self._accelerations(positions, masses)
        v_half = velocities + 0.5 * a0 * dt

        # Drift: advance positions by full step using half-step velocities
        new_pos = positions + v_half * dt

        # Extreme displacement guard
        if len(positions) > 0:
            disp = np.linalg.norm(new_pos - positions, axis=1)
            if np.any(disp > self.max_displacement):
                max_disp = float(np.max(disp))
                raise NumericalIntegrityError(
                    f"Extreme displacement detected in single step: {max_disp:.2e} AU "
                    f"(limit: {self.max_displacement:.2e} AU)"
                )

        # Force evaluation at new positions
        a1 = self._accelerations(new_pos, masses)

        # Kick 2: advance half-step velocities by half-step to full step
        new_vel = v_half + 0.5 * a1 * dt

        if not np.all(np.isfinite(new_pos)) or not np.all(np.isfinite(new_vel)):
            raise NumericalIntegrityError("Non-finite state generated by integration step.")

        if return_acc:
            return new_pos, new_vel, a1
        return new_pos, new_vel


INTEGRATOR_REGISTRY: dict[str, type] = {
    "velocity_verlet": VelocityVerletIntegrator,
    "leapfrog": LeapfrogIntegrator,
}


def create_integrator(
    config_or_name: IntegratorConfig | str = "velocity_verlet",
    *,
    softening: float | None = None,
    max_displacement: float | None = None,
    **kwargs,
) -> Integrator:
    """Factory creating an integrator instance from a name or IntegratorConfig.

    Parameters
    ----------
    config_or_name : IntegratorConfig or str
        Integrator specification.
    softening : float, optional
        Override softening length if provided.
    max_displacement : float, optional
        Override max displacement bound if provided.

    Returns
    -------
    Integrator instance conforming to the Integrator protocol.
    """
    if isinstance(config_or_name, IntegratorConfig):
        name = config_or_name.name
        s = softening if softening is not None else config_or_name.softening
        disp = max_displacement if max_displacement is not None else config_or_name.max_displacement
        extra_params = dict(config_or_name.parameters)
        extra_params.update(kwargs)
    elif isinstance(config_or_name, str):
        name = config_or_name.lower().strip()
        s = softening if softening is not None else SOFTENING
        disp = max_displacement if max_displacement is not None else MAX_DISPLACEMENT_PER_STEP
        extra_params = kwargs
    else:
        raise TypeError(f"Expected IntegratorConfig or str, got {type(config_or_name).__name__}")

    if name not in INTEGRATOR_REGISTRY:
        raise ValueError(
            f"Unknown integrator '{name}'. Available integrators: {sorted(list(INTEGRATOR_REGISTRY.keys()))}"
        )

    cls = INTEGRATOR_REGISTRY[name]
    return cls(softening=s, max_displacement=disp, **extra_params)
