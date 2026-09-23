"""Cross-integrator scientific validation: Velocity Verlet vs Leapfrog."""
from __future__ import annotations
import numpy as np

from nbodiesgravity.engine.integrator import (
    VelocityVerletIntegrator,
    LeapfrogIntegrator,
    G_AU_DAY,
    IntegratorConfig,
)
from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.system import SolarSystem
from nbodiesgravity.engine.diagnostics import compute_total_energy


def _setup_circular_two_body() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Sun-Earth circular two-body system."""
    m1 = 1.98847e30
    m2 = 5.9722e24
    r = 1.0  # AU
    # Circular orbital speed: v = sqrt(G * (m1 + m2) / r)
    v_circ = float(np.sqrt(G_AU_DAY * (m1 + m2) / r))
    # Barycentric coordinates
    mu1 = m2 / (m1 + m2)
    mu2 = m1 / (m1 + m2)
    pos = np.array([[-mu1 * r, 0.0, 0.0], [mu2 * r, 0.0, 0.0]], dtype=float)
    vel = np.array([[0.0, -mu1 * v_circ, 0.0], [0.0, mu2 * v_circ, 0.0]], dtype=float)
    masses = np.array([m1, m2], dtype=float)
    return pos, vel, masses


def test_verlet_vs_leapfrog_identical_trajectory_fixed_dt():
    """Verify Velocity Verlet and synchronous Kick-Drift-Kick Leapfrog produce identical paths."""
    pos_vv, vel_vv, masses = _setup_circular_two_body()
    pos_lf, vel_lf, _ = _setup_circular_two_body()

    itg_vv = VelocityVerletIntegrator()
    itg_lf = LeapfrogIntegrator()

    dt = 0.05   # days
    n_steps = 200

    for _ in range(n_steps):
        pos_vv, vel_vv = itg_vv.step(pos_vv, vel_vv, masses, dt)
        pos_lf, vel_lf = itg_lf.step(pos_lf, vel_lf, masses, dt)

    np.testing.assert_allclose(pos_vv, pos_lf, atol=1e-14, rtol=1e-14)
    np.testing.assert_allclose(vel_vv, vel_lf, atol=1e-14, rtol=1e-14)


def test_leapfrog_energy_conservation_circular_orbit():
    """Verify Leapfrog conserves energy over 1 full orbit (365 days) within 0.01%."""
    pos, vel, masses = _setup_circular_two_body()
    itg = LeapfrogIntegrator()

    e0 = compute_total_energy(pos, vel, masses, softening=itg.softening)

    dt = 0.1   # ~3652 steps for 1 year
    n_steps = int(365.25 / dt)

    for _ in range(n_steps):
        pos, vel = itg.step(pos, vel, masses, dt)

    e_final = compute_total_energy(pos, vel, masses, softening=itg.softening)
    rel_drift = abs(e_final - e0) / abs(e0)
    assert rel_drift < 1e-4, f"Leapfrog energy drift {rel_drift:.2e} exceeded 1e-4"


def test_leapfrog_fixed_step_convergence():
    """Verify Leapfrog exhibits second-order O(dt²) convergence."""
    pos0, vel0, masses = _setup_circular_two_body()
    itg = LeapfrogIntegrator()

    duration = 50.0   # days

    # Reference high-resolution trajectory: dt = 0.01
    dt_ref = 0.01
    p_ref, v_ref = pos0.copy(), vel0.copy()
    for _ in range(int(duration / dt_ref)):
        p_ref, v_ref = itg.step(p_ref, v_ref, masses, dt_ref)

    # Test dt values: 1.0, 0.5, 0.25
    errors = []
    dts = [1.0, 0.5, 0.25]
    for dt in dts:
        p, v = pos0.copy(), vel0.copy()
        for _ in range(int(duration / dt)):
            p, v = itg.step(p, v, masses, dt)
        err = float(np.linalg.norm(p[1] - p_ref[1]))
        errors.append(err)

    assert errors[0] > errors[1] > errors[2]
    # Ratio of errors e(dt/2) / e(dt) should be approx 0.25 for second-order
    ratio_1 = errors[1] / errors[0]
    ratio_2 = errors[2] / errors[1]
    assert 0.20 <= ratio_1 <= 0.30, f"Expected ratio in [0.20, 0.30], got {ratio_1:.3f}"
    assert 0.20 <= ratio_2 <= 0.30, f"Expected ratio in [0.20, 0.30], got {ratio_2:.3f}"


def test_leapfrog_in_solarsystem_integration():
    """Verify SolarSystem functions seamlessly with Leapfrog integrator."""
    pos, vel, masses = _setup_circular_two_body()
    bodies = [
        CelestialBody("Star", masses[0], pos[0], vel[0], 696340.0, (255, 255, 0), label="star"),
        CelestialBody("Planet", masses[1], pos[1], vel[1], 6371.0, (0, 0, 255), label="planet"),
    ]
    sys = SolarSystem(bodies, integrator_config=IntegratorConfig("leapfrog"))
    assert sys.integrator.name == "leapfrog"

    # Step forward 10 days
    sys.step(10.0)
    assert sys.cumulative_substeps > 0
    assert np.all(np.isfinite(sys.bodies[1].pos))
