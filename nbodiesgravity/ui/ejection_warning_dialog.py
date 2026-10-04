"""Non-modal, auto-closing warning dialog issued when a body is ejected from the system."""
from __future__ import annotations

from typing import Sequence
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyle,
    QApplication,
    QScrollArea,
    QWidget,
)

from nbodiesgravity.engine.stability import EjectionEvent


class EjectionWarningDialog(QDialog):
    """Notification popup displayed when celestial bodies escape the system boundary.

    Automatically closes after a few seconds without blocking simulation execution.
    """

    def __init__(
        self,
        events: Sequence[EjectionEvent],
        parent: QWidget | None = None,
        duration_sec: float = 4.0,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("System Boundary Ejection Warning — NBodiesGravity")
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.resize(520, 280)

        self._events: list[EjectionEvent] = list(events)
        self._duration_sec: float = duration_sec
        self._remaining_sec: int = int(round(duration_sec))

        self._build_ui()

        # Auto-closing countdown timer
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_timer_tick)
        self._timer.start()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header row: Warning Icon + Title
        hdr_layout = QHBoxLayout()
        hdr_layout.setSpacing(12)

        icon_label = QLabel()
        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
        icon_label.setPixmap(icon.pixmap(36, 36))
        hdr_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        lbl_title = QLabel("<b>Celestial Body Ejection Warning</b>")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #e67e22;")
        lbl_subtitle = QLabel("Unbound body detected outside gravitational system boundary.")
        lbl_subtitle.setStyleSheet("color: #888888; font-size: 12px;")
        title_layout.addWidget(lbl_title)
        title_layout.addWidget(lbl_subtitle)
        hdr_layout.addLayout(title_layout, 1)

        layout.addLayout(hdr_layout)

        # Body details area (scrollable if multiple bodies ejected)
        self._body_label = QLabel()
        self._body_label.setWordWrap(True)
        self._body_label.setTextFormat(Qt.TextFormat.RichText)
        self._update_body_text()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.addWidget(self._body_label)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        # Scientific note
        lbl_note = QLabel(
            "<span style='color:#7f8c8d; font-size:11px;'>"
            "<b>Astrophysical Rationale:</b> A body on an outward hyperbolic trajectory "
            "(<i>E &ge; 0</i>) past 1,000 AU is gravitationally unbound and will not return. "
            "Excluding it from N-body integration prevents coordinate scale collapse, "
            "preserves numerical stability, and avoids unnecessary <i>O(N)</i> computation."
            "</span>"
        )
        lbl_note.setWordWrap(True)
        lbl_note.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(lbl_note)

        # Bottom Bar: Countdown notice + Acknowledge Button
        bottom_layout = QHBoxLayout()
        self._lbl_countdown = QLabel(f"Closing automatically in {self._remaining_sec}s…")
        self._lbl_countdown.setStyleSheet("color: #95a5a6; font-size: 11px;")
        bottom_layout.addWidget(self._lbl_countdown)
        bottom_layout.addStretch()

        btn_ack = QPushButton("Acknowledge")
        btn_ack.setDefault(True)
        btn_ack.setFixedWidth(110)
        btn_ack.clicked.connect(self.accept)
        bottom_layout.addWidget(btn_ack)

        layout.addLayout(bottom_layout)

    def _update_body_text(self) -> None:
        lines: list[str] = []
        if len(self._events) == 1:
            ev = self._events[0]
            lines.append(
                f"Body <b>{ev.name}</b> has exceeded the system boundary at "
                f"<b>{ev.distance_au:.1f} AU</b> on an unbound trajectory "
                f"(asymptotic speed <i>v<sub>&infin;</sub></i>: <b>{ev.v_infinity_km_s:.1f} km/s</b>)."
            )
            lines.append(
                "<br>It has been <b>excluded from the simulation and computation</b>."
            )
        else:
            lines.append("The following bodies have left the system and were excluded from integration:<br>")
            for ev in self._events:
                lines.append(
                    f"• <b>{ev.name}</b>: distance {ev.distance_au:.1f} AU, "
                    f"<i>v<sub>&infin;</sub></i> {ev.v_infinity_km_s:.1f} km/s"
                )
        self._body_label.setText("".join(lines))

    def append_events(self, new_events: Sequence[EjectionEvent]) -> None:
        """Append newly escaped bodies to an existing dialog and reset the countdown."""
        for ev in new_events:
            if not any(e.name == ev.name for e in self._events):
                self._events.append(ev)
        self._update_body_text()
        self._remaining_sec = int(round(self._duration_sec))
        self._lbl_countdown.setText(f"Closing automatically in {self._remaining_sec}s…")

    def _on_timer_tick(self) -> None:
        self._remaining_sec -= 1
        if self._remaining_sec <= 0:
            self._timer.stop()
            self.accept()
        else:
            self._lbl_countdown.setText(f"Closing automatically in {self._remaining_sec}s…")
