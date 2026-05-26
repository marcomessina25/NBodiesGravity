"""Main 3D OpenGL viewport.

Renders Phong-lit spheres and coloured trails at 60 FPS.
Reads positions from SimulationThread.latest_snapshot each frame.
Mouse: left-drag = orbit, right-drag = distance adjust, scroll = zoom.
"""
from __future__ import annotations
import ctypes
import numpy as np

from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QMouseEvent, QWheelEvent

from OpenGL.GL import (
    glEnable, glClear, glClearColor, glViewport, glBlendFunc,
    glUseProgram, glUniform1i, glUniform1f, glUniform3f,
    glGetUniformLocation, glUniformMatrix4fv,
    glCreateShader, glShaderSource, glCompileShader,
    glGetShaderiv, glGetShaderInfoLog,
    glCreateProgram, glAttachShader, glLinkProgram,
    glGetProgramiv, glGetProgramInfoLog,
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT,
    GL_DEPTH_TEST, GL_BLEND, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA,
    GL_VERTEX_SHADER, GL_FRAGMENT_SHADER,
    GL_COMPILE_STATUS, GL_LINK_STATUS, GL_TRUE, GL_FALSE,
)

from nbodiesgravity.rendering.camera import Camera
from nbodiesgravity.rendering.display_info import BodyDisplayInfo
from nbodiesgravity.rendering.sphere_mesh import (
    SphereMesh, SPHERE_VERT_SRC, SPHERE_FRAG_SRC, LINE_VERT_SRC, LINE_FRAG_SRC,
)
from nbodiesgravity.rendering.trail_buffer import TrailBuffer


def _compile_shader(src: str, kind: int) -> int:
    s = glCreateShader(kind)
    glShaderSource(s, src)
    glCompileShader(s)
    if glGetShaderiv(s, GL_COMPILE_STATUS) != GL_TRUE:
        raise RuntimeError(f"Shader error:\n{glGetShaderInfoLog(s).decode()}")
    return s


def _link_program(vert_src: str, frag_src: str) -> int:
    p = glCreateProgram()
    glAttachShader(p, _compile_shader(vert_src, GL_VERTEX_SHADER))
    glAttachShader(p, _compile_shader(frag_src, GL_FRAGMENT_SHADER))
    glLinkProgram(p)
    if glGetProgramiv(p, GL_LINK_STATUS) != GL_TRUE:
        raise RuntimeError(f"Link error:\n{glGetProgramInfoLog(p).decode()}")
    return p


def _perspective(fov_deg: float, aspect: float, near: float, far: float) -> np.ndarray:
    f = 1.0 / np.tan(np.radians(fov_deg) / 2.0)
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = 2.0 * far * near / (near - far)
    m[3, 2] = -1.0
    return m


def _model_matrix(offset: np.ndarray, scale: float) -> np.ndarray:
    m = np.eye(4, dtype=np.float32)
    m[0, 0] = m[1, 1] = m[2, 2] = scale
    m[:3, 3] = offset
    return m


class GLWidget(QOpenGLWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.camera = Camera()
        self._sphere_mesh = SphereMesh()
        self._trail_buffers: dict[str, TrailBuffer] = {}
        self._display_info: dict[str, BodyDisplayInfo] = {}
        self._sphere_prog: int = 0
        self._line_prog: int = 0
        self._proj = np.eye(4, dtype=np.float32)
        self._simulation_thread = None
        self._last_mouse_pos = None
        self._last_mouse_btn = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(16)   # ~60 FPS

    def set_simulation_thread(self, thread) -> None:
        self._simulation_thread = thread

    def set_display_info(self, infos: list[BodyDisplayInfo]) -> None:
        """Register rendering metadata. Call after every system load/reset."""
        self._display_info = {info.name: info for info in infos}
        for info in infos:
            if info.name not in self._trail_buffers:
                tb = TrailBuffer(info.color)
                if self._sphere_prog:   # GL context already exists
                    tb.initialize()
                self._trail_buffers[info.name] = tb

    def clear_trails(self) -> None:
        """Reset all trail ring buffers. Call on center change or user request."""
        for tb in self._trail_buffers.values():
            tb.reset()

    # ---------------------------------------------------------------
    # QOpenGLWidget callbacks
    # ---------------------------------------------------------------

    def initializeGL(self) -> None:
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glClearColor(0.0, 0.0, 0.0, 1.0)
        self._sphere_prog = _link_program(SPHERE_VERT_SRC, SPHERE_FRAG_SRC)
        self._line_prog = _link_program(LINE_VERT_SRC, LINE_FRAG_SRC)
        self._sphere_mesh.initialize()
        for tb in self._trail_buffers.values():
            tb.initialize()

    def resizeGL(self, w: int, h: int) -> None:
        glViewport(0, 0, w, h)
        self._proj = _perspective(45.0, w / max(h, 1), 0.0001, 100000.0)

    def paintGL(self) -> None:
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        if self._simulation_thread is None:
            return
        snap = self._simulation_thread.latest_snapshot
        if not snap:
            return

        self.camera.update_center_pos(snap)
        offset = self.camera.center_pos
        view = self.camera.view_matrix()
        vp = (self._proj @ view).astype(np.float32)

        # Lazy-init trail buffers for bodies added after GL init
        for state in snap:
            if state.name not in self._trail_buffers:
                info = self._display_info.get(state.name)
                color = info.color if info else (1.0, 1.0, 1.0)
                tb = TrailBuffer(color)
                tb.initialize()
                self._trail_buffers[state.name] = tb

        # Accumulate trail positions (relative to current center)
        for state in snap:
            self._trail_buffers[state.name].append(state.pos, offset)

        # --- Trails ---
        glUseProgram(self._line_prog)
        glUniformMatrix4fv(
            glGetUniformLocation(self._line_prog, "uViewProjection"),
            1, GL_FALSE, vp.T,
        )
        # uCenterOffset zeroed: relative offset is baked into TrailBuffer at append time
        glUniform3f(glGetUniformLocation(self._line_prog, "uCenterOffset"), 0.0, 0.0, 0.0)
        glUniform1f(glGetUniformLocation(self._line_prog, "uAlpha"), 0.55)
        for state in snap:
            body = (self._simulation_thread.system.get_body(state.name)
                    if self._simulation_thread else None)
            if body and not body.show_trail:
                continue
            tb = self._trail_buffers[state.name]
            glUniform3f(glGetUniformLocation(self._line_prog, "uColor"), *tb.color)
            tb.draw()

        # --- Spheres ---
        glUseProgram(self._sphere_prog)
        glUniformMatrix4fv(
            glGetUniformLocation(self._sphere_prog, "uView"), 1, GL_FALSE, view.T)
        glUniformMatrix4fv(
            glGetUniformLocation(self._sphere_prog, "uProjection"), 1, GL_FALSE, self._proj.T)
        sun = next((s for s in snap if s.name == "Sun"), snap[0])
        glUniform3f(
            glGetUniformLocation(self._sphere_prog, "uLightPos"),
            *(sun.pos - offset).astype(np.float32),
        )
        for state in snap:
            info = self._display_info.get(state.name)
            r = info.display_radius if info else 0.02
            pos_rel = (state.pos - offset).astype(np.float32)
            model = _model_matrix(pos_rel, r)
            glUniformMatrix4fv(
                glGetUniformLocation(self._sphere_prog, "uModel"), 1, GL_FALSE, model.T)
            color = info.color if info else (1.0, 1.0, 1.0)
            glUniform3f(glGetUniformLocation(self._sphere_prog, "uColor"), *color)
            glUniform1i(
                glGetUniformLocation(self._sphere_prog, "uEmissive"),
                int(info.is_star if info else False),
            )
            self._sphere_mesh.draw()

    # ---------------------------------------------------------------
    # Mouse events
    # ---------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._last_mouse_pos = event.position()
        self._last_mouse_btn = event.button()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._last_mouse_pos is None:
            return
        dx = event.position().x() - self._last_mouse_pos.x()
        dy = event.position().y() - self._last_mouse_pos.y()
        if self._last_mouse_btn == Qt.MouseButton.LeftButton:
            self.camera.rotate(dx * 0.005, -dy * 0.005)
        elif self._last_mouse_btn == Qt.MouseButton.RightButton:
            self.camera.distance = max(
                0.001, self.camera.distance + dy * self.camera.distance * 0.005
            )
        self._last_mouse_pos = event.position()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._last_mouse_pos = None
        self._last_mouse_btn = None

    def wheelEvent(self, event: QWheelEvent) -> None:
        self.camera.zoom(0.9 if event.angleDelta().y() > 0 else 1.1)
