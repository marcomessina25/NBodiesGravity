# NBodiesGravity v1.0 — Public Engine API Reference

This document defines the frozen public Python API for NBodiesGravity v1.0. All symbols documented here are exposed through the top-level package namespace `nbodiesgravity.engine`.

---

## 1. Units and Conventions

All engine APIs operate directly with astrodynamical units in the **Solar System Barycenter (SSB)** inertial reference frame:

| Quantity | Unit | Mathematical Symbol / Equivalent |
|---|---|---|
| Position ($\mathbf{r}$) | Astronomical Unit ($\text{AU}$) | $1\text{ AU} \approx 1.495978707 \times 10^{11}\text{ m}$ |
| Time ($t, \Delta t$) | Julian Day ($\text{day}$) | $1\text{ day} = 86,400\text{ s}$ |
| Velocity ($\mathbf{v}$) | $\text{AU} / \text{day}$ | $1\text{ AU/day} \approx 1,731.4568\text{ km/s}$ |
| Acceleration ($\mathbf{a}$) | $\text{AU} / \text{day}^2$ | $1\text{ AU/day}^2 \approx 20.04\text{ m/s}^2$ |
| Mass ($m$) | Kilogram ($\text{kg}$) | Standard SI kilogram |
| Radius ($R$) | Kilometer ($\text{km}$) | Used for visual rendering and inelastic physical merger radius |
| Gravitational Constant ($G$) | $\text{AU}^3\text{ kg}^{-1}\text{ day}^{-2}$ | $G_{\rm AU\_DAY} \approx 1.488136 \times 10^{-34}$ |

---

## 2. Core State & Kinematics

### `CelestialBody`
*Mutable representation of a gravitationally interacting body.*

```python
@dataclass
class CelestialBody:
    name: str
    mass: float                         # kg (> 0)
    pos: np.ndarray                     # AU, shape (3,), float64
    vel: np.ndarray                     # AU/day, shape (3,), float64
    radius: float                       # km (> 0) — visual & collision radius
    color: tuple[float, float, float]   # RGB floats [0.0, 1.0]
    show_trail: bool = True
    active: bool = True                 # False = excluded from physics and rendering
    label: str = "planet"               # "star", "planet", "moon", "dwarf planet", "asteroid"
    show_name: bool = True
```
- **Thread Safety**: Mutable; modifications must be performed when `SimulationThread` is paused or under `SimulationThread._lock`.
- **Key Methods**:
  - `snapshot() -> BodyState`: Produces an immutable, thread-safe snapshot with copied coordinate arrays.

### `BodyState`
*Immutable, thread-safe snapshot of a body's kinematic and physical state.*

```python
class BodyState(NamedTuple):
    name: str
    pos: np.ndarray                     # AU, shape (3,)
    vel: np.ndarray                     # AU/day, shape (3,)
    active: bool = True
    mass: float = 0.0
    radius: float = 0.0
    color: tuple[float, float, float] = (1.0, 1.0, 1.0)
    label: str = "planet"
    show_name: bool = True
    show_trail: bool = True
```

### `CollisionEvent`
*Immutable record of an inelastic merger.*

```python
class CollisionEvent(NamedTuple):
    absorbed: str   # name of body merged and removed
    survivor: str   # name of surviving body
```

---

## 3. System Orchestration

### `SolarSystem`
*Central engine container managing body collections, numerical stepping, adaptive timestepping, and collisions.*

```python
class SolarSystem:
    def __init__(
        self,
        bodies: list[CelestialBody] | None = None,
        timestep_config: TimeStepConfig | None = None,
        integrator_config: IntegratorConfig | None = None,
        physics_config: PhysicsConfig | None = None,
        collision_config: CollisionConfig | None = None,
    ) -> None
```

- **Properties**:
  - `bodies -> list[CelestialBody]`: List of all bodies.
  - `active_bodies -> list[CelestialBody]`: Filtered list of bodies where `active == True`.
  - `integrator -> Integrator`: Currently active numerical integrator.
  - `timestep_config -> TimeStepConfig`: Timestep configuration parameters.
  - `physics_config -> PhysicsConfig`: Physical parameters (e.g. $G$, softening).
  - `collision_config -> CollisionConfig`: Collision configuration.
  - `last_substeps -> int`: Substeps taken in the last `step()` call.
  - `last_adaptive_dt -> float`: Adaptive timestep size selected during the last step.
  - `last_collision_events -> list[CollisionEvent]`: Mergers that occurred during the last step.

- **Primary Methods**:
  - `step(dt: float) -> list[CollisionEvent]`: Advances active bodies by `dt` days using adaptive substeps.
  - `step_once() -> list[CollisionEvent]`: Advances active bodies by a single internal substep (`dt = last_adaptive_dt`).
  - `advance(duration: float) -> list[CollisionEvent]`: Advances active bodies by `duration` days in discrete outer steps.
  - `snapshot() -> list[BodyState]`: Returns an immutable snapshot list of all bodies.
  - `clone() -> SolarSystem`: Deep copy of the system, configurations, and bodies.
  - `set_integrator(name: str, **params) -> None`: Switches the active numerical integrator.

---

## 4. Numerical Integrators & Configurations

### `Integrator` (Protocol)
*Runtime-checkable protocol defining the standard stepper interface.*

```python
@runtime_checkable
class Integrator(Protocol):
    name: str
    softening: float
    max_displacement: float
    g_constant: float

    def step(
        self,
        positions: np.ndarray,      # shape (N, 3), AU
        velocities: np.ndarray,     # shape (N, 3), AU/day
        masses: np.ndarray,         # shape (N,), kg
        dt: float,                  # days
        a0: np.ndarray | None = None,
        return_acc: bool = False,
    ) -> tuple[np.ndarray, np.ndarray] | tuple[np.ndarray, np.ndarray, np.ndarray]:
        ...

    def reset(self) -> None:
        ...
```

### Supported Integrators
1. **`VelocityVerletIntegrator`** (`"velocity_verlet"`):
   - Validated default baseline.
   - Second-order symplectic formulation under fixed timestepping; adaptive second-order error control under variable timestepping.
   - Supports substep acceleration reuse (`return_acc=True`).
2. **`LeapfrogIntegrator`** (`"leapfrog"`):
   - Synchronous Kick-Drift-Kick (KDK) formulation.
   - Second-order symplectic formulation under fixed timestepping; adaptive second-order error control under variable timestepping.
   - Trajectories match Velocity Verlet within $< 10^{-14}$ floating-point divergence for position-dependent forces.

### `IntegratorConfig`
```python
@dataclass
class IntegratorConfig:
    name: str = "velocity_verlet"
    softening: float = 1e-4          # AU
    max_displacement: float = 100.0   # AU
    g_constant: float = G_AU_DAY      # AU^3 kg^-1 day^-2
    parameters: dict[str, Any] = field(default_factory=dict)
```

### `create_integrator(config: IntegratorConfig | None = None, **kwargs) -> Integrator`
Instantiates an integrator from the global registry (`INTEGRATOR_REGISTRY`).

---

## 5. Physical & Timestep Configurations

### `PhysicsConfig`
```python
@dataclass
class PhysicsConfig:
    gravitational_constant: float = G_AU_DAY
    softening_length: float = 1e-4
    gravity_model: str = "newtonian"     # "newtonian"
    softening_model: str = "plummer"     # "plummer"
```

### `CollisionConfig`
```python
@dataclass
class CollisionConfig:
    enabled: bool = True
    model: str = "merge"                 # "merge" (inelastic) or "ignore"
    restitution_coefficient: float = 0.0
```

### `TimeStepConfig`
```python
@dataclass
class TimeStepConfig:
    min_dt: float = 1e-5         # days (~0.864 s)
    max_dt: float = 1.0          # days
    safety_factor: float = 0.01  # targets ~100 substeps per shortest orbital period
    max_substeps: int = 10_000   # maximum substeps per step() before raising budget error
```

---

## 6. Analytical Presets

All presets accept an optional `physics_config: PhysicsConfig | None = None` and compute theoretical velocities using the configured $G$.

```python
get_preset(name: str, **kwargs) -> InitialConditionSet
list_presets() -> list[str]
register_preset(name: str, factory_fn: Callable[..., InitialConditionSet]) -> None
```

### Standard Preset Names:
- `"circular_two_body"`: Keplerian circular orbit ($v_0 = \sqrt{G(m_1+m_2)/r}$).
- `"eccentric_two_body"`: Keplerian eccentric orbit ($e=0.5$).
- `"oriented_two_body"`: Rotated 3D two-body system ($i, \Omega, \omega$).
- `"earth_moon"`: Geocentric Earth-Moon system in dynamical equilibrium.
- `"binary_star"`: Equal-mass binary star system orbiting mutual barycenter.
- `"restricted_three_body"`: Circular restricted-three-body-like system with primaries and negligible test particles at analytical triangular Lagrange points $L_4$ and $L_5$.

---

## 7. Checkpoints & Experiments

### `SimulationCheckpoint`
*State serialization with deterministic IEEE-754 double-precision state restoration.*

```python
@dataclass(frozen=True)
class SimulationCheckpoint:
    schema_version: int = 2
    checkpoint_version: int = 1
    application_version: str = "1.0.0"
    epoch: str = "2000-01-01"
    elapsed_days: float = 0.0
    bodies: list[dict[str, Any]]
    timestep_config: dict[str, Any]
    integrator_config: dict[str, Any]
    physics_config: dict[str, Any]
    collision_config: dict[str, Any]
    metadata: dict[str, Any]

    @classmethod
    def create(cls, system: SolarSystem, epoch: datetime, elapsed_days: float, metadata: dict | None = None) -> SimulationCheckpoint: ...
    def save(self, path: str | Path) -> None: ...
    @classmethod
    def load(cls, path: str | Path) -> SimulationCheckpoint: ...
    def restore(self) -> tuple[SolarSystem, datetime, float, dict[str, Any]]: ...
```

### `ExperimentConfig`
*Headless deterministic experiment execution harness.*

```python
@dataclass(frozen=True)
class ExperimentConfig:
    metadata: ExperimentMetadata
    initial_conditions: InitialConditionSet
    target_duration: float
    time_limit_seconds: float | None = None
    save_trajectory: bool = False
    trajectory_interval: float = 1.0

    def run_replay(self) -> dict[str, Any]: ...
```

---

## 8. Diagnostics

### `ConservationTracker`
```python
class ConservationTracker:
    def __init__(self, initial_bodies: list[CelestialBody | BodyState], g_constant: float = G_AU_DAY) -> None
    def evaluate(self, current_bodies: list[CelestialBody | BodyState], elapsed_days: float = 0.0) -> DiagnosticReport
    def reset(self, new_initial_bodies: list[CelestialBody | BodyState], elapsed_days: float = 0.0) -> None
```

### `DiagnosticReport`
Provides relative energy drift ($\Delta E / |E_0|$), normalized linear momentum drift, relative angular momentum drift, and center-of-mass shift.

---

## 9. Exceptions

- **`NumericalIntegrityError`** (`ValueError`): Raised on NaN/Inf coordinates, non-positive or non-finite timesteps, or single-step displacements exceeding `max_displacement`.
- **`ComputationalBudgetExceededError`** (`NumericalIntegrityError`): Raised when required substeps exceed `TimeStepConfig.max_substeps`.
