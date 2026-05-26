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
