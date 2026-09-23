"""QThread that drives the physics simulation loop.

Calls SolarSystem.step() with wall-clock-driven dt, targeting _TARGET_HZ
iterations per second, and keeps latest_snapshot up to date for the render thread to read.

Public interface
----------------
set_timescale(days_per_second)  — call from any thread
pause() / resume()              — call from UI thread
step_once(dt=None)              — step once while paused
advance(duration)               — advance by duration while paused
reset(system)                   — call while paused
stop_thread()                   — call before application exit
latest_snapshot                 — read from render thread (GIL-safe)
"""
from __future__ import annotations
import time
import threading
import logging

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

from nbodiesgravity.engine.body import BodyState
from nbodiesgravity.engine.exceptions import NumericalIntegrityError
from nbodiesgravity.engine.system import SolarSystem
from nbodiesgravity.engine.diagnostics import ConservationTracker, DiagnosticsHistoryBuffer, DiagnosticReport

logger = logging.getLogger(__name__)

_TARGET_HZ: int = 500       # real-time physics rate cap (~500 iterations/s)
_MAX_SIM_DT: float = 1.0    # max simulated days per sub-step (accuracy cap)


class SimulationThread(QThread):
    snapshot_ready = pyqtSignal(list)   # list[BodyState]
    blow_up_detected = pyqtSignal()
    numerical_failure_detected = pyqtSignal(str)
    collisions_detected = pyqtSignal(list)   # list[CollisionEvent]
    diagnostics_ready = pyqtSignal(object)  # DiagnosticReport
    target_time_reached = pyqtSignal(float)
    step_completed = pyqtSignal(float)  # emits elapsed_days

    def __init__(self, system: SolarSystem, parent=None) -> None:
        super().__init__(parent)
        self._system = system
        self._timescale: float = 1.0   # simulated days per real second
        self._paused: bool = True
        self._running: bool = True
        self._lock = threading.Lock()
        self.latest_snapshot: list[BodyState] = system.snapshot()
        self._elapsed_days: float = 0.0
        self._max_simulation_time: float | None = None
        self._tracker = ConservationTracker(
            system.bodies,
            softening=system.softening,
            g_constant=system.physics_config.gravitational_constant,
        )
        self._history = DiagnosticsHistoryBuffer(max_points=2000)
        self._latest_report: DiagnosticReport | None = None
        self._last_diag_time: float = 0.0
        self._last_snap_time: float = 0.0

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

    @property
    def max_simulation_time(self) -> float | None:
        return self._max_simulation_time

    @max_simulation_time.setter
    def max_simulation_time(self, limit: float | None) -> None:
        self._max_simulation_time = float(limit) if limit is not None else None

    @property
    def diagnostics_history(self) -> DiagnosticsHistoryBuffer:
        return self._history

    @property
    def latest_diagnostic_report(self) -> DiagnosticReport | None:
        return self._latest_report

    @property
    def conservation_tracker(self) -> ConservationTracker:
        return self._tracker

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
            self._tracker = ConservationTracker(
                system.bodies,
                softening=system.softening,
                g_constant=system.physics_config.gravitational_constant,
            )
            self._history.clear()
            self._latest_report = None
        self._elapsed_days = 0.0   # reset date counter to match the new epoch

    def refresh_snapshot(self) -> None:
        """Force a snapshot refresh from the current system state. Safe to call while paused."""
        with self._lock:
            self.latest_snapshot = self._system.snapshot()

    def _record_diagnostics(self, snap: list[BodyState]) -> None:
        try:
            try:
                report = self._tracker.evaluate(
                    snap,
                    integrator_name=getattr(self._system.integrator, "name", "velocity_verlet"),
                    gravity_model=self._system.physics_config.gravity_model,
                    collision_model=self._system.collision_config.model,
                )
            except TypeError:
                report = self._tracker.evaluate(snap)
            self._history.append(
                self._elapsed_days,
                report,
                substeps=self._system.last_substeps,
                adaptive_dt=self._system.last_adaptive_dt,
            )
            self._latest_report = report
            self.diagnostics_ready.emit(report)
        except Exception as exc:
            logger.warning(
                "Diagnostics evaluation failed at day %.3f: %s",
                self._elapsed_days,
                exc,
                exc_info=True,
            )

    def step_once(self, dt: float | None = None) -> list:
        """Advance by exactly one substep while paused. Thread-safe."""
        with self._lock:
            collisions = self._system.step_once(dt)
            step_dt = self._system.last_adaptive_dt
            self._elapsed_days += step_dt
            snap = self._system.snapshot()
            self.latest_snapshot = snap
            if collisions:
                self.collisions_detected.emit(collisions)
            if self.receivers(self.snapshot_ready) > 0:
                self.snapshot_ready.emit(snap)
            self._record_diagnostics(snap)
            self.step_completed.emit(self._elapsed_days)
            return collisions

    def advance(self, duration: float) -> list:
        """Advance by a bounded duration in days while paused. Thread-safe."""
        with self._lock:
            remaining = duration
            collisions = []
            while remaining > 0:
                step_dt = min(remaining, _MAX_SIM_DT)
                collisions.extend(self._system.step(step_dt))
                remaining -= step_dt
            self._elapsed_days += duration
            snap = self._system.snapshot()
            self.latest_snapshot = snap
            if collisions:
                self.collisions_detected.emit(collisions)
            if self.receivers(self.snapshot_ready) > 0:
                self.snapshot_ready.emit(snap)
            self._record_diagnostics(snap)
            self.step_completed.emit(self._elapsed_days)
            return collisions

    def stop_thread(self) -> None:
        self._running = False
        self.wait()

    def run(self) -> None:
        t_prev = time.perf_counter()
        while self._running:
            if self._paused:
                time.sleep(0.001)
                t_prev = time.perf_counter()   # reset so resume never produces a huge dt
                continue

            if self._max_simulation_time is not None and self._elapsed_days >= self._max_simulation_time:
                self._paused = True
                self.target_time_reached.emit(self._elapsed_days)
                continue

            t_now = time.perf_counter()
            real_dt = min(t_now - t_prev, 0.05)   # cap at 50 ms — prevents spiral of death
            t_prev = t_now

            sim_dt = real_dt * self._timescale
            if self._max_simulation_time is not None:
                sim_dt = min(sim_dt, max(0.0, self._max_simulation_time - self._elapsed_days))
                if sim_dt <= 1e-9:
                    self._paused = True
                    self.target_time_reached.emit(self._elapsed_days)
                    continue

            collisions: list = []
            publish_snap = (t_now - self._last_snap_time >= 0.008)  # ~120 Hz render cadence
            try:
                with self._lock:
                    remaining = sim_dt
                    while remaining > 0:
                        step_dt = min(remaining, _MAX_SIM_DT)
                        collisions.extend(self._system.step(step_dt))
                        remaining -= step_dt
                    if publish_snap or collisions:
                        snap = self._system.snapshot()
            except NumericalIntegrityError as exc:
                self._paused = True
                self.numerical_failure_detected.emit(str(exc))
                continue

            self._elapsed_days += sim_dt
            if publish_snap or collisions:
                self.latest_snapshot = snap
                self._last_snap_time = t_now
                if self.receivers(self.snapshot_ready) > 0:
                    self.snapshot_ready.emit(snap)
            else:
                snap = self.latest_snapshot

            if collisions:
                self.collisions_detected.emit(collisions)

            # Record diagnostics periodically (~20 Hz)
            if t_now - self._last_diag_time >= 0.05:
                self._last_diag_time = t_now
                self._record_diagnostics(snap)

            if any(np.isnan(s.pos).any() or np.isinf(s.pos).any() or float(np.linalg.norm(s.pos)) > 1000.0 for s in snap if s.active):
                self._paused = True
                self.blow_up_detected.emit()

            # Sleep remainder of a 1/_TARGET_HZ real-time slot to yield CPU
            sleep_for = (1.0 / _TARGET_HZ) - (time.perf_counter() - t_prev)
            if sleep_for > 0:
                time.sleep(sleep_for)
