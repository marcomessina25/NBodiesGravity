# CLAUDE.md — N-body Gravity Simulation

Developer/AI context file. Read at the start of every session. Not user-facing.

---

## Critical constraints (enforce without exception)

### 1. Conda environment

Always use the `nbodiesgravity` conda environment for every Python command:

```bash
conda run -n nbodiesgravity python nbodiesgravity/main.py
conda run -n nbodiesgravity pytest tests/ -v
```

Never run `python` or `pytest` bare. Never `conda activate` — always `conda run -n nbodiesgravity`.

### 2. Branch push policy

Always push to the current branch directly. If the current branch is `main` or `master`, create a new feature branch first, then push there. Never ask the user about this.

### 3. Dependency freeze

Stack is Python 3.12, PyQt6, PyOpenGL, NumPy. Do not introduce new Python dependencies without explicit user approval. If a new dependency is approved, update `environment.yml` before committing.

---

## Project overview

N-body gravitational simulation desktop application. A background QThread runs the physics loop; the render thread reads position snapshots via a GIL-safe reference swap. The UI is PyQt6. The viewport is a `QOpenGLWidget` using OpenGL 3.3 Core Profile.

**Run:** `conda run -n nbodiesgravity python nbodiesgravity/main.py`
**Tests:** `conda run -n nbodiesgravity pytest tests/ -v` — 37 tests, all must pass.

---

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| UI framework | PyQt6 6.5+ |
| 3D rendering | PyOpenGL (OpenGL 3.3 Core Profile) |
| Numerics | NumPy |
| HTTP | Requests (JPL Horizons) |
| Test mocking | responses |
| Tests | pytest |
| Package manager | Conda (`environment.yml`) |

---

## Architecture

```
UI thread (Qt main thread)
├── MainWindow          — top-level orchestrator, signal wiring
├── ControlPanel        — epoch, speed, center, play/pause, clear trails
├── BodyListPanel       — body list, trail toggles, select/edit
├── GLWidget            — QOpenGLWidget, 60 FPS render loop (paintGL)
│       └── Camera      — orbital camera, azimuth/elevation/distance
└── DateLoaderWorker    — QThread, JPL fetch, emits body_loaded / finished / error

Physics thread
└── SimulationThread    — QThread, 120 steps/s Velocity Verlet
        └── SolarSystem — owns list[CelestialBody], step(), snapshot()
```

### Thread safety rules

- `SimulationThread.latest_snapshot` is written by the physics thread and read by the render thread. GIL-safe: a single Python reference assignment is atomic.
- `SimulationThread._elapsed_days` is a plain float incremented by one writer. GIL guarantees atomicity.
- `SimulationThread._lock` (threading.Lock) guards `_system.step()` and `system.snapshot()` calls. `set_timescale`, `pause`, `resume` write simple fields — no lock needed for those.
- Never call Qt UI methods from the physics thread. Use signals.

---

## Module map

### `engine/body.py`

- `BodyState(NamedTuple)` — immutable kinematic snapshot: `name, pos, vel` (AU, AU/day).
- `CelestialBody(dataclass)` — mutable physics body: `name, mass, pos, vel, radius, color, show_trail`.
- `CelestialBody.snapshot()` → `BodyState` (copies arrays).

### `engine/integrator.py`

- `step(bodies, dt)` — Velocity Verlet N-body step. Units: AU, days, kg. G in AU³/(kg·day²).

### `engine/system.py`

- `SolarSystem` — holds `list[CelestialBody]`, delegates to integrator.
- `step(dt)`, `snapshot() → list[BodyState]`, `add_body`, `remove_body`, `get_body`.

### `engine/simulation_thread.py`

- `SimulationThread(QThread)` — runs `system.step(dt)` at 120 steps/s.
- `_timescale: float` — simulated days per real second (default 1.0).
- `_elapsed_days: float` — accumulated simulated days since last load. GIL-safe.
- `elapsed_days` property — read from any thread.
- `set_timescale(days_per_second)`, `pause()`, `resume()`, `reset(system)`, `stop_thread()`.
- `reset(system)` zeroes `_elapsed_days`.
- Signals: `snapshot_ready(list[BodyState])`, `blow_up_detected()`.

### `data/cache.py`

- Stores and retrieves JPL Horizons state vectors as JSON files keyed by `(body_id, date)`.

### `data/horizons.py`

- `fetch(body_id, date) → dict` — queries `https://ssd.jpl.nasa.gov/api/horizons.api`.
- Raises `HorizonsError` on failure.

### `data/loader.py`

- `load_default_system() → SolarSystem` — reads `data/snapshots/j2000.json`. Instant, no network.
- `load_system_at_date(epoch, progress_cb) → SolarSystem` — cache → Horizons fallback per body.

### `rendering/display_info.py`

- `BodyDisplayInfo(dataclass)` — `name, radius_km, color, is_star`.
- `display_radius` property: log-scale, maps `log10(radius_km)` from `[2, 6]` → `[0.0003, 0.003]` AU. Camera-distance floor is applied in `GLWidget`.

### `rendering/camera.py`

- `Camera` — orbital camera. `distance` (AU), `azimuth`, `elevation` (radians). `center_name` tracks the followed body.
- `update_center_pos(snapshot)` — called every frame to follow the center body.
- `view_matrix()` → 4×4 float32 lookAt.
- `zoom(factor)` — multiplies distance, min 0.001 AU.

### `rendering/trail_buffer.py`

- `TrailBuffer(color)` — ring buffer of 2000 `float32` positions (relative frame).
- `append(pos, center_pos)` — stores `pos − center_pos`. Render thread only.
- `reset()` — zeroes buffer, head, count. Called on center change or Clear Trails.
- `draw()` — uploads if dirty, draws `GL_LINE_STRIP`. Returns early if `_vao is None` (not yet GPU-initialized) or `_count < 2`.
- `initialize()` — allocates VAO/VBO. **Must be called from within `paintGL`** (GL context current).

### `rendering/sphere_mesh.py`

- UV sphere VBO. GLSL shader sources: `SPHERE_VERT_SRC`, `SPHERE_FRAG_SRC`, `LINE_VERT_SRC`, `LINE_FRAG_SRC`.

### `rendering/gl_widget.py`

- `GLWidget(QOpenGLWidget)` — 60 FPS render loop.
- `set_display_info(infos)` — registers `BodyDisplayInfo` list, creates `TrailBuffer` per body (GPU init deferred to `paintGL`).
- `set_simulation_thread(thread)` — wires up the snapshot source.
- `clear_trails()` — calls `tb.reset()` on all trail buffers.
- `paintGL()` sequence:
  1. Lazy-init any `TrailBuffer` whose `_vao is None` (runs with GL context current).
  2. Accumulates trail: `tb.append(state.pos, camera.center_pos)` for every body.
  3. Draws trails with `uCenterOffset = (0,0,0)` — offset is baked into the buffer.
  4. Draws Phong spheres. Body radius = `max(display_radius, camera.distance * 0.008)`.
- **Never call `tb.initialize()` from outside `paintGL`.** The GL context is only current during `initializeGL`, `resizeGL`, and `paintGL`.

### `ui/control_panel.py`

- Signals: `date_changed(datetime)`, `timescale_changed(float)`, `center_changed(str)`, `play_toggled(bool)`, `clear_trails_requested()`.
- Speed slider: 200 steps, log10 scale. `_LOG_MIN = log10(1/24)` (1 h/s), `_LOG_MAX = log10(365.25)` (1 y/s). Emits days/s.
- `set_sim_date(text)` — updates the live simulation date label.
- `set_body_names(names)` — repopulates center combo, preserves current selection.

### `ui/body_list_panel.py`

- Signals: `body_selected(str)`, `body_edit_requested(str)`, `trail_toggled(str, bool)`.
- `populate(bodies)` — rebuilds list rows.

### `ui/body_editor_dialog.py`

- `BodyEditorDialog(existing_names, body=None, template_bodies=None, parent=None)`.
- Edit mode (`body` provided): no template selector shown.
- Add mode: template combo with "Blank" / body names / "Average of two…" (latter only if ≥2 template bodies).
- `result_body() → CelestialBody` — call after `exec()` returns Accepted.
- Helper methods: `_on_template_changed`, `_on_avg_selection_changed`, `_clear_fields`, `_fill_from_body`, `_fill_from_average`.
- `_validate()` called explicitly at end of every fill method and connected to field signals.

### `ui/date_loader_worker.py`

- `DateLoaderWorker(QThread)` — runs `load_system_at_date` in background.
- Signals: `body_loaded(str)`, `finished(SolarSystem)`, `error(str)`.

### `ui/main_window.py`

- `MainWindow` — assembles all panels, wires all signals.
- `_load_system(system)`: clears trails → resets date label → starts timer → starts sim thread (in that order — `clear_trails()` must precede `_sim.start()` to avoid race).
- `_date_timer` (QTimer, 250 ms) → `_update_sim_date()` → `_ctrl.set_sim_date(...)`.
- Center change and `body_selected` both wire to `lambda _: self._gl.clear_trails()`.
- `closeEvent`: stops `_date_timer` before `_sim.stop_thread()`.

---

## Signal/slot wiring (MainWindow)

| Source | Signal | Slot |
|---|---|---|
| `_ctrl` | `date_changed` | `_on_date_changed` (triggers JPL fetch) |
| `_ctrl` | `timescale_changed` | `lambda v: _sim.set_timescale(v)` |
| `_ctrl` | `center_changed` | `_gl.camera.set_center` |
| `_ctrl` | `center_changed` | `lambda _: _gl.clear_trails()` |
| `_ctrl` | `play_toggled` | `_on_play_toggled` |
| `_ctrl` | `clear_trails_requested` | `_gl.clear_trails` |
| `_body_list` | `body_selected` | `_gl.camera.set_center` |
| `_body_list` | `body_selected` | `lambda _: _gl.clear_trails()` |
| `_body_list` | `body_edit_requested` | `_edit_body` |
| `_body_list` | `trail_toggled` | `_on_trail_toggled` |
| `_sim` | `blow_up_detected` | `_on_blow_up` |
| `_date_timer` | `timeout` | `_update_sim_date` |

---

## Key design decisions

1. **Relative-frame trails**: offset baked at `append` time (`pos − center_pos`). When the center changes, all buffers are cleared — old data is in the wrong reference frame.
2. **GIL-safe snapshot**: `latest_snapshot` is a list reference. Python's GIL ensures a reference assignment is atomic. No lock needed for reads.
3. **GPU init deferred to paintGL**: `TrailBuffer.initialize()` requires the GL context to be current. `set_display_info` is called from the Qt main thread outside any GL callback — do not call `initialize()` there.
4. **`elapsed_days` resets automatically**: `_load_system` always creates a fresh `SimulationThread`, so `_elapsed_days` starts at 0. `reset(system)` also explicitly zeroes it.
5. **Log-scale speed**: slider maps to `10^(LOG_MIN + t*(LOG_MAX-LOG_MIN))` days/s. `timescale_changed` always emits float days/s.
6. **Body display size**: physical log-scaled base `[0.0003, 0.003]` AU, floored at `camera.distance * 0.008`. Moons become visible outside parent planets when `camera.distance ≲ 0.1 AU`.

---

## Physics units

| Quantity | Unit |
|---|---|
| Position | AU (Astronomical Units) |
| Velocity | AU/day |
| Mass | kg |
| Time step | days |
| G | 6.674×10⁻¹¹ m³/(kg·s²) converted to AU³/(kg·day²) |

---

## Testing

```bash
conda run -n nbodiesgravity pytest tests/ -v
```

37 tests across:

- `tests/engine/` — integrator energy conservation, system operations, `simulation_thread` property.
- `tests/data/` — cache, Horizons client (mocked with `responses`), loader.
- `tests/rendering/` — `TrailBuffer` relative append, reset, ring-wrap.

`tests/conftest.py` provides a session-scoped `QApplication` fixture required for any `QThread` instantiation.

UI behaviour (dialogs, rendering) is verified manually — Qt widget testing requires a display.

---

## Development workflow

This project uses the `superpowers` skill suite:

1. `superpowers:brainstorming` — design + spec doc (Opus orchestrates).
2. `superpowers:writing-plans` — TDD task list with exact code blocks.
3. `superpowers:subagent-driven-development` — fresh subagent per task + two-stage review (Sonnet implements; spec-compliance reviewer + code-quality reviewer follow).
4. `superpowers:finishing-a-development-branch` — merge/PR/cleanup.

Feature branches use git worktrees (`.worktrees/` — gitignored).

### Subagent model selection

| Role | Model |
|---|---|
| Implementer (production code, multi-file) | `sonnet` |
| Implementer (verbatim-paste, single-file append) | `haiku` |
| Spec-compliance reviewer | `sonnet` |
| Code-quality reviewer | `superpowers:code-reviewer` (do not pass model) |
| Documenter (README, docstrings) | `haiku` |

---

## Common pitfalls

- **Do not call `TrailBuffer.initialize()` outside `paintGL`.** The GL context is not current. `_vao` will be set to a garbage integer, bypassing `draw()`'s `None` guard and silently producing no output.
- **Do not call `_sim.start()` before `_gl.clear_trails()` in `_load_system`.** The physics thread may write trail points between `start()` and a subsequent `clear_trails()`.
- **Do not add new dependencies without updating `environment.yml`.**
- **`BodyListPanel.populate()` may emit `body_selected` on programmatic selection.** Wiring that signal to `clear_trails()` means trails clear on every `populate()` — currently harmless since buffers are empty at that point, but be aware of this if that invariant ever changes.
- **Do not read `SimulationThread._elapsed_days` with a lock.** It is GIL-safe; adding a lock here is incorrect and risks deadlock if called from the physics thread indirectly.
- **`closeEvent` order matters.** Stop `_date_timer` before `_sim.stop_thread()`. Reversing this risks the timer firing after the thread has stopped and `latest_snapshot` is stale or None.
