# NBodiesGravity v1.0 — Reproducibility & Checkpointing Contract

This document defines the formal reproducibility contract, checkpoint serialization specifications, and experiment replay mechanics for NBodiesGravity v1.0.

---

## 1. Reproducibility Scope & Environmental Assumptions

### Same-Environment Determinism
Under an identical computing environment:
- Python 3.12+;
- NumPy (64-bit IEEE-754 double-precision arithmetic);
- Identical `PhysicsConfig` (gravitational constant $G$, softening $\varepsilon$);
- Identical `IntegratorConfig` (integrator name, displacement threshold);
- Identical `TimeStepConfig` (bounds, safety factor, substep budget);
- Identical initial body states $(\mathbf{r}_0, \mathbf{v}_0, m, R)$;

**NBodiesGravity guarantees deterministic simulation trajectories.** Given identical inputs and configurations, the numerical engine evolves along the same discrete trajectory without ambient randomness, unseeded noise, or non-deterministic thread ordering.

### Cross-Platform & Hardware Scope
While IEEE-754 double-precision floating-point arithmetic is standard across modern CPUs, slight variations in low-level transcendental functions (e.g. `libm` implementations, fused multiply-add compiler optimizations, or x87 extended precision) can introduce subtle discrepancies at the level of the least significant bit (Unit in the Last Place, ULP) across disparate OS platforms or instruction sets.

Therefore, NBodiesGravity guarantees:
> **Reproducible checkpoint/resume with deterministic IEEE-754 double-precision state serialization.**
It does **not** assert universal cross-compiler or cross-architecture bitwise identity.

---

## 2. Simulation Checkpoints (`SimulationCheckpoint`)

Checkpoints capture the complete state of a simulation at a discrete epoch, allowing interrupted runs to resume seamlessly.

### Schema Specification
```json
{
  "schema_version": 2,
  "checkpoint_version": 1,
  "application_version": "1.0.0",
  "timestamp_iso": "2026-09-23T12:00:00.000000+00:00",
  "epoch": "2000-01-01",
  "elapsed_days": 100.5,
  "timestep_config": {
    "min_dt": 1e-05,
    "max_dt": 1.0,
    "safety_factor": 0.01,
    "max_substeps": 10000
  },
  "integrator_config": {
    "name": "velocity_verlet",
    "softening": 0.0001,
    "max_displacement": 100.0,
    "g_constant": 1.488136e-34,
    "parameters": {}
  },
  "physics_config": {
    "gravitational_constant": 1.488136e-34,
    "softening_length": 0.0001,
    "gravity_model": "newtonian",
    "softening_model": "plummer"
  },
  "collision_config": {
    "enabled": true,
    "model": "merge",
    "restitution_coefficient": 0.0
  },
  "metadata": {
    "application_version": "1.0.0"
  },
  "bodies": [
    {
      "name": "Sun",
      "mass_kg": 1.989e+30,
      "pos_au": [0.0, 0.0, 0.0],
      "vel_au_per_day": [0.0, 0.0, 0.0],
      "radius_km": 696340.0,
      "color": [1.0, 1.0, 0.0],
      "label": "star",
      "active": true,
      "show_trail": false,
      "show_name": true
    }
  ]
}
```

### Checkpoint Resume Equivalence
A simulation paused at time $T$, saved to a checkpoint, restored, and stepped forward for duration $\Delta T$ matches continuous stepping from $0$ to $T + \Delta T$ within machine precision:
$$\|\mathbf{r}_{\rm resumed}(T + \Delta T) - \mathbf{r}_{\rm continuous}(T + \Delta T)\| < 10^{-14}\text{ AU}$$
$$\|\mathbf{v}_{\rm resumed}(T + \Delta T) - \mathbf{v}_{\rm continuous}(T + \Delta T)\| < 10^{-14}\text{ AU/day}$$

---

## 3. Headless Experiment Harness (`ExperimentConfig`)

For scientific validation and automated benchmarking, experiments can be executed headlessly without the Qt UI:

```python
from nbodiesgravity.engine import (
    ExperimentConfig,
    ExperimentMetadata,
    get_preset,
)

# 1. Select initial conditions
preset = get_preset("circular_two_body")

# 2. Define experiment parameters
experiment = ExperimentConfig(
    metadata=ExperimentMetadata(
        experiment_id="two_body_verification",
        name="Circular Two-Body Stability",
        description="Verify energy conservation over 100 days",
    ),
    initial_conditions=preset,
    target_duration=100.0,   # days
    save_trajectory=False,
)

# 3. Run deterministic replay
results = experiment.run_replay()

print(f"Substeps: {results['cumulative_substeps']}")
print(f"Energy relative drift: {results['energy_rel_drift']:+.3e}")
print(f"Momentum normalized drift: {results['momentum_norm_drift']:+.3e}")
```

Replay output includes exact final body coordinates, elapsed wall-clock time, step counts, and physical conservation metrics, providing a verifiable foundation for automated testing and CI pipelines.
