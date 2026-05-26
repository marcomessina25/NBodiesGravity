import numpy as np
from nbodiesgravity.rendering.trail_buffer import TrailBuffer, MAX_TRAIL_POINTS


def test_append_stores_relative_position():
    tb = TrailBuffer((1.0, 0.0, 0.0))
    pos = np.array([3.0, 4.0, 5.0])
    center = np.array([1.0, 2.0, 3.0])
    tb.append(pos, center)
    assert np.allclose(tb._buf[0], [2.0, 2.0, 2.0])
    assert tb._count == 1


def test_append_center_at_origin_leaves_pos_unchanged():
    tb = TrailBuffer((0.0, 1.0, 0.0))
    pos = np.array([1.5, 0.0, -2.0])
    tb.append(pos, np.zeros(3))
    assert np.allclose(tb._buf[0], [1.5, 0.0, -2.0])


def test_reset_zeroes_count_and_buffer():
    tb = TrailBuffer((0.0, 0.0, 1.0))
    tb.append(np.array([1.0, 2.0, 3.0]), np.zeros(3))
    tb.append(np.array([4.0, 5.0, 6.0]), np.zeros(3))
    tb.reset()
    assert tb._count == 0
    assert tb._head == 0
    assert np.all(tb._buf == 0.0)


def test_append_after_reset_starts_fresh():
    tb = TrailBuffer((0.0, 0.0, 1.0))
    tb.append(np.array([99.0, 0.0, 0.0]), np.zeros(3))
    tb.reset()
    tb.append(np.array([1.0, 2.0, 3.0]), np.zeros(3))
    assert tb._count == 1
    assert np.allclose(tb._buf[0], [1.0, 2.0, 3.0])


def test_ring_buffer_wraps_and_count_caps_at_max():
    tb = TrailBuffer((1.0, 1.0, 0.0))
    center = np.zeros(3)
    for i in range(MAX_TRAIL_POINTS + 3):
        tb.append(np.array([float(i), 0.0, 0.0]), center)
    assert tb._count == MAX_TRAIL_POINTS
    assert tb._head == 3
