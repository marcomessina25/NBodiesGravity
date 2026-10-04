"""Ejection detection and heuristic dynamical-stability assessment (no Qt, no UI).

Design rationale (see docs/stability_and_ejection.md)
-----------------------------------------------------
* A body is *ejected* only when it is, simultaneously,
    1. far from the rest of the system (``r > min_distance_au``) **and** far outside its extent,
    2. moving outward (``r . v > 0``), and
    3. gravitationally **unbound** from the rest of the system
       (specific orbital energy ``v^2/2 - G M_rest / r > 0``).
  A pure distance cut-off is not physical: a bound body on a very eccentric orbit
  (e.g. a long-period comet) is a legitimate member of the system, while an unbound
  one can never return. Condition 3 guarantees that an ejected body cannot come back
  (monopole approximation, valid because of condition 1).
* The stability verdict is a *heuristic* classification, not a proof. N-body stability
  over arbitrary time is undecidable in general; we combine well-established
  analytic criteria (Gladman 1993 Hill stability, Holman & Wiegert 1999 critical
  semi-major axes, orbit-crossing and unbound-body tests) and report which one fired.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence

import numpy as np

from .integrator import G_AU_DAY, SOFTENING
from .orbital_elements import compute_orbital_elements

AU_KM: float = 149_597_870.7
DAY_S: float = 86_400.0
AU_DAY_TO_KM_S: float = AU_KM / DAY_S

#: Bodies lighter than this fraction of the primary are treated as test particles
#: for pairwise stability analysis (they do not dynamically stir the system).
TEST_PARTICLE_MASS_RATIO: float = 1e-8
#: Bodies at least this fraction of the primary's mass are treated as stellar perturbers.
STELLAR_PERTURBER_MASS_RATIO: float = 0.1
#: Gladman (1993): two-planet Hill stability for circular orbits when delta > 2*sqrt(3).
HILL_UNSTABLE_DELTA: float = 2.0 * np.sqrt(3.0)
#: Heuristic "marginal" band (resonance / chaos may still lead to long-term instability).
HILL_MARGINAL_DELTA: float = 5.0


@dataclass(frozen=True)
class EscapeConfig:
    """Parameters of the ejection policy.

    min_distance_au : minimum distance from the rest-of-system barycenter before a body
        can be considered ejected. Unbound-ness is *also* required.
    extent_factor : the body must also be farther than ``extent_factor`` times the
        extent of the remaining system, so the monopole approximation is valid.
    """
    enabled: bool = True
    min_distance_au: float = 1000.0
    extent_factor: float = 5.0

    def __post_init__(self) -> None:
        if not np.isfinite(self.min_distance_au) or self.min_distance_au <= 0:
            raise ValueError(f"min_distance_au must be positive and finite, got {self.min_distance_au}")
        if not np.isfinite(self.extent_factor) or self.extent_factor < 1.0:
            raise ValueError(f"extent_factor must be >= 1, got {self.extent_factor}")


@dataclass(frozen=True)
class EjectionEvent:
    """A body that left the system and was removed from the integration.

    The ``*_jump`` fields are the change of the *remaining* system's conserved
    quantities caused by the removal; the diagnostics tracker uses them to rebase its
    baseline, so conservation drift keeps measuring numerical error only.
    """
    name: str
    mass: float                       # kg
    distance_au: float                # from the remaining system's barycenter
    speed_au_day: float               # relative to the remaining system's barycenter
    v_infinity_km_s: float            # asymptotic speed sqrt(2*eps)
    pos: np.ndarray = field(repr=False, default_factory=lambda: np.zeros(3))
    vel: np.ndarray = field(repr=False, default_factory=lambda: np.zeros(3))
    energy_jump: float = 0.0
    momentum_jump: np.ndarray = field(repr=False, default_factory=lambda: np.zeros(3))
    angular_momentum_jump: np.ndarray = field(repr=False, default_factory=lambda: np.zeros(3))
    com_jump: np.ndarray = field(repr=False, default_factory=lambda: np.zeros(3))
    mass_jump: float = 0.0
    momentum_scale_jump: float = 0.0


def find_ejected_index(
    positions: np.ndarray,
    velocities: np.ndarray,
    masses: np.ndarray,
    config: EscapeConfig,
    g_constant: float = G_AU_DAY,
    softening: float = SOFTENING,
) -> tuple[int, float, float, float] | None:
    """Return ``(index, distance, speed, v_inf_au_day)`` of the farthest ejected body, else None."""
    n = len(masses)
    if not config.enabled or n < 2:
        return None
    total_m = float(np.sum(masses))
    if total_m <= 0:
        return None
    com = np.sum(masses[:, None] * positions, axis=0) / total_m
    # Cheap pre-filter: nothing is far from the barycenter -> nothing to do.
    d_com = np.linalg.norm(positions - com, axis=1)
    candidates = np.nonzero(d_com > config.min_distance_au * 0.5)[0]
    if len(candidates) == 0:
        return None
    com_v = np.sum(masses[:, None] * velocities, axis=0) / total_m

    best = None
    for i in candidates[np.argsort(-d_com[candidates])]:
        m_rest = total_m - masses[i]
        if m_rest <= 0:
            continue
        com_rest = (total_m * com - masses[i] * positions[i]) / m_rest
        v_rest = (total_m * com_v - masses[i] * velocities[i]) / m_rest
        r_vec = positions[i] - com_rest
        v_vec = velocities[i] - v_rest
        r = float(np.linalg.norm(r_vec))
        if r <= config.min_distance_au:
            continue
        mask = np.ones(n, dtype=bool)
        mask[i] = False
        extent = float(np.max(np.linalg.norm(positions[mask] - com_rest, axis=1)))
        if r < config.extent_factor * extent and r < config.min_distance_au * 2.0:
            continue
        rad_vel = float(np.dot(r_vec, v_vec))
        eps = 0.5 * float(np.dot(v_vec, v_vec)) - g_constant * m_rest / np.sqrt(r * r + softening ** 2)
        if rad_vel < 0.0 and eps < 0.0 and r < config.min_distance_au * 2.0:
            continue
        v_inf = float(np.sqrt(2.0 * max(0.0, eps)))
        best = (int(i), r, float(np.linalg.norm(v_vec)), v_inf)
        break
    return best


class StabilityStatus(str, Enum):
    STABLE = "stable"
    MARGINAL = "marginal"
    UNSTABLE = "unstable"


_RANK = {StabilityStatus.STABLE: 0, StabilityStatus.MARGINAL: 1, StabilityStatus.UNSTABLE: 2}


@dataclass(frozen=True)
class StabilityReport:
    """Heuristic verdict plus the individual findings that produced it."""
    status: StabilityStatus
    reasons: tuple[str, ...]
    n_active: int
    n_ejected: int
    min_hill_delta: float | None = None
    primary: str | None = None

    @property
    def headline(self) -> str:
        return {
            StabilityStatus.STABLE: "Stable (no instability indicator fired)",
            StabilityStatus.MARGINAL: "Marginal / possibly unstable",
            StabilityStatus.UNSTABLE: "Unstable",
        }[self.status]


def _worse(a: StabilityStatus, b: StabilityStatus) -> StabilityStatus:
    return a if _RANK[a] >= _RANK[b] else b


def _holman_wiegert_s(a_b: float, e_b: float, mu: float) -> float:
    """Critical semi-major axis for S-type (planet around one star) orbits (HW99, eq. 1)."""
    return a_b * (0.464 - 0.380 * mu - 0.631 * e_b + 0.586 * mu * e_b + 0.150 * e_b ** 2 - 0.198 * mu * e_b ** 2)


def _holman_wiegert_p(a_b: float, e_b: float, mu: float) -> float:
    """Critical semi-major axis for P-type (circumbinary) orbits (HW99, eq. 3)."""
    return a_b * (1.60 + 5.10 * e_b - 2.22 * e_b ** 2 + 4.12 * mu - 4.27 * e_b * mu - 5.09 * mu ** 2 + 4.61 * e_b ** 2 * mu ** 2)


def assess_stability(
    names: Sequence[str],
    positions: np.ndarray,
    velocities: np.ndarray,
    masses: np.ndarray,
    ejected: Sequence[EjectionEvent] = (),
    g_constant: float = G_AU_DAY,
) -> StabilityReport:
    """Classify the instantaneous configuration as stable / marginal / unstable.

    Heuristic only: osculating elements w.r.t. the most massive body are used, so the
    result is most meaningful for hierarchical (star + planets + moons) systems.
    """
    n = len(masses)
    reasons: list[str] = []
    status = StabilityStatus.STABLE

    # --- Ejections that already happened are the strongest evidence of instability.
    if ejected:
        heavy = [e for e in ejected if e.mass > 0]
        names_str = ", ".join(e.name for e in ejected[:5]) + ("..." if len(ejected) > 5 else "")
        ref_mass = float(np.max(masses)) if n else 0.0
        significant = ref_mass > 0 and any(e.mass >= TEST_PARTICLE_MASS_RATIO * ref_mass for e in heavy)
        status = _worse(status, StabilityStatus.UNSTABLE if significant else StabilityStatus.MARGINAL)
        reasons.append(f"{len(ejected)} body(ies) ejected from the system: {names_str}")

    if n < 2:
        return StabilityReport(status, tuple(reasons), n, len(ejected))

    ip = int(np.argmax(masses))
    m_p = float(masses[ip])
    primary = str(names[ip])
    sig = masses >= TEST_PARTICLE_MASS_RATIO * m_p

    rel_pos = positions - positions[ip]
    rel_vel = velocities - velocities[ip]
    dist = np.linalg.norm(rel_pos, axis=1)

    stars = [i for i in range(n) if i != ip and masses[i] >= STELLAR_PERTURBER_MASS_RATIO * m_p]
    planets: list[tuple[int, object]] = []   # (index, OrbitalElements about primary)

    _elem_cache: dict[int, object] = {}

    def elems(i: int):
        if i not in _elem_cache:
            _elem_cache[i] = compute_orbital_elements(rel_pos[i], rel_vel[i], g_constant * (m_p + masses[i]))
        return _elem_cache[i]

    # --- Precompute potential satellite hosts and their Hill spheres
    host_indices = [k for k in range(n) if k != ip and k not in stars and masses[k] > 0]
    if host_indices:
        h_idx = np.array(host_indices, dtype=int)
        h_masses = masses[h_idx]
        h_r_hill_sq = (dist[h_idx] * (h_masses / (3.0 * m_p)) ** (1.0 / 3.0)) ** 2
        h_positions = positions[h_idx]

        def is_satellite(i: int) -> bool:
            m_i = masses[i]
            mask = (h_idx != i) & (h_masses > m_i)
            if not np.any(mask):
                return False
            diff = h_positions[mask] - positions[i]
            d_sq = np.sum(diff * diff, axis=1)
            return bool(np.any(d_sq < h_r_hill_sq[mask]))
    else:
        def is_satellite(i: int) -> bool:
            return False

    # --- Stellar perturbers: Holman & Wiegert (1999) or flyby test.
    for s in stars:
        es = elems(s)
        mu = float(masses[s] / (m_p + masses[s]))
        inner = [i for i in range(n) if i not in (ip, s) and sig[i] and masses[i] < STELLAR_PERTURBER_MASS_RATIO * m_p
                 and not is_satellite(i)]
        if es.is_bound:
            a_b, e_b = es.semi_major_axis, es.eccentricity
            a_cs = _holman_wiegert_s(a_b, e_b, mu)
            a_cp = _holman_wiegert_p(a_b, e_b, mu)
            for i in inner:
                ei = elems(i)
                if not ei.is_bound:
                    continue
                a_i = ei.semi_major_axis
                if a_i > a_b:   # circumbinary (P-type) regime
                    if a_i < a_cp:
                        status = _worse(status, StabilityStatus.UNSTABLE)
                        reasons.append(f"{names[i]}: circumbinary orbit a={a_i:.3g} AU inside P-type critical radius {a_cp:.3g} AU")
                else:
                    ratio = a_i / a_cs if a_cs > 0 else np.inf
                    if ratio > 1.0:
                        status = _worse(status, StabilityStatus.UNSTABLE)
                        reasons.append(f"{names[i]}: a={a_i:.3g} AU exceeds S-type critical radius {a_cs:.3g} AU of companion {names[s]}")
                    elif ratio > 0.8:
                        status = _worse(status, StabilityStatus.MARGINAL)
                        reasons.append(f"{names[i]}: a={a_i:.3g} AU is within 20% of S-type critical radius {a_cs:.3g} AU (companion {names[s]})")
            # A companion that is bound but whose periapsis reaches the planets also disrupts them.
            if es.periapsis > 0:
                for i in inner:
                    ei = elems(i)
                    if ei.is_bound and ei.apoapsis * 3.0 > es.periapsis and ei.semi_major_axis <= es.semi_major_axis:
                        status = _worse(status, StabilityStatus.MARGINAL)
                        reasons.append(f"{names[i]}: apoapsis {ei.apoapsis:.3g} AU within 3x of companion periapsis {es.periapsis:.3g} AU")
                        break
        else:
            q = es.periapsis
            threat = [i for i in inner if elems(i).is_bound and elems(i).apoapsis * 3.0 > q]
            if threat:
                status = _worse(status, StabilityStatus.UNSTABLE)
                reasons.append(f"Stellar flyby {names[s]} (periapsis {q:.3g} AU) disturbs the orbit of {names[threat[0]]}")
            else:
                status = _worse(status, StabilityStatus.MARGINAL)
                reasons.append(f"Unbound star {names[s]} passing through (periapsis {q:.3g} AU); long-term effect small")

    # --- Planet-like bodies around the primary: unbound, crossing, Hill separation.
    for i in range(n):
        if i == ip or i in stars or is_satellite(i):
            continue
        ei = elems(i)
        if not ei.is_bound:
            weight = StabilityStatus.UNSTABLE if sig[i] else StabilityStatus.MARGINAL
            status = _worse(status, weight)
            reasons.append(f"{names[i]} is unbound w.r.t. {primary} (e={ei.eccentricity:.3f}); escaping")
            continue
        if sig[i]:
            planets.append((i, ei))

    planets.sort(key=lambda t: t[1].semi_major_axis)
    min_delta: float | None = None
    for (i1, e1), (i2, e2) in zip(planets[:-1], planets[1:]):
        a1, a2 = e1.semi_major_axis, e2.semi_major_axis
        m1, m2 = float(masses[i1]), float(masses[i2])
        r_hill = ((m1 + m2) / (3.0 * m_p)) ** (1.0 / 3.0) * 0.5 * (a1 + a2)
        delta = (a2 - a1) / r_hill if r_hill > 0 else np.inf
        min_delta = delta if min_delta is None else min(min_delta, delta)
        pair = f"{names[i1]}-{names[i2]}"
        if e1.apoapsis >= e2.periapsis:
            status = _worse(status, StabilityStatus.UNSTABLE)
            reasons.append(f"{pair}: orbits cross (Q={e1.apoapsis:.3g} AU >= q={e2.periapsis:.3g} AU); stable only if resonance-protected")
        elif delta < HILL_UNSTABLE_DELTA:
            status = _worse(status, StabilityStatus.UNSTABLE)
            reasons.append(f"{pair}: separation {delta:.2f} mutual Hill radii < 2*sqrt(3) (Gladman 1993); not Hill-stable")
        elif delta < HILL_MARGINAL_DELTA:
            status = _worse(status, StabilityStatus.MARGINAL)
            reasons.append(f"{pair}: separation {delta:.2f} mutual Hill radii is small; long-term chaos possible")

    return StabilityReport(
        status=status,
        reasons=tuple(reasons),
        n_active=n,
        n_ejected=len(ejected),
        min_hill_delta=min_delta,
        primary=primary,
    )
