"""Tests for ScientificDiagnosticsDialog and MainWindow diagnostics integration."""
import numpy as np
import pytest
from PyQt6.QtCore import Qt

from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.system import SolarSystem
from nbodiesgravity.engine.simulation_thread import SimulationThread
from nbodiesgravity.ui.diagnostics_dialog import ScientificDiagnosticsDialog
from nbodiesgravity.ui.main_window import MainWindow


@pytest.fixture
def test_sim():
    sun = CelestialBody("Sun", 1.989e30, np.zeros(3), np.zeros(3), 696340.0, (1.0, 1.0, 0.0), label="star")
    earth = CelestialBody("Earth", 5.972e24, np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0172, 0.0]), 6371.0, (0.0, 0.5, 1.0), label="planet")
    system = SolarSystem([sun, earth])
    sim = SimulationThread(system)
    return sim


def test_diagnostics_dialog_creation_and_tabs(qapp, test_sim):
    dialog = ScientificDiagnosticsDialog(test_sim)
    try:
        assert dialog.windowTitle().startswith("Scientific Diagnostics")
        assert dialog._tabs.count() == 3

        # Check tab names
        assert "Conservation" in dialog._tabs.tabText(0)
        assert "Orbital" in dialog._tabs.tabText(1)
        assert "Plots" in dialog._tabs.tabText(2)

        # Combo should contain Sun and Earth
        assert dialog._combo_target_body.count() == 2
        assert dialog._combo_primary_body.count() == 3  # "Auto-detect" + Sun + Earth

        # Target Earth
        dialog._combo_target_body.setCurrentText("Earth")
        dialog._update_orbital_view()

        assert "AU" in dialog._lbl_semi_major.text()
        assert dialog._lbl_dominant_parent.text() == "Sun"

        # Check conservation labels
        report = test_sim.conservation_tracker.evaluate(test_sim.system.bodies)
        dialog._update_conservation_view(report)
        assert "AU² kg day⁻²" in dialog._lbl_total_energy.text()
        assert "%" in dialog._lbl_energy_drift.text()
    finally:
        dialog.close()


def test_diagnostics_plots_update(qapp, test_sim):
    dialog = ScientificDiagnosticsDialog(test_sim)
    try:
        report = test_sim.conservation_tracker.evaluate(test_sim.system.bodies)
        test_sim.diagnostics_history.append(0.0, report, substeps=1, adaptive_dt=1.0)
        test_sim.diagnostics_history.append(1.0, report, substeps=2, adaptive_dt=0.5)

        dialog._update_plots()
        # Canvas should have drawn without error
        assert dialog._canvas is not None

        dialog._clear_plot_history()
        assert len(test_sim.diagnostics_history) == 0
    finally:
        dialog.close()


def test_main_window_diagnostics_action(qapp):
    window = MainWindow()
    try:
        assert hasattr(window, "_action_open_diag")
        assert window._action_open_diag.shortcut().toString() == "Ctrl+D"

        # Trigger via action
        window._action_open_diag.trigger()
        qapp.processEvents()
        assert window._diag_dialog is not None
        assert window._diag_dialog.isVisible()

        # Hide and trigger via control panel button
        window._diag_dialog.hide()
        assert not window._diag_dialog.isVisible()

        window._ctrl._diag_btn.click()
        qapp.processEvents()
        assert window._diag_dialog.isVisible()
    finally:
        if window._diag_dialog is not None:
            window._diag_dialog.close()
        window.close()
