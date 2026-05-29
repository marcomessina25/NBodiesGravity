import numpy as np
import pytest
from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.ui.body_editor_dialog import BodyEditorDialog


def test_body_editor_dialog_modes_and_templates(qapp):
    """Verify that localized templated features compute correct mass, radius, pos, and vel."""
    sun = CelestialBody(
        name="Sun", mass=2.0e30, pos=np.array([1.0, 2.0, 3.0]),
        vel=np.array([0.1, 0.2, 0.3]), radius=700000.0, color=(1.0, 0.0, 0.0)
    )
    earth = CelestialBody(
        name="Earth", mass=6.0e24, pos=np.array([3.0, 4.0, 5.0]),
        vel=np.array([0.3, 0.4, 0.5]), radius=6300.0, color=(0.0, 0.0, 1.0)
    )
    templates = [sun, earth]

    dlg = BodyEditorDialog(
        existing_names=["Mars"],
        body=None,
        template_bodies=templates,
    )

    # 1. Test Mass Mode: Template * Multiplier
    dlg._mass_mode_combo.setCurrentText("Template * Multiplier")
    dlg._mass_template_combo.setCurrentText("Sun")
    dlg._mass_mult_spin.setValue(0.5)
    # Mass spinbox should be updated to 0.5 * sun.mass = 1.0e30
    assert np.allclose(dlg._mass_spin.value(), 1.0e30)

    # 2. Test Radius Mode: Template * Multiplier
    dlg._radius_mode_combo.setCurrentText("Template * Multiplier")
    dlg._radius_template_combo.setCurrentText("Earth")
    dlg._radius_mult_spin.setValue(3.0)
    # Radius spinbox should be 3.0 * earth.radius = 18900.0
    assert np.allclose(dlg._radius_spin.value(), 18900.0)

    # 3. Test Position Mode: Average of Two
    dlg._pos_mode_combo.setCurrentText("Average of Two")
    dlg._pos_avg_a_combo.setCurrentText("Sun")
    dlg._pos_avg_b_combo.setCurrentText("Earth")
    # Position should be average of Sun [1, 2, 3] and Earth [3, 4, 5] = [2, 3, 4]
    assert np.allclose(dlg._px.value(), 2.0)
    assert np.allclose(dlg._py.value(), 3.0)
    assert np.allclose(dlg._pz.value(), 4.0)

    # 4. Test Velocity Mode: From Template
    dlg._vel_mode_combo.setCurrentText("From Template")
    dlg._vel_template_combo.setCurrentText("Earth")
    # Velocity should be Earth vel = [0.3, 0.4, 0.5]
    assert np.allclose(dlg._vx.value(), 0.3)
    assert np.allclose(dlg._vy.value(), 0.4)
    assert np.allclose(dlg._vz.value(), 0.5)

    # Retrieve output body and verify
    dlg._name_edit.setText("New Planet")
    body = dlg.result_body()
    assert body.name == "New Planet"
    assert body.mass == 1.0e30
    assert body.radius == 18900.0
    assert np.allclose(body.pos, [2.0, 3.0, 4.0])
    assert np.allclose(body.vel, [0.3, 0.4, 0.5])
