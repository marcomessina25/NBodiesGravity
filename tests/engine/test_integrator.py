import numpy as np
from nbodiesgravity.engine.integrator import VelocityVerletIntegrator, G_AU_DAY


def test_single_body_no_force():
    """A lone body must travel in a straight line at constant velocity."""
    masses = np.array([1.989e30])
    pos = np.array([[0.0, 0.0, 0.0]])
    vel = np.array([[1.0, 0.0, 0.0]])
    itg = VelocityVerletIntegrator()
    new_pos, new_vel = itg.step(pos, vel, masses, dt=1.0)
    assert np.allclose(new_pos, [[1.0, 0.0, 0.0]], atol=1e-10)
    assert np.allclose(new_vel, [[1.0, 0.0, 0.0]], atol=1e-10)


def test_two_body_earth_returns_near_start_after_one_year():
    """Earth should be close to its starting position after ~365 steps of dt=1 day."""
    masses = np.array([1.989e30, 5.972e24])
    pos = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    vel = np.array([[0.0, 0.0, 0.0], [0.0, 0.017202, 0.0]])
    itg = VelocityVerletIntegrator()
    for _ in range(365):
        pos, vel = itg.step(pos, vel, masses, dt=1.0)
    assert np.linalg.norm(pos[1] - np.array([1.0, 0.0, 0.0])) < 0.05


def test_two_body_energy_conservation():
    """Total energy must drift less than 0.01% over 1000 steps of dt=1 day."""
    m_sun, m_earth = 1.989e30, 5.972e24
    masses = np.array([m_sun, m_earth])
    pos = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    vel = np.array([[0.0, 0.0, 0.0], [0.0, 0.017202, 0.0]])

    def total_energy(p, v):
        ke = 0.5 * np.sum(masses[:, np.newaxis] * v ** 2)
        r = np.linalg.norm(p[1] - p[0])
        return ke - G_AU_DAY * m_sun * m_earth / r

    itg = VelocityVerletIntegrator()
    e0 = total_energy(pos, vel)
    for _ in range(1000):
        pos, vel = itg.step(pos, vel, masses, dt=1.0)
    e1 = total_energy(pos, vel)
    assert abs((e1 - e0) / e0) < 1e-4


def test_accelerations_shape():
    """_accelerations must return (N, 3) for N bodies."""
    itg = VelocityVerletIntegrator()
    pos = np.random.rand(5, 3)
    masses = np.ones(5) * 1e24
    acc = itg._accelerations(pos, masses)
    assert acc.shape == (5, 3)
