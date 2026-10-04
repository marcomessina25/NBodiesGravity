# Items Left for v1.0.1

## Purpose

This document lists the remaining work required before merging the `v1.0.1` release PR.

The v1.0.1 implementation is otherwise considered feature-complete. The remaining work is primarily about ensuring that the new ejection/stability behavior is scientifically consistent with the specification and fully covered by regression tests.

---

# 1. Fix the ejection criterion

## Priority: P0 — Required before merge

The current `find_ejected_index()` implementation must be corrected so that **distance alone can never cause a gravitationally bound body to be classified as permanently ejected**.

An object should be considered ejected only when **all** of the following conditions are satisfied:

1. The object is sufficiently far from the system:

   ```text
   r > MIN_EJECTION_DISTANCE
   ```

2. The object is outside the meaningful extent of the remaining system:

   ```text
   r > EXTENT_FACTOR × system_extent
   ```

3. The object is moving outward:

   ```text
   radial_velocity > 0
   ```

4. The object is gravitationally unbound:

   ```text
   specific_energy >= 0
   ```

Where:

```text
radial_velocity = dot(r_vec, v_vec) / |r_vec|

specific_energy = 0.5 × |v|² - G × M / r
```

The implementation may use the existing approximation for the relevant central/remaining system mass, provided the approximation is documented.

### Important invariant

A body with:

```text
specific_energy < 0
```

must **never** be classified as permanently ejected solely because it has travelled beyond the distance threshold.

A very distant but bound body may be on a highly eccentric orbit and can eventually return.

---

# 2. Make the implementation match the specification

## Priority: P0 — Required before merge

Review `nbodiesgravity/engine/stability.py` and ensure that the implementation expresses the four ejection requirements clearly.

Avoid logic where the negative-energy condition only applies inside a particular distance range.

The code should make the following relationship obvious:

```text
far enough
AND
outside system extent
AND
moving outward
AND
unbound
→ ejected
```

Prefer explicit, readable logic over compact conditional expressions.

Add/update comments explaining why **positive specific orbital energy is required**.

---

# 3. Update the ejection regression tests

## Priority: P0 — Required before merge

Update `tests/engine/test_stability.py`.

The existing test that expects a distant object with zero velocity to be ejected must be changed.

A body at approximately 1000+ AU with zero velocity is gravitationally bound and therefore must **not** be classified as permanently ejected.

Add explicit tests covering at least the following cases.

### Case A — Distant but bound

```text
r > MIN_EJECTION_DISTANCE
radial velocity >= 0
specific energy < 0
```

Expected:

```text
NOT EJECTED
```

### Case B — Distant, bound and moving inward

```text
r > MIN_EJECTION_DISTANCE
radial velocity < 0
specific energy < 0
```

Expected:

```text
NOT EJECTED
```

### Case C — Distant, unbound but moving inward

```text
r > MIN_EJECTION_DISTANCE
radial velocity < 0
specific energy >= 0
```

Expected:

```text
NOT EJECTED
```

The object may be on an unbound trajectory but is not currently moving outward through the ejection boundary.

### Case D — Genuine ejection

```text
r > MIN_EJECTION_DISTANCE
outside system extent
radial velocity > 0
specific energy >= 0
```

Expected:

```text
EJECTED
```

### Case E — Unbound but not far enough

```text
specific energy >= 0
radial velocity > 0
r < MIN_EJECTION_DISTANCE
```

Expected:

```text
NOT EJECTED
```

### Case F — Far away but still bound

Explicitly test a highly distant bound object, e.g. several thousand AU.

Expected:

```text
NOT EJECTED
```

This regression is important because it protects against accidentally reintroducing the original distance-only behavior.

---

# 4. Verify the system-lifecycle behavior

## Priority: P1

After an object satisfies the complete ejection criterion:

- it must be removed from the active N-body system;
- the remaining bodies must continue simulating;
- the simulation must not be treated as numerically failed;
- diagnostics must distinguish ejection from numerical instability;
- the ejected object's identity/index handling must remain correct.

Add or update an integration test if necessary.

The expected distinction is:

```text
Numerical failure
    → simulation failure / stop

Physical ejection
    → valid simulation event / continue

Collision
    → valid simulation event according to existing collision policy
```

---

# 5. Verify diagnostics after ejection

## Priority: P1

Ensure that conservation diagnostics do not misleadingly report the removal of an ejected object as an ordinary numerical error.

The existing behavior/documentation should clearly explain that an open system can lose:

- mass,
- momentum,
- kinetic energy,
- total mechanical energy

from the perspective of the remaining active system when an object is intentionally removed.

If the implementation already handles this correctly, no architectural change is required.

Only add tests/documentation where necessary.

---

# 6. Keep the ejection criterion explicitly heuristic

## Priority: P1

The current ejection test is an approximation for a general N-body system.

Document that the specific-energy calculation is an approximate escape criterion, particularly for systems where:

- multiple massive bodies contribute significantly;
- the system is non-hierarchical;
- the gravitational potential changes significantly during escape.

Do **not** attempt to turn v1.0.1 into a fully rigorous general N-body escape solver.

The goal is a robust and scientifically defensible practical criterion for the simulator's intended use cases.

---

# 7. Verify existing stability tests

## Priority: P1

Run the complete stability test suite after changing ejection behavior.

Verify that the following existing functionality remains unaffected:

- Hill stability
- mutual Hill separation
- orbit crossing
- binary-star stability
- S-type stability
- P-type stability
- stability diagnostics/reporting
- normal bound planetary systems

No unrelated stability behavior should change as a side effect of the ejection fix.

---

# 8. Clean the v1.0.1 README/version badge

## Priority: P2

Review the README version badge.

The current PR introduces the v1.0.1 badge without cleanly replacing the previous v1.0.0 badge.

Clean this up so the README presents a single authoritative current version.

---

# 9. Review GitHub Actions warning

## Priority: P2

The current CI passes successfully, but GitHub reports an environment/deprecation warning related to the Node.js/Ubuntu runner transition.

Do not expand the scope of v1.0.1 unnecessarily.

Simply:

- determine whether an immediate change is required;
- if not, document it as post-v1.0.1 maintenance;
- avoid unrelated CI changes that could destabilize the release PR.

---

# 10. Final release validation

## Priority: P0 — Required before merge

After all changes:

### Tests

Run:

```bash
pytest -q
```

Expected:

```text
0 failures
0 errors
0 unexpected warnings
```

### Compilation

Run the existing byte-compilation validation.

### Headless smoke test

Run the existing headless simulation smoke test.

### Ejection-specific validation

Explicitly verify:

```text
bound distant body       → retained
bound inward body        → retained
unbound inward body      → retained
unbound outward distant  → ejected
unbound outward nearby   → retained
```

### Documentation consistency

Verify that:

```text
docs/specs/v101.md
nbodiesgravity/engine/stability.py
tests/engine/test_stability.py
README
```

all describe the same ejection semantics.

There must be no contradiction between specification, implementation, and tests.

---

# Definition of Done

v1.0.1 is ready to merge when:

- [x] Ejection requires sufficient distance.
- [x] Ejection requires being outside the system extent.
- [x] Ejection requires outward radial motion.
- [x] Ejection requires non-negative specific orbital energy.
- [x] A distant bound object is never classified as permanently ejected.
- [x] Regression tests cover bound and unbound distant objects.
- [x] Physical ejection continues the simulation normally.
- [x] Numerical failure remains distinct from physical ejection.
- [x] Stability diagnostics remain unaffected.
- [x] Full test suite passes.
- [x] Headless smoke test passes.
- [x] README version badge is clean.
- [x] CI warning has either been addressed or explicitly deferred.
- [x] Specification, implementation, and tests are consistent.
- [x] No unrelated scope has been introduced into v1.0.1.

---

# Final v1.0.1 Principle

The key scientific rule introduced/finalized by this release is:

> **Being far away is not the same as being ejected.**

A body is considered permanently ejected only when it is sufficiently far from the active system, is outside the meaningful system extent, is moving outward, and has non-negative specific orbital energy.

This preserves physically valid long-period bound orbits while allowing genuinely escaping bodies to be removed from the active N-body calculation and the simulation to continue.
