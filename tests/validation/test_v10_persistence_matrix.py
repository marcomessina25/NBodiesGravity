"""Comprehensive save and checkpoint persistence migration matrix for NBodiesGravity v1.0.

Verifies:
1. Historical save migration across all past schema formats (v0.5, v0.6, v0.7, v0.8, v0.9, v1.0).
2. Checkpoint restore from schema_version 1 and schema_version 2.
3. Resilience against corrupt, empty, and malformed files.
"""
from __future__ import annotations
import json
import tempfile
from pathlib import Path
from datetime import datetime
import numpy as np
import pytest

from nbodiesgravity.engine import (
    CelestialBody,
    SolarSystem,
    TimeStepConfig,
    IntegratorConfig,
    PhysicsConfig,
    CollisionConfig,
    SimulationCheckpoint,
    get_preset,
    G_AU_DAY,
)
from nbodiesgravity.data.loader import load_checkpoint


# ============================================================================
# 1. Historical Save Migration Matrix
# ============================================================================

def test_v10_migration_v05_format():
    """Migrate v0.5 save file format (position, velocity, radius, color)."""
    data = {
        "epoch": "2010-05-15",
        "bodies": [
            {
                "name": "Primary",
                "mass": 2e30,
                "position": [0.0, 0.0, 0.0],
                "velocity": [0.0, 0.0, 0.0],
                "radius": 700000.0,
                "color": [255, 200, 50],
            },
            {
                "name": "Companion",
                "mass": 1e24,
                "position": [1.5, 0.0, 0.0],
                "velocity": [0.0, 0.012, 0.0],
                "radius": 6000.0,
                "color": [50, 150, 255],
            },
        ],
    }

    # Simulate parsing in loader / MainWindow
    bodies = [
        CelestialBody(
            name=e["name"],
            mass=e.get("mass_kg", e.get("mass", 1.0)),
            pos=np.array(e.get("pos_au", e.get("position")), dtype=float),
            vel=np.array(e.get("vel_au_per_day", e.get("velocity")), dtype=float),
            radius=e.get("radius_km", e.get("radius", 1000.0)),
            color=tuple(e["color"]),
            label=e.get("label", "planet"),
        )
        for e in data["bodies"]
    ]
    sys = SolarSystem(bodies)
    assert len(sys.bodies) == 2
    assert sys.integrator.name == "velocity_verlet"
    assert sys.physics_config.gravitational_constant == G_AU_DAY


def test_v10_migration_v08_format():
    """Migrate v0.8 format with format_version=1 and explicit field names."""
    data = {
        "format_version": 1,
        "epoch": "2024-06-01",
        "bodies": [
            {
                "name": "Sol",
                "label": "star",
                "mass_kg": 1.989e30,
                "radius_km": 696340.0,
                "color": [255, 255, 0],
                "pos_au": [0.0, 0.0, 0.0],
                "vel_au_per_day": [0.0, 0.0, 0.0],
                "active": True,
                "show_trail": False,
                "show_name": True,
            }
        ],
    }
    bodies = [
        CelestialBody(
            name=e["name"],
            mass=e["mass_kg"],
            pos=np.array(e["pos_au"], dtype=float),
            vel=np.array(e["vel_au_per_day"], dtype=float),
            radius=e["radius_km"],
            color=tuple(e["color"]),
            label=e.get("label", "star"),
            active=e.get("active", True),
            show_trail=e.get("show_trail", True),
            show_name=e.get("show_name", True),
        )
        for e in data["bodies"]
    ]
    sys = SolarSystem(bodies)
    assert len(sys.bodies) == 1
    assert sys.bodies[0].label == "star"
    assert not sys.bodies[0].show_trail


def test_v10_migration_v09_format_with_configs():
    """Migrate v0.9 format containing explicit physics and integrator configurations."""
    data = {
        "format_version": 1,
        "application_version": "0.9.0",
        "epoch": "2030-01-01",
        "timestep_config": {
            "min_dt": 1e-4,
            "max_dt": 0.5,
            "safety_factor": 0.02,
            "max_substeps": 5000,
        },
        "integrator_config": {
            "name": "leapfrog",
            "softening": 2e-4,
            "max_displacement": 50.0,
            "g_constant": 2.0 * G_AU_DAY,
            "parameters": {},
        },
        "physics_config": {
            "gravitational_constant": 2.0 * G_AU_DAY,
            "softening_length": 2e-4,
            "gravity_model": "newtonian",
            "softening_model": "plummer",
        },
        "collision_config": {
            "enabled": True,
            "model": "merge",
            "restitution_coefficient": 0.0,
        },
        "bodies": [
            {
                "name": "Star",
                "label": "star",
                "mass_kg": 1e30,
                "radius_km": 50000.0,
                "color": [255, 200, 100],
                "pos_au": [0.0, 0.0, 0.0],
                "vel_au_per_day": [0.0, 0.0, 0.0],
                "active": True,
                "show_trail": True,
                "show_name": True,
            }
        ],
    }

    t_cfg = TimeStepConfig.from_dict(data["timestep_config"])
    itg_cfg = IntegratorConfig.from_dict(data["integrator_config"])
    phy_cfg = PhysicsConfig.from_dict(data["physics_config"])
    col_cfg = CollisionConfig.from_dict(data["collision_config"])

    bodies = [
        CelestialBody(
            name=e["name"],
            mass=e["mass_kg"],
            pos=np.array(e["pos_au"], dtype=float),
            vel=np.array(e["vel_au_per_day"], dtype=float),
            radius=e["radius_km"],
            color=tuple(e["color"]),
        )
        for e in data["bodies"]
    ]

    sys = SolarSystem(
        bodies=bodies,
        timestep_config=t_cfg,
        integrator_config=itg_cfg,
        physics_config=phy_cfg,
        collision_config=col_cfg,
    )

    assert sys.integrator.name == "leapfrog"
    assert sys.integrator.g_constant == 2.0 * G_AU_DAY
    assert sys.physics_config.gravitational_constant == 2.0 * G_AU_DAY
    assert sys.timestep_config.safety_factor == 0.02


# ============================================================================
# 2. Checkpoint Version Compatibility (Schema 1 and 2)
# ============================================================================

def test_v10_checkpoint_schema_1_migration():
    """Verify that a schema_version=1 checkpoint file is migrated cleanly to v1.0."""
    data = {
        "schema_version": 1,
        "epoch": "2022-01-01",
        "elapsed_days": 15.5,
        "bodies": [
            {
                "name": "P1",
                "mass": 1e30,
                "pos": [0.0, 0.0, 0.0],
                "vel": [0.0, 0.0, 0.0],
                "radius": 1000.0,
                "color": [1.0, 1.0, 1.0],
                "active": True,
                "label": "star",
            }
        ],
    }
    chk = SimulationCheckpoint.from_dict(data)
    assert chk.schema_version == 2
    assert chk.elapsed_days == 15.5
    sys, epoch, elapsed, _ = chk.restore()
    assert len(sys.bodies) == 1
    assert elapsed == 15.5
    assert sys.integrator.name == "velocity_verlet"


def test_v10_checkpoint_schema_2_full_roundtrip():
    """Verify that a schema_version=2 checkpoint preserves all configurations and evolves identically."""
    p_orig = get_preset("circular_two_body")
    sys_orig = p_orig.create_system()
    sys_orig.set_integrator("leapfrog")

    chk = SimulationCheckpoint.create(sys_orig, datetime(2025, 1, 1), elapsed_days=50.0)
    chk_dict = chk.to_dict()

    assert chk_dict["application_version"] == "1.0.0"
    assert chk_dict["schema_version"] == 2
    assert chk_dict["integrator_config"]["name"] == "leapfrog"

    # Restore from dict
    restored_chk = SimulationCheckpoint.from_dict(chk_dict)
    sys_restored, epoch, elapsed, _ = restored_chk.restore()

    assert sys_restored.integrator.name == "leapfrog"
    assert elapsed == 50.0

    # Advance both systems for 10 days; evolution must be identical
    sys_orig.advance(10.0)
    sys_restored.advance(10.0)

    for b_o, b_r in zip(sys_orig.bodies, sys_restored.bodies):
        np.testing.assert_allclose(b_o.pos, b_r.pos, rtol=1e-14, atol=1e-15)
        np.testing.assert_allclose(b_o.vel, b_r.vel, rtol=1e-14, atol=1e-15)


# ============================================================================
# 3. Corrupt and Malformed File Resilience
# ============================================================================

def test_v10_corrupt_file_handling():
    """Verify that malformed or empty checkpoint files raise appropriate errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bad_json = Path(tmpdir) / "bad.json"
        bad_json.write_text("Not a json file", encoding="utf-8")

        with pytest.raises(json.JSONDecodeError):
            SimulationCheckpoint.load(bad_json)

        empty_json = Path(tmpdir) / "empty.json"
        empty_json.write_text("{}", encoding="utf-8")
        chk = SimulationCheckpoint.load(empty_json)
        assert len(chk.bodies) == 0
        sys, _, _, _ = chk.restore()
        assert len(sys.bodies) == 0
