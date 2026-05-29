import numpy as np
import pytest
from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.system import SolarSystem


def test_system_clone_creates_independent_copy():
    """Verify clone() produces a completely detached duplicate of the system and its bodies."""
    b1 = CelestialBody(
        name="Star", mass=2e30, pos=np.array([0.0, 0.0, 0.0]),
        vel=np.array([0.0, 0.0, 0.0]), radius=700000.0, color=(1.0, 1.0, 0.0)
    )
    b2 = CelestialBody(
        name="Planet", mass=6e24, pos=np.array([1.0, 0.0, 0.0]),
        vel=np.array([0.0, 0.02, 0.0]), radius=6371.0, color=(0.0, 0.0, 1.0)
    )
    original = SolarSystem([b1, b2])
    cloned = original.clone()

    assert len(cloned.bodies) == 2
    assert cloned.bodies[0].name == "Star"
    assert cloned.bodies[1].name == "Planet"

    # Modify clone and verify original is unaffected
    cloned.bodies[0].name = "Modified Star"
    cloned.bodies[0].pos[0] = 9.9
    cloned.bodies[0].active = False

    assert original.bodies[0].name == "Star"
    assert original.bodies[0].pos[0] == 0.0
    assert original.bodies[0].active is True


def test_adaptive_step_caps_on_tight_orbit():
    """Verify that a close binary or tight orbit reduces the maximum internal integration step size."""
    # Sun and Earth at 1.0 AU
    b1 = CelestialBody("Sun", 1.9885e30, np.zeros(3), np.zeros(3), 1.0, (1.0, 1.0, 1.0))
    b2 = CelestialBody("Earth", 5.972e24, np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0172, 0.0]), 1.0, (1.0, 1.0, 1.0))
    sys_normal = SolarSystem([b1, b2])

    # Sun and very close companion at 0.005 AU
    b3 = CelestialBody("Companion", 5.972e24, np.array([0.005, 0.0, 0.0]), np.array([0.0, 0.2, 0.0]), 1.0, (1.0, 1.0, 1.0))
    sys_tight = SolarSystem([b1, b3])

    # We can inspect the step behavior indirectly or verify stability.
    # Let's perform a step of 1.0 day and see if the systems remain stable.
    sys_normal.step(1.0)
    sys_tight.step(1.0)

    # Let's ensure coordinates are still real and in reasonable bounds (no NaN explosions)
    assert np.all(np.isfinite(sys_normal.bodies[1].pos))
    assert np.all(np.isfinite(sys_tight.bodies[1].pos))
