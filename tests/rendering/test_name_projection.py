import numpy as np
import pytest
from PyQt6.QtCore import Qt
from nbodiesgravity.rendering.gl_widget import GLWidget


def test_toggle_show_names(qapp):
    """Verify set_show_names correctly updates the internal visibility flag."""
    gl = GLWidget()
    assert gl._show_names is True  # default enabled

    gl.set_show_names(False)
    assert gl._show_names is False

    gl.set_show_names(True)
    assert gl._show_names is True


def test_project_to_screen_in_front_of_camera(qapp):
    """Verify a point in front of the camera projects to correct 2D screen coordinates."""
    gl = GLWidget()
    gl.resize(800, 600)

    # Use identity for projection and view
    gl._proj = np.eye(4, dtype=np.float32)
    view = np.eye(4, dtype=np.float32)

    # In front of camera (negative Z in camera space)
    # pos_cam = [0.5, -0.5, -5.0, 1.0]
    pos_rel = np.array([0.5, -0.5, -5.0])
    res = gl.project_to_screen(pos_rel, view)
    
    assert res is not None
    screen_x, screen_y = res
    # NDC coord should be [0.5, -0.5, -5.0]
    # screen_x = (0.5 + 1.0) * 0.5 * 800 = 1.5 * 400 = 600.0
    # screen_y = (1.0 - (-0.5)) * 0.5 * 600 = 1.5 * 300 = 450.0
    assert np.allclose(screen_x, 600.0)
    assert np.allclose(screen_y, 450.0)


def test_project_to_screen_behind_camera_returns_none(qapp):
    """Verify points behind the camera are correctly ignored and return None."""
    gl = GLWidget()
    gl._proj = np.eye(4, dtype=np.float32)
    view = np.eye(4, dtype=np.float32)

    # Behind camera (positive Z in camera space)
    pos_rel = np.array([0.0, 0.0, 5.0])
    res = gl.project_to_screen(pos_rel, view)
    assert res is None


def test_project_to_screen_outside_ndc_bounds_returns_none(qapp):
    """Verify points way out of view (high NDC) are ignored and return None."""
    gl = GLWidget()
    gl._proj = np.eye(4, dtype=np.float32)
    view = np.eye(4, dtype=np.float32)

    # Way off to the side (NDC x = 3.0 > 2.0)
    pos_rel = np.array([3.0, 0.0, -1.0])
    res = gl.project_to_screen(pos_rel, view)
    assert res is None
