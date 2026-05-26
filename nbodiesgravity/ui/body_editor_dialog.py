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
        )

    def _build_ui(self, body: CelestialBody | None) -> None:
        form = QFormLayout(self)

        # ---- Template selector (Add mode only) ----
        if not self._edit_mode and self._template_bodies:
            self._template_combo = QComboBox()
            self._template_combo.addItem("Blank")
            for name in self._template_bodies:
                self._template_combo.addItem(name)
            if len(self._template_bodies) >= 2:
                self._template_combo.addItem("Average of two…")
            self._template_combo.currentTextChanged.connect(self._on_template_changed)
            form.addRow("Template:", self._template_combo)

            if len(self._template_bodies) >= 2:
                self._avg_container = QWidget()
                avg_inner = QFormLayout(self._avg_container)
                avg_inner.setContentsMargins(0, 0, 0, 0)
                self._avg_a_combo = QComboBox()
                self._avg_b_combo = QComboBox()
                for name in self._template_bodies:
                    self._avg_a_combo.addItem(name)
                    self._avg_b_combo.addItem(name)
                self._avg_a_combo.setCurrentIndex(-1)
                self._avg_b_combo.setCurrentIndex(-1)
                self._avg_a_combo.currentTextChanged.connect(self._on_avg_selection_changed)
                self._avg_b_combo.currentTextChanged.connect(self._on_avg_selection_changed)
                avg_inner.addRow("Body A:", self._avg_a_combo)
                avg_inner.addRow("Body B:", self._avg_b_combo)
                self._avg_container.setVisible(False)
                form.addRow(self._avg_container)

        # ---- Main fields ----
        self._name_edit = QLineEdit(body.name if body else "")
        self._name_edit.textChanged.connect(self._validate)
        form.addRow("Name:", self._name_edit)

        self._mass_spin = _sci_spin(1e-3, 2e30, body.mass if body else 1e22)
        self._mass_spin.valueChanged.connect(self._validate)
        form.addRow("Mass (kg):", self._mass_spin)

        self._radius_spin = _sci_spin(0.1, 1e7, body.radius if body else 1000.0)
        self._radius_spin.valueChanged.connect(self._validate)
        form.addRow("Radius (km):", self._radius_spin)

        cw = QWidget()
        cl = QHBoxLayout(cw)
        cl.setContentsMargins(0, 0, 0, 0)
        self._color_btn = QPushButton()
        self._color_btn.clicked.connect(self._pick_color)
        cl.addWidget(self._color_btn)
        cl.addStretch()
        self._update_color_btn()
        form.addRow("Color:", cw)

        pos = body.pos if body else np.zeros(3)
        self._px = _au_spin(pos[0])
        self._py = _au_spin(pos[1])
        self._pz = _au_spin(pos[2])
        form.addRow("Position X (AU):", self._px)
        form.addRow("Position Y (AU):", self._py)
        form.addRow("Position Z (AU):", self._pz)

        vel = body.vel if body else np.zeros(3)
        self._vx = _au_spin(vel[0])
        self._vy = _au_spin(vel[1])
        self._vz = _au_spin(vel[2])
        form.addRow("Velocity VX (AU/day):", self._vx)
        form.addRow("Velocity VY (AU/day):", self._vy)
        form.addRow("Velocity VZ (AU/day):", self._vz)

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

    def _on_template_changed(self, text: str) -> None:
        has_avg = hasattr(self, "_avg_container")
        if has_avg and text == "Average of two…":
            self._avg_container.setVisible(True)
            self._avg_a_combo.setCurrentIndex(-1)
            self._avg_b_combo.setCurrentIndex(-1)
            return
        if has_avg:
            self._avg_container.setVisible(False)
        if text == "Blank":
            self._clear_fields()
        elif text in self._template_bodies:
            self._fill_from_body(self._template_bodies[text])

    def _on_avg_selection_changed(self) -> None:
        a_name = self._avg_a_combo.currentText()
        b_name = self._avg_b_combo.currentText()
        if (a_name and b_name
                and a_name in self._template_bodies
                and b_name in self._template_bodies):
            self._fill_from_average(
                self._template_bodies[a_name],
                self._template_bodies[b_name],
            )

    def _clear_fields(self) -> None:
        self._name_edit.clear()
        self._mass_spin.setValue(1e22)
        self._radius_spin.setValue(1000.0)
        self._px.setValue(0.0)
        self._py.setValue(0.0)
        self._pz.setValue(0.0)
        self._vx.setValue(0.0)
        self._vy.setValue(0.0)
        self._vz.setValue(0.0)
        self._color = (1.0, 1.0, 1.0)
        self._update_color_btn()

    def _fill_from_body(self, body: CelestialBody) -> None:
        self._name_edit.clear()
        self._mass_spin.setValue(body.mass)
        self._radius_spin.setValue(body.radius)
        self._px.setValue(float(body.pos[0]))
        self._py.setValue(float(body.pos[1]))
        self._pz.setValue(float(body.pos[2]))
        self._vx.setValue(float(body.vel[0]))
        self._vy.setValue(float(body.vel[1]))
        self._vz.setValue(float(body.vel[2]))
        self._color = body.color
        self._update_color_btn()

    def _fill_from_average(self, a: CelestialBody, b: CelestialBody) -> None:
        avg_pos = (a.pos + b.pos) / 2
        avg_vel = (a.vel + b.vel) / 2
        self._name_edit.clear()
        self._mass_spin.setValue((a.mass + b.mass) / 2)
        self._radius_spin.setValue((a.radius + b.radius) / 2)
        self._px.setValue(float(avg_pos[0]))
        self._py.setValue(float(avg_pos[1]))
        self._pz.setValue(float(avg_pos[2]))
        self._vx.setValue(float(avg_vel[0]))
        self._vy.setValue(float(avg_vel[1]))
        self._vz.setValue(float(avg_vel[2]))
        self._color = (
            (a.color[0] + b.color[0]) / 2,
            (a.color[1] + b.color[1]) / 2,
            (a.color[2] + b.color[2]) / 2,
        )
        self._update_color_btn()


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
