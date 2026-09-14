# v0.7 — Items Left Before PR

Final pre-PR checklist for branch `v07`.

The v0.7 implementation is fundamentally sound. Remaining work is limited to
scientific-validation, UI, diagnostics robustness, and documentation/spec cleanup.
No major architectural redesign is required.

## 🔴 Must Fix

### None currently identified

No fundamental physics, architecture, persistence, or numerical-integrity blocker
was identified in the current v0.7 implementation.

---

## 🟠 Recommended Before PR (All Completed)

### 1. Add the missing adaptive-integration plot [COMPLETED]

The v0.7 diagnostics specification calls for visualization of adaptive integration,
including:

- substeps per simulation step vs. simulation time
- adaptive `dt` vs. simulation time

The diagnostics history already records `substeps` and `adaptive_dt`, so this should
be a small UI addition.

**Acceptance criteria**
- [x] Diagnostics dialog exposes adaptive-integration history.
- [x] Plots use actual recorded values.
- [x] Existing conservation plots remain unchanged.
- [x] The bounded history buffer is respected.

### 2. Strengthen orbital-elements analytical tests [COMPLETED]

Add or strengthen tests for:

- inclined orbit with `i = 30°`
- non-zero longitude of ascending node `Ω`
- non-zero argument of periapsis `ω`
- known true anomaly `ν`
- preferably the parabolic boundary (`e ≈ 1`) if numerical tolerances allow

Existing circular, eccentric, inclined, hyperbolic, and degenerate tests should remain.

**Acceptance criteria**
- [x] Tests verify numerical values, not only successful execution.
- [x] Floating-point tolerances are appropriate.
- [x] No existing orbital-element tests regress.

### 3. Do not silently swallow diagnostics failures [COMPLETED]

`SimulationThread` currently protects the simulation from diagnostics exceptions,
which is good, but diagnostics failures should not disappear silently.

Replace silent broad exception handling with logging while allowing the physics
simulation to continue.

**Desired behavior**
- [x] Diagnostics failure does not stop the simulation.
- [x] The failure is visible in logs/debug output.
- [x] Normal simulation-thread error handling is unaffected.

### 4. Update the README project tree [COMPLETED]

Add the principal v0.7 additions, notably:

- [x] `engine/orbital_elements.py`
- [x] `data/export.py`
- [x] `ui/diagnostics_dialog.py`
- [x] `scripts/compare_convergence.py`
- [x] relevant v0.7 test/validation directories

### 5. Clarify the v0.7 export scope [COMPLETED]

Current implementation provides:

- conservation/diagnostics history export
- orbital-elements export

The original specification also described historical ephemeris/trajectory export.

**Preferred approach:** do not add a large trajectory-history subsystem solely for
this wording. Update the v0.7 specification/roadmap to state that trajectory-history
export is deferred, while diagnostics-history and orbital-elements export are part
of v0.7.

- [x] v0.7 specification and master roadmap updated to clarify that conservation history and orbital elements export are part of v0.7, while continuous historical trajectory/ephemeris export is deferred to v0.9.

---

## 🟢 Deferred / Do Not Expand v0.7

### Adaptive-vs-fixed convergence characterization
A more rigorous high-resolution reference trajectory and maximum coordinate-error
comparison can be developed later.

### Historical trajectory/ephemeris subsystem
Defer unless it becomes a concrete requirement.

### UI refactoring
Do not turn this PR into a general UI architecture refactor.

### Renderer/performance optimization
Keep OpenGL/plotting optimization in the v0.8 performance/scalability scope.

### Advanced integrators
Do not introduce new numerical integration methods in v0.7.

---

# Final Verification Before Opening the PR

- [x] Run the complete `pytest` suite.
- [x] Confirm all v0.6 validation tests still pass.
- [x] Confirm all v0.7 orbital-element tests pass.
- [x] Confirm diagnostics UI opens and updates during simulation.
- [x] Confirm conservation plots still update correctly.
- [x] Confirm adaptive `dt` / substep plots use real recorded data.
- [x] Test diagnostics CSV export.
- [x] Test diagnostics JSON export.
- [x] Test orbital-elements CSV/JSON export.
- [x] Perform a short manual orbital-analysis smoke test.
- [x] Confirm diagnostics failures are logged rather than silently swallowed.
- [x] Review README/spec consistency.
- [x] Confirm version is consistently `0.7.0`.
- [x] Inspect the final `git diff` against the v0.6 baseline.
- [x] Confirm no accidental/generated files are included.
- [x] Confirm the branch is clean and pushed.

# PR Decision

**Target:** `v07` → `main`

**Current status:** 🟢 PR-ready

All items in the v0.7 pre-PR checklist have been implemented and verified.
The test suite passes completely (157 passed). No blockers remain.
