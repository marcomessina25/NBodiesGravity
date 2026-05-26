"""Shared UV-sphere mesh and GLSL shader sources.

One SphereMesh instance is shared by all bodies — each body sets its own
model matrix uniform (translate + scale) before calling draw().

SPHERE_VERT / SPHERE_FRAG : Phong-lit sphere. Sun uses uEmissive=true.
LINE_VERT / LINE_FRAG      : Unlit lines for trails.
"""
from __future__ import annotations
import ctypes
import numpy as np
from OpenGL.GL import (
    glGenVertexArrays, glGenBuffers, glBindVertexArray, glBindBuffer,
    glBufferData, glVertexAttribPointer, glEnableVertexAttribArray,
    glDrawElements,
    GL_ARRAY_BUFFER, GL_ELEMENT_ARRAY_BUFFER,
    GL_FLOAT, GL_FALSE, GL_TRIANGLES, GL_UNSIGNED_INT, GL_STATIC_DRAW,
)

# ---------------------------------------------------------------------------
# GLSL sources
# ---------------------------------------------------------------------------

SPHERE_VERT_SRC: str = """
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;
uniform mat4 uModel;
uniform mat4 uView;
uniform mat4 uProjection;
out vec3 FragPos;
out vec3 Normal;
void main() {
    vec4 worldPos = uModel * vec4(aPos, 1.0);
    FragPos = worldPos.xyz;
    Normal = mat3(transpose(inverse(uModel))) * aNormal;
    gl_Position = uProjection * uView * worldPos;
}
"""

SPHERE_FRAG_SRC: str = """
#version 330 core
in vec3 FragPos;
in vec3 Normal;
uniform vec3  uColor;
uniform vec3  uLightPos;
uniform bool  uEmissive;
out vec4 FragColor;
void main() {
    if (uEmissive) { FragColor = vec4(uColor, 1.0); return; }
    vec3 norm     = normalize(Normal);
    vec3 lightDir = normalize(uLightPos - FragPos);
    float diff    = max(dot(norm, lightDir), 0.15);
    FragColor     = vec4(diff * uColor, 1.0);
}
"""

LINE_VERT_SRC: str = """
#version 330 core
layout(location = 0) in vec3 aPos;
uniform mat4 uViewProjection;
uniform vec3 uCenterOffset;
void main() {
    gl_Position = uViewProjection * vec4(aPos - uCenterOffset, 1.0);
}
"""

LINE_FRAG_SRC: str = """
#version 330 core
uniform vec3  uColor;
uniform float uAlpha;
out vec4 FragColor;
void main() { FragColor = vec4(uColor, uAlpha); }
"""

# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

def _generate_uv_sphere(
    stacks: int = 24, slices: int = 24
) -> tuple[np.ndarray, np.ndarray]:
    """Return (vertices float32 (N,6), indices uint32) for a unit sphere."""
    verts: list[float] = []
    for i in range(stacks + 1):
        phi = np.pi * i / stacks
        for j in range(slices + 1):
            theta = 2.0 * np.pi * j / slices
            x = float(np.sin(phi) * np.cos(theta))
            y = float(np.cos(phi))
            z = float(np.sin(phi) * np.sin(theta))
            verts += [x, y, z, x, y, z]   # pos == normal for unit sphere
    idxs: list[int] = []
    for i in range(stacks):
        for j in range(slices):
            a = i * (slices + 1) + j
            b = a + slices + 1
            idxs += [a, b, a + 1, b, b + 1, a + 1]
    return np.array(verts, dtype=np.float32), np.array(idxs, dtype=np.uint32)


# ---------------------------------------------------------------------------
# SphereMesh
# ---------------------------------------------------------------------------

class SphereMesh:
    """Single VBO shared by every body. Scale via model-matrix uniform."""

    def __init__(self) -> None:
        self._vao: int | None = None
        self._index_count: int = 0

    def initialize(self) -> None:
        """Upload to GPU. Must be called from the GL thread after context creation."""
        vertices, indices = _generate_uv_sphere()
        self._index_count = len(indices)
        self._vao = glGenVertexArrays(1)
        vbo = glGenBuffers(1)
        ebo = glGenBuffers(1)
        glBindVertexArray(self._vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)
        stride = 6 * 4
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(12))
        glEnableVertexAttribArray(1)
        glBindVertexArray(0)

    def draw(self) -> None:
        glBindVertexArray(self._vao)
        glDrawElements(GL_TRIANGLES, self._index_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)
