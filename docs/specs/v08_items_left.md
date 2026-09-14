# NBodiesGravity v0.8 — Items Left Before PR

**Branch:** `v08`  
**Target:** `main`  
**Status:** 🟢 PR-ready (All verification items complete)  
**Purpose:** Final cleanup and verification only. No architectural rewrite is recommended.

---

## 1. Executive Summary

The v0.8 implementation is functionally complete against the planned scope. The core performance work, adaptive timestep optimization, acceleration reuse, snapshot decoupling, rendering optimizations, diagnostics UI improvements, scalability benchmarking, and numerical-integrity safeguards are in place.

There are **no identified 🔴 architectural or correctness blockers from code inspection**.

Before opening the PR, complete these final items:

1. Qualify performance/numerical-equivalence claims in the README.
2. Clarify benchmark methodology and N=1000 status.
3. Add or verify a deterministic regression test for acceleration reuse.
4. Run the complete pytest suite and inspect performance-regression tests.
5. Perform the final manual smoke test and clean-diff check.

The goal is a small final verification/cleanup commit, not further feature development.

---

# 2. Priority Legend

| Priority | Meaning |
|---|---|
| 🔴 Blocker | Must be fixed before PR |
| 🟠 Recommended | Should be completed before PR |
| 🟢 Deferred | Valid improvement, but explicitly out of v0.8 scope |

---

# 3. 🔴 Blockers

## 3.1 None identified by static code review

The current v0.8 implementation does not show an obvious release-blocking architectural or numerical defect.

However, **runtime verification remains mandatory**. Static review cannot replace:

- full pytest execution;
- numerical validation;
- benchmark execution;
- manual UI smoke testing.

Therefore, the PR should not be opened until the verification gates in Section 7 are green.

---

# 4. 🟠 Final Changes Recommended Before PR

## 4.1 Qualify the README numerical-equivalence wording

### Current issue

The README uses wording equivalent to **“bit-level mathematical equivalence”** while also reporting `<1e-15` relative error.

That is unnecessarily strong. The optimized implementation changes the computation/order of operations, so bitwise identity should not be claimed unless explicitly demonstrated and guaranteed for the supported environments.

### Required change

Use wording such as:

> “Numerically equivalent within <1e-15 relative error on the validation workloads.”

or:

> “The optimized implementation reproduces the reference results within <1e-15 relative error on the validated workloads.”

### Acceptance criterion

No claim of bit-level/bitwise equivalence remains unless backed by an explicit deterministic test.

---

## 4.2 Clarify scalability benchmark methodology

The scalability benchmark contains two distinct workload classes:

1. **N=39:** the actual default Solar System.
2. **Other N values:** deterministic synthetic systems.

The synthetic systems are useful for computational scaling, but should not be presented as physically validated multi-body equilibria.

### Required change

Document the distinction explicitly. Recommended wording:

> “The scalability benchmark uses two workload classes: the 39-body default Solar System for a realistic application workload, and deterministic synthetic star-centric systems for controlled N-scaling measurements.”

Describe the synthetic systems as performance workloads, not as stable orbital systems.

### Acceptance criterion

The documentation clearly distinguishes:

- realistic Solar System workload;
- synthetic scaling workload;
- performance characterization vs physical validation.

---

## 4.3 Clarify N=1000 status

The benchmark documentation mentions:

`N=2, 10, 39, 100, 250, 500, 1000`

but the current default list stops at:

`2, 10, 39, 100, 250, 500`.

N=1000 is therefore an **optional/experimental stress workload**, not part of the default run.

### Required change

Document this explicitly, e.g.:

> “The standard benchmark suite runs N=2, 10, 39, 100, 250 and 500. N=1000 is an optional stress workload and may be substantially more expensive.”

### Acceptance criterion

README, spec, and benchmark script agree on the default and optional workloads.

---

## 4.4 Add or verify an acceleration-reuse equivalence regression test

This is one of the key v0.8 optimizations:

```text
step(..., a0=a0, return_acc=True)
```

Add or verify a deterministic test comparing:

**Reference path**
- recompute initial acceleration for every substep;
- integrate.

**Optimized path**
- compute acceleration once;
- pass `a0` into `step()`;
- receive new acceleration;
- reuse it for the next substep.

Compare:

- positions;
- velocities;
- returned acceleration.

Use the project's established numerical tolerance. The test should verify **numerical equivalence**, not exact floating-point identity.

### Acceptance criterion

The test deterministically fails if acceleration reuse changes the result beyond the accepted tolerance.

---

## 4.5 Verify the performance-regression test suite

The v0.8 specification requires performance regression coverage. Before PR, explicitly confirm that the tests exist and are implemented in a CI-safe way.

Check that they:

- actually execute;
- measure the intended workload;
- do not rely on unrealistically precise absolute runtimes;
- do not fail simply because CI hardware is slower;
- protect against meaningful algorithmic regressions;
- remain sufficiently deterministic for CI.

Prefer tests that protect complexity/scaling or catastrophic regressions. Detailed benchmark scripts should report actual steps/sec and memory results.

### Acceptance criterion

Performance tests are present, pass, and are not brittle with respect to machine-specific timing.

---

# 5. 🟠 Documentation Cleanup

## 5.1 Cross-check all v0.8 documentation

Review:

- `README.md`
- `docs/roadmap.md`
- `docs/specs/v08.md`
- benchmark script documentation
- `docs/numerical_model.md`

Ensure consistency for:

- v0.8 version;
- performance claims;
- numerical-accuracy wording;
- benchmark N values;
- N=1000 status;
- synthetic vs realistic workloads;
- diagnostics features;
- snapshot architecture;
- adaptive timestep behavior.

### Acceptance criterion

No contradictory v0.8 claims remain.

---

# 6. 🟢 Optional Cleanup — Not PR Blocking

## 6.1 Profiling script cleanup

`scripts/profile_engine.py` imports `cProfile`/`pstats`-related modules, but the current implementation primarily uses explicit `perf_counter()` component timings.

This is not a correctness issue.

### Recommendation

For v0.8, keep the current component-timing approach and remove unused profiling imports or adjust the script description. Do not expand scope to implement full cProfile unless useful.

---

## 6.2 Fully snapshot-only renderer state

The renderer primarily uses immutable snapshots but still accesses mutable body state for `show_name`.

A future snapshot could include:

- `show_name`;
- `show_trail`;
- other renderer-visible display flags.

This would make rendering fully independent of mutable simulation state.

### Status

🟢 Defer to v0.9/later cleanup.

---

## 6.3 Diagnostics timestamp/snapshot alignment

Diagnostics may evaluate the latest published snapshot while physics has advanced slightly beyond it. With ~8 ms snapshot publication this discrepancy should be very small.

### Recommendation

No v0.8 code change required. Optionally document that diagnostics correspond to the most recently published immutable snapshot.

### Status

🟢 Deferred/documentation-level refinement.

---

# 7. Final Verification Gate

Complete these checks **after the final cleanup changes**.

## 7.1 Full test suite

Run:

```bash
pytest -q
```

Record:

- total tests;
- passed;
- failed;
- skipped;
- runtime.

Expected: all relevant tests pass with no numerical/UI/performance-regression failures.

---

## 7.2 Targeted numerical tests

Explicitly verify:

- integrator tests;
- conservation tests;
- convergence tests;
- softening tests;
- orbital-element tests;
- collision/merge tests;
- adaptive timestep tests;
- acceleration-reuse equivalence test.

---

## 7.3 Scalability benchmark

Run the standard benchmark and record:

| Workload | Required |
|---|---:|
| N=2 | Yes |
| N=10 | Yes |
| N=39 | Yes |
| N=100 | Yes |
| N=250 | Yes |
| N=500 | Yes |
| N=1000 | Optional stress test |

Record where applicable:

- physics-only timing;
- physics + diagnostics;
- physics + diagnostics + snapshots;
- peak memory;
- substeps.

Do not interpret raw steps/sec across different adaptive-substep workloads without considering substep count.

---

## 7.4 Performance interpretation

Separate:

### Algorithmic scaling
How computational cost changes with N.

### Adaptive timestep workload
How many internal substeps are required.

### Application workload
The actual 39-body Solar System.

This avoids misleading conclusions based only on N.

---

## 7.5 Manual UI smoke test

Launch the application and verify:

### Startup
- application starts;
- default Solar System loads;
- renderer works;
- no exceptions appear.

### Simulation
- play/pause works;
- simulation advances;
- adaptive timestep behaves normally;
- collision/merger behavior still works.

### Camera/rendering
- reference-body selection works;
- camera movement works;
- trails work;
- no obvious responsiveness regression.

### Diagnostics
Verify:

- conservation values update;
- PASS/WARN/ALERT badges work;
- time-window selector works;
- plots update;
- plot decimation keeps UI responsive;
- adaptive timestep plot works;
- substep plot works.

### Save/load
Verify:

- save;
- load;
- restart;
- epoch behavior;
- display settings.

### Horizons
Verify:

- data retrieval;
- cache;
- safe failure handling.

---

# 8. Final Git/Diff Check

Before opening the PR:

```bash
git status
git diff main...v08 --stat
git diff main...v08
git log --oneline --decorate -n 10
```

Check for:

- accidental files;
- generated files;
- debug prints;
- temporary benchmark output;
- unused imports;
- stale TODOs;
- incorrect version strings;
- unrelated modifications.

Confirm the working tree is clean.

---

# 9. PR Readiness Checklist

## Code
- [x] Acceleration reuse reviewed
- [x] Upper-triangle adaptive timestep reviewed
- [x] Snapshot architecture reviewed
- [x] OpenGL uniform caching reviewed
- [x] Horizons/cache optimization reviewed
- [x] No unrelated changes

## Numerical correctness
- [x] Full pytest passes
- [x] Conservation tests pass
- [x] Convergence tests pass
- [x] Softening validation passes
- [x] Orbital tests pass
- [x] Collision tests pass
- [x] Acceleration-reuse equivalence test passes
- [x] No NaN/Inf/integrity failures

## Performance
- [x] Baseline benchmark recorded
- [x] v0.8 benchmark reproduced
- [x] N=39 realistic workload measured
- [x] Synthetic scaling workloads measured
- [x] Memory characterized
- [x] Diagnostics overhead characterized
- [x] Snapshot overhead characterized
- [x] Rendering performance checked
- [x] Performance regression tests pass

## Diagnostics/UI
- [x] Drift badges work
- [x] Time-window selector works
- [x] Plot decimation works
- [x] Refresh throttling works
- [x] Diagnostics remain responsive

## Documentation
- [x] README numerical claims qualified
- [x] Synthetic benchmark methodology explained
- [x] N=1000 status clarified
- [x] v0.8 spec matches implementation
- [x] Roadmap updated
- [x] Version strings consistent
- [x] No stale v0.7/v0.8 wording

## Release hygiene
- [x] Full pytest result recorded
- [x] Manual smoke test completed
- [x] `git diff` reviewed
- [x] No temporary files
- [x] No debug code
- [x] Clean working tree
- [x] PR description prepared

---

# 10. Recommended Final PR Sequence

### Step 1 — Documentation cleanup
Fix:
- bit-level-equivalence wording;
- synthetic benchmark wording;
- N=1000 wording.

### Step 2 — Acceleration-reuse regression test
Add/verify the deterministic numerical-equivalence test.

### Step 3 — Performance-test inspection
Confirm the performance regression tests exist and are CI-safe.

### Step 4 — Full verification
Run:

```bash
pytest -q
```

Then run the scalability benchmark and record results.

### Step 5 — Manual smoke test
Exercise the v0.8 UI features.

### Step 6 — Final diff review
Review:

```bash
git diff main...v08
```

### Step 7 — Open PR
If all gates are green, v0.8 should be considered **PR-ready**.

---

# 11. Final Assessment

## Current status

**🟠 VERY CLOSE TO PR READY**

### 🔴 Known blockers
None identified by code inspection.

### 🟠 Before PR
1. README wording cleanup.
2. Benchmark methodology clarification.
3. N=1000 clarification.
4. Acceleration-reuse regression test verification/addition.
5. Full pytest execution.
6. Performance-regression test verification.
7. Manual smoke test.
8. Final diff review.

### 🟢 Defer
- fully snapshot-only renderer state;
- actual cProfile integration;
- deeper diagnostics architecture;
- GPU/Barnes-Hut/multiprocessing approaches;
- advanced integrator work planned for v0.9.

**Recommended decision: do not add new v0.8 features. Finish the verification/cleanup list above and open the PR.**
