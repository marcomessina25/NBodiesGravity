"""Regression and verification tests for configurable gravitational constant G."""
from __future__ import annotations
from datetime import datetime
import numpy as np
import pytest

from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.integrator import (
    G_AU_DAY,
    VelocityVerletIntegrator,
    LeapfrogIntegrator,
    create_integrator,
    compute_accelerations,
)
from nbodiesgravity.engine.system import SolarSystem, TimeStepConfig, compute_adaptive_dt
from nbodiesgravity.engine.physics import PhysicsConfig
from nbodiesgravity.engine.presets import (
    get_preset,
    create_circular_two_body,
    create_eccentric_two_body,
    create_restricted_three_body_preset,
)
from nbodiesgravity.engine.checkpoints import SimulationCheckpoint
from nbodiesgravity.engine.experiments import ExperimentConfig, ExperimentMetadata


def test_custom_g_acceleration_scaling():
    """Verify that doubling G exactly doubles gravitational acceleration."""
    pos = np.array([[-0.5, 0.0, 0.0], [0.5, 0.0, 0.0]], dtype=float)
    masses = np.array([1e30, 1e30], dtype=float)

    # 1. Direct compute_accelerations
    acc_1x = compute_accelerations(pos, masses, g_constant=G_AU_DAY)
    acc_2x = compute_accelerations(pos, masses, g_constant=2.0 * G_AU_DAY)
    np.testing.assert_allclose(acc_2x, 2.0 * acc_1x, rtol=1e-14)

    # 2. VelocityVerletIntegrator
    vv_1x = VelocityVerletIntegrator(g_constant=G_AU_DAY)
    vv_2x = VelocityVerletIntegrator(g_constant=2.0 * G_AU_DAY)
    np.testing.assert_allclose(vv_2x._accelerations(pos, masses), 2.0 * vv_1x._accelerations(pos, masses), rtol=1e-14)

    # 3. LeapfrogIntegrator
    lf_1x = LeapfrogIntegrator(g_constant=G_AU_DAY)
    lf_2x = LeapfrogIntegrator(g_constant=2.0 * G_AU_DAY)
    np.testing.assert_allclose(lf_2x._accelerations(pos, masses), 2.0 * lf_1x._accelerations(pos, masses), rtol=1e-14)

    # 4. SolarSystem with PhysicsConfig
    b1_a = CelestialBody("B1", 1e30, pos[0].copy(), np.zeros(3), radius=1000.0, color=(1.0, 1.0, 1.0))
    b2_a = CelestialBody("B2", 1e30, pos[1].copy(), np.zeros(3), radius=1000.0, color=(1.0, 1.0, 1.0))
    sys_1x = SolarSystem([b1_a, b2_a], physics_config=PhysicsConfig(gravitational_constant=G_AU_DAY))

    b1_b = CelestialBody("B1", 1e30, pos[0].copy(), np.zeros(3), radius=1000.0, color=(1.0, 1.0, 1.0))
    b2_b = CelestialBody("B2", 1e30, pos[1].copy(), np.zeros(3), radius=1000.0, color=(1.0, 1.0, 1.0))
    sys_2x = SolarSystem([b1_b, b2_b], physics_config=PhysicsConfig(gravitational_constant=2.0 * G_AU_DAY))

    assert sys_1x.integrator.g_constant == G_AU_DAY
    assert sys_2x.integrator.g_constant == 2.0 * G_AU_DAY
    np.testing.assert_allclose(sys_2x.integrator._accelerations(pos, masses), 2.0 * sys_1x.integrator._accelerations(pos, masses), rtol=1e-14)


def test_custom_g_adaptive_dt_scaling():
    """Verify that multiplying G by 4 halves the orbital timescale and adaptive dt."""
    pos = np.array([[-0.5, 0.0, 0.0], [0.5, 0.0, 0.0]], dtype=float)
    masses = np.array([1e30, 1e30], dtype=float)
    t_cfg = TimeStepConfig(min_dt=1e-8, max_dt=100.0, safety_factor=0.01)

    # Direct compute_adaptive_dt
    dt_1x = compute_adaptive_dt(pos, masses, config=t_cfg, g_constant=G_AU_DAY)
    dt_4x = compute_adaptive_dt(pos, masses, config=t_cfg, g_constant=4.0 * G_AU_DAY)

    # T ~ 1 / sqrt(G), so 4x G -> 0.5x dt
    np.testing.assert_allclose(dt_4x, 0.5 * dt_1x, rtol=1e-12)

    # Through SolarSystem.step
    b1_a = CelestialBody("B1", 1e30, pos[0].copy(), np.zeros(3), radius=1000.0, color=(1.0, 1.0, 1.0))
    b2_a = CelestialBody("B2", 1e30, pos[1].copy(), np.zeros(3), radius=1000.0, color=(1.0, 1.0, 1.0))
    sys_1x = SolarSystem([b1_a, b2_a], timestep_config=t_cfg, physics_config=PhysicsConfig(gravitational_constant=G_AU_DAY))

    b1_b = CelestialBody("B1", 1e30, pos[0].copy(), np.zeros(3), radius=1000.0, color=(1.0, 1.0, 1.0))
    b2_b = CelestialBody("B2", 1e30, pos[1].copy(), np.zeros(3), radius=1000.0, color=(1.0, 1.0, 1.0))
    sys_4x = SolarSystem([b1_b, b2_b], timestep_config=t_cfg, physics_config=PhysicsConfig(gravitational_constant=4.0 * G_AU_DAY))

    sys_1x.step(0.01)
    sys_4x.step(0.01)

    np.testing.assert_allclose(sys_4x.last_adaptive_dt, 0.5 * sys_1x.last_adaptive_dt, rtol=1e-12)


def test_custom_g_trajectory_divergence():
    """Verify that systems with different G evolve along physically different trajectories."""
    b1_a = CelestialBody("Primary", 1e30, np.array([0.0, 0.0, 0.0]), np.array([0.0, -0.005, 0.0]), radius=50000.0, color=(1.0, 1.0, 0.0))
    b2_a = CelestialBody("Secondary", 1e24, np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.015, 0.0]), radius=5000.0, color=(0.0, 0.5, 1.0))
    sys_1x = SolarSystem([b1_a, b2_a], physics_config=PhysicsConfig(gravitational_constant=G_AU_DAY))

    b1_b = CelestialBody("Primary", 1e30, np.array([0.0, 0.0, 0.0]), np.array([0.0, -0.005, 0.0]), radius=50000.0, color=(1.0, 1.0, 0.0))
    b2_b = CelestialBody("Secondary", 1e24, np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.015, 0.0]), radius=5000.0, color=(0.0, 0.5, 1.0))
    sys_2x = SolarSystem([b1_b, b2_b], physics_config=PhysicsConfig(gravitational_constant=2.0 * G_AU_DAY))

    sys_1x.advance(20.0)
    sys_2x.advance(20.0)

    # Trajectories must clearly diverge under differing G
    pos_diff = np.linalg.norm(sys_1x.bodies[1].pos - sys_2x.bodies[1].pos)
    assert pos_diff > 1e-2


def test_custom_g_presets():
    """Verify that analytical presets generate orbital velocities matching configured G."""
    pc_1x = PhysicsConfig(gravitational_constant=G_AU_DAY)
    pc_4x = PhysicsConfig(gravitational_constant=4.0 * G_AU_DAY)

    # Circular two-body: v = sqrt(G * M / r) -> 4x G gives 2x orbital velocity
    p_1x = create_circular_two_body(r=1.0, physics_config=pc_1x)
    p_4x = create_circular_two_body(r=1.0, physics_config=pc_4x)

    v1_1x = np.linalg.norm(p_1x.bodies[0].vel)
    v1_4x = np.linalg.norm(p_4x.bodies[0].vel)
    np.testing.assert_allclose(v1_4x, 2.0 * v1_1x, rtol=1e-12)

    v2_1x = np.linalg.norm(p_1x.bodies[1].vel)
    v2_4x = np.linalg.norm(p_4x.bodies[1].vel)
    np.testing.assert_allclose(v2_4x, 2.0 * v2_1x, rtol=1e-12)

    # System instantiated from preset carries the custom G
    sys = p_4x.create_system()
    assert sys.physics_config.gravitational_constant == 4.0 * G_AU_DAY
    assert sys.integrator.g_constant == 4.0 * G_AU_DAY

    # Eccentric two-body with custom G
    ecc_4x = create_eccentric_two_body(physics_config=pc_4x)
    assert ecc_4x.physics_config.gravitational_constant == 4.0 * G_AU_DAY

    # Restricted three body with custom G
    r3b_4x = create_restricted_three_body_preset(physics_config=pc_4x)
    assert r3b_4x.physics_config.gravitational_constant == 4.0 * G_AU_DAY


def test_custom_g_checkpoint_and_replay_roundtrip():
    """Verify that custom G survives checkpoint serialization and resume, matching exact evolution."""
    pc = PhysicsConfig(gravitational_constant=2.5 * G_AU_DAY)
    preset = create_circular_two_body(physics_config=pc)
    sys = preset.create_system()

    # Step for 10 days
    sys.advance(10.0)

    # Save checkpoint
    chk = SimulationCheckpoint.create(sys, datetime(2000, 1, 1), elapsed_days=10.0)
    chk_dict = chk.to_dict()
    assert chk_dict["physics_config"]["gravitational_constant"] == 2.5 * G_AU_DAY

    # Restore checkpoint
    restored_chk = SimulationCheckpoint.from_dict(chk_dict)
    restored_sys, _, elapsed_days, _ = restored_chk.restore()

    assert elapsed_days == 10.0
    assert restored_sys.physics_config.gravitational_constant == 2.5 * G_AU_DAY
    assert restored_sys.integrator.g_constant == 2.5 * G_AU_DAY

    # Advance both for another 10 days
    sys.advance(10.0)
    restored_sys.advance(10.0)

    for b_orig, b_rest in zip(sys.bodies, restored_sys.bodies):
        np.testing.assert_allclose(b_orig.pos, b_rest.pos, rtol=1e-14, atol=1e-15)
        np.testing.assert_allclose(b_orig.vel, b_rest.vel, rtol=1e-14, atol=1e-15)


def test_custom_g_experiment_replay():
    """Verify that ExperimentConfig deterministic replay executes with custom G."""
    pc = PhysicsConfig(gravitational_constant=1.5 * G_AU_DAY)
    ic = create_circular_two_body(physics_config=pc)
    exp = ExperimentConfig(
        metadata=ExperimentMetadata(experiment_id="custom_g_test", name="Custom G Replay", description=""),
        initial_conditions=ic,
        target_duration=5.0,
    )
    result = exp.run_replay()
    assert len(result["final_bodies"]) == 2
    assert result["cumulative_substeps"] > 0
    assert np.isfinite(result["energy_rel_drift"])
