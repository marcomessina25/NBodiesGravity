#!/usr/bin/env python3
"""Synthetic N-body scaling and component overhead benchmark script.

Measures scalability across varying body counts (N = 2, 10, 39, 100, 250, 500, 1000):
- Pure physics stepping throughput
- Physics + Diagnostics overhead
- Physics + Diagnostics + Snapshot overhead
- Memory allocation footprint (tracemalloc peak memory)

Usage:
    conda run -n nbodiesgravity python scripts/benchmark_scalability.py
    conda run -n nbodiesgravity python scripts/benchmark_scalability.py --markdown
    conda run -n nbodiesgravity python scripts/benchmark_scalability.py --json
    conda run -n nbodiesgravity python scripts/benchmark_scalability.py --bodies 2,10,39,100,250 --steps 50
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import time
import tracemalloc
from typing import Any

# Ensure project root is in sys.path when invoked directly
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np

from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.diagnostics import ConservationTracker
from nbodiesgravity.engine.system import SolarSystem
from nbodiesgravity.data.loader import load_default_system


def generate_synthetic_system(n_bodies: int, seed: int = 42) -> SolarSystem:
    """Generate a stable synthetic Keplerian planetary system with N bodies."""
    if n_bodies == 39:
        try:
            return load_default_system()
        except Exception:
            pass

    rng = np.random.default_rng(seed)
    # Gravitational constant G in AU^3 kg^-1 day^-2
    G = 1.48818e-34
    m_sun = 1.989e30

    sun = CelestialBody(
        name="Star",
        mass=m_sun,
        pos=np.zeros(3),
        vel=np.zeros(3),
        radius=696340.0,
        color=(1.0, 1.0, 0.0),
        label="star",
    )
    bodies = [sun]

    if n_bodies > 1:
        # Distribute semi-major axes logarithmically from 0.35 AU to 35.0 AU
        semi_major_axes = np.geomspace(0.35, 35.0, n_bodies - 1)
        # Random initial orbital angles
        angles = rng.uniform(0.0, 2.0 * np.pi, size=n_bodies - 1)
        # Small inclinations
        inclinations = rng.normal(0.0, np.radians(2.0), size=n_bodies - 1)
        # Planetary masses between 1e21 kg (dwarf) and 1e27 kg (gas giant)
        masses = 10.0 ** rng.uniform(21.0, 27.0, size=n_bodies - 1)

        for i in range(n_bodies - 1):
            r = semi_major_axes[i]
            theta = angles[i]
            inc = inclinations[i]

            pos = np.array([
                r * np.cos(theta) * np.cos(inc),
                r * np.sin(theta) * np.cos(inc),
                r * np.sin(inc),
            ])

            # Circular orbital speed: v = sqrt(G * M / r)
            v_mag = np.sqrt(G * m_sun / r)
            vel = np.array([
                -v_mag * np.sin(theta),
                v_mag * np.cos(theta),
                0.0,
            ])

            bodies.append(
                CelestialBody(
                    name=f"Body_{i+1:03d}",
                    mass=masses[i],
                    pos=pos,
                    vel=vel,
                    radius=6371.0,
                    color=(0.5, 0.5, 0.8),
                    label="planet",
                )
            )

    return SolarSystem(bodies)


def benchmark_configuration(
    n_bodies: int,
    num_steps: int = 50,
    dt: float = 1.0,
) -> dict[str, Any]:
    """Benchmark pure physics, physics+diagnostics, and physics+diagnostics+snapshots."""
    # 1. Pure Physics
    sys_pure = generate_synthetic_system(n_bodies)
    tracemalloc.start()
    t0 = time.perf_counter()
    pure_substeps = 0
    for _ in range(num_steps):
        sys_pure.step(dt)
        pure_substeps += sys_pure.last_substeps
    t_pure = max(1e-6, time.perf_counter() - t0)
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # 2. Physics + Diagnostics
    sys_diag = generate_synthetic_system(n_bodies)
    tracker = ConservationTracker(sys_diag.bodies)
    t0 = time.perf_counter()
    for _ in range(num_steps):
        sys_diag.step(dt)
        _ = tracker.evaluate(sys_diag.bodies)
    t_diag = max(1e-6, time.perf_counter() - t0)

    # 3. Physics + Diagnostics + Snapshot
    sys_full = generate_synthetic_system(n_bodies)
    tracker_full = ConservationTracker(sys_full.bodies)
    t0 = time.perf_counter()
    for _ in range(num_steps):
        sys_full.step(dt)
        _ = tracker_full.evaluate(sys_full.bodies)
        _ = sys_full.snapshot()
    t_full = max(1e-6, time.perf_counter() - t0)

    pure_steps_per_sec = num_steps / t_pure
    pure_substeps_per_sec = pure_substeps / t_pure
    diag_overhead_pct = ((t_diag - t_pure) / t_pure) * 100.0 if t_pure > 0 else 0.0
    snap_overhead_pct = ((t_full - t_diag) / t_pure) * 100.0 if t_pure > 0 else 0.0

    return {
        "n_bodies": n_bodies,
        "num_steps": num_steps,
        "pure_time_s": t_pure,
        "pure_steps_per_sec": pure_steps_per_sec,
        "pure_substeps_per_sec": pure_substeps_per_sec,
        "diag_time_s": t_diag,
        "diag_overhead_pct": diag_overhead_pct,
        "full_time_s": t_full,
        "snap_overhead_pct": snap_overhead_pct,
        "peak_memory_kb": peak_mem / 1024.0,
    }


def format_table_markdown(results: list[dict[str, Any]]) -> str:
    """Format benchmark results as a Markdown table."""
    lines = [
        "| N Bodies | Steps/s (Pure) | Substeps/s | Wall Time (50 steps) | Diag Overhead | Snap Overhead | Peak Mem (KB) |",
        "|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]
    for r in results:
        lines.append(
            f"| **{r['n_bodies']}** | {r['pure_steps_per_sec']:,.1f} | {r['pure_substeps_per_sec']:,.1f} | "
            f"{r['pure_time_s'] * 1000.0:,.1f} ms | {r['diag_overhead_pct']:+.1f}% | "
            f"{r['snap_overhead_pct']:+.1f}% | {r['peak_memory_kb']:,.1f} KB |"
        )
    return "\n".join(lines)


def format_table_ascii(results: list[dict[str, Any]]) -> str:
    """Format benchmark results as a plain text terminal table."""
    header = (
        f"{'N':>5} | {'Steps/s':>10} | {'Substeps/s':>12} | "
        f"{'50-Step Time':>13} | {'Diag +%':>9} | {'Snap +%':>9} | {'Peak Mem':>12}"
    )
    sep = "-" * len(header)
    lines = [sep, header, sep]
    for r in results:
        time_str = f"{r['pure_time_s'] * 1000.0:.1f} ms"
        lines.append(
            f"{r['n_bodies']:>5} | {r['pure_steps_per_sec']:>10.1f} | {r['pure_substeps_per_sec']:>12.1f} | "
            f"{time_str:>13} | {r['diag_overhead_pct']:>8.1f}% | "
            f"{r['snap_overhead_pct']:>8.1f}% | {r['peak_memory_kb']:>9.1f} KB"
        )
    lines.append(sep)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="NBodiesGravity Scalability Benchmark")
    parser.add_argument(
        "--bodies",
        type=str,
        default="2,10,39,100,250,500",
        help="Comma-separated list of body counts to evaluate (default: 2,10,39,100,250,500)",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=50,
        help="Number of outer simulation steps per benchmark tier (default: 50)",
    )
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--markdown", action="store_true", help="Output results as a Markdown table")

    args = parser.parse_args()
    body_counts = [int(n.strip()) for n in args.bodies.split(",") if n.strip()]

    results: list[dict[str, Any]] = []
    for n in body_counts:
        res = benchmark_configuration(n, num_steps=args.steps, dt=1.0)
        results.append(res)

    if args.json:
        print(json.dumps(results, indent=2))
    elif args.markdown:
        print(format_table_markdown(results))
    else:
        print(format_table_ascii(results))

    return 0


if __name__ == "__main__":
    sys.exit(main())
