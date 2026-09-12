# NBodiesGravity Numerical Model & Validation Specification

This document provides the formal mathematical and numerical specifications for NBodiesGravity v0.6.0+, documenting physical units, force models, integration semantics, collision mechanics, conservation diagnostics, and validation methodologies.

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

### 3.2 Symplectic Semantics
For fixed timestep $\Delta t$, Velocity Verlet is a **symplectic integrator**: it preserves phase space volume and conserves a shadow Hamiltonian $\tilde{H} = H + O(\Delta t^2)$, ensuring that energy errors oscillate with zero secular growth over multi-decade integration spans.

When the timestep $\Delta t$ is selected adaptively as a function of instantaneous coordinates, strict symplecticity is no longer formally preserved. However, by selecting $\Delta t$ safely and smoothly based on the shortest estimated orbital timescale, energy drift remains bounded to machine precision for regular planetary orbits.

### 3.3 Explicit Timestep Configuration (`TimeStepConfig`)
Adaptive timestepping is governed by `TimeStepConfig`:

```text
min_dt        : 1e-5 days (~0.864 seconds)
max_dt        : 1.0 day
safety_factor : 0.01 (targets ~100 steps per orbital period)
max_substeps  : 10,000 substeps per step() call
```

The adaptive substep is computed from the minimum pairwise orbital timescale proxy:
$$T_{ij} \approx 2\pi \sqrt{\frac{d_{ij}^3}{G(m_i + m_j)}}$$
$$\Delta t = \max\left(\text{min\_dt}, \min\left(\text{max\_dt}, \text{safety\_factor} \times \min_{i<j} T_{ij}\right)\right)$$

If a pathological configuration requires more substeps than `max_substeps`, the integrator halts and raises `ComputationalBudgetExceededError`, preserving the simulation state rather than hanging the application.

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
