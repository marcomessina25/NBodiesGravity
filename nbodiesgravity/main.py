"""N-Body Gravity entry point (Milestone 2 — rendering smoke test).

Run:
    conda run -n nbodiesgravity python nbodiesgravity/main.py
"""
from __future__ import annotations
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QSurfaceFormat
from nbodiesgravity.data.loader import load_default_system
from nbodiesgravity.engine.simulation_thread import SimulationThread
from nbodiesgravity.rendering.display_info import BodyDisplayInfo
from nbodiesgravity.rendering.gl_widget import GLWidget


def _request_opengl_33() -> None:
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setDepthBufferSize(24)
    QSurfaceFormat.setDefaultFormat(fmt)


def main() -> None:
    _request_opengl_33()
    app = QApplication(sys.argv)
    system = load_default_system()
    display_infos = [
        BodyDisplayInfo(b.name, b.radius, b.color, is_star=(b.name == "Sun"))
        for b in system.bodies
    ]
    sim = SimulationThread(system)
    gl = GLWidget()
    gl.set_display_info(display_infos)
    gl.set_simulation_thread(sim)
    gl.resize(1200, 900)
    gl.setWindowTitle("N-Body Gravity — Milestone 2 Rendering")
    gl.show()
    sim.start()
    sim.set_timescale(10.0)
    sim.resume()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
