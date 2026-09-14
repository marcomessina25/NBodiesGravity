"""Validation tests evaluating the effect of gravitational softening parameter ε."""
import numpy as np
import pytest
from nbodiesgravity.engine.benchmarks import create_circular_two_body
from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.diagnostics import compute_potential_energy, ConservationTracker
from nbodiesgravity.engine.integrator import VelocityVerletIntegrator, SOFTENING
from nbodiesgravity.engine.system import SolarSystem, TimeStepConfig


def test_softening_effect_at_planetary_distance():
    """At 1 AU, softening of 1e-4 AU modifies potential and force by < 1e-7 relative."""
    m1, m2 = 1.989e30, 5.972e24
    masses = np.array([m1, m2])
    positions = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])

    u_zero = compute_potential_energy(positions, masses, softening=0.0)
    u_default = compute_potential_energy(positions, masses, softening=SOFTENING)          # 1e-4
    u_small = compute_potential_energy(positions, masses, softening=SOFTENING * 0.1)     # 1e-5
    u_large = compute_potential_energy(positions, masses, softening=SOFTENING * 10.0)    # 1e-3

    # Relative difference (1/sqrt(1 + eps²) - 1) ≈ -0.5 * eps²
    diff_default = abs(u_default - u_zero) / abs(u_zero)
    diff_small = abs(u_small - u_zero) / abs(u_zero)
    diff_large = abs(u_large - u_zero) / abs(u_zero)

    assert diff_small < 1e-9
    assert diff_default < 1e-7
    assert diff_large < 1e-5


def test_softening_regularizes_close_encounter_force():
    """Verify that softening caps acceleration during close encounter."""
    m1, m2 = 1e30, 1e30
    masses = np.array([m1, m2])
    # Very close bodies: separation 1e-5 AU
    positions = np.array([[0.0, 0.0, 0.0], [1e-5, 0.0, 0.0]])

    int_default = VelocityVerletIntegrator(softening=1e-4)
    int_small = VelocityVerletIntegrator(softening=1e-5)
    int_large = VelocityVerletIntegrator(softening=1e-3)

    acc_default = int_default._accelerations(positions, masses)
    acc_small = int_small._accelerations(positions, masses)
    acc_large = int_large._accelerations(positions, masses)

    a_def_norm = float(np.linalg.norm(acc_default[0]))
    a_sml_norm = float(np.linalg.norm(acc_small[0]))
    a_lrg_norm = float(np.linalg.norm(acc_large[0]))

    # Larger softening suppresses peak acceleration
    assert a_lrg_norm < a_def_norm < a_sml_norm
    # All computed accelerations remain completely finite
    assert np.isfinite(a_def_norm)
    assert np.isfinite(a_sml_norm)
    assert np.isfinite(a_lrg_norm)


def test_softening_parameter_orbit_stability():
    """Verify orbital stability under default, small, and large softening."""
    for eps in [1e-5, 1e-4, 1e-3]:
        system = create_circular_two_body(r=1.0, softening=eps)
        tracker = ConservationTracker(system.bodies, softening=eps)
        
        # Advance for 30 days
        for _ in range(30):
            system.step(1.0)
            
        report = tracker.evaluate(system.bodies)
        assert abs(report.energy_drift.rel_drift) < 1e-4
        assert report.normalized_momentum_drift < 1e-12
