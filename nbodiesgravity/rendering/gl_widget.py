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
from PyQt6.QtGui import QMouseEvent, QWheelEvent, QPainter, QColor, QFont

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
        self._timer.start(8)    # ~120 FPS
        self._show_names = True

    def set_simulation_thread(self, thread) -> None:
        self._simulation_thread = thread

    def set_display_info(self, infos: list[BodyDisplayInfo]) -> None:
        """Register rendering metadata. Call after every system load/reset."""
        self._display_info = {info.name: info for info in infos}
        # Keep only trail buffers of active display bodies to avoid stale memory
        active_names = {info.name for info in infos}
        self._trail_buffers = {name: tb for name, tb in self._trail_buffers.items() if name in active_names}
        for info in infos:
            if info.name not in self._trail_buffers:
                # GPU initialization is deferred to paintGL where the GL
                # context is guaranteed current.  Do NOT call tb.initialize()
                # here — this method may be called from outside paintGL.
                self._trail_buffers[info.name] = TrailBuffer(info.color)

    def clear_trails(self) -> None:
        """Reset all trail ring buffers. Call on center change or user request."""
        for tb in self._trail_buffers.values():
            tb.reset()

    def clear_trail_for(self, name: str) -> None:
        """Reset the trail ring-buffer for a single named body.

        Call when a body is deactivated so stale trail segments do not
        persist across an active/inactive transition.
        """
        tb = self._trail_buffers.get(name)
        if tb is not None:
            tb.reset()

    def set_show_names(self, show: bool) -> None:
        """Toggle displaying the names of the bodies."""
        self._show_names = show
        self.update()

    def project_to_screen(self, pos_rel: np.ndarray, view: np.ndarray) -> tuple[float, float] | None:
        """Project a 3D coordinate (relative to center) to 2D screen pixels."""
        pos_4d = np.array([pos_rel[0], pos_rel[1], pos_rel[2], 1.0], dtype=np.float32)
        pos_cam = view @ pos_4d
        
        # Check if behind camera
        if pos_cam[2] >= 0:
            return None
            
        pos_clip = self._proj @ pos_cam
        if pos_clip[3] <= 0:
            return None
            
        pos_ndc = pos_clip[:3] / pos_clip[3]
        
        # Check reasonable NDC bounds
        if not (-2.0 <= pos_ndc[0] <= 2.0 and -2.0 <= pos_ndc[1] <= 2.0):
            return None
            
        w = self.width()
        h = self.height()
        screen_x = (pos_ndc[0] + 1.0) * 0.5 * w
        screen_y = (1.0 - pos_ndc[1]) * 0.5 * h
        return screen_x, screen_y

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

        # Lazy-init trail buffers for bodies added after GL init.
        # Also catches buffers created by set_display_info (called outside
        # paintGL where the GL context was not current) whose VAO is still None.
        for state in snap:
            tb = self._trail_buffers.get(state.name)
            if tb is None:
                info = self._display_info.get(state.name)
                color = info.color if info else (1.0, 1.0, 1.0)
                tb = TrailBuffer(color)
                self._trail_buffers[state.name] = tb
            if tb._vao is None:
                tb.initialize()

        # Accumulate trail positions (relative to current center)
        for state in snap:
            if not state.active:
                continue
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
            if not state.active:
                continue
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
            if not state.active:
                continue
            info = self._display_info.get(state.name)
            # Physical log-scaled base, floored to 0.8 % of camera distance so
            # bodies stay visible when zoomed out to the full solar-system view.
            phys_r = info.display_radius if info else 0.002
            r = max(phys_r, self.camera.distance * 0.002)
            if state.name in {"Moon", "Io", "Europa", "Ganymede", "Callisto", "Titan", "Triton"}:
                r /= 10.0
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

    def paintEvent(self, event) -> None:
        # 1. Let OpenGL render the scene first
        super().paintEvent(event)
        
        # 2. Draw 2D overlays (body names)
        if not self._show_names:
            return
            
        snap = self._simulation_thread.latest_snapshot if self._simulation_thread else None
        if not snap:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Premium sans-serif font
        font = QFont("Segoe UI", 9)
        painter.setFont(font)
        
        offset = self.camera.center_pos
        view = self.camera.view_matrix()
        
        for state in snap:
            if not state.active:
                continue
                
            info = self._display_info.get(state.name)
            pos_rel = state.pos - offset
            
            screen_pos = self.project_to_screen(pos_rel, view)
            if screen_pos is None:
                continue
                
            x, y = screen_pos
            
            # Determine spacing offset based on dynamic sphere size on screen
            phys_r = info.display_radius if info else 0.002
            r = max(phys_r, self.camera.distance * 0.002)
            if state.name in {"Moon", "Io", "Europa", "Ganymede", "Callisto", "Titan", "Triton"}:
                r /= 10.0
            
            # Approximate screen-space radius using projection geometry
            # fov_factor = 2.0 * distance * tan(fov / 2)
            fov_factor = 2.0 * self.camera.distance * 0.41421356
            screen_r = (r / fov_factor) * self.height() if fov_factor > 0 else 10
            screen_r = max(6.0, min(100.0, screen_r))
            
            text_x = x + screen_r + 6
            text_y = y + 4
            
            # Draw a subtle drop shadow for perfect readability on bright/dark backgrounds
            painter.setPen(QColor(0, 0, 0, 110))
            painter.drawText(int(text_x + 1), int(text_y + 1), state.name)
            
            # Premium tint: blend 75% white with 25% of the body's actual color at 180 opacity
            color = info.color if info else (1.0, 1.0, 1.0)
            r_c = int((0.75 * 1.0 + 0.25 * color[0]) * 255)
            g_c = int((0.75 * 1.0 + 0.25 * color[1]) * 255)
            b_c = int((0.75 * 1.0 + 0.25 * color[2]) * 255)
            
            painter.setPen(QColor(r_c, g_c, b_c, 180))
            painter.drawText(int(text_x), int(text_y), state.name)
            
        painter.end()

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
            self.camera.pan(dx, dy)
        self._last_mouse_pos = event.position()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._last_mouse_pos = None
        self._last_mouse_btn = None

    def wheelEvent(self, event: QWheelEvent) -> None:
        self.camera.zoom(0.9 if event.angleDelta().y() > 0 else 1.1)
