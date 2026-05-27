# Add-Bodies Feature Set — Design Spec

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add per-body active/inactive toggle (physics-excluded when off), bulk enable/disable buttons for both bodies and trails, and two new dwarf planets (Haumea, Makemake) to the J2000 snapshot.

**Architecture:** The `active` flag lives on `CelestialBody` and is carried through `BodyState` into the snapshot. `SolarSystem.step()` filters to active bodies only. `GLWidget` skips inactive bodies in both trail accumulation and sphere rendering. `BodyListPanel` grows a second per-row checkbox and four bulk-action buttons.

**Tech Stack:** Python 3.12, PyQt6, PyOpenGL, NumPy — no new dependencies.

---

## 1. Engine layer

### 1.1 `engine/body.py`

Add `active: bool = True` to `CelestialBody`:

```python
@dataclass
class CelestialBody:
    name: str
    mass: float
    pos: np.ndarray
    vel: np.ndarray
    radius: float
    color: tuple[float, float, float]
    show_trail: bool = True
    active: bool = True          # NEW — False = excluded from integrator
```

Add `active` to `BodyState` and propagate it through `snapshot()`:

```python
class BodyState(NamedTuple):
    name: str
    pos: np.ndarray
    vel: np.ndarray
    active: bool = True          # NEW

# In CelestialBody.snapshot():
def snapshot(self) -> BodyState:
    return BodyState(
        name=self.name,
        pos=self.pos.copy(),
        vel=self.vel.copy(),
        active=self.active,      # NEW
    )
```

### 1.2 `engine/system.py`

`SolarSystem.step()` filters to active bodies only. Inactive bodies' `pos`/`vel` are not touched — they freeze at their last position.

```python
def step(self, dt: float) -> None:
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

Thread safety: setting `body.active` from the UI thread is GIL-safe (single bool attribute write), identical in pattern to `show_trail`. The change takes effect on the next `step()` call, which is held under `SimulationThread._lock`.

---

## 2. Rendering layer

### 2.1 `rendering/gl_widget.py`

**`paintGL` — trail accumulation loop:** Skip any state where `state.active is False`. No trail point appended for inactive bodies.

**`paintGL` — sphere draw loop:** Skip any state where `state.active is False`. No sphere rendered.

**New method `clear_trail_for(name: str)`:** Resets the `TrailBuffer` for a single named body. Called by `MainWindow` when a body is deactivated.

```python
def clear_trail_for(self, name: str) -> None:
    tb = self._trail_buffers.get(name)
    if tb is not None:
        tb.reset()
```

The existing `clear_trails()` (resets all buffers) is unchanged.

---

## 3. UI layer

### 3.1 `ui/body_list_panel.py`

**Per-row layout** (left to right):

```
[●] Body Name          [✓ Active] [✓ Trail]
```

The "Active" checkbox is added to the left of the existing "Trail" checkbox. Default: checked.

**Bulk-action header** replaces the plain "Bodies" label:

```
Bodies:  [Enable All]  [Disable All]
Trails:  [Enable All]  [Disable All]
```

**New signals:**

```python
body_active_toggled = pyqtSignal(str, bool)   # (name, active)
all_bodies_set      = pyqtSignal(bool)         # True = enable all, False = disable all
all_trails_set      = pyqtSignal(bool)         # True = enable all, False = disable all
```

Existing signals (`body_selected`, `body_edit_requested`, `trail_toggled`) are unchanged.

---

## 4. MainWindow wiring

### 4.1 New slots in `ui/main_window.py`

**`_on_body_active_toggled(name: str, active: bool)`**
```python
def _on_body_active_toggled(self, name: str, active: bool) -> None:
    if self._sim:
        body = self._sim.system.get_body(name)
        if body:
            body.active = active
            if not active:
                self._gl.clear_trail_for(name)
```

**`_on_all_bodies_set(active: bool)`**
```python
def _on_all_bodies_set(self, active: bool) -> None:
    if self._sim is None:
        return
    for body in self._sim.system.bodies:
        body.active = active
    if not active:
        self._gl.clear_trails()
    self._body_list.populate(self._sim.system.bodies)
```

**`_on_all_trails_set(enabled: bool)`**
```python
def _on_all_trails_set(self, enabled: bool) -> None:
    if self._sim is None:
        return
    for body in self._sim.system.bodies:
        body.show_trail = enabled
    self._body_list.populate(self._sim.system.bodies)
```

### 4.2 Signal wiring (added in `_build_ui`)

```python
self._body_list.body_active_toggled.connect(self._on_body_active_toggled)
self._body_list.all_bodies_set.connect(self._on_all_bodies_set)
self._body_list.all_trails_set.connect(self._on_all_trails_set)
```

### 4.3 `_toggle_all_trails` (View menu)

Reimplement to delegate to `_on_all_trails_set`, toggling based on current state:

```python
def _toggle_all_trails(self) -> None:
    if self._sim is None:
        return
    bodies = self._sim.system.bodies
    new_state = not all(b.show_trail for b in bodies)
    self._on_all_trails_set(new_state)
```

---

## 5. Data — Haumea and Makemake

### 5.1 `scripts/fetch_j2000.py`

Add two entries to the `BODIES` list after Ceres:

```python
("Haumea",   "136108;",  4.006e21,  780, [0.85, 0.75, 0.60]),
("Makemake", "136472;",  3.100e21,  715, [0.90, 0.60, 0.50]),
```

Re-run the script:
```bash
conda run -n nbodiesgravity python scripts/fetch_j2000.py
```

This updates `nbodiesgravity/data/snapshots/j2000.json` from 20 → 22 bodies.

### 5.2 `ui/date_loader_worker.py` / `ui/main_window.py`

The JPL Horizons progress dialog in `_on_date_changed` is hardcoded to `QProgressDialog(..., 0, 20, ...)`. Update to `22`.

---

## 6. Testing

Existing tests should continue to pass unchanged — `BodyState` gains a field with a default, so no existing construction breaks.

New tests to add in `tests/engine/test_system.py`:

- `test_inactive_body_not_integrated`: create a 2-body system, deactivate one, step, verify frozen body's position unchanged and active body's position changed.
- `test_all_inactive_step_is_noop`: deactivate all bodies, step, verify no position changes and no exception raised.
- `test_reactivate_body_resumes_integration`: deactivate, step N times, reactivate, step — verify the formerly-frozen body starts moving again.

New test in `tests/rendering/test_trail_buffer.py` (or `test_gl_widget.py`):

- `test_clear_trail_for`: populate two trail buffers, call `clear_trail_for` on one, verify only that one is reset.

---

## 7. File change summary

| File | Change |
|---|---|
| `engine/body.py` | Add `active: bool = True` to `CelestialBody`; add `active: bool` to `BodyState` and `snapshot()` |
| `engine/system.py` | Filter active bodies in `step()` |
| `rendering/gl_widget.py` | Skip inactive states in paintGL loops; add `clear_trail_for(name)` |
| `ui/body_list_panel.py` | Add Active checkbox per row; add four bulk-action buttons; add three new signals |
| `ui/main_window.py` | Wire new signals; add `_on_body_active_toggled`, `_on_all_bodies_set`, `_on_all_trails_set`; update progress bar max to 22; refactor `_toggle_all_trails` |
| `scripts/fetch_j2000.py` | Add Haumea and Makemake entries |
| `nbodiesgravity/data/snapshots/j2000.json` | Regenerated with 22 bodies |
| `tests/engine/test_system.py` | Add 3 new tests for active filtering |
| `tests/rendering/test_trail_buffer.py` | Add `test_clear_trail_for` |
