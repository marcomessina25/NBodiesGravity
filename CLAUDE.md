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
**Tests:** `conda run -n nbodiesgravity pytest tests/ -v` — 70 tests, all must pass.

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
└── SimulationThread    — QThread, up to 500 steps/s adaptive Velocity Verlet
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

- `BodyState(NamedTuple)` — immutable kinematic snapshot: `name, pos, vel, active` (AU, AU/day). `active=False` bodies are invisible and excluded from the integrator.
- `CelestialBody(dataclass)` — mutable physics body: `name, mass, pos, vel, radius, color, show_trail, active, label, show_name`. `label` is one of `"star"`, `"planet"`, `"moon"`, `"dwarf planet"`, `"asteroid"` (default `"planet"`). `show_name` controls in-viewport label visibility (default `True`).
- `CelestialBody.snapshot()` → `BodyState` (copies arrays).
- `CollisionEvent(NamedTuple)` — `absorbed, survivor` (body names). Returned by `SolarSystem.step()` when a merge occurs.

### `engine/integrator.py`

- `step(bodies, dt)` — Velocity Verlet N-body step. Units: AU, days, kg. G in AU³/(kg·day²).

### `engine/system.py`

- `SolarSystem` — holds `list[CelestialBody]`, delegates to integrator.
- `clone() → SolarSystem` — deep-copies all bodies (including `label`, `show_name`, `active`). Used by restart and initial-state tracking.
- `step(dt) → list[CollisionEvent]` — advances only active bodies. Computes adaptive `max_step` from the minimum pairwise orbital timescale: `max_step = max(1e-5, min(1.0, 0.01 * min_t_orb))`. Sub-steps `dt` in chunks of at most `max_step` to maintain accuracy for tight orbits. Returns list of collision events (empty if none).
- `_resolve_collisions() → list[CollisionEvent]` — merges active bodies whose centres come within the sum of their physical radii (`KM_PER_AU = 1.495978707e8` converts km radii to AU). Survivor = larger mass (ties broken by alphabetically-first name); momentum conserved (`v = (mₛvₛ + mₐvₐ)/(mₛ+mₐ)`), mass summed, radius grows by equal-density volume (`r = (rₛ³ + rₐ³)^⅓`). Loops until no overlap remains so chains collapse in one call. Always on.
- `snapshot() → list[BodyState]`, `add_body`, `remove_body`, `get_body`.

### `engine/simulation_thread.py`

- `SimulationThread(QThread)` — drives `system.step(dt)` targeting `_TARGET_HZ = 500` real-time iterations/s; actual physics step is adaptive (see `system.py`). Real-dt capped at 50 ms to prevent spiral-of-death.
- `_timescale: float` — simulated days per real second (default 1.0); minimum enforced at `1e-3` by `set_timescale`.
- `_elapsed_days: float` — accumulated simulated days since last system load. GIL-safe float.
- `elapsed_days` property — read from any thread.
- `is_playing` property — `True` when not paused.
- `system` property — read-only access to `_system`.
- `set_timescale(days_per_second)`, `pause()`, `resume()`, `reset(system)`, `stop_thread()`.
- `refresh_snapshot()` — forces a snapshot refresh from the current system state while paused (used after body edits to update `latest_snapshot` before the thread resumes).
- `reset(system)` zeroes `_elapsed_days`.
- Blow-up detection checks only **active** bodies for NaN/inf positions or distance > 1000 AU.
- Signals: `snapshot_ready(list[BodyState])`, `blow_up_detected()`, `collisions_detected(list[CollisionEvent])`.

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

- Signals: `body_selected(str)`, `body_edit_requested(str)`, `trail_toggled(str, bool)`, `body_active_toggled(str, bool)`, `all_bodies_set(bool)`, `all_trails_set(bool)`, `category_active_toggled(str, bool)`, `category_trail_toggled(str, bool)`, `category_name_toggled(str, bool)`.
- `populate(bodies)` — rebuilds list rows; also rebuilds per-category header rows with bulk-toggle checkboxes.
- `_category_widgets` dict — keyed by label string, each value is `{"active": QCheckBox, "trail": QCheckBox, "name": QCheckBox}`. Used in tests to verify checkbox state after operations.

### `ui/body_editor_dialog.py`

- `BodyEditorDialog(existing_names, body=None, template_bodies=None, parent=None)`.
- Edit mode (`body` provided) and Add mode both show template-based fields when `template_bodies` is non-empty.
- Fields: **Name**, **Label** (combo: star/planet/moon/dwarf planet/asteroid), **Mass**, **Radius**, **Color**, **Position X/Y/Z**, **Velocity VX/VY/VZ**.
- When `template_bodies` is provided, each of Mass, Radius, Position, and Velocity gains a **Mode** combo:
  - Mass/Radius modes: `"Manual"` | `"Template * Multiplier"` — picks a template body and a float multiplier, auto-computes the value.
  - Position/Velocity modes: `"Manual"` | `"From Template"` | `"Average of Two"` — copies or averages from up to two template bodies.
- **Position overlap validation**: `_validate()` checks that the entered position does not match any template body's position (within `1e-9` AU, skipping the body's own original position in edit mode). OK button disabled while the error label is non-empty.
- `result_body() → CelestialBody` — call after `exec()` returns Accepted; includes `label` field.
- `_validate()` is called at the end of every template-fill slot and connected to all field-change signals.

### `ui/date_loader_worker.py`

- `DateLoaderWorker(QThread)` — runs `load_system_at_date` in background.
- Signals: `body_loaded(str)`, `finished(SolarSystem)`, `error(str)`.

### `ui/main_window.py`

- `MainWindow` — assembles all panels, wires all signals.
- `_initial_system: SolarSystem | None` — clone of the system captured at each non-restart load; used by `_on_restart()` to restore epoch state.
- `_initial_epoch: datetime` — epoch captured alongside `_initial_system`.
- `_load_system(system, is_restart=False)`: clears trails → resets date label → starts timer → starts sim thread. When `is_restart=False` (default), captures `_initial_system = system.clone()` and `_initial_epoch`. When `is_restart=True`, skips the clone so the initial-state snapshot is preserved.
- `_on_restart()` — restores `_initial_system.clone()` at `_initial_epoch` without re-cloning the initial snapshot.
- `_date_timer` (QTimer, 250 ms) → `_update_sim_date()` → `_ctrl.set_sim_date(...)`.
- `_on_body_active_toggled(name, active)` — toggles `body.active` under lock; if the camera was following the deactivated body, falls back to the next active body.
- `_on_all_bodies_set(active)` / `_on_all_trails_set(enabled)` — bulk-set all bodies; camera resets to Sun when all deactivated.
- `_on_category_active_toggled(label, active)` / `_on_category_trail_toggled` / `_on_category_name_toggled` — per-category bulk operations.
- `_refresh_after_body_change()` — rebuilds `display_infos`, repopulates list and center combo, updates `latest_snapshot`. Called after any add/edit/remove body operation.
- `_on_collisions(events)` — on merges from the physics thread: follows the collision chain to the final survivor and retargets the camera if it was following an absorbed body, then calls `_refresh_after_body_change()`. Not mirrored into `_initial_system` — Restart restores the pre-collision epoch state.
- `_save_to_file()` / `_load_from_file()` — JSON save/load of body state via `QFileDialog`.
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
| `_ctrl` | `show_names_toggled` | `_on_show_names_toggled_from_ctrl` |
| `_ctrl` | `restart_requested` | `_on_restart` |
| `_ctrl` | `top_view_requested` | `_on_top_view` |
| `_body_list` | `body_selected` | `_on_body_selected` (focus camera + update) |
| `_body_list` | `body_edit_requested` | `_edit_body` |
| `_body_list` | `trail_toggled` | `_on_trail_toggled` |
| `_body_list` | `body_active_toggled` | `_on_body_active_toggled` |
| `_body_list` | `all_bodies_set` | `_on_all_bodies_set` |
| `_body_list` | `all_trails_set` | `_on_all_trails_set` |
| `_body_list` | `category_active_toggled` | `_on_category_active_toggled` |
| `_body_list` | `category_trail_toggled` | `_on_category_trail_toggled` |
| `_body_list` | `category_name_toggled` | `_on_category_name_toggled` |
| `_sim` | `blow_up_detected` | `_on_blow_up` |
| `_sim` | `collisions_detected` | `_on_collisions` |
| `_date_timer` | `timeout` | `_update_sim_date` |

---

## Key design decisions

1. **Relative-frame trails**: offset baked at `append` time (`pos − center_pos`). When the center changes, all buffers are cleared — old data is in the wrong reference frame.
2. **GIL-safe snapshot**: `latest_snapshot` is a list reference. Python's GIL ensures a reference assignment is atomic. No lock needed for reads.
3. **GPU init deferred to paintGL**: `TrailBuffer.initialize()` requires the GL context to be current. `set_display_info` is called from the Qt main thread outside any GL callback — do not call `initialize()` there.
4. **`elapsed_days` resets automatically**: `_load_system` always creates a fresh `SimulationThread`, so `_elapsed_days` starts at 0. `reset(system)` also explicitly zeroes it.
5. **Log-scale speed**: slider maps to `10^(LOG_MIN + t*(LOG_MAX-LOG_MIN))` days/s. `timescale_changed` always emits float days/s.
6. **Body display size**: physical log-scaled base `[0.0003, 0.003]` AU, floored at `camera.distance * 0.008`. Moons become visible outside parent planets when `camera.distance ≲ 0.1 AU`.
7. **Adaptive physics sub-stepping**: `SolarSystem.step()` computes the minimum pairwise orbital timescale each call and targets ~100 steps per orbit (`max_step = 0.01 * min_t_orb`, clamped `[1e-5, 1.0]` days). Prevents numerical blow-up for tight orbits (moons, close-approach bodies) without a hard-coded step size.
8. **Restart preserves modifications**: `_initial_system` is cloned at every non-restart `_load_system`. Add/edit/remove body operations also update `_initial_system` under `_sim._lock` so restart reproduces the user's manual modifications at the original epoch.
9. **Category controls propagate to initial system**: all per-category bulk operations (`active`, `trail`, `show_name`) mirror their mutations into `_initial_system` so restart is consistent.

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

70 tests across:

- `tests/engine/` — integrator energy conservation, system operations, `simulation_thread` property, adaptive sub-stepping (same-position no-infinite-loop), system cloning.
- `tests/data/` — cache, Horizons client (mocked with `responses`), loader.
- `tests/rendering/` — `TrailBuffer` relative append, reset, ring-wrap; camera; name projection.
- `tests/ui/` — body editor templates and overlap validation; category toggling; interactive body add/edit/remove (thread-safety); restart preserves modifications; blow-up detection.

`tests/conftest.py` provides a session-scoped `QApplication` fixture required for any `QThread` instantiation.

UI tests mock OpenGL via monkeypatching (`GLWidget.initializeGL`, `resizeGL`, `paintGL`, `paintEvent` are all replaced with no-ops) to allow headless execution without a display.

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
- **`BodyListPanel.populate()` may emit `body_selected` on programmatic selection.** `body_selected` is no longer wired to `clear_trails()` directly; it goes to `_on_body_selected` which focuses the camera. Still, be aware that any signal-to-clear-trails wiring on populate would clear on every rebuild.
- **Always mirror body mutations into `_initial_system`.** Every add/edit/remove/toggle operation must duplicate the change into `_initial_system` (under `_sim._lock`) so that `_on_restart()` produces a consistent result.
- **Do not read `SimulationThread._elapsed_days` with a lock.** It is GIL-safe; adding a lock here is incorrect and risks deadlock if called from the physics thread indirectly.
- **`closeEvent` order matters.** Stop `_date_timer` before `_sim.stop_thread()`. Reversing this risks the timer firing after the thread has stopped and `latest_snapshot` is stale or None.
- **Collision detection is per-step, not continuous.** Fast, small bodies can tunnel through each other between `step()` calls without registering a collision. Realistic collisions (into the Sun, or user-placed near-overlapping bodies) are caught. Continuous collision detection is out of scope.
