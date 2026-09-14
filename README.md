# NBodiesGravity

A real-time 3D N-body gravitational simulation of the Solar System, written in Python with PyQt6 and OpenGL. Watch the planets orbit the Sun, zoom in to see the Moon trace its path around Earth, category-toggle active states and trails, or build your own planetary system from scratch.

![Version](https://img.shields.io/badge/Version-0.8.0-purple) ![Python](https://img.shields.io/badge/Python-3.12-blue) ![License](https://img.shields.io/badge/License-MIT-green) ![OpenGL](https://img.shields.io/badge/OpenGL-3.3_Core-orange)

---

## Features

### Simulation Engine & High-Performance Numerics

- N-body gravitational physics using the **Velocity Verlet** integrator with a gravitational softening parameter $\varepsilon = 10^{-4}\text{ AU}$ to handle close flybys smoothly.
- **Optimized $O(N^2)$ Pairwise Vectorization**: In-place distance scaling and einsum contractions eliminate intermediate NumPy allocations, achieving **2.2x to 9.6x speedups** with bit-level mathematical equivalence ($< 10^{-15}$ relative error).
- **Substep Acceleration Reuse**: Reuses end-of-step acceleration vectors across consecutive Velocity Verlet substeps, halving expensive pairwise force evaluations in multi-substep integration.
- **Upper-Triangle Adaptive Timestepping**: Vectorized timescale calculations using upper-triangle indices without full-matrix temporaries or diagonal masking overhead.
- **Adaptive Timestep Control (`TimeStepConfig`)**: Enforces explicit minimum and maximum bounds ($10^{-5}$ to $1.0$ day), targets $\approx 100$ substeps per shortest orbital period, and caps maximum substeps per tick (10,000) to prevent unbounded loops on pathological systems.
- **Scientific Diagnostics & Orbital Analysis**: Real-time interactive laboratory (`Ctrl+D`) displaying conserved quantities, normalized drift rates, osculating Keplerian orbital elements ($a, e, i, \Omega, \omega, \nu, r_p, r_a, T$), Hill sphere gravitational parent detection, live embedded Matplotlib drift charts, and CSV/JSON export.
- **Drift Tolerance Status Badges**: Visual indicators (`PASS` in green, `WARN` in amber, `ALERT` in red) for energy, linear momentum, angular momentum, and center of mass conservation drift against documented scientific thresholds.
- **Time-Window Selection & Plot Decimation**: Selectable historical view windows (All Retained History, Last 100 Days, Last 365 Days) with automatic plot decimation to guarantee responsive UI interactions regardless of buffer depth.
- **Numerical Integrity Protection**: Halts simulation safely upon detecting non-finite coordinates, velocities, accelerations, invalid timesteps, or extreme single-step displacements, strictly preserving the last known valid state.
- **Center-of-Mass Conserving Mergers**: Inelastic collisions where larger masses absorb smaller bodies, strictly conserving total mass, linear momentum, center of mass, and equal-density volume.
- **Decoupled Snapshot Architecture**: 500 Hz physics loop decoupled from rendering via throttled 120 Hz immutable snapshots, eliminating heap contention and GIL-safe state sharing.
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
| Restart | Instantly restarts the simulation from the initial loaded epoch (returns to the initial state of the loaded system, not to the state immediately preceding a collision) |
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

## Roadmap & Specifications

NBodiesGravity follows Semantic Versioning (`MAJOR.MINOR.PATCH`):

- **[Master Development Roadmap](docs/roadmap.md)**: Release plan and architectural principles across releases:
  - **v0.5.0**: State consistency, transactional epoch loading, full persistence round-trip, star classification.
  - **v0.6.0**: Numerical robustness, safe timestep limits, conservation metrics, deterministic benchmarks, and fixed-step O(dt²) convergence validation.
  - **v0.7.0**: Scientific diagnostics, orbital element analysis, physical plotting, and data export.
  - **v0.8.0** *(current)*: Performance profiling, memory optimization, and scalability characterization.
  - **v0.9.0**: Advanced integrators, custom presets, and simulation checkpoints.
  - **v1.0.0**: Stable, validated scientific baseline.
- **[Numerical Model & Validation Specification](docs/numerical_model.md)**: Mathematical formulations, softening potential, symplectic semantics, and validation methodology.
- **[v0.5.0 Specification](docs/specs/v05.md)**: Detailed plan and acceptance checklist for v0.5.0.
- **[v0.6.0 Specification](docs/specs/v06.md)**: Detailed plan and acceptance criteria for v0.6.0.
- **[v0.7.0 Specification](docs/specs/v07.md)**: Detailed plan and acceptance criteria for v0.7.0.
- **[v0.8.0 Specification](docs/specs/v08.md)**: Performance profiling, benchmarks, and scalability specification.
- **[v0.9.0 Specification](docs/specs/v09.md)**: Advanced simulation capabilities specification.

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

### Run Application

```bash
# With conda run (no manual activation needed)
conda run -n nbodiesgravity python nbodiesgravity/main.py

# Or after activating the environment
python nbodiesgravity/main.py
```

### Automated Tests & Numerical Benchmarks

```bash
# Run the complete test suite (engine, data, rendering, ui, validation)
conda run -n nbodiesgravity pytest tests/ -v

# Run the headless numerical benchmarking tool
conda run -n nbodiesgravity python scripts/benchmark_engine.py --benchmark earth_sun --years 1.0
conda run -n nbodiesgravity python scripts/benchmark_engine.py --all

# Run the synthetic N-body scalability benchmark across body counts
conda run -n nbodiesgravity python scripts/benchmark_scalability.py
```

The comprehensive automated test suite covers the integrator, collisions, body datatypes, JPL Horizons client, cache layer, camera panning and top view, rendering name projections, trail buffers, category controls, transactional date loading, persistence round-tripping, timestep configuration, numerical failure detection, deterministic physical benchmarks with fixed-step second-order O(dt²) convergence verification, and performance regression assertions.

---

## Performance & Scalability

NBodiesGravity v0.8.0 delivers an optimized, memory-efficient vectorized $O(N^2)$ Velocity Verlet physics engine with zero compromise to numerical accuracy ($< 10^{-15}$ relative error):

- **In-place Pairwise Accelerations**: Distance scaling and einsum contractions eliminate intermediate NumPy allocations, cutting single-step time by 2.2x to 9.6x.
- **Verlet Substep Acceleration Reuse**: Halves pairwise acceleration evaluations across consecutive substeps during adaptive timestepping.
- **Upper-Triangle Adaptive Timestepping**: Vectorized timescale evaluation avoiding full-matrix temporaries.
- **Decoupled 120 Hz Snapshot Cadence**: Throttles snapshot allocations to the render rate, keeping the 500 Hz physics loop unburdened.
- **Cached OpenGL Shader Uniforms & Horizons I/O**: Eliminates redundant GPU uniform queries and disk reads.

### Scalability Benchmark Results (v0.8.0 Baseline)

Measured on Windows 11 / Python 3.12 / NumPy 2.x via `scripts/benchmark_scalability.py`:

| N Bodies | Steps/s (Pure) | Substeps/s | 50-Step Wall Time | Diag Overhead | Snap Overhead | Peak Mem (KB) |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **2** | 2,296.3 | 4,592.5 | 13.1 ms | < 1% | < 1% | 12.1 KB |
| **10** | 2,103.2 | 4,206.3 | 14.3 ms | < 1% | 1.4% | 17.8 KB |
| **39 (Solar System)** | 40.0 | 8,307.6 | 749.9 ms | < 1% | < 1% | 127.6 KB |
| **100** | 706.8 | 1,413.7 | 42.4 ms | < 1% | 7.1% | 496.7 KB |
| **250** | 116.2 | 232.4 | 258.2 ms | 6.7% | < 1% | 2,758.5 KB |
| **500** | 25.7 | 67.8 | 1,165.9 ms | 10.3% | 2.7% | 10,882.8 KB |

*Note: For the 39-body Solar System, the presence of closely orbiting moons (e.g. Jovian and Saturnian satellites) activates adaptive substeps (~200 substeps per day step), resulting in 8,307.6 substeps/s.*

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
docs/
    numerical_model.md           # Mathematical formulations, softening, and validation methodology
    roadmap.md                   # Master multi-release development roadmap
    specs/
        v05.md                   # v0.5.0 implementation specification
        v06.md                   # v0.6.0 numerical robustness specification
        v07.md                   # v0.7.0 scientific diagnostics and orbital analysis specification
        v07_items_left.md        # v0.7.0 pre-PR checklist and verification tracking
        v08.md                   # v0.8.0 performance and scalability specification
        v09.md                   # v0.9.0 advanced simulation capabilities specification
nbodiesgravity/
    engine/
        benchmarks.py            # Canonical deterministic benchmarks A through F
        body.py                  # CelestialBody (mutable) and BodyState (immutable snapshot)
        diagnostics.py           # Reusable scientific conservation metrics and DiagnosticsHistoryBuffer
        exceptions.py            # NumericalIntegrityError and budget exceptions
        integrator.py            # Vectorized pairwise Velocity Verlet integrator with softening
        orbital_elements.py      # Pure-NumPy Keplerian orbital elements solver and primary detection
        system.py                # SolarSystem — step, snapshot, TimeStepConfig, collision resolution
        simulation_thread.py     # QThread physics loop (500 Hz loop, real-time synchronized)
    data/
        cache.py                 # Local JSON cache for Horizons results
        export.py                # Scientific data export (CSV and JSON for conservation and orbital elements)
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
        diagnostics_dialog.py    # Non-modal scientific diagnostics, live Matplotlib plots, and export dialog
        main_window.py           # Top-level window assembly and signal wiring
    main.py                      # Entry point
scripts/
    benchmark_engine.py          # Headless benchmarking and conservation reporting tool
    benchmark_scalability.py     # Synthetic N-body scaling and component overhead benchmark tool
    compare_convergence.py       # Adaptive vs. fixed timestep convergence characterization
    fetch_j2000.py               # One-time script to regenerate j2000.json
    profile_engine.py            # Detailed per-component physics profiler
    smoke_test_headless.py       # Headless matplotlib orbit plot for quick checks
tests/
    data/                        # Horizons client, cache, and CSV/JSON export tests
    engine/                      # Integrator, system, orbital elements, diagnostics history, collisions, and timestep tests
    rendering/                   # OpenGL, camera, shaders, and trail buffer tests
    ui/                          # PyQt widget, diagnostics panel, transaction, and persistence tests
    validation/                  # Physical conservation, benchmarks A-F, convergence, and softening tests
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

**Collisions and restart policy**
Restart returns to the initial state of the loaded system, not to the state immediately preceding a collision.

**Numerical drift at high timescales**
At very high timescales (months or years per second) combined with long run times, integration drift accumulates. This is expected behaviour for a simple Verlet integrator and is not a bug.

---

## License

This project is licensed under the [MIT License](LICENSE).
