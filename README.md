# NBodiesGravity

A real-time 3D N-body gravitational simulation of the Solar System, written in Python with PyQt6 and OpenGL. Watch the planets orbit the Sun, zoom in to see the Moon trace its path around Earth, category-toggle active states and trails, or build your own planetary system from scratch.

![Python](https://img.shields.io/badge/Python-3.12-blue) ![License](https://img.shields.io/badge/License-MIT-green) ![OpenGL](https://img.shields.io/badge/OpenGL-3.3_Core-orange)

---

## Features

### Simulation Engine

- N-body gravitational physics using the **Velocity Verlet** integrator with a gravitational softening parameter $\varepsilon = 10^{-4}\text{ AU}$ to handle close flybys smoothly.
- Physics loop runs in a background QThread at **500 Hz**, keeping the UI fully responsive and fluid.
- Time unit: **AU / days** in the Solar System Barycenter (SSB) frame.
- Configurable timescale via a log-scale speed slider (1 h/s to 1 y/s).
- **Blow-up detection**: simulation auto-pauses if any body drifts beyond 1000 AU from the origin.

### Solar System Data & Classifications

- **Bundled J2000 snapshot** (2000-01-01) — starts instantly with no network connection required.
- **39 standard bodies included**:
  - **Stars**: Sun.
  - **Planets**: Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, Neptune.
  - **Moons**: Moon, Io, Europa, Ganymede, Callisto, Titan, Triton, Charon, Titania, Rhea, Oberon, Iapetus, Umbriel, Ariel, Dione, Enceladus, Mimas, Miranda, Tethys.
  - **Dwarf Planets**: Pluto, Eris, Ceres, Haumea, Makemake, Gonggong, Quaoar, Sedna, Orcus, Vauna.
  - **Asteroids**: Vesta.
- **JPL Horizons integration**: fetch real NASA state vectors for any date via the REST API.
- **Local JSON cache** for Horizons results — repeated fetches for the same date are instant.

### 3D Rendering & Camera Navigation

- Real-time OpenGL 3.3 Core Profile viewport at a fluid ~120 FPS.
- Phong-lit UV spheres; stars rendered as emissive (unlit).
- **Per-body colour trails** stored in a ring buffer (last 2000 positions).
- Trails are computed in the **reference frame of the selected center body**, showing the trajectory as seen from that body.
- **Camera-distance-proportional display size**: bodies appear small at Solar System zoom and physically scaled when zoomed into a planetary system — moons become visible outside their parent planets at ~0.1 AU.
- **Dynamic Moon Radius Scaling**: Moons are scaled down by a factor of 10 to keep system representations proportioned correctly (whilst preserving Charon's realistic size proportions as Pluto's binary partner).
- **Advanced Camera Navigation**:
  - **Left Drag**: Orbit camera (azimuth / elevation).
  - **Right Drag**: Pan target offset perpendicular to camera look direction, with translation velocity dynamically scaled by zoom factor.
  - **Scroll Wheel**: Smooth camera zoom.
  - **Top View Button**: Conveniently aligns the camera perpendicular to the orbital plane looking straight down along the Z-axis, completely stable and immune to gimbal lock.

### Control Bar (Bottom Panel)

| Control | Description |
|---|---|
| Epoch date picker | Select a start date; fetches state vectors from JPL Horizons with a dynamic progress bar |
| Live simulation date | Shows the current simulated date (YYYY-MM-DD), updated at 4 Hz |
| Play / Pause | Start or pause the physics loop |
| Restart | Instantly restarts the simulation from the initial loaded epoch |
| Speed slider | 200-step log scale; 1 s = 1 h (left) to 1 s = 1 y (right); scroll-wheel friendly |
| Center body selector | Sets the camera and trail reference frame; changing it resets camera panning and clears trails |
| Top View | Instantly aligns view angle looking straight down from the Z-axis, centered on target |
| Clear Trails | Wipes all trail data immediately |

### Side Panel (Left Sidebar)

- **Category Controls Grid**:
  - Column actions for **Act** (Active), **Trl** (Trail), and **Nam** (Name).
  - Categorized rows for **Stars**, **Planets**, **Moons**, **Dwarf Pl.**, and **Asteroids**.
  - Bulk actions toggle active simulation, trail lines, or 3D name overlays for all bodies under that label at once.
  - **Two-way Synchronization**: Category checkboxes dynamically update during population to reflect actual body configurations.
- **Individual Bodies Scroll List**:
  - Color dot indicators for quick identification.
  - Granular trail and active checkboxes per body.
  - **Selective Focus**: Single-click a body name to center the camera focal target on it without changing the reference coordinate center or resetting trails.
  - Double-click a body name to open the body editor.

### Body Editor Dialog (Add / Edit)

The editor provides a full form for every physical parameter:

- **Name**, **Label** (star, planet, moon, dwarf planet, asteroid), **mass** (kg), **radius** (km), **colour** (colour picker).
- **Position** (x, y, z in AU) and **velocity** (vx, vy, vz in AU/day).

In **Add** mode, a localized template selector allows pre-filling the form separately for each feature:

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
| **View** | Reset Camera, Top View, Toggle All Trails, Show/Hide Body Names |

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

The comprehensive test suite contains **61 tests** covering the integrator, body datatypes, JPL Horizons client, cache layer, camera panning and top view, rendering name projections, trail buffers, and PyQt UI category controls.

---

## Tech Stack

| Component | Library |
|---|---|
| UI framework | PyQt6 |
| 3D rendering | PyOpenGL (OpenGL 3.3 Core) |
| Numerics | NumPy |
| Horizons HTTP client | Requests |
| Language | Python 3.12 |
| Package manager | Conda (`nbodiesgravity` environment) |

---

## Project Structure

```
nbodiesgravity/
    engine/
        body.py                  # CelestialBody (mutable) and BodyState (immutable snapshot)
        integrator.py            # Vectorized pairwise Velocity Verlet integrator
        system.py                # SolarSystem — step, snapshot, add/remove body
        simulation_thread.py     # QThread physics loop (500 Hz loop, real-time synchronized)
    data/
        cache.py                 # Local JSON cache for Horizons results
        horizons.py              # JPL Horizons REST client
        loader.py                # load_default_system / load_system_at_date
        snapshots/j2000.json     # Bundled J2000 snapshot (39 standard bodies)
    rendering/
        camera.py                # 3D Camera (azimuth / elevation / distance / panning)
        display_info.py          # Log-scaled display radius per body
        gl_widget.py             # QOpenGLWidget — 120 FPS Phong shading + trails
        sphere_mesh.py           # UV sphere VBO and GLSL shader sources
        trail_buffer.py          # Ring-buffer trail (relative reference frame)
    ui/
        body_editor_dialog.py    # Add / edit body dialog with template and average selector
        body_list_panel.py       # Sidebar with Category Controls and body list
        control_panel.py         # Bottom control bar: date, speed, center, top view, play/pause
        date_loader_worker.py    # QThread for background JPL Horizons fetch
        main_window.py           # Top-level window assembly and signal wiring
    main.py                      # Entry point
scripts/
    fetch_j2000.py               # One-time script to regenerate j2000.json
    smoke_test_headless.py       # Headless matplotlib orbit plot for quick checks
tests/                           # pytest suite (61 tests)
environment.yml
```

---

## Usage Tips

**Observing the Earth–Moon system**
Select **Earth** as the center body and zoom in to roughly **0.1 AU**. The Moon will appear as a distinct body tracing its orbit around Earth.

**Observing Jovian moons**
Select **Jupiter** as the center body and zoom in to roughly **0.5 AU**. Io, Europa, Ganymede, and Callisto will separate from Jupiter's disc. Keep the timescale slow (1–7 days/s or less) to watch them trace individual orbits.

**Observing Saturn's moons**
Select **Saturn** as the center body and zoom in to roughly **0.5 AU**. Watch Titan orbit Saturn at slow timescales.

**Understanding trails**
Trails are reference-frame relative — they show the trajectory as seen from the current center body. Whenever you change the center body, all trails are cleared because the previous frame's data is incompatible with the new reference frame.

**Saving a snapshot**
*File → Save System…* captures the current live positions and velocities, not the original J2000 state. Use this to resume a simulation from a specific point in time.

**Numerical drift at high timescales**
At very high timescales (months or years per second) combined with long run times, integration drift accumulates. This is expected behaviour for a simple Verlet integrator and is not a bug.

---

## License

This project is licensed under the [MIT License](LICENSE).
