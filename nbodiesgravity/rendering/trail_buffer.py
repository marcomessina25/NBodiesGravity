"""Per-body trail rendered as an OpenGL GL_LINE_STRIP.

Ring buffer of the last MAX_TRAIL_POINTS positions.  History accumulates
even when show_trail is False — toggling trails back on shows the full
history immediately without waiting for re-fill.
"""
from __future__ import annotations
import ctypes
import numpy as np
from OpenGL.GL import (
    glGenVertexArrays, glGenBuffers, glBindVertexArray, glBindBuffer,
    glBufferData, glBufferSubData, glVertexAttribPointer,
    glEnableVertexAttribArray, glDrawArrays,
    GL_ARRAY_BUFFER, GL_FLOAT, GL_FALSE, GL_DYNAMIC_DRAW, GL_LINE_STRIP,
)

MAX_TRAIL_POINTS: int = 2000


class TrailBuffer:
    def __init__(self, color: tuple[float, float, float]) -> None:
        self.color = color
        self._buf = np.zeros((MAX_TRAIL_POINTS, 3), dtype=np.float32)
        self._head: int = 0    # next write index
        self._count: int = 0   # valid points so far
        self._dirty: bool = False
        self._vao: int | None = None
        self._vbo: int | None = None

    def initialize(self) -> None:
        """Allocate GPU buffer. Must be called from the GL thread."""
        self._vao = glGenVertexArrays(1)
        self._vbo = glGenBuffers(1)
        glBindVertexArray(self._vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
        glBufferData(
            GL_ARRAY_BUFFER,
            MAX_TRAIL_POINTS * 3 * 4,
            None,
            GL_DYNAMIC_DRAW,
        )
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 12, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glBindVertexArray(0)

    def append(self, pos: np.ndarray, center_pos: np.ndarray) -> None:
        """Add pos relative to center_pos to the ring buffer. Render-thread only."""
        self._buf[self._head] = (pos - center_pos).astype(np.float32)
        self._head = (self._head + 1) % MAX_TRAIL_POINTS
        if self._count < MAX_TRAIL_POINTS:
            self._count += 1
        self._dirty = True

    def reset(self) -> None:
        """Clear all trail history. Call on center change or user request."""
        self._buf[:] = 0.0
        self._head = 0
        self._count = 0
        self._dirty = True

    def draw(self) -> None:
        """Upload if dirty and draw. GL thread only."""
        if self._vao is None:
            return
        if self._count < 2:
            return
        if self._dirty:
            if self._count < MAX_TRAIL_POINTS:
                ordered = self._buf[: self._count]
            else:
                ordered = np.roll(self._buf, -self._head, axis=0)
            glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
            glBufferSubData(GL_ARRAY_BUFFER, 0, ordered.nbytes, ordered)
            self._dirty = False
        glBindVertexArray(self._vao)
        glDrawArrays(GL_LINE_STRIP, 0, self._count)
        glBindVertexArray(0)
