import numpy as np
import pytest
from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.system import SolarSystem
from nbodiesgravity.engine.simulation_thread import SimulationThread


def _one_body_system() -> SolarSystem:
    body = CelestialBody(
        name="Earth", mass=5.972e24,
        pos=np.array([1.0, 0.0, 0.0]),
        vel=np.array([0.0, 0.01720, 0.0]),
        radius=6371.0, color=(0.2, 0.5, 1.0),
    )
    return SolarSystem([body])


def test_elapsed_days_zero_on_construction(qapp):
    thread = SimulationThread(_one_body_system())
    assert thread.elapsed_days == 0.0


def test_elapsed_days_property_reflects_internal_state(qapp):
    thread = SimulationThread(_one_body_system())
    thread._elapsed_days = 42.5
    assert thread.elapsed_days == 42.5
