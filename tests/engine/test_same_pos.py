import numpy as np
from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.system import SolarSystem


def test_same_position_no_infinite_loop():
    """Verify that having two active bodies at the exact same position does not cause an infinite loop in step()."""
    sun1 = CelestialBody("Sun1", 1.989e30, np.zeros(3), np.zeros(3), 695700, (1.0, 0.9, 0.2))
    sun2 = CelestialBody("Sun2", 1.989e30, np.zeros(3), np.zeros(3), 695700, (1.0, 0.9, 0.2))
    system = SolarSystem([sun1, sun2])

    # Try to step the system. This will complete immediately instead of hanging.
    system.step(0.1)
