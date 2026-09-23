# NBodiesGravity v0.9 — Items Left Before Merge

**Branch:** `v09`  
**Status:** 🟢 Complete (Merge-ready)

## 1. Executive Summary

The v0.9 implementation is substantially complete and the architecture is sound. The remaining work is intentionally small and should **not** expand the feature scope.

The principal correctness issue is that `PhysicsConfig.gravitational_constant` is currently exposed and serialized but is not fully propagated through the numerical engine. The configured value must actually control:

- gravitational acceleration;
- adaptive timestep calculation;
- analytical initial-condition presets;
- checkpoint/replay behaviour.

A small set of tests and documentation corrections should accompany that fix.

### Final objective

After these items are complete:

> **v0.9 should be merge-ready and provide a reproducible, explicitly configured simulation model without regressing the validated v0.8 baseline.**

---

# 2. Priority Legend

| Priority | Meaning |
|---|---|
| 🔴 Blocker | Must be fixed before merge |
| 🟠 Recommended | Should be fixed before merge |
| 🟢 Deferred | Explicitly leave for v1.0/later |

---

# 3. 🔴 Make Configured G Actually Operative

## Problem

`PhysicsConfig` exposes `gravitational_constant` and serializes it, but the numerical path can still fall back to the module-level `G_AU_DAY`.

This violates the v0.9 requirement that physical-model choices be explicit/configurable and creates a reproducibility inconsistency for checkpoints.

## Required architecture

```text
PhysicsConfig.gravitational_constant
            ↓
       SolarSystem
            ↓
        Integrator
            ↓
 compute_accelerations(..., g_constant=G)
```

and:

```text
PhysicsConfig.gravitational_constant
            ↓
 compute_adaptive_dt(..., g_constant=G)
```

Avoid a second hidden global source of truth.

## Acceptance criteria

- [x] Custom G changes gravitational acceleration.
- [x] Custom G changes adaptive timestep calculations consistently.
- [x] Default G produces existing v0.8 behaviour.
- [x] Velocity Verlet uses configured G.
- [x] Leapfrog uses configured G.
- [x] Checkpoints preserve configured G.
- [x] Replay preserves configured G.
- [x] No numerical path silently falls back to global `G_AU_DAY` when configured G exists.

---

# 4. 🔴 Make Presets Respect PhysicsConfig

Analytical presets currently use the canonical global G when deriving orbital velocities.

Implement one consistent rule:

> Presets generate initial conditions using the supplied `PhysicsConfig`.

Apply to:

- circular two-body;
- eccentric two-body;
- oriented two-body;
- Earth-Moon;
- binary star;
- restricted-three-body/L4-L5.

## Acceptance criteria

- [x] Preset orbital velocities use configured G.
- [x] Default preset behaviour remains unchanged.
- [x] Custom-G presets remain internally consistent.
- [x] At least one analytical preset is tested under non-default G.

---

# 5. 🟠 Add Custom-G Regression Tests

Add focused tests for:

### A — Acceleration

Create identical systems with:

```text
G = G_default
G = 2 * G_default
```

Verify acceleration changes consistently.

### B — Trajectory

Run identical two-body initial conditions under two G values and verify trajectories differ as expected.

### C — Checkpoint

```text
run
→ checkpoint
→ reload
```

Verify configured G survives and subsequent evolution matches.

### D — Adaptive timestep

Verify adaptive timestep receives configured G.

---

# 6. 🟠 Add `max_simulation_time` Test Coverage

The feature is implemented but needs an explicit test.

Verify:

```text
max_simulation_time = X
run
→ simulation stops at X
→ target-time event is emitted
→ no further simulation time accumulates
```

Also test the case where remaining duration is smaller than the normal outer step.

---

# 7. 🟠 Correct Reproducibility Terminology

Avoid claims such as:

> “bitwise-reproducible”

unless an explicit bit-pattern test and supported-environment guarantee exist.

Prefer:

> **deterministic floating-point checkpoint/resume**

or:

> **reproducible checkpoint/resume with IEEE-754 double-precision state serialization**

Acceptance:

- [x] README corrected.
- [x] v0.9 spec corrected.
- [x] No unsupported cross-platform bitwise claim.

---

# 8. 🟠 Qualify Symplectic Terminology

Velocity Verlet and Leapfrog are symplectic under the appropriate fixed-step formulation. Adaptive timesteps change the formal situation.

Document:

```text
fixed timestep:
    symplectic formulation

adaptive timestep:
    second-order integration with adaptive timestep control;
    fixed-step symplectic guarantees do not directly apply
```

Apply the caveat to both integrators.

---

# 9. 🟠 Clarify Restricted Three-Body Preset

The current preset uses a very small but non-zero test-particle mass.

Recommended wording:

> “restricted-three-body-like system with a numerically negligible test particle”

Do not introduce massless-body support just for this cleanup.

---

# 10. 🟠 Qualify L4/L5 Equilibrium Wording

Avoid an unconditional “exact equilibrium” claim.

Prefer:

> “analytical L4/L5 initial configuration for the idealized circular restricted model.”

The actual simulator also includes finite test-particle mass, softening, numerical integration, adaptive timestep and collision handling.

---

# 11. 🟠 Update `docs/numerical_model.md`

Make the documentation match the actual `Integrator.step()` API.

Document:

- actual step semantics;
- acceleration reuse;
- Velocity Verlet;
- Leapfrog KDK;
- fixed vs adaptive timestep caveat;
- configured G;
- softening;
- numerical-integrity checks.

---

# 12. 🟠 README Cleanup

Remove duplicate/stale content:

- duplicate feature entries;
- duplicate acceleration-reuse descriptions;
- stale v0.9 history entries;
- old `integrator.py` project-tree descriptions;
- inconsistent terminology.

---

# 13. 🟠 Full Verification

After the fixes:

```bash
pytest -q
```

Expected:

- all tests pass;
- no regressions;
- custom-G tests pass;
- max-simulation-time tests pass;
- checkpoint/replay tests pass.

Repeat the complete suite rather than relying on the previous PR result.

---

# 14. 🟠 Performance Regression Check

Repeat at least N=39 and preferably:

```text
N=2
N=10
N=39
N=100
N=250
N=500
```

Compare Velocity Verlet against the v0.8 baseline.

Verify that the new configuration path introduces no material per-step regression.

---

# 15. 🟠 Manual Smoke Test

Verify:

- default Solar System;
- Velocity Verlet;
- Leapfrog;
- all presets;
- diagnostics;
- custom physics configuration;
- checkpoint save/load;
- Step;
- Advance;
- maximum simulation time;
- integrator/model display;
- collision events;
- Horizons workflows.

---

# 16. 🟢 Explicitly Defer to v1.0

Do not add to the v0.9 corrective pass:

- additional integrators;
- GPU acceleration;
- Barnes-Hut;
- massless-body engine support;
- advanced collision physics;
- relativistic physics;
- major renderer refactor;
- plugin architecture;
- new preset families;
- major UI redesign.

---

# 17. Final PR Checklist

- [x] Configured G is used by force calculation.
- [x] Configured G is used by adaptive timestep calculation.
- [x] Configured G is used by presets.
- [x] Default G remains unchanged.
- [x] Custom-G tests pass.
- [x] Checkpoint/replay preserves G.
- [x] Max simulation time is tested.
- [x] Symplectic terminology qualified.
- [x] Restricted-three-body/L4/L5 terminology qualified.
- [x] Numerical-model docs updated.
- [x] README cleaned.
- [x] Full pytest passes.
- [x] Performance regression checked.
- [x] Manual smoke test passes.
- [x] Final diff reviewed.

## Recommended corrective commit

```text
fix(v0.9): honor configurable physics and tighten validation
```

After this pass:

**🟢 v0.9 merge-ready**

