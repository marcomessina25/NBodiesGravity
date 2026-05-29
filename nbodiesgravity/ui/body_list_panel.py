"""Side panel: scrollable body list with colour dot, active toggle, and trail toggle per row."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QListWidget, QListWidgetItem,
    QCheckBox, QLabel, QPushButton,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap

from nbodiesgravity.engine.body import CelestialBody


class BodyListPanel(QWidget):
    body_selected           = pyqtSignal(str)        # single-click
    body_edit_requested     = pyqtSignal(str)        # double-click
    trail_toggled           = pyqtSignal(str, bool)  # (name, enabled)
    body_active_toggled     = pyqtSignal(str, bool)  # (name, active)
    all_bodies_set          = pyqtSignal(bool)       # True = enable all, False = disable all
    all_trails_set          = pyqtSignal(bool)       # True = enable all, False = disable all
    
    category_active_toggled = pyqtSignal(str, bool)  # (label, active)
    category_trail_toggled  = pyqtSignal(str, bool)  # (label, show_trail)
    category_name_toggled   = pyqtSignal(str, bool)  # (label, show_name)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Global Controls Section
        layout.addWidget(QLabel("Global Actions"))
        
        global_btns = QGridLayout()
        global_btns.setContentsMargins(0, 0, 0, 0)
        global_btns.setSpacing(4)
        
        global_btns.addWidget(QLabel("Bodies:"), 0, 0)
        self._btn_bodies_on  = QPushButton("Enable")
        self._btn_bodies_off = QPushButton("Disable")
        self._btn_bodies_on.setFixedHeight(22)
        self._btn_bodies_off.setFixedHeight(22)
        self._btn_bodies_on.clicked.connect(lambda: self.all_bodies_set.emit(True))
        self._btn_bodies_off.clicked.connect(lambda: self.all_bodies_set.emit(False))
        global_btns.addWidget(self._btn_bodies_on, 0, 1)
        global_btns.addWidget(self._btn_bodies_off, 0, 2)
        
        global_btns.addWidget(QLabel("Trails:"), 1, 0)
        self._btn_trails_on  = QPushButton("Enable")
        self._btn_trails_off = QPushButton("Disable")
        self._btn_trails_on.setFixedHeight(22)
        self._btn_trails_off.setFixedHeight(22)
        self._btn_trails_on.clicked.connect(lambda: self.all_trails_set.emit(True))
        self._btn_trails_off.clicked.connect(lambda: self.all_trails_set.emit(False))
        global_btns.addWidget(self._btn_trails_on, 1, 1)
        global_btns.addWidget(self._btn_trails_off, 1, 2)
        
        layout.addLayout(global_btns)
        layout.addSpacing(4)

        # Category-level controls grid
        layout.addWidget(QLabel("Category Controls"))
        grid = QGridLayout()
        grid.setContentsMargins(2, 2, 2, 2)
        grid.setSpacing(4)
        
        # Headers
        grid.addWidget(QLabel("Category"), 0, 0, Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(QLabel("Act"), 0, 1, Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(QLabel("Trl"), 0, 2, Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(QLabel("Nam"), 0, 3, Qt.AlignmentFlag.AlignCenter)
        
        self._category_widgets = {}
        self._block_category_signals = False
        
        categories = [
            ("star", "Stars"),
            ("planet", "Planets"),
            ("moon", "Moons"),
            ("dwarf planet", "Dwarf Pl."),
            ("asteroid", "Asteroids")
        ]
        
        for idx, (label, display_name) in enumerate(categories, start=1):
            grid.addWidget(QLabel(display_name), idx, 0, Qt.AlignmentFlag.AlignLeft)
            
            cb_act = QCheckBox()
            cb_trl = QCheckBox()
            cb_nam = QCheckBox()
            
            # Connect signals
            cb_act.toggled.connect(lambda checked, l=label: self._on_cat_act_toggled(l, checked))
            cb_trl.toggled.connect(lambda checked, l=label: self._on_cat_trl_toggled(l, checked))
            cb_nam.toggled.connect(lambda checked, l=label: self._on_cat_nam_toggled(l, checked))
            
            grid.addWidget(cb_act, idx, 1, Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(cb_trl, idx, 2, Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(cb_nam, idx, 3, Qt.AlignmentFlag.AlignCenter)
            
            self._category_widgets[label] = {
                "active": cb_act,
                "trail": cb_trl,
                "name": cb_nam
            }
            
        layout.addLayout(grid)
        layout.addSpacing(4)

        layout.addWidget(QLabel("Individual Bodies"))
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
            
        self.update_category_checkboxes(bodies)

    def update_category_checkboxes(self, bodies: list[CelestialBody]) -> None:
        self._block_category_signals = True
        
        for label, widgets in self._category_widgets.items():
            cat_bodies = [b for b in bodies if b.label == label]
            if not cat_bodies:
                widgets["active"].setChecked(False)
                widgets["trail"].setChecked(False)
                widgets["name"].setChecked(False)
                continue
                
            all_active = all(b.active for b in cat_bodies)
            all_trail = all(b.show_trail for b in cat_bodies)
            all_name = all(b.show_name for b in cat_bodies)
            
            widgets["active"].setChecked(all_active)
            widgets["trail"].setChecked(all_trail)
            widgets["name"].setChecked(all_name)
            
        self._block_category_signals = False

    def selected_name(self) -> str | None:
        item = self._list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _on_cat_act_toggled(self, label: str, checked: bool) -> None:
        if not self._block_category_signals:
            self.category_active_toggled.emit(label, checked)

    def _on_cat_trl_toggled(self, label: str, checked: bool) -> None:
        if not self._block_category_signals:
            self.category_trail_toggled.emit(label, checked)

    def _on_cat_nam_toggled(self, label: str, checked: bool) -> None:
        if not self._block_category_signals:
            self.category_name_toggled.emit(label, checked)

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
