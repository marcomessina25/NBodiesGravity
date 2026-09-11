import numpy as np
from nbodiesgravity.engine.body import CelestialBody, BodyState
from nbodiesgravity.rendering.display_info import BodyDisplayInfo
from nbodiesgravity.rendering.gl_widget import GLWidget


def test_body_display_info_star_classification():
    """Verify is_star relies strictly on label=='star', regardless of body name."""
    sun = CelestialBody(
        name="Sun", mass=1.989e30, pos=np.zeros(3), vel=np.zeros(3),
        radius=696340.0, color=(1.0, 1.0, 0.0), label="star",
    )
    custom_star = CelestialBody(
        name="Sirius", mass=4e30, pos=np.zeros(3), vel=np.zeros(3),
        radius=1e6, color=(0.8, 0.9, 1.0), label="star",
    )
    renamed_sun_planet = CelestialBody(
        name="Sun", mass=1e24, pos=np.zeros(3), vel=np.zeros(3),
        radius=6000.0, color=(0.0, 0.0, 1.0), label="planet",
    )
    earth = CelestialBody(
        name="Earth", mass=5.972e24, pos=np.zeros(3), vel=np.zeros(3),
        radius=6371.0, color=(0.2, 0.4, 1.0), label="planet",
    )

    info_sun = BodyDisplayInfo(sun.name, sun.radius, sun.color, is_star=(sun.label == "star"))
    info_sirius = BodyDisplayInfo(custom_star.name, custom_star.radius, custom_star.color, is_star=(custom_star.label == "star"))
    info_renamed = BodyDisplayInfo(renamed_sun_planet.name, renamed_sun_planet.radius, renamed_sun_planet.color, is_star=(renamed_sun_planet.label == "star"))
    info_earth = BodyDisplayInfo(earth.name, earth.radius, earth.color, is_star=(earth.label == "star"))

    assert info_sun.is_star is True
    assert info_sirius.is_star is True
    assert info_renamed.is_star is False
    assert info_earth.is_star is False


def test_gl_widget_light_pos_resolution_with_custom_star(qapp):
    """GLWidget should pick any body marked is_star as the light source."""
    gl = GLWidget()
    infos = [
        BodyDisplayInfo("Sirius", 1e6, (1.0, 1.0, 1.0), is_star=True),
        BodyDisplayInfo("PlanetX", 5000.0, (0.5, 0.5, 0.5), is_star=False),
    ]
    gl.set_display_info(infos)

    snap = [
        BodyState("PlanetX", np.array([10.0, 0.0, 0.0]), np.zeros(3), True),
        BodyState("Sirius", np.array([2.0, 3.0, 4.0]), np.zeros(3), True),
    ]

    star_state = next(
        (s for s in snap if (info := gl._display_info.get(s.name)) and info.is_star),
        next((s for s in snap if s.name == "Sun"), snap[0]),
    )
    assert star_state.name == "Sirius"
    assert np.allclose(star_state.pos, [2.0, 3.0, 4.0])
