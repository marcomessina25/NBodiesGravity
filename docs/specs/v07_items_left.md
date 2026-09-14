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

## 🟠 Recommended Before PR

### 1. Add the missing adaptive-integration plot

The v0.7 diagnostics specification calls for visualization of adaptive integration,
including:

- substeps per simulation step vs. simulation time
- adaptive `dt` vs. simulation time

The diagnostics history already records `substeps` and `adaptive_dt`, so this should
be a small UI addition.

**Acceptance criteria**
- Diagnostics dialog exposes adaptive-integration history.
- Plots use actual recorded values.
- Existing conservation plots remain unchanged.
- The bounded history buffer is respected.

### 2. Strengthen orbital-elements analytical tests

Add or strengthen tests for:

- inclined orbit with `i = 30°`
- non-zero longitude of ascending node `Ω`
- non-zero argument of periapsis `ω`
- known true anomaly `ν`
- preferably the parabolic boundary (`e ≈ 1`) if numerical tolerances allow

Existing circular, eccentric, inclined, hyperbolic, and degenerate tests should remain.

**Acceptance criteria**
- Tests verify numerical values, not only successful execution.
- Floating-point tolerances are appropriate.
- No existing orbital-element tests regress.

### 3. Do not silently swallow diagnostics failures

`SimulationThread` currently protects the simulation from diagnostics exceptions,
which is good, but diagnostics failures should not disappear silently.

Replace silent broad exception handling with logging while allowing the physics
simulation to continue.

**Desired behavior**
- Diagnostics failure does not stop the simulation.
- The failure is visible in logs/debug output.
- Normal simulation-thread error handling is unaffected.

### 4. Update the README project tree

Add the principal v0.7 additions, notably:

- `engine/orbital_elements.py`
- `data/export.py`
- `ui/diagnostics_dialog.py`
- `scripts/compare_convergence.py`
- relevant v0.7 test/validation directories

### 5. Clarify the v0.7 export scope

Current implementation provides:

- conservation/diagnostics history export
- orbital-elements export

The original specification also described historical ephemeris/trajectory export.

**Preferred approach:** do not add a large trajectory-history subsystem solely for
this wording. Update the v0.7 specification/roadmap to state that trajectory-history
export is deferred, while diagnostics-history and orbital-elements export are part
of v0.7.

If trajectory export is considered mandatory, implement it separately with bounded
history and dedicated tests.

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

- [ ] Run the complete `pytest` suite.
- [ ] Confirm all v0.6 validation tests still pass.
- [ ] Confirm all v0.7 orbital-element tests pass.
- [ ] Confirm diagnostics UI opens and updates during simulation.
- [ ] Confirm conservation plots still update correctly.
- [ ] Confirm adaptive `dt` / substep plots use real recorded data.
- [ ] Test diagnostics CSV export.
- [ ] Test diagnostics JSON export.
- [ ] Test orbital-elements CSV/JSON export.
- [ ] Perform a short manual orbital-analysis smoke test.
- [ ] Confirm diagnostics failures are logged rather than silently swallowed.
- [ ] Review README/spec consistency.
- [ ] Confirm version is consistently `0.7.0`.
- [ ] Inspect the final `git diff` against the v0.6 baseline.
- [ ] Confirm no accidental/generated files are included.
- [ ] Confirm the branch is clean and pushed.

# PR Decision

**Target:** `v07` → `main`

**Current status:** 🟠 Almost ready

**Expected status after this checklist:** 🟢 PR-ready

No major redesign is expected. The remaining work should be a short final
quality/validation pass rather than another development cycle.
