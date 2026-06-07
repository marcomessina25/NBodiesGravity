"""QMainWindow assembling all panels and wiring all signals/slots."""
from __future__ import annotations
import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QVBoxLayout,
    QProgressDialog, QFileDialog, QMessageBox, QStatusBar,
)
from PyQt6.QtCore import Qt, QTimer

from nbodiesgravity.data.loader import load_default_system
from nbodiesgravity.engine.body import CelestialBody
from nbodiesgravity.engine.system import SolarSystem
from nbodiesgravity.engine.simulation_thread import SimulationThread
from nbodiesgravity.rendering.display_info import BodyDisplayInfo
from nbodiesgravity.rendering.gl_widget import GLWidget
from nbodiesgravity.ui.body_editor_dialog import BodyEditorDialog
from nbodiesgravity.ui.body_list_panel import BodyListPanel
from nbodiesgravity.ui.control_panel import ControlPanel
from nbodiesgravity.ui.date_loader_worker import DateLoaderWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("N-Body Gravity Simulation")
        self.resize(1400, 900)
        self._sim: SimulationThread | None = None
        self._loader: DateLoaderWorker | None = None
        self._progress: QProgressDialog | None = None
        self._last_epoch = datetime(2000, 1, 1)
        self._initial_system: SolarSystem | None = None
        self._initial_epoch: datetime = datetime(2000, 1, 1)
        self._date_timer = QTimer(self)
        self._date_timer.setInterval(250)   # 4 Hz — invisible to the user
        self._date_timer.timeout.connect(self._update_sim_date)
        self._build_ui()
        self._load_system(load_default_system())

    # ----------------------------------------------------------------
    # UI construction
    # ----------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._body_list = BodyListPanel()
        self._body_list.setFixedWidth(220)
        self._gl = GLWidget()
        splitter.addWidget(self._body_list)
        splitter.addWidget(self._gl)
        splitter.setStretchFactor(1, 1)
        outer.addWidget(splitter, stretch=1)

        self._ctrl = ControlPanel()
        outer.addWidget(self._ctrl)
        self.setStatusBar(QStatusBar())

        self._build_menus()

        # Wire signals
        self._ctrl.date_changed.connect(self._on_date_changed)
        self._ctrl.timescale_changed.connect(
            lambda v: self._sim and self._sim.set_timescale(v)
        )
        self._ctrl.center_changed.connect(self._gl.camera.set_center)
        self._ctrl.play_toggled.connect(self._on_play_toggled)
        self._body_list.body_selected.connect(self._on_body_selected)
        self._body_list.body_edit_requested.connect(self._edit_body)
        self._body_list.trail_toggled.connect(self._on_trail_toggled)
        self._body_list.body_active_toggled.connect(self._on_body_active_toggled)
        self._body_list.all_bodies_set.connect(self._on_all_bodies_set)
        self._body_list.all_trails_set.connect(self._on_all_trails_set)
        self._ctrl.clear_trails_requested.connect(self._gl.clear_trails)
        self._ctrl.center_changed.connect(lambda _: self._gl.clear_trails())
        self._ctrl.show_names_toggled.connect(self._on_show_names_toggled_from_ctrl)
        self._ctrl.restart_requested.connect(self._on_restart)
        self._ctrl.top_view_requested.connect(self._on_top_view)
        
        self._body_list.category_active_toggled.connect(self._on_category_active_toggled)
        self._body_list.category_trail_toggled.connect(self._on_category_trail_toggled)
        self._body_list.category_name_toggled.connect(self._on_category_name_toggled)

    def _build_menus(self) -> None:
        mb = self.menuBar()
        fm = mb.addMenu("&File")
        fm.addAction("New System",       self._new_system)
        fm.addAction("Load System…",     self._load_from_file)
        fm.addAction("Save System…",     self._save_to_file)
        fm.addSeparator()
        fm.addAction("E&xit",            self.close)

        sm = mb.addMenu("&Simulation")
        sm.addAction("Add Body…",        self._add_body)
        sm.addAction("Edit Selected…",   lambda: self._edit_body(self._body_list.selected_name()))
        sm.addAction("Remove Selected",  self._remove_selected)

        vm = mb.addMenu("&View")
        vm.addAction("Reset Camera",     self._reset_camera)
        vm.addAction("Top View",         self._on_top_view)
        vm.addAction("Toggle All Trails",self._toggle_all_trails)
        self._action_show_names = vm.addAction("Show Body Names")
        self._action_show_names.setCheckable(True)
        self._action_show_names.setChecked(True)
        self._action_show_names.triggered.connect(self._on_show_names_toggled)

    # ----------------------------------------------------------------
    # System management
    # ----------------------------------------------------------------

    def _load_system(self, system: SolarSystem, is_restart: bool = False) -> None:
        if self._sim is not None:
            self._sim.pause()
            self._sim.stop_thread()
        if not is_restart:
            self._initial_system = system.clone()
            self._initial_epoch = self._last_epoch
        self._sim = SimulationThread(system)
        self._sim.blow_up_detected.connect(self._on_blow_up)
        self._sim.collisions_detected.connect(self._on_collisions)
        display_infos = [
            BodyDisplayInfo(b.name, b.radius, b.color, is_star=(b.name == "Sun"))
            for b in system.bodies
        ]
        self._gl.set_display_info(display_infos)
        self._gl.set_simulation_thread(self._sim)
        self._ctrl.set_body_names([b.name for b in system.bodies])
        self._ctrl.set_playing(False)
        self._ctrl.set_epoch_date(self._last_epoch)
        self._body_list.populate(system.bodies)
        self._gl.clear_trails()         # reset trails BEFORE thread writes new ones
        self._ctrl.set_sim_date("–")
        self._date_timer.start()
        self._sim.start()
        self.statusBar().showMessage(f"Loaded {len(system.bodies)} bodies.")

    # ----------------------------------------------------------------
    # Control panel slots
    # ----------------------------------------------------------------

    def _on_play_toggled(self, playing: bool) -> None:
        if self._sim:
            self._sim.resume() if playing else self._sim.pause()

    def _on_body_selected(self, name: str) -> None:
        if self._sim:
            snap = self._sim.latest_snapshot
            self._gl.camera.focus_on_body(name, snap)
            self._gl.update()

    def _on_date_changed(self, dt: datetime) -> None:
        # Ignore if the target date is identical to current to prevent focus loops
        if dt == self._last_epoch:
            return
            
        # Ignore if already loading to prevent duplicate queries
        if self._loader is not None and self._loader.isRunning():
            return

        if self._sim:
            self._sim.pause()
            self._ctrl.set_playing(False)
            with self._sim._lock:
                num_bodies = len(self._sim.system.bodies)
        else:
            num_bodies = 39
        self._last_epoch = dt
        self._progress = QProgressDialog(
            "Fetching from JPL Horizons…", "Cancel", 0, num_bodies, self
        )
        self._progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress.setMinimumDuration(0)   # show immediately, don't wait 4s
        self._progress.setValue(0)
        self._progress.show()
        self._loader = DateLoaderWorker(dt)
        self._loader.body_loaded.connect(self._on_body_loaded)
        self._loader.finished.connect(self._on_load_finished)
        self._loader.error.connect(self._on_load_error)
        self._loader.start()

    def _on_body_loaded(self, name: str) -> None:
        prog = self._progress
        if prog is not None:
            prog.setLabelText(f"Loaded {name}…")
            prog.setValue(prog.value() + 1)

    def _on_load_finished(self, system: SolarSystem) -> None:
        if self._progress:
            self._progress.close()
            self._progress = None
        self._loader = None
        self._load_system(system)

    def _on_load_error(self, msg: str) -> None:
        if self._progress:
            self._progress.close()
            self._progress = None
        self._loader = None
        QMessageBox.warning(
            self, "JPL Horizons Error",
            f"Could not fetch state vectors:\n{msg}\n\nReverted to last valid epoch.",
        )
        self.statusBar().showMessage("JPL error — reverted.")

    def _on_restart(self) -> None:
        if self._initial_system is not None:
            self._last_epoch = self._initial_epoch
            self._load_system(self._initial_system.clone(), is_restart=True)
            self.statusBar().showMessage("Simulation restarted.")

    # ----------------------------------------------------------------
    # Body editor slots
    # ----------------------------------------------------------------

    # Body editor slots
    # ----------------------------------------------------------------

    def _add_body(self) -> None:
        if self._sim is None:
            return
        self._sim.pause()
        self._ctrl.set_playing(False)
        with self._sim._lock:
            bodies = self._sim.system.bodies
        existing = [b.name for b in bodies]
        dlg = BodyEditorDialog(
            existing_names=existing,
            template_bodies=bodies,
            parent=self,
        )
        if dlg.exec() == BodyEditorDialog.DialogCode.Accepted:
            body = dlg.result_body()
            with self._sim._lock:
                self._sim.system.add_body(body)
                if self._initial_system is not None:
                    initial_body = CelestialBody(
                        name=body.name,
                        mass=body.mass,
                        pos=body.pos.copy(),
                        vel=body.vel.copy(),
                        radius=body.radius,
                        color=body.color,
                        show_trail=body.show_trail,
                        active=body.active,
                        label=body.label,
                        show_name=body.show_name,
                    )
                    self._initial_system.add_body(initial_body)
            self._refresh_after_body_change()

    def _edit_body(self, name: str | None) -> None:
        if not name or self._sim is None:
            return
        self._sim.pause()
        self._ctrl.set_playing(False)
        with self._sim._lock:
            body = self._sim.system.get_body(name)
            bodies = self._sim.system.bodies
        if body is None:
            return
        existing = [b.name for b in bodies if b.name != name]
        templates = [b for b in bodies if b.name != name]
        dlg = BodyEditorDialog(
            existing_names=existing,
            body=body,
            template_bodies=templates,
            parent=self,
        )
        if dlg.exec() == BodyEditorDialog.DialogCode.Accepted:
            updated = dlg.result_body()
            with self._sim._lock:
                body.name = updated.name
                body.mass = updated.mass
                body.pos = updated.pos
                body.vel = updated.vel
                body.radius = updated.radius
                body.color = updated.color
                body.label = updated.label
                if self._initial_system is not None:
                    initial_body = self._initial_system.get_body(name)
                    if initial_body:
                        initial_body.name = updated.name
                        initial_body.mass = updated.mass
                        initial_body.pos = updated.pos.copy()
                        initial_body.vel = updated.vel.copy()
                        initial_body.radius = updated.radius
                        initial_body.color = updated.color
                        initial_body.label = updated.label
            self._refresh_after_body_change()

    def _remove_selected(self) -> None:
        name = self._body_list.selected_name()
        if not name or self._sim is None:
            return
        if QMessageBox.question(
            self, "Remove Body", f"Remove '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._sim.pause()
        self._ctrl.set_playing(False)
        with self._sim._lock:
            self._sim.system.remove_body(name)
            if self._initial_system is not None:
                self._initial_system.remove_body(name)
        self._refresh_after_body_change()

    def _on_trail_toggled(self, name: str, enabled: bool) -> None:
        if self._sim:
            with self._sim._lock:
                body = self._sim.system.get_body(name)
                if body:
                    body.show_trail = enabled
                    if self._initial_system is not None:
                        initial_body = self._initial_system.get_body(name)
                        if initial_body:
                            initial_body.show_trail = enabled

    def _on_body_active_toggled(self, name: str, active: bool) -> None:
        if self._sim is None:
            return
        with self._sim._lock:
            body = self._sim.system.get_body(name)
            if body:
                body.active = active
                if self._initial_system is not None:
                    initial_body = self._initial_system.get_body(name)
                    if initial_body:
                        initial_body.active = active
                if not active:
                    self._gl.clear_trail_for(name)
                    # If the camera is following this body, move to the first remaining
                    # active body so the camera does not freeze on a deactivated body.
                    if self._gl.camera.center_name == name:
                        fallback = next(
                            (b.name for b in self._sim.system.bodies
                             if b.active and b.name != name),
                            name,  # last resort: stay on frozen body
                        )
                        self._gl.camera.set_center(fallback)
                        self._ctrl.set_center_name(fallback)
                        self._gl.clear_trails()

    def _on_all_bodies_set(self, active: bool) -> None:
        if self._sim is None:
            return
        with self._sim._lock:
            for body in self._sim.system.bodies:
                body.active = active
                if self._initial_system is not None:
                    initial_body = self._initial_system.get_body(body.name)
                    if initial_body:
                        initial_body.active = active
            if not active:
                self._gl.clear_trails()
                # All bodies deactivated — reset camera center to Sun so it does
                # not freeze at the last position of whatever body was followed.
                if self._gl.camera.center_name != "Sun":
                    self._gl.camera.set_center("Sun")
                    self._ctrl.set_center_name("Sun")
            bodies = self._sim.system.bodies
        self._body_list.populate(bodies)

    def _on_all_trails_set(self, enabled: bool) -> None:
        if self._sim is None:
            return
        with self._sim._lock:
            for body in self._sim.system.bodies:
                body.show_trail = enabled
                if self._initial_system is not None:
                    initial_body = self._initial_system.get_body(body.name)
                    if initial_body:
                        initial_body.show_trail = enabled
            bodies = self._sim.system.bodies
        self._body_list.populate(bodies)

    def _on_category_active_toggled(self, label: str, active: bool) -> None:
        if self._sim is None:
            return
        with self._sim._lock:
            for body in self._sim.system.bodies:
                if body.label == label:
                    body.active = active
                    if self._initial_system is not None:
                        initial_body = self._initial_system.get_body(body.name)
                        if initial_body:
                            initial_body.active = active
                    if not active:
                        self._gl.clear_trail_for(body.name)
            if not active and self._gl.camera.center_name:
                followed = self._sim.system.get_body(self._gl.camera.center_name)
                if followed and not followed.active:
                    fallback = next(
                        (b.name for b in self._sim.system.bodies if b.active),
                        self._gl.camera.center_name
                    )
                    self._gl.camera.set_center(fallback)
                    self._ctrl.set_center_name(fallback)
                    self._gl.clear_trails()
            bodies = self._sim.system.bodies
        self._body_list.populate(bodies)
        self._gl.update()

    def _on_category_trail_toggled(self, label: str, enabled: bool) -> None:
        if self._sim is None:
            return
        with self._sim._lock:
            for body in self._sim.system.bodies:
                if body.label == label:
                    body.show_trail = enabled
                    if self._initial_system is not None:
                        initial_body = self._initial_system.get_body(body.name)
                        if initial_body:
                            initial_body.show_trail = enabled
            bodies = self._sim.system.bodies
        self._body_list.populate(bodies)
        self._gl.update()

    def _on_category_name_toggled(self, label: str, enabled: bool) -> None:
        if self._sim is None:
            return
        with self._sim._lock:
            for body in self._sim.system.bodies:
                if body.label == label:
                    body.show_name = enabled
                    if self._initial_system is not None:
                        initial_body = self._initial_system.get_body(body.name)
                        if initial_body:
                            initial_body.show_name = enabled
            bodies = self._sim.system.bodies
        self._body_list.populate(bodies)
        self._gl.update()

    def _refresh_after_body_change(self) -> None:
        if self._sim is None:
            return
        with self._sim._lock:
            bodies = self._sim.system.bodies
            display_infos = [
                BodyDisplayInfo(b.name, b.radius, b.color, is_star=(b.name == "Sun"))
                for b in bodies
            ]
            self._sim.latest_snapshot = self._sim.system.snapshot()
        self._body_list.populate(bodies)
        self._ctrl.set_body_names([b.name for b in bodies])
        self._gl.set_display_info(display_infos)
        self._gl.update()

    # ----------------------------------------------------------------
    # View menu
    # ----------------------------------------------------------------

    def _reset_camera(self) -> None:
        cam = self._gl.camera
        cam.azimuth, cam.elevation, cam.distance = 0.3, 0.5, 6.0
        cam.panning_offset = np.zeros(3, dtype=np.float32)
        self._gl.update()

    def _on_top_view(self) -> None:
        self._gl.camera.set_top_view()
        self._gl.update()

    def _toggle_all_trails(self) -> None:
        if self._sim is None:
            return
        bodies = self._sim.system.bodies
        new_state = not all(b.show_trail for b in bodies)
        self._on_all_trails_set(new_state)

    def _on_show_names_toggled(self, checked: bool) -> None:
        self._ctrl.blockSignals(True)
        self._ctrl.set_show_names(checked)
        self._ctrl.blockSignals(False)
        self._gl.set_show_names(checked)

    def _on_show_names_toggled_from_ctrl(self, checked: bool) -> None:
        self._action_show_names.blockSignals(True)
        self._action_show_names.setChecked(checked)
        self._action_show_names.blockSignals(False)
        self._gl.set_show_names(checked)

    # ----------------------------------------------------------------
    # File menu
    # ----------------------------------------------------------------

    def _new_system(self) -> None:
        self._load_system(load_default_system())

    def _save_to_file(self) -> None:
        if self._sim is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save System", "", "JSON (*.json)")
        if not path:
            return
        was_playing = self._sim.is_playing
        self._sim.pause()
        self._ctrl.set_playing(False)
        with self._sim._lock:
            bodies = self._sim.system.bodies
            data = {
                "bodies": [
                    {
                        "name": b.name, "mass_kg": b.mass, "radius_km": b.radius,
                        "color": list(b.color),
                        "pos_au": b.pos.tolist(),
                        "vel_au_per_day": b.vel.tolist(),
                    }
                    for b in bodies
                ]
            }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self.statusBar().showMessage(f"Saved {len(bodies)} bodies to {Path(path).name}")
        if was_playing:
            self._sim.resume()
            self._ctrl.set_playing(True)

    def _load_from_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load System", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            bodies = [
                CelestialBody(
                    name=e["name"], mass=e["mass_kg"],
                    pos=np.array(e["pos_au"], dtype=float),
                    vel=np.array(e["vel_au_per_day"], dtype=float),
                    radius=e["radius_km"], color=tuple(e["color"]),
                )
                for e in data["bodies"]
            ]
            self._load_system(SolarSystem(bodies))
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "Load Error", f"Cannot parse file:\n{exc}")

    # ----------------------------------------------------------------
    # Misc
    # ----------------------------------------------------------------

    def _on_blow_up(self) -> None:
        self._ctrl.set_playing(False)
        self.statusBar().showMessage("⚠ Blow-up detected (body > 1000 AU). Simulation paused.")

    def _on_collisions(self, events) -> None:
        """Handle merges reported by the physics thread (UI thread, queued).

        Retargets the camera if it was following an absorbed body, then rebuilds
        the body list, display infos, and center combo. Collisions are NOT
        mirrored into _initial_system, so Restart restores the pre-collision
        epoch state.
        """
        if self._sim is None:
            return
        center = self._gl.camera.center_name
        new_center = center
        for ev in events:
            # Follow the chain: a survivor of an earlier merge can be absorbed by
            # a later one within the same batch. Resolve to the final survivor so
            # the camera never lands on a body that was itself absorbed.
            if ev.absorbed == new_center:
                new_center = ev.survivor
        if new_center != center:
            self._gl.camera.set_center(new_center)
            self._ctrl.set_center_name(new_center)
            self._gl.clear_trails()
        self._refresh_after_body_change()

    def _update_sim_date(self) -> None:
        if self._sim is None:
            return
        current = self._last_epoch + timedelta(days=self._sim.elapsed_days)
        self._ctrl.set_sim_date(current.strftime("%Y-%m-%d"))

    def closeEvent(self, event) -> None:
        self._date_timer.stop()
        if self._sim:
            self._sim.stop_thread()
        super().closeEvent(event)
