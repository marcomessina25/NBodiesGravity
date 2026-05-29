# Add-Bodies Feature Set — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-body active/inactive toggle that fully excludes bodies from the physics integrator, bulk enable/disable buttons for bodies and trails, and Haumea + Makemake to the J2000 snapshot.

**Architecture:** `active: bool` lives on `CelestialBody` and is carried through `BodyState` snapshots. `SolarSystem.step()` filters to active bodies only; inactive bodies freeze in place. `GLWidget.paintGL()` skips inactive bodies in both trail accumulation and sphere rendering. `BodyListPanel` gains a second per-row checkbox and four bulk-action buttons above the list. `MainWindow` wires three new signals and two new slots.

**Tech Stack:** Python 3.12, PyQt6, PyOpenGL, NumPy — no new dependencies.

---

## File change map

| File | Change type | What changes |
|---|---|---|
| `nbodiesgravity/engine/body.py` | Modify | Add `active: bool = True` to `CelestialBody`; add `active: bool = True` to `BodyState`; propagate in `snapshot()` |
| `nbodiesgravity/engine/system.py` | Modify | Filter active bodies in `step()` |
| `nbodiesgravity/rendering/gl_widget.py` | Modify | Skip inactive states in trail + sphere loops; add `clear_trail_for(name)` |
| `nbodiesgravity/ui/body_list_panel.py` | Modify | Add Active checkbox per row; add four bulk-action buttons; add three new signals |
| `nbodiesgravity/ui/main_window.py` | Modify | Wire three new signals; add `_on_body_active_toggled`, `_on_all_bodies_set`, `_on_all_trails_set`; update progress bar max to 22; refactor `_toggle_all_trails` |
| `scripts/fetch_j2000.py` | Modify | Add Haumea and Makemake to `BODIES` list |
| `nbodiesgravity/data/snapshots/j2000.json` | Regenerate | Re-run fetch script; 20 → 22 bodies |
| `tests/engine/test_body.py` | Modify | Add 2 new tests for `active` field |
| `tests/engine/test_system.py` | Modify | Add 3 new tests for active filtering in `step()` |
| `tests/rendering/test_trail_buffer.py` | Modify | Add 1 test for multi-buffer isolation |
| `tests/data/test_loader.py` | Modify | Update `test_load_default_has_20_bodies` → 22 |

---

## Task 1: `engine/body.py` — `active` field on `CelestialBody` and `BodyState`

**Files:**
- Modify: `nbodiesgravity/engine/body.py`
- Test: `tests/engine/test_body.py`

- [ ] **Step 1: Write the failing tests**

Open `tests/engine/test_body.py` and append these two tests:

```python
def test_celestial_body_active_default():
    body = CelestialBody(
        name="Test", mass=1e20, pos=np.zeros(3), vel=np.zeros(3),
        radius=100.0, color=(1.0, 1.0, 1.0),
    )
    assert body.active is True


def test_snapshot_carries_active_flag():
    body = CelestialBody(
        name="Test", mass=1e20, pos=np.zeros(3), vel=np.zeros(3),
        radius=100.0, color=(1.0, 1.0, 1.0),
    )
    body.active = False
    snap = body.snapshot()
    assert snap.active is False

    body.active = True
    snap2 = body.snapshot()
    assert snap2.active is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
conda run -n nbodiesgravity pytest tests/engine/test_body.py::test_celestial_body_active_default tests/engine/test_body.py::test_snapshot_carries_active_flag -v
```

Expected: both FAIL — `CelestialBody` has no `active` attribute and `BodyState` has no `active` field.

- [ ] **Step 3: Implement — update `body.py`**

Replace the entire contents of `nbodiesgravity/engine/body.py` with:

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import NamedTuple
import numpy as np


class BodyState(NamedTuple):
    """Thread-safe snapshot of a body's kinematic state.

    Use NamedTuple so the object is immutable at the Python level.
    Array *contents* can still be mutated, so snapshot() copies them.
    """
    name: str
    pos: np.ndarray   # AU, shape (3,)
    vel: np.ndarray   # AU/day, shape (3,)
    active: bool = True   # False = excluded from integrator, invisible in render


@dataclass
class CelestialBody:
    """A gravitationally interacting body.

    Positions and velocities are always stored in the Solar System
    Barycenter (SSB) frame, in units of AU and AU/day.
    """
    name: str
    mass: float                         # kg
    pos: np.ndarray                     # AU, shape (3,)
    vel: np.ndarray                     # AU/day, shape (3,)
    radius: float                       # km — for rendering only
    color: tuple[float, float, float]   # RGB 0–1
    show_trail: bool = True
    active: bool = True                 # False = excluded from integrator

    def snapshot(self) -> BodyState:
        """Return a thread-safe copy of kinematic state."""
        return BodyState(
            name=self.name,
            pos=self.pos.copy(),
            vel=self.vel.copy(),
            active=self.active,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
conda run -n nbodiesgravity pytest tests/engine/test_body.py -v
```

Expected: all 6 tests PASS (4 pre-existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add nbodiesgravity/engine/body.py tests/engine/test_body.py
git commit -m "feat: add active flag to CelestialBody and BodyState"
```

---

## Task 2: `engine/system.py` — filter active bodies in `step()`

**Files:**
- Modify: `nbodiesgravity/engine/system.py`
- Test: `tests/engine/test_system.py`

- [ ] **Step 1: Write the failing tests**

Open `tests/engine/test_system.py` and append these three tests (the helper `_earth` and `_sun` are already defined at the top of that file):

```python
def test_inactive_body_not_integrated():
    sun = _sun()
    earth = _earth()
    earth.active = False
    frozen_pos = earth.pos.copy()   # save BEFORE step

    system = SolarSystem([sun, earth])
    system.step(1.0)

    # Earth is inactive — its position must not change at all
    assert np.allclose(system.bodies[1].pos, frozen_pos)


def test_all_inactive_step_is_noop():
    sun = _sun()
    earth = _earth()
    sun.active = False
    earth.active = False
    frozen_sun   = sun.pos.copy()
    frozen_earth = earth.pos.copy()

    system = SolarSystem([sun, earth])
    system.step(1.0)   # must not raise

    assert np.allclose(system.bodies[0].pos, frozen_sun)
    assert np.allclose(system.bodies[1].pos, frozen_earth)


def test_reactivate_body_resumes_integration():
    sun = _sun()
    earth = _earth()
    earth.active = False

    system = SolarSystem([sun, earth])
    for _ in range(5):
        system.step(1.0)

    frozen_pos = system.bodies[1].pos.copy()   # save BEFORE reactivation

    # Reactivate — Sun is still at near-origin, Earth at ~1 AU.
    # Gravity from Sun will pull Earth; one step is sufficient to detect movement.
    system.bodies[1].active = True
    system.step(1.0)

    assert not np.allclose(system.bodies[1].pos, frozen_pos)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
conda run -n nbodiesgravity pytest tests/engine/test_system.py::test_inactive_body_not_integrated tests/engine/test_system.py::test_all_inactive_step_is_noop tests/engine/test_system.py::test_reactivate_body_resumes_integration -v
```

Expected: all three FAIL — `step()` currently integrates all bodies regardless of `active`.

- [ ] **Step 3: Implement — update `system.py`**

Replace `step()` in `nbodiesgravity/engine/system.py`. The full updated method (the rest of the file is unchanged):

```python
def step(self, dt: float) -> None:
    """Advance all *active* bodies by dt days using Velocity Verlet.

    Inactive bodies (body.active is False) are skipped entirely —
    their pos/vel remain frozen at their last integrated values.
    """
    active = [b for b in self._bodies if b.active]
    if not active:
        return
    positions  = np.array([b.pos for b in active])
    velocities = np.array([b.vel for b in active])
    masses     = np.array([b.mass for b in active])
    new_pos, new_vel = self._integrator.step(positions, velocities, masses, dt)
    for i, body in enumerate(active):
        body.pos = new_pos[i]
        body.vel = new_vel[i]
```

- [ ] **Step 4: Run all engine tests to verify they pass**

```bash
conda run -n nbodiesgravity pytest tests/engine/ -v
```

Expected: all tests PASS (existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add nbodiesgravity/engine/system.py tests/engine/test_system.py
git commit -m "feat: exclude inactive bodies from SolarSystem.step()"
```

---

## Task 3: `rendering/gl_widget.py` — skip inactive bodies + `clear_trail_for()`

**Files:**
- Modify: `nbodiesgravity/rendering/gl_widget.py`
- Test: `tests/rendering/test_trail_buffer.py`

- [ ] **Step 1: Write the failing test**

Open `tests/rendering/test_trail_buffer.py` and append:

```python
def test_reset_only_affects_target_buffer():
    """Resetting one TrailBuffer must not disturb another.

    This validates the isolation behaviour that GLWidget.clear_trail_for()
    relies on — it calls tb.reset() on exactly one buffer.
    """
    tb1 = TrailBuffer((1.0, 0.0, 0.0))
    tb2 = TrailBuffer((0.0, 1.0, 0.0))
    tb1.append(np.array([1.0, 2.0, 3.0]), np.zeros(3))
    tb2.append(np.array([4.0, 5.0, 6.0]), np.zeros(3))

    tb1.reset()

    assert tb1._count == 0
    assert tb2._count == 1   # tb2 must be unaffected
    assert np.allclose(tb2._buf[0], [4.0, 5.0, 6.0])
```

- [ ] **Step 2: Run test to verify it passes immediately**

```bash
conda run -n nbodiesgravity pytest tests/rendering/test_trail_buffer.py::test_reset_only_affects_target_buffer -v
```

Expected: PASS — `TrailBuffer.reset()` already works correctly in isolation. This test codifies the guarantee.

- [ ] **Step 3: Implement — update `gl_widget.py`**

Make three changes to `nbodiesgravity/rendering/gl_widget.py`:

**Change 1** — add `clear_trail_for()` method after `clear_trails()` (around line 107):

```python
def clear_trail_for(self, name: str) -> None:
    """Reset the trail ring-buffer for a single named body."""
    tb = self._trail_buffers.get(name)
    if tb is not None:
        tb.reset()
```

**Change 2** — in `paintGL()`, the trail-draw loop (around line 167). Add an `active` guard:

```python
        # --- Trails ---
        glUseProgram(self._line_prog)
        glUniformMatrix4fv(
            glGetUniformLocation(self._line_prog, "uViewProjection"),
            1, GL_FALSE, vp.T,
        )
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
```

**Change 3** — in `paintGL()`, the trail-accumulation loop (around line 155). Add an `active` guard:

```python
        # Accumulate trail positions (relative to current center)
        for state in snap:
            if not state.active:
                continue
            self._trail_buffers[state.name].append(state.pos, offset)
```

**Change 4** — in `paintGL()`, the sphere-draw loop (around line 187). Add an `active` guard at the top of the loop:

```python
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
            phys_r = info.display_radius if info else 0.002
            r = max(phys_r, self.camera.distance * 0.008)
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
```

- [ ] **Step 4: Run full test suite**

```bash
conda run -n nbodiesgravity pytest tests/ -v
```

Expected: all tests PASS (37 existing + 6 new = 43 total).

- [ ] **Step 5: Commit**

```bash
git add nbodiesgravity/rendering/gl_widget.py tests/rendering/test_trail_buffer.py
git commit -m "feat: skip inactive bodies in GLWidget; add clear_trail_for()"
```

---

## Task 4: `ui/body_list_panel.py` — Active checkbox + bulk buttons

**Files:**
- Modify: `nbodiesgravity/ui/body_list_panel.py`

No automated tests — Qt widget UI is verified manually. The signals emitted by the panel will be tested through integration in Task 5.

- [ ] **Step 1: Replace `body_list_panel.py` with the new implementation**

Write the full new contents of `nbodiesgravity/ui/body_list_panel.py`:

```python
"""Side panel: scrollable body list with colour dot, active toggle, and trail toggle per row."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QCheckBox, QLabel, QPushButton,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap

from nbodiesgravity.engine.body import CelestialBody


class BodyListPanel(QWidget):
    body_selected       = pyqtSignal(str)        # single-click
    body_edit_requested = pyqtSignal(str)        # double-click
    trail_toggled       = pyqtSignal(str, bool)  # (name, enabled)
    body_active_toggled = pyqtSignal(str, bool)  # (name, active)
    all_bodies_set      = pyqtSignal(bool)       # True = enable all, False = disable all
    all_trails_set      = pyqtSignal(bool)       # True = enable all, False = disable all

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Bodies bulk-action row
        layout.addWidget(QLabel("Bodies"))
        body_btns = QHBoxLayout()
        btn_bodies_on  = QPushButton("Enable All")
        btn_bodies_off = QPushButton("Disable All")
        btn_bodies_on.setFixedHeight(22)
        btn_bodies_off.setFixedHeight(22)
        btn_bodies_on.clicked.connect(lambda: self.all_bodies_set.emit(True))
        btn_bodies_off.clicked.connect(lambda: self.all_bodies_set.emit(False))
        body_btns.addWidget(btn_bodies_on)
        body_btns.addWidget(btn_bodies_off)
        layout.addLayout(body_btns)

        # Trails bulk-action row
        layout.addWidget(QLabel("Trails"))
        trail_btns = QHBoxLayout()
        btn_trails_on  = QPushButton("Enable All")
        btn_trails_off = QPushButton("Disable All")
        btn_trails_on.setFixedHeight(22)
        btn_trails_off.setFixedHeight(22)
        btn_trails_on.clicked.connect(lambda: self.all_trails_set.emit(True))
        btn_trails_off.clicked.connect(lambda: self.all_trails_set.emit(False))
        trail_btns.addWidget(btn_trails_on)
        trail_btns.addWidget(btn_trails_off)
        layout.addLayout(trail_btns)

        self._list = QListWidget()
        self._list.itemClicked.connect(
            lambda item: self.body_selected.emit(item.data(Qt.ItemDataRole.UserRole))
        )
        self._list.itemDoubleClicked.connect(
            lambda item: self.body_edit_requested.emit(item.data(Qt.ItemDataRole.UserRole))
        )
        layout.addWidget(self._list)

    def populate(self, bodies: list[CelestialBody]) -> None:
        self._list.clear()
        for body in bodies:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, body.name)
            widget = self._row_widget(body)
            self._list.addItem(item)
            item.setSizeHint(widget.sizeHint())
            self._list.setItemWidget(item, widget)

    def selected_name(self) -> str | None:
        item = self._list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _row_widget(self, body: CelestialBody) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 2, 4, 2)
        # Colour dot
        px = QPixmap(14, 14)
        r, g, b = (int(c * 255) for c in body.color)
        px.fill(QColor(r, g, b))
        dot = QLabel()
        dot.setPixmap(px)
        layout.addWidget(dot)
        # Name
        layout.addWidget(QLabel(body.name), stretch=1)
        # Active checkbox
        cb_active = QCheckBox("Active")
        cb_active.setChecked(body.active)
        name = body.name
        cb_active.stateChanged.connect(
            lambda state, n=name: self.body_active_toggled.emit(
                n, state == Qt.CheckState.Checked.value
            )
        )
        layout.addWidget(cb_active)
        # Trail checkbox
        cb_trail = QCheckBox("Trail")
        cb_trail.setChecked(body.show_trail)
        cb_trail.stateChanged.connect(
            lambda state, n=name: self.trail_toggled.emit(
                n, state == Qt.CheckState.Checked.value
            )
        )
        layout.addWidget(cb_trail)
        return row
```

- [ ] **Step 2: Run full test suite to confirm nothing broke**

```bash
conda run -n nbodiesgravity pytest tests/ -v
```

Expected: all 43 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add nbodiesgravity/ui/body_list_panel.py
git commit -m "feat: add Active checkbox and bulk enable/disable buttons to BodyListPanel"
```

---

## Task 5: `ui/main_window.py` — wire signals + new slots

**Files:**
- Modify: `nbodiesgravity/ui/main_window.py`

- [ ] **Step 1: Wire the three new signals in `_build_ui()`**

In `_build_ui()`, after the existing `self._body_list.trail_toggled.connect(...)` line, add:

```python
        self._body_list.body_active_toggled.connect(self._on_body_active_toggled)
        self._body_list.all_bodies_set.connect(self._on_all_bodies_set)
        self._body_list.all_trails_set.connect(self._on_all_trails_set)
```

- [ ] **Step 2: Add the three new slot methods**

Add these three methods to `MainWindow`, after `_on_trail_toggled`:

```python
    def _on_body_active_toggled(self, name: str, active: bool) -> None:
        if self._sim is None:
            return
        body = self._sim.system.get_body(name)
        if body:
            body.active = active
            if not active:
                self._gl.clear_trail_for(name)

    def _on_all_bodies_set(self, active: bool) -> None:
        if self._sim is None:
            return
        for body in self._sim.system.bodies:
            body.active = active
        if not active:
            self._gl.clear_trails()
        self._body_list.populate(self._sim.system.bodies)

    def _on_all_trails_set(self, enabled: bool) -> None:
        if self._sim is None:
            return
        for body in self._sim.system.bodies:
            body.show_trail = enabled
        self._body_list.populate(self._sim.system.bodies)
```

- [ ] **Step 3: Refactor `_toggle_all_trails()` to delegate to `_on_all_trails_set()`**

Replace the existing `_toggle_all_trails` method:

```python
    def _toggle_all_trails(self) -> None:
        if self._sim is None:
            return
        bodies = self._sim.system.bodies
        new_state = not all(b.show_trail for b in bodies)
        self._on_all_trails_set(new_state)
```

- [ ] **Step 4: Update the JPL Horizons progress bar max from 20 to 22**

In `_on_date_changed()`, change:

```python
        self._progress = QProgressDialog(
            "Fetching from JPL Horizons…", "Cancel", 0, 20, self
        )
```

to:

```python
        self._progress = QProgressDialog(
            "Fetching from JPL Horizons…", "Cancel", 0, 22, self
        )
```

- [ ] **Step 5: Run full test suite**

```bash
conda run -n nbodiesgravity pytest tests/ -v
```

Expected: all 43 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add nbodiesgravity/ui/main_window.py
git commit -m "feat: wire body active toggle and bulk enable/disable slots in MainWindow"
```

---

## Task 6: Data — Haumea, Makemake, and updated snapshot

**Files:**
- Modify: `scripts/fetch_j2000.py`
- Regenerate: `nbodiesgravity/data/snapshots/j2000.json`
- Modify: `tests/data/test_loader.py`

- [ ] **Step 1: Add Haumea and Makemake to `fetch_j2000.py`**

In `scripts/fetch_j2000.py`, find the `BODIES` list and append two entries after `("Ceres", ...)`:

```python
    ("Haumea",   "136108;",  4.006e21,  780, [0.85, 0.75, 0.60]),
    ("Makemake", "136472;",  3.100e21,  715, [0.90, 0.60, 0.50]),
```

The full updated BODIES list becomes:

```python
BODIES = [
    ("Sun",      "10",       1.989e30,  695700, [1.0, 0.9, 0.2]),
    ("Mercury",  "199",      3.301e23,    2440, [0.7, 0.7, 0.7]),
    ("Venus",    "299",      4.867e24,    6052, [0.9, 0.8, 0.5]),
    ("Earth",    "399",      5.972e24,    6371, [0.2, 0.5, 1.0]),
    ("Mars",     "499",      6.417e23,    3390, [0.9, 0.4, 0.2]),
    ("Jupiter",  "599",      1.898e27,   69911, [0.8, 0.7, 0.5]),
    ("Saturn",   "699",      5.683e26,   58232, [0.9, 0.8, 0.6]),
    ("Uranus",   "799",      8.681e25,   25362, [0.5, 0.8, 0.9]),
    ("Neptune",  "899",      1.024e26,   24622, [0.3, 0.4, 0.9]),
    ("Moon",     "301",      7.342e22,    1737, [0.8, 0.8, 0.8]),
    ("Io",       "501",      8.932e22,    1822, [1.0, 0.8, 0.3]),
    ("Europa",   "502",      4.800e22,    1561, [0.8, 0.7, 0.6]),
    ("Ganymede", "503",      1.482e23,    2634, [0.5, 0.5, 0.5]),
    ("Callisto", "504",      1.076e23,    2410, [0.4, 0.4, 0.4]),
    ("Titan",    "606",      1.345e23,    2575, [0.9, 0.7, 0.4]),
    ("Triton",   "801",      2.139e22,    1354, [0.7, 0.8, 0.9]),
    ("Pluto",    "999",      1.307e22,    1188, [0.8, 0.7, 0.6]),
    ("Charon",   "901",      1.586e21,     606, [0.6, 0.6, 0.6]),
    ("Eris",     "136199;",  1.660e22,    1163, [0.9, 0.9, 0.9]),
    ("Ceres",    "1;",       9.383e20,     473, [0.6, 0.6, 0.6]),
    ("Haumea",   "136108;",  4.006e21,    780, [0.85, 0.75, 0.60]),
    ("Makemake", "136472;",  3.100e21,    715, [0.90, 0.60, 0.50]),
]
```

- [ ] **Step 2: Update the failing loader test before regenerating**

In `tests/data/test_loader.py`, rename and update:

```python
def test_load_default_has_22_bodies():
    system = load_default_system()
    assert len(system.bodies) == 22
```

(Delete the old `test_load_default_has_20_bodies` function and replace it with the above.)

Also add a check that the new bodies are present:

```python
def test_load_default_contains_haumea_and_makemake():
    system = load_default_system()
    names = {b.name for b in system.bodies}
    assert "Haumea" in names
    assert "Makemake" in names
```

- [ ] **Step 3: Run the loader test to verify it fails (snapshot still has 20)**

```bash
conda run -n nbodiesgravity pytest tests/data/test_loader.py::test_load_default_has_22_bodies tests/data/test_loader.py::test_load_default_contains_haumea_and_makemake -v
```

Expected: both FAIL — `j2000.json` still has 20 bodies.

- [ ] **Step 4: Regenerate `j2000.json` (requires internet)**

```bash
conda run -n nbodiesgravity python scripts/fetch_j2000.py
```

Expected output (22 lines, one per body):
```
  Sun        (10      )... OK
  Mercury    (199     )... OK
  Venus      (299     )... OK
  Earth      (399     )... OK
  Mars       (499     )... OK
  Jupiter    (599     )... OK
  Saturn     (699     )... OK
  Uranus     (799     )... OK
  Neptune    (899     )... OK
  Moon       (301     )... OK
  Io         (501     )... OK
  Europa     (502     )... OK
  Ganymede   (503     )... OK
  Callisto   (504     )... OK
  Titan      (606     )... OK
  Triton     (801     )... OK
  Pluto      (999     )... OK
  Charon     (901     )... OK
  Eris       (136199; )... OK
  Ceres      (1;      )... OK
  Haumea     (136108; )... OK
  Makemake   (136472; )... OK

Wrote 22 bodies to ...j2000.json
```

- [ ] **Step 5: Run all tests to verify they all pass**

```bash
conda run -n nbodiesgravity pytest tests/ -v
```

Expected: all 45 tests PASS (43 previous + 2 new loader tests).

- [ ] **Step 6: Commit**

```bash
git add scripts/fetch_j2000.py nbodiesgravity/data/snapshots/j2000.json tests/data/test_loader.py
git commit -m "feat: add Haumea and Makemake to J2000 snapshot (22 bodies total)"
```

---

## Final verification

After all 6 tasks are committed, run the full suite one last time:

```bash
conda run -n nbodiesgravity pytest tests/ -v
```

Expected: **45 tests, 0 failures.**

Then push:

```bash
git push
```
