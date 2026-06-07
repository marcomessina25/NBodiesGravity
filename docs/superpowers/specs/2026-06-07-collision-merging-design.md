# Collision Merging — Design

**Date:** 2026-06-07
**Status:** Approved, pending implementation

## Problem

When two celestial bodies pass through the same point in space, the softened
gravitational force produces physically illegal behaviour (extreme
accelerations, slingshots, eventual blow-up). We want a deterministic,
physically motivated resolution: on collision, the smaller body disappears and
the larger body absorbs all of its mass.

## Behaviour summary

When two **active** bodies' centres come within the sum of their physical
radii, they merge:

- The **lower-mass** body is removed.
- The **higher-mass** body absorbs the other's mass, conserving momentum, and
  grows in radius.
- Collision handling is **always on** (no toggle).
- The UI is notified via a signal and refreshes; the camera retargets if it was
  following an absorbed body.

## 1. Detection geometry (`SolarSystem`)

- Radii are stored in **km**; positions in **AU**.
- Add a module constant `KM_PER_AU = 1.495978707e8`.
- A pair `(i, j)` of active bodies collides when:

  ```
  ‖pos_i − pos_j‖ < (radius_i + radius_j) / KM_PER_AU
  ```

- Only **active** bodies participate (consistent with the integrator, which
  also ignores inactive bodies).

## 2. Merge resolution

New method `SolarSystem._resolve_collisions() -> list[CollisionEvent]`:

1. Compute pairwise distances among active bodies; find colliding pairs.
2. For each colliding pair:
   - **survivor** = larger mass (ties broken by `name` for determinism).
   - **absorbed** = the other body.
3. Update the survivor in place:
   - `v_new = (m_s·v_s + m_a·v_a) / (m_s + m_a)` — momentum conserved.
   - `mass_new = m_s + m_a`.
   - `radius_new = (r_s³ + r_a³) ** (1/3)` — equal-density volume sum.
4. Remove the absorbed body from `_bodies`.
5. **Loop until no colliding pairs remain.** This handles chains (A+B merge,
   then the survivor overlaps C, all within one step). Resolve the closest
   colliding pair first on each iteration so the order is deterministic.
6. Return a list of `CollisionEvent(absorbed: str, survivor: str)` describing
   every merge performed this call.

`CollisionEvent` is a small `NamedTuple` defined in `engine/body.py` alongside
`BodyState`:

```python
class CollisionEvent(NamedTuple):
    absorbed: str   # name of the body that was removed
    survivor: str   # name of the body that absorbed it
```

`SolarSystem.step(dt)` calls `_resolve_collisions()` after the integration
write-back and **returns** the event list (empty when nothing collided).

## 3. Threading integration (`SimulationThread`)

- `run()` already calls `self._system.step(step_dt)` under `self._lock`.
  Mutating `_bodies` inside `step()` is therefore safe.
- Accumulate the events returned across the inner `while remaining > 0` loop.
- After the lock is released and the snapshot is published, if any events were
  collected, emit a new signal:

  ```python
  collisions_detected = pyqtSignal(list)   # list[CollisionEvent]
  ```

## 4. UI wiring (`MainWindow`)

- Wire `_sim.collisions_detected` → new slot `_on_collisions(events)`.
  Qt queues the cross-thread signal onto the UI thread automatically.
- `_on_collisions(events)`:
  - If `_gl.camera.center_name` matches any event's `absorbed` body, retarget
    the camera to that event's `survivor`.
  - Call `_refresh_after_body_change()` to rebuild display infos, the body
    list, and the center combo, and update `latest_snapshot`.
- **Restart semantics:** collision merges are **not** mirrored into
  `_initial_system`. Restart restores the original epoch state, so absorbed
  bodies reappear — the correct behaviour (restart = back to the loaded epoch).

## 5. Known limitation (v1, documented — not fixed)

Detection runs once per `SolarSystem.step()` call, not continuously. Fast,
small bodies can tunnel through each other between steps without registering a
collision. Realistic collisions (a body falling into the Sun, or user-placed
near-overlapping bodies) are caught because at least one body is large or the
relative motion is slow. Continuous collision detection is out of scope for v1.
Note this in `CLAUDE.md`.

## 6. Test plan (pytest, headless — no display required)

**Engine (`tests/engine/`):**
- Overlapping pair merges → exactly one body remains; mass is summed; velocity
  equals the momentum-conserved value; radius equals the cube-root combination.
- Non-overlapping pair → untouched (no merge, empty event list).
- Chained 3-body merge resolved within a single `step()` call.
- Inactive bodies are excluded from collision detection.
- `step()` returns a correct `list[CollisionEvent]`.
- Momentum (Σ m·v) is conserved across a merge (numeric assertion).

**Thread / UI (`tests/ui/`):**
- `collisions_detected` is emitted with the correct `(absorbed, survivor)`
  names when a merge occurs.
- `MainWindow._on_collisions` rebuilds the body list and retargets the camera
  off an absorbed center body onto the survivor.

## Files touched

| File | Change |
|---|---|
| `engine/body.py` | Add `CollisionEvent` NamedTuple. |
| `engine/system.py` | Add `KM_PER_AU`, `_resolve_collisions()`; `step()` returns events. |
| `engine/simulation_thread.py` | Accumulate events, add `collisions_detected` signal, emit. |
| `ui/main_window.py` | Wire signal, add `_on_collisions` slot. |
| `tests/engine/`, `tests/ui/` | New tests per the plan above. |
| `CLAUDE.md` | Document collision behaviour and the tunneling limitation. |
