"""Unit tests for analytical initial-condition presets and registry."""
from __future__ import annotations
import numpy as np
import pytest

from nbodiesgravity.engine.presets import (
    list_presets,
    get_preset,
    create_circular_two_body,
    create_eccentric_two_body,
    create_oriented_two_body,
    create_earth_moon_preset,
    create_binary_star_preset,
    create_restricted_three_body_preset,
    InitialConditionSet,
)
from nbodiesgravity.engine.diagnostics import compute_center_of_mass
from nbodiesgravity.engine.system import SolarSystem


def test_list_presets():
    presets = list_presets()
    assert "circular_two_body" in presets
    assert "eccentric_two_body" in presets
    assert "oriented_two_body" in presets
    assert "earth_moon" in presets
    assert "binary_star" in presets
    assert "restricted_three_body" in presets


def test_get_preset_unknown_raises():
    with pytest.raises(ValueError, match="Unknown preset 'invalid'"):
        get_preset("invalid")


def test_circular_two_body_preset():
    preset = get_preset("circular_two_body", r=1.5)
    assert len(preset.bodies) == 2
    sys = preset.create_system()
    assert isinstance(sys, SolarSystem)

    # Check barycenter is at origin
    masses = np.array([b.mass for b in preset.bodies])
    positions = np.array([b.pos for b in preset.bodies])
    com = compute_center_of_mass(positions, masses)
    np.testing.assert_allclose(com, [0.0, 0.0, 0.0], atol=1e-12)


def test_eccentric_two_body_preset():
    preset = get_preset("eccentric_two_body", a=2.0, e=0.6)
    assert len(preset.bodies) == 2
    # Verify separation is a*(1-e) = 0.8
    sep = np.linalg.norm(preset.bodies[1].pos - preset.bodies[0].pos)
    assert np.isclose(sep, 0.8, atol=1e-12)

    with pytest.raises(ValueError, match="Eccentricity"):
        create_eccentric_two_body(e=1.5)


def test_oriented_two_body_preset():
    preset = get_preset(
        "oriented_two_body",
        inc_deg=45.0,
        lan_deg=30.0,
        arg_pe_deg=15.0,
    )
    assert len(preset.bodies) == 2
    # Out of plane position should be non-zero
    assert abs(preset.bodies[1].pos[2]) > 1e-5


def test_earth_moon_preset():
    preset = get_preset("earth_moon")
    assert len(preset.bodies) == 2
    names = [b.name for b in preset.bodies]
    assert "Earth" in names
    assert "Moon" in names


def test_binary_star_preset():
    preset = get_preset("binary_star", separation=3.0)
    assert len(preset.bodies) == 2
    sep = np.linalg.norm(preset.bodies[0].pos - preset.bodies[1].pos)
    assert np.isclose(sep, 3.0, atol=1e-12)


def test_restricted_three_body_preset():
    preset_l4 = get_preset("restricted_three_body", lagrange_point="L4")
    assert len(preset_l4.bodies) == 3
    # L4 y coordinate should be positive
    assert preset_l4.bodies[2].pos[1] > 0.0

    preset_l5 = get_preset("restricted_three_body", lagrange_point="L5")
    assert preset_l5.bodies[2].pos[1] < 0.0


def test_preset_serialization_roundtrip():
    preset = get_preset("circular_two_body")
    d = preset.to_dict()
    restored = InitialConditionSet.from_dict(d)

    assert restored.name == preset.name
    assert len(restored.bodies) == len(preset.bodies)
    np.testing.assert_allclose(restored.bodies[0].pos, preset.bodies[0].pos)
    np.testing.assert_allclose(restored.bodies[1].vel, preset.bodies[1].vel)
