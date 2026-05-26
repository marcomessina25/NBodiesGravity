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
    clear_trails_requested = pyqtSignal()    # user clicked "Clear Trails"

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

        layout.addSpacing(8)
        self._clear_trails_btn = QPushButton("Clear Trails")
        self._clear_trails_btn.clicked.connect(self.clear_trails_requested)
        layout.addWidget(self._clear_trails_btn)

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
