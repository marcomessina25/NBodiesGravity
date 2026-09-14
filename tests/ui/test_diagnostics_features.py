"""Tests for Diagnostics UI badges, time-window selection, and decimation."""
import numpy as np
import pytest

from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.system import SolarSystem
from nbodiesgravity.engine.simulation_thread import SimulationThread
from nbodiesgravity.ui.diagnostics_dialog import (
    ScientificDiagnosticsDialog,
    _make_badge,
    TOL_ENERGY_PASS,
    TOL_ENERGY_WARN,
    MAX_PLOT_POINTS,
)


@pytest.fixture
def sim_setup():
    sun = CelestialBody("Sun", 1.989e30, np.zeros(3), np.zeros(3), 696340.0, (1.0, 1.0, 0.0))
    earth = CelestialBody("Earth", 5.972e24, np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0172, 0.0]), 6371.0, (0.0, 0.5, 1.0))
    system = SolarSystem([sun, earth])
    sim = SimulationThread(system)
    return sim


def test_make_badge_thresholds():
    """Verify _make_badge classifies drift magnitudes into PASS, WARN, and ALERT."""
    # PASS: well within tolerance
    badge_pass = _make_badge(1e-6, TOL_ENERGY_PASS, TOL_ENERGY_WARN)
    assert "PASS" in badge_pass
    assert "#2ecc71" in badge_pass

    # Negative value handled via abs()
    badge_pass_neg = _make_badge(-1e-6, TOL_ENERGY_PASS, TOL_ENERGY_WARN)
    assert "PASS" in badge_pass_neg

    # WARN: moderate drift
    badge_warn = _make_badge(5e-3, TOL_ENERGY_PASS, TOL_ENERGY_WARN)
    assert "WARN" in badge_warn
    assert "#f39c12" in badge_warn

    # ALERT: severe drift
    badge_alert = _make_badge(0.05, TOL_ENERGY_PASS, TOL_ENERGY_WARN)
    assert "ALERT" in badge_alert
    assert "#e74c3c" in badge_alert


def test_diagnostics_conservation_badges_rendered(qapp, sim_setup):
    """Verify status badges are placed on energy, momentum, and COM labels."""
    dialog = ScientificDiagnosticsDialog(sim_setup)
    try:
        report = sim_setup.conservation_tracker.evaluate(sim_setup.system.bodies)
        dialog._update_conservation_view(report)

        # Labels must contain badge HTML with PASS, WARN, or ALERT
        assert any(tag in dialog._lbl_energy_drift.text() for tag in ("PASS", "WARN", "ALERT"))
        assert any(tag in dialog._lbl_linear_drift.text() for tag in ("PASS", "WARN", "ALERT"))
        assert any(tag in dialog._lbl_angular_drift.text() for tag in ("PASS", "WARN", "ALERT"))
        assert any(tag in dialog._lbl_com_drift.text() for tag in ("PASS", "WARN", "ALERT"))
    finally:
        dialog.close()


def test_diagnostics_time_window_filtering(qapp, sim_setup):
    """Verify time-window combo filters displayed plot points without modifying history."""
    dialog = ScientificDiagnosticsDialog(sim_setup)
    try:
        report = sim_setup.conservation_tracker.evaluate(sim_setup.system.bodies)
        # Add points at t = 0, 50, 200, 300, 400 days
        for t in [0.0, 50.0, 200.0, 300.0, 400.0]:
            sim_setup.diagnostics_history.append(t, report, substeps=1, adaptive_dt=0.5)

        # Default: All Retained History (5 points)
        dialog._combo_time_window.setCurrentText("All Retained History")
        dialog._update_plots()
        xdata_all = dialog._ax_energy.lines[0].get_xdata()
        assert len(xdata_all) == 5
        assert np.allclose(xdata_all, [0.0, 50.0, 200.0, 300.0, 400.0])

        # Last 100 Days: points >= 400 - 100 = 300 (2 points: 300 and 400)
        dialog._combo_time_window.setCurrentText("Last 100 Days")
        dialog._update_plots()
        xdata_100 = dialog._ax_energy.lines[0].get_xdata()
        assert len(xdata_100) == 2
        assert np.allclose(xdata_100, [300.0, 400.0])

        # Last 365 Days: points >= 400 - 365 = 35 (4 points: 50, 200, 300, 400)
        dialog._combo_time_window.setCurrentText("Last 365 Days (1 Year)")
        dialog._update_plots()
        xdata_365 = dialog._ax_energy.lines[0].get_xdata()
        assert len(xdata_365) == 4
        assert np.allclose(xdata_365, [50.0, 200.0, 300.0, 400.0])

        # History in sim_setup must still retain all 5 raw records
        assert len(sim_setup.diagnostics_history) == 5
    finally:
        dialog.close()


def test_diagnostics_plot_decimation(qapp, sim_setup):
    """Verify plot decimation downsamples large datasets for display without losing raw data."""
    dialog = ScientificDiagnosticsDialog(sim_setup)
    try:
        report = sim_setup.conservation_tracker.evaluate(sim_setup.system.bodies)
        # Append 1500 points
        for i in range(1500):
            sim_setup.diagnostics_history.append(float(i), report, substeps=1, adaptive_dt=0.1)

        dialog._combo_time_window.setCurrentText("All Retained History")
        dialog._update_plots()

        # Plotted line points must be decimated down to approx MAX_PLOT_POINTS
        xdata = dialog._ax_energy.lines[0].get_xdata()
        assert len(xdata) <= MAX_PLOT_POINTS + 5
        assert len(xdata) < 1500

        # Raw history remains intact
        assert len(sim_setup.diagnostics_history) == 1500
    finally:
        dialog.close()
