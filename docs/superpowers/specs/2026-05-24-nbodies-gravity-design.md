# N-Body Gravity Simulation — Design Spec
**Date:** 2026-05-24  
**Status:** Approved  

---

## Overview

A Python desktop application that computes and displays the gravitational orbits of stars, planets, and satellites in a stellar system. Defaults to the full solar system (Sun, 8 planets, major moons, dwarf planets). Users can add, edit, or remove bodies, pick a start date, choose a reference-frame center, and control simulation speed in real time.

---

## Decisions Log

| Question | Answer |
|---|---|
| Platform | Developer workstation — run from source via `conda run -n nbodiesgravity python main.py` |
| Rendering | Full 3D OpenGL via Qt `QOpenGLWidget` |
| Data sourcing | Bundled J2000 JSON snapshot (default) + optional live JPL Horizons query with local cache |
| Default bodies | Sun, 8 planets, major moons (~15), dwarf planets (Pluto, Eris, Ceres, Charon) — ~25 bodies |
| Orbit trails | Per-body toggleable; history accumulates even when hidden |
| Collisions | Pass-through — no collision detection or merging |

---

## 1. Module Structure

```
nbodiesgravity/
├── main.py                        # Entry point — builds QApplication, wires layers together
├── engine/
│   ├── body.py                    # CelestialBody dataclass
│   ├── integrator.py              # Velocity Verlet integrator (pure NumPy)
│   ├── system.py                  # SolarSystem — owns body list, calls integrator
│   └── simulation_thread.py      # QThread wrapper — steps simulation, emits snapshots
├── data/
│   ├── horizons.py                # JPL Horizons REST API client
│   ├── cache.py                   # Local JSON cache (~/.nbodiesgravity/cache.json)
│   ├── loader.py                  # Assembles SolarSystem from snapshot or API response
│   └── snapshots/
│       └── j2000.json             # Bundled state vectors at J2000 epoch (~25 bodies)
├── ui/
│   ├── main_window.py             # QMainWindow — menus, toolbar, layout
│   ├── control_panel.py           # Date picker, play/pause, time-scale slider, center-on picker
│   ├── body_list_panel.py         # Scrollable body list with trail toggles
│   └── body_editor_dialog.py      # QDialog for add / edit / delete body
└── rendering/
    ├── gl_widget.py               # QOpenGLWidget — owns GL context, drives draw calls at 60 FPS
    ├── camera.py                  # Camera state: center body, azimuth, elevation, zoom
    ├── sphere_mesh.py             # UV-sphere VBO, shared by bodies of equal radius
    └── trail_buffer.py            # Per-body ring-buffer of recent positions → line VBO
```

**Key boundary rule:** `engine/` has zero Qt imports. `rendering/` has zero physics imports — it only reads position snapshots. This allows headless pytest testing of the physics engine.

---

## 2. Physics Engine

### `CelestialBody` (`engine/body.py`)
A dataclass with fields:

| Field | Type | Unit |
|---|---|---|
| `name` | `str` | — |
| `mass` | `float` | kg |
| `pos` | `np.ndarray (3,)` | AU |
| `vel` | `np.ndarray (3,)` | AU/day |
| `radius` | `float` | km (rendering only) |
| `color` | `tuple[float, float, float]` | RGB 0–1 |
| `show_trail` | `bool` | — |

Positions and velocities are always stored in the Solar System Barycenter (SSB) frame.

### `VelocityVerletIntegrator` (`engine/integrator.py`)
Pure NumPy — no Python loops over body pairs. Given `positions: (N,3)` and `masses: (N,)` arrays, computes all pairwise accelerations using broadcasting:

```
a(t)     = Σ G·mj·(rj−ri) / (|rj−ri|² + ε²)^(3/2)   for all j≠i
r(t+dt)  = r(t) + v(t)·dt + 0.5·a(t)·dt²
a(t+dt)  = recompute accelerations at r(t+dt)
v(t+dt)  = v(t) + 0.5·(a(t) + a(t+dt))·dt
```

- `dt` in days
- Softening parameter `ε = 1e-4 AU` prevents singularities at close approaches
- Integrator is stateless — takes arrays in, returns arrays out

### `SolarSystem` (`engine/system.py`)
Owns the list of `CelestialBody` objects. Interface:

- `step(dt: float)` — advances one timestep, updates all `body.pos` / `body.vel` in place
- `snapshot() → list[BodyState]` — returns a lightweight thread-safe copy of current state
- `add_body(body: CelestialBody)` — safe only when simulation is paused
- `remove_body(name: str)` — safe only when simulation is paused

### `SimulationThread` (`engine/simulation_thread.py`)
A `QThread` that runs `system.step(dt)` in a tight loop. Emits `snapshot_ready(list[BodyState])` signal after each step — Qt's signal/slot mechanism handles cross-thread delivery safely.

- `set_timescale(days_per_second: float)` — recalculates `dt = days_per_second / 120` (120 sub-steps/second target)
- `pause()` / `resume()` — thread-safe stop/start
- `reset(system: SolarSystem)` — replaces the system (only callable while paused)
- Auto-pauses and emits `blow_up_detected` if any body position exceeds 1000 AU

---

## 3. Data Layer

### Bundled snapshot (`data/snapshots/j2000.json`)
State vectors for ~25 default bodies at epoch J2000.0 (2000-Jan-01 12:00 TT), pre-fetched from JPL Horizons and committed to the repo.

```json
{
  "epoch": "2000-01-01T12:00:00",
  "bodies": [
    {
      "name": "Sun", "id": "10",
      "mass_kg": 1.989e30, "radius_km": 695700,
      "color": [1.0, 0.9, 0.2],
      "pos_au": [x, y, z],
      "vel_au_per_day": [vx, vy, vz]
    }
  ]
}
```

Default bodies: Sun, Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, Neptune, Moon, Io, Europa, Ganymede, Callisto, Titan, Triton, Pluto, Charon, Eris, Ceres.

### `horizons.py` — JPL API client
Wraps `https://ssd.jpl.nasa.gov/api/horizons.api`. Given a body ID and date, requests a 1-step Vector Table relative to the SSB. Returns a `BodyState` dict. Raises `HorizonsError` on network failure or unexpected response format. Logs full error responses to `~/.nbodiesgravity/horizons_error.log`.

### `cache.py` — local query cache
Reads/writes `~/.nbodiesgravity/cache.json`. Cache key: `"{body_id}_{YYYY-MM-DD}"`. Cache entries never expire. Exposes `clear_cache()` for debugging.

### `loader.py` — system assembly
Two public functions:

- `load_default_system() → SolarSystem` — reads `j2000.json`, builds and returns a `SolarSystem` synchronously (~instant)
- `load_system_at_date(date: datetime, progress_cb: Callable) → SolarSystem` — for each body: cache hit → use cached; cache miss → fetch from JPL → store in cache. Calls `progress_cb(body_name)` after each body for UI progress updates. Designed to run in a `QThread` worker.

---

## 4. UI Layer

### Layout (`main_window.py`)
```
┌─────────────────────────────────────────────────┐
│  Menu: File | Simulation | View | Help           │
│  Toolbar: Play/Pause | Step | Reset              │
├──────────────┬──────────────────────────────────┤
│  Body List   │                                  │
│  Panel       │       GL Viewport (3D)           │
│  (200px)     │                                  │
├──────────────┴──────────────────────────────────┤
│  Control Panel: Date | Speed | Center-on        │
└─────────────────────────────────────────────────┘
```

Menus:
- **File:** New System, Load System (JSON), Save System (JSON), Exit
- **Simulation:** Add Body, Edit Selected Body, Remove Selected Body
- **View:** Reset Camera, Toggle All Trails, Toggle Grid

### `control_panel.py`
- `QDateEdit` for epoch — changing triggers `DateLoaderWorker` in background with progress bar; reverts to last valid date on error
- `QSlider` + `QLineEdit` for time-scale — presets (1s=1day, 1s=1month, 1s=1year) plus free entry; calls `simulation_thread.set_timescale()` immediately
- `QComboBox` for center-on — lists all body names; changing calls `camera.set_center(body_name)`
- Play/Pause button starts/stops `SimulationThread`

### `body_list_panel.py`
Scrollable `QListWidget`. Each row: colored dot + body name + trail `QCheckBox`. Single-click selects and highlights body in viewport. Double-click opens `BodyEditorDialog`. Checkbox state writes directly to `body.show_trail`.

### `body_editor_dialog.py`
Used for both Add and Edit. Fields: Name, Mass (kg), Radius (km), Color (picker), Position x/y/z (AU), Velocity vx/vy/vz (AU/day). Validations: mass > 0, radius > 0, name unique. Simulation is automatically paused on open and can be resumed after OK/Cancel.

---

## 5. Rendering Layer

### `gl_widget.py` — `GLWidget(QOpenGLWidget)`
- `initializeGL()` — compiles two GLSL shader pairs (lit spheres, unlit lines), creates VBOs, enables depth testing, sets black background
- `resizeGL(w, h)` — updates perspective projection matrix (45° FOV)
- `paintGL()` — driven by 60 FPS `QTimer`:
  1. Read `simulation_thread.latest_snapshot` (atomic read)
  2. Update `camera.center_pos` from center body's position
  3. Append new positions to each body's `TrailBuffer`
  4. Draw: grid → trails → spheres → body name labels

Mouse: left-drag = rotate, scroll = zoom, right-drag = pan.

### `camera.py`
State: `center_pos (3,)`, `azimuth`, `elevation`, `distance`.  
`view_matrix()` builds a lookAt matrix with eye orbiting around `center_pos`. The renderer subtracts `center_pos` from all body positions before passing to OpenGL — physics coordinates are never modified.

### `sphere_mesh.py`
UV-sphere (24 stacks × 24 slices). Vertices + normals + indices uploaded to a single VBO on first use. Bodies sharing the same display radius reuse the same mesh; scale is applied via the model matrix uniform. The Sun uses an emissive material in the shader (unaffected by the point light at the Sun's position).

### `trail_buffer.py`
Per-body ring buffer of the last 2000 positions. New position appended each frame; oldest dropped when full. Uploaded to GPU as a line-strip VBO. Buffer accumulates even when `show_trail = False` — toggling trails back on shows full history immediately.

---

## 6. Data Flow

### Startup
```
main.py
  → load_default_system()           # reads j2000.json → SolarSystem (~instant)
  → MainWindow.__init__()           # creates widgets, wires signals/slots
  → SimulationThread.start()        # begins stepping at 1s=1day
  → GLWidget QTimer.start(16ms)     # 60 FPS render loop begins
```

### Date change
```
User picks new date
  → SimulationThread.pause()
  → DateLoaderWorker(QThread).start()
      for each body:
        cache.get() → hit: use vectors
                    → miss: horizons.fetch() → cache.store()
        emit progress_signal(body_name)
  → loader.assemble() → new SolarSystem
  → SimulationThread.reset(new_system)
  → SimulationThread.resume()
```

### Time-scale change
```
User moves speed slider
  → SimulationThread.set_timescale(days_per_second)
  → dt = days_per_second / 120   (120 sub-steps/second)
```

### Render loop (60 FPS)
```
QTimer fires → GLWidget.paintGL()
  → snapshot = simulation_thread.latest_snapshot   (atomic read)
  → camera.center_pos = snapshot[center_body].pos
  → for each body: trail_buffer.append(pos)
  → draw: grid, trails, spheres, labels
```

---

## 7. Error Handling

| Situation | Behaviour |
|---|---|
| JPL Horizons network failure | `HorizonsError` caught in worker; status bar shows warning; date reverts to last valid |
| JPL returns unexpected format | Same as above; full response logged to `~/.nbodiesgravity/horizons_error.log` |
| Body editor: duplicate name | OK disabled; inline red label "Name already exists" |
| Body editor: mass = 0 | OK disabled; inline red label |
| Simulation blow-up (pos > 1000 AU) | `SimulationThread` auto-pauses; status bar warning; user can reset to default |

---

## 8. Testing Strategy

- **`engine/`** — `pytest`, headless (no Qt). Tests: single-body free-fall, two-body circular orbit energy conservation over 1000 steps (energy drift < 0.01%), Moon stability around Earth over 30 simulated days.
- **`data/`** — `pytest` + `responses` (HTTP mock library). Tests: cache hit/miss, JPL response parsing, `HorizonsError` on bad response.
- **UI & rendering** — not unit-tested; validated manually against the four development milestones.

---

## 9. Development Milestones

1. **Headless engine:** Sun + Earth + Moon from `j2000.json`, Verlet integrator, `matplotlib` 2D output. Verify Earth loops Sun, Moon loops Earth.
2. **Rendering core:** `QOpenGLWidget` window, sphere rendering, camera centering logic.
3. **Time & UI controls:** Play/pause, speed slider, date picker with JPL query + cache.
4. **Body editor:** Full Qt UI for add/edit/delete bodies, save/load system JSON.

---

## 10. Dependencies

| Package | Purpose |
|---|---|
| `numpy` | Vectorized physics math |
| `PyQt6` or `PySide6` | UI framework + OpenGL widget |
| `PyOpenGL` | OpenGL bindings |
| `requests` | JPL Horizons HTTP client |
| `pytest` | Headless engine tests |
| `responses` | HTTP mock for data layer tests |
