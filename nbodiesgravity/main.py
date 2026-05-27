"""N-Body Gravity Simulation — application entry point.

Run:
    conda run -n nbodiesgravity python nbodiesgravity/main.py
"""
from __future__ import annotations
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QSurfaceFormat
from nbodiesgravity.ui.main_window import MainWindow


def _request_opengl_33() -> None:
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setDepthBufferSize(24)
    QSurfaceFormat.setDefaultFormat(fmt)


def main() -> None:
    _request_opengl_33()
    app = QApplication(sys.argv)
    app.setApplicationName("NBodiesGravity")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
