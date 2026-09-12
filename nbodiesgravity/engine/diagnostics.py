"""Scientific conservation diagnostics independent of UI.

Calculates kinetic energy, Plummer-softened gravitational potential energy,
total mechanical energy, linear momentum, angular momentum, center of mass,
and drift metrics across simulation runs.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence, Union
import numpy as np

from .body import CelestialBody, BodyState
from .integrator import G_AU_DAY, SOFTENING


@dataclass(frozen=True)
class MetricDrift:
    """Drift metrics comparing an initial value to the current state."""
    initial: float | np.ndarray
    current: float | np.ndarray
    abs_drift: float
    rel_drift: float
    diff_vector: np.ndarray | None = None


@dataclass(frozen=True)
class ConservationSnapshot:
    """Kinematic and dynamical conservation snapshot at a specific point in time."""
    kinetic_energy: float
    potential_energy: float
    total_energy: float
    linear_momentum: np.ndarray        # shape (3,) AU kg day⁻¹
    angular_momentum: np.ndarray       # shape (3,) AU² kg day⁻¹
    center_of_mass: np.ndarray         # shape (3,) AU
    total_mass: float                  # kg
    momentum_scale: float              # Σ m_i * |v_i| (total momentum capacity)


@dataclass(frozen=True)
class DiagnosticReport:
    """Comprehensive conservation comparison between baseline and current state."""
    initial: ConservationSnapshot
    current: ConservationSnapshot
    energy_drift: MetricDrift
    linear_momentum_drift: MetricDrift
    angular_momentum_drift: MetricDrift
    center_of_mass_drift: MetricDrift

    @property
    def normalized_momentum_drift(self) -> float:
        """Linear momentum drift normalized by total system momentum capacity Σ m_i |v_i|."""
        scale = max(self.initial.momentum_scale, self.current.momentum_scale)
        return float(self.linear_momentum_drift.abs_drift / scale) if scale > 1e-30 else 0.0


def _extract_arrays(
    source: Union[
        Sequence[CelestialBody],
        Sequence[BodyState],
        tuple[np.ndarray, np.ndarray, np.ndarray],
    ]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Extract (positions, velocities, masses) as numpy arrays from bodies or raw tuples."""
    if isinstance(source, tuple) and len(source) == 3:
        p, v, m = source
        return np.asarray(p, dtype=float), np.asarray(v, dtype=float), np.asarray(m, dtype=float)

    # Filter active bodies
    active = [b for b in source if getattr(b, "active", True)]
    if not active:
        return np.zeros((0, 3)), np.zeros((0, 3)), np.zeros(0)

    pos = np.array([b.pos for b in active], dtype=float)
    vel = np.array([b.vel for b in active], dtype=float)
    mass = np.array([getattr(b, "mass", 1.0) for b in active], dtype=float)
    return pos, vel, mass


def compute_kinetic_energy(masses: np.ndarray, velocities: np.ndarray) -> float:
    """Return total kinetic energy K = 0.5 * Σ m_i * |v_i|²."""
    if len(masses) == 0:
        return 0.0
    v_sq = np.einsum("ij,ij->i", velocities, velocities)
    return float(0.5 * np.sum(masses * v_sq))


def compute_potential_energy(
    positions: np.ndarray, masses: np.ndarray, softening: float = SOFTENING
) -> float:
    """Return softened gravitational potential energy U = - Σ_{i<j} G m_i m_j / sqrt(r_ij² + ε²)."""
    n = len(masses)
    if n < 2:
        return 0.0
    diff = positions[np.newaxis, :, :] - positions[:, np.newaxis, :]
    dist_sq = np.einsum("ijk,ijk->ij", diff, diff) + softening ** 2
    np.fill_diagonal(dist_sq, 1.0)   # prevent divide-by-zero when softening=0.0
    dist = np.sqrt(dist_sq)

    # Pairwise mass products G * m_i * m_j
    m_prod = G_AU_DAY * (masses[:, np.newaxis] * masses[np.newaxis, :])
    factor = m_prod / dist
    np.fill_diagonal(factor, 0.0)
    # Sum over distinct pairs i < j (half of symmetric matrix sum)
    return float(-0.5 * np.sum(factor))


def compute_total_energy(
    positions: np.ndarray,
    velocities: np.ndarray,
    masses: np.ndarray,
    softening: float = SOFTENING,
) -> float:
    """Return total mechanical energy E = K + U."""
    return compute_kinetic_energy(masses, velocities) + compute_potential_energy(
        positions, masses, softening=softening
    )


def compute_linear_momentum(masses: np.ndarray, velocities: np.ndarray) -> np.ndarray:
    """Return total linear momentum P = Σ m_i * v_i, shape (3,)."""
    if len(masses) == 0:
        return np.zeros(3, dtype=float)
    return np.sum(masses[:, np.newaxis] * velocities, axis=0)


def compute_angular_momentum(
    positions: np.ndarray, velocities: np.ndarray, masses: np.ndarray
) -> np.ndarray:
    """Return total angular momentum L = Σ m_i * (r_i x v_i), shape (3,)."""
    if len(masses) == 0:
        return np.zeros(3, dtype=float)
    cross = np.cross(positions, velocities)
    return np.sum(masses[:, np.newaxis] * cross, axis=0)


def compute_center_of_mass(positions: np.ndarray, masses: np.ndarray) -> np.ndarray:
    """Return center of mass R_cm = Σ m_i * r_i / Σ m_i, shape (3,)."""
    total_mass = float(np.sum(masses))
    if total_mass <= 0 or len(masses) == 0:
        return np.zeros(3, dtype=float)
    return np.sum(masses[:, np.newaxis] * positions, axis=0) / total_mass


def compute_snapshot(
    source: Union[
        Sequence[CelestialBody],
        Sequence[BodyState],
        tuple[np.ndarray, np.ndarray, np.ndarray],
    ],
    softening: float = SOFTENING,
) -> ConservationSnapshot:
    """Compute complete conservation snapshot from bodies or arrays."""
    pos, vel, mass = _extract_arrays(source)
    total_mass = float(np.sum(mass))
    ke = compute_kinetic_energy(mass, vel)
    pe = compute_potential_energy(pos, mass, softening=softening)
    p = compute_linear_momentum(mass, vel)
    l = compute_angular_momentum(pos, vel, mass)
    cm = compute_center_of_mass(pos, mass)
    p_scale = float(np.sum(mass * np.linalg.norm(vel, axis=1))) if len(mass) > 0 else 0.0

    return ConservationSnapshot(
        kinetic_energy=ke,
        potential_energy=pe,
        total_energy=ke + pe,
        linear_momentum=p,
        angular_momentum=l,
        center_of_mass=cm,
        total_mass=total_mass,
        momentum_scale=p_scale,
    )


def compute_drift(initial: float | np.ndarray, current: float | np.ndarray) -> MetricDrift:
    """Calculate absolute and relative drift between initial and current metric."""
    if isinstance(initial, (int, float)) and isinstance(current, (int, float)):
        diff = float(current - initial)
        base = abs(float(initial))
        rel = (diff / base) if base > 1e-30 else (0.0 if abs(diff) < 1e-30 else float("inf"))
        return MetricDrift(
            initial=float(initial),
            current=float(current),
            abs_drift=abs(diff),
            rel_drift=rel,
        )

    init_arr = np.asarray(initial, dtype=float)
    curr_arr = np.asarray(current, dtype=float)
    diff_arr = curr_arr - init_arr
    abs_err = float(np.linalg.norm(diff_arr))
    init_norm = float(np.linalg.norm(init_arr))
    rel = (abs_err / init_norm) if init_norm > 1e-30 else (0.0 if abs_err < 1e-30 else float("inf"))
    return MetricDrift(
        initial=init_arr,
        current=curr_arr,
        abs_drift=abs_err,
        rel_drift=rel,
        diff_vector=diff_arr,
    )


class ConservationTracker:
    """Tracks physical quantities and drift metrics against an initial baseline."""

    def __init__(
        self,
        initial_source: Union[
            Sequence[CelestialBody],
            Sequence[BodyState],
            tuple[np.ndarray, np.ndarray, np.ndarray],
        ],
        softening: float = SOFTENING,
    ) -> None:
        self.softening = softening
        self.initial_snapshot = compute_snapshot(initial_source, softening=softening)

    def evaluate(
        self,
        current_source: Union[
            Sequence[CelestialBody],
            Sequence[BodyState],
            tuple[np.ndarray, np.ndarray, np.ndarray],
        ],
    ) -> DiagnosticReport:
        """Evaluate current state and return a DiagnosticReport with drift metrics."""
        current_snap = compute_snapshot(current_source, softening=self.softening)
        e_drift = compute_drift(self.initial_snapshot.total_energy, current_snap.total_energy)
        p_drift = compute_drift(self.initial_snapshot.linear_momentum, current_snap.linear_momentum)
        l_drift = compute_drift(self.initial_snapshot.angular_momentum, current_snap.angular_momentum)
        cm_drift = compute_drift(self.initial_snapshot.center_of_mass, current_snap.center_of_mass)

        return DiagnosticReport(
            initial=self.initial_snapshot,
            current=current_snap,
            energy_drift=e_drift,
            linear_momentum_drift=p_drift,
            angular_momentum_drift=l_drift,
            center_of_mass_drift=cm_drift,
        )
