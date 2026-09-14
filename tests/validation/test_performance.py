"""Performance regression and throughput baseline validation tests.

Establishes deterministic workloads and broad regression ceilings for:
- Solar System (39 bodies) stepping and conservation
- Scaled N=100 planetary cluster stepping
- Pure pairwise acceleration kernel throughput
- Diagnostics and snapshot relative overhead boundaries
"""
import time
import numpy as np
import pytest

from nbodiesgravity.data.loader import load_default_system
from nbodiesgravity.engine.diagnostics import ConservationTracker
from nbodiesgravity.engine.integrator import VelocityVerletIntegrator
from nbodiesgravity.engine.system import SolarSystem
from scripts.benchmark_scalability import generate_synthetic_system


def test_solar_system_stepping_performance():
    """Verify 39-body Solar System maintains throughput and energy conservation."""
    system = load_default_system()
    tracker = ConservationTracker(system.bodies)
    num_steps = 10
    dt = 1.0

    t0 = time.perf_counter()
    for _ in range(num_steps):
        system.step(dt)
    elapsed = max(1e-6, time.perf_counter() - t0)

    throughput = num_steps / elapsed
    # Conservative baseline: must achieve at least 5 steps/sec even under slow CI
    # (Typical optimized performance: > 80 steps/sec)
    assert throughput > 5.0, f"Solar System throughput regressed: {throughput:.1f} steps/s"

    report = tracker.evaluate(system.bodies)
    assert np.isfinite(report.current.total_energy)
    assert abs(report.energy_drift.rel_drift) < 1e-4


def test_n100_scaling_performance():
    """Verify 100-body synthetic system stepping maintains throughput."""
    system = generate_synthetic_system(100, seed=123)
    num_steps = 20
    dt = 1.0

    t0 = time.perf_counter()
    for _ in range(num_steps):
        system.step(dt)
    elapsed = max(1e-6, time.perf_counter() - t0)

    throughput = num_steps / elapsed
    # Must achieve at least 25 steps/sec (typical: > 500 steps/sec)
    assert throughput > 25.0, f"N=100 throughput regressed: {throughput:.1f} steps/s"
    assert system.cumulative_substeps >= num_steps


def test_acceleration_eval_throughput():
    """Verify pairwise acceleration kernel evaluates at least 1,000 times/sec for N=39."""
    system = load_default_system()
    pos = np.array([b.pos for b in system.bodies if b.active], dtype=float)
    vel = np.array([b.vel for b in system.bodies if b.active], dtype=float)
    mass = np.array([b.mass for b in system.bodies if b.active], dtype=float)
    integrator = VelocityVerletIntegrator(softening=system.softening)

    evals = 200
    t0 = time.perf_counter()
    for _ in range(evals):
        _ = integrator._accelerations(pos, mass)
    elapsed = max(1e-6, time.perf_counter() - t0)

    rate = evals / elapsed
    # Must evaluate at least 1,000 times/s (typical: > 25,000 evals/s)
    assert rate > 1000.0, f"Acceleration kernel throughput regressed: {rate:.1f} evals/s"


def test_diagnostics_and_snapshot_overhead_bounds():
    """Verify diagnostics and snapshots do not exceed 5x pure physics execution time."""
    n_bodies = 50
    steps = 25
    dt = 1.0

    # 1. Pure physics
    sys_pure = generate_synthetic_system(n_bodies, seed=42)
    t0 = time.perf_counter()
    for _ in range(steps):
        sys_pure.step(dt)
    t_pure = max(1e-5, time.perf_counter() - t0)

    # 2. Physics + Diagnostics
    sys_diag = generate_synthetic_system(n_bodies, seed=42)
    tracker = ConservationTracker(sys_diag.bodies)
    t0 = time.perf_counter()
    for _ in range(steps):
        sys_diag.step(dt)
        _ = tracker.evaluate(sys_diag.bodies)
    t_diag = max(1e-5, time.perf_counter() - t0)

    # 3. Physics + Diagnostics + Snapshot
    sys_snap = generate_synthetic_system(n_bodies, seed=42)
    tracker_snap = ConservationTracker(sys_snap.bodies)
    t0 = time.perf_counter()
    for _ in range(steps):
        sys_snap.step(dt)
        _ = tracker_snap.evaluate(sys_snap.bodies)
        _ = sys_snap.snapshot()
    t_snap = max(1e-5, time.perf_counter() - t0)

    # Overhead checks: diagnostics and snapshots must remain bounded
    assert t_diag < t_pure * 5.0, f"Diagnostics overhead too high: {t_diag / t_pure:.2f}x"
    assert t_snap < t_pure * 5.0, f"Snapshot overhead too high: {t_snap / t_pure:.2f}x"
