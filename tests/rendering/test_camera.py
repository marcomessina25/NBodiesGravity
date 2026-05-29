import numpy as np
from nbodiesgravity.rendering.camera import Camera
from nbodiesgravity.engine.body import BodyState


def test_camera_initialization():
    cam = Camera()
    assert np.allclose(cam.panning_offset, 0.0)
    assert cam.center_name == "Sun"
    assert np.allclose(cam.center_pos, 0.0)


def test_camera_set_center():
    cam = Camera()
    cam.panning_offset = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    cam.set_center("Earth")
    assert cam.center_name == "Earth"
    assert np.allclose(cam.panning_offset, 0.0)


def test_camera_pan():
    cam = Camera()
    # Starting at some azimuth/elevation
    cam.azimuth = 0.0
    cam.elevation = 0.0
    cam.distance = 10.0
    
    # Initial offset
    assert np.allclose(cam.panning_offset, 0.0)
    
    # Pan camera
    cam.pan(10.0, 5.0)
    
    # We should have modified panning_offset
    assert not np.allclose(cam.panning_offset, 0.0)


def test_camera_focus_on_body():
    cam = Camera()
    cam.set_center("Sun")
    cam.center_pos = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    
    snapshot = [
        BodyState(name="Sun", pos=np.array([1.0, 2.0, 3.0]), vel=np.zeros(3), active=True),
        BodyState(name="Earth", pos=np.array([5.0, 7.0, 9.0]), vel=np.zeros(3), active=True),
    ]
    
    cam.focus_on_body("Earth", snapshot)
    
    # panning_offset should be the vector from Sun (center) to Earth
    expected_offset = np.array([4.0, 5.0, 6.0], dtype=np.float32)
    assert np.allclose(cam.panning_offset, expected_offset)
    assert cam.center_name == "Sun"  # should not change the reference system center
