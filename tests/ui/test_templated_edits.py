import numpy as np
import pytest
from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.ui.body_editor_dialog import BodyEditorDialog


def test_body_editor_dialog_templated_edits(qapp):
    """Verify that templated features are fully functional when editing an existing body."""
    sun = CelestialBody(
        name="Sun", mass=2.0e30, pos=np.array([1.0, 2.0, 3.0]),
        vel=np.array([0.1, 0.2, 0.3]), radius=700000.0, color=(1.0, 0.0, 0.0)
    )
    earth = CelestialBody(
        name="Earth", mass=6.0e24, pos=np.array([3.0, 4.0, 5.0]),
        vel=np.array([0.3, 0.4, 0.5]), radius=6300.0, color=(0.0, 0.0, 1.0)
    )

    # We are editing Earth, and Sun is the template
    dlg = BodyEditorDialog(
        existing_names=["Sun"],
        body=earth,
        template_bodies=[sun],
    )

    # Check that it's in edit mode and fields are prefilled
    assert dlg._edit_mode is True
    assert dlg._name_edit.text() == "Earth"
    assert np.allclose(dlg._mass_spin.value(), 6.0e24)
    assert np.allclose(dlg._radius_spin.value(), 6300.0)

    # 1. Test Mass Mode from template
    dlg._mass_mode_combo.setCurrentText("Template * Multiplier")
    dlg._mass_template_combo.setCurrentText("Sun")
    dlg._mass_mult_spin.setValue(0.5)
    # Mass spinbox should be updated to 0.5 * sun.mass = 1.0e30
    assert np.allclose(dlg._mass_spin.value(), 1.0e30)

    # 2. Test Radius Mode from template
    dlg._radius_mode_combo.setCurrentText("Template * Multiplier")
    dlg._radius_template_combo.setCurrentText("Sun")
    dlg._radius_mult_spin.setValue(0.01)
    # Radius spinbox should be 0.01 * sun.radius = 7000.0
    assert np.allclose(dlg._radius_spin.value(), 7000.0)

    # 3. Test Position Mode: From Template
    dlg._pos_mode_combo.setCurrentText("From Template")
    dlg._pos_template_combo.setCurrentText("Sun")
    assert np.allclose(dlg._px.value(), 1.0)
    assert np.allclose(dlg._py.value(), 2.0)
    assert np.allclose(dlg._pz.value(), 3.0)

    # 4. Test Velocity Mode: From Template
    dlg._vel_mode_combo.setCurrentText("From Template")
    dlg._vel_template_combo.setCurrentText("Sun")
    assert np.allclose(dlg._vx.value(), 0.1)
    assert np.allclose(dlg._vy.value(), 0.2)
    assert np.allclose(dlg._vz.value(), 0.3)

    # Retrieve output body and verify
    body = dlg.result_body()
    assert body.name == "Earth"
    assert body.mass == 1.0e30
    assert body.radius == 7000.0
    assert np.allclose(body.pos, [1.0, 2.0, 3.0])
    assert np.allclose(body.vel, [0.1, 0.2, 0.3])


def test_body_editor_dialog_position_overlap_validation(qapp):
    """Verify that entering coordinates matching an existing body triggers validation and blocks save."""
    from PyQt6.QtWidgets import QDialogButtonBox

    sun = CelestialBody(
        name="Sun", mass=2.0e30, pos=np.array([1.0, 2.0, 3.0]),
        vel=np.array([0.1, 0.2, 0.3]), radius=700000.0, color=(1.0, 0.0, 0.0)
    )
    earth = CelestialBody(
        name="Earth", mass=6.0e24, pos=np.array([3.0, 4.0, 5.0]),
        vel=np.array([0.3, 0.4, 0.5]), radius=6300.0, color=(0.0, 0.0, 1.0)
    )

    # 1. Add mode: try to set coordinates to same as Sun
    dlg = BodyEditorDialog(
        existing_names=["Sun", "Earth"],
        body=None,
        template_bodies=[sun, earth],
    )

    # Initially validation error is "Name is required." because name is empty
    assert dlg._err.text() == "Name is required."
    assert dlg._btns.button(QDialogButtonBox.StandardButton.Ok).isEnabled() is False

    # Set name to clear that error
    dlg._name_edit.setText("Mars")
    assert dlg._err.text() == ""
    assert dlg._btns.button(QDialogButtonBox.StandardButton.Ok).isEnabled() is True

    # Change position to match Sun (1, 2, 3)
    dlg._px.setValue(1.0)
    dlg._py.setValue(2.0)
    dlg._pz.setValue(3.0)

    # This should trigger position overlap validation error
    assert "overlaps with" in dlg._err.text()
    assert dlg._btns.button(QDialogButtonBox.StandardButton.Ok).isEnabled() is False

    # 2. Edit mode: editing Earth, changing position to match Sun should be blocked, but matching its own original position should be allowed.
    dlg_edit = BodyEditorDialog(
        existing_names=["Sun"],
        body=earth,
        template_bodies=[sun],
    )

    assert dlg_edit._err.text() == ""
    assert dlg_edit._btns.button(QDialogButtonBox.StandardButton.Ok).isEnabled() is True

    # Change position to match Sun (1, 2, 3)
    dlg_edit._px.setValue(1.0)
    dlg_edit._py.setValue(2.0)
    dlg_edit._pz.setValue(3.0)

    assert "overlaps with" in dlg_edit._err.text()
    assert dlg_edit._btns.button(QDialogButtonBox.StandardButton.Ok).isEnabled() is False

