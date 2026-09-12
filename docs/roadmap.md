# NBodiesGravity Development Roadmap

## 1. Purpose

This document is the master development roadmap for **NBodiesGravity**.

The roadmap starts from the current `feature_v5` branch and defines:

- the work required to finish `feature_v5`;
- the work required to merge that branch into `main` as **v0.5.0**;
- the objectives and scope of subsequent releases;
- the relationship between releases and their detailed implementation documents.

The guiding principle is:

> **Correctness and architectural stability first; new scientific and visualization capabilities second; optimization only when justified by measurements.**

The existing architecture should be evolved rather than rewritten.

---

## 2. Versioning policy

Starting with the merge of `feature_v5`, the project should adopt **Semantic Versioning**:

`MAJOR.MINOR.PATCH`

### Major

A major release indicates a breaking change to the public data format, application behavior, or architecture that requires users/developers to migrate.

### Minor

A minor release adds meaningful functionality while preserving compatibility.

Examples:

- `v0.5.0` — first formal release after `feature_v5`;
- `v0.6.0` — numerical robustness and validation infrastructure;
- `v0.7.0` — scientific analysis and diagnostics;
- `v0.8.0` — performance/scalability improvements;
- `v0.9.0` — advanced simulation capabilities and pre-1.0 hardening;
- `v1.0.0` — stable, validated baseline.

### Patch

A patch release contains only backward-compatible bug fixes, documentation fixes, packaging fixes, or similarly small corrections.

Examples:

- `v0.5.1` — bug fixes after the v0.5.0 release;
- `v0.6.1` — fixes to validation/diagnostic infrastructure.

---

## 3. Current baseline: `feature_v5`

`feature_v5` is the starting point for this roadmap.

The branch already contains a substantial interactive Solar System simulator with:

- N-body Newtonian gravity;
- vectorized NumPy force calculation;
- Velocity Verlet integration;
- adaptive timestep selection;
- gravitational softening;
- collision detection and merging;
- a background Qt simulation thread;
- immutable simulation snapshots for rendering;
- a PyQt6 UI;
- OpenGL 3.3 rendering;
- reference-frame camera control;
- relative trails;
- body labels and category controls;
- body creation/editing/removal;
- J2000 bundled initial data;
- JPL Horizons state-vector loading;
- local Horizons caching;
- JSON save/load;
- a test suite covering engine, data, rendering and UI functionality.

The current branch is therefore **not a rewrite or foundational implementation phase**. The immediate objective is to finish and harden what is already there, then release it as `v0.5.0`.

---

# 4. Release overview

| Release | Theme | Main outcome |
|---|---|---|
| **v0.5.0** | Finish `feature_v5` / State & application correctness | A coherent, releasable baseline with fixed state, persistence and UX issues |
| **v0.6.0** | Numerical robustness & scientific validation | A simulator whose numerical behavior is measurable, bounded and regression-tested |
| **v0.7.0** | Scientific diagnostics & orbital analysis | Tools to understand and quantify what the simulation is doing |
| **v0.8.0** | Performance & scalability | Measured performance improvements and support for larger systems |
| **v0.9.0** | Advanced simulation capabilities | More sophisticated initial conditions, integration options and physical models |
| **v1.0.0** | Stable scientific application | Stable public baseline with documented limitations and validated core behavior |

The detailed implementation documents currently defined are:

- `docs/v05.md`
- `docs/v06.md`

Detailed plans for later releases should be created when the preceding release is complete and its actual implementation results are known.

---

# 5. v0.5.0 — Finish `feature_v5`

## Objective

Turn the current `feature_v5` branch into a clean, internally consistent release candidate and merge it into `main`.

This release should **not** introduce major new features. It should finish the current feature set and address the correctness findings from the code review.

### Detailed plan

See [`v05.md`](v05.md).

### Required work

1. Fix epoch/state consistency.
2. Fix rollback after failed Horizons loading.
3. Complete save/load serialization.
4. Resolve the unimplemented date-loading cancellation behavior.
5. Fix custom-star classification in rendering.
6. Correct documentation/code inconsistencies.
7. Add regression tests for every identified issue.
8. Run the complete test suite.
9. Perform a manual application smoke test.
10. Update README/version information.
11. Create the `v0.5.0` release candidate.
12. Create the PR from `feature_v5` to `main`.
13. Merge only after all acceptance criteria are satisfied.
14. Tag the merged commit as `v0.5.0`.

### Definition of Done

`feature_v5` is ready for PR when:

- simulation state and displayed epoch cannot diverge through the known UI workflows;
- failed date loads leave the previous valid simulation untouched;
- saved systems round-trip without losing body configuration;
- cancellation behavior is either genuinely implemented or the misleading UI is removed;
- custom stars are rendered according to their classification;
- all new regression tests pass;
- the existing suite passes;
- README and version information describe the release accurately;
- a manual smoke test confirms the main workflows work;
- no known P0/P1 issue from the review remains unresolved.

---

# 6. v0.6.0 — Numerical robustness & validation

## Objective

Make numerical behavior a first-class part of the application.

The simulator already uses Velocity Verlet and adaptive timestep control, but the current implementation needs stronger guarantees around extreme timesteps, instability and long-term numerical behavior.

### Detailed plan

See [`v06.md`](v06.md).

### Main workstreams

1. Formalize simulation timestep configuration.
2. Add a safe maximum substep budget.
3. Detect NaN/Inf and other numerical failures.
4. Improve handling of pathological close encounters.
5. Add conservation diagnostics internally.
6. Add deterministic benchmark systems.
7. Add fixed-step convergence tests (O(dt²)).
8. Measure energy, linear momentum and angular momentum drift.
9. Clarify the numerical meaning of adaptive Velocity Verlet.
10. Document the limitations of softening and collision merging.
11. Establish a reproducible validation workflow.
12. Preserve backward compatibility with the v0.5 data model where practical.

### Definition of Done

v0.6.0 should be able to answer, quantitatively:

- Is the integration stable for a given system?
- How does error change when the timestep is reduced?
- How much energy drift occurs over a defined interval?
- Is linear momentum conserved?
- Is angular momentum conserved?
- What happens when an encounter requires an extremely small timestep?
- Does the application stop safely instead of entering an effectively unbounded computation?

---

# 7. v0.7.0 — Scientific diagnostics & orbital analysis

## Objective

Expose the numerical information developed in v0.6 to the user.

The application should move beyond simply showing bodies moving on screen and allow users to inspect the physical behavior of the simulation.

### Planned capabilities

- total kinetic energy;
- gravitational potential energy;
- total mechanical energy;
- relative energy drift;
- total linear momentum;
- total angular momentum;
- center of mass;
- body-specific orbital elements;
- semi-major axis;
- eccentricity;
- inclination;
- periapsis and apoapsis;
- orbital period estimates;
- trajectory statistics;
- numerical diagnostics over time;
- plots of conserved quantities;
- export of simulation/diagnostic data.

### Important design rule

Diagnostics should consume the same simulation state used by the physics engine. They should not reconstruct physical quantities from rendered coordinates.

---

# 8. v0.8.0 — Performance & scalability

## Objective

Improve performance based on actual profiling rather than premature optimization.

The current direct O(N²) vectorized implementation is appropriate for the current Solar System-scale body count. It should remain the baseline until measurements demonstrate a need for more.

### Planned work

- profile the physics loop;
- profile NumPy allocations;
- profile snapshot generation;
- cache OpenGL uniform locations;
- reduce unnecessary rendering-side access to mutable simulation state;
- optimize Horizons data loading;
- consider bounded concurrent Horizons requests;
- benchmark different body counts;
- benchmark different timesteps;
- establish performance regression tests.

Only after those measurements should the project consider:

- alternative O(N²) kernels;
- multiprocessing/threading strategies;
- GPU acceleration;
- Barnes-Hut or other approximate algorithms.

### Definition of Done

Performance work must demonstrate measurable improvement without reducing numerical correctness.

---

# 9. v0.9.0 — Advanced simulation capabilities

## Objective

Add advanced capabilities only after the core numerical and diagnostic infrastructure is trustworthy.

Potential scope:

### Integrators

Provide a pluggable integration interface allowing controlled comparison between:

- Velocity Verlet;
- leapfrog variants;
- higher-order methods where justified.

### Initial conditions

Add reusable presets such as:

- two-body circular orbit;
- two-body eccentric orbit;
- Earth-Moon;
- binary systems;
- restricted three-body configurations;
- custom planetary systems.

### Simulation controls

Potential additions:

- single-step forward;
- configurable integration limits;
- simulation checkpoints;
- deterministic replay;
- rewind from checkpoints;
- improved reset semantics.

### Physical models

Only where justified by the project goals:

- configurable softening;
- selectable collision models;
- center-of-mass-aware merging;
- optional relativistic corrections as a separate experimental model.

Experimental physics should be clearly separated from the validated baseline.

---

# 10. v1.0.0 — Stable release

## Objective

Declare the core application stable enough for regular use.

v1.0 should not mean "perfect physics." It should mean:

- the supported numerical model is clearly defined;
- known limitations are documented;
- the core simulation has reproducible validation;
- persistence is stable;
- the UI is coherent;
- releases are versioned;
- automated tests protect the important behavior;
- performance characteristics are understood;
- the application can be packaged and distributed reproducibly.

### v1.0 release gate

Before v1.0:

- no known critical state-management bugs;
- no known uncontrolled numerical failure mode;
- benchmark suite is stable;
- conservation/convergence behavior is documented;
- save/load format is documented;
- test suite is green;
- packaged application is manually verified;
- README accurately describes capabilities and limitations.

---

# 11. Cross-release engineering principles

## 11.1 Do not rewrite working architecture

Keep the current separation:

```text
UI
 ↓
SimulationThread
 ↓
SolarSystem
 ↓
Integrator
```

with:

```text
Data → SolarSystem
Simulation → immutable snapshots → Renderer
```

Improvements should preserve this structure unless a concrete problem requires changing it.

## 11.2 Tests accompany implementation

Every bug fix should add a regression test.

Every new numerical feature should add deterministic tests.

Every new UI behavior should have either an automated test or a documented manual acceptance test.

## 11.3 Scientific claims require measurements

Do not describe the simulator as "accurate" merely because an orbit looks visually correct.

Use:

- conservation error;
- convergence;
- comparison against known analytical solutions;
- comparison against external ephemeris data where appropriate.

## 11.4 Separate physical state from presentation state

Physics must not depend on:

- camera position;
- rendering scale;
- trails;
- labels;
- OpenGL state.

The renderer should transform physical state for visualization rather than modify the physical model.

## 11.5 Prefer explicit state transitions

Loading, restarting, saving, editing and resetting should have clear commit/rollback semantics.

A failed operation must not partially modify the active simulation.

---

# 12. Release workflow

For every minor release:

```text
1. Define scope
2. Create/update detailed vXX plan
3. Implement in small commits
4. Add/update tests
5. Run full test suite
6. Perform manual smoke test
7. Update documentation
8. Update version
9. Freeze release branch
10. Open PR
11. Review PR
12. Merge to main
13. Create Git tag
14. Publish release notes
15. Start next version from main
```

The version should describe the state **after** the release, not the development branch name.

Thus:

```text
feature_v5
    ↓
finish/harden
    ↓
PR → main
    ↓
tag v0.5.0
```

and subsequently:

```text
main @ v0.5.0
    ↓
feature_v6
    ↓
PR → main
    ↓
tag v0.6.0
```

---

# 13. Master priority list

### Immediate — v0.5

- [x] Epoch consistency
- [x] Failed-load rollback
- [x] Complete persistence
- [x] Cancellation behavior
- [x] Custom star classification
- [x] Documentation consistency
- [x] Regression tests
- [x] Full test pass
- [x] Manual smoke test
- [x] Version/release preparation
- [ ] PR `feature_v5 → main`
- [ ] Tag `v0.5.0`

### Current — v0.6

- [x] Safe adaptive timestep limits
- [x] Numerical failure detection
- [x] Conservation metrics
- [x] Benchmark systems
- [x] Fixed-step convergence tests (O(dt²))
- [x] Long-term stability tests
- [x] Numerical documentation
- [x] Validation workflow

### Future — v0.7

- [ ] Scientific diagnostics UI
- [ ] Orbital elements
- [ ] Physical plots
- [ ] Data export

### Future — v0.8

- [ ] Profiling
- [ ] Physics optimization
- [ ] Rendering optimization
- [ ] Data-loading optimization
- [ ] Scalability benchmarks

### Future — v0.9

- [ ] Additional integrators
- [ ] Initial-condition presets
- [ ] Checkpoints/replay
- [ ] More advanced collision/physics models

### Final — v1.0

- [ ] Stable validated baseline
- [ ] Documented limitations
- [ ] Reproducible build
- [ ] Stable persistence
- [ ] Comprehensive regression suite
- [ ] Public release

---

# 14. Detailed-plan index

| Document | Release | Purpose |
|---|---|---|
| [`v05.md`](v05.md) | v0.5.0 | Detailed implementation plan for finishing `feature_v5` and preparing the PR to `main` |
| [`v06.md`](v06.md) | v0.6.0 | Detailed implementation plan for numerical robustness and validation |
| `v07.md` | v0.7.0 | To be created when v0.6.0 is complete |
| `v08.md` | v0.8.0 | To be created when v0.7.0 is complete |
| `v09.md` | v0.9.0 | To be created when v0.8.0 is complete |
