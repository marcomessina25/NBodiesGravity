# gemini.md — Gemini Developer & AI Context

Developer/AI context file for the N-body Gravity Simulation project. Read at the start of every session to establish system state, constraints, and architecture. This document is optimized for **Gemini** (using the Antigravity agentic coding assistant).

---

## ⚡ Critical Constraints & Environment (Windows / PowerShell)

### 1. Conda Environment Execution
Always execute all Python commands within the `nbodiesgravity` environment using `conda run`. **Never** use bare `python` or `pytest` commands, and **never** attempt to run `conda activate` in the sandboxed terminal.

*   **Run Application:**
    ```powershell
    conda run -n nbodiesgravity python nbodiesgravity/main.py
    ```
*   **Run Tests:**
    ```powershell
    conda run -n nbodiesgravity pytest tests/ -v
    ```

### 2. Version Controls & Dependencies
*   **Stack:** Python 3.12, PyQt6 (6.5+), PyOpenGL, NumPy (pure vectorized calculations), Requests (for JPL Horizons queries), and `responses` (for testing).
*   **Freeze Policy:** Do not introduce new Python or system dependencies without explicit user confirmation. If a new library is approved, update the conda configuration in `environment.yml` immediately.

### 3. Git Branching Policy
Always push directly to the current working branch. If the current branch is `main` or `master`, create a fresh feature branch first, then push to that branch. Never block execution asking the user about branching strategy.

---

## 🌌 Project Overview & Features

An interactive, high-performance 3D N-body gravitational simulation desktop application written in Python, PyQt6, and PyOpenGL. It calculates and visualizes orbital mechanics for stars, planets, and satellites.

### Core Simulation Features
1.  **JPL Horizons Sourcing:** Loads state vectors at a selected epoch date from the JPL Horizons API or falls back to a local query cache (`~/.nbodiesgravity/cache.json`) to prevent duplicate network calls. Comes with a pre-fetched default snapshot of 22 bodies at the J2000 epoch.
2.  **Velocity Verlet Integrator:** A pure NumPy, vectorized N-body integrator using a gravitational softening parameter $\varepsilon = 10^{-4}\text{ AU}$ to prevent infinite acceleration singularities during close encounters.
3.  **Real-Time Simulation Thread:** A physics background thread capped at $500\text{ Hz}$ to synchronize simulated time delta (`sim_dt`) to wall-clock time (`real_dt`) accurately:
    $$\text{sim\_dt} = \text{real\_dt} \times \text{timescale}$$
    It automatically segments large jumps into sub-steps with a cap of $\text{max\_dt} = 1.0\text{ day}$ to preserve integrator accuracy.
4.  **Ultra-Fluid 120 FPS Rendering:** Driven by an 8 ms rendering timer in PyOpenGL, utilizing UV-sphere meshes and Phong lighting/shading models.
5.  **Relative-Frame Orbit Trails:** Visual trails are stored in the frame of reference of the currently followed body (relative offset: $\vec{x}_{\text{trail}} = \vec{x}_{\text{body}} - \vec{x}_{\text{center}}$) and accumulated at append time, ensuring historic trails follow the center body correctly. Trails are cleared on center changes.
6.  **Active/Inactive Toggle:** Bodies can be programmatically deactivated via a checkable list. Inactive bodies are completely excluded from physics integration, do not render, freeze in space, and do not record trails.
7.  **Add Body Templates & Averages:** "Add Body" dialog allows initializing new bodies from blank slates, existing celestial bodies, or an arithmetic average of two chosen template bodies.

---

## 📐 Architecture & Module Map

The codebase is split strictly into standard layers: `engine` (no Qt imports), `rendering` (no physics math imports), `data` (network & file serialization), and `ui` (PyQt widgets and orchestrations).

```
C:\Projects\NBodiesGravity\nbodiesgravity\
├── main.py                        # Application entry point & Qt runner
├── engine/
│   ├── body.py                    # CelestialBody (mutable) & BodyState (immutable snapshot)
│   ├── integrator.py              # Pure NumPy pairwise N-body Velocity Verlet solver
│   ├── system.py                  # SolarSystem — filters active bodies & runs steps
│   └── simulation_thread.py       # Physics runner thread (500Hz loop, wall-clock synchronized)
├── data/
│   ├── cache.py                   # Local query cache implementation
│   ├── horizons.py                # REST API wrapper for JPL Horizons Vector Table queries
│   ├── loader.py                  # Loader to build SolarSystem from snapshot or date queries
│   └── snapshots/
│       └── j2000.json             # Pre-fetched snapshot (22 default bodies)
├── ui/
│   ├── main_window.py             # QMainWindow assembly, wiring hub, and QTimer (4 Hz epoch)
│   ├── control_panel.py           # Play/pause, speed log slider, date edit, clear trails button
│   ├── body_list_panel.py         # Bodies scroll panel with active/trail checkboxes and bulk headers
│   ├── body_editor_dialog.py      # QDialog with template pre-fills & "Average of two" computation
│   └── date_loader_worker.py      # QThread loader for background JPL fetches (progress bar 0 to 22)
└── rendering/
    ├── gl_widget.py               # QOpenGLWidget running rendering cycles at 120 FPS
    ├── camera.py                  # Orbital 3D camera tracker (distance, azimuth, elevation)
    ├── sphere_mesh.py             # UV-sphere mesh vertices & Phong GLSL shader sources
    └── trail_buffer.py            # Ring buffer for relative trail coordinates
```

---

## 🧵 Thread Safety & Threading Rules

The application uses a dual-thread setup: **Main Thread (UI + Rendering)** and **Physics Thread (`SimulationThread`)**. To prevent race conditions and deadlocks, adhere strictly to these rules:

1.  **Reference Assignment Atomicity:** `SimulationThread.latest_snapshot` stores the immutable `list[BodyState]`. Reading/writing this reference is guaranteed atomic under the Python GIL. No lock is needed for the render thread to read it.
2.  **Physics Lock:** `SimulationThread._lock` (a `threading.Lock`) protects all operations inside `SolarSystem.step()` and `system.snapshot()`. Direct manipulation of systems, adding or removing bodies must be guarded by this lock or performed when the thread is paused.
3.  **Timescale and Pause Safety:** `SimulationThread._paused` and `SimulationThread._timescale` are basic primitive types. Re-assigning them is GIL-safe; no lock is required.
4.  **UI Updates:** Never call Qt UI methods or directly manipulate widgets from the background thread. Always communicate from the background thread via Qt Signals (e.g., `snapshot_ready`, `blow_up_detected`, `body_loaded`).

---

## 🔌 Signal/Slot Wiring (MainWindow)

The signal propagation matrix managed in `nbodiesgravity/ui/main_window.py`:

| Source Component | Signal | Target / Slot | Action / Purpose |
| :--- | :--- | :--- | :--- |
| `_ctrl` (ControlPanel) | `date_changed` | `_on_date_changed` | Pauses sim, kicks off background JPL Horizons date query |
| `_ctrl` (ControlPanel) | `timescale_changed` | `_sim.set_timescale` | Updates physics speed immediately (days/sec) |
| `_ctrl` (ControlPanel) | `center_changed` | `_gl.camera.set_center` | Updates the orbital camera focal target |
| `_ctrl` (ControlPanel) | `center_changed` | `_gl.clear_trails` | Clears all orbital trail buffers (since reference frame changed) |
| `_ctrl` (ControlPanel) | `play_toggled` | `_on_play_toggled` | Resumes or pauses the physics loop |
| `_ctrl` (ControlPanel) | `clear_trails_requested`| `_gl.clear_trails` | Flushes all active trail lines |
| `_body_list` (BodyList) | `body_selected` | `_gl.camera.set_center` | Centers the view on the clicked celestial body |
| `_body_list` (BodyList) | `body_selected` | `_gl.clear_trails` | Clears trails to match new focal center reference frame |
| `_body_list` (BodyList) | `body_edit_requested` | `_edit_body` | Pauses sim and displays edit dialog for body |
| `_body_list` (BodyList) | `trail_toggled` | `_on_trail_toggled` | Toggles rendering of the individual body's trail line |
| `_body_list` (BodyList) | `body_active_toggled` | `_on_body_active_toggled`| Flags body as active/inactive in engine, flushes trail if off |
| `_body_list` (BodyList) | `all_bodies_set` | `_on_all_bodies_set` | Bulk activates/deactivates all bodies and updates UI list |
| `_body_list` (BodyList) | `all_trails_set` | `_on_all_trails_set` | Bulk enables/disables all orbital trails and updates UI |
| `_sim` (Simulation) | `blow_up_detected` | `_on_blow_up` | Pauses simulation and alerts user of distance escape (>1000 AU) |
| `_date_timer` (QTimer) | `timeout` | `_update_sim_date` | Updates date label at 4 Hz based on `_sim.elapsed_days` |

---

## 🧪 Testing Guidelines

*   The automated test suite runs **headless** using a session-scoped `QApplication` fixture defined in `tests/conftest.py` to support `QThread` and core Qt widgets.
*   **Run command:** `conda run -n nbodiesgravity pytest tests/ -v`
*   **Engine Tests (`tests/engine/`):**
    *   Verifies energy conservation of 2-body orbits (drift must remain $< 0.01\%$ over 1000 steps).
    *   Verifies orbital stability of the Moon around Earth over 30 days.
    *   Verifies deactivation mechanics: inactive bodies are frozen in space while active ones continue moving.
    *   Verifies reactivating a body resumes its motion normally from its frozen coordinate.
*   **Data Tests (`tests/data/`):**
    *   Verifies JSON cache lookups and storage mechanisms.
    *   Uses `responses` to mock the JPL Horizons API responses.
*   **Rendering Tests (`tests/rendering/`):**
    *   Verifies relative-frame coordinate calculation ($\vec{x}_{\text{trail}} = \vec{x}_{\text{body}} - \vec{x}_{\text{center}}$) inside the trail buffers.
    *   Verifies ring-buffer index wrapping and buffer resets.
    *   Verifies single-body trail resets using `clear_trail_for()`.

---

## ⚠️ Common Pitfalls & High-Risk Areas

1.  **PyOpenGL Context Binding Contexts:** Do not call `TrailBuffer.initialize()` or execute GPU allocations outside the OpenGL rendering cycle (i.e. outside `initializeGL()`, `resizeGL()`, or `paintGL()`). If done outside, PyOpenGL will bind to a garbage/null context, resulting in silent failures (blank rendering) and visual trails not drawing.
2.  **Trail Initialization Deferred:** `TrailBuffer.initialize()` is lazily triggered inside `paintGL()` when `_vao is None` to ensure it runs under a correct OpenGL thread context. Maintain this design pattern.
3.  **Race Conditions on Load:** In `MainWindow._load_system()`, always clear trails (`self._gl.clear_trails()`) **before** starting the physics simulation thread (`_sim.start()`). If reversed, the physics thread might append fresh points to the trail buffer before they are wiped, resulting in line artifacts.
4.  **Timer Cleanup in closeEvent:** When closing the UI, the `_date_timer` must be stopped (`self._date_timer.stop()`) **before** stopping the physics thread (`_sim.stop_thread()`). Swapping this order will crash the app when the timer fires on a stopped, partially-destroyed physics thread.
5.  **Softening Parameter $\varepsilon$:** When rewriting the NumPy integrator or adding new mathematical models, keep the softening value $\varepsilon = 10^{-4}\text{ AU}$ active in pairwise distance divisions to handle close orbital flybys smoothly.
6.  **Real-Time Loop Cap:** The real-time synchronization in `SimulationThread.run()` caps time steps at 50 ms. This prevents the "spiral of death" (where long frames cause huge time steps, causing more computational workload, leading to even longer frames). Keep this cap in place.

---

## 🛠️ Gemini Agentic Workflow (Planning Mode)

When performing complex edits or feature additions with **Gemini**, leverage standard Planning Mode behaviors:

1.  **Research:** Use `view_file`, `list_dir`, and `grep_search` to map dependencies. Do not make code modifications in this phase.
2.  **Implementation Plan:** For tasks requiring multiple file modifications, write or update the `implementation_plan.md` artifact under the current conversation directory. Outline proposed changes precisely with file targets:
    *   `[MODIFY] file_name`
    *   `[NEW] file_name`
    *   `[DELETE] file_name`
    Specify how you will test and verify the change, then await explicit user approval.
3.  **Checklist Execution:** Create a `task.md` document to track execution steps (`[ ]` uncompleted, `[/]` in progress, `[x]` completed). Keep it updated as files are written.
4.  **Verification & Walkthrough:** Verify changes by running the test suite (`conda run -n nbodiesgravity pytest tests/ -v`) and compile a brief, readable summary in `walkthrough.md` with results.
