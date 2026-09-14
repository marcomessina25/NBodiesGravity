"""Profiling script for NBodiesGravity v0.8.0.

Measures CPU time, wall-clock time, and memory/allocation profiles for:
- Force/acceleration calculation
- Adaptive timestep calculation
- Integrator sub-stepping
- Collision detection
- Diagnostics evaluation
- Snapshot construction
Across varying body counts (N=2, N=39, N=100, N=250).
"""
from __future__ import annotations
import sys
import time
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.integrator import VelocityVerletIntegrator, G_AU_DAY, SOFTENING
from nbodiesgravity.engine.system import SolarSystem, TimeStepConfig, compute_adaptive_dt
from nbodiesgravity.engine.diagnostics import ConservationTracker, DiagnosticsHistoryBuffer
from nbodiesgravity.data.loader import load_default_system


def generate_synthetic_system(n_bodies: int) -> SolarSystem:
    """Generate a synthetic stable planar multi-body system for profiling."""
    np.random.seed(42)
    bodies = []
    # Central massive star
    m_sun = 1.989e30
    bodies.append(
        CelestialBody(
            name="CentralStar",
            mass=m_sun,
            pos=np.zeros(3),
            vel=np.zeros(3),
            radius=695700.0,
            color=(1.0, 0.8, 0.2),
            label="star",
        )
    )

    # Distribute N-1 bodies in approximately circular Keplerian orbits
    radii = np.linspace(0.4, 30.0, n_bodies - 1)
    for i, r in enumerate(radii):
        angle = np.random.uniform(0, 2 * np.pi)
        pos = np.array([r * np.cos(angle), r * np.sin(angle), np.random.uniform(-0.01, 0.01)])
        v_circ = np.sqrt(G_AU_DAY * m_sun / r)
        vel = np.array([-v_circ * np.sin(angle), v_circ * np.cos(angle), 0.0])
        mass = np.random.uniform(1e22, 1e25)  # planet / dwarf mass
        bodies.append(
            CelestialBody(
                name=f"Body_{i+1}",
                mass=mass,
                pos=pos,
                vel=vel,
                radius=np.random.uniform(1000, 20000),
                color=(0.2, 0.5, 1.0),
                label="planet",
            )
        )

    return SolarSystem(bodies, softening=SOFTENING)


def profile_components(system: SolarSystem, n_steps: int = 100) -> dict[str, float]:
    """Profile individual subsystem operations."""
    active = [b for b in system.bodies if b.active]
    pos = np.array([b.pos for b in active], dtype=float)
    vel = np.array([b.vel for b in active], dtype=float)
    masses = np.array([b.mass for b in active], dtype=float)
    integrator = system._integrator
    config = system.timestep_config

    # 1. Accelerations only
    t0 = time.perf_counter()
    for _ in range(n_steps):
        integrator._accelerations(pos, masses)
    t_acc = (time.perf_counter() - t0) / n_steps

    # 2. Adaptive dt computation
    t0 = time.perf_counter()
    for _ in range(n_steps):
        compute_adaptive_dt(pos, masses, config)
    t_adapt = (time.perf_counter() - t0) / n_steps

    # 3. Single integrator step
    t0 = time.perf_counter()
    for _ in range(n_steps):
        integrator.step(pos, vel, masses, 0.1)
    t_integ_step = (time.perf_counter() - t0) / n_steps

    # 4. SolarSystem.step (including array extraction, substep loop, collisions)
    sys_copy = system.clone()
    t0 = time.perf_counter()
    for _ in range(n_steps):
        sys_copy.step(1.0)
    t_sys_step = (time.perf_counter() - t0) / n_steps

    # 5. Snapshot construction
    t0 = time.perf_counter()
    for _ in range(n_steps):
        system.snapshot()
    t_snap = (time.perf_counter() - t0) / n_steps

    # 6. Diagnostics evaluation
    tracker = ConservationTracker(system.bodies)
    snap = system.snapshot()
    t0 = time.perf_counter()
    for _ in range(n_steps):
        tracker.evaluate(snap)
    t_diag = (time.perf_counter() - t0) / n_steps

    return {
        "acc_us": t_acc * 1e6,
        "adapt_dt_us": t_adapt * 1e6,
        "integ_step_us": t_integ_step * 1e6,
        "sys_step_us": t_sys_step * 1e6,
        "snapshot_us": t_snap * 1e6,
        "diagnostics_us": t_diag * 1e6,
    }


def main() -> None:
    print("=" * 72)
    print("NBodiesGravity v0.8.0 Baseline Profiling Report")
    print("=" * 72)

    systems = [
        ("Solar System (N=39)", load_default_system()),
        ("Synthetic N=10", generate_synthetic_system(10)),
        ("Synthetic N=100", generate_synthetic_system(100)),
        ("Synthetic N=250", generate_synthetic_system(250)),
    ]

    print(f"{'System':<24} | {'Acc (µs)':<10} | {'Adapt dt (µs)':<13} | {'Integ (µs)':<10} | {'Sys.step (µs)':<13} | {'Snap (µs)':<10} | {'Diag (µs)':<10}")
    print("-" * 105)

    for name, sys in systems:
        n_steps = 100 if len(sys.bodies) <= 100 else 30
        res = profile_components(sys, n_steps=n_steps)
        print(
            f"{name:<24} | {res['acc_us']:>10.1f} | {res['adapt_dt_us']:>13.1f} | "
            f"{res['integ_step_us']:>10.1f} | {res['sys_step_us']:>13.1f} | "
            f"{res['snapshot_us']:>10.1f} | {res['diagnostics_us']:>10.1f}"
        )

    print("=" * 72)


if __name__ == "__main__":
    main()
