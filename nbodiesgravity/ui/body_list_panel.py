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
