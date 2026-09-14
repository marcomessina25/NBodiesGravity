#!/usr/bin/env python3
"""Headless performance benchmarking and numerical diagnostic reporting tool.

Measures:
- Bodies simulated & execution duration
- Physics updates per second & simulation speed (days/real-second)
- Integration time & acceleration calculation performance
- Timestep statistics (min, max, average dt, total substeps)
- Conservation drift metrics (energy, momentum, angular momentum, center of mass)

Usage:
    conda run -n nbodiesgravity python scripts/benchmark_engine.py --benchmark earth_sun --years 1.0
    conda run -n nbodiesgravity python scripts/benchmark_engine.py --all --json
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any

# Ensure project root is in sys.path when invoked directly
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np

from nbodiesgravity.data.loader import load_default_system
from nbodiesgravity.engine.benchmarks import (
    create_circular_two_body,
    create_eccentric_two_body,
    create_earth_sun,
    create_earth_moon,
    create_three_body_lagrange,
)
from nbodiesgravity.engine.diagnostics import ConservationTracker
from nbodiesgravity.engine.system import SolarSystem, compute_adaptive_dt


BENCHMARKS = {
    "earth_sun": ("Earth-Sun (1 yr orbit)", create_earth_sun, 365.25),
    "earth_moon": ("Earth-Moon (5 lunar months)", create_earth_moon, 136.6),
    "circular": ("Circular Two-Body", create_circular_two_body, 365.25),
    "eccentric": ("Eccentric Two-Body (e=0.5)", lambda: create_eccentric_two_body(e=0.5), 365.25),
    "lagrange": ("Lagrange Three-Body Equilateral", create_three_body_lagrange, 365.25),
    "solar_system": ("Full Solar System (39 bodies)", load_default_system, 365.25),
}


def run_benchmark(
    name: str,
    system_factory: Any,
    duration_days: float,
    step_dt: float = 1.0,
) -> dict[str, Any]:
    """Run a headless simulation benchmark and return structured diagnostic metrics."""
    system: SolarSystem = system_factory()
    tracker = ConservationTracker(system.bodies)
    num_bodies = len([b for b in system.bodies if b.active])

    t_start = time.perf_counter()
    days_elapsed = 0.0
    steps_count = 0
    substeps_count = 0
    dts_recorded: list[float] = []

    while days_elapsed < duration_days - 1e-9:
        dt = min(step_dt, duration_days - days_elapsed)

        # Estimate adaptive substep
        active = [b for b in system.bodies if b.active]
        pos = np.array([b.pos for b in active], dtype=float)
        mass = np.array([b.mass for b in active], dtype=float)
        adaptive_dt = compute_adaptive_dt(pos, mass, system.timestep_config)
        dts_recorded.append(adaptive_dt)
        substeps_in_step = int(np.ceil(dt / max(1e-9, adaptive_dt)))
        substeps_count += max(1, substeps_in_step)

        system.step(dt)
        days_elapsed += dt
        steps_count += 1

    t_end = time.perf_counter()
    wall_clock_sec = max(1e-6, t_end - t_start)
    report = tracker.evaluate(system.bodies)

    avg_dt = float(np.mean(dts_recorded)) if dts_recorded else dt
    min_dt = float(np.min(dts_recorded)) if dts_recorded else dt
    max_dt = float(np.max(dts_recorded)) if dts_recorded else dt

    return {
        "benchmark": name,
        "bodies_simulated": num_bodies,
        "duration_sim_days": days_elapsed,
        "wall_clock_seconds": wall_clock_sec,
        "physics_steps": steps_count,
        "substeps_total": substeps_count,
        "steps_per_second": steps_count / wall_clock_sec,
        "sim_days_per_real_second": days_elapsed / wall_clock_sec,
        "average_dt_days": avg_dt,
        "min_dt_days": min_dt,
        "max_dt_days": max_dt,
        "energy": {
            "initial": report.initial.total_energy,
            "final": report.current.total_energy,
            "rel_drift": report.energy_drift.rel_drift,
        },
        "linear_momentum": {
            "initial_norm": float(np.linalg.norm(report.initial.linear_momentum)),
            "final_norm": float(np.linalg.norm(report.current.linear_momentum)),
            "normalized_drift": report.normalized_momentum_drift,
        },
        "angular_momentum": {
            "initial_norm": float(np.linalg.norm(report.initial.angular_momentum)),
            "final_norm": float(np.linalg.norm(report.current.angular_momentum)),
            "rel_drift": report.angular_momentum_drift.rel_drift,
        },
        "center_of_mass": {
            "abs_drift": report.center_of_mass_drift.abs_drift,
        },
    }


def format_report_text(data: dict[str, Any]) -> str:
    """Format benchmark metrics into a human-readable table."""
    lines = [
        "=" * 64,
        f"Benchmark: {data['benchmark']}",
        "=" * 64,
        f"Bodies Simulated         : {data['bodies_simulated']}",
        f"Simulated Duration       : {data['duration_sim_days']:.2f} days ({data['duration_sim_days'] / 365.25:.2f} years)",
        f"Wall-Clock Time          : {data['wall_clock_seconds']:.4f} s",
        f"Throughput               : {data['steps_per_second']:.1f} steps/s",
        f"Simulation Rate          : {data['sim_days_per_real_second']:.1f} sim-days/real-s",
        f"Substeps (Total / Avg dt): {data['substeps_total']} / {data['average_dt_days']:.6e} days",
        f"Timestep Bounds [Min/Max]: [{data['min_dt_days']:.6e}, {data['max_dt_days']:.6e}] days",
        "-" * 64,
        "Conservation Diagnostics:",
        f"  Relative Energy Drift       : {data['energy']['rel_drift']:+.6e}",
        f"  Normalized Momentum Drift   : {data['linear_momentum']['normalized_drift']:.6e}",
        f"  Relative Angular Mom. Drift : {data['angular_momentum']['rel_drift']:+.6e}",
        f"  Center of Mass Drift        : {data['center_of_mass']['abs_drift']:.6e} AU",
        "=" * 64,
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="NBodiesGravity Numerical Benchmarking Tool")
    parser.add_argument(
        "--benchmark", "-b",
        choices=list(BENCHMARKS.keys()),
        default="earth_sun",
        help="Benchmark system to evaluate (default: earth_sun)",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Run all available benchmark configurations sequentially",
    )
    parser.add_argument(
        "--days", type=float, default=None,
        help="Simulation duration in days",
    )
    parser.add_argument(
        "--years", type=float, default=None,
        help="Simulation duration in years (multiplies by 365.25 days)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output machine-readable JSON format",
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="Save report to file path",
    )
    args = parser.parse_args()

    targets = list(BENCHMARKS.keys()) if args.all else [args.benchmark]
    results = []

    for key in targets:
        title, factory, default_days = BENCHMARKS[key]
        if args.days is not None:
            duration = args.days
        elif args.years is not None:
            duration = args.years * 365.25
        else:
            duration = default_days

        res = run_benchmark(title, factory, duration_days=duration)
        results.append(res)
        if not args.json:
            print(format_report_text(res))
            print()

    if args.json:
        payload = results[0] if len(results) == 1 else results
        formatted_json = json.dumps(payload, indent=2)
        print(formatted_json)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(formatted_json)
    elif args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            for r in results:
                f.write(format_report_text(r) + "\n\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
