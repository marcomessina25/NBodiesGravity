# NBodiesGravity

A real-time 3D N-body gravitational simulation of the Solar System, written in Python with PyQt6 and OpenGL. Watch the planets orbit the Sun, zoom in to see the Moon trace its path around Earth, or build your own planetary system from scratch.

![Python](https://img.shields.io/badge/Python-3.12-blue) ![License](https://img.shields.io/badge/License-MIT-green) ![OpenGL](https://img.shields.io/badge/OpenGL-3.3_Core-orange)

---

## Features

### Simulation engine

- N-body gravitational physics using the **Velocity Verlet** integrator
- Physics loop runs in a background QThread at **120 steps/second**, keeping the UI fully responsive
- Time unit: **AU / days** in the Solar System Barycenter (SSB) frame
- Configurable timescale via a log-scale speed slider (1 h/s to 1 y/s)
- **Blow-up detection**: simulation auto-pauses if any body drifts beyond 1000 AU from the origin

### Solar System data

- **Bundled J2000 snapshot** (2000-01-01) — starts instantly with no network connection required
- **20 bodies included**: all 8 planets + Sun; Earth's Moon; the four Galilean moons of Jupiter (Io, Europa, Ganymede, Callisto); Saturn's Titan; Neptune's Triton; dwarf planets Pluto (+ Charon), Eris, and Ceres
- **JPL Horizons integration**: fetch real NASA state vectors for any date via the REST API
- **Local JSON cache** for Horizons results — repeated fetches for the same date are instant

### 3D rendering

- Real-time OpenGL 3.3 Core viewport at ~60 FPS
- Phong-lit UV spheres; stars rendered as emissive (unlit)
- **Per-body colour trails** stored in a ring buffer (last 2000 positions)
- Trails are computed in the **reference frame of the selected center body**, showing the trajectory as seen from that body
- **Camera-distance-proportional display size**: bodies appear small at Solar System zoom and physically scaled when zoomed into a planetary system — moons become visible outside their parent planets at ~0.1 AU

### Control bar

| Control | Description |
|---|---|
| Epoch date picker | Select a start date; fetches state vectors from JPL Horizons with a progress dialog |
| Live simulation date | Shows the current simulated date (YYYY-MM-DD), updated at 4 Hz |
| Play / Pause | Start or pause the physics loop |
| Speed slider | 200-step log scale; 1 s = 1 h (left) to 1 s = 1 y (right); scroll-wheel friendly |
| Center body selector | Sets the camera and trail reference frame; changing it clears all trails |
| Clear Trails | Wipes all trail data immediately |

### Body list panel (left sidebar)

- Lists every body currently in the simulation
- Colour dot per body for quick identification
- Trail toggle checkbox per body
- Click a body to re-center the camera on it
- Edit button to open the body editor for that body

### Body editor dialog (Add / Edit)

The editor provides a full form for every physical parameter:

- **Name**, **mass** (kg), **radius** (km), **colour** (colour picker)
- **Position** (x, y, z in AU) and **velocity** (vx, vy, vz in AU/day)

In **Add** mode, a template selector pre-fills the form:

| Template | Behaviour |
|---|---|
| Blank | All fields at defaults |
| `<body name>` | Pre-fills from that body's current live state; name left empty so you can rename it |
| Average of two… | Body A / Body B pickers; fills all fields with the arithmetic mean of both bodies |

Inline validation is active at all times: the name must be non-empty and unique (in Add mode), mass and radius must be positive. The **OK** button is disabled until all validation passes.

### Menus

| Menu | Actions |
|---|---|
| **File** | New System (reload J2000), Load System… (JSON), Save System… (JSON), Exit |
| **Simulation** | Add Body…, Edit Selected…, Remove Selected |
| **View** | Reset Camera, Toggle All Trails |

### Mouse controls (3D viewport)

| Input | Action |
|---|---|
| Left drag | Orbit camera (azimuth / elevation) |
| Right drag up/down | Zoom in / out |
| Scroll wheel | Zoom in / out |

---

## Installation

### Prerequisites

- [Anaconda](https://www.anaconda.com/) or [Miniconda](https://docs.conda.io/en/latest/miniconda.html)
- GPU supporting **OpenGL 3.3 Core Profile**
- Internet connection *(optional — only needed for non-J2000 dates)*

### Steps

```bash
git clone https://github.com/marcomessina25/NBodiesGravity.git
cd NBodiesGravity
conda env create -f environment.yml
conda activate nbodiesgravity
```

### Run

```bash
# With conda run (no manual activation needed)
conda run -n nbodiesgravity python nbodiesgravity/main.py

# Or after activating the environment
python nbodiesgravity/main.py
```

### Tests

```bash
conda run -n nbodiesgravity pytest tests/ -v
```

The test suite contains 37 tests covering the integrator, body datatypes, JPL Horizons client, cache layer, trail buffer, and simulation thread.

---

## Tech stack

| Component | Library |
|---|---|
| UI framework | PyQt6 |
| 3D rendering | PyOpenGL (OpenGL 3.3 Core) |
| Numerics | NumPy |
| Horizons HTTP client | Requests |
| Language | Python 3.12 |
| Package manager | Conda (`nbodiesgravity` environment) |

---

## Project structure

```
nbodiesgravity/
    engine/
        body.py                  # CelestialBody and BodyState datatypes
        integrator.py            # Velocity Verlet integrator
        system.py                # SolarSystem — step, snapshot, add/remove body
        simulation_thread.py     # QThread physics loop (120 steps/s)
    data/
        cache.py                 # Local JSON cache for Horizons results
        horizons.py              # JPL Horizons REST client
        loader.py                # load_default_system / load_system_at_date
        snapshots/j2000.json     # Bundled J2000 Solar System snapshot
    rendering/
        camera.py                # Orbital camera (azimuth / elevation / distance)
        display_info.py          # Log-scaled display radius per body
        gl_widget.py             # QOpenGLWidget — 60 FPS Phong shading + trails
        sphere_mesh.py           # UV sphere VBO and GLSL shader sources
        trail_buffer.py          # Ring-buffer trail (relative reference frame)
    ui/
        body_editor_dialog.py    # Add / edit body dialog with template selector
        body_list_panel.py       # Left sidebar with trail toggles
        control_panel.py         # Bottom bar: date, speed, center, play/pause
        date_loader_worker.py    # QThread for background JPL Horizons fetch
        main_window.py           # Top-level window and signal wiring
    main.py                      # Entry point
scripts/
    fetch_j2000.py               # One-time script to regenerate j2000.json
    smoke_test_headless.py       # Headless matplotlib orbit plot for quick checks
tests/                           # pytest suite (37 tests)
environment.yml
```

---

## Usage tips

**Observing the Earth–Moon system**
Select **Earth** as the center body and zoom in to roughly **0.1 AU**. The Moon will appear as a distinct body tracing its orbit around Earth.

**Observing Jovian moons**
Select **Jupiter** as the center body and zoom in to roughly **0.5 AU**. Io, Europa, Ganymede, and Callisto will separate from Jupiter's disc. Because the inner Galilean moons orbit Jupiter in just 2–7 days, you need a **slow timescale** (1–7 days/s or less) to watch them trace individual orbits without the motion blurring into a continuous ring of trail. At higher speeds the moons are there, but each orbit completes in a fraction of a second.

**Observing Saturn's moons**
Select **Saturn** as the center body and zoom in to roughly **0.5 AU**. Titan is the most prominent. As with the Jovian system, keep the timescale slow (a few days/s) so Titan's 16-day orbit is visible as a distinct arc rather than a full closed trail rendered instantly.

**Understanding trails**
Trails are reference-frame relative — they show the trajectory as seen from the current center body. Whenever you change the center body, all trails are cleared because the previous frame's data is incompatible with the new reference frame.

**Saving a snapshot**
*File → Save System…* captures the current live positions and velocities, not the original J2000 state. Use this to resume a simulation from a specific point in time.

**Numerical drift at high timescales**
At very high timescales (months or years per second) combined with long run times, integration drift accumulates. This is expected behaviour for a simple Verlet integrator and is not a bug.

---

## License

This project is licensed under the [MIT License](LICENSE).
