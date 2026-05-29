"""Side panel: scrollable body list with colour dot, active toggle, and trail toggle per row."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QCheckBox, QLabel, QPushButton,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap

from nbodiesgravity.engine.body import CelestialBody


class BodyListPanel(QWidget):
    body_selected       = pyqtSignal(str)        # single-click
    body_edit_requested = pyqtSignal(str)        # double-click
    trail_toggled       = pyqtSignal(str, bool)  # (name, enabled)
    body_active_toggled = pyqtSignal(str, bool)  # (name, active)
    all_bodies_set      = pyqtSignal(bool)       # True = enable all, False = disable all
    all_trails_set      = pyqtSignal(bool)       # True = enable all, False = disable all

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Bodies bulk-action row
        layout.addWidget(QLabel("Bodies"))
        body_btns = QHBoxLayout()
        self._btn_bodies_on  = QPushButton("Enable All")
        self._btn_bodies_off = QPushButton("Disable All")
        self._btn_bodies_on.setFixedHeight(22)
        self._btn_bodies_off.setFixedHeight(22)
        self._btn_bodies_on.clicked.connect(lambda: self.all_bodies_set.emit(True))
        self._btn_bodies_off.clicked.connect(lambda: self.all_bodies_set.emit(False))
        body_btns.addWidget(self._btn_bodies_on)
        body_btns.addWidget(self._btn_bodies_off)
        layout.addLayout(body_btns)

        # Trails bulk-action row
        layout.addWidget(QLabel("Trails"))
        trail_btns = QHBoxLayout()
        self._btn_trails_on  = QPushButton("Enable All")
        self._btn_trails_off = QPushButton("Disable All")
        self._btn_trails_on.setFixedHeight(22)
        self._btn_trails_off.setFixedHeight(22)
        self._btn_trails_on.clicked.connect(lambda: self.all_trails_set.emit(True))
        self._btn_trails_off.clicked.connect(lambda: self.all_trails_set.emit(False))
        trail_btns.addWidget(self._btn_trails_on)
        trail_btns.addWidget(self._btn_trails_off)
        layout.addLayout(trail_btns)

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
        # Active checkbox
        cb_active = QCheckBox("Active")
        cb_active.setChecked(body.active)
        name = body.name
        cb_active.checkStateChanged.connect(
            lambda state, n=name: self.body_active_toggled.emit(
                n, state == Qt.CheckState.Checked
            )
        )
        layout.addWidget(cb_active)
        # Trail checkbox
        cb_trail = QCheckBox("Trail")
        cb_trail.setChecked(body.show_trail)
        cb_trail.checkStateChanged.connect(
            lambda state, n=name: self.trail_toggled.emit(
                n, state == Qt.CheckState.Checked
            )
        )
        layout.addWidget(cb_trail)
        return row
