"""QDialog for adding or editing a CelestialBody.

Validation (OK button disabled until all pass):
  - name not empty; not duplicate (in Add mode)
  - mass > 0
  - radius > 0
"""
from __future__ import annotations
import numpy as np
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QDialogButtonBox, QLineEdit,
    QDoubleSpinBox, QPushButton, QLabel, QColorDialog,
    QHBoxLayout, QWidget,
)
from PyQt6.QtGui import QColor
from nbodiesgravity.engine.body import CelestialBody


class BodyEditorDialog(QDialog):
    def __init__(
        self,
        existing_names: list[str],
        body: CelestialBody | None = None,
        template_bodies: list[CelestialBody] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._existing_names = existing_names
        self._edit_mode = body is not None
        self._template_bodies: dict[str, CelestialBody] = (
            {b.name: b for b in template_bodies} if template_bodies else {}
        )
        self._color: tuple[float, float, float] = body.color if body else (1.0, 1.0, 1.0)
        self.setWindowTitle("Edit Body" if self._edit_mode else "Add Body")
        self.setModal(True)
        self._build_ui(body)
        self._validate()

    def result_body(self) -> CelestialBody:
        """Call after exec() returns Accepted to retrieve the configured body."""
        return CelestialBody(
            name=self._name_edit.text().strip(),
            mass=self._mass_spin.value(),
            pos=np.array([self._px.value(), self._py.value(), self._pz.value()]),
            vel=np.array([self._vx.value(), self._vy.value(), self._vz.value()]),
            radius=self._radius_spin.value(),
            color=self._color,
            label=self._label_combo.currentText(),
        )

    def _build_ui(self, body: CelestialBody | None) -> None:
        form = QFormLayout(self)

        # Name row
        self._name_edit = QLineEdit(body.name if body else "")
        self._name_edit.textChanged.connect(self._validate)
        form.addRow("Name:", self._name_edit)

        # Label row
        self._label_combo = QComboBox()
        self._label_combo.addItems(["star", "planet", "moon", "dwarf planet", "asteroid"])
        self._label_combo.setCurrentText(body.label if body else "planet")
        form.addRow("Label:", self._label_combo)

        # Mass rows
        self._mass_spin = _sci_spin(1e-3, 2e30, body.mass if body else 1e22)
        self._mass_spin.valueChanged.connect(self._validate)

        if not self._edit_mode and self._template_bodies:
            self._mass_mode_combo = QComboBox()
            self._mass_mode_combo.addItems(["Manual", "Template * Multiplier"])
            self._mass_mode_combo.currentTextChanged.connect(self._on_mass_mode_changed)
            form.addRow("Mass Mode:", self._mass_mode_combo)

            self._mass_template_container = QWidget()
            mass_temp_layout = QHBoxLayout(self._mass_template_container)
            mass_temp_layout.setContentsMargins(0, 0, 0, 0)
            self._mass_template_combo = QComboBox()
            for name in self._template_bodies:
                self._mass_template_combo.addItem(name)
            self._mass_template_combo.currentTextChanged.connect(lambda _: self._update_templated_mass())

            self._mass_mult_spin = QDoubleSpinBox()
            self._mass_mult_spin.setRange(1e-6, 1e6)
            self._mass_mult_spin.setValue(1.0)
            self._mass_mult_spin.setDecimals(4)
            self._mass_mult_spin.setStepType(QDoubleSpinBox.StepType.AdaptiveDecimalStepType)
            self._mass_mult_spin.valueChanged.connect(lambda _: self._update_templated_mass())

            mass_temp_layout.addWidget(QLabel("Body:"))
            mass_temp_layout.addWidget(self._mass_template_combo)
            mass_temp_layout.addWidget(QLabel("Multiplier:"))
            mass_temp_layout.addWidget(self._mass_mult_spin)

            form.addRow("Mass (kg):", self._mass_spin)
            form.addRow("Mass Template Source:", self._mass_template_container)
            self._mass_template_container.setVisible(False)
        else:
            form.addRow("Mass (kg):", self._mass_spin)

        # Radius rows
        self._radius_spin = _sci_spin(0.1, 1e7, body.radius if body else 1000.0)
        self._radius_spin.valueChanged.connect(self._validate)

        if not self._edit_mode and self._template_bodies:
            self._radius_mode_combo = QComboBox()
            self._radius_mode_combo.addItems(["Manual", "Template * Multiplier"])
            self._radius_mode_combo.currentTextChanged.connect(self._on_radius_mode_changed)
            form.addRow("Radius Mode:", self._radius_mode_combo)

            self._radius_template_container = QWidget()
            rad_temp_layout = QHBoxLayout(self._radius_template_container)
            rad_temp_layout.setContentsMargins(0, 0, 0, 0)
            self._radius_template_combo = QComboBox()
            for name in self._template_bodies:
                self._radius_template_combo.addItem(name)
            self._radius_template_combo.currentTextChanged.connect(lambda _: self._update_templated_radius())

            self._radius_mult_spin = QDoubleSpinBox()
            self._radius_mult_spin.setRange(1e-6, 1e6)
            self._radius_mult_spin.setValue(1.0)
            self._radius_mult_spin.setDecimals(4)
            self._radius_mult_spin.setStepType(QDoubleSpinBox.StepType.AdaptiveDecimalStepType)
            self._radius_mult_spin.valueChanged.connect(lambda _: self._update_templated_radius())

            rad_temp_layout.addWidget(QLabel("Body:"))
            rad_temp_layout.addWidget(self._radius_template_combo)
            rad_temp_layout.addWidget(QLabel("Multiplier:"))
            rad_temp_layout.addWidget(self._radius_mult_spin)

            form.addRow("Radius (km):", self._radius_spin)
            form.addRow("Radius Template Source:", self._radius_template_container)
            self._radius_template_container.setVisible(False)
        else:
            form.addRow("Radius (km):", self._radius_spin)

        # Color row
        cw = QWidget()
        cl = QHBoxLayout(cw)
        cl.setContentsMargins(0, 0, 0, 0)
        self._color_btn = QPushButton()
        self._color_btn.clicked.connect(self._pick_color)
        cl.addWidget(self._color_btn)
        cl.addStretch()
        self._update_color_btn()
        form.addRow("Color:", cw)

        # Position rows
        pos = body.pos if body else np.zeros(3)
        self._px = _au_spin(pos[0])
        self._py = _au_spin(pos[1])
        self._pz = _au_spin(pos[2])

        if not self._edit_mode and self._template_bodies:
            self._pos_mode_combo = QComboBox()
            self._pos_mode_combo.addItems(["Manual", "From Template", "Average of Two"])
            self._pos_mode_combo.currentTextChanged.connect(self._on_pos_mode_changed)
            form.addRow("Position Mode:", self._pos_mode_combo)

            self._pos_template_container = QWidget()
            pos_temp_layout = QHBoxLayout(self._pos_template_container)
            pos_temp_layout.setContentsMargins(0, 0, 0, 0)
            self._pos_template_combo = QComboBox()
            for name in self._template_bodies:
                self._pos_template_combo.addItem(name)
            self._pos_template_combo.currentTextChanged.connect(lambda _: self._update_templated_pos())
            pos_temp_layout.addWidget(QLabel("Body:"))
            pos_temp_layout.addWidget(self._pos_template_combo)

            self._pos_avg_container = QWidget()
            pos_avg_layout = QHBoxLayout(self._pos_avg_container)
            pos_avg_layout.setContentsMargins(0, 0, 0, 0)
            self._pos_avg_a_combo = QComboBox()
            self._pos_avg_b_combo = QComboBox()
            for name in self._template_bodies:
                self._pos_avg_a_combo.addItem(name)
                self._pos_avg_b_combo.addItem(name)
            self._pos_avg_a_combo.setCurrentIndex(-1)
            self._pos_avg_b_combo.setCurrentIndex(-1)
            self._pos_avg_a_combo.currentTextChanged.connect(lambda _: self._update_templated_pos())
            self._pos_avg_b_combo.currentTextChanged.connect(lambda _: self._update_templated_pos())
            pos_avg_layout.addWidget(QLabel("Body A:"))
            pos_avg_layout.addWidget(self._pos_avg_a_combo)
            pos_avg_layout.addWidget(QLabel("Body B:"))
            pos_avg_layout.addWidget(self._pos_avg_b_combo)

            form.addRow("Position X (AU):", self._px)
            form.addRow("Position Y (AU):", self._py)
            form.addRow("Position Z (AU):", self._pz)
            form.addRow("Position Template:", self._pos_template_container)
            form.addRow("Position Averages:", self._pos_avg_container)
            self._pos_template_container.setVisible(False)
            self._pos_avg_container.setVisible(False)
        else:
            form.addRow("Position X (AU):", self._px)
            form.addRow("Position Y (AU):", self._py)
            form.addRow("Position Z (AU):", self._pz)

        # Velocity rows
        vel = body.vel if body else np.zeros(3)
        self._vx = _au_spin(vel[0])
        self._vy = _au_spin(vel[1])
        self._vz = _au_spin(vel[2])

        if not self._edit_mode and self._template_bodies:
            self._vel_mode_combo = QComboBox()
            self._vel_mode_combo.addItems(["Manual", "From Template", "Average of Two"])
            self._vel_mode_combo.currentTextChanged.connect(self._on_vel_mode_changed)
            form.addRow("Velocity Mode:", self._vel_mode_combo)

            self._vel_template_container = QWidget()
            vel_temp_layout = QHBoxLayout(self._vel_template_container)
            vel_temp_layout.setContentsMargins(0, 0, 0, 0)
            self._vel_template_combo = QComboBox()
            for name in self._template_bodies:
                self._vel_template_combo.addItem(name)
            self._vel_template_combo.currentTextChanged.connect(lambda _: self._update_templated_vel())
            vel_temp_layout.addWidget(QLabel("Body:"))
            vel_temp_layout.addWidget(self._vel_template_combo)

            self._vel_avg_container = QWidget()
            vel_avg_layout = QHBoxLayout(self._vel_avg_container)
            vel_avg_layout.setContentsMargins(0, 0, 0, 0)
            self._vel_avg_a_combo = QComboBox()
            self._vel_avg_b_combo = QComboBox()
            for name in self._template_bodies:
                self._vel_avg_a_combo.addItem(name)
                self._vel_avg_b_combo.addItem(name)
            self._vel_avg_a_combo.setCurrentIndex(-1)
            self._vel_avg_b_combo.setCurrentIndex(-1)
            self._vel_avg_a_combo.currentTextChanged.connect(lambda _: self._update_templated_vel())
            self._vel_avg_b_combo.currentTextChanged.connect(lambda _: self._update_templated_vel())
            vel_avg_layout.addWidget(QLabel("Body A:"))
            vel_avg_layout.addWidget(self._vel_avg_a_combo)
            vel_avg_layout.addWidget(QLabel("Body B:"))
            vel_avg_layout.addWidget(self._vel_avg_b_combo)

            form.addRow("Velocity VX (AU/day):", self._vx)
            form.addRow("Velocity VY (AU/day):", self._vy)
            form.addRow("Velocity VZ (AU/day):", self._vz)
            form.addRow("Velocity Template:", self._vel_template_container)
            form.addRow("Velocity Averages:", self._vel_avg_container)
            self._vel_template_container.setVisible(False)
            self._vel_avg_container.setVisible(False)
        else:
            form.addRow("Velocity VX (AU/day):", self._vx)
            form.addRow("Velocity VY (AU/day):", self._vy)
            form.addRow("Velocity VZ (AU/day):", self._vz)

        # OK / Cancel Buttons
        self._err = QLabel("")
        self._err.setStyleSheet("color: red;")
        form.addRow(self._err)

        self._btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._btns.accepted.connect(self.accept)
        self._btns.rejected.connect(self.reject)
        form.addRow(self._btns)

    def _update_color_btn(self) -> None:
        r, g, b = (int(c * 255) for c in self._color)
        self._color_btn.setStyleSheet(
            f"background-color: rgb({r},{g},{b}); min-width:60px; min-height:20px;"
        )

    def _pick_color(self) -> None:
        r, g, b = (int(c * 255) for c in self._color)
        qc = QColorDialog.getColor(QColor(r, g, b), self, "Pick Body Color")
        if qc.isValid():
            self._color = (qc.redF(), qc.greenF(), qc.blueF())
            self._update_color_btn()

    def _validate(self) -> None:
        name = self._name_edit.text().strip()
        err = ""
        if not name:
            err = "Name is required."
        elif not self._edit_mode and name in self._existing_names:
            err = f"'{name}' already exists."
        elif self._mass_spin.value() <= 0:
            err = "Mass must be > 0."
        elif self._radius_spin.value() <= 0:
            err = "Radius must be > 0."
        self._err.setText(err)
        self._btns.button(QDialogButtonBox.StandardButton.Ok).setEnabled(err == "")

    # ---- Mass template slots ----
    def _on_mass_mode_changed(self, text: str) -> None:
        is_manual = (text == "Manual")
        self._mass_spin.setEnabled(is_manual)
        self._mass_template_container.setVisible(not is_manual)
        if not is_manual:
            self._update_templated_mass()

    def _update_templated_mass(self) -> None:
        if not hasattr(self, "_mass_template_combo"):
            return
        t_name = self._mass_template_combo.currentText()
        if t_name in self._template_bodies:
            base_mass = self._template_bodies[t_name].mass
            mult = self._mass_mult_spin.value()
            self._mass_spin.setValue(base_mass * mult)

    # ---- Radius template slots ----
    def _on_radius_mode_changed(self, text: str) -> None:
        is_manual = (text == "Manual")
        self._radius_spin.setEnabled(is_manual)
        self._radius_template_container.setVisible(not is_manual)
        if not is_manual:
            self._update_templated_radius()

    def _update_templated_radius(self) -> None:
        if not hasattr(self, "_radius_template_combo"):
            return
        t_name = self._radius_template_combo.currentText()
        if t_name in self._template_bodies:
            base_rad = self._template_bodies[t_name].radius
            mult = self._radius_mult_spin.value()
            self._radius_spin.setValue(base_rad * mult)

    # ---- Position template slots ----
    def _on_pos_mode_changed(self, text: str) -> None:
        self._px.setEnabled(text == "Manual")
        self._py.setEnabled(text == "Manual")
        self._pz.setEnabled(text == "Manual")
        self._pos_template_container.setVisible(text == "From Template")
        self._pos_avg_container.setVisible(text == "Average of Two")
        if text != "Manual":
            self._update_templated_pos()

    def _update_templated_pos(self) -> None:
        mode = self._pos_mode_combo.currentText()
        if mode == "From Template":
            t_name = self._pos_template_combo.currentText()
            if t_name in self._template_bodies:
                body = self._template_bodies[t_name]
                self._px.setValue(float(body.pos[0]))
                self._py.setValue(float(body.pos[1]))
                self._pz.setValue(float(body.pos[2]))
        elif mode == "Average of Two":
            a_name = self._pos_avg_a_combo.currentText()
            b_name = self._pos_avg_b_combo.currentText()
            if (a_name and b_name
                    and a_name in self._template_bodies
                    and b_name in self._template_bodies):
                avg_pos = (self._template_bodies[a_name].pos + self._template_bodies[b_name].pos) / 2.0
                self._px.setValue(float(avg_pos[0]))
                self._py.setValue(float(avg_pos[1]))
                self._pz.setValue(float(avg_pos[2]))

    # ---- Velocity template slots ----
    def _on_vel_mode_changed(self, text: str) -> None:
        self._vx.setEnabled(text == "Manual")
        self._vy.setEnabled(text == "Manual")
        self._vz.setEnabled(text == "Manual")
        self._vel_template_container.setVisible(text == "From Template")
        self._vel_avg_container.setVisible(text == "Average of Two")
        if text != "Manual":
            self._update_templated_vel()

    def _update_templated_vel(self) -> None:
        mode = self._vel_mode_combo.currentText()
        if mode == "From Template":
            t_name = self._vel_template_combo.currentText()
            if t_name in self._template_bodies:
                body = self._template_bodies[t_name]
                self._vx.setValue(float(body.vel[0]))
                self._vy.setValue(float(body.vel[1]))
                self._vz.setValue(float(body.vel[2]))
        elif mode == "Average of Two":
            a_name = self._vel_avg_a_combo.currentText()
            b_name = self._vel_avg_b_combo.currentText()
            if (a_name and b_name
                    and a_name in self._template_bodies
                    and b_name in self._template_bodies):
                avg_vel = (self._template_bodies[a_name].vel + self._template_bodies[b_name].vel) / 2.0
                self._vx.setValue(float(avg_vel[0]))
                self._vy.setValue(float(avg_vel[1]))
                self._vz.setValue(float(avg_vel[2]))


def _sci_spin(min_v: float, max_v: float, value: float) -> QDoubleSpinBox:
    sb = QDoubleSpinBox()
    sb.setDecimals(3)
    sb.setMinimum(min_v)
    sb.setMaximum(max_v)
    sb.setValue(value)
    sb.setStepType(QDoubleSpinBox.StepType.AdaptiveDecimalStepType)
    return sb


def _au_spin(value: float) -> QDoubleSpinBox:
    sb = QDoubleSpinBox()
    sb.setDecimals(8)
    sb.setMinimum(-10000.0)
    sb.setMaximum(10000.0)
    sb.setValue(value)
    return sb
