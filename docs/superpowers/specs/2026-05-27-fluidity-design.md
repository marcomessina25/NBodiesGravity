# Fluidity Improvement — Design Spec

**Date:** 2026-05-27  
**Branch:** `features/add_bodies`  
**Status:** Approved

---

## Problem

The simulation loop in `simulation_thread.py` spins at maximum CPU speed with a fixed
`dt = timescale / 120`. Because there is no sleep or wall-clock synchronisation, the
physics advances 10–20× faster than real time. Every render frame reads a `latest_snapshot`
that has jumped far ahead of its expected position, producing visible body "teleportation"
at all timescale settings.

The render timer fires every 16 ms (~60 FPS), which compounds the problem: fewer frames
per second means larger position gaps between successive renders.

---

## Chosen Approach

**Option B — Real-time physics loop + 120 FPS render.**

Two files changed, no new dependencies.

---

## Changes

### 1. `nbodiesgravity/engine/simulation_thread.py`

**Replace** `_STEPS_PER_SECOND: int = 120` with:

```python
_TARGET_HZ: int = 500       # real-time physics rate cap (~500 iterations/s)
_MAX_SIM_DT: float = 1.0    # max simulated days per sub-step (accuracy cap)
```

**Rewrite `run()`** to use wall-clock time:

```python
def run(self) -> None:
    self._running = True
    t_prev = time.perf_counter()
    while self._running:
        if self._paused:
            time.sleep(0.001)
            t_prev = time.perf_counter()   # reset clock so resume never produces a huge dt
            continue

        t_now = time.perf_counter()
        real_dt = min(t_now - t_prev, 0.05)   # cap at 50 ms — prevents spiral of death
        t_prev = t_now

        sim_dt = real_dt * self._timescale

        with self._lock:
            remaining = sim_dt
            while remaining > 0:
                self._system.step(min(remaining, _MAX_SIM_DT))
                remaining -= min(remaining, _MAX_SIM_DT)
            snap = self._system.snapshot()

        self._elapsed_days += sim_dt
        self.latest_snapshot = snap
        self.snapshot_ready.emit(snap)

        if any(float(np.linalg.norm(s.pos)) > 1000.0 for s in snap if s.active):
            self._paused = True
            self.blow_up_detected.emit()

        # Yield CPU — sleep remainder of a 1/_TARGET_HZ real-time slot
        sleep_for = (1.0 / _TARGET_HZ) - (time.perf_counter() - t_prev)
        if sleep_for > 0:
            time.sleep(sleep_for)
```

**Invariants preserved:**
- `set_timescale`, `pause`, `resume`, `reset`, `stop_thread`, `elapsed_days` — all unchanged.
- `_elapsed_days` now accrues at exactly `timescale` days per real second (previously it accrued faster because the loop ran faster than real time).
- GIL-safe `latest_snapshot` reference swap — unchanged.
- Lock usage — unchanged.

**Numerical accuracy:**
- At 500 Hz with max timescale (365 days/s): `sim_dt ≈ 0.002 × 365 = 0.73 days/step` — well within Velocity Verlet accuracy for solar-system bodies.
- Sub-step cap of 1 day only fires during OS scheduling hiccups (50 ms real-time spike → 18 sub-steps at max timescale).

### 2. `nbodiesgravity/rendering/gl_widget.py`

Change the render timer interval from 16 ms to 8 ms:

```python
# Before
self._timer.start(16)   # ~60 FPS

# After
self._timer.start(8)    # ~120 FPS
```

**Result per frame at 120 FPS:**

| Timescale | Sim days/frame | Earth movement/frame |
|---|---|---|
| 1 day/s | 0.008 days | 0.008° |
| 30 days/s | 0.24 days | 0.24° |
| 365 days/s (max) | ~3 days | ~3° |

All values smooth to the eye.

---

## What Does NOT Change

- `VelocityVerletIntegrator` — accepts arbitrary `dt`; no change needed.
- `SolarSystem`, `CelestialBody`, `BodyState` — untouched.
- `Camera`, `TrailBuffer`, `SphereMesh` — untouched.
- Speed slider range and `timescale` units (days/s) — unchanged.
- All 37 existing tests — `simulation_thread` tests check `elapsed_days`, `pause`, `resume`,
  and `reset` semantics, none of which change. Timing-sensitive test assertions (if any) may
  need adjustment if they assert exact step counts; the behaviour under test remains correct.

---

## Testing

- Run full test suite: `conda run -n nbodiesgravity pytest tests/ -v` — all 37 must pass.
- Manual verification: launch app, observe body motion at slow (1 day/s), medium (30 days/s),
  and fast (365 days/s) timescales. Motion must be continuous with no visible jumps.
