# NBodiesGravity v0.6.0 — Items Left Before PR

## Purpose

This document is the **remaining-work checklist for the v0.6 release**.

It is intended to be used directly by either:

- a human developer; or
- an AI coding agent working on the repository.

The scope is deliberately narrow. **Do not expand v0.6 with new features.** The objective is to finish the current `v6` branch, verify it, make the small corrections below, and prepare the PR to `main`.

---

# 1. Current status

The `v6` branch already implements the main v0.6 objectives:

- explicit timestep configuration;
- adaptive timestep protection;
- maximum substep budget;
- numerical integrity checks;
- preservation of the last valid simulation state;
- energy diagnostics;
- linear momentum diagnostics;
- angular momentum diagnostics;
- center-of-mass diagnostics;
- softened gravitational potential;
- deterministic validation benchmarks;
- convergence tests;
- softening validation;
- collision-model validation/documentation;
- headless benchmark tooling;
- v0.6 numerical-model documentation.

Therefore, **do not redesign the numerical engine** unless one of the checks below reveals an actual defect.

---

# 2. Priority classification

## 🔴 Must complete before PR

These are release gates.

1. Run the complete test suite on the exact current `v6` branch.
2. Verify the numerical-failure handling paths.
3. Verify the computational-budget-exceeded path.
4. Verify all deterministic benchmark tests pass.
5. Inspect the final diff against `main`.

## 🟠 Recommended small fixes before PR

These are not architectural changes but should be corrected because they affect scientific precision or release-quality documentation.

6. Correct/document the softened-force assumption in Benchmark F.
7. Tighten the O(dt²) convergence wording.
8. Correct the stale `max_substeps` docstring.

## 🟢 Defer to v0.7+

Do not hold the v0.6 PR for these unless implementation reveals a concrete problem.

9. Exact adaptive-vs-fixed convergence characterization.
10. Actual substep counting from inside the engine rather than benchmark-side estimation.
11. Advanced diagnostics UI.
12. More sophisticated numerical experiments.
13. Additional performance optimization.

---

# 3. Item 1 — Run the complete test suite

## Objective

Establish that the current pushed `v6` branch passes all tests after the numerical changes.

## Actions

From a clean checkout of the `v6` branch:

```bash
git status
git fetch origin
git checkout v6
git pull --ff-only origin v6

pytest -q
```

Record:

- total tests;
- passed;
- failed;
- skipped;
- warnings;
- execution time.

## Acceptance criteria

- Full test suite passes.
- No unexpected test failures.
- No existing v0.5 functionality has regressed.

If failures occur, investigate them before proceeding.

---

# 4. Item 2 — Verify numerical-integrity failure handling

## Objective

Confirm that an invalid numerical state cannot become the active simulation state.

## Inspect

Review:

- `nbodiesgravity/engine/integrator.py`
- `nbodiesgravity/engine/system.py`
- `nbodiesgravity/engine/simulation_thread.py`
- `nbodiesgravity/engine/exceptions.py`

Verify the intended sequence:

```text
valid state
    ↓
integration
    ↓
invalid numerical result
    ↓
exception
    ↓
invalid state discarded
    ↓
last valid state retained
    ↓
simulation paused/stopped
```

## Specifically test

- NaN position.
- Inf position.
- NaN velocity.
- Inf velocity.
- invalid acceleration.
- invalid timestep.
- excessive displacement if the protection is triggered.

## Acceptance criteria

- An invalid state raises the appropriate exception.
- The existing valid body state is not overwritten by invalid output.
- The simulation thread stops/pauses safely.
- No invalid snapshot is published to the renderer.

If the current implementation already satisfies all of these and tests cover them, mark this item complete without modifying the architecture.

---

# 5. Item 3 — Verify `ComputationalBudgetExceededError`

## Objective

Ensure the maximum-substep protection really prevents pathological integration loops.

## Inspect

Verify that `SolarSystem.step()`:

- enforces `max_substeps`;
- cannot run indefinitely because of adaptive timestep reduction;
- raises `ComputationalBudgetExceededError` when the budget is exhausted.

## Test

Construct or use a deterministic pathological configuration that requires more substeps than the configured limit.

Verify:

```text
step()
  ↓
budget exceeded
  ↓
exception
  ↓
simulation state remains valid
```

## Important distinction

A computational budget failure is not necessarily evidence of corrupted numerical state.

If the UI currently reports both through the same numerical-error mechanism, ensure the message makes the distinction clear enough.

No new error architecture is required for v0.6.

---

# 6. Item 4 — Verify all deterministic benchmarks

## Objective

Confirm that the validation suite is actually executable and stable.

The expected benchmark set is:

```text
A — Free particle
B — Circular two-body
C — Eccentric two-body
D — Earth-Sun
E — Earth-Moon
F — Lagrange three-body
```

## Actions

Run the validation tests independently if useful:

```bash
pytest -q tests/validation/
```

Also run the headless benchmark tool where practical:

```bash
python scripts/benchmark_engine.py
```

Use the actual repository invocation if the script exposes command-line arguments.

## Record

For each benchmark, where available:

- duration;
- timestep statistics;
- energy drift;
- momentum drift;
- angular momentum drift;
- center-of-mass drift;
- execution time.

## Acceptance criteria

- Benchmark tests pass deterministically.
- No benchmark relies on network access.
- Results are reproducible within reasonable floating-point tolerance.

---

# 7. Item 5 — Final diff review against `main`

## Objective

Confirm that the PR contains only the intended v0.6 work.

Run:

```bash
git fetch origin
git diff --stat origin/main...v6
git diff origin/main...v6
```

Also inspect:

```bash
git log --oneline --decorate origin/main..v6
```

## Look specifically for

- debugging code;
- temporary print statements;
- generated files;
- local configuration;
- accidental IDE files;
- unrelated refactors;
- obsolete comments;
- stale documentation;
- test hacks;
- changes outside the v0.6 scope.

## Acceptance criteria

The diff should tell a coherent story:

> v0.6 adds numerical robustness, validation and diagnostics infrastructure without unrelated changes.

---

# 8. Item 6 — Benchmark F: softened-force consistency

## Finding

The Lagrange three-body benchmark calculates its angular velocity using the standard/unsoftened gravitational expression:

\[
\omega^2 = \frac{3Gm}{L^3}
\]

while the actual simulator uses gravitational softening.

For the current parameters the discrepancy is extremely small, so this is not expected to cause a practical failure.

However, a scientific validation benchmark should explicitly account for the physical model being tested.

## Preferred action

Investigate whether the exact softened equilibrium can be derived and used.

If straightforward, update the benchmark to use the softened expression.

If not worth changing for v0.6, explicitly document that:

- the benchmark's analytic initial condition is based on the unsoftened model;
- the current softening-to-separation ratio makes the difference negligible for the benchmark;
- the test is therefore being used as a near-equilibrium validation rather than an exact softened equilibrium proof.

## Acceptance criteria

There must be no ambiguity about whether Benchmark F is:

```text
exactly consistent with the softened model
```

or:

```text
an intentionally approximate reference
```

Do not silently leave the inconsistency unexplained.

---

# 9. Item 7 — Tighten the O(dt²) convergence wording

## Finding

The current convergence validation uses fixed-step Velocity Verlet.

That is appropriate because fixed-step Velocity Verlet has second-order convergence.

The broader simulator, however, uses adaptive timestep selection.

Therefore the documentation should not accidentally imply that the complete adaptive algorithm has formally established O(dt²) convergence.

## Required wording principle

Prefer language equivalent to:

> The fixed-step Velocity Verlet integrator demonstrates second-order convergence in the deterministic convergence benchmark.

Avoid claiming:

> The adaptive simulator is proven to have O(dt²) convergence.

unless future testing establishes that specifically.

## Files to inspect

- `README.md`
- `docs/numerical_model.md`
- `docs/roadmap.md`
- `docs/specs/v06.md`
- relevant test documentation/comments.

## Acceptance criteria

The distinction between:

```text
fixed-step convergence
```

and:

```text
adaptive timestep behavior
```

is explicit.

---

# 10. Item 8 — Fix the `max_substeps` documentation mismatch

## Finding

The `TimeStepConfig` documentation currently contains a stale statement indicating a default of `1000`, while the implementation uses:

```python
max_substeps = 10_000
```

## Required change

Make the docstring agree with the actual default.

Do not change the implementation merely to match the stale documentation unless there is an independent reason to change the default.

## Acceptance criteria

The following all agree:

- code;
- docstring;
- numerical-model documentation;
- README, where applicable;
- tests.

---

# 11. Item 9 — Adaptive-vs-fixed convergence characterization

## Status

**DEFER.**

This is useful scientific work but is not required to close the v0.6 PR if the current validation suite is otherwise sound.

Future work should compare:

```text
fixed dt
vs
adaptive dt
```

for the same canonical systems and measure:

- energy drift;
- angular momentum drift;
- orbital parameter drift;
- timestep distribution;
- computational cost.

This belongs naturally in v0.7 scientific diagnostics/analysis unless the v0.6 implementation currently makes an unsupported claim that requires immediate correction.

---

# 12. Item 10 — Actual substep accounting

## Status

**DEFER.**

The benchmark script currently derives/estimates substep information rather than obtaining an authoritative count directly from the engine.

For a future improvement, expose actual integration statistics from the simulation engine.

A desirable design would allow the benchmark layer to report:

```text
actual substeps performed
actual dt sequence/statistics
```

rather than reconstructing them externally.

Do not redesign `SolarSystem.step()` solely for this in the v0.6 PR unless the current benchmark results are demonstrably misleading.

---

# 13. Item 11 — Advanced diagnostics UI

## Status

**DEFER TO v0.7.**

The v0.6 goal is to establish the diagnostics API.

The next release can expose:

- energy plots;
- momentum plots;
- angular momentum plots;
- center-of-mass movement;
- orbital elements;
- diagnostic history;
- export.

Do not add a large diagnostics UI now.

---

# 14. Item 12 — Additional numerical experiments

## Status

**DEFER.**

Future experiments can investigate:

- longer Solar System integrations;
- different softening values;
- close encounters;
- different adaptive safety factors;
- different maximum timestep values;
- alternative integrators.

The v0.6 validation infrastructure should make these experiments easy to add later.

---

# 15. Item 13 — Performance optimization

## Status

**DEFER TO v0.8.**

The current v0.6 benchmark infrastructure should establish a baseline.

Do not introduce:

- GPU acceleration;
- Barnes-Hut;
- multiprocessing;
- major NumPy rewrites;
- architectural changes

just to improve v0.6 benchmark numbers.

Optimization should follow profiling and belong to v0.8.

---

# 16. Final pre-PR checklist

Before opening the PR, all of the following should be true:

## Code

- [x] No known critical numerical-integrity bug.
- [x] Timestep bounds are enforced.
- [x] Maximum substep budget is enforced.
- [x] Invalid states cannot overwrite valid state.
- [x] Computational budget failures are handled safely.
- [x] Diagnostics use the same physical model as the engine.
- [x] Collision behavior remains consistent with the documented model.

## Validation

- [x] All deterministic benchmarks pass.
- [x] Conservation tests pass.
- [x] Fixed-step convergence test passes.
- [x] Softening validation passes.
- [x] Numerical failure tests pass.
- [x] Full pytest suite passes.

## Documentation

- [x] Benchmark F softening issue resolved or explicitly documented.
- [x] O(dt²) wording is scientifically precise.
- [x] `max_substeps` documentation is correct.
- [x] README matches the actual v0.6 implementation.
- [x] `docs/numerical_model.md` matches the implementation.
- [x] `docs/specs/v06.md` matches the implementation.

## Repository

- [x] `git status` is clean.
- [x] No temporary/generated files are included.
- [x] `git diff origin/main...v6` contains only intended v0.6 work.
- [x] Version information is consistently `0.6.0`.

---

# 17. PR decision rule

Use this rule after completing the checklist.

### Create the PR

If:

- all 🔴 items pass;
- the three 🟠 documentation/scientific issues are resolved;
- the full test suite is green;
- the final diff is clean.

Then:

```text
v6 → main
```

and prepare the release as:

```text
v0.6.0
```

### Do not create the PR

Only hold the PR if verification reveals:

- a failing regression;
- an actual numerical-integrity defect;
- a broken benchmark;
- an invalid conservation calculation;
- a state-corruption issue;
- an unrelated regression;
- or another concrete correctness problem.

Do **not** hold the PR merely because future scientific improvements would be useful.

---

# 18. Recommended agent execution prompt

An AI coding agent can use the following instruction:

> Work on the current `v6` branch of NBodiesGravity. Read `docs/roadmap.md`, `docs/specs/v06.md`, and this `v06_items_left.md` before making changes.
>
> Treat this as a v0.6 release-completion task, not a new-feature task.
>
> First inspect the current implementation and run the existing test suite. Then address only the 🔴 release-gate items and the three 🟠 small corrections listed in this document.
>
> For every code fix, add or update a focused regression test where appropriate. Do not redesign working architecture and do not implement deferred v0.7/v0.8 functionality.
>
> After the fixes, run the full test suite again, run the validation benchmarks, inspect the diff against `main`, and report:
>
> 1. files changed;
> 2. tests added/changed;
> 3. test results;
> 4. benchmark results;
> 5. any remaining issues;
> 6. whether the branch is ready for `v6 → main`.
>
> Do not create the PR or merge anything unless explicitly instructed.

---

# 19. Expected end state

The desired result is:

```text
v6
 │
 ├── final numerical checks
 ├── small documentation/scientific corrections
 ├── all tests passing
 ├── benchmarks passing
 └── clean diff
       │
       ▼
   PR → main
       │
       ▼
    v0.6.0
```

Once this state is reached, stop v0.6 development.

The next development branch should begin from the merged `main` at `v0.6.0` and focus on the v0.7 scientific diagnostics and orbital-analysis roadmap.
