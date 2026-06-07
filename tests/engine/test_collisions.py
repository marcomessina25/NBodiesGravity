import pytest
import numpy as np
from nbodiesgravity.engine.body import CollisionEvent, CelestialBody
from nbodiesgravity.engine.system import SolarSystem, KM_PER_AU


def test_collision_event_fields():
    ev = CollisionEvent(absorbed="Moon", survivor="Earth")
    assert ev.absorbed == "Moon"
    assert ev.survivor == "Earth"
    # NamedTuple => positional + immutable
    assert tuple(ev) == ("Moon", "Earth")


def _big(name, mass, pos, vel=(0.0, 0.0, 0.0), radius=695700.0):
    return CelestialBody(name=name, mass=mass, pos=np.array(pos, dtype=float),
                         vel=np.array(vel, dtype=float), radius=radius,
                         color=(1.0, 1.0, 1.0))


def test_overlapping_pair_merges_into_larger_mass():
    # Centres 1e-4 AU apart; A radius alone = 695700/KM_PER_AU ~= 4.65e-3 AU > 1e-4 => overlap.
    a = _big("A", 2.0e30, [0.0, 0.0, 0.0], vel=[0.0, 0.0, 0.0], radius=695700.0)
    b = _big("B", 1.0e24, [1e-4, 0.0, 0.0], vel=[0.1, 0.0, 0.0], radius=6371.0)
    system = SolarSystem([a, b])

    events = system._resolve_collisions()

    assert len(events) == 1
    assert events[0].absorbed == "B"
    assert events[0].survivor == "A"
    assert len(system.bodies) == 1
    assert system.bodies[0].name == "A"


def test_merge_conserves_momentum_and_mass():
    a = _big("A", 2.0e30, [0.0, 0.0, 0.0], vel=[0.0, 0.0, 0.0], radius=695700.0)
    b = _big("B", 1.0e24, [1e-4, 0.0, 0.0], vel=[0.4, 0.0, 0.0], radius=6371.0)
    p_before = a.mass * a.vel + b.mass * b.vel
    m_before = a.mass + b.mass

    system = SolarSystem([a, b])
    system._resolve_collisions()

    survivor = system.bodies[0]
    assert survivor.mass == pytest.approx(m_before)
    np.testing.assert_allclose(survivor.mass * survivor.vel, p_before, rtol=1e-12)


def test_merge_grows_radius_by_equal_density_volume():
    a = _big("A", 2.0e30, [0.0, 0.0, 0.0], radius=695700.0)
    b = _big("B", 1.0e24, [1e-4, 0.0, 0.0], radius=6371.0)
    expected = (695700.0 ** 3 + 6371.0 ** 3) ** (1.0 / 3.0)

    system = SolarSystem([a, b])
    system._resolve_collisions()

    assert system.bodies[0].radius == pytest.approx(expected)


def test_non_overlapping_pair_untouched():
    a = _big("A", 2.0e30, [0.0, 0.0, 0.0], radius=695700.0)   # radius ~4.65e-3 AU
    b = _big("B", 1.0e24, [1.0, 0.0, 0.0], radius=6371.0)     # 1 AU away
    system = SolarSystem([a, b])

    events = system._resolve_collisions()

    assert events == []
    assert len(system.bodies) == 2


def test_chained_three_body_merge_in_one_call():
    # All three within the Sun-sized radius of A => chain to a single survivor.
    a = _big("A", 3.0e30, [0.0, 0.0, 0.0], radius=695700.0)
    b = _big("B", 2.0e30, [1e-4, 0.0, 0.0], radius=695700.0)
    c = _big("C", 1.0e30, [2e-4, 0.0, 0.0], radius=695700.0)
    system = SolarSystem([a, b, c])

    events = system._resolve_collisions()

    assert len(events) == 2
    assert len(system.bodies) == 1
    assert system.bodies[0].name == "A"
    assert system.bodies[0].mass == pytest.approx(6.0e30)


def test_inactive_bodies_excluded_from_collision():
    a = _big("A", 2.0e30, [0.0, 0.0, 0.0], radius=695700.0)
    b = _big("B", 1.0e24, [1e-4, 0.0, 0.0], radius=6371.0)
    b.active = False
    system = SolarSystem([a, b])

    events = system._resolve_collisions()

    assert events == []
    assert len(system.bodies) == 2


def test_step_returns_collision_events():
    a = _big("A", 2.0e30, [0.0, 0.0, 0.0], radius=695700.0)
    b = _big("B", 1.0e24, [1e-4, 0.0, 0.0], radius=6371.0)
    system = SolarSystem([a, b])

    events = system.step(0.001)

    assert isinstance(events, list)
    assert len(events) == 1
    assert events[0].absorbed == "B"


def test_step_returns_empty_list_when_no_collision():
    a = _big("A", 2.0e30, [0.0, 0.0, 0.0], radius=695700.0)
    b = _big("B", 1.0e24, [1.0, 0.0, 0.0], radius=6371.0)
    system = SolarSystem([a, b])

    assert system.step(0.001) == []
