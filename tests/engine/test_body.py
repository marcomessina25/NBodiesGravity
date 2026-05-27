import numpy as np
from nbodiesgravity.engine.body import BodyState, CelestialBody


def test_body_state_copies_arrays():
    pos = np.array([1.0, 2.0, 3.0])
    vel = np.array([0.1, 0.2, 0.3])
    state = BodyState(name="Earth", pos=pos.copy(), vel=vel.copy())
    pos[0] = 999.0
    assert state.pos[0] == 1.0  # must not reflect mutation of original


def test_body_state_fields():
    state = BodyState(name="Mars", pos=np.zeros(3), vel=np.ones(3))
    assert state.name == "Mars"
    assert state.pos.shape == (3,)
    assert state.vel.shape == (3,)


def test_celestial_body_snapshot_is_copy():
    body = CelestialBody(
        name="Earth", mass=5.972e24,
        pos=np.array([1.0, 0.0, 0.0]),
        vel=np.array([0.0, 0.01720, 0.0]),
        radius=6371.0, color=(0.2, 0.5, 1.0),
    )
    snap = body.snapshot()
    assert snap.name == "Earth"
    assert np.allclose(snap.pos, [1.0, 0.0, 0.0])
    body.pos[0] = 99.0       # mutate the body
    assert snap.pos[0] == 1.0  # snapshot pos must not change
    body.vel[0] = 99.0       # mutate velocity
    assert snap.vel[0] == 0.0  # snapshot vel must also be isolated


def test_celestial_body_show_trail_default():
    body = CelestialBody(
        name="Test", mass=1e20, pos=np.zeros(3), vel=np.zeros(3),
        radius=100.0, color=(1.0, 1.0, 1.0),
    )
    assert body.show_trail is True
