import numpy as np
from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.system import SolarSystem


def _sun():
    return CelestialBody(
        name="Sun", mass=1.989e30, pos=np.zeros(3), vel=np.zeros(3),
        radius=695700, color=(1.0, 0.9, 0.2),
    )

def _earth():
    return CelestialBody(
        name="Earth", mass=5.972e24,
        pos=np.array([1.0, 0.0, 0.0]),
        vel=np.array([0.0, 0.017202, 0.0]),
        radius=6371, color=(0.2, 0.5, 1.0),
    )


def test_step_moves_earth():
    system = SolarSystem([_sun(), _earth()])
    initial = system.bodies[1].pos.copy()
    system.step(1.0)
    assert not np.allclose(system.bodies[1].pos, initial)


def test_snapshot_is_independent_copy():
    system = SolarSystem([_earth()])
    snap = system.snapshot()
    snap[0].pos[0] = 999.0           # mutate snapshot
    assert system.bodies[0].pos[0] == 1.0  # original unchanged


def test_snapshot_names_match_body_order():
    system = SolarSystem([_sun(), _earth()])
    snap = system.snapshot()
    assert [s.name for s in snap] == ["Sun", "Earth"]


def test_add_remove_body():
    system = SolarSystem([_sun()])
    system.add_body(_earth())
    assert len(system.bodies) == 2
    system.remove_body("Earth")
    assert len(system.bodies) == 1
    assert system.bodies[0].name == "Sun"


def test_remove_nonexistent_is_noop():
    system = SolarSystem([_sun()])
    system.remove_body("Ghost")
    assert len(system.bodies) == 1


def test_get_body_found_and_not_found():
    system = SolarSystem([_sun(), _earth()])
    assert system.get_body("Earth") is not None
    assert system.get_body("Mars") is None


def test_empty_system_step_does_not_raise():
    system = SolarSystem([])
    system.step(1.0)  # must not raise


def test_inactive_body_not_integrated():
    sun = _sun()
    earth = _earth()
    earth.active = False
    frozen_pos = earth.pos.copy()   # save BEFORE step
    frozen_vel = earth.vel.copy()

    system = SolarSystem([sun, earth])
    system.step(1.0)

    # Earth is inactive — its position and velocity must not change at all
    assert np.allclose(system.bodies[1].pos, frozen_pos)
    assert np.allclose(system.bodies[1].vel, frozen_vel)


def test_all_inactive_step_is_noop():
    sun = _sun()
    earth = _earth()
    sun.active = False
    earth.active = False
    frozen_sun_pos   = sun.pos.copy()
    frozen_sun_vel   = sun.vel.copy()
    frozen_earth_pos = earth.pos.copy()
    frozen_earth_vel = earth.vel.copy()

    system = SolarSystem([sun, earth])
    system.step(1.0)   # must not raise

    assert np.allclose(system.bodies[0].pos, frozen_sun_pos)
    assert np.allclose(system.bodies[0].vel, frozen_sun_vel)
    assert np.allclose(system.bodies[1].pos, frozen_earth_pos)
    assert np.allclose(system.bodies[1].vel, frozen_earth_vel)


def test_reactivate_body_resumes_integration():
    sun = _sun()
    earth = _earth()
    earth.active = False

    system = SolarSystem([sun, earth])
    for _ in range(5):
        system.step(1.0)

    frozen_pos = system.bodies[1].pos.copy()   # save BEFORE reactivation

    # Reactivate — Sun has drifted negligibly (~1e-7 AU) from Earth's pull over 5 steps.
    # Gravity from Sun will pull Earth; one step is sufficient to detect movement.
    system.bodies[1].active = True
    system.step(1.0)

    assert not np.allclose(system.bodies[1].pos, frozen_pos)
