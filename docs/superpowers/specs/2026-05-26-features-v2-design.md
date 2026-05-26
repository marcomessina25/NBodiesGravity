# N-Body Gravity — Feature Set v2 Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add relative-frame trails, a live simulation-date label, a clear-trails button, and richer "Add Body" templates to the existing N-body desktop application.

**Architecture:** All changes are additive or minimal surgical edits to existing files. No new modules required. The engine layer (`simulation_thread.py`) grows one property; the rendering layer (`trail_buffer.py`, `gl_widget.py`) changes the trail append contract; the two UI files (`control_panel.py`, `body_editor_dialog.py`) and the wiring hub (`main_window.py`) absorb the rest.

**Tech Stack:** Python 3.11, PyQt6, PyOpenGL, NumPy — same as v1.

---

## Feature 1 — Relative-Frame Trails

### Problem

`TrailBuffer.append` currently stores absolute SSB positions. The line shader subtracts the *current* `camera.center_pos` from every vertex, but that is wrong for historic trail points — the center body has moved since those points were recorded.

### Fix

**`TrailBuffer.append(pos, center_pos)`** stores `(pos − center_pos).astype(float32)` — the relative position is baked in at record time. The ring buffer, GPU upload, and `draw()` are otherwise unchanged.

**`TrailBuffer.reset()`** — new method. Zeroes `_buf`, sets `_head = _count = 0`, `_dirty = True`.

**`GLWidget`**:
- Every `tb.append(state.pos)` becomes `tb.append(state.pos, self.camera.center_pos)`.
- `uCenterOffset` uniform for the line shader is set to `(0.0, 0.0, 0.0)` — the baked-in relative data makes it redundant.
- New `clear_trails()` method: calls `tb.reset()` for every entry in `_trail_buffers`.

**Center-change behaviour:** Whenever the camera center changes (either from `ControlPanel.center_changed` or `BodyListPanel.body_selected`), `GLWidget.clear_trails()` is called immediately. Old trail data is incompatible with a new reference frame and must be discarded. `MainWindow` wires these two signals to both `camera.set_center` and `gl.clear_trails`.

---

## Feature 2 — Live Simulation Date Label

### SimulationThread (`engine/simulation_thread.py`)

Add `_elapsed_days: float = 0.0` — incremented by `dt` on every physics step inside `run()`. This is a plain float assignment (GIL-safe, same pattern as `latest_snapshot`). A new read-only property `elapsed_days -> float` exposes it. Because `_load_system` creates a fresh `SimulationThread` for every system load, `elapsed_days` resets to zero automatically.

### ControlPanel (`ui/control_panel.py`)

A `QLabel` is inserted immediately after the epoch `QDateEdit`, initialised to `"→  –"`. Public method:

```python
def set_sim_date(self, text: str) -> None:
    self._sim_date_label.setText(f"→  {text}")
```

### MainWindow (`ui/main_window.py`)

A `QTimer` (`self._date_timer`) fires at 4 Hz (250 ms interval). Its slot `_update_sim_date()` reads `self._sim.elapsed_days`, computes `self._last_epoch + timedelta(days=elapsed)`, formats as `"YYYY-MM-DD"`, and calls `self._ctrl.set_sim_date(...)`. The timer is (re-)started inside `_load_system`. When the simulation is paused the label simply stops changing — no special handling needed.

---

## Feature 3 — Clear Trails Button

### ControlPanel (`ui/control_panel.py`)

New signal: `clear_trails_requested = pyqtSignal()`

A `QPushButton("Clear Trails")` is appended at the right end of the control bar (after the center combo). Its `clicked` signal emits `clear_trails_requested`.

### GLWidget (`rendering/gl_widget.py`)

`clear_trails()` (described above in Feature 1) is the sole implementation target.

### MainWindow (`ui/main_window.py`)

```python
self._ctrl.clear_trails_requested.connect(self._gl.clear_trails)
```

This is the only wiring change for this feature. The center-change wiring is covered by Feature 1.

---

## Feature 4 — Add Body with Defaults

### BodyEditorDialog (`ui/body_editor_dialog.py`)

New optional constructor parameter: `template_bodies: list[CelestialBody] = []`. The parameter is ignored in edit mode.

A `QComboBox` labelled **"Template:"** is prepended to the form (hidden when `edit_mode=True`). Its items are:

```
["Blank"] + [b.name for b in template_bodies] + ["Average of two…"]
```

**Blank (default):** form fields show the existing defaults — no change to current behaviour.

**Selecting a body name:** all form fields are pre-filled from that body's current state. The name field is left empty so the user must supply a distinct name.

**Selecting "Average of two…":** two `QComboBox` widgets ("Body A:" / "Body B:") become visible below the template selector. Once both pickers hold a valid selection, all numeric fields are computed as the arithmetic mean of the two bodies:

| Field | Formula |
|---|---|
| Position (x, y, z) | `(a.pos + b.pos) / 2` |
| Velocity (vx, vy, vz) | `(a.vel + b.vel) / 2` |
| Mass | `(a.mass + b.mass) / 2` |
| Radius | `(a.radius + b.radius) / 2` |
| Color (r, g, b) | `((a.color[i] + b.color[i]) / 2)` per channel |

The user may override any field freely after pre-fill. The name field is always left empty.

### MainWindow (`ui/main_window.py`)

`_add_body()` passes the current body list as template bodies:

```python
dlg = BodyEditorDialog(
    existing_names=existing,
    template_bodies=self._sim.system.bodies,
    parent=self,
)
```

---

## Files Changed

| File | Change type |
|---|---|
| `nbodiesgravity/rendering/trail_buffer.py` | `append` signature + `reset()` |
| `nbodiesgravity/rendering/gl_widget.py` | relative append, `clear_trails()`, `uCenterOffset=0` for trails |
| `nbodiesgravity/engine/simulation_thread.py` | `_elapsed_days` + `elapsed_days` property |
| `nbodiesgravity/ui/control_panel.py` | sim-date label + clear-trails button + signal |
| `nbodiesgravity/ui/body_editor_dialog.py` | template selector + average-of-two pickers |
| `nbodiesgravity/ui/main_window.py` | date timer, clear_trails wiring, template_bodies arg |

---

## Testing

**`tests/rendering/test_trail_buffer.py`** (new file):
- `append(pos, center)` stores `pos − center` in the buffer.
- After the buffer wraps around, data is still correct.
- `reset()` zeroes count and head; a subsequent `append` starts fresh.

**`tests/engine/test_simulation_thread.py`** (new file):
- `elapsed_days` is `0.0` before any steps.
- After N steps with `dt`, `elapsed_days ≈ N * dt`.

UI behaviour (date label, template dialog, clear button) is verified manually — Qt widget testing requires a display and is out of scope for the automated suite.

---

## Constraints & Non-Goals

- No changes to the physics engine (`integrator.py`, `system.py`, `body.py`).
- No new Python dependencies.
- The existing `uCenterOffset` uniform remains in the line shader source for now (set to zero) — removing it would require a shader recompile with no user-visible benefit.
- Trail history is lost on center change and on system reload — this is intentional.
