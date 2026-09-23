# NBodiesGravity v1.0 — Scientific Guarantees and Limitations

This document provides an explicit, transparent statement of what NBodiesGravity v1.0 guarantees and what it explicitly does not guarantee.

---

## 1. What NBodiesGravity v1.0 Guarantees

### 1.1 Determinism Under Identical Environments
- Given identical software environments (Python 3.12, NumPy 64-bit IEEE-754 arithmetic), identical physical configurations (`PhysicsConfig`), identical timestep parameters (`TimeStepConfig`), and identical initial body conditions, the engine executes deterministically without random fluctuations or thread-scheduling race conditions.
- Continuous integration and checkpoint-and-resume produce identical trajectories within machine precision ($< 10^{-14}\text{ AU}$).

### 1.2 Conservation Laws Within Documented Tolerances
- **Linear Momentum**: Strictly conserved to machine precision ($< 10^{-12}$ normalized drift) for all closed systems.
- **Center of Mass**: Conserved within $< 10^{-8}\text{ AU}$ across multi-orbit planetary runs and strictly conserved across inelastic mergers.
- **Angular Momentum**: Conserved within $< 10^{-12}$ relative drift for circular and isolated two-body systems.
- **Total Mechanical Energy**: Conserved with zero secular energy growth under fixed-step symplectic Velocity Verlet; bounded within documented tolerances ($< 10^{-6}$ for eccentric orbits, $< 10^{-10}$ for circular planetary systems) under adaptive timestepping.

### 1.3 Backward-Compatible Save & Checkpoint Persistence
- All save files created in v0.5, v0.6, v0.7, v0.8, and v0.9 load smoothly, initializing missing fields with validated baseline defaults.
- Schema version 1 and 2 checkpoints restore simulation coordinates, velocities, and configurations with IEEE-754 double-precision accuracy.

### 1.4 Stable Default Scientific Baseline
- The validated baseline configuration (Newtonian point-mass gravity, Plummer softening $\varepsilon = 10^{-4}\text{ AU}$, Velocity Verlet integrator with substep acceleration reuse, and adaptive timescale control) is frozen and preserved across all minor updates.

### 1.5 Public Engine API Stability
- All public engine classes and protocols exposed in `nbodiesgravity.engine` adhere to semantic versioning guarantees and will not incur breaking signature changes within the v1.x lifecycle.

---

## 2. What NBodiesGravity v1.0 Does Not Guarantee

### 2.1 Symplecticity Under Adaptive Timestepping
- While the fixed-step formulations of Velocity Verlet and Leapfrog are strictly symplectic (conserving phase space volume and a shadow Hamiltonian $\tilde{H} = H + O(\Delta t^2)$), variable timesteps alter the symplectic geometry.
- Adaptive timestepping provides **second-order integration with adaptive error control**, not formal fixed-step symplecticity. Energy drift remains bounded by timescale proxies, but fixed-step symplectic guarantees do not directly apply.

### 2.2 Microscopic Inverse-Square Gravity ($r \ll \varepsilon$)
- Plummer-style gravitational softening regularizes the potential ($U = -G m_1 m_2 / \sqrt{r^2 + \varepsilon^2}$) with $\varepsilon = 10^{-4}\text{ AU} \approx 14,960\text{ km}$.
- At planetary distances ($r \ge 1\text{ AU}$), softening introduces a negligible difference ($< 10^{-7}$). At microscopic distances ($r \ll \varepsilon$), the force smoothly transitions to a bounded linear core ($\mathbf{a} \propto -\mathbf{r}$), eliminating infinite acceleration singularities. It does **not** model point-mass singularity dynamics.

### 2.3 Complex Impact Hydrodynamics
- The collision model implements an idealized **completely inelastic merger**: mass, linear momentum, center of mass, and volume (equal density) are strictly conserved.
- It does **not** simulate impact heating, radiation losses, tidal disruption, spin redistribution, fragmentation, or cratering.

### 2.4 Long-Term Chaotic Orbit Determinism
- Non-linear gravitational N-body systems exhibit deterministic chaos with finite Lyapunov horizons. Two different double-precision implementations or different numerical timestepping schemes will naturally diverge exponentially beyond the system's characteristic Lyapunov timescale.
- NBodiesGravity guarantees consistency with its own discrete equations, not infinite-horizon tracking of chaotic celestial bodies.

### 2.5 Infinite Scaling to Arbitrary $N$
- NBodiesGravity computes exact pairwise gravitational forces with optimized vectorized $O(N^2)$ direct summation.
- While optimized for up to $N = 500$ bodies in real time, simulating tens of thousands of bodies in real time is computationally prohibitive without tree codes (e.g. Barnes-Hut) or GPU acceleration, which are explicitly deferred to post-v1.0 releases.
