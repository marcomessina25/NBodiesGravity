"""Unit tests for integrator factory and IntegratorConfig serialization."""
from __future__ import annotations
import pytest

from nbodiesgravity.engine.integrator import (
    IntegratorConfig,
    VelocityVerletIntegrator,
    LeapfrogIntegrator,
    create_integrator,
    INTEGRATOR_REGISTRY,
)


def test_create_integrator_by_string():
    vv = create_integrator("velocity_verlet")
    assert isinstance(vv, VelocityVerletIntegrator)
    assert vv.name == "velocity_verlet"

    lf = create_integrator("leapfrog")
    assert isinstance(lf, LeapfrogIntegrator)
    assert lf.name == "leapfrog"

    # Case insensitive
    lf_upper = create_integrator("  LEAPFROG  ")
    assert isinstance(lf_upper, LeapfrogIntegrator)


def test_create_integrator_with_overrides():
    vv = create_integrator("velocity_verlet", softening=5e-4, max_displacement=20.0)
    assert vv.softening == 5e-4
    assert vv.max_displacement == 20.0


def test_create_integrator_by_config():
    cfg = IntegratorConfig(name="leapfrog", softening=3e-4, max_displacement=40.0)
    itg = create_integrator(cfg)
    assert isinstance(itg, LeapfrogIntegrator)
    assert itg.softening == 3e-4
    assert itg.max_displacement == 40.0


def test_create_integrator_unknown_raises():
    with pytest.raises(ValueError, match="Unknown integrator 'rk4'"):
        create_integrator("rk4")


def test_create_integrator_invalid_type():
    with pytest.raises(TypeError, match="Expected IntegratorConfig or str"):
        create_integrator(12345)  # type: ignore


def test_integrator_config_serialization():
    cfg = IntegratorConfig(name="leapfrog", softening=2.5e-4, max_displacement=50.0)
    d = cfg.to_dict()
    assert d["name"] == "leapfrog"
    assert d["softening"] == 2.5e-4
    assert d["max_displacement"] == 50.0

    restored = IntegratorConfig.from_dict(d)
    assert restored == cfg
