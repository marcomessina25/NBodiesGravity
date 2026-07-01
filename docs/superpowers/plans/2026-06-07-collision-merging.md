# Collision Merging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When two active bodies' centres come within the sum of their physical radii, merge them — the lower-mass body is removed and the higher-mass body absorbs its mass (momentum conserved, radius grows), with the UI auto-refreshing.

**Architecture:** Detection and merge live in `SolarSystem` (engine, no Qt). `SolarSystem.step()` returns a list of `CollisionEvent`s. `SimulationThread` accumulates them across its inner step loop and emits a new `collisions_detected` signal. `MainWindow` handles the signal on the UI thread: retargets the camera off any absorbed body and rebuilds the body list / display infos / center combo. Always on; collisions are NOT mirrored into `_initial_system`, so Restart restores the pre-collision epoch state.

**Tech Stack:** Python 3.12, NumPy, PyQt6, pytest. Conda env `nbodiesgravity` — every command uses `conda run -n nbodiesgravity`.

---

## Conventions

- **Run a single test:** `conda run -n nbodiesgravity pytest <path>::<test> -v`
- **Run full suite:** `conda run -n nbodiesgravity pytest tests/ -v`
- **Commit + push** to the current branch (`feature_v4`) after each task.
- Units: position AU, velocity AU/day, mass kg, radius **km**.

---

## Task 1: `CollisionEvent` NamedTuple

**Files:**
- Modify: `nbodiesgravity/engine/body.py`
- Test: `tests/engine/test_collisions.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/engine/test_collisions.py`:

```python
import numpy as np
from nbodiesgravity.engine.body import CollisionEvent


def test_collision_event_fields():
    ev = CollisionEvent(absorbed="Moon", survivor="Earth")
    assert ev.absorbed == "Moon"
    assert ev.survivor == "Earth"
    # NamedTuple => positional + immutable
    assert tuple(ev) == ("Moon", "Earth")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n nbodiesgravity pytest tests/engine/test_collisions.py::test_collision_event_fields -v`
Expected: FAIL — `ImportError: cannot import name 'CollisionEvent'`.

- [ ] **Step 3: Add the NamedTuple**

In `nbodiesgravity/engine/body.py`, after the `BodyState` class definition (before `CelestialBody`), add:

```python
class CollisionEvent(NamedTuple):
    """Record of one merge: `absorbed` was removed into `survivor`."""
    absorbed: str   # name of the body that was removed
    survivor: str   # name of the body that absorbed it
```

(`NamedTuple` is already imported at the top of the file.)

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n nbodiesgravity pytest tests/engine/test_collisions.py::test_collision_event_fields -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add nbodiesgravity/engine/body.py tests/engine/test_collisions.py
git commit -m "feat: add CollisionEvent NamedTuple"
git push
```

---

## Task 2: Collision detection + merge in `SolarSystem`

**Files:**
- Modify: `nbodiesgravity/engine/system.py`
- Test: `tests/engine/test_collisions.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/engine/test_collisions.py`:

```python
import pytest
from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.system import SolarSystem, KM_PER_AU


def _big(name, mass, pos, vel=(0.0, 0.0, 0.0), radius=695700.0):
    return CelestialBody(name=name, mass=mass, pos=np.array(pos, dtype=float),
                         vel=np.array(vel, dtype=float), radius=radius,
                         color=(1.0, 1.0, 1.0))


def test_overlapping_pair_merges_into_larger_mass():
    # Centres 1e-4 AU apart; A radius alone = 695700/KM_PER_AU ~= 4.65e-3 AU > 1e-4 => overlap.
    a = _big("A", 2.0e30, [0.0, 0.0, 0.0], vel=[0.0, 0.0, 0.0], radius=695700.0)
    b = _big("B", 1.0e24, [1e-4, 0.0, 0.0], vel=[0.1, 0.0, 0.0], radius=6371.0)
    system = SolarSystem([a, b])

    events = system._resolve_collisions()

    assert len(events) == 1
    assert events[0].absorbed == "B"
    assert events[0].survivor == "A"
    assert len(system.bodies) == 1
    assert system.bodies[0].name == "A"


def test_merge_conserves_momentum_and_mass():
    a = _big("A", 2.0e30, [0.0, 0.0, 0.0], vel=[0.0, 0.0, 0.0], radius=695700.0)
    b = _big("B", 1.0e24, [1e-4, 0.0, 0.0], vel=[0.4, 0.0, 0.0], radius=6371.0)
    p_before = a.mass * a.vel + b.mass * b.vel
    m_before = a.mass + b.mass

    system = SolarSystem([a, b])
    system._resolve_collisions()

    survivor = system.bodies[0]
    assert survivor.mass == pytest.approx(m_before)
    np.testing.assert_allclose(survivor.mass * survivor.vel, p_before, rtol=1e-12)


def test_merge_grows_radius_by_equal_density_volume():
    a = _big("A", 2.0e30, [0.0, 0.0, 0.0], radius=695700.0)
    b = _big("B", 1.0e24, [1e-4, 0.0, 0.0], radius=6371.0)
    expected = (695700.0 ** 3 + 6371.0 ** 3) ** (1.0 / 3.0)

    system = SolarSystem([a, b])
    system._resolve_collisions()

    assert system.bodies[0].radius == pytest.approx(expected)


def test_non_overlapping_pair_untouched():
    a = _big("A", 2.0e30, [0.0, 0.0, 0.0], radius=695700.0)   # radius ~4.65e-3 AU
    b = _big("B", 1.0e24, [1.0, 0.0, 0.0], radius=6371.0)     # 1 AU away
    system = SolarSystem([a, b])

    events = system._resolve_collisions()

    assert events == []
    assert len(system.bodies) == 2


def test_chained_three_body_merge_in_one_call():
    # All three within the Sun-sized radius of A => chain to a single survivor.
    a = _big("A", 3.0e30, [0.0, 0.0, 0.0], radius=695700.0)
    b = _big("B", 2.0e30, [1e-4, 0.0, 0.0], radius=695700.0)
    c = _big("C", 1.0e30, [2e-4, 0.0, 0.0], radius=695700.0)
    system = SolarSystem([a, b, c])

    events = system._resolve_collisions()

    assert len(events) == 2
    assert len(system.bodies) == 1
    assert system.bodies[0].name == "A"
    assert system.bodies[0].mass == pytest.approx(6.0e30)


def test_inactive_bodies_excluded_from_collision():
    a = _big("A", 2.0e30, [0.0, 0.0, 0.0], radius=695700.0)
    b = _big("B", 1.0e24, [1e-4, 0.0, 0.0], radius=6371.0)
    b.active = False
    system = SolarSystem([a, b])

    events = system._resolve_collisions()

    assert events == []
    assert len(system.bodies) == 2


def test_step_returns_collision_events():
    a = _big("A", 2.0e30, [0.0, 0.0, 0.0], radius=695700.0)
    b = _big("B", 1.0e24, [1e-4, 0.0, 0.0], radius=6371.0)
    system = SolarSystem([a, b])

    events = system.step(0.001)

    assert isinstance(events, list)
    assert len(events) == 1
    assert events[0].absorbed == "B"


def test_step_returns_empty_list_when_no_collision():
    a = _big("A", 2.0e30, [0.0, 0.0, 0.0], radius=695700.0)
    b = _big("B", 1.0e24, [1.0, 0.0, 0.0], radius=6371.0)
    system = SolarSystem([a, b])

    assert system.step(0.001) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n nbodiesgravity pytest tests/engine/test_collisions.py -v`
Expected: FAIL — `ImportError: cannot import name 'KM_PER_AU'` / `AttributeError: 'SolarSystem' object has no attribute '_resolve_collisions'`.

- [ ] **Step 3: Add the constant and import**

At the top of `nbodiesgravity/engine/system.py`, update the imports / module constants. After the existing imports add:

```python
from .body import CelestialBody, BodyState, CollisionEvent

#: Kilometres per Astronomical Unit — converts km radii to AU for collision tests.
KM_PER_AU: float = 1.495978707e8
```

(Replace the existing `from .body import CelestialBody, BodyState` line — do not duplicate it.)

- [ ] **Step 4: Add `_resolve_collisions`**

Add this method to `SolarSystem` (e.g. directly after `step`):

```python
    def _resolve_collisions(self) -> list[CollisionEvent]:
        """Merge any active bodies whose centres overlap (sum of physical radii).

        Survivor = larger mass (ties broken by the alphabetically-first name).
        Momentum is conserved; the survivor's radius grows by equal-density
        volume. Loops until no overlapping pair remains so chains collapse in a
        single call. Returns one CollisionEvent per merge performed.
        """
        events: list[CollisionEvent] = []
        while True:
            active = [b for b in self._bodies if b.active]
            if len(active) < 2:
                break

            closest = None   # (dist, body_i, body_j)
            for i in range(len(active)):
                for j in range(i + 1, len(active)):
                    bi, bj = active[i], active[j]
                    dist = float(np.linalg.norm(bi.pos - bj.pos))
                    threshold = (bi.radius + bj.radius) / KM_PER_AU
                    if dist < threshold and (closest is None or dist < closest[0]):
                        closest = (dist, bi, bj)

            if closest is None:
                break

            _, ba, bb = closest
            if ba.mass > bb.mass or (ba.mass == bb.mass and ba.name < bb.name):
                survivor, absorbed = ba, bb
            else:
                survivor, absorbed = bb, ba

            total_mass = survivor.mass + absorbed.mass
            survivor.vel = (
                survivor.mass * survivor.vel + absorbed.mass * absorbed.vel
            ) / total_mass
            survivor.radius = (survivor.radius ** 3 + absorbed.radius ** 3) ** (1.0 / 3.0)
            survivor.mass = total_mass

            self._bodies = [b for b in self._bodies if b is not absorbed]
            events.append(CollisionEvent(absorbed=absorbed.name, survivor=survivor.name))

        return events
```

- [ ] **Step 5: Make `step` return collision events**

In `SolarSystem.step`, change the early-return and the end of the method so the signature returns `list[CollisionEvent]`.

Change the signature line:

```python
    def step(self, dt: float) -> list[CollisionEvent]:
```

Change the empty-active early return:

```python
        active = [b for b in self._bodies if b.active]
        if not active:
            return []
```

And after the write-back loop (`body.vel = velocities[i]`), append:

```python
        return self._resolve_collisions()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `conda run -n nbodiesgravity pytest tests/engine/test_collisions.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 7: Run the full suite (no regressions)**

Run: `conda run -n nbodiesgravity pytest tests/ -v`
Expected: all existing tests still PASS (`step` callers ignore the new return value).

- [ ] **Step 8: Commit**

```bash
git add nbodiesgravity/engine/system.py tests/engine/test_collisions.py
git commit -m "feat: collision detection and momentum-conserving merge in SolarSystem"
git push
```

---

## Task 3: `collisions_detected` signal in `SimulationThread`

**Files:**
- Modify: `nbodiesgravity/engine/simulation_thread.py`
- Test: `tests/engine/test_simulation_thread.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/engine/test_simulation_thread.py`:

```python
import time as _time


def test_collisions_detected_signal_emitted(qapp):
    from nbodiesgravity.engine.body import CelestialBody
    from nbodiesgravity.engine.system import SolarSystem
    from nbodiesgravity.engine.simulation_thread import SimulationThread

    a = CelestialBody("A", 2.0e30, np.zeros(3), np.zeros(3), 695700.0, (1.0, 1.0, 1.0))
    b = CelestialBody("B", 1.0e24, np.array([1e-4, 0.0, 0.0]), np.zeros(3), 6371.0, (0.0, 0.0, 1.0))
    system = SolarSystem([a, b])

    thread = SimulationThread(system)
    recorded: list = []
    thread.collisions_detected.connect(lambda evs: recorded.extend(evs))
    thread.set_timescale(1.0)
    thread.resume()
    thread.start()
    try:
        deadline = _time.time() + 5.0
        while not recorded and _time.time() < deadline:
            qapp.processEvents()
            _time.sleep(0.01)
    finally:
        thread.stop_thread()

    assert recorded, "collisions_detected was not emitted"
    assert recorded[0].absorbed == "B"
    assert recorded[0].survivor == "A"
```

(Check the top of `test_simulation_thread.py`; `import numpy as np` is already present. If not, add it.)

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n nbodiesgravity pytest tests/engine/test_simulation_thread.py::test_collisions_detected_signal_emitted -v`
Expected: FAIL — `AttributeError: 'SimulationThread' object has no attribute 'collisions_detected'`.

- [ ] **Step 3: Declare the signal**

In `nbodiesgravity/engine/simulation_thread.py`, in the `SimulationThread` class signal block, add below `blow_up_detected`:

```python
    collisions_detected = pyqtSignal(list)   # list[CollisionEvent]
```

- [ ] **Step 4: Accumulate and emit events in `run`**

In `run()`, change the locked step loop so it collects returned events, then emit after publishing the snapshot. Replace the existing block:

```python
            with self._lock:
                remaining = sim_dt
                while remaining > 0:
                    step_dt = min(remaining, _MAX_SIM_DT)
                    self._system.step(step_dt)
                    remaining -= step_dt
                snap = self._system.snapshot()

            self._elapsed_days += sim_dt
            self.latest_snapshot = snap
            self.snapshot_ready.emit(snap)
```

with:

```python
            collisions: list = []
            with self._lock:
                remaining = sim_dt
                while remaining > 0:
                    step_dt = min(remaining, _MAX_SIM_DT)
                    collisions.extend(self._system.step(step_dt))
                    remaining -= step_dt
                snap = self._system.snapshot()

            self._elapsed_days += sim_dt
            self.latest_snapshot = snap
            self.snapshot_ready.emit(snap)
            if collisions:
                self.collisions_detected.emit(collisions)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `conda run -n nbodiesgravity pytest tests/engine/test_simulation_thread.py::test_collisions_detected_signal_emitted -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add nbodiesgravity/engine/simulation_thread.py tests/engine/test_simulation_thread.py
git commit -m "feat: emit collisions_detected from SimulationThread"
git push
```

---

## Task 4: Wire signal + `_on_collisions` slot in `MainWindow`

**Files:**
- Modify: `nbodiesgravity/ui/main_window.py`
- Test: `tests/ui/test_restart_and_collision.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/ui/test_restart_and_collision.py` (the `mock_opengl` autouse fixture at the top already covers OpenGL):

```python
def test_on_collisions_retargets_camera_and_refreshes(qapp):
    from nbodiesgravity.engine.body import CollisionEvent

    sun = CelestialBody("Sun", 1.989e30, np.zeros(3), np.zeros(3), 695700, (1.0, 0.9, 0.2), label="star")
    earth = CelestialBody("Earth", 5.972e24, np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0172, 0.0]), 6371, (0.2, 0.5, 1.0), label="planet")
    system = SolarSystem([sun, earth])

    window = MainWindow()
    window._load_system(system)
    try:
        window._gl.camera.set_center("Earth")

        # Simulate the merge the physics layer already performed: Earth absorbed by Sun.
        with window._sim._lock:
            window._sim.system.remove_body("Earth")

        window._on_collisions([CollisionEvent(absorbed="Earth", survivor="Sun")])

        # Camera retargeted off the absorbed body onto the survivor.
        assert window._gl.camera.center_name == "Sun"
        # Body list / system no longer contains the absorbed body.
        names = [b.name for b in window._sim.system.bodies]
        assert "Earth" not in names
        assert "Sun" in names
    finally:
        window._date_timer.stop()
        window._sim.stop_thread()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n nbodiesgravity pytest tests/ui/test_restart_and_collision.py::test_on_collisions_retargets_camera_and_refreshes -v`
Expected: FAIL — `AttributeError: 'MainWindow' object has no attribute '_on_collisions'`.

- [ ] **Step 3: Connect the signal**

In `nbodiesgravity/ui/main_window.py`, in `_load_system`, directly after the line:

```python
        self._sim.blow_up_detected.connect(self._on_blow_up)
```

add:

```python
        self._sim.collisions_detected.connect(self._on_collisions)
```

- [ ] **Step 4: Add the `_on_collisions` slot**

Add this method next to `_on_blow_up` in `MainWindow`:

```python
    def _on_collisions(self, events) -> None:
        """Handle merges reported by the physics thread (UI thread, queued).

        Retargets the camera if it was following an absorbed body, then rebuilds
        the body list, display infos, and center combo. Collisions are NOT
        mirrored into _initial_system, so Restart restores the pre-collision
        epoch state.
        """
        if self._sim is None:
            return
        center = self._gl.camera.center_name
        for ev in events:
            if ev.absorbed == center:
                self._gl.camera.set_center(ev.survivor)
                self._ctrl.set_center_name(ev.survivor)
                self._gl.clear_trails()
                break
        self._refresh_after_body_change()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `conda run -n nbodiesgravity pytest tests/ui/test_restart_and_collision.py::test_on_collisions_retargets_camera_and_refreshes -v`
Expected: PASS.

- [ ] **Step 6: Run the full suite**

Run: `conda run -n nbodiesgravity pytest tests/ -v`
Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add nbodiesgravity/ui/main_window.py tests/ui/test_restart_and_collision.py
git commit -m "feat: handle collisions_detected in MainWindow (camera retarget + refresh)"
git push
```

---

## Task 5: Documentation (CLAUDE.md)

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Document `CollisionEvent` and the engine behaviour**

In `CLAUDE.md` under `### engine/body.py`, add a bullet:

```markdown
- `CollisionEvent(NamedTuple)` — `absorbed, survivor` (body names). Returned by `SolarSystem.step()` when a merge occurs.
```

Under `### engine/system.py`, add to the `step(dt)` description that it now returns `list[CollisionEvent]`, and add a bullet:

```markdown
- `_resolve_collisions() → list[CollisionEvent]` — merges active bodies whose centres come within the sum of their physical radii (`KM_PER_AU = 1.495978707e8` converts km radii to AU). Survivor = larger mass (ties broken by alphabetically-first name); momentum conserved (`v = (mₛvₛ + mₐvₐ)/(mₛ+mₐ)`), mass summed, radius grows by equal-density volume (`r = (rₛ³ + rₐ³)^⅓`). Loops until no overlap remains so chains collapse in one call. Always on.
```

- [ ] **Step 2: Document the signal and slot**

Under `### engine/simulation_thread.py`, add `collisions_detected(list[CollisionEvent])` to the Signals line. Under `### ui/main_window.py`, add a bullet:

```markdown
- `_on_collisions(events)` — on merges from the physics thread: retargets the camera off an absorbed body onto its survivor, then calls `_refresh_after_body_change()`. Not mirrored into `_initial_system` — Restart restores the pre-collision epoch state.
```

Add the wiring row to the Signal/slot table:

```markdown
| `_sim` | `collisions_detected` | `_on_collisions` |
```

- [ ] **Step 3: Document the known limitation**

Under `## Common pitfalls` (or Key design decisions), add:

```markdown
- **Collision detection is per-step, not continuous.** Fast, small bodies can tunnel through each other between `step()` calls without registering a collision. Realistic collisions (into the Sun, or user-placed near-overlapping bodies) are caught. Continuous collision detection is out of scope.
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document collision merging behaviour"
git push
```

---

## Self-Review notes

- **Spec coverage:** detection geometry (Task 2 §3), merge math incl. momentum/mass/radius (Task 2), chained merges (Task 2), inactive exclusion (Task 2), `step` returns events (Task 2), thread signal (Task 3), UI refresh + camera retarget (Task 4), restart unaffected (Task 4 — not mirrored into `_initial_system`, asserted implicitly), docs + limitation (Task 5). All covered.
- **Type consistency:** `CollisionEvent(absorbed, survivor)` used identically across Tasks 1–4. `KM_PER_AU` defined in Task 2, imported in tests. `collisions_detected = pyqtSignal(list)` declared Task 3, connected Task 4.
- **No placeholders:** every code/test step is complete and runnable.
