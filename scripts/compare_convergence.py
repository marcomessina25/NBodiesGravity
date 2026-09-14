"""Compare Fixed-Step vs. Adaptive-Step Integration on Canonical Benchmarks.

Quantifies relative energy drift, momentum drift, total substeps taken, and wall-clock
runtime for fixed-step vs. adaptive-step Velocity Verlet integration.
"""
from __future__ import annotations
import sys
import time
from pathlib import Path
import numpy as np

# Ensure project root is in sys.path when invoked directly
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from nbodiesgravity.engine.benchmarks import (
    create_circular_two_body,
    create_eccentric_two_body,
    create_earth_sun,
)
from nbodiesgravity.engine.diagnostics import ConservationTracker
from nbodiesgravity.engine.system import SolarSystem, TimeStepConfig


def run_comparison(
    system_factory,
    name: str,
    duration_days: float,
    fixed_dts: list[float] = [1.0, 0.25, 0.05],
    adaptive_safety_factors: list[float] = [0.05, 0.01, 0.002],
) -> None:
    print("=" * 80)
    print(f"Convergence Characterization: {name} (Duration: {duration_days} days)")
    print("=" * 80)
    print(f"{'Mode':<18} | {'Param':<10} | {'Substeps':<10} | {'Rel Energy Drift':<18} | {'Norm Mom Drift':<16} | {'Runtime (s)':<11}")
    print("-" * 80)

    # 1. Fixed dt runs
    for dt in fixed_dts:
        system = system_factory()
        # Set min_dt = max_dt = dt to force fixed stepping
        system.timestep_config = TimeStepConfig(min_dt=dt, max_dt=dt, safety_factor=1.0)
        tracker = ConservationTracker(system.bodies, softening=system.softening)

        t_start = time.perf_counter()
        remaining = duration_days
        while remaining > 1e-9:
            step_size = min(remaining, dt)
            system.step(step_size)
            remaining -= step_size
        t_elapsed = time.perf_counter() - t_start

        report = tracker.evaluate(system.bodies)
        print(
            f"{'Fixed Step':<18} | {f'dt={dt:.3f}':<10} | {system.cumulative_substeps:<10} | "
            f"{report.energy_drift.rel_drift:+18.6e} | {report.normalized_momentum_drift:16.6e} | {t_elapsed:11.4f}"
        )

    print("-" * 80)

    # 2. Adaptive dt runs
    for sf in adaptive_safety_factors:
        system = system_factory()
        system.timestep_config = TimeStepConfig(min_dt=1e-5, max_dt=1.0, safety_factor=sf)
        tracker = ConservationTracker(system.bodies, softening=system.softening)

        t_start = time.perf_counter()
        remaining = duration_days
        # Outer updates of 1.0 day
        while remaining > 1e-9:
            step_size = min(remaining, 1.0)
            system.step(step_size)
            remaining -= step_size
        t_elapsed = time.perf_counter() - t_start

        report = tracker.evaluate(system.bodies)
        print(
            f"{'Adaptive Step':<18} | {f'sf={sf:.3f}':<10} | {system.cumulative_substeps:<10} | "
            f"{report.energy_drift.rel_drift:+18.6e} | {report.normalized_momentum_drift:16.6e} | {t_elapsed:11.4f}"
        )

    print("=" * 80)
    print()


def main() -> None:
    # 1. Circular Two-Body (Benchmark B)
    run_comparison(create_circular_two_body, "Benchmark B: Circular Two-Body", duration_days=365.25)

    # 2. Eccentric Two-Body e=0.5 (Benchmark C)
    run_comparison(create_eccentric_two_body, "Benchmark C: Eccentric Two-Body (e=0.5)", duration_days=365.25)

    # 3. Earth-Sun 1-Year (Benchmark D)
    run_comparison(create_earth_sun, "Benchmark D: Earth-Sun", duration_days=365.25)


if __name__ == "__main__":
    main()
