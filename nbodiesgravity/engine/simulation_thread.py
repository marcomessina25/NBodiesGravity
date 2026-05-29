"""QThread that drives the physics simulation loop.

Calls SolarSystem.step() with wall-clock-driven dt, targeting _TARGET_HZ
iterations per second, and keeps
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

_TARGET_HZ: int = 500       # real-time physics rate cap (~500 iterations/s)
_MAX_SIM_DT: float = 1.0    # max simulated days per sub-step (accuracy cap)


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
        self._elapsed_days: float = 0.0

    @property
    def is_playing(self) -> bool:
        return not self._paused

    @property
    def system(self) -> SolarSystem:
        return self._system

    @property
    def elapsed_days(self) -> float:
        """Simulated days elapsed since last system load. GIL-safe float read."""
        return self._elapsed_days

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
        self._elapsed_days = 0.0   # reset date counter to match the new epoch

    def refresh_snapshot(self) -> None:
        """Force a snapshot refresh from the current system state. Safe to call while paused."""
        with self._lock:
            self.latest_snapshot = self._system.snapshot()

    def stop_thread(self) -> None:
        self._running = False
        self.wait()

    def run(self) -> None:
        self._running = True
        t_prev = time.perf_counter()
        while self._running:
            if self._paused:
                time.sleep(0.001)
                t_prev = time.perf_counter()   # reset so resume never produces a huge dt
                continue

            t_now = time.perf_counter()
            real_dt = min(t_now - t_prev, 0.05)   # cap at 50 ms — prevents spiral of death
            t_prev = t_now

            sim_dt = real_dt * self._timescale

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

            if any(float(np.linalg.norm(s.pos)) > 1000.0 for s in snap if s.active):
                self._paused = True
                self.blow_up_detected.emit()

            # Sleep remainder of a 1/_TARGET_HZ real-time slot to yield CPU
            sleep_for = (1.0 / _TARGET_HZ) - (time.perf_counter() - t_prev)
            if sleep_for > 0:
                time.sleep(sleep_for)
