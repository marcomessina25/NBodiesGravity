# NBodiesGravity v1.0 — Troubleshooting & FAQ

This guide provides troubleshooting solutions and technical explanations for common questions encountered when running NBodiesGravity.

---

## 1. Simulation Dynamics & Numerical Drift

### Why does my orbit show energy drift at high timescales?
**Cause**:
The simulation thread advances physical time proportional to wall-clock time multiplied by the speed slider setting ($\text{sim\_dt} = \text{real\_dt} \times \text{timescale}$). At extreme timescales (e.g. months or years per second), large time deltas are subdivided into smaller internal substeps (governed by `TimeStepConfig.max_dt = 1.0` day). While the Velocity Verlet integrator is second-order, truncation error naturally accumulates over hundreds of simulated orbits.

**Remedy**:
1. Reduce the simulation speed slider to slower timescales ($1\text{ s} = 1\text{ day}$ to $1\text{ week}$).
2. For high-eccentricity flybys, decrease `max_dt` or `safety_factor` via `TimeStepConfig` (e.g. `safety_factor=0.005`).
3. Check the **Scientific Diagnostics** dialog (`Ctrl+D`) to inspect relative drift metrics against theoretical thresholds.

---

## 2. Computational Budget & Numerical Integrity Errors

### What does `ComputationalBudgetExceededError` mean?
**Cause**:
When two bodies experience an ultra-close encounter or a tightly bound orbit, the adaptive timestepping algorithm dynamically reduces the integration step size $\Delta t$ to resolve the shortest orbital period ($T \approx 2\pi \sqrt{r^3 / GM}$). If resolving an outer step requires more than `TimeStepConfig.max_substeps` (default: 10,000 substeps), the engine raises `ComputationalBudgetExceededError` to prevent freezing the application.

**Remedy**:
- The simulation automatically preserves the last valid state before the error.
- If you intend to simulate dense clusters with frequent close flybys, increase `max_substeps` or activate inelastic collision merging (`CollisionConfig.enabled = True`) to merge bodies before singular approach.

### What causes a "Blow-Up Detected" auto-pause?
**Cause**:
If any active body's position expands beyond $1000\text{ AU}$ from the Solar System Barycenter origin or produces NaN/Inf values, the engine halts the simulation to prevent graphical corruption and memory instability.

**Remedy**:
- Check body initial velocities. Unbound bodies with hyperbolic escape velocities will trigger this threshold once they reach deep interstellar space ($> 1000\text{ AU}$).

---

## 3. OpenGL Viewport & Graphics

### The viewport is completely black or crashes on startup
**Cause**:
NBodiesGravity requires a graphics context supporting **OpenGL 3.3 Core Profile** (GLSL 3.30). Virtual machines, remote desktop connections, or legacy GPU drivers without OpenGL 3.3 support may fail during shader compilation or VAO creation.

**Remedy**:
1. Update your GPU display drivers (NVIDIA, AMD, or Intel).
2. On Windows systems with dual GPUs (integrated Intel and dedicated NVIDIA/AMD), ensure Windows Graphics Settings runs `python.exe` on the high-performance GPU.
3. If running inside a virtual machine, enable 3D hardware acceleration in hypervisor settings.

### Why do trails disappear when I change the Center Body?
**Explanation**:
Orbital trails are recorded in the **relative reference frame** of the currently selected focal body:
$$\vec{x}_{\rm trail}(t) = \vec{x}_{\rm body}(t) - \vec{x}_{\rm center}(t)$$
Because trail history recorded relative to the Sun is mathematically incompatible with history relative to Earth, the trail ring buffer must be cleared whenever the reference body changes to avoid drawing visual artifacts across the screen.

---

## 4. JPL Horizons & External Data

### How do I use the simulator offline?
NBodiesGravity comes bundled with a verified **J2000 snapshot** containing all 39 standard bodies (Sun, planets, moons, dwarf planets, and asteroids) as of January 1, 2000. It requires zero network connectivity on startup.

### JPL Horizons query times out or returns an error
**Cause**:
Network firewalls, proxy environments, or NASA server maintenance can interrupt REST API requests.

**Remedy**:
1. Check your internet connection.
2. NBodiesGravity maintains a local cache at `~/.nbodiesgravity/cache.json`. Any date previously queried is stored permanently and retrieved instantaneously without network access.
3. If a request is interrupted, click **Cancel** in the progress dialog. The simulator will gracefully revert to the previous valid epoch.

---

## 5. Persistence & Checkpoint Compatibility

### Can I load save files created with earlier versions of NBodiesGravity?
Yes. NBodiesGravity v1.0 implements a comprehensive backward-compatibility migration layer:
- Legacy v0.5 JSON saves (with `position`, `velocity`, `radius`, and `color` keys) load smoothly and initialize with validated Velocity Verlet defaults.
- v0.8 saves (with `format_version=1`) preserve body visibility, trails, and labels.
- v0.9 and v1.0 saves preserve full physical configurations (`PhysicsConfig`, `IntegratorConfig`, and `CollisionConfig`).
- Schema version 1 and 2 simulation checkpoints restore coordinates and velocities with IEEE-754 double-precision accuracy.
