# N-Body Gravity Simulation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python desktop application that numerically simulates and displays gravitational orbits in 3D, defaulting to the solar system (~20 bodies) with full interactivity.

**Architecture:** Physics engine (Velocity Verlet, NumPy-vectorized) runs in a `QThread`, emitting position snapshots to a `QOpenGLWidget` rendering at 60 FPS. A data layer fetches initial state vectors from a bundled J2000 snapshot or the JPL Horizons API with local caching. Four Qt panels (GL viewport, body list, control panel, body editor dialog) are assembled in `QMainWindow`.

**Tech Stack:** Python 3.11, NumPy, PyQt6, PyOpenGL, requests, pytest. Conda env: `nbodiesgravity`.

---

## File Map

```
nbodiesgravity/
├── main.py                        # entry point, QApplication + QSurfaceFormat setup
├── engine/
│   ├── __init__.py
│   ├── body.py                    # BodyState (NamedTuple), CelestialBody (dataclass)
│   ├── integrator.py              # VelocityVerletIntegrator — pure NumPy, stateless
│   ├── system.py                  # SolarSystem — owns body list, step/snapshot/add/remove
│   └── simulation_thread.py      # QThread — runs step() loop, exposes latest_snapshot
├── data/
│   ├── __init__.py
│   ├── horizons.py                # JPL Horizons REST client, HorizonsError
│   ├── cache.py                   # ~/.nbodiesgravity/cache.json read/write
│   ├── loader.py                  # load_default_system(), load_system_at_date()
│   └── snapshots/
│       └── j2000.json             # pre-fetched state vectors for 20 bodies at J2000
├── rendering/
│   ├── __init__.py
│   ├── display_info.py            # BodyDisplayInfo dataclass (name, radius_km, color, is_star)
│   ├── camera.py                  # Camera — center tracking, view matrix, mouse rotation/zoom
│   ├── sphere_mesh.py             # SphereMesh VBO + GLSL shader sources (sphere + line)
│   ├── trail_buffer.py            # TrailBuffer — ring buffer → GPU line-strip VBO
│   └── gl_widget.py               # GLWidget(QOpenGLWidget) — 60 FPS render loop, mouse events
├── ui/
│   ├── __init__.py
│   ├── main_window.py             # QMainWindow — full layout, menus, toolbar, all wiring
│   ├── control_panel.py           # QDateEdit, speed slider, center combo, play/pause
│   ├── body_list_panel.py         # QListWidget with colour dots and trail checkboxes
│   ├── body_editor_dialog.py      # QDialog for add / edit body with validation
│   └── date_loader_worker.py      # QThread worker — fetch all bodies at a date, emit progress

scripts/
├── fetch_j2000.py                 # one-time script: fetch J2000 vectors from JPL → j2000.json
└── smoke_test_headless.py         # Milestone 1 matplotlib smoke test

tests/
├── __init__.py
├── engine/
│   ├── __init__.py
│   ├── test_body.py
│   ├── test_integrator.py
│   └── test_system.py
└── data/
    ├── __init__.py
    ├── test_cache.py
    ├── test_horizons.py
    └── test_loader.py
```

---

## Milestone 1 — Headless Engine

---

### Task 1: Project scaffold

**Files:**
- Create: `environment.yml`
- Create: `pyproject.toml`
- Create: all `__init__.py` files listed in the file map
- Create: `nbodiesgravity/data/snapshots/` directory
- Create: `scripts/` directory

- [ ] **Step 1: Create `environment.yml`**

```yaml
name: nbodiesgravity
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.11
  - numpy>=1.24
  - matplotlib>=3.7
  - pip
  - pip:
    - PyQt6>=6.5
    - PyOpenGL>=3.1
    - PyOpenGL-accelerate>=3.1
    - requests>=2.31
    - responses>=0.23
    - pytest>=7.4
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[project]
name = "nbodiesgravity"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 3: Install dependencies into the existing conda env**

Run: `conda run -n nbodiesgravity pip install PyQt6 "PyOpenGL>=3.1" "PyOpenGL-accelerate>=3.1" requests responses pytest matplotlib`

Expected: `Successfully installed` (no errors)

- [ ] **Step 4: Create all empty `__init__.py` files**

Create these as empty files:
- `nbodiesgravity/__init__.py`
- `nbodiesgravity/engine/__init__.py`
- `nbodiesgravity/data/__init__.py`
- `nbodiesgravity/rendering/__init__.py`
- `nbodiesgravity/ui/__init__.py`
- `tests/__init__.py`
- `tests/engine/__init__.py`
- `tests/data/__init__.py`

Also create empty directories: `nbodiesgravity/data/snapshots/`, `scripts/`

- [ ] **Step 5: Verify pytest discovers zero tests**

Run: `conda run -n nbodiesgravity python -m pytest --collect-only`

Expected: `no tests ran`

- [ ] **Step 6: Commit**

```bash
git add environment.yml pyproject.toml nbodiesgravity/ tests/ scripts/
git commit -m "feat: scaffold project structure and install dependencies"
```

---

### Task 2: `engine/body.py` — BodyState and CelestialBody

**Files:**
- Create: `nbodiesgravity/engine/body.py`
- Create: `tests/engine/test_body.py`

- [ ] **Step 1: Write the failing tests**

`tests/engine/test_body.py`:
```python
import numpy as np
from nbodiesgravity.engine.body import BodyState, CelestialBody


def test_body_state_copies_arrays():
    pos = np.array([1.0, 2.0, 3.0])
    vel = np.array([0.1, 0.2, 0.3])
    state = BodyState(name="Earth", pos=pos.copy(), vel=vel.copy())
    pos[0] = 999.0
    assert state.pos[0] == 1.0  # must not reflect mutation of original


def test_body_state_fields():
    state = BodyState(name="Mars", pos=np.zeros(3), vel=np.ones(3))
    assert state.name == "Mars"
    assert state.pos.shape == (3,)
    assert state.vel.shape == (3,)


def test_celestial_body_snapshot_is_copy():
    body = CelestialBody(
        name="Earth", mass=5.972e24,
        pos=np.array([1.0, 0.0, 0.0]),
        vel=np.array([0.0, 0.01720, 0.0]),
        radius=6371.0, color=(0.2, 0.5, 1.0),
    )
    snap = body.snapshot()
    assert snap.name == "Earth"
    assert np.allclose(snap.pos, [1.0, 0.0, 0.0])
    body.pos[0] = 99.0       # mutate the body
    assert snap.pos[0] == 1.0  # snapshot must not change


def test_celestial_body_show_trail_default():
    body = CelestialBody(
        name="Test", mass=1e20, pos=np.zeros(3), vel=np.zeros(3),
        radius=100.0, color=(1.0, 1.0, 1.0),
    )
    assert body.show_trail is True
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `conda run -n nbodiesgravity python -m pytest tests/engine/test_body.py -v`

Expected: `ModuleNotFoundError: No module named 'nbodiesgravity.engine.body'`

- [ ] **Step 3: Implement `nbodiesgravity/engine/body.py`**

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import NamedTuple
import numpy as np


class BodyState(NamedTuple):
    """Thread-safe snapshot of a body's kinematic state.

    Use NamedTuple so the object is immutable at the Python level.
    Array *contents* can still be mutated, so snapshot() copies them.
    """
    name: str
    pos: np.ndarray   # AU, shape (3,)
    vel: np.ndarray   # AU/day, shape (3,)


@dataclass
class CelestialBody:
    """A gravitationally interacting body.

    Positions and velocities are always stored in the Solar System
    Barycenter (SSB) frame, in units of AU and AU/day.
    """
    name: str
    mass: float                         # kg
    pos: np.ndarray                     # AU, shape (3,)
    vel: np.ndarray                     # AU/day, shape (3,)
    radius: float                       # km — for rendering only
    color: tuple[float, float, float]   # RGB 0–1
    show_trail: bool = True

    def snapshot(self) -> BodyState:
        """Return a thread-safe copy of kinematic state."""
        return BodyState(name=self.name, pos=self.pos.copy(), vel=self.vel.copy())
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `conda run -n nbodiesgravity python -m pytest tests/engine/test_body.py -v`

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add nbodiesgravity/engine/body.py tests/engine/test_body.py
git commit -m "feat: add BodyState and CelestialBody datatypes"
```

---

### Task 3: `engine/integrator.py` — Velocity Verlet

**Files:**
- Create: `nbodiesgravity/engine/integrator.py`
- Create: `tests/engine/test_integrator.py`

- [ ] **Step 1: Write the failing tests**

`tests/engine/test_integrator.py`:
```python
import numpy as np
from nbodiesgravity.engine.integrator import VelocityVerletIntegrator, G_AU_DAY


def test_single_body_no_force():
    """A lone body must travel in a straight line at constant velocity."""
    masses = np.array([1.989e30])
    pos = np.array([[0.0, 0.0, 0.0]])
    vel = np.array([[1.0, 0.0, 0.0]])
    itg = VelocityVerletIntegrator()
    new_pos, new_vel = itg.step(pos, vel, masses, dt=1.0)
    assert np.allclose(new_pos, [[1.0, 0.0, 0.0]], atol=1e-10)
    assert np.allclose(new_vel, [[1.0, 0.0, 0.0]], atol=1e-10)


def test_two_body_earth_returns_near_start_after_one_year():
    """Earth should be close to its starting position after ~365 steps of dt=1 day."""
    masses = np.array([1.989e30, 5.972e24])
    pos = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    vel = np.array([[0.0, 0.0, 0.0], [0.0, 0.017202, 0.0]])
    itg = VelocityVerletIntegrator()
    for _ in range(365):
        pos, vel = itg.step(pos, vel, masses, dt=1.0)
    assert np.linalg.norm(pos[1] - np.array([1.0, 0.0, 0.0])) < 0.05


def test_two_body_energy_conservation():
    """Total energy must drift less than 0.01% over 1000 steps of dt=1 day."""
    m_sun, m_earth = 1.989e30, 5.972e24
    masses = np.array([m_sun, m_earth])
    pos = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    vel = np.array([[0.0, 0.0, 0.0], [0.0, 0.017202, 0.0]])

    def total_energy(p, v):
        ke = 0.5 * np.sum(masses[:, np.newaxis] * v ** 2)
        r = np.linalg.norm(p[1] - p[0])
        return ke - G_AU_DAY * m_sun * m_earth / r

    itg = VelocityVerletIntegrator()
    e0 = total_energy(pos, vel)
    for _ in range(1000):
        pos, vel = itg.step(pos, vel, masses, dt=1.0)
    e1 = total_energy(pos, vel)
    assert abs((e1 - e0) / e0) < 1e-4


def test_accelerations_shape():
    """_accelerations must return (N, 3) for N bodies."""
    itg = VelocityVerletIntegrator()
    pos = np.random.rand(5, 3)
    masses = np.ones(5) * 1e24
    acc = itg._accelerations(pos, masses)
    assert acc.shape == (5, 3)
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `conda run -n nbodiesgravity python -m pytest tests/engine/test_integrator.py -v`

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement `nbodiesgravity/engine/integrator.py`**

```python
"""Velocity Verlet integrator for N-body gravitational simulation.

Units throughout: AU (position), AU/day (velocity), AU³ kg⁻¹ day⁻² (G).
The integrator is fully stateless: arrays in, arrays out.
"""
from __future__ import annotations
import numpy as np

# Convert G from SI to AU³ kg⁻¹ day⁻²
# G_SI = 6.674e-11 m³ kg⁻¹ s⁻²
# 1 AU = 1.495978707e11 m,  1 day = 86400 s
G_AU_DAY: float = 6.674e-11 * (86400.0 ** 2) / (1.495978707e11 ** 3)

#: Softening length (AU) — prevents force singularities at close approach
SOFTENING: float = 1e-4


class VelocityVerletIntegrator:
    """Symplectic Velocity Verlet integrator.

    Conserves orbital energy far better than plain Euler integration
    over long time spans, making it suitable for multi-year simulations.
    """

    def __init__(self, softening: float = SOFTENING) -> None:
        self.softening = softening

    def _accelerations(
        self, positions: np.ndarray, masses: np.ndarray
    ) -> np.ndarray:
        """Return gravitational accelerations for all bodies.

        Parameters
        ----------
        positions : (N, 3) ndarray — body positions in AU
        masses    : (N,)   ndarray — body masses in kg

        Returns
        -------
        (N, 3) ndarray — accelerations in AU day⁻²
        """
        # diff[i, j] = r_j - r_i, shape (N, N, 3)
        diff = positions[np.newaxis, :, :] - positions[:, np.newaxis, :]
        # Squared distance with softening, shape (N, N)
        dist_sq = np.einsum("ijk,ijk->ij", diff, diff) + self.softening ** 2
        dist_cubed = dist_sq ** 1.5
        # factor[i, j] = G * m_j / |r_j - r_i|³
        factor = G_AU_DAY * masses[np.newaxis, :] / dist_cubed
        np.fill_diagonal(factor, 0.0)   # zero out self-interaction
        # acc[i] = Σ_j factor[i,j] * diff[i,j]
        return np.einsum("ij,ijk->ik", factor, diff)

    def step(
        self,
        positions: np.ndarray,
        velocities: np.ndarray,
        masses: np.ndarray,
        dt: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Advance by one timestep dt (days).

        Returns new (positions, velocities), both (N, 3).
        """
        a0 = self._accelerations(positions, masses)
        new_pos = positions + velocities * dt + 0.5 * a0 * dt ** 2
        a1 = self._accelerations(new_pos, masses)
        new_vel = velocities + 0.5 * (a0 + a1) * dt
        return new_pos, new_vel
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `conda run -n nbodiesgravity python -m pytest tests/engine/test_integrator.py -v`

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add nbodiesgravity/engine/integrator.py tests/engine/test_integrator.py
git commit -m "feat: add Velocity Verlet integrator with energy conservation test"
```

---

### Task 4: `engine/system.py` — SolarSystem

**Files:**
- Create: `nbodiesgravity/engine/system.py`
- Create: `tests/engine/test_system.py`

- [ ] **Step 1: Write the failing tests**

`tests/engine/test_system.py`:
```python
import numpy as np
from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.system import SolarSystem


def _sun():
    return CelestialBody(
        name="Sun", mass=1.989e30, pos=np.zeros(3), vel=np.zeros(3),
        radius=695700, color=(1.0, 0.9, 0.2),
    )

def _earth():
    return CelestialBody(
        name="Earth", mass=5.972e24,
        pos=np.array([1.0, 0.0, 0.0]),
        vel=np.array([0.0, 0.017202, 0.0]),
        radius=6371, color=(0.2, 0.5, 1.0),
    )


def test_step_moves_earth():
    system = SolarSystem([_sun(), _earth()])
    initial = system.bodies[1].pos.copy()
    system.step(1.0)
    assert not np.allclose(system.bodies[1].pos, initial)


def test_snapshot_is_independent_copy():
    system = SolarSystem([_earth()])
    snap = system.snapshot()
    snap[0].pos[0] = 999.0           # mutate snapshot
    assert system.bodies[0].pos[0] == 1.0  # original unchanged


def test_snapshot_names_match_body_order():
    system = SolarSystem([_sun(), _earth()])
    snap = system.snapshot()
    assert [s.name for s in snap] == ["Sun", "Earth"]


def test_add_remove_body():
    system = SolarSystem([_sun()])
    system.add_body(_earth())
    assert len(system.bodies) == 2
    system.remove_body("Earth")
    assert len(system.bodies) == 1
    assert system.bodies[0].name == "Sun"


def test_remove_nonexistent_is_noop():
    system = SolarSystem([_sun()])
    system.remove_body("Ghost")
    assert len(system.bodies) == 1


def test_get_body_found_and_not_found():
    system = SolarSystem([_sun(), _earth()])
    assert system.get_body("Earth") is not None
    assert system.get_body("Mars") is None


def test_empty_system_step_does_not_raise():
    system = SolarSystem([])
    system.step(1.0)  # must not raise
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `conda run -n nbodiesgravity python -m pytest tests/engine/test_system.py -v`

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement `nbodiesgravity/engine/system.py`**

```python
from __future__ import annotations
import numpy as np
from .body import CelestialBody, BodyState
from .integrator import VelocityVerletIntegrator


class SolarSystem:
    """Owns a collection of CelestialBody objects and advances them in time.

    add_body / remove_body must only be called while the SimulationThread
    is paused — they are not thread-safe.
    """

    def __init__(self, bodies: list[CelestialBody]) -> None:
        self._bodies: list[CelestialBody] = list(bodies)
        self._integrator = VelocityVerletIntegrator()

    @property
    def bodies(self) -> list[CelestialBody]:
        """Shallow copy — callers cannot mutate the internal list."""
        return list(self._bodies)

    def step(self, dt: float) -> None:
        """Advance all bodies by dt days using Velocity Verlet."""
        if not self._bodies:
            return
        positions = np.array([b.pos for b in self._bodies])
        velocities = np.array([b.vel for b in self._bodies])
        masses = np.array([b.mass for b in self._bodies])
        new_pos, new_vel = self._integrator.step(positions, velocities, masses, dt)
        for i, body in enumerate(self._bodies):
            body.pos = new_pos[i]
            body.vel = new_vel[i]

    def snapshot(self) -> list[BodyState]:
        """Return a thread-safe copy of all body states."""
        return [b.snapshot() for b in self._bodies]

    def add_body(self, body: CelestialBody) -> None:
        """Append a body. Call only while simulation is paused."""
        self._bodies.append(body)

    def remove_body(self, name: str) -> None:
        """Remove the named body. No-op if not found."""
        self._bodies = [b for b in self._bodies if b.name != name]

    def get_body(self, name: str) -> CelestialBody | None:
        for b in self._bodies:
            if b.name == name:
                return b
        return None
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `conda run -n nbodiesgravity python -m pytest tests/engine/test_system.py -v`

Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add nbodiesgravity/engine/system.py tests/engine/test_system.py
git commit -m "feat: add SolarSystem with step, snapshot, add/remove/get body"
```

---

### Task 5: `data/cache.py` — local JSON cache

**Files:**
- Create: `nbodiesgravity/data/cache.py`
- Create: `tests/data/test_cache.py`

- [ ] **Step 1: Write the failing tests**

`tests/data/test_cache.py`:
```python
from datetime import date
import pytest


@pytest.fixture()
def cache(tmp_path, monkeypatch):
    """Redirect cache file to a temp dir so tests never touch ~/.nbodiesgravity."""
    import nbodiesgravity.data.cache as mod
    monkeypatch.setattr(mod, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(mod, "CACHE_FILE", tmp_path / "cache.json")
    return mod


def test_miss_returns_none(cache):
    assert cache.get("399", date(2000, 1, 1)) is None


def test_store_and_retrieve(cache):
    state = {"pos_au": [1.0, 0.0, 0.0], "vel_au_per_day": [0.0, 0.017202, 0.0]}
    cache.store("399", date(2000, 1, 1), state)
    assert cache.get("399", date(2000, 1, 1)) == state


def test_different_dates_are_independent(cache):
    a = {"pos_au": [1.0, 0.0, 0.0], "vel_au_per_day": [0.0, 0.017, 0.0]}
    b = {"pos_au": [0.0, 1.0, 0.0], "vel_au_per_day": [-0.017, 0.0, 0.0]}
    cache.store("399", date(2000, 1, 1), a)
    cache.store("399", date(2001, 1, 1), b)
    assert cache.get("399", date(2000, 1, 1)) == a
    assert cache.get("399", date(2001, 1, 1)) == b


def test_clear_cache_removes_file(cache, tmp_path):
    cache.store("399", date(2000, 1, 1), {"pos_au": [1, 0, 0], "vel_au_per_day": [0, 0, 0]})
    assert (tmp_path / "cache.json").exists()
    cache.clear_cache()
    assert not (tmp_path / "cache.json").exists()


def test_clear_nonexistent_cache_does_not_raise(cache):
    cache.clear_cache()  # file does not exist — must not raise
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `conda run -n nbodiesgravity python -m pytest tests/data/test_cache.py -v`

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement `nbodiesgravity/data/cache.py`**

```python
"""Local JSON cache for JPL Horizons query results.

Cache file: ~/.nbodiesgravity/cache.json
Key format: "{body_id}_{YYYY-MM-DD}"
Entries never expire — orbital mechanics are deterministic.
"""
from __future__ import annotations
import json
from datetime import date
from pathlib import Path

CACHE_DIR: Path = Path.home() / ".nbodiesgravity"
CACHE_FILE: Path = CACHE_DIR / "cache.json"


def _load() -> dict:
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save(data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _key(body_id: str, epoch_date: date) -> str:
    return f"{body_id}_{epoch_date.strftime('%Y-%m-%d')}"


def get(body_id: str, epoch_date: date) -> dict | None:
    """Return cached state dict, or None if not present."""
    return _load().get(_key(body_id, epoch_date))


def store(body_id: str, epoch_date: date, state: dict) -> None:
    """Persist a state dict keyed by body_id and date."""
    data = _load()
    data[_key(body_id, epoch_date)] = state
    _save(data)


def clear_cache() -> None:
    """Delete the cache file. No-op if it does not exist."""
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `conda run -n nbodiesgravity python -m pytest tests/data/test_cache.py -v`

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add nbodiesgravity/data/cache.py tests/data/test_cache.py
git commit -m "feat: add local JSON cache for Horizons query results"
```

---

### Task 6: `data/horizons.py` — JPL Horizons client

**Files:**
- Create: `nbodiesgravity/data/horizons.py`
- Create: `tests/data/test_horizons.py`

- [ ] **Step 1: Write the failing tests**

`tests/data/test_horizons.py`:
```python
import pytest
import responses as resp_mock
from datetime import date
from nbodiesgravity.data.horizons import fetch, HorizonsError, HORIZONS_URL

# Minimal realistic Horizons vector-table response
_MOCK_RESULT = (
    "Ephemeris / API_USER\n"
    "$$SOE\n"
    "2451545.000000000 = A.D. 2000-Jan-01 12:00:00.0000 TDB \n"
    " X = 1.068727563E-01 Y =-9.259066609E-01 Z =-4.013741985E-04\n"
    " VX= 1.725849684E-02 VY= 2.067254143E-03 VZ=-2.128408063E-04\n"
    " LT= 5.365027063E-03 RG= 9.274975424E-01 RR= 2.484052831E-03\n"
    "$$EOE\n"
)


@resp_mock.activate
def test_fetch_returns_pos_and_vel():
    resp_mock.add(resp_mock.GET, HORIZONS_URL, json={"result": _MOCK_RESULT}, status=200)
    result = fetch("399", date(2000, 1, 1))
    assert "pos_au" in result and "vel_au_per_day" in result
    assert len(result["pos_au"]) == 3
    assert len(result["vel_au_per_day"]) == 3
    assert abs(result["pos_au"][0] - 1.068727563e-01) < 1e-8
    assert abs(result["vel_au_per_day"][0] - 1.725849684e-02) < 1e-10


@resp_mock.activate
def test_fetch_raises_on_network_error():
    resp_mock.add(resp_mock.GET, HORIZONS_URL, body=ConnectionError("timeout"))
    with pytest.raises(HorizonsError, match="Network error"):
        fetch("399", date(2000, 1, 1))


@resp_mock.activate
def test_fetch_raises_on_api_error_field():
    resp_mock.add(resp_mock.GET, HORIZONS_URL, json={"error": "No match"}, status=200)
    with pytest.raises(HorizonsError, match="Horizons error"):
        fetch("399", date(2000, 1, 1))


@resp_mock.activate
def test_fetch_raises_when_soe_missing():
    resp_mock.add(resp_mock.GET, HORIZONS_URL, json={"result": "no data here"}, status=200)
    with pytest.raises(HorizonsError, match="SOE"):
        fetch("399", date(2000, 1, 1))
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `conda run -n nbodiesgravity python -m pytest tests/data/test_horizons.py -v`

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement `nbodiesgravity/data/horizons.py`**

```python
"""JPL Horizons REST API client.

Fetches state vectors (position + velocity) for a solar-system body
at a given date, relative to the Solar System Barycenter (SSB).

API docs: https://ssd.jpl.nasa.gov/horizons/app.html
"""
from __future__ import annotations
import re
from datetime import date
from pathlib import Path
import requests

HORIZONS_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
_LOG_FILE = Path.home() / ".nbodiesgravity" / "horizons_error.log"


class HorizonsError(Exception):
    """Raised on network failure or unparseable Horizons response."""


def _log_error(body_id: str, text: str) -> None:
    _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"--- body_id={body_id} ---\n{text}\n\n")


def fetch(body_id: str, epoch_date: date) -> dict:
    """Fetch state vectors from JPL Horizons.

    Parameters
    ----------
    body_id    : JPL COMMAND identifier, e.g. "399" (Earth), "1;" (Ceres)
    epoch_date : the date for which to retrieve vectors

    Returns
    -------
    dict with "pos_au" (list[float]) and "vel_au_per_day" (list[float])

    Raises
    ------
    HorizonsError on network failure, API error, or unparseable response.
    """
    date_str = epoch_date.strftime("%Y-%m-%d")
    params = {
        "format": "json",
        "COMMAND": f"'{body_id}'",
        "OBJ_DATA": "NO",
        "MAKE_EPHEM": "YES",
        "EPHEM_TYPE": "VECTORS",
        "CENTER": "'500@0'",
        "START_TIME": f"'{date_str}'",
        "STOP_TIME": f"'{date_str}'",
        "STEP_SIZE": "'1 d'",
        "VEC_TABLE": "'2'",
        "OUT_UNITS": "'AU-D'",
        "REF_PLANE": "ECLIPTIC",
        "REF_SYSTEM": "J2000",
        "CSV_FORMAT": "NO",
    }
    try:
        resp = requests.get(HORIZONS_URL, params=params, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise HorizonsError(f"Network error fetching body {body_id}: {exc}") from exc

    data = resp.json()
    if "error" in data:
        _log_error(body_id, str(data))
        raise HorizonsError(f"Horizons error for body {body_id}: {data['error']}")

    return _parse_vectors(body_id, data.get("result", ""))


def _parse_vectors(body_id: str, result_text: str) -> dict:
    match = re.search(r"\$\$SOE(.*?)\$\$EOE", result_text, re.DOTALL)
    if not match:
        raise HorizonsError(
            f"Could not find $$SOE/$$EOE block in Horizons response for body {body_id}"
        )
    block = match.group(1)
    return {
        "pos_au": [_val(body_id, block, k) for k in ("X", "Y", "Z")],
        "vel_au_per_day": [_val(body_id, block, k) for k in ("VX", "VY", "VZ")],
    }


def _val(body_id: str, text: str, key: str) -> float:
    m = re.search(rf"{re.escape(key)}\s*=\s*([-+]?\d+\.\d+[Ee][+-]?\d+)", text)
    if not m:
        raise HorizonsError(
            f"Could not parse '{key}' from Horizons response for body {body_id}"
        )
    return float(m.group(1))
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `conda run -n nbodiesgravity python -m pytest tests/data/test_horizons.py -v`

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add nbodiesgravity/data/horizons.py tests/data/test_horizons.py
git commit -m "feat: add JPL Horizons REST client with HorizonsError and mocked tests"
```

---

### Task 7: `data/loader.py` + fetch script + `j2000.json`

**Files:**
- Create: `scripts/fetch_j2000.py`
- Create: `nbodiesgravity/data/snapshots/j2000.json` (generated by the script)
- Create: `nbodiesgravity/data/loader.py`
- Create: `tests/data/test_loader.py`

- [ ] **Step 1: Create `scripts/fetch_j2000.py`**

```python
"""One-time script: fetch J2000 state vectors for all default bodies.

Run once (requires internet):
    conda run -n nbodiesgravity python scripts/fetch_j2000.py

Writes: nbodiesgravity/data/snapshots/j2000.json
Then commit the file to the repo.

Notes on Horizons IDs
---------------------
- Major planets / satellites: plain number, e.g. "399" (Earth)
- Small bodies (Ceres, Eris): append semicolon for disambiguation, e.g. "1;"
"""
import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from nbodiesgravity.data.horizons import fetch, HorizonsError

J2000 = date(2000, 1, 1)

# (name, horizons_id, mass_kg, radius_km, color_rgb)
BODIES = [
    ("Sun",      "10",       1.989e30,  695700, [1.0, 0.9, 0.2]),
    ("Mercury",  "199",      3.301e23,    2440, [0.7, 0.7, 0.7]),
    ("Venus",    "299",      4.867e24,    6052, [0.9, 0.8, 0.5]),
    ("Earth",    "399",      5.972e24,    6371, [0.2, 0.5, 1.0]),
    ("Mars",     "499",      6.417e23,    3390, [0.9, 0.4, 0.2]),
    ("Jupiter",  "599",      1.898e27,   69911, [0.8, 0.7, 0.5]),
    ("Saturn",   "699",      5.683e26,   58232, [0.9, 0.8, 0.6]),
    ("Uranus",   "799",      8.681e25,   25362, [0.5, 0.8, 0.9]),
    ("Neptune",  "899",      1.024e26,   24622, [0.3, 0.4, 0.9]),
    ("Moon",     "301",      7.342e22,    1737, [0.8, 0.8, 0.8]),
    ("Io",       "501",      8.932e22,    1822, [1.0, 0.8, 0.3]),
    ("Europa",   "502",      4.800e22,    1561, [0.8, 0.7, 0.6]),
    ("Ganymede", "503",      1.482e23,    2634, [0.5, 0.5, 0.5]),
    ("Callisto", "504",      1.076e23,    2410, [0.4, 0.4, 0.4]),
    ("Titan",    "606",      1.345e23,    2575, [0.9, 0.7, 0.4]),
    ("Triton",   "801",      2.139e22,    1354, [0.7, 0.8, 0.9]),
    ("Pluto",    "999",      1.307e22,    1188, [0.8, 0.7, 0.6]),
    ("Charon",   "901",      1.586e21,     606, [0.6, 0.6, 0.6]),
    ("Eris",     "136199;",  1.660e22,    1163, [0.9, 0.9, 0.9]),
    ("Ceres",    "1;",       9.383e20,     473, [0.6, 0.6, 0.6]),
]

OUT = (
    Path(__file__).parent.parent
    / "nbodiesgravity" / "data" / "snapshots" / "j2000.json"
)


def main() -> None:
    entries = []
    for name, body_id, mass_kg, radius_km, color in BODIES:
        print(f"  {name:10s} ({body_id:8s})...", end=" ", flush=True)
        try:
            state = fetch(body_id, J2000)
        except HorizonsError as exc:
            print(f"FAILED: {exc}")
            sys.exit(1)
        entries.append({
            "name": name, "id": body_id,
            "mass_kg": mass_kg, "radius_km": radius_km, "color": color,
            "pos_au": state["pos_au"],
            "vel_au_per_day": state["vel_au_per_day"],
        })
        print("OK")
        time.sleep(0.4)   # be polite to the JPL API

    snapshot = {
        "epoch": "2000-01-01T12:00:00",
        "description": "J2000 state vectors for default solar system bodies",
        "bodies": entries,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)
    print(f"\nWrote {len(entries)} bodies to {OUT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the fetch script (requires internet)**

Run: `conda run -n nbodiesgravity python scripts/fetch_j2000.py`

Expected: 20 lines of `<name> ... OK`, then `Wrote 20 bodies to ...j2000.json`

If a small body fails (Eris, Ceres), try changing `"136199;"` → `"136199"` or `"1;"` → `"2000001"` in the BODIES list and re-run.

- [ ] **Step 3: Write the failing tests for `loader.py`**

`tests/data/test_loader.py`:
```python
import numpy as np
from datetime import datetime
import pytest
from nbodiesgravity.data.loader import load_default_system, load_system_at_date
from nbodiesgravity.engine.system import SolarSystem


def test_load_default_returns_solar_system():
    system = load_default_system()
    assert isinstance(system, SolarSystem)


def test_load_default_has_20_bodies():
    system = load_default_system()
    assert len(system.bodies) == 20


def test_load_default_contains_sun_earth_moon():
    system = load_default_system()
    names = {b.name for b in system.bodies}
    assert {"Sun", "Earth", "Moon"}.issubset(names)


def test_earth_near_1_au_at_j2000():
    system = load_default_system()
    earth = system.get_body("Earth")
    assert earth is not None
    assert 0.9 < np.linalg.norm(earth.pos) < 1.1


def test_load_at_date_uses_cache_on_second_call(tmp_path, monkeypatch):
    import nbodiesgravity.data.cache as cache_mod
    import nbodiesgravity.data.loader as loader_mod

    monkeypatch.setattr(cache_mod, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(cache_mod, "CACHE_FILE", tmp_path / "cache.json")

    calls = []

    def fake_fetch(body_id, epoch_date):
        calls.append(body_id)
        return {"pos_au": [1.0, 0.0, 0.0], "vel_au_per_day": [0.0, 0.017, 0.0]}

    monkeypatch.setattr(loader_mod, "_fetch_from_horizons", fake_fetch)

    epoch = datetime(2020, 6, 1)
    load_system_at_date(epoch, progress_cb=lambda _: None)
    n_first = len(calls)

    # Second call with same date — cache must serve all bodies, no new fetches
    load_system_at_date(epoch, progress_cb=lambda _: None)
    assert len(calls) == n_first   # no additional Horizons calls
```

- [ ] **Step 4: Run tests — verify they fail**

Run: `conda run -n nbodiesgravity python -m pytest tests/data/test_loader.py -v`

Expected: `ModuleNotFoundError` or `FileNotFoundError`

- [ ] **Step 5: Implement `nbodiesgravity/data/loader.py`**

```python
"""Assembles a SolarSystem from the bundled J2000 snapshot or JPL Horizons.

Public API
----------
load_default_system() -> SolarSystem
    Reads j2000.json. Synchronous, no network required.

load_system_at_date(epoch, progress_cb) -> SolarSystem
    Checks local cache; falls back to JPL Horizons.
    Designed to run inside a QThread worker (DateLoaderWorker).
"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Callable
import numpy as np

from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.system import SolarSystem
import nbodiesgravity.data.cache as _cache
# Indirected name so tests can monkeypatch _fetch_from_horizons
from nbodiesgravity.data.horizons import fetch as _fetch_from_horizons  # noqa: F401

SNAPSHOT_PATH: Path = Path(__file__).parent / "snapshots" / "j2000.json"


def _read_snapshot() -> dict:
    with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _body_from_entry(
    entry: dict, pos_au: list[float], vel_au_per_day: list[float]
) -> CelestialBody:
    return CelestialBody(
        name=entry["name"],
        mass=entry["mass_kg"],
        pos=np.array(pos_au, dtype=float),
        vel=np.array(vel_au_per_day, dtype=float),
        radius=entry["radius_km"],
        color=tuple(entry["color"]),
    )


def load_default_system() -> SolarSystem:
    """Build a SolarSystem from the bundled J2000 snapshot. Instant."""
    snapshot = _read_snapshot()
    bodies = [
        _body_from_entry(e, e["pos_au"], e["vel_au_per_day"])
        for e in snapshot["bodies"]
    ]
    return SolarSystem(bodies)


def load_system_at_date(
    epoch: datetime,
    progress_cb: Callable[[str], None],
) -> SolarSystem:
    """Fetch state vectors for all default bodies at *epoch*.

    For each body: checks local cache first, then queries JPL Horizons.
    Calls progress_cb(body_name) after each body is resolved.
    Raises HorizonsError if any body cannot be fetched.
    """
    # Import here so monkeypatching the module-level name works in tests
    import nbodiesgravity.data.loader as _self
    fetch_fn = _self._fetch_from_horizons

    snapshot = _read_snapshot()
    epoch_date = epoch.date()
    bodies = []
    for entry in snapshot["bodies"]:
        body_id = entry["id"]
        state = _cache.get(body_id, epoch_date)
        if state is None:
            state = fetch_fn(body_id, epoch_date)
            _cache.store(body_id, epoch_date, state)
        bodies.append(_body_from_entry(entry, state["pos_au"], state["vel_au_per_day"]))
        progress_cb(entry["name"])
    return SolarSystem(bodies)
```

- [ ] **Step 6: Run tests — verify they pass**

Run: `conda run -n nbodiesgravity python -m pytest tests/data/test_loader.py -v`

Expected: `5 passed`

- [ ] **Step 7: Commit**

```bash
git add scripts/fetch_j2000.py nbodiesgravity/data/loader.py tests/data/test_loader.py nbodiesgravity/data/snapshots/j2000.json
git commit -m "feat: add data loader, j2000 snapshot, and one-time fetch script"
```

---

### Task 8: Headless smoke test — matplotlib 2D orbit plot (Milestone 1 complete)

**Files:**
- Create: `scripts/smoke_test_headless.py`

- [ ] **Step 1: Create `scripts/smoke_test_headless.py`**

```python
"""Milestone 1 smoke test: Sun + Earth + Moon orbits over 60 simulated days.

Run:
    conda run -n nbodiesgravity python scripts/smoke_test_headless.py

Expected: matplotlib window showing Earth arcing around the Sun and the
Moon spiralling around Earth's path (60 days ≈ 1/6th of one Earth orbit).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import matplotlib.pyplot as plt
from nbodiesgravity.data.loader import load_default_system

STEPS, DT = 60, 1.0   # 60 days, 1 day per step

system = load_default_system()
# Keep only the three bodies to speed up the test
for name in [b.name for b in system.bodies]:
    if name not in {"Sun", "Earth", "Moon"}:
        system.remove_body(name)

tracks: dict[str, list] = {b.name: [] for b in system.bodies}
for _ in range(STEPS):
    system.step(DT)
    for s in system.snapshot():
        tracks[s.name].append(s.pos.copy())

fig, ax = plt.subplots(figsize=(8, 8))
ax.set_facecolor("black")
ax.set_aspect("equal")
COLORS = {"Sun": "yellow", "Earth": "dodgerblue", "Moon": "lightgray"}
for name, pts in tracks.items():
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    ax.plot(xs, ys, color=COLORS[name], linewidth=1, label=name)
    ax.scatter([xs[-1]], [ys[-1]], color=COLORS[name], s=30, zorder=5)
ax.set_title("Milestone 1 — Sun / Earth / Moon (60 simulated days)", color="white")
ax.tick_params(colors="white")
for s in ax.spines.values():
    s.set_edgecolor("white")
ax.legend(facecolor="black", labelcolor="white")
fig.patch.set_facecolor("black")
plt.tight_layout()
plt.show()
```

- [ ] **Step 2: Run smoke test**

Run: `conda run -n nbodiesgravity python scripts/smoke_test_headless.py`

Expected: a matplotlib window opens. Earth traces a shallow arc around the Sun. The Moon traces a tight oscillating path along Earth's arc.

- [ ] **Step 3: Run full test suite**

Run: `conda run -n nbodiesgravity python -m pytest tests/ -v`

Expected: `20 passed` (4 + 4 + 7 + 5 tests)

- [ ] **Step 4: Commit**

```bash
git add scripts/smoke_test_headless.py
git commit -m "test: add headless matplotlib smoke test — Milestone 1 complete"
```

---

## Milestone 2 — Rendering Core

---

### Task 9: `engine/simulation_thread.py` — physics QThread

**Files:**
- Create: `nbodiesgravity/engine/simulation_thread.py`

Note: `SimulationThread` uses PyQt6 so it is not unit-tested headlessly. It is verified by running `main.py` in Task 14.

- [ ] **Step 1: Implement `nbodiesgravity/engine/simulation_thread.py`**

```python
"""QThread that drives the physics simulation loop.

Calls SolarSystem.step(dt) at ~120 steps/second and keeps
latest_snapshot up to date for the render thread to read.

Public interface
----------------
set_timescale(days_per_second)  — call from any thread
pause() / resume()              — call from UI thread
reset(system)                   — call while paused
stop_thread()                   — call before application exit
latest_snapshot                 — read from render thread (GIL-safe)
"""
from __future__ import annotations
import time
import threading

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

from nbodiesgravity.engine.body import BodyState
from nbodiesgravity.engine.system import SolarSystem

_STEPS_PER_SECOND: int = 120


class SimulationThread(QThread):
    snapshot_ready = pyqtSignal(list)   # list[BodyState]
    blow_up_detected = pyqtSignal()

    def __init__(self, system: SolarSystem, parent=None) -> None:
        super().__init__(parent)
        self._system = system
        self._timescale: float = 1.0   # simulated days per real second
        self._paused: bool = True
        self._running: bool = False
        self._lock = threading.Lock()
        self.latest_snapshot: list[BodyState] = system.snapshot()

    @property
    def is_playing(self) -> bool:
        return not self._paused

    @property
    def system(self) -> SolarSystem:
        return self._system

    def set_timescale(self, days_per_second: float) -> None:
        self._timescale = max(days_per_second, 1e-3)

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def reset(self, system: SolarSystem) -> None:
        """Replace the system. Must be called while paused."""
        with self._lock:
            self._system = system
            self.latest_snapshot = system.snapshot()

    def stop_thread(self) -> None:
        self._running = False
        self.wait()

    def run(self) -> None:
        self._running = True
        while self._running:
            if self._paused:
                time.sleep(0.001)
                continue
            dt = self._timescale / _STEPS_PER_SECOND
            with self._lock:
                self._system.step(dt)
                snap = self._system.snapshot()
            self.latest_snapshot = snap   # atomic reference swap (GIL)
            self.snapshot_ready.emit(snap)
            if any(float(np.linalg.norm(s.pos)) > 1000.0 for s in snap):
                self._paused = True
                self.blow_up_detected.emit()
```

- [ ] **Step 2: Verify import**

Run: `conda run -n nbodiesgravity python -c "from nbodiesgravity.engine.simulation_thread import SimulationThread; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add nbodiesgravity/engine/simulation_thread.py
git commit -m "feat: add SimulationThread QThread for physics loop"
```

---

### Task 10: `rendering/display_info.py` + `rendering/camera.py`

**Files:**
- Create: `nbodiesgravity/rendering/display_info.py`
- Create: `nbodiesgravity/rendering/camera.py`

- [ ] **Step 1: Implement `nbodiesgravity/rendering/display_info.py`**

```python
"""Rendering metadata for a celestial body.

Kept entirely separate from physics (engine/) — the rendering layer has
zero physics imports.  main.py bridges the two by converting CelestialBody
fields into BodyDisplayInfo when a system is loaded.
"""
from __future__ import annotations
import math
from dataclasses import dataclass


@dataclass
class BodyDisplayInfo:
    name: str
    radius_km: float
    color: tuple[float, float, float]   # RGB 0–1
    is_star: bool = False

    @property
    def display_radius(self) -> float:
        """Visible radius in AU.

        Applies a log scale so tiny moons and giant planets are both
        legible without dominating the view.
        Maps log10(radius_km) from [2, 6] → [0.01, 0.25] AU.
        """
        log_r = math.log10(max(self.radius_km, 1.0))
        t = max(0.0, min(1.0, (log_r - 2.0) / (6.0 - 2.0)))
        return 0.01 + t * (0.25 - 0.01)
```

- [ ] **Step 2: Implement `nbodiesgravity/rendering/camera.py`**

```python
"""3D camera that orbits a tracked body.

Physics always runs in SSB coordinates.  The renderer subtracts
center_pos from every body position before passing to OpenGL — the
physics engine is never modified by view changes.
"""
from __future__ import annotations
import numpy as np
from nbodiesgravity.engine.body import BodyState


class Camera:
    def __init__(self) -> None:
        self.center_pos: np.ndarray = np.zeros(3, dtype=np.float32)
        self.azimuth: float = 0.3       # radians
        self.elevation: float = 0.5     # radians
        self.distance: float = 6.0      # AU
        self._center_name: str = "Sun"

    @property
    def center_name(self) -> str:
        return self._center_name

    def set_center(self, name: str) -> None:
        self._center_name = name

    def update_center_pos(self, snapshot: list[BodyState]) -> None:
        for state in snapshot:
            if state.name == self._center_name:
                self.center_pos = state.pos.astype(np.float32)
                return

    def view_matrix(self) -> np.ndarray:
        """Return column-major 4×4 lookAt matrix (float32)."""
        eye = np.array([
            self.distance * np.cos(self.elevation) * np.sin(self.azimuth),
            self.distance * np.sin(self.elevation),
            self.distance * np.cos(self.elevation) * np.cos(self.azimuth),
        ], dtype=np.float32)
        return _look_at(eye, np.zeros(3, dtype=np.float32),
                        np.array([0.0, 1.0, 0.0], dtype=np.float32))

    def rotate(self, d_az: float, d_el: float) -> None:
        self.azimuth += d_az
        self.elevation = float(np.clip(
            self.elevation + d_el, -np.pi / 2 + 0.01, np.pi / 2 - 0.01
        ))

    def zoom(self, factor: float) -> None:
        self.distance = max(0.001, self.distance * factor)


def _look_at(
    eye: np.ndarray, target: np.ndarray, up: np.ndarray
) -> np.ndarray:
    f = target - eye
    f /= np.linalg.norm(f)
    r = np.cross(f, up)
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    m = np.eye(4, dtype=np.float32)
    m[0, :3] = r
    m[1, :3] = u
    m[2, :3] = -f
    m[0, 3] = float(-np.dot(r, eye))
    m[1, 3] = float(-np.dot(u, eye))
    m[2, 3] = float(np.dot(f, eye))
    return m
```

- [ ] **Step 3: Verify imports**

Run: `conda run -n nbodiesgravity python -c "from nbodiesgravity.rendering.camera import Camera; from nbodiesgravity.rendering.display_info import BodyDisplayInfo; c=Camera(); print(c.view_matrix().shape)"`

Expected: `(4, 4)`

- [ ] **Step 4: Commit**

```bash
git add nbodiesgravity/rendering/display_info.py nbodiesgravity/rendering/camera.py
git commit -m "feat: add Camera and BodyDisplayInfo for rendering layer"
```

---

### Task 11: `rendering/sphere_mesh.py` — UV sphere VBO + GLSL shaders

**Files:**
- Create: `nbodiesgravity/rendering/sphere_mesh.py`

- [ ] **Step 1: Implement `nbodiesgravity/rendering/sphere_mesh.py`**

```python
"""Shared UV-sphere mesh and GLSL shader sources.

One SphereMesh instance is shared by all bodies — each body sets its own
model matrix uniform (translate + scale) before calling draw().

SPHERE_VERT / SPHERE_FRAG : Phong-lit sphere. Sun uses uEmissive=true.
LINE_VERT / LINE_FRAG      : Unlit lines for trails.
"""
from __future__ import annotations
import ctypes
import numpy as np
from OpenGL.GL import (
    glGenVertexArrays, glGenBuffers, glBindVertexArray, glBindBuffer,
    glBufferData, glVertexAttribPointer, glEnableVertexAttribArray,
    glDrawElements,
    GL_ARRAY_BUFFER, GL_ELEMENT_ARRAY_BUFFER,
    GL_FLOAT, GL_FALSE, GL_TRIANGLES, GL_UNSIGNED_INT, GL_STATIC_DRAW,
)

# ---------------------------------------------------------------------------
# GLSL sources
# ---------------------------------------------------------------------------

SPHERE_VERT_SRC: str = """
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;
uniform mat4 uModel;
uniform mat4 uView;
uniform mat4 uProjection;
out vec3 FragPos;
out vec3 Normal;
void main() {
    vec4 worldPos = uModel * vec4(aPos, 1.0);
    FragPos = worldPos.xyz;
    Normal = mat3(transpose(inverse(uModel))) * aNormal;
    gl_Position = uProjection * uView * worldPos;
}
"""

SPHERE_FRAG_SRC: str = """
#version 330 core
in vec3 FragPos;
in vec3 Normal;
uniform vec3  uColor;
uniform vec3  uLightPos;
uniform bool  uEmissive;
out vec4 FragColor;
void main() {
    if (uEmissive) { FragColor = vec4(uColor, 1.0); return; }
    vec3 norm     = normalize(Normal);
    vec3 lightDir = normalize(uLightPos - FragPos);
    float diff    = max(dot(norm, lightDir), 0.15);
    FragColor     = vec4(diff * uColor, 1.0);
}
"""

LINE_VERT_SRC: str = """
#version 330 core
layout(location = 0) in vec3 aPos;
uniform mat4 uViewProjection;
uniform vec3 uCenterOffset;
void main() {
    gl_Position = uViewProjection * vec4(aPos - uCenterOffset, 1.0);
}
"""

LINE_FRAG_SRC: str = """
#version 330 core
uniform vec3  uColor;
uniform float uAlpha;
out vec4 FragColor;
void main() { FragColor = vec4(uColor, uAlpha); }
"""

# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

def _generate_uv_sphere(
    stacks: int = 24, slices: int = 24
) -> tuple[np.ndarray, np.ndarray]:
    """Return (vertices float32 (N,6), indices uint32) for a unit sphere."""
    verts: list[float] = []
    for i in range(stacks + 1):
        phi = np.pi * i / stacks
        for j in range(slices + 1):
            theta = 2.0 * np.pi * j / slices
            x = float(np.sin(phi) * np.cos(theta))
            y = float(np.cos(phi))
            z = float(np.sin(phi) * np.sin(theta))
            verts += [x, y, z, x, y, z]   # pos == normal for unit sphere
    idxs: list[int] = []
    for i in range(stacks):
        for j in range(slices):
            a = i * (slices + 1) + j
            b = a + slices + 1
            idxs += [a, b, a + 1, b, b + 1, a + 1]
    return np.array(verts, dtype=np.float32), np.array(idxs, dtype=np.uint32)


# ---------------------------------------------------------------------------
# SphereMesh
# ---------------------------------------------------------------------------

class SphereMesh:
    """Single VBO shared by every body. Scale via model-matrix uniform."""

    def __init__(self) -> None:
        self._vao: int | None = None
        self._index_count: int = 0

    def initialize(self) -> None:
        """Upload to GPU. Must be called from the GL thread after context creation."""
        vertices, indices = _generate_uv_sphere()
        self._index_count = len(indices)
        self._vao = glGenVertexArrays(1)
        vbo = glGenBuffers(1)
        ebo = glGenBuffers(1)
        glBindVertexArray(self._vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)
        stride = 6 * 4
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(12))
        glEnableVertexAttribArray(1)
        glBindVertexArray(0)

    def draw(self) -> None:
        glBindVertexArray(self._vao)
        glDrawElements(GL_TRIANGLES, self._index_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)
```

- [ ] **Step 2: Verify import**

Run: `conda run -n nbodiesgravity python -c "from nbodiesgravity.rendering.sphere_mesh import SphereMesh, SPHERE_VERT_SRC; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add nbodiesgravity/rendering/sphere_mesh.py
git commit -m "feat: add SphereMesh VBO and GLSL shader sources"
```

---

### Task 12: `rendering/trail_buffer.py` — per-body ring-buffer trail

**Files:**
- Create: `nbodiesgravity/rendering/trail_buffer.py`

- [ ] **Step 1: Implement `nbodiesgravity/rendering/trail_buffer.py`**

```python
"""Per-body trail rendered as an OpenGL GL_LINE_STRIP.

Ring buffer of the last MAX_TRAIL_POINTS positions.  History accumulates
even when show_trail is False — toggling trails back on shows the full
history immediately without waiting for re-fill.
"""
from __future__ import annotations
import ctypes
import numpy as np
from OpenGL.GL import (
    glGenVertexArrays, glGenBuffers, glBindVertexArray, glBindBuffer,
    glBufferData, glBufferSubData, glVertexAttribPointer,
    glEnableVertexAttribArray, glDrawArrays,
    GL_ARRAY_BUFFER, GL_FLOAT, GL_FALSE, GL_DYNAMIC_DRAW, GL_LINE_STRIP,
)

MAX_TRAIL_POINTS: int = 2000


class TrailBuffer:
    def __init__(self, color: tuple[float, float, float]) -> None:
        self.color = color
        self._buf = np.zeros((MAX_TRAIL_POINTS, 3), dtype=np.float32)
        self._head: int = 0    # next write index
        self._count: int = 0   # valid points so far
        self._dirty: bool = False
        self._vao: int | None = None
        self._vbo: int | None = None

    def initialize(self) -> None:
        """Allocate GPU buffer. Must be called from the GL thread."""
        self._vao = glGenVertexArrays(1)
        self._vbo = glGenBuffers(1)
        glBindVertexArray(self._vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
        glBufferData(
            GL_ARRAY_BUFFER,
            MAX_TRAIL_POINTS * 3 * 4,
            None,
            GL_DYNAMIC_DRAW,
        )
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 12, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glBindVertexArray(0)

    def append(self, pos: np.ndarray) -> None:
        """Add a position to the ring buffer. Render-thread only."""
        self._buf[self._head] = pos.astype(np.float32)
        self._head = (self._head + 1) % MAX_TRAIL_POINTS
        if self._count < MAX_TRAIL_POINTS:
            self._count += 1
        self._dirty = True

    def draw(self) -> None:
        """Upload if dirty and draw. GL thread only."""
        if self._count < 2:
            return
        if self._dirty:
            if self._count < MAX_TRAIL_POINTS:
                ordered = self._buf[: self._count]
            else:
                ordered = np.roll(self._buf, -self._head, axis=0)
            glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
            glBufferSubData(GL_ARRAY_BUFFER, 0, ordered.nbytes, ordered)
            self._dirty = False
        glBindVertexArray(self._vao)
        glDrawArrays(GL_LINE_STRIP, 0, self._count)
        glBindVertexArray(0)
```

- [ ] **Step 2: Verify import**

Run: `conda run -n nbodiesgravity python -c "from nbodiesgravity.rendering.trail_buffer import TrailBuffer; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add nbodiesgravity/rendering/trail_buffer.py
git commit -m "feat: add TrailBuffer ring-buffer trail for OpenGL line strip"
```

---

### Task 13: `rendering/gl_widget.py` — QOpenGLWidget

**Files:**
- Create: `nbodiesgravity/rendering/gl_widget.py`

- [ ] **Step 1: Implement `nbodiesgravity/rendering/gl_widget.py`**

```python
"""Main 3D OpenGL viewport.

Renders Phong-lit spheres and coloured trails at 60 FPS.
Reads positions from SimulationThread.latest_snapshot each frame.
Mouse: left-drag = orbit, right-drag = distance adjust, scroll = zoom.
"""
from __future__ import annotations
import ctypes
import numpy as np

from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QMouseEvent, QWheelEvent

from OpenGL.GL import (
    glEnable, glClear, glClearColor, glViewport, glBlendFunc,
    glUseProgram, glUniform1i, glUniform1f, glUniform3f,
    glGetUniformLocation, glUniformMatrix4fv,
    glCreateShader, glShaderSource, glCompileShader,
    glGetShaderiv, glGetShaderInfoLog,
    glCreateProgram, glAttachShader, glLinkProgram,
    glGetProgramiv, glGetProgramInfoLog,
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT,
    GL_DEPTH_TEST, GL_BLEND, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA,
    GL_VERTEX_SHADER, GL_FRAGMENT_SHADER,
    GL_COMPILE_STATUS, GL_LINK_STATUS, GL_TRUE, GL_FALSE,
)

from nbodiesgravity.rendering.camera import Camera
from nbodiesgravity.rendering.display_info import BodyDisplayInfo
from nbodiesgravity.rendering.sphere_mesh import (
    SphereMesh, SPHERE_VERT_SRC, SPHERE_FRAG_SRC, LINE_VERT_SRC, LINE_FRAG_SRC,
)
from nbodiesgravity.rendering.trail_buffer import TrailBuffer


def _compile_shader(src: str, kind: int) -> int:
    s = glCreateShader(kind)
    glShaderSource(s, src)
    glCompileShader(s)
    if glGetShaderiv(s, GL_COMPILE_STATUS) != GL_TRUE:
        raise RuntimeError(f"Shader error:\n{glGetShaderInfoLog(s).decode()}")
    return s


def _link_program(vert_src: str, frag_src: str) -> int:
    p = glCreateProgram()
    glAttachShader(p, _compile_shader(vert_src, GL_VERTEX_SHADER))
    glAttachShader(p, _compile_shader(frag_src, GL_FRAGMENT_SHADER))
    glLinkProgram(p)
    if glGetProgramiv(p, GL_LINK_STATUS) != GL_TRUE:
        raise RuntimeError(f"Link error:\n{glGetProgramInfoLog(p).decode()}")
    return p


def _perspective(fov_deg: float, aspect: float, near: float, far: float) -> np.ndarray:
    f = 1.0 / np.tan(np.radians(fov_deg) / 2.0)
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = 2.0 * far * near / (near - far)
    m[3, 2] = -1.0
    return m


def _model_matrix(offset: np.ndarray, scale: float) -> np.ndarray:
    m = np.eye(4, dtype=np.float32)
    m[0, 0] = m[1, 1] = m[2, 2] = scale
    m[:3, 3] = offset
    return m


class GLWidget(QOpenGLWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.camera = Camera()
        self._sphere_mesh = SphereMesh()
        self._trail_buffers: dict[str, TrailBuffer] = {}
        self._display_info: dict[str, BodyDisplayInfo] = {}
        self._sphere_prog: int = 0
        self._line_prog: int = 0
        self._proj = np.eye(4, dtype=np.float32)
        self._simulation_thread = None
        self._last_mouse_pos = None
        self._last_mouse_btn = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(16)   # ~60 FPS

    def set_simulation_thread(self, thread) -> None:
        self._simulation_thread = thread

    def set_display_info(self, infos: list[BodyDisplayInfo]) -> None:
        """Register rendering metadata. Call after every system load/reset."""
        self._display_info = {info.name: info for info in infos}
        for info in infos:
            if info.name not in self._trail_buffers:
                tb = TrailBuffer(info.color)
                if self._sphere_prog:   # GL context already exists
                    tb.initialize()
                self._trail_buffers[info.name] = tb

    # ---------------------------------------------------------------
    # QOpenGLWidget callbacks
    # ---------------------------------------------------------------

    def initializeGL(self) -> None:
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glClearColor(0.0, 0.0, 0.0, 1.0)
        self._sphere_prog = _link_program(SPHERE_VERT_SRC, SPHERE_FRAG_SRC)
        self._line_prog = _link_program(LINE_VERT_SRC, LINE_FRAG_SRC)
        self._sphere_mesh.initialize()
        for tb in self._trail_buffers.values():
            tb.initialize()

    def resizeGL(self, w: int, h: int) -> None:
        glViewport(0, 0, w, h)
        self._proj = _perspective(45.0, w / max(h, 1), 0.0001, 100000.0)

    def paintGL(self) -> None:
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        if self._simulation_thread is None:
            return
        snap = self._simulation_thread.latest_snapshot
        if not snap:
            return

        self.camera.update_center_pos(snap)
        offset = self.camera.center_pos
        view = self.camera.view_matrix()
        vp = (self._proj @ view).astype(np.float32)

        # Lazy-init trail buffers for bodies added after GL init
        for state in snap:
            if state.name not in self._trail_buffers:
                info = self._display_info.get(state.name)
                color = info.color if info else (1.0, 1.0, 1.0)
                tb = TrailBuffer(color)
                tb.initialize()
                self._trail_buffers[state.name] = tb

        # Accumulate trail positions
        for state in snap:
            self._trail_buffers[state.name].append(state.pos)

        # --- Trails ---
        glUseProgram(self._line_prog)
        glUniformMatrix4fv(
            glGetUniformLocation(self._line_prog, "uViewProjection"),
            1, GL_FALSE, vp.T,
        )
        glUniform3f(glGetUniformLocation(self._line_prog, "uCenterOffset"), *offset)
        glUniform1f(glGetUniformLocation(self._line_prog, "uAlpha"), 0.55)
        for state in snap:
            body = (self._simulation_thread.system.get_body(state.name)
                    if self._simulation_thread else None)
            if body and not body.show_trail:
                continue
            tb = self._trail_buffers[state.name]
            glUniform3f(glGetUniformLocation(self._line_prog, "uColor"), *tb.color)
            tb.draw()

        # --- Spheres ---
        glUseProgram(self._sphere_prog)
        glUniformMatrix4fv(
            glGetUniformLocation(self._sphere_prog, "uView"), 1, GL_FALSE, view.T)
        glUniformMatrix4fv(
            glGetUniformLocation(self._sphere_prog, "uProjection"), 1, GL_FALSE, self._proj.T)
        sun = next((s for s in snap if s.name == "Sun"), snap[0])
        glUniform3f(
            glGetUniformLocation(self._sphere_prog, "uLightPos"),
            *(sun.pos - offset).astype(np.float32),
        )
        for state in snap:
            info = self._display_info.get(state.name)
            r = info.display_radius if info else 0.02
            pos_rel = (state.pos - offset).astype(np.float32)
            model = _model_matrix(pos_rel, r)
            glUniformMatrix4fv(
                glGetUniformLocation(self._sphere_prog, "uModel"), 1, GL_FALSE, model.T)
            color = info.color if info else (1.0, 1.0, 1.0)
            glUniform3f(glGetUniformLocation(self._sphere_prog, "uColor"), *color)
            glUniform1i(
                glGetUniformLocation(self._sphere_prog, "uEmissive"),
                int(info.is_star if info else False),
            )
            self._sphere_mesh.draw()

    # ---------------------------------------------------------------
    # Mouse events
    # ---------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._last_mouse_pos = event.position()
        self._last_mouse_btn = event.button()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._last_mouse_pos is None:
            return
        dx = event.position().x() - self._last_mouse_pos.x()
        dy = event.position().y() - self._last_mouse_pos.y()
        if self._last_mouse_btn == Qt.MouseButton.LeftButton:
            self.camera.rotate(dx * 0.005, -dy * 0.005)
        elif self._last_mouse_btn == Qt.MouseButton.RightButton:
            self.camera.distance = max(
                0.001, self.camera.distance + dy * self.camera.distance * 0.005
            )
        self._last_mouse_pos = event.position()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._last_mouse_pos = None
        self._last_mouse_btn = None

    def wheelEvent(self, event: QWheelEvent) -> None:
        self.camera.zoom(0.9 if event.angleDelta().y() > 0 else 1.1)
```

- [ ] **Step 2: Verify import**

Run: `conda run -n nbodiesgravity python -c "from nbodiesgravity.rendering.gl_widget import GLWidget; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add nbodiesgravity/rendering/gl_widget.py
git commit -m "feat: add GLWidget with Phong sphere and trail rendering at 60 FPS"
```

---

### Task 14: Minimal `main.py` — Milestone 2 smoke test

**Files:**
- Create: `nbodiesgravity/main.py`

- [ ] **Step 1: Create minimal `nbodiesgravity/main.py`**

```python
"""N-Body Gravity entry point (Milestone 2 — rendering smoke test).

Run:
    conda run -n nbodiesgravity python nbodiesgravity/main.py
"""
from __future__ import annotations
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QSurfaceFormat
from nbodiesgravity.data.loader import load_default_system
from nbodiesgravity.engine.simulation_thread import SimulationThread
from nbodiesgravity.rendering.display_info import BodyDisplayInfo
from nbodiesgravity.rendering.gl_widget import GLWidget


def _request_opengl_33() -> None:
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setDepthBufferSize(24)
    QSurfaceFormat.setDefaultFormat(fmt)


def main() -> None:
    _request_opengl_33()
    app = QApplication(sys.argv)
    system = load_default_system()
    display_infos = [
        BodyDisplayInfo(b.name, b.radius, b.color, is_star=(b.name == "Sun"))
        for b in system.bodies
    ]
    sim = SimulationThread(system)
    gl = GLWidget()
    gl.set_display_info(display_infos)
    gl.set_simulation_thread(sim)
    gl.resize(1200, 900)
    gl.setWindowTitle("N-Body Gravity — Milestone 2 Rendering")
    gl.show()
    sim.start()
    sim.set_timescale(10.0)
    sim.resume()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run Milestone 2 smoke test**

Run: `conda run -n nbodiesgravity python nbodiesgravity/main.py`

Expected:
- Black 3D window opens showing coloured spheres for the Sun and planets
- Left-drag rotates the view; scroll zooms in/out
- Trails appear within a few seconds as bodies begin moving
- No Python errors or OpenGL shader compile errors in the terminal

- [ ] **Step 3: Commit**

```bash
git add nbodiesgravity/main.py
git commit -m "feat: add minimal main.py for Milestone 2 rendering smoke test"
```

---

## Milestone 3 — Time & UI Controls

---

### Task 15: `ui/control_panel.py`

**Files:**
- Create: `nbodiesgravity/ui/control_panel.py`

- [ ] **Step 1: Implement `nbodiesgravity/ui/control_panel.py`**

```python
"""Bottom control bar: epoch date picker, speed presets, center picker, play/pause."""
from __future__ import annotations
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QDateEdit, QComboBox,
    QPushButton, QLineEdit, QSizePolicy,
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QDoubleValidator


class ControlPanel(QWidget):
    date_changed = pyqtSignal(datetime)       # user committed a new epoch date
    timescale_changed = pyqtSignal(float)     # simulated days per real second
    center_changed = pyqtSignal(str)          # new center body name
    play_toggled = pyqtSignal(bool)           # True = playing

    _PRESETS: list[tuple[str, float]] = [
        ("1 s = 1 day",   1.0),
        ("1 s = 1 month", 30.0),
        ("1 s = 1 year",  365.25),
        ("Custom",        0.0),
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._playing = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)

        layout.addWidget(QLabel("Epoch:"))
        self._date_edit = QDateEdit(QDate(2000, 1, 1))
        self._date_edit.setDisplayFormat("yyyy-MM-dd")
        self._date_edit.setCalendarPopup(True)
        self._date_edit.editingFinished.connect(self._on_date_committed)
        layout.addWidget(self._date_edit)

        layout.addSpacing(12)

        self._play_btn = QPushButton("▶  Play")
        self._play_btn.setFixedWidth(90)
        self._play_btn.clicked.connect(self._on_play_clicked)
        layout.addWidget(self._play_btn)

        layout.addSpacing(12)

        layout.addWidget(QLabel("Speed:"))
        self._preset_combo = QComboBox()
        for label, _ in self._PRESETS:
            self._preset_combo.addItem(label)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        layout.addWidget(self._preset_combo)

        self._custom_edit = QLineEdit("1.0")
        self._custom_edit.setFixedWidth(70)
        self._custom_edit.setPlaceholderText("days/s")
        self._custom_edit.setValidator(QDoubleValidator(0.001, 1e6, 3))
        self._custom_edit.setVisible(False)
        self._custom_edit.returnPressed.connect(self._on_custom_timescale)
        layout.addWidget(self._custom_edit)

        layout.addSpacing(12)

        layout.addWidget(QLabel("Center:"))
        self._center_combo = QComboBox()
        self._center_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._center_combo.currentTextChanged.connect(self.center_changed)
        layout.addWidget(self._center_combo)

    # Public API
    def set_body_names(self, names: list[str]) -> None:
        self._center_combo.blockSignals(True)
        current = self._center_combo.currentText()
        self._center_combo.clear()
        for name in names:
            self._center_combo.addItem(name)
        idx = self._center_combo.findText(current)
        self._center_combo.setCurrentIndex(max(0, idx))
        self._center_combo.blockSignals(False)

    def set_playing(self, playing: bool) -> None:
        self._playing = playing
        self._play_btn.setText("⏸  Pause" if playing else "▶  Play")

    # Private slots
    def _on_date_committed(self) -> None:
        qd = self._date_edit.date()
        self.date_changed.emit(datetime(qd.year(), qd.month(), qd.day()))

    def _on_play_clicked(self) -> None:
        self._playing = not self._playing
        self.set_playing(self._playing)
        self.play_toggled.emit(self._playing)

    def _on_preset_changed(self, idx: int) -> None:
        label, value = self._PRESETS[idx]
        is_custom = label == "Custom"
        self._custom_edit.setVisible(is_custom)
        if not is_custom:
            self.timescale_changed.emit(value)

    def _on_custom_timescale(self) -> None:
        try:
            v = float(self._custom_edit.text())
            if v > 0:
                self.timescale_changed.emit(v)
        except ValueError:
            pass
```

- [ ] **Step 2: Verify import**

Run: `conda run -n nbodiesgravity python -c "from nbodiesgravity.ui.control_panel import ControlPanel; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add nbodiesgravity/ui/control_panel.py
git commit -m "feat: add ControlPanel with date picker, speed presets, center picker"
```

---

### Task 16: `ui/date_loader_worker.py`

**Files:**
- Create: `nbodiesgravity/ui/date_loader_worker.py`

- [ ] **Step 1: Implement `nbodiesgravity/ui/date_loader_worker.py`**

```python
"""Background QThread worker that fetches state vectors for a new epoch date.

Keeps the UI responsive during JPL Horizons queries (up to 20 HTTP requests).

Signals
-------
body_loaded(name) : emitted after each body is resolved (for progress bar)
finished(system)  : emitted on success with the assembled SolarSystem
error(message)    : emitted on HorizonsError or unexpected exception
"""
from __future__ import annotations
from datetime import datetime

from PyQt6.QtCore import QThread, pyqtSignal

from nbodiesgravity.data.horizons import HorizonsError
from nbodiesgravity.data.loader import load_system_at_date
from nbodiesgravity.engine.system import SolarSystem


class DateLoaderWorker(QThread):
    body_loaded = pyqtSignal(str)
    finished = pyqtSignal(object)   # SolarSystem — object avoids Qt metatype issues
    error = pyqtSignal(str)

    def __init__(self, epoch: datetime, parent=None) -> None:
        super().__init__(parent)
        self.epoch = epoch

    def run(self) -> None:
        try:
            system = load_system_at_date(
                epoch=self.epoch,
                progress_cb=self.body_loaded.emit,
            )
            self.finished.emit(system)
        except HorizonsError as exc:
            self.error.emit(str(exc))
        except Exception as exc:
            self.error.emit(f"Unexpected error: {exc}")
```

- [ ] **Step 2: Verify import**

Run: `conda run -n nbodiesgravity python -c "from nbodiesgravity.ui.date_loader_worker import DateLoaderWorker; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add nbodiesgravity/ui/date_loader_worker.py
git commit -m "feat: add DateLoaderWorker QThread for background JPL date fetching"
```

---

### Task 17: `ui/body_list_panel.py`

**Files:**
- Create: `nbodiesgravity/ui/body_list_panel.py`

- [ ] **Step 1: Implement `nbodiesgravity/ui/body_list_panel.py`**

```python
"""Side panel: scrollable body list with colour dot and trail toggle per row."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QHBoxLayout, QCheckBox, QLabel,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap

from nbodiesgravity.engine.body import CelestialBody


class BodyListPanel(QWidget):
    body_selected = pyqtSignal(str)         # single-click
    body_edit_requested = pyqtSignal(str)   # double-click
    trail_toggled = pyqtSignal(str, bool)   # (name, enabled)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(QLabel("Bodies"))
        self._list = QListWidget()
        self._list.itemClicked.connect(
            lambda item: self.body_selected.emit(item.data(Qt.ItemDataRole.UserRole))
        )
        self._list.itemDoubleClicked.connect(
            lambda item: self.body_edit_requested.emit(item.data(Qt.ItemDataRole.UserRole))
        )
        layout.addWidget(self._list)

    def populate(self, bodies: list[CelestialBody]) -> None:
        self._list.clear()
        for body in bodies:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, body.name)
            widget = self._row_widget(body)
            self._list.addItem(item)
            item.setSizeHint(widget.sizeHint())
            self._list.setItemWidget(item, widget)

    def selected_name(self) -> str | None:
        item = self._list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _row_widget(self, body: CelestialBody) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 2, 4, 2)
        # Colour dot
        px = QPixmap(14, 14)
        r, g, b = (int(c * 255) for c in body.color)
        px.fill(QColor(r, g, b))
        dot = QLabel()
        dot.setPixmap(px)
        layout.addWidget(dot)
        # Name
        layout.addWidget(QLabel(body.name), stretch=1)
        # Trail checkbox
        cb = QCheckBox("Trail")
        cb.setChecked(body.show_trail)
        name = body.name
        cb.stateChanged.connect(
            lambda state, n=name: self.trail_toggled.emit(
                n, state == Qt.CheckState.Checked.value
            )
        )
        layout.addWidget(cb)
        return row
```

- [ ] **Step 2: Verify import**

Run: `conda run -n nbodiesgravity python -c "from nbodiesgravity.ui.body_list_panel import BodyListPanel; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add nbodiesgravity/ui/body_list_panel.py
git commit -m "feat: add BodyListPanel with colour dots and trail toggles"
```

---

## Milestone 4 — Body Editor & Full Assembly

---

### Task 18: `ui/body_editor_dialog.py`

**Files:**
- Create: `nbodiesgravity/ui/body_editor_dialog.py`

- [ ] **Step 1: Implement `nbodiesgravity/ui/body_editor_dialog.py`**

```python
"""QDialog for adding or editing a CelestialBody.

Validation (OK button disabled until all pass):
  - name not empty; not duplicate (in Add mode)
  - mass > 0
  - radius > 0
"""
from __future__ import annotations
import numpy as np
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QDialogButtonBox, QLineEdit,
    QDoubleSpinBox, QPushButton, QLabel, QColorDialog,
    QHBoxLayout, QWidget,
)
from PyQt6.QtGui import QColor
from nbodiesgravity.engine.body import CelestialBody


class BodyEditorDialog(QDialog):
    def __init__(
        self,
        existing_names: list[str],
        body: CelestialBody | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._existing_names = existing_names
        self._edit_mode = body is not None
        self._color: tuple[float, float, float] = body.color if body else (1.0, 1.0, 1.0)
        self.setWindowTitle("Edit Body" if self._edit_mode else "Add Body")
        self.setModal(True)
        self._build_ui(body)
        self._validate()

    def result_body(self) -> CelestialBody:
        """Call after exec() returns Accepted to retrieve the configured body."""
        return CelestialBody(
            name=self._name_edit.text().strip(),
            mass=self._mass_spin.value(),
            pos=np.array([self._px.value(), self._py.value(), self._pz.value()]),
            vel=np.array([self._vx.value(), self._vy.value(), self._vz.value()]),
            radius=self._radius_spin.value(),
            color=self._color,
        )

    def _build_ui(self, body: CelestialBody | None) -> None:
        form = QFormLayout(self)

        self._name_edit = QLineEdit(body.name if body else "")
        self._name_edit.textChanged.connect(self._validate)
        form.addRow("Name:", self._name_edit)

        self._mass_spin = _sci_spin(1e-3, 2e30, body.mass if body else 1e22)
        self._mass_spin.valueChanged.connect(self._validate)
        form.addRow("Mass (kg):", self._mass_spin)

        self._radius_spin = _sci_spin(0.1, 1e7, body.radius if body else 1000.0)
        self._radius_spin.valueChanged.connect(self._validate)
        form.addRow("Radius (km):", self._radius_spin)

        cw = QWidget()
        cl = QHBoxLayout(cw)
        cl.setContentsMargins(0, 0, 0, 0)
        self._color_btn = QPushButton()
        self._color_btn.clicked.connect(self._pick_color)
        cl.addWidget(self._color_btn)
        cl.addStretch()
        self._update_color_btn()
        form.addRow("Color:", cw)

        pos = body.pos if body else np.zeros(3)
        self._px = _au_spin(pos[0])
        self._py = _au_spin(pos[1])
        self._pz = _au_spin(pos[2])
        form.addRow("Position X (AU):", self._px)
        form.addRow("Position Y (AU):", self._py)
        form.addRow("Position Z (AU):", self._pz)

        vel = body.vel if body else np.zeros(3)
        self._vx = _au_spin(vel[0])
        self._vy = _au_spin(vel[1])
        self._vz = _au_spin(vel[2])
        form.addRow("Velocity VX (AU/day):", self._vx)
        form.addRow("Velocity VY (AU/day):", self._vy)
        form.addRow("Velocity VZ (AU/day):", self._vz)

        self._err = QLabel("")
        self._err.setStyleSheet("color: red;")
        form.addRow(self._err)

        self._btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._btns.accepted.connect(self.accept)
        self._btns.rejected.connect(self.reject)
        form.addRow(self._btns)

    def _update_color_btn(self) -> None:
        r, g, b = (int(c * 255) for c in self._color)
        self._color_btn.setStyleSheet(
            f"background-color: rgb({r},{g},{b}); min-width:60px; min-height:20px;"
        )

    def _pick_color(self) -> None:
        r, g, b = (int(c * 255) for c in self._color)
        qc = QColorDialog.getColor(QColor(r, g, b), self, "Pick Body Color")
        if qc.isValid():
            self._color = (qc.redF(), qc.greenF(), qc.blueF())
            self._update_color_btn()

    def _validate(self) -> None:
        name = self._name_edit.text().strip()
        err = ""
        if not name:
            err = "Name is required."
        elif not self._edit_mode and name in self._existing_names:
            err = f"'{name}' already exists."
        elif self._mass_spin.value() <= 0:
            err = "Mass must be > 0."
        elif self._radius_spin.value() <= 0:
            err = "Radius must be > 0."
        self._err.setText(err)
        self._btns.button(QDialogButtonBox.StandardButton.Ok).setEnabled(err == "")


def _sci_spin(min_v: float, max_v: float, value: float) -> QDoubleSpinBox:
    sb = QDoubleSpinBox()
    sb.setDecimals(3)
    sb.setMinimum(min_v)
    sb.setMaximum(max_v)
    sb.setValue(value)
    sb.setStepType(QDoubleSpinBox.StepType.AdaptiveDecimalStepType)
    return sb


def _au_spin(value: float) -> QDoubleSpinBox:
    sb = QDoubleSpinBox()
    sb.setDecimals(8)
    sb.setMinimum(-10000.0)
    sb.setMaximum(10000.0)
    sb.setValue(value)
    return sb
```

- [ ] **Step 2: Verify import**

Run: `conda run -n nbodiesgravity python -c "from nbodiesgravity.ui.body_editor_dialog import BodyEditorDialog; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add nbodiesgravity/ui/body_editor_dialog.py
git commit -m "feat: add BodyEditorDialog with inline validation"
```

---

### Task 19: `ui/main_window.py` — full assembly

**Files:**
- Create: `nbodiesgravity/ui/main_window.py`

- [ ] **Step 1: Implement `nbodiesgravity/ui/main_window.py`**

```python
"""QMainWindow assembling all panels and wiring all signals/slots."""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

import numpy as np
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QVBoxLayout,
    QProgressDialog, QFileDialog, QMessageBox, QStatusBar,
)
from PyQt6.QtCore import Qt

from nbodiesgravity.data.loader import load_default_system
from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.system import SolarSystem
from nbodiesgravity.engine.simulation_thread import SimulationThread
from nbodiesgravity.rendering.display_info import BodyDisplayInfo
from nbodiesgravity.rendering.gl_widget import GLWidget
from nbodiesgravity.ui.body_editor_dialog import BodyEditorDialog
from nbodiesgravity.ui.body_list_panel import BodyListPanel
from nbodiesgravity.ui.control_panel import ControlPanel
from nbodiesgravity.ui.date_loader_worker import DateLoaderWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("N-Body Gravity Simulation")
        self.resize(1400, 900)
        self._sim: SimulationThread | None = None
        self._loader: DateLoaderWorker | None = None
        self._progress: QProgressDialog | None = None
        self._last_epoch = datetime(2000, 1, 1)
        self._build_ui()
        self._load_system(load_default_system())

    # ----------------------------------------------------------------
    # UI construction
    # ----------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._body_list = BodyListPanel()
        self._body_list.setFixedWidth(220)
        self._gl = GLWidget()
        splitter.addWidget(self._body_list)
        splitter.addWidget(self._gl)
        splitter.setStretchFactor(1, 1)
        outer.addWidget(splitter, stretch=1)

        self._ctrl = ControlPanel()
        outer.addWidget(self._ctrl)
        self.setStatusBar(QStatusBar())

        self._build_menus()

        # Wire signals
        self._ctrl.date_changed.connect(self._on_date_changed)
        self._ctrl.timescale_changed.connect(
            lambda v: self._sim and self._sim.set_timescale(v)
        )
        self._ctrl.center_changed.connect(self._gl.camera.set_center)
        self._ctrl.play_toggled.connect(self._on_play_toggled)
        self._body_list.body_selected.connect(self._gl.camera.set_center)
        self._body_list.body_edit_requested.connect(self._edit_body)
        self._body_list.trail_toggled.connect(self._on_trail_toggled)

    def _build_menus(self) -> None:
        mb = self.menuBar()
        fm = mb.addMenu("&File")
        fm.addAction("New System",       self._new_system)
        fm.addAction("Load System…",     self._load_from_file)
        fm.addAction("Save System…",     self._save_to_file)
        fm.addSeparator()
        fm.addAction("E&xit",            self.close)

        sm = mb.addMenu("&Simulation")
        sm.addAction("Add Body…",        self._add_body)
        sm.addAction("Edit Selected…",   lambda: self._edit_body(self._body_list.selected_name()))
        sm.addAction("Remove Selected",  self._remove_selected)

        vm = mb.addMenu("&View")
        vm.addAction("Reset Camera",     self._reset_camera)
        vm.addAction("Toggle All Trails",self._toggle_all_trails)

    # ----------------------------------------------------------------
    # System management
    # ----------------------------------------------------------------

    def _load_system(self, system: SolarSystem) -> None:
        if self._sim is not None:
            self._sim.pause()
            self._sim.stop_thread()
        self._sim = SimulationThread(system)
        self._sim.blow_up_detected.connect(self._on_blow_up)
        display_infos = [
            BodyDisplayInfo(b.name, b.radius, b.color, is_star=(b.name == "Sun"))
            for b in system.bodies
        ]
        self._gl.set_display_info(display_infos)
        self._gl.set_simulation_thread(self._sim)
        self._ctrl.set_body_names([b.name for b in system.bodies])
        self._ctrl.set_playing(False)
        self._body_list.populate(system.bodies)
        self._sim.start()
        self.statusBar().showMessage(f"Loaded {len(system.bodies)} bodies.")

    # ----------------------------------------------------------------
    # Control panel slots
    # ----------------------------------------------------------------

    def _on_play_toggled(self, playing: bool) -> None:
        if self._sim:
            self._sim.resume() if playing else self._sim.pause()

    def _on_date_changed(self, dt: datetime) -> None:
        if self._sim:
            self._sim.pause()
            self._ctrl.set_playing(False)
        self._last_epoch = dt
        self._progress = QProgressDialog(
            "Fetching from JPL Horizons…", "Cancel", 0, 20, self
        )
        self._progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress.setMinimumDuration(0)   # show immediately, don't wait 4s
        self._progress.setValue(0)
        self._progress.show()
        self._loader = DateLoaderWorker(dt)
        self._loader.body_loaded.connect(self._on_body_loaded)
        self._loader.finished.connect(self._on_load_finished)
        self._loader.error.connect(self._on_load_error)
        self._loader.start()

    def _on_body_loaded(self, name: str) -> None:
        if self._progress:
            self._progress.setValue(self._progress.value() + 1)
            self._progress.setLabelText(f"Loaded {name}…")

    def _on_load_finished(self, system: SolarSystem) -> None:
        if self._progress:
            self._progress.close()
        self._load_system(system)

    def _on_load_error(self, msg: str) -> None:
        if self._progress:
            self._progress.close()
        QMessageBox.warning(
            self, "JPL Horizons Error",
            f"Could not fetch state vectors:\n{msg}\n\nReverted to last valid epoch.",
        )
        self.statusBar().showMessage("JPL error — reverted.")

    # ----------------------------------------------------------------
    # Body editor slots
    # ----------------------------------------------------------------

    def _add_body(self) -> None:
        if self._sim is None:
            return
        was_playing = self._sim.is_playing
        self._sim.pause()
        existing = [b.name for b in self._sim.system.bodies]
        dlg = BodyEditorDialog(existing_names=existing, parent=self)
        if dlg.exec() == BodyEditorDialog.DialogCode.Accepted:
            body = dlg.result_body()
            self._sim.system.add_body(body)
            self._refresh_after_body_change()
        if was_playing:
            self._sim.resume()

    def _edit_body(self, name: str | None) -> None:
        if not name or self._sim is None:
            return
        was_playing = self._sim.is_playing
        self._sim.pause()
        body = self._sim.system.get_body(name)
        if body is None:
            return
        existing = [b.name for b in self._sim.system.bodies if b.name != name]
        dlg = BodyEditorDialog(existing_names=existing, body=body, parent=self)
        if dlg.exec() == BodyEditorDialog.DialogCode.Accepted:
            updated = dlg.result_body()
            body.name = updated.name
            body.mass = updated.mass
            body.pos = updated.pos
            body.vel = updated.vel
            body.radius = updated.radius
            body.color = updated.color
            self._refresh_after_body_change()
        if was_playing:
            self._sim.resume()

    def _remove_selected(self) -> None:
        name = self._body_list.selected_name()
        if not name or self._sim is None:
            return
        if QMessageBox.question(
            self, "Remove Body", f"Remove '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        was_playing = self._sim.is_playing
        self._sim.pause()
        self._sim.system.remove_body(name)
        self._refresh_after_body_change()
        if was_playing:
            self._sim.resume()

    def _on_trail_toggled(self, name: str, enabled: bool) -> None:
        if self._sim:
            body = self._sim.system.get_body(name)
            if body:
                body.show_trail = enabled

    def _refresh_after_body_change(self) -> None:
        if self._sim is None:
            return
        bodies = self._sim.system.bodies
        self._body_list.populate(bodies)
        self._ctrl.set_body_names([b.name for b in bodies])
        display_infos = [
            BodyDisplayInfo(b.name, b.radius, b.color, is_star=(b.name == "Sun"))
            for b in bodies
        ]
        self._gl.set_display_info(display_infos)

    # ----------------------------------------------------------------
    # View menu
    # ----------------------------------------------------------------

    def _reset_camera(self) -> None:
        cam = self._gl.camera
        cam.azimuth, cam.elevation, cam.distance = 0.3, 0.5, 6.0

    def _toggle_all_trails(self) -> None:
        if self._sim is None:
            return
        bodies = self._sim.system.bodies
        new_state = not all(b.show_trail for b in bodies)
        for b in bodies:
            b.show_trail = new_state
        self._body_list.populate(bodies)

    # ----------------------------------------------------------------
    # File menu
    # ----------------------------------------------------------------

    def _new_system(self) -> None:
        self._load_system(load_default_system())

    def _save_to_file(self) -> None:
        if self._sim is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save System", "", "JSON (*.json)")
        if not path:
            return
        was_playing = self._sim.is_playing
        self._sim.pause()
        bodies = self._sim.system.bodies
        data = {
            "bodies": [
                {
                    "name": b.name, "mass_kg": b.mass, "radius_km": b.radius,
                    "color": list(b.color),
                    "pos_au": b.pos.tolist(),
                    "vel_au_per_day": b.vel.tolist(),
                }
                for b in bodies
            ]
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self.statusBar().showMessage(f"Saved {len(bodies)} bodies to {Path(path).name}")
        if was_playing:
            self._sim.resume()

    def _load_from_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load System", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            bodies = [
                CelestialBody(
                    name=e["name"], mass=e["mass_kg"],
                    pos=np.array(e["pos_au"], dtype=float),
                    vel=np.array(e["vel_au_per_day"], dtype=float),
                    radius=e["radius_km"], color=tuple(e["color"]),
                )
                for e in data["bodies"]
            ]
            self._load_system(SolarSystem(bodies))
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "Load Error", f"Cannot parse file:\n{exc}")

    # ----------------------------------------------------------------
    # Misc
    # ----------------------------------------------------------------

    def _on_blow_up(self) -> None:
        self._ctrl.set_playing(False)
        self.statusBar().showMessage("⚠ Blow-up detected (body > 1000 AU). Simulation paused.")

    def closeEvent(self, event) -> None:
        if self._sim:
            self._sim.stop_thread()
        super().closeEvent(event)
```

- [ ] **Step 2: Verify import**

Run: `conda run -n nbodiesgravity python -c "from nbodiesgravity.ui.main_window import MainWindow; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add nbodiesgravity/ui/main_window.py
git commit -m "feat: add MainWindow with all panels, menus, and save/load JSON"
```

---

### Task 20: Update `main.py` — final wiring + full Milestone 4 smoke test

**Files:**
- Modify: `nbodiesgravity/main.py`

- [ ] **Step 1: Replace `main.py` with the full-window version**

```python
"""N-Body Gravity Simulation — application entry point.

Run:
    conda run -n nbodiesgravity python nbodiesgravity/main.py
"""
from __future__ import annotations
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QSurfaceFormat
from nbodiesgravity.ui.main_window import MainWindow


def _request_opengl_33() -> None:
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setDepthBufferSize(24)
    QSurfaceFormat.setDefaultFormat(fmt)


def main() -> None:
    _request_opengl_33()
    app = QApplication(sys.argv)
    app.setApplicationName("NBodiesGravity")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the complete application**

Run: `conda run -n nbodiesgravity python nbodiesgravity/main.py`

Verify each of the following manually:

| Feature | Expected behaviour |
|---|---|
| Startup | Full window with body list (left), 3D viewport (right), control panel (bottom) |
| Play button | Bodies move, coloured trails appear |
| Speed "1 s = 1 year" | Orbits visibly faster |
| Center-on Earth | Camera re-centres; Sun orbits around Earth's frame |
| Left-drag / scroll | Viewport rotates / zooms smoothly |
| Trail checkbox | Unchecking hides a trail; re-checking restores full history |
| Simulation → Add Body | Dialog opens; fills fields; new body appears in list and viewport |
| Simulation → Edit Body | Dialog pre-fills with current values; edits take effect immediately |
| Simulation → Remove Body | Confirmation prompt; body disappears |
| File → Save System | Creates a valid JSON file |
| File → Load System | Loads the saved JSON, replaces current system |
| File → New System | Reloads default solar system |
| Change date to 2010-01-01 | Progress bar appears; new state vectors loaded after JPL fetch |

- [ ] **Step 3: Run full test suite**

Run: `conda run -n nbodiesgravity python -m pytest tests/ -v`

Expected: `20 passed`

- [ ] **Step 4: Commit**

```bash
git add nbodiesgravity/main.py
git commit -m "feat: wire MainWindow into main.py — Milestone 4 complete"
```
