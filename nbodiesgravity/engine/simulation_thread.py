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
            self._elapsed_days += dt          # GIL-safe: single float write, one writer
            self.latest_snapshot = snap       # atomic reference swap (GIL)
            self.snapshot_ready.emit(snap)
            if any(float(np.linalg.norm(s.pos)) > 1000.0 for s in snap):
                self._paused = True
                self.blow_up_detected.emit()
