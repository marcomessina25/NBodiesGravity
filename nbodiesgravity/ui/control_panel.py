"""Bottom control bar: epoch date picker, speed slider, center picker, play/pause."""
from __future__ import annotations
import math
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QDateEdit, QComboBox,
    QPushButton, QSlider, QSizePolicy, QCheckBox,
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal

# Speed slider covers 1 h/s … 1 y/s on a log10 scale
_LOG_MIN: float = math.log10(1.0 / 24.0)   # log10(days) for 1 h/s
_LOG_MAX: float = math.log10(365.25)         # log10(days) for 1 y/s
_SLIDER_STEPS: int = 200                     # integer ticks across the range
# Default: 1 real second = 1 simulated day (slider position ≈ 35 %)
_DEFAULT_DAYS: float = 1.0


class ControlPanel(QWidget):
    date_changed = pyqtSignal(datetime)       # user committed a new epoch date
    timescale_changed = pyqtSignal(float)     # simulated days per real second
    center_changed = pyqtSignal(str)          # new center body name
    play_toggled = pyqtSignal(bool)           # True = playing
    clear_trails_requested = pyqtSignal()     # user clicked "Clear Trails"
    show_names_toggled = pyqtSignal(bool)     # True = show names

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

        self._sim_date_label = QLabel("→  –")
        self._sim_date_label.setMinimumWidth(95)
        layout.addWidget(self._sim_date_label)

        layout.addSpacing(12)

        self._play_btn = QPushButton("▶  Play")
        self._play_btn.setFixedWidth(90)
        self._play_btn.clicked.connect(self._on_play_clicked)
        layout.addWidget(self._play_btn)

        layout.addSpacing(12)

        layout.addWidget(QLabel("Speed:"))
        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setRange(0, _SLIDER_STEPS)
        self._speed_slider.setSingleStep(1)
        self._speed_slider.setPageStep(10)
        self._speed_slider.setFixedWidth(160)
        self._speed_slider.setValue(self._days_to_slider(_DEFAULT_DAYS))
        self._speed_slider.valueChanged.connect(self._on_speed_changed)
        layout.addWidget(self._speed_slider)

        self._speed_label = QLabel(self._days_to_label(_DEFAULT_DAYS))
        self._speed_label.setMinimumWidth(100)
        layout.addWidget(self._speed_label)

        layout.addSpacing(12)

        layout.addWidget(QLabel("Center:"))
        self._center_combo = QComboBox()
        self._center_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._center_combo.currentTextChanged.connect(self.center_changed)
        layout.addWidget(self._center_combo)

        layout.addSpacing(8)
        self._clear_trails_btn = QPushButton("Clear Trails")
        self._clear_trails_btn.clicked.connect(self.clear_trails_requested)
        layout.addWidget(self._clear_trails_btn)

        layout.addSpacing(12)
        self._show_names_cb = QCheckBox("Show Names")
        self._show_names_cb.setChecked(True)
        self._show_names_cb.toggled.connect(self.show_names_toggled)
        layout.addWidget(self._show_names_cb)

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

    def set_sim_date(self, text: str) -> None:
        """Update the live simulation date label. Call with a 'YYYY-MM-DD' string."""
        self._sim_date_label.setText(f"→  {text}")

    def set_center_name(self, name: str) -> None:
        """Programmatically select a body in the center combo without emitting center_changed.

        Use when code resets the camera center without user interaction (e.g., when
        a followed body is deactivated).  No-op if the name is not in the combo.
        """
        self._center_combo.blockSignals(True)
        idx = self._center_combo.findText(name)
        if idx >= 0:
            self._center_combo.setCurrentIndex(idx)
        self._center_combo.blockSignals(False)

    def set_show_names(self, checked: bool) -> None:
        """Programmatically toggle the show names checkbox without emitting show_names_toggled."""
        self._show_names_cb.blockSignals(True)
        self._show_names_cb.setChecked(checked)
        self._show_names_cb.blockSignals(False)

    # Private slots
    def _on_date_committed(self) -> None:
        qd = self._date_edit.date()
        self.date_changed.emit(datetime(qd.year(), qd.month(), qd.day()))

    def _on_play_clicked(self) -> None:
        self._playing = not self._playing
        self.set_playing(self._playing)
        self.play_toggled.emit(self._playing)

    def _on_speed_changed(self, pos: int) -> None:
        days = self._slider_to_days(pos)
        self._speed_label.setText(self._days_to_label(days))
        self.timescale_changed.emit(days)

    # ----------------------------------------------------------------
    # Speed scale helpers
    # ----------------------------------------------------------------

    @staticmethod
    def _slider_to_days(pos: int) -> float:
        """Map slider position [0, _SLIDER_STEPS] → days/real-second (log scale)."""
        t = pos / _SLIDER_STEPS
        return 10.0 ** (_LOG_MIN + t * (_LOG_MAX - _LOG_MIN))

    @staticmethod
    def _days_to_slider(days: float) -> int:
        """Inverse of _slider_to_days — used to set slider from a known days value."""
        t = (math.log10(max(days, 10.0 ** _LOG_MIN)) - _LOG_MIN) / (_LOG_MAX - _LOG_MIN)
        return round(max(0, min(_SLIDER_STEPS, t * _SLIDER_STEPS)))

    @staticmethod
    def _days_to_label(days: float) -> str:
        """Human-readable speed string, auto-selecting the most natural unit."""
        hours = days * 24.0
        if hours < 23.9:
            return f"1s = {hours:.1f}h"
        if days < 29.5:
            return f"1s = {days:.1f}d"
        months = days / 30.4375
        if months < 11.5:
            return f"1s = {months:.1f}mo"
        return f"1s = {days / 365.25:.2f}y"
