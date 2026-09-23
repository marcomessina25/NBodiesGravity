# NBodiesGravity v1.0 — Getting Started & User Guide

Welcome to **NBodiesGravity**, an interactive, real-time 3D N-body gravitational simulation of the Solar System and orbital mechanics.

---

## 1. Quick Start

### Installation
Ensure you have Conda installed (Anaconda or Miniconda):

```bash
git clone https://github.com/marcomessina25/NBodiesGravity.git
cd NBodiesGravity
conda env create -f environment.yml
conda activate nbodiesgravity
```

### Running the Simulator
```bash
# Direct run via conda
conda run -n nbodiesgravity python nbodiesgravity/main.py

# Or after activating the conda environment
python nbodiesgravity/main.py
```

The simulator opens immediately with the bundled **J2000 snapshot** (39 standard celestial bodies as of January 1, 2000). No internet connection is needed for startup.

---

## 2. Interface Overview

The interface consists of three primary interaction zones:
1. **3D OpenGL Viewport** (center): Renders celestial bodies as illuminated UV spheres with orbit trails and projected 3D name overlays.
2. **Category & Body List Sidebar** (left): Granular and bulk controls for active physics simulation, visual trails, and name visibility.
3. **Control Bar** (bottom): Play/pause, discrete stepping, speed slider, reference frame selector, top-view alignment, and epoch date selection.

```
+-----------------------------------------------------------------------------------+
| Menu: File | Simulation | View                                                    |
+---------------------+-------------------------------------------------------------+
| Category Controls   |                                                             |
| [x] Stars           |                                                             |
| [x] Planets         |                                                             |
| [x] Moons           |                      3D OpenGL Viewport                     |
| [x] Dwarf Pl.       |                                                             |
| [x] Asteroids       |                                                             |
|                     |                                                             |
| Body List           |                                                             |
| * Sun               |                                                             |
| * Earth             |                                                             |
| * Moon              |                                                             |
| ...                 |                                                             |
+---------------------+-------------------------------------------------------------+
| Date | [Play/Pause] [Step] [Restart] | Speed Slider | Center Body | [Top View] ...|
+-----------------------------------------------------------------------------------+
```

---

## 3. 3D Camera Navigation

| Interaction | Action |
|---|---|
| **Left Click + Drag** | Orbit camera around current focal center (azimuth and elevation). |
| **Right Click + Drag** | Pan target offset perpendicular to camera look direction (pan velocity automatically scales with zoom). |
| **Scroll Wheel** | Smooth zoom in and out. |
| **Top View Button** | Aligns camera directly along the positive Z-axis looking down onto the orbital plane. Immune to gimbal lock. |
| **Reset Camera (`View → Reset Camera`)** | Restores default distance and orientation. |

---

## 4. Simulation Controls

- **Play / Pause (`Space`)**: Toggles real-time physics integration in the background thread (500 Hz).
- **Step Once (`F10` or "Step" button)**: When paused, advances physics by a single discrete timestep and updates rendering immediately.
- **Restart**: Restores the simulation to the initial loaded epoch and initial coordinates of the loaded system.
- **Speed Slider**: Logarithmic timescale control ranging from $1\text{ second} = 1\text{ hour}$ (far left) to $1\text{ second} = 1\text{ year}$ (far right).
- **Center Body Selector**: Sets the focal center of the camera and the relative reference frame for orbital trails.
  > *Note*: Changing the center body flushes existing trails because trails are calculated relative to the currently followed body ($\vec{x}_{\rm trail} = \vec{x}_{\rm body} - \vec{x}_{\rm center}$).

---

## 5. Analytical Initial-Condition Presets

Access via **File → Load Preset…**:

1. **Circular Two-Body**: Two equal stellar masses in mutual circular orbit at 1 AU with exact orbital velocity $v_0 = \sqrt{G(m_1+m_2)/r}$.
2. **Eccentric Two-Body**: Two masses in a Keplerian orbit with eccentricity $e = 0.5$ and analytical vis-viva periapsis velocity.
3. **Oriented Two-Body**: Keplerian two-body system arbitrarily inclined and rotated in 3D space ($i=45^\circ, \Omega=30^\circ, \omega=60^\circ$).
4. **Earth-Moon**: Geocentric Earth-Moon system initialized in dynamical equilibrium.
5. **Binary Star**: Equal-mass binary stars revolving around their mutual barycenter.
6. **Restricted Three-Body (Lagrange)**: Circular restricted model with primaries and a numerically negligible test particle placed at analytical triangular Lagrange points $L_4$ or $L_5$.

---

## 6. Saving, Loading & Checkpoints

- **Save / Load System (`File → Save System…` / `File → Load System…`)**: Saves current live positions, velocities, masses, and configurations in standard JSON format.
- **Save / Load Checkpoint (`File → Save Checkpoint…` / `File → Load Checkpoint…`)**: Saves a deterministic `SimulationCheckpoint` capturing exact IEEE-754 double-precision state, elapsed simulated time, and physical configurations for reproducible continuation.

---

## 7. Scientific Diagnostics (`Ctrl+D`)

Open the Scientific Diagnostics Laboratory via **View → Scientific Diagnostics…** or pressing `Ctrl+D`:
- **Active Model Metadata**: Displays current numerical integrator (e.g. Velocity Verlet [Validated Baseline] or Leapfrog [Alternative]), softening length, and collision policy.
- **Conservation Drift Status**: Visual badges (`PASS`, `WARN`, `ALERT`) measuring relative energy drift, normalized linear momentum drift, angular momentum drift, and center-of-mass shift.
- **Live Matplotlib Plots**: Visualizes historical drift trends with selectable time windows (All History, Last 100 Days, Last 365 Days) and automatic decimation.
- **Keplerian Orbital Elements**: Computes instantaneous osculating semi-major axis ($a$), eccentricity ($e$), inclination ($i$), longitude of ascending node ($\Omega$), argument of periapsis ($\omega$), true anomaly ($\nu$), and orbital period ($T$) relative to detected primary masses.
- **Export**: Exports recorded conservation telemetry and orbital elements to CSV or JSON.
