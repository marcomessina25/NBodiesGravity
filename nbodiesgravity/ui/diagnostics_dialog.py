"""Scientific Diagnostics, Orbital Analysis, and Conservation Plotting Dialog."""
from __future__ import annotations
from typing import TYPE_CHECKING
import numpy as np

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QGroupBox, QGridLayout, QComboBox, QPushButton,
    QFileDialog, QMessageBox, QFrame,
)
from PyQt6.QtCore import Qt, QTimer

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from nbodiesgravity.engine.orbital_elements import (
    compute_elements_for_body,
    find_dominant_primary,
    OrbitalElements,
)
from nbodiesgravity.data.export import (
    export_conservation_history_csv,
    export_conservation_history_json,
    export_orbital_elements_csv,
    export_orbital_elements_json,
)

if TYPE_CHECKING:
    from nbodiesgravity.engine.simulation_thread import SimulationThread


class ScientificDiagnosticsDialog(QDialog):
    """Non-modal diagnostic inspection and orbital analysis laboratory."""

    def __init__(self, sim: SimulationThread, parent=None) -> None:
        super().__init__(parent)
        self._sim = sim
        self.setWindowTitle("Scientific Diagnostics & Orbital Analysis — NBodiesGravity")
        self.resize(850, 620)

        self._build_ui()

        # Connect live simulation signal
        self._sim.diagnostics_ready.connect(self._on_diagnostics_ready)

        # Timer for throttled UI & plot refreshes (~4 Hz)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(250)
        self._refresh_timer.timeout.connect(self._on_periodic_refresh)
        self._refresh_timer.start()

        self._populate_body_combos()
        self._update_conservation_view()
        self._update_orbital_view()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        # Tab 1: Conservation Overview
        self._tab_conservation = QWidget()
        self._build_conservation_tab(self._tab_conservation)
        self._tabs.addTab(self._tab_conservation, "⚡ Conservation & Integrator")

        # Tab 2: Orbital Elements Inspector
        self._tab_orbital = QWidget()
        self._build_orbital_tab(self._tab_orbital)
        self._tabs.addTab(self._tab_orbital, "🪐 Orbital Elements Inspector")

        # Tab 3: Live Conservation Plots
        self._tab_plots = QWidget()
        self._build_plots_tab(self._tab_plots)
        self._tabs.addTab(self._tab_plots, "📈 Physical Conservation Plots")

        # Bottom Action Bar
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        btn_exp_diag_csv = QPushButton("Export Diag (CSV)…")
        btn_exp_diag_csv.clicked.connect(self._export_diag_csv)
        bottom_bar.addWidget(btn_exp_diag_csv)

        btn_exp_diag_json = QPushButton("Export Diag (JSON)…")
        btn_exp_diag_json.clicked.connect(self._export_diag_json)
        bottom_bar.addWidget(btn_exp_diag_json)

        btn_exp_orb_csv = QPushButton("Export Orbits (CSV)…")
        btn_exp_orb_csv.clicked.connect(self._export_orbital_csv)
        bottom_bar.addWidget(btn_exp_orb_csv)

        btn_exp_orb_json = QPushButton("Export Orbits (JSON)…")
        btn_exp_orb_json.clicked.connect(self._export_orbital_json)
        bottom_bar.addWidget(btn_exp_orb_json)

        bottom_bar.addStretch()

        btn_close = QPushButton("Close")
        btn_close.setFixedWidth(80)
        btn_close.clicked.connect(self.hide)
        bottom_bar.addWidget(btn_close)

        layout.addLayout(bottom_bar)

    # -------------------------------------------------------------------------
    # Tab 1: Conservation & Integrator
    # -------------------------------------------------------------------------
    def _build_conservation_tab(self, parent: QWidget) -> None:
        layout = QVBoxLayout(parent)
        layout.setSpacing(12)

        # Energy & Conservation Box
        box_energy = QGroupBox("Mechanical Energy & Drifts")
        grid_e = QGridLayout(box_energy)

        grid_e.addWidget(QLabel("<b>Total Energy (E):</b>"), 0, 0)
        self._lbl_total_energy = QLabel("–")
        grid_e.addWidget(self._lbl_total_energy, 0, 1)

        grid_e.addWidget(QLabel("<b>Kinetic Energy (K):</b>"), 1, 0)
        self._lbl_kinetic_energy = QLabel("–")
        grid_e.addWidget(self._lbl_kinetic_energy, 1, 1)

        grid_e.addWidget(QLabel("<b>Potential Energy (U):</b>"), 2, 0)
        self._lbl_potential_energy = QLabel("–")
        grid_e.addWidget(self._lbl_potential_energy, 2, 1)

        grid_e.addWidget(QLabel("<b>Relative Energy Drift (ΔE/E₀):</b>"), 3, 0)
        self._lbl_energy_drift = QLabel("–")
        grid_e.addWidget(self._lbl_energy_drift, 3, 1)

        layout.addWidget(box_energy)

        # Momentum & Center of Mass Box
        box_mom = QGroupBox("Momentum & Center of Mass")
        grid_m = QGridLayout(box_mom)

        grid_m.addWidget(QLabel("<b>Linear Momentum |P|:</b>"), 0, 0)
        self._lbl_linear_mom = QLabel("–")
        grid_m.addWidget(self._lbl_linear_mom, 0, 1)

        grid_m.addWidget(QLabel("<b>Normalized Momentum Drift:</b>"), 0, 2)
        self._lbl_linear_drift = QLabel("–")
        grid_m.addWidget(self._lbl_linear_drift, 0, 3)

        grid_m.addWidget(QLabel("<b>Angular Momentum |L|:</b>"), 1, 0)
        self._lbl_angular_mom = QLabel("–")
        grid_m.addWidget(self._lbl_angular_mom, 1, 1)

        grid_m.addWidget(QLabel("<b>Relative Angular Drift (ΔL/L₀):</b>"), 1, 2)
        self._lbl_angular_drift = QLabel("–")
        grid_m.addWidget(self._lbl_angular_drift, 1, 3)

        grid_m.addWidget(QLabel("<b>Center of Mass [X, Y, Z]:</b>"), 2, 0)
        self._lbl_center_of_mass = QLabel("–")
        grid_m.addWidget(self._lbl_center_of_mass, 2, 1)

        grid_m.addWidget(QLabel("<b>Center of Mass Drift:</b>"), 2, 2)
        self._lbl_com_drift = QLabel("–")
        grid_m.addWidget(self._lbl_com_drift, 2, 3)

        layout.addWidget(box_mom)

        # Integrator & Timestep Budget
        box_int = QGroupBox("Velocity Verlet Integrator & Substep Budget")
        grid_i = QGridLayout(box_int)

        grid_i.addWidget(QLabel("<b>Last Substeps:</b>"), 0, 0)
        self._lbl_last_substeps = QLabel("–")
        grid_i.addWidget(self._lbl_last_substeps, 0, 1)

        grid_i.addWidget(QLabel("<b>Cumulative Substeps:</b>"), 0, 2)
        self._lbl_cum_substeps = QLabel("–")
        grid_i.addWidget(self._lbl_cum_substeps, 0, 3)

        grid_i.addWidget(QLabel("<b>Selected Substep (dt):</b>"), 1, 0)
        self._lbl_adaptive_dt = QLabel("–")
        grid_i.addWidget(self._lbl_adaptive_dt, 1, 1)

        grid_i.addWidget(QLabel("<b>Max Budget:</b>"), 1, 2)
        self._lbl_max_substeps = QLabel("10,000 substeps")
        grid_i.addWidget(self._lbl_max_substeps, 1, 3)

        grid_i.addWidget(QLabel("<b>Softening (ε):</b>"), 2, 0)
        self._lbl_softening = QLabel("–")
        grid_i.addWidget(self._lbl_softening, 2, 1)

        layout.addWidget(box_int)
        layout.addStretch()

    # -------------------------------------------------------------------------
    # Tab 2: Orbital Elements Inspector
    # -------------------------------------------------------------------------
    def _build_orbital_tab(self, parent: QWidget) -> None:
        layout = QVBoxLayout(parent)
        layout.setSpacing(10)

        # Body selection bar
        sel_bar = QHBoxLayout()
        sel_bar.addWidget(QLabel("Target Body:"))
        self._combo_target_body = QComboBox()
        self._combo_target_body.currentTextChanged.connect(self._update_orbital_view)
        sel_bar.addWidget(self._combo_target_body, stretch=1)

        sel_bar.addSpacing(16)
        sel_bar.addWidget(QLabel("Primary Center:"))
        self._combo_primary_body = QComboBox()
        self._combo_primary_body.currentTextChanged.connect(self._update_orbital_view)
        sel_bar.addWidget(self._combo_primary_body, stretch=1)

        layout.addLayout(sel_bar)

        # Elements Card Grid
        box_elements = QGroupBox("Osculating Keplerian Elements")
        grid_orb = QGridLayout(box_elements)
        grid_orb.setSpacing(10)

        grid_orb.addWidget(QLabel("<b>Semi-Major Axis (a):</b>"), 0, 0)
        self._lbl_semi_major = QLabel("–")
        grid_orb.addWidget(self._lbl_semi_major, 0, 1)

        grid_orb.addWidget(QLabel("<b>Eccentricity (e):</b>"), 0, 2)
        self._lbl_eccentricity = QLabel("–")
        grid_orb.addWidget(self._lbl_eccentricity, 0, 3)

        grid_orb.addWidget(QLabel("<b>Inclination (i):</b>"), 1, 0)
        self._lbl_inclination = QLabel("–")
        grid_orb.addWidget(self._lbl_inclination, 1, 1)

        grid_orb.addWidget(QLabel("<b>Orbit Classification:</b>"), 1, 2)
        self._lbl_orbit_type = QLabel("–")
        grid_orb.addWidget(self._lbl_orbit_type, 1, 3)

        grid_orb.addWidget(QLabel("<b>Periapsis (q):</b>"), 2, 0)
        self._lbl_periapsis = QLabel("–")
        grid_orb.addWidget(self._lbl_periapsis, 2, 1)

        grid_orb.addWidget(QLabel("<b>Apoapsis (Q):</b>"), 2, 2)
        self._lbl_apoapsis = QLabel("–")
        grid_orb.addWidget(self._lbl_apoapsis, 2, 3)

        grid_orb.addWidget(QLabel("<b>Orbital Period (T):</b>"), 3, 0)
        self._lbl_period = QLabel("–")
        grid_orb.addWidget(self._lbl_period, 3, 1)

        grid_orb.addWidget(QLabel("<b>Specific Energy (ε):</b>"), 3, 2)
        self._lbl_spec_energy = QLabel("–")
        grid_orb.addWidget(self._lbl_spec_energy, 3, 3)

        grid_orb.addWidget(QLabel("<b>Longitude of Asc. Node (Ω):</b>"), 4, 0)
        self._lbl_long_node = QLabel("–")
        grid_orb.addWidget(self._lbl_long_node, 4, 1)

        grid_orb.addWidget(QLabel("<b>Argument of Periapsis (ω):</b>"), 4, 2)
        self._lbl_arg_peri = QLabel("–")
        grid_orb.addWidget(self._lbl_arg_peri, 4, 3)

        grid_orb.addWidget(QLabel("<b>True Anomaly (ν):</b>"), 5, 0)
        self._lbl_true_anomaly = QLabel("–")
        grid_orb.addWidget(self._lbl_true_anomaly, 5, 1)

        grid_orb.addWidget(QLabel("<b>Dominant Parent:</b>"), 5, 2)
        self._lbl_dominant_parent = QLabel("–")
        grid_orb.addWidget(self._lbl_dominant_parent, 5, 3)

        layout.addWidget(box_elements)
        layout.addStretch()

    # -------------------------------------------------------------------------
    # Tab 3: Conservation Plots
    # -------------------------------------------------------------------------
    def _build_plots_tab(self, parent: QWidget) -> None:
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(4, 4, 4, 4)

        # Matplotlib Figure with dark theme
        self._fig = Figure(figsize=(6, 5.5), dpi=100)
        self._fig.patch.set_facecolor("#1e1e1e")

        self._ax_energy = self._fig.add_subplot(311)
        self._ax_momentum = self._fig.add_subplot(312)
        self._ax_adaptive = self._fig.add_subplot(313)
        self._ax_adaptive_dt = self._ax_adaptive.twinx()

        self._style_axes(self._ax_energy, "Relative Energy Drift (ΔE/E₀)")
        self._style_axes(self._ax_momentum, "Momentum Drifts")
        self._style_axes(self._ax_adaptive, "Substeps per Step")
        self._style_twin_axis(self._ax_adaptive_dt, "Adaptive dt (days)")

        self._fig.tight_layout()
        self._canvas = FigureCanvas(self._fig)
        layout.addWidget(self._canvas, stretch=1)

        btn_bar = QHBoxLayout()
        btn_clear_plots = QPushButton("Clear Plot Buffer")
        btn_clear_plots.clicked.connect(self._clear_plot_history)
        btn_bar.addWidget(btn_clear_plots)
        btn_bar.addStretch()
        layout.addLayout(btn_bar)

    def _style_axes(self, ax, ylabel: str) -> None:
        ax.set_facecolor("#252525")
        ax.tick_params(colors="#cccccc", labelsize=8)
        ax.xaxis.label.set_color("#cccccc")
        ax.yaxis.label.set_color("#cccccc")
        ax.set_ylabel(ylabel, color="#ffffff", fontsize=8)
        ax.grid(True, linestyle="--", alpha=0.3, color="#666666")
        for spine in ax.spines.values():
            spine.set_color("#555555")

    def _style_twin_axis(self, ax, ylabel: str) -> None:
        ax.tick_params(colors="#e056fd", labelsize=8)
        ax.yaxis.label.set_color("#e056fd")
        ax.set_ylabel(ylabel, color="#e056fd", fontsize=8)
        ax.grid(False)
        for spine in ax.spines.values():
            spine.set_color("#555555")

    # -------------------------------------------------------------------------
    # Live Updates
    # -------------------------------------------------------------------------
    def _populate_body_combos(self) -> None:
        snapshot = self._sim.latest_snapshot
        current_target = self._combo_target_body.currentText()
        current_primary = self._combo_primary_body.currentText()

        self._combo_target_body.blockSignals(True)
        self._combo_primary_body.blockSignals(True)

        self._combo_target_body.clear()
        self._combo_primary_body.clear()

        self._combo_primary_body.addItem("Auto-detect (Hill sphere)")

        for b in snapshot:
            if b.active:
                self._combo_target_body.addItem(b.name)
                self._combo_primary_body.addItem(b.name)

        if current_target and self._combo_target_body.findText(current_target) >= 0:
            self._combo_target_body.setCurrentText(current_target)
        elif self._combo_target_body.count() > 1:
            self._combo_target_body.setCurrentIndex(1)  # choose Earth or second body

        if current_primary and self._combo_primary_body.findText(current_primary) >= 0:
            self._combo_primary_body.setCurrentText(current_primary)

        self._combo_target_body.blockSignals(False)
        self._combo_primary_body.blockSignals(False)

    def _on_diagnostics_ready(self, report) -> None:
        if self.isVisible() and self._tabs.currentIndex() == 0:
            self._update_conservation_view(report)

    def _on_periodic_refresh(self) -> None:
        if not self.isVisible():
            return

        idx = self._tabs.currentIndex()
        if idx == 0:
            self._update_conservation_view()
        elif idx == 1:
            self._update_orbital_view()
        elif idx == 2:
            self._update_plots()

    def _update_conservation_view(self, report=None) -> None:
        if report is None:
            report = self._sim.latest_diagnostic_report
        if report is None:
            return

        curr = report.current
        self._lbl_total_energy.setText(f"{curr.total_energy:+.8e} AU² kg day⁻²")
        self._lbl_kinetic_energy.setText(f"{curr.kinetic_energy:+.8e} AU² kg day⁻²")
        self._lbl_potential_energy.setText(f"{curr.potential_energy:+.8e} AU² kg day⁻²")

        rel_e = report.energy_drift.rel_drift
        badge_color = "#2ecc71" if abs(rel_e) < 1e-4 else ("#f39c12" if abs(rel_e) < 1e-2 else "#e74c3c")
        self._lbl_energy_drift.setText(
            f"<span style='color:{badge_color}; font-weight:bold;'>{rel_e:+.4e} ({rel_e * 100.0:+.4f}%)</span>"
        )

        p_norm = float(np.linalg.norm(curr.linear_momentum))
        self._lbl_linear_mom.setText(f"{p_norm:.6e} AU kg day⁻¹")
        self._lbl_linear_drift.setText(f"{report.normalized_momentum_drift:.4e}")

        l_norm = float(np.linalg.norm(curr.angular_momentum))
        self._lbl_angular_mom.setText(f"{l_norm:.6e} AU² kg day⁻¹")
        self._lbl_angular_drift.setText(f"{report.angular_momentum_drift.rel_drift:+.4e}")

        cm = curr.center_of_mass
        self._lbl_center_of_mass.setText(f"[{cm[0]:+.4e}, {cm[1]:+.4e}, {cm[2]:+.4e}] AU")
        self._lbl_com_drift.setText(f"{report.center_of_mass_drift.abs_drift:.4e} AU")

        self._lbl_last_substeps.setText(f"{self._sim.system.last_substeps} substeps")
        self._lbl_cum_substeps.setText(f"{self._sim.system.cumulative_substeps:,} substeps")
        self._lbl_adaptive_dt.setText(f"{self._sim.system.last_adaptive_dt:.6e} days")
        self._lbl_max_substeps.setText(f"{self._sim.system.timestep_config.max_substeps:,} substeps")
        self._lbl_softening.setText(f"{self._sim.system.softening:.2e} AU")

    def _update_orbital_view(self) -> None:
        target_name = self._combo_target_body.currentText()
        if not target_name:
            return

        snapshot = self._sim.latest_snapshot
        body = next((b for b in snapshot if b.name == target_name and b.active), None)
        if not body:
            return

        primary_choice = self._combo_primary_body.currentText()
        if primary_choice == "Auto-detect (Hill sphere)":
            primary = find_dominant_primary(body, snapshot)
        else:
            primary = next((b for b in snapshot if b.name == primary_choice and b.active), None)

        if not primary or primary.name == body.name:
            self._lbl_dominant_parent.setText("None (Unbound / Self)")
            self._clear_orbital_labels()
            return

        self._lbl_dominant_parent.setText(primary.name)
        elem = compute_elements_for_body(body, primary)

        km_per_au = 1.495978707e8
        self._lbl_semi_major.setText(f"{elem.semi_major_axis:.6f} AU ({elem.semi_major_axis * km_per_au:,.0f} km)")
        self._lbl_eccentricity.setText(f"{elem.eccentricity:.6f}")

        if elem.eccentricity < 1e-4:
            otype = "<span style='color:#3498db;'>Circular</span>"
        elif elem.eccentricity < 1.0:
            otype = "<span style='color:#2ecc71;'>Elliptical</span>"
        elif abs(elem.eccentricity - 1.0) < 1e-3:
            otype = "<span style='color:#f39c12;'>Parabolic</span>"
        else:
            otype = "<span style='color:#e74c3c;'>Hyperbolic (Escape)</span>"
        self._lbl_orbit_type.setText(otype)

        self._lbl_inclination.setText(f"{elem.inclination_deg:.3f}° ({elem.inclination:.4f} rad)")

        rp_str = f"{elem.periapsis:.6f} AU ({elem.periapsis * km_per_au:,.0f} km)"
        self._lbl_periapsis.setText(rp_str)

        if np.isfinite(elem.apoapsis):
            ra_str = f"{elem.apoapsis:.6f} AU ({elem.apoapsis * km_per_au:,.0f} km)"
        else:
            ra_str = "∞ (Unbound)"
        self._lbl_apoapsis.setText(ra_str)

        if np.isfinite(elem.period):
            p_str = f"{elem.period:.2f} days ({elem.period_years:.4f} yr)"
        else:
            p_str = "∞ (Unbound)"
        self._lbl_period.setText(p_str)

        self._lbl_spec_energy.setText(f"{elem.specific_energy:+.6e} AU² day⁻²")
        self._lbl_long_node.setText(f"{elem.longitude_ascending_node_deg:.3f}°")
        self._lbl_arg_peri.setText(f"{elem.argument_of_periapsis_deg:.3f}°")
        self._lbl_true_anomaly.setText(f"{elem.true_anomaly_deg:.3f}°")

    def _clear_orbital_labels(self) -> None:
        self._lbl_semi_major.setText("–")
        self._lbl_eccentricity.setText("–")
        self._lbl_orbit_type.setText("–")
        self._lbl_inclination.setText("–")
        self._lbl_periapsis.setText("–")
        self._lbl_apoapsis.setText("–")
        self._lbl_period.setText("–")
        self._lbl_spec_energy.setText("–")
        self._lbl_long_node.setText("–")
        self._lbl_arg_peri.setText("–")
        self._lbl_true_anomaly.setText("–")

    def _update_plots(self) -> None:
        data = self._sim.diagnostics_history.get_data()
        times = data["times"]
        if len(times) < 2:
            return

        self._ax_energy.clear()
        self._ax_momentum.clear()
        self._ax_adaptive.clear()
        self._ax_adaptive_dt.clear()

        self._style_axes(self._ax_energy, "Rel. Energy Drift (ΔE/E₀)")
        self._style_axes(self._ax_momentum, "Momentum Drift")
        self._style_axes(self._ax_adaptive, "Substeps")
        self._style_twin_axis(self._ax_adaptive_dt, "Adaptive dt (days)")
        self._ax_adaptive.set_xlabel("Elapsed Time (days)", color="#cccccc", fontsize=9)

        # Plot energy drift
        self._ax_energy.plot(times, data["energy_rel_drift"], color="#00d4ff", linewidth=1.5, label="ΔE/E₀")
        self._ax_energy.legend(loc="upper right", facecolor="#1e1e1e", edgecolor="#555555", labelcolor="#ffffff", fontsize=8)

        # Plot linear and angular momentum drift
        self._ax_momentum.plot(times, data["momentum_norm_drift"], color="#ff9900", linewidth=1.5, label="Linear Norm ΔP")
        self._ax_momentum.plot(times, data["angular_momentum_rel_drift"], color="#00ff88", linewidth=1.5, label="Angular ΔL/L₀")
        self._ax_momentum.legend(loc="upper right", facecolor="#1e1e1e", edgecolor="#555555", labelcolor="#ffffff", fontsize=8)

        # Plot adaptive integration: substeps per step and selected dt
        line1 = self._ax_adaptive.plot(times, data["substeps"], color="#f1c40f", linewidth=1.5, label="Substeps")
        line2 = self._ax_adaptive_dt.plot(times, data["adaptive_dt"], color="#e056fd", linewidth=1.5, linestyle="--", label="Adaptive dt")
        lines = line1 + line2
        labels = [line.get_label() for line in lines]
        self._ax_adaptive.legend(lines, labels, loc="upper right", facecolor="#1e1e1e", edgecolor="#555555", labelcolor="#ffffff", fontsize=8)

        self._fig.tight_layout()
        self._canvas.draw_idle()

    def _clear_plot_history(self) -> None:
        self._sim.diagnostics_history.clear()
        self._ax_energy.clear()
        self._ax_momentum.clear()
        self._ax_adaptive.clear()
        self._ax_adaptive_dt.clear()
        self._style_axes(self._ax_energy, "Rel. Energy Drift (ΔE/E₀)")
        self._style_axes(self._ax_momentum, "Momentum Drift")
        self._style_axes(self._ax_adaptive, "Substeps")
        self._style_twin_axis(self._ax_adaptive_dt, "Adaptive dt (days)")
        self._fig.tight_layout()
        self._canvas.draw_idle()

    # -------------------------------------------------------------------------
    # Export Actions
    # -------------------------------------------------------------------------
    def _export_diag_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Diagnostics to CSV", "diagnostics_history.csv", "CSV Files (*.csv)")
        if path:
            export_conservation_history_csv(self._sim.diagnostics_history, path)
            QMessageBox.information(self, "Export Successful", f"Diagnostics history saved to:\n{path}")

    def _export_diag_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Diagnostics to JSON", "diagnostics_history.json", "JSON Files (*.json)")
        if path:
            export_conservation_history_json(self._sim.diagnostics_history, path)
            QMessageBox.information(self, "Export Successful", f"Diagnostics history saved to:\n{path}")

    def _export_orbital_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Orbital Elements to CSV", "orbital_elements.csv", "CSV Files (*.csv)")
        if path:
            elem_map = self._collect_all_orbital_elements()
            export_orbital_elements_csv(elem_map, path)
            QMessageBox.information(self, "Export Successful", f"Orbital elements saved to:\n{path}")

    def _export_orbital_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Orbital Elements to JSON", "orbital_elements.json", "JSON Files (*.json)")
        if path:
            elem_map = self._collect_all_orbital_elements()
            export_orbital_elements_json(elem_map, path)
            QMessageBox.information(self, "Export Successful", f"Orbital elements saved to:\n{path}")

    def _collect_all_orbital_elements(self) -> dict[str, OrbitalElements]:
        snapshot = self._sim.latest_snapshot
        elements_map: dict[str, OrbitalElements] = {}
        for b in snapshot:
            if not b.active:
                continue
            primary = find_dominant_primary(b, snapshot)
            if primary and primary.name != b.name:
                elements_map[b.name] = compute_elements_for_body(b, primary)
        return elements_map
