# NBodiesGravity Numerical Model & Validation Specification

This document provides the formal mathematical and numerical specifications for NBodiesGravity v1.0.0+, documenting physical units, force models, integration semantics, collision mechanics, conservation diagnostics, and validation methodologies.

---

## 1. Units and Coordinate Reference Frame

NBodiesGravity operates directly in astrodynamical units:

| Dimension | Unit | Definition |
|---|---|---|
| **Length / Position** | Astronomical Unit ($\text{AU}$) | $1\text{ AU} = 1.495978707 \times 10^{11}\text{ m}$ |
| **Time** | Julian Day ($\text{day}$) | $1\text{ day} = 86,400\text{ s}$ |
| **Mass** | Kilogram ($\text{kg}$) | Standard SI kilogram |
| **Velocity** | $\text{AU} / \text{day}$ | $1\text{ AU/day} \approx 1,731.4568\text{ km/s}$ |
| **Acceleration** | $\text{AU} / \text{day}^2$ | $1\text{ AU/day}^2 \approx 20.04\text{ m/s}^2$ |

### Gravitational Constant $G$
In the internal system of units:
$$G = 6.674 \times 10^{-11} \times \frac{(86,400)^2}{(1.495978707 \times 10^{11})^3} \approx 1.488136 \times 10^{-34}\text{ AU}^3\text{ kg}^{-1}\text{ day}^{-2}$$

### Reference Frame
All physical coordinates and velocities are represented in the **Solar System Barycenter (SSB)** inertial frame. The coordinate origin corresponds to the center of mass of the Solar System. Visual orbital trails and camera navigation may be mapped to a designated body-centric reference frame at display time, but the physical integrator operates exclusively in the SSB frame.

---

## 2. Gravitational Force & Softening Model

### 2.1 Gravitational Acceleration
The gravitational acceleration experienced by body $i$ due to all other active bodies $j \neq i$ uses Newtonian pairwise gravitation with Plummer-style gravitational softening:

$$\mathbf{a}_i = G \sum_{j \neq i} m_j \frac{\mathbf{r}_j - \mathbf{r}_i}{\left(|\mathbf{r}_j - \mathbf{r}_i|^2 + \varepsilon^2\right)^{3/2}}$$

where:
- $\mathbf{r}_i \in \mathbb{R}^3$ is the position vector of body $i$;
- $m_j$ is the mass of body $j$;
- $\varepsilon = 10^{-4}\text{ AU} \approx 14,960\text{ km}$ is the softening parameter.

### 2.2 Softened Gravitational Potential Energy
The potential energy $U$ is defined consistently with the softened force law such that $\mathbf{F}_i = m_i \mathbf{a}_i = -\nabla_i U$:

$$U = - \sum_{i < j} \frac{G m_i m_j}{\sqrt{|\mathbf{r}_i - \mathbf{r}_j|^2 + \varepsilon^2}}$$

### 2.3 Rationale and Limitations of Softening
- **Purpose**: In point-mass simulations, close flybys ($r \to 0$) produce singular divisions ($1/r^2 \to \infty$), causing numerical instability, artificial ejection, or excessive sub-stepping. Softening regularizes the interaction at short distances.
- **Asymptotic Behavior**: At planetary distances ($r \ge 1\text{ AU}$), the relative difference introduced by $\varepsilon = 10^{-4}\text{ AU}$ is less than $10^{-7}$ (negligible). At close approaches ($r \ll \varepsilon$), the force law transitions smoothly from inverse-square gravity to an effective harmonic oscillator core ($\mathbf{a} \approx - G M \mathbf{r} / \varepsilon^3$) with a bounded maximum force.

---

## 3. Integrator & Timestep Control

### 3.1 Velocity Verlet Formulation
The integrator advances kinematics through the standard second-order Velocity Verlet algorithm:

1. **Position update**:
   $$\mathbf{r}_{n+1} = \mathbf{r}_n + \mathbf{v}_n \Delta t + \frac{1}{2} \mathbf{a}_n \Delta t^2$$
2. **Acceleration re-evaluation**:
   $$\mathbf{a}_{n+1} = \mathbf{a}(\mathbf{r}_{n+1})$$
3. **Velocity update**:
   $$\mathbf{v}_{n+1} = \mathbf{v}_n + \frac{1}{2} (\mathbf{a}_n + \mathbf{a}_{n+1}) \Delta t$$

### 3.2 Symplectic Semantics & Fixed vs. Adaptive Timesteps
For fixed timestep $\Delta t$, Velocity Verlet and Leapfrog (KDK) are **symplectic integrators**: they preserve phase space volume and conserve a shadow Hamiltonian $\tilde{H} = H + O(\Delta t^2)$, ensuring that energy errors oscillate with zero secular growth over multi-decade integration spans.

When the timestep $\Delta t$ is selected adaptively as a function of instantaneous coordinates, strict symplecticity is no longer formally preserved. The scheme operates as a second-order integration method with adaptive timestep error control; fixed-step symplectic guarantees do not directly apply. However, by selecting $\Delta t$ safely and smoothly based on the shortest estimated orbital timescale, energy drift remains bounded to machine precision for regular planetary orbits.

### 3.3 Explicit Timestep Configuration (`TimeStepConfig`)
Adaptive timestepping is governed by `TimeStepConfig`:

```text
min_dt        : 1e-5 days (~0.864 seconds)
max_dt        : 1.0 day
safety_factor : 0.01 (targets ~100 steps per orbital period)
max_substeps  : 10,000 substeps per step() call
```

The adaptive substep is computed from the minimum pairwise orbital timescale proxy, evaluating with the configured gravitational constant $G$:
$$T_{ij} \approx 2\pi \sqrt{\frac{d_{ij}^3}{G(m_i + m_j)}}$$
$$\Delta t = \max\left(\text{min\_dt}, \min\left(\text{max\_dt}, \text{safety\_factor} \times \min_{i<j} T_{ij}\right)\right)$$

If a pathological configuration requires more substeps than `max_substeps`, the integrator halts and raises `ComputationalBudgetExceededError`, preserving the simulation state rather than hanging the application.

### 3.4 Leapfrog Integrator (Kick-Drift-Kick Formulation)
In v0.9, an alternative second-order symplectic integrator is available: the Kick-Drift-Kick (KDK) Leapfrog integrator (`LeapfrogIntegrator`):

1. **Half-Step Velocity Kick**:
   $$\mathbf{v}_{n+1/2} = \mathbf{v}_n + \frac{1}{2} \mathbf{a}_n \Delta t$$
2. **Full-Step Position Drift**:
   $$\mathbf{r}_{n+1} = \mathbf{r}_n + \mathbf{v}_{n+1/2} \Delta t$$
3. **Acceleration Evaluation**:
   $$\mathbf{a}_{n+1} = \mathbf{a}(\mathbf{r}_{n+1})$$
4. **Half-Step Velocity Kick**:
   $$\mathbf{v}_{n+1} = \mathbf{v}_{n+1/2} + \frac{1}{2} \mathbf{a}_{n+1} \Delta t$$

#### Mathematical Equivalence to Velocity Verlet
For conservative, velocity-independent gravitational force fields $\mathbf{a} = \mathbf{a}(\mathbf{r})$, substituting the half-step velocity kick (1) into the drift step (2) yields:
$$\mathbf{r}_{n+1} = \mathbf{r}_n + \left(\mathbf{v}_n + \frac{1}{2} \mathbf{a}_n \Delta t\right) \Delta t = \mathbf{r}_n + \mathbf{v}_n \Delta t + \frac{1}{2} \mathbf{a}_n \Delta t^2$$
and substituting (1) into the final kick (4) yields:
$$\mathbf{v}_{n+1} = \mathbf{v}_n + \frac{1}{2} (\mathbf{a}_n + \mathbf{a}_{n+1}) \Delta t$$
Thus, synchronous KDK Leapfrog produces trajectories that are mathematically equivalent to Velocity Verlet within machine precision ($< 10^{-14}$ floating-point divergence), sharing its second-order $O(\Delta t^2)$ convergence and symplecticity under fixed timestepping while offering an explicit half-step velocity representation.

### 3.5 Substep Acceleration Reuse
Both `VelocityVerletIntegrator` and `LeapfrogIntegrator` support acceleration reuse across consecutive substeps:
- The integrator accepts an optional precomputed acceleration $\mathbf{a}_0$ matching positions $\mathbf{r}_n$. If provided, evaluation of initial acceleration is bypassed.
- When `return_acc=True`, the integrator returns the newly computed acceleration $\mathbf{a}_{n+1}$ alongside updated positions and velocities.
- `SolarSystem.step()` caches this $\mathbf{a}_{n+1}$ and feeds it as $\mathbf{a}_0$ into the subsequent substep within each outer step, halving expensive pairwise force evaluations during multi-substep integration. Cached accelerations are automatically invalidated whenever bodies are added, edited, removed, or merged.

---

## 4. Collision and Merger Physics

NBodiesGravity resolves physical overlaps ($|\mathbf{r}_i - \mathbf{r}_j| < (R_i + R_j) / \text{KM\_PER\_AU}$) through completely inelastic mergers:

1. **Survivor Selection**: The body with the larger mass survives. Ties are broken deterministically by alphabetical order of name.
2. **Total Mass**:
   $$M = m_1 + m_2$$
3. **Center-of-Mass Conservation**:
   $$\mathbf{r}_{\rm new} = \frac{m_1 \mathbf{r}_1 + m_2 \mathbf{r}_2}{m_1 + m_2}$$
4. **Linear Momentum Conservation**:
   $$\mathbf{v}_{\rm new} = \frac{m_1 \mathbf{v}_1 + m_2 \mathbf{v}_2}{m_1 + m_2}$$
5. **Volume Conservation**:
   $$R_{\rm new} = \left(R_1^3 + R_2^3\right)^{1/3}$$

### Documented Limitations
The simplified merger model does not simulate:
- Impact energy dissipation into heat or radiation;
- Physical deformation or tidal disruption;
- Ejecta or fragmentation;
- Internal rotation or spin angular momentum redistribution.

---

## 5. Conservation Diagnostics API

The diagnostics module (`nbodiesgravity.engine.diagnostics`) provides a reusable scientific layer independent of PyQt6:

- **Total Mechanical Energy**: $E = K + U = \frac{1}{2} \sum_i m_i |\mathbf{v}_i|^2 - \sum_{i<j} \frac{G m_i m_j}{\sqrt{r_{ij}^2 + \varepsilon^2}}$
- **Total Linear Momentum**: $\mathbf{P} = \sum_i m_i \mathbf{v}_i$
- **Total Angular Momentum**: $\mathbf{L} = \sum_i m_i (\mathbf{r}_i \times \mathbf{v}_i)$
- **Center of Mass**: $\mathbf{R}_{\rm CM} = \frac{\sum_i m_i \mathbf{r}_i}{\sum_i m_i}$
- **Drift Evaluation**: Compares instantaneous values against initial baseline, computing relative energy drift $\Delta E / |E_0|$, normalized momentum drift $\|\Delta \mathbf{P}\| / (\sum m_i |v_i|)$, relative angular momentum drift $\|\Delta \mathbf{L}\| / \|\mathbf{L}_0\|$, and center of mass shift $\|\Delta \mathbf{R}_{\rm CM}\|$.

---

## 6. Numerical Integrity & Failure Protection

The engine protects against unphysical states:
1. **Invalid State Detection**: Rejection of NaN or Inf in positions, velocities, or accelerations.
2. **Timestep Bounds**: Verification that $\Delta t > 0$ and $\Delta t$ is finite.
3. **Displacement Threshold**: Detection of unphysical single-step leaps ($\Delta r > 100\text{ AU}$).
4. **State Preservation**: On detection of any `NumericalIntegrityError`, intermediate invalid calculations are discarded, the simulation automatically pauses, the last valid simulation snapshot is retained for rendering, and a diagnostic notification is dispatched to the UI.

---

## 7. Deterministic Benchmarks & Convergence Verification

### 7.1 Canonical Benchmark Systems
The validation layer (`nbodiesgravity.engine.benchmarks`) provides six canonical deterministic benchmarks designed for automated verification:

- **Benchmark A — Free Particle**: Isolated body moving linearly at constant velocity, verifying that $\mathbf{a} = 0$, linear momentum is exact, and position matches $\mathbf{r}(t) = \mathbf{r}_0 + \mathbf{v}_0 t$.
- **Benchmark B — Circular Two-Body**: Two equal masses ($m_1 = m_2 = 10^{30}\text{ kg}$) in circular orbit at separation $r = 1\text{ AU}$, testing circular orbital frequency and energy conservation.
- **Benchmark C — Eccentric Two-Body**: Two masses in Keplerian eccentric orbit ($e = 0.5$, $a = 1\text{ AU}$), exercising rapid acceleration variations near periapsis.
- **Benchmark D — Earth-Sun System**: Realistic masses and orbital parameters for Earth orbiting the Sun ($m_{\rm sun} = 1.989 \times 10^{30}\text{ kg}$, $m_{\rm earth} = 5.972 \times 10^{24}\text{ kg}$, $r = 1\text{ AU}$, circular velocity $v = 2\pi\text{ AU/yr} \approx 0.01720209895\text{ AU/day}$), testing 1-year and multi-year orbital closure.
- **Benchmark E — Earth-Moon System**: Moon in geocentric orbit ($m_{\rm earth} = 5.972 \times 10^{24}\text{ kg}$, $m_{\rm moon} = 7.342 \times 10^{22}\text{ kg}$, $r \approx 384,400\text{ km} \approx 0.002569555\text{ AU}$), configured with fine substep resolution ($\Delta t_{\rm max} = 0.25\text{ days}$) testing lunar orbital stability (~27.3 day period).
- **Benchmark F — Lagrange Three-Body Solution (Exact Softened Equilibrium)**: Three equal masses ($m = 10^{30}\text{ kg}$) placed at the vertices of an equilateral triangle of side $L = 1\text{ AU}$. In the standard unsoftened Newtonian model, the angular velocity is $\omega_0 = \sqrt{3Gm / L^3}$. Under the Plummer softening potential $\varepsilon = 10^{-4}\text{ AU}$, the pairwise force along each edge of length $L$ is $F = G m^2 L / (L^2 + \varepsilon^2)^{3/2}$. Projecting both forces toward the barycenter ($R = L / \sqrt{3}$) yields the net centripetal acceleration:
  $$a_{\rm net} = 2 \cos(30^\circ) \frac{G m L}{(L^2 + \varepsilon^2)^{3/2}} = \frac{\sqrt{3} G m L}{(L^2 + \varepsilon^2)^{3/2}}$$
  Equating $a_{\rm net} = \omega^2 R = \omega^2 L / \sqrt{3}$ produces the exact softened equilibrium angular velocity:
  $$\omega = \sqrt{\frac{3 G m}{\left(L^2 + \varepsilon^2\right)^{3/2}}}$$
  NBodiesGravity initializes Benchmark F with this exact softened angular velocity, guaranteeing that the initial configuration is in exact dynamical equilibrium under the softened force law (reducing identically to $\sqrt{3Gm/L^3}$ when $\varepsilon = 0$).

### 7.2 Convergence Verification: Fixed-Step vs. Adaptive Behavior
- **Fixed-Step Velocity Verlet Convergence**: The fixed-step Velocity Verlet integrator demonstrates second-order $O(\Delta t^2)$ convergence in the deterministic convergence benchmarks (`tests/validation/test_convergence.py`). Under a fixed timestep $\Delta t$, halving the step size reduces position truncation error at a fixed terminal time by a factor of 4 ($\approx 2^{-2} = 0.25$):
  $$\frac{e(\Delta t / 2)}{e(\Delta t)} \approx 0.25, \quad p = \log_2 \left(\frac{e(\Delta t)}{e(\Delta t / 2)}\right) \approx 2.0 \pm 0.25$$
  This validates the second-order convergence of the underlying discrete integration operator on both circular and eccentric Keplerian orbits.
- **Adaptive Timestepping Semantics**: In the live interactive simulation, timesteps are chosen adaptively based on instantaneous orbital timescale proxies ($T_{ij} \approx 2\pi \sqrt{d_{ij}^3 / G(m_i + m_j)}$) within the bounds $[\text{min\_dt}, \text{max\_dt}]$ and subject to a maximum substep budget (`max_substeps = 10,000`). While adaptive step variation bounds truncation errors during close approaches and maintains numerical stability, the formal asymptotic $O(\Delta t^2)$ convergence rate applies specifically to the fixed-step integrator; the full adaptive engine is governed by timescale-bounded error control.

---

## 8. Pluggable Integrators, Presets & Reproducibility

### 8.1 Pluggable Integrator Architecture
The numerical stepping kernel is abstracted via the runtime-checkable `Integrator` protocol (`nbodiesgravity.engine.integrator`):
- `name: str`: Human-readable identifier (`velocity_verlet`, `leapfrog`).
- `softening: float`: Gravitational softening parameter $\varepsilon$ in AU.
- `max_displacement: float`: Maximum allowable single-step displacement threshold in AU.
- `g_constant: float`: Configured gravitational constant $G$, passed explicitly to force evaluations.
- `step(positions, velocities, masses, dt, a0=None, return_acc=False)`: Advances positions and velocities for a single step $\Delta t$, optionally accepting precomputed accelerations $\mathbf{a}_0$ and returning updated accelerations $\mathbf{a}_{n+1}$ for acceleration reuse across substeps.
- `reset()`: Flushes internal state or cached accelerations when the system configuration or body list changes discontinuously.

The factory function `create_integrator(config)` instantiates integrators dynamically from an extensible registry (`INTEGRATOR_REGISTRY`).

### 8.2 Analytical Initial-Condition Presets
NBodiesGravity v0.9 introduces six deterministic analytical initial-condition presets (`nbodiesgravity.engine.presets`) that strictly honor the configured `PhysicsConfig.gravitational_constant`:
1. **`circular_two_body`**: Keplerian two-body system in circular orbit with exact theoretical velocity $v_0 = \sqrt{G(m_1 + m_2)/r}$.
2. **`eccentric_two_body`**: Two-body system with configurable eccentricity $e = 0.5$, periapsis distance $r_p = a(1-e)$, and vis-viva periapsis velocity $v_p = \sqrt{G(m_1 + m_2)(2/r_p - 1/a)}$.
3. **`oriented_two_body`**: Two-body system rotated arbitrarily in 3D space by inclination $i$, longitude of ascending node $\Omega$, and argument of periapsis $\omega$ via standard Euler rotation matrices.
4. **`earth_moon`**: Geocentric Earth-Moon system initialized in dynamical equilibrium.
5. **`binary_star`**: Equal-mass binary star system orbiting their mutual barycenter.
6. **`restricted_three_body`**: Circular restricted-three-body-like system with primaries and a numerically negligible test particle placed at analytical triangular Lagrange points $L_4$ and $L_5$ for the idealized circular model.

### 8.3 Checkpoint Serialization & Replay Harness
Simulation state can be captured into high-precision, reproducible checkpoints (`nbodiesgravity.engine.checkpoints`) with IEEE-754 double-precision state serialization:
- **Schema Version**: `schema_version = 2`, `checkpoint_version = 1`.
- **Physical Precision**: Exact IEEE 754 floating-point coordinates, velocities, masses, and radii.
- **System Configuration**: Full serialization of `IntegratorConfig`, `PhysicsConfig` (including configured $G$), `CollisionConfig`, `TimeStepConfig`, and elapsed simulated days.
- **Experiment Replay**: Headless deterministic experiment execution (`nbodiesgravity.engine.experiments.run_replay` and `run_experiment`) reproducing trajectories identically without UI overhead.

