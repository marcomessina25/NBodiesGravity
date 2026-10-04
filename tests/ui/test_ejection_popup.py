"""UI verification tests for ejection warning popup and dynamical stability diagnostics."""
import numpy as np
from PyQt6.QtCore import Qt

from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.simulation_thread import SimulationThread
from nbodiesgravity.engine.stability import EjectionEvent, StabilityStatus, StabilityReport
from nbodiesgravity.engine.system import SolarSystem
from nbodiesgravity.ui.ejection_warning_dialog import EjectionWarningDialog
from nbodiesgravity.ui.diagnostics_dialog import ScientificDiagnosticsDialog
from nbodiesgravity.ui.main_window import MainWindow


def test_ejection_warning_dialog_lifecycle(qapp):
    ev1 = EjectionEvent(
        name="Pluto",
        mass=1.303e22,
        distance_au=1005.4,
        speed_au_day=0.015,
        v_infinity_km_s=25.8,
    )
    dlg = EjectionWarningDialog([ev1], duration_sec=2.0)
    assert not dlg.isModal()
    assert "Pluto" in dlg._body_label.text()
    assert "1005.4 AU" in dlg._body_label.text()
    assert "25.8 km/s" in dlg._body_label.text()

    # Append another event
    ev2 = EjectionEvent(
        name="Sedna",
        mass=1e21,
        distance_au=1020.1,
        speed_au_day=0.012,
        v_infinity_km_s=18.4,
    )
    dlg.append_events([ev2])
    assert "Sedna" in dlg._body_label.text()
    assert dlg._remaining_sec == 2

    # Advance timer ticks to verify auto-close
    dlg._on_timer_tick()
    assert dlg._remaining_sec == 1
    assert "1s" in dlg._lbl_countdown.text()

    dlg._on_timer_tick()
    # Should have triggered accept and closed
    assert dlg._remaining_sec <= 0
    dlg.close()


def test_main_window_ejection_handling_and_camera_retarget(qapp):
    sun = CelestialBody("Sun", 1.989e30, np.zeros(3), np.zeros(3), 695700, (1.0, 0.9, 0.2), label="star")
    earth = CelestialBody("Earth", 5.972e24, np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0172, 0.0]), 6371, (0.2, 0.5, 1.0))
    rogue = CelestialBody("Rogue", 1e20, np.array([1010.0, 0.0, 0.0]), np.array([0.02, 0.0, 0.0]), 50.0, (0.5, 0.5, 0.5))

    system = SolarSystem([sun, earth, rogue])
    window = MainWindow()
    window._load_system(system)

    try:
        # Focus camera on the rogue body
        window._gl.camera.set_center("Rogue")
        assert window._gl.camera.center_name == "Rogue"

        # Simulate physics thread reporting the ejection of Rogue
        ev = EjectionEvent(
            name="Rogue",
            mass=1e20,
            distance_au=1010.0,
            speed_au_day=0.02,
            v_infinity_km_s=34.6,
        )
        window._on_ejections([ev])

        # Camera must have automatically retargeted away from the ejected body
        assert window._gl.camera.center_name != "Rogue"
        assert window._gl.camera.center_name in ["Sun", "Earth"]

        # Ejection popup must have been created and visible
        assert window._ejection_dialog is not None
        assert window._ejection_dialog.isVisible()
        assert "Rogue" in window._ejection_dialog._body_label.text()

        window._ejection_dialog.close()
    finally:
        window.close()


def test_diagnostics_dialog_stability_display(qapp):
    sun = CelestialBody("Sun", 1.989e30, np.zeros(3), np.zeros(3), 695700, (1.0, 0.9, 0.2), label="star")
    earth = CelestialBody("Earth", 5.972e24, np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0172, 0.0]), 6371, (0.2, 0.5, 1.0))
    system = SolarSystem([sun, earth])

    thread = SimulationThread(system)
    diag = ScientificDiagnosticsDialog(thread)

    try:
        # Trigger report update
        report = thread.conservation_tracker.evaluate(system.bodies)
        diag._update_conservation_view(report)

        # Check stability box content
        assert "STABLE" in diag._lbl_stability_status.text()
        assert "Sun" in diag._lbl_stability_primary.text()
        assert "0 bodies" in diag._lbl_ejected_count.text()

        # Simulate unstable report (e.g. from an intrusive star)
        unstable_rep = StabilityReport(
            status=StabilityStatus.UNSTABLE,
            reasons=("Companion Star penetrates planetary zone",),
            n_active=3,
            n_ejected=0,
            primary="Sun",
            min_hill_delta=1.2,
        )
        report_with_unstable = thread.conservation_tracker.evaluate(system.bodies)
        object.__setattr__(report_with_unstable, "stability", unstable_rep)
        diag._update_conservation_view(report_with_unstable)

        assert "UNSTABLE" in diag._lbl_stability_status.text()
        assert "Companion Star" in diag._lbl_stability_findings.text()
        assert "1.20" in diag._lbl_min_hill_delta.text()
    finally:
        diag.close()
        thread.stop_thread()
