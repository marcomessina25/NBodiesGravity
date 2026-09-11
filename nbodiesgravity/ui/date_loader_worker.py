"""Background QThread worker that fetches state vectors for a new epoch date.

Keeps the UI responsive during JPL Horizons queries (up to 39 HTTP requests).

Signals
-------
body_loaded(name) : emitted after each body is resolved (for progress bar)
finished(system)  : emitted on success with the assembled SolarSystem
error(message)    : emitted on HorizonsError or unexpected exception
cancelled()       : emitted when the worker was cancelled before completion
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
    cancelled = pyqtSignal()

    def __init__(self, epoch: datetime, parent=None) -> None:
        super().__init__(parent)
        self.epoch = epoch
        self._is_cancelled = False

    def cancel(self) -> None:
        """Signal this worker to abort fetching further bodies."""
        self._is_cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def run(self) -> None:
        try:
            system = load_system_at_date(
                epoch=self.epoch,
                progress_cb=self.body_loaded.emit,
                cancel_cb=lambda: self._is_cancelled,
            )
            if self._is_cancelled:
                self.cancelled.emit()
            elif system is not None:
                self.finished.emit(system)
        except HorizonsError as exc:
            if self._is_cancelled:
                self.cancelled.emit()
            else:
                self.error.emit(str(exc))
        except Exception as exc:
            if self._is_cancelled:
                self.cancelled.emit()
            else:
                self.error.emit(f"Unexpected error: {exc}")
