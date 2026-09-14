"""Tests for substep accounting and DiagnosticsHistoryBuffer."""
import numpy as np
import pytest
from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.diagnostics import (
    ConservationTracker,
    DiagnosticsHistoryBuffer,
    compute_snapshot,
)
from nbodiesgravity.engine.system import SolarSystem, TimeStepConfig
from nbodiesgravity.engine.simulation_thread import SimulationThread


def test_diagnostics_history_buffer_operations():
    buf = DiagnosticsHistoryBuffer(max_points=5)
    assert len(buf) == 0
    assert buf.latest_report is None

    b = CelestialBody("A", 1e30, np.zeros(3), np.zeros(3), 1.0, (1, 1, 1))
    tracker = ConservationTracker([b])

    for i in range(7):
        report = tracker.evaluate([b])
        buf.append(time=float(i), report=report, substeps=i + 1, adaptive_dt=0.1)

    # Max points is 5, so length should be 5
    assert len(buf) == 5
    assert buf.latest_report is not None

    data = buf.get_data()
    assert len(data["times"]) == 5
    # Oldest (0 and 1) dropped, so times are [2, 3, 4, 5, 6]
    np.testing.assert_array_equal(data["times"], np.array([2.0, 3.0, 4.0, 5.0, 6.0]))
    np.testing.assert_array_equal(data["substeps"], np.array([3, 4, 5, 6, 7]))
    assert len(data["kinetic_energy"]) == 5
    assert len(data["total_energy"]) == 5
    assert len(data["energy_rel_drift"]) == 5

    buf.clear()
    assert len(buf) == 0
    assert buf.latest_report is None
    assert len(buf.get_data()["times"]) == 0


def test_solar_system_substep_accounting():
    b1 = CelestialBody("Sun", 1.989e30, np.zeros(3), np.zeros(3), 1.0, (1, 1, 0))
    b2 = CelestialBody("Earth", 5.972e24, np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0172, 0.0]), 1.0, (0, 0, 1))
    system = SolarSystem([b1, b2], timestep_config=TimeStepConfig(max_dt=0.25))

    assert system.last_substeps == 0
    assert system.cumulative_substeps == 0
    assert system.last_adaptive_dt == 0.0

    # Step dt=1.0 with max_dt=0.25 should require 4 substeps
    system.step(1.0)
    assert system.last_substeps == 4
    assert system.cumulative_substeps == 4
    assert system.last_adaptive_dt <= 0.25

    # Step again
    system.step(1.0)
    assert system.last_substeps == 4
    assert system.cumulative_substeps == 8

    system.reset_stats()
    assert system.last_substeps == 0
    assert system.cumulative_substeps == 0
    assert system.last_adaptive_dt == 0.0


def test_simulation_thread_diagnostics_integration(qapp):
    import time as _time
    b1 = CelestialBody("Sun", 1.989e30, np.zeros(3), np.zeros(3), 1.0, (1, 1, 0))
    b2 = CelestialBody("Earth", 5.972e24, np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0172, 0.0]), 1.0, (0, 0, 1))
    system = SolarSystem([b1, b2])
    sim = SimulationThread(system)

    assert sim.diagnostics_history is not None
    assert len(sim.diagnostics_history) == 0

    reports = []
    sim.diagnostics_ready.connect(reports.append)

    sim.set_timescale(10.0)
    sim.resume()
    sim.start()

    # Wait for thread to run and emit diagnostics
    for _ in range(50):
        if len(reports) > 0:
            break
        _time.sleep(0.01)
        qapp.processEvents()

    sim.pause()
    sim.stop_thread()

    assert len(reports) > 0
    assert sim.latest_diagnostic_report is not None
    assert len(sim.diagnostics_history) > 0
    data = sim.diagnostics_history.get_data()
    assert len(data["times"]) == len(sim.diagnostics_history)

