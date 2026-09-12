"""Convergence validation suite: demonstrates second-order O(dt²) accuracy of Velocity Verlet."""
import numpy as np
import pytest
from nbodiesgravity.engine.benchmarks import create_circular_two_body, create_eccentric_two_body
from nbodiesgravity.engine.system import TimeStepConfig


def _run_fixed_step(create_fn, total_days: float, step_size: float) -> np.ndarray:
    """Run simulation for total_days using a fixed step size and return final positions."""
    system = create_fn()
    # Disable adaptive stepping reduction so step_size is strictly used
    system.timestep_config = TimeStepConfig(
        min_dt=step_size,
        max_dt=step_size,
        max_substeps=100_000,
    )
    t = 0.0
    while t < total_days - 1e-9:
        dt = min(step_size, total_days - t)
        system.step(dt)
        t += dt

    return np.array([b.pos.copy() for b in system.bodies])


def test_velocity_verlet_second_order_convergence_circular():
    """Verify that halving the timestep reduces position error by ~4x (O(dt²))."""
    duration = 50.0  # 50 days

    # Reference solution with high resolution dt = 0.01 days
    pos_ref = _run_fixed_step(create_circular_two_body, duration, step_size=0.01)

    # Coarse steps
    dt1 = 1.0
    dt2 = 0.5
    dt3 = 0.25

    pos_dt1 = _run_fixed_step(create_circular_two_body, duration, step_size=dt1)
    pos_dt2 = _run_fixed_step(create_circular_two_body, duration, step_size=dt2)
    pos_dt3 = _run_fixed_step(create_circular_two_body, duration, step_size=dt3)

    # Calculate position errors for secondary body
    err1 = float(np.linalg.norm(pos_dt1[1] - pos_ref[1]))
    err2 = float(np.linalg.norm(pos_dt2[1] - pos_ref[1]))
    err3 = float(np.linalg.norm(pos_dt3[1] - pos_ref[1]))

    assert err1 > err2 > err3

    # Convergence ratios e(dt/2) / e(dt) for a 2nd-order method are ~0.25
    ratio1 = err2 / err1
    ratio2 = err3 / err2

    # Ratios must be within [0.20, 0.30], confirming order of convergence ~ 2.0
    assert 0.20 <= ratio1 <= 0.30
    assert 0.20 <= ratio2 <= 0.30

    # Empirical order of accuracy p = log2(e_coarse / e_fine)
    order1 = np.log2(err1 / err2)
    order2 = np.log2(err2 / err3)

    assert order1 == pytest.approx(2.0, abs=0.25)
    assert order2 == pytest.approx(2.0, abs=0.25)


def test_velocity_verlet_convergence_eccentric():
    """Verify convergence on eccentric orbit (e=0.5)."""
    duration = 30.0  # 30 days

    fn = lambda: create_eccentric_two_body(a=1.0, e=0.5)
    pos_ref = _run_fixed_step(fn, duration, step_size=0.005)

    pos_dt1 = _run_fixed_step(fn, duration, step_size=0.4)
    pos_dt2 = _run_fixed_step(fn, duration, step_size=0.2)

    err1 = float(np.linalg.norm(pos_dt1[1] - pos_ref[1]))
    err2 = float(np.linalg.norm(pos_dt2[1] - pos_ref[1]))

    ratio = err2 / err1
    # For eccentric orbit over 30 days, error decreases by ~4x
    assert 0.20 <= ratio <= 0.32
