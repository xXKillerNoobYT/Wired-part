"""Clock-in and clock-out dialogs for labor tracking."""

import json
import os
import shutil

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wired_part.config import Config
from wired_part.database.repository import Repository
from wired_part.utils.constants import LABOR_SUBTASK_CATEGORIES
from wired_part.utils.gps import GPSError, fetch_gps, is_gps_available


class _LocationWorker(QThread):
    """Background thread to fetch device GPS coordinates.

    Uses the cross-platform GPS module which supports Windows, macOS,
    and Linux with automatic fallback to manual entry.
    """

    location_found = Signal(float, float)  # lat, lon
    location_error = Signal(str)           # error message

    def run(self):
        """Try to get location using platform-appropriate method."""
        try:
            lat, lon = fetch_gps()
            self.location_found.emit(lat, lon)
        except GPSError as e:
            self.location_error.emit(str(e))


class _PhotoSection(QGroupBox):
    """Reusable photo attachment section for clock dialogs."""

    def __init__(self, title: str = "Photos", required: bool = True,
                 parent=None):
        super().__init__(title, parent)
        self.required = required
        self._photo_paths: list[str] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        req_text = " (at least 1 required)" if self.required else ""
        self.info_label = QLabel(
            f"Attach photos of your work{req_text}."
        )
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("font-size: 10px; color: #a6adc8;")
        layout.addWidget(self.info_label)

        self.photo_list = QListWidget()
        self.photo_list.setMaximumHeight(80)
        self.photo_list.setToolTip("Attached photos")
        layout.addWidget(self.photo_list)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Photos...")
        add_btn.setToolTip(
            "Browse for photos (JPG, PNG, BMP) to attach"
        )
        add_btn.clicked.connect(self._on_add_photos)
        btn_row.addWidget(add_btn)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.setToolTip("Remove the selected photo from the list")
        remove_btn.clicked.connect(self._on_remove_photo)
        btn_row.addWidget(remove_btn)

        btn_row.addStretch()

        self.count_label = QLabel("0 photos")
        self.count_label.setStyleSheet("font-weight: bold;")
        btn_row.addWidget(self.count_label)

        layout.addLayout(btn_row)

    def _on_add_photos(self):
        """Open file dialog to select photos."""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Photos", "",
            "Images (*.jpg *.jpeg *.png *.bmp *.gif *.webp);;"
            "All Files (*)",
        )
        if files:
            for f in files:
                if f not in self._photo_paths:
                    self._photo_paths.append(f)
                    name = os.path.basename(f)
                    item = QListWidgetItem(name)
                    item.setToolTip(f)
                    self.photo_list.addItem(item)
            self._update_count()

    def _on_remove_photo(self):
        """Remove the selected photo."""
        row = self.photo_list.currentRow()
        if row >= 0:
            self.photo_list.takeItem(row)
            self._photo_paths.pop(row)
            self._update_count()

    def _update_count(self):
        """Update the photo count label."""
        n = len(self._photo_paths)
        self.count_label.setText(f"{n} photo{'s' if n != 1 else ''}")
        if self.required and n == 0:
            self.count_label.setStyleSheet(
                "font-weight: bold; color: #f38ba8;"
            )
        else:
            self.count_label.setStyleSheet(
                "font-weight: bold; color: #a6e3a1;"
            )

    def get_photo_paths(self) -> list[str]:
        """Return the list of selected photo paths."""
        return list(self._photo_paths)

    def has_minimum(self) -> bool:
        """Check if the minimum photo requirement is met."""
        if self.required:
            return len(self._photo_paths) >= 1
        return True

    def copy_photos_to_storage(self) -> list[str]:
        """Copy photos to the configured photos directory and return
        the stored paths. Creates the directory if needed."""
        photos_dir = Config.PHOTOS_DIRECTORY
        os.makedirs(photos_dir, exist_ok=True)

        stored_paths = []
        for src_path in self._photo_paths:
            filename = os.path.basename(src_path)
            # Add timestamp prefix to avoid collisions
            from datetime import datetime
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest_name = f"{ts}_{filename}"
            dest_path = os.path.join(photos_dir, dest_name)
            try:
                shutil.copy2(src_path, dest_path)
                stored_paths.append(dest_path)
            except (OSError, shutil.SameFileError):
                # If copy fails (e.g. same file), use original path
                stored_paths.append(src_path)
        return stored_paths


class _GPSSection(QGroupBox):
    """Reusable GPS section with read-only lat/lon fields (GPS-only input)."""

    def __init__(self, title: str = "GPS Location", parent=None):
        super().__init__(title, parent)
        self._loc_worker = None
        self._setup_ui()

    def _setup_ui(self):
        gps_layout = QFormLayout(self)

        self.lat_input = QLineEdit()
        self.lat_input.setReadOnly(True)
        self.lat_input.setPlaceholderText("Auto-detected by GPS")
        gps_layout.addRow("Latitude:", self.lat_input)

        self.lon_input = QLineEdit()
        self.lon_input.setReadOnly(True)
        self.lon_input.setPlaceholderText("Auto-detected by GPS")
        gps_layout.addRow("Longitude:", self.lon_input)

        self.locate_btn = QPushButton("Get My Location")
        self.locate_btn.setToolTip("Auto-detect your GPS location")
        self.locate_btn.clicked.connect(self._on_get_location)
        gps_layout.addRow("", self.locate_btn)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        gps_layout.addRow("", self.status_label)

    def auto_detect(self):
        """Start automatic GPS detection."""
        self.status_label.setText("Detecting location...")
        self.status_label.setStyleSheet("color: #fab387;")
        self.locate_btn.setEnabled(False)

        self._loc_worker = _LocationWorker()
        self._loc_worker.location_found.connect(self._on_location_found)
        self._loc_worker.location_error.connect(self._on_location_error)
        self._loc_worker.start()

    def _on_get_location(self):
        """Manually trigger GPS detection."""
        self.auto_detect()

    def _on_location_found(self, lat: float, lon: float):
        """GPS location was found."""
        self.lat_input.setText(f"{lat:.6f}")
        self.lon_input.setText(f"{lon:.6f}")
        self.locate_btn.setEnabled(True)
        self.status_label.setText(
            f"Location detected: {lat:.4f}, {lon:.4f}"
        )
        self.status_label.setStyleSheet("color: #a6e3a1;")

    def _on_location_error(self, error: str):
        """GPS detection failed."""
        self.locate_btn.setEnabled(True)
        self.status_label.setText(error)
        self.status_label.setStyleSheet("color: #a6adc8;")

    def get_coords(self) -> tuple:
        """Return (lat, lon) or (None, None) if not detected."""
        lat_text = self.lat_input.text().strip()
        lon_text = self.lon_input.text().strip()
        if lat_text and lon_text:
            try:
                return float(lat_text), float(lon_text)
            except ValueError:
                pass
        return None, None

    def stop_worker(self):
        """Stop any running GPS thread."""
        if self._loc_worker and self._loc_worker.isRunning():
            self._loc_worker.quit()
            self._loc_worker.wait(2000)


class ClockInDialog(QDialog):
    """Dialog for clocking in to a job."""

    def __init__(self, repo: Repository, user_id: int,
                 job_id: int = None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.user_id = user_id
        self.result_entry_id = None
        self.setWindowTitle("Clock In")
        self.setMinimumWidth(440)
        self._setup_ui()
        if job_id:
            idx = self.job_selector.findData(job_id)
            if idx >= 0:
                self.job_selector.setCurrentIndex(idx)
        # Auto-detect GPS on open
        self.gps_section.auto_detect()

    def closeEvent(self, event):
        """Ensure GPS thread is stopped before closing."""
        self.gps_section.stop_worker()
        super().closeEvent(event)

    def reject(self):
        """Ensure GPS thread is stopped on cancel."""
        self.gps_section.stop_worker()
        super().reject()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        # Job selector
        self.job_selector = QComboBox()
        self.job_selector.addItem("-- Select a job --", None)
        for job in self.repo.get_all_jobs("active"):
            self.job_selector.addItem(
                f"{job.job_number} -- {job.name}", job.id
            )
        self.job_selector.currentIndexChanged.connect(self._on_job_changed)
        form.addRow("Job:", self.job_selector)

        # Category
        self.category_selector = QComboBox()
        for cat in LABOR_SUBTASK_CATEGORIES:
            self.category_selector.addItem(cat)
        form.addRow("Task Category:", self.category_selector)

        layout.addLayout(form)

        # Photo section (optional at clock-in)
        self.photos = _PhotoSection(
            "Photos (optional)", required=False, parent=self
        )
        layout.addWidget(self.photos)

        # GPS section (read-only, GPS-only)
        self.gps_section = _GPSSection("GPS Location", parent=self)
        layout.addWidget(self.gps_section)

        # Proximity label (separate from GPS section for job-aware checks)
        self.proximity_label = QLabel("")
        self.proximity_label.setWordWrap(True)
        layout.addWidget(self.proximity_label)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Ok).setText("Clock In")
        buttons.accepted.connect(self._on_clock_in)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Wire GPS changes to proximity check
        self.gps_section.lat_input.textChanged.connect(
            self._check_proximity
        )
        self.gps_section.lon_input.textChanged.connect(
            self._check_proximity
        )

    def _on_job_changed(self):
        """Check proximity when job changes and GPS is entered."""
        self._check_proximity()

    def _check_proximity(self):
        """Check GPS proximity to job site if coords are provided."""
        job_id = self.job_selector.currentData()
        lat, lon = self.gps_section.get_coords()

        if not job_id or lat is None:
            return

        try:
            result = self.repo.check_proximity(lat, lon, job_id)
            if result.get("no_location"):
                self.proximity_label.setText(
                    "No location set for this job. "
                    "Proximity check skipped."
                )
                self.proximity_label.setStyleSheet("color: #a6adc8;")
            elif result["within_radius"]:
                self.proximity_label.setText(
                    f"Within range ({result['distance_miles']:.2f} mi)"
                )
                self.proximity_label.setStyleSheet("color: #a6e3a1;")
            else:
                self.proximity_label.setText(
                    f"WARNING: {result['distance_miles']:.2f} mi from "
                    f"job site (limit: {Config.GEOFENCE_RADIUS} mi). "
                    f"You can still clock in."
                )
                self.proximity_label.setStyleSheet("color: #f38ba8;")
        except ValueError:
            pass  # GPS coords still loading

    def _on_clock_in(self):
        """Validate and create clock-in entry."""
        job_id = self.job_selector.currentData()
        if not job_id:
            QMessageBox.warning(
                self, "Validation", "Please select a job."
            )
            return

        # Check for active clock-in (single clock-in enforcement)
        active = self.repo.get_active_clock_in(self.user_id)
        if active:
            QMessageBox.warning(
                self, "Already Clocked In",
                f"You are already clocked in to job "
                f"{active.job_number or 'unknown'}.\n"
                "Please clock out first.",
            )
            return

        # Get GPS coords (GPS-only, no manual entry)
        lat, lon = self.gps_section.get_coords()

        # Copy photos to storage
        stored_photos = self.photos.copy_photos_to_storage()
        photos_json = json.dumps(stored_photos) if stored_photos else None

        try:
            self.result_entry_id = self.repo.clock_in(
                user_id=self.user_id,
                job_id=job_id,
                category=self.category_selector.currentText(),
                lat=lat,
                lon=lon,
                photos=photos_json,
            )
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "Clock In Error", str(e))


# ── Construction work description prompts ─────────────────────────
# These help electricians remember what to document during clock-out
WORK_DESCRIPTION_PROMPTS = [
    "What area/room(s) did you work in today?",
    "What was roughed in, trimmed out, or completed?",
    "Any circuits pulled, terminated, or tested?",
    "Panel work: breakers landed, circuits labeled?",
    "Fixtures/devices installed or prepped?",
    "Conduit or raceway runs completed?",
    "What's the status of the work area? Clean/messy?",
]


class ClockOutDialog(QDialog):
    """Dialog for clocking out from an active labor entry.

    Features:
    - Work description (required) with construction prompts
    - Drive time (hours + minutes)
    - Photo attachment (required)
    - GPS location (GPS-only, read-only fields)
    - Checkout checklist: orders, owner notes, materials, work left,
      planning, next big things, and freeform notes
    """

    def __init__(self, repo: Repository, entry_id: int, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.entry_id = entry_id
        self.setWindowTitle("Clock Out")
        self.setMinimumWidth(520)
        self.setMinimumHeight(600)

        entry = self.repo.get_labor_entry_by_id(entry_id)
        self.entry = entry
        self._note_inputs: list[QTextEdit] = []
        self._setup_ui()
        # Auto-detect GPS on open
        self.gps_section.auto_detect()

    def closeEvent(self, event):
        """Ensure GPS thread is stopped before closing."""
        self.gps_section.stop_worker()
        super().closeEvent(event)

    def reject(self):
        """Ensure GPS thread is stopped on cancel."""
        self.gps_section.stop_worker()
        super().reject()

    def _setup_ui(self):
        # Use a scroll area since there's lots of content
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        container = QWidget()
        layout = QVBoxLayout(container)

        # ── Clock-in info ─────────────────────────────────────────
        if self.entry:
            info = QLabel(
                f"<b>Job:</b> {self.entry.job_number or 'N/A'}<br>"
                f"<b>Category:</b> {self.entry.sub_task_category}<br>"
                f"<b>Clocked In:</b> {self.entry.start_time}"
            )
            info.setWordWrap(True)
            layout.addWidget(info)

        # ── Work Description (REQUIRED) ───────────────────────────
        desc_group = QGroupBox("Work Done (required)")
        desc_layout = QVBoxLayout(desc_group)

        # Construction prompt hints
        prompts_text = "\n".join(
            f"  - {p}" for p in WORK_DESCRIPTION_PROMPTS
        )
        hint = QLabel(
            f"<b>Think about:</b><br>"
            f"{'<br>'.join('  - ' + p for p in WORK_DESCRIPTION_PROMPTS)}"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size: 10px; color: #a6adc8; padding: 4px;")
        desc_layout.addWidget(hint)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText(
            "Describe all work performed today..."
        )
        self.description_input.setMinimumHeight(100)
        self.description_input.setMaximumHeight(140)
        desc_layout.addWidget(self.description_input)
        layout.addWidget(desc_group)

        # ── Drive Time ────────────────────────────────────────────
        drive_group = QGroupBox("Drive Time")
        drive_layout = QHBoxLayout(drive_group)

        drive_layout.addWidget(QLabel("Hours:"))
        self.drive_hours = QSpinBox()
        self.drive_hours.setRange(0, 12)
        self.drive_hours.setValue(0)
        drive_layout.addWidget(self.drive_hours)

        drive_layout.addWidget(QLabel("Minutes:"))
        self.drive_minutes = QSpinBox()
        self.drive_minutes.setRange(0, 59)
        self.drive_minutes.setSingleStep(5)
        self.drive_minutes.setValue(0)
        drive_layout.addWidget(self.drive_minutes)

        drive_layout.addStretch()
        layout.addWidget(drive_group)

        # ── Photo section (required) ──────────────────────────────
        self.photos = _PhotoSection(
            "Photos (required)", required=True, parent=container
        )
        layout.addWidget(self.photos)

        # ── GPS section (read-only) ───────────────────────────────
        self.gps_section = _GPSSection("GPS Location", parent=container)
        layout.addWidget(self.gps_section)

        # ── Checkout Checklist ────────────────────────────────────
        checklist_group = QGroupBox("Checkout Checklist")
        cl = QVBoxLayout(checklist_group)

        # 1. Orders for missing parts
        self.chk_orders = QCheckBox(
            "Orders put in for missing parts?"
        )
        self.chk_orders.setToolTip(
            "If not done, consider canceling clock-out to handle this first."
        )
        cl.addWidget(self.chk_orders)
        self.orders_note = QLabel(
            "<i>If No: Consider canceling and placing orders first.</i>"
        )
        self.orders_note.setStyleSheet("font-size: 9px; color: #fab387;")
        self.orders_note.setWordWrap(True)
        cl.addWidget(self.orders_note)

        # 2. Owner/Janitor requests
        self.chk_owner_notes = QCheckBox(
            "Owner/tenant requests added to Job Notes?"
        )
        self.chk_owner_notes.setToolTip(
            "If not done, consider canceling and adding notes first."
        )
        cl.addWidget(self.chk_owner_notes)
        self.owner_note = QLabel(
            "<i>If No: Consider canceling and adding notes first.</i>"
        )
        self.owner_note.setStyleSheet("font-size: 9px; color: #fab387;")
        self.owner_note.setWordWrap(True)
        cl.addWidget(self.owner_note)

        # 3. Materials received
        self.chk_materials = QCheckBox(
            "Any materials/parts you picked up today?"
        )
        cl.addWidget(self.chk_materials)

        # 4. Work left
        cl.addWidget(QLabel("<b>Work left on this visit:</b>"))
        self.work_left_combo = QComboBox()
        self.work_left_combo.addItems([
            "Full day remaining",
            "Part day remaining",
            "No work left (complete)",
        ])
        cl.addWidget(self.work_left_combo)

        # 5. Planning: what I'm doing next 2 days
        cl.addWidget(QLabel("<b>Planning for next 2 days:</b>"))
        plan_row = QHBoxLayout()
        self.plan_day1 = QLineEdit()
        self.plan_day1.setPlaceholderText("Tomorrow...")
        plan_row.addWidget(self.plan_day1)
        self.plan_day2 = QLineEdit()
        self.plan_day2.setPlaceholderText("Day after...")
        plan_row.addWidget(self.plan_day2)
        cl.addLayout(plan_row)

        # 6. Next big things for this job
        cl.addWidget(QLabel("<b>Next big things for this job:</b>"))
        self.next_big_things = QTextEdit()
        self.next_big_things.setPlaceholderText(
            "Major upcoming milestones, inspections, deliveries..."
        )
        self.next_big_things.setMaximumHeight(60)
        cl.addWidget(self.next_big_things)

        # 7. Freeform notes (add as many as needed)
        cl.addWidget(QLabel(
            "<b>Notes:</b> <i>Blockers, observations, anything else. "
            "Goal: capture too much info, not too little.</i>"
        ))
        self._notes_container = QVBoxLayout()
        cl.addLayout(self._notes_container)
        self._add_note_field()  # Start with one

        add_note_btn = QPushButton("+ Add Another Note")
        add_note_btn.clicked.connect(self._add_note_field)
        cl.addWidget(add_note_btn)

        layout.addWidget(checklist_group)

        scroll.setWidget(container)

        # ── Main dialog layout ────────────────────────────────────
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)

        # Buttons at bottom (outside scroll)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Ok).setText("Clock Out")
        buttons.accepted.connect(self._on_clock_out)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    def _add_note_field(self):
        """Add a new freeform note text block."""
        note = QTextEdit()
        note.setPlaceholderText(
            f"Note #{len(self._note_inputs) + 1}: "
            "blocker, observation, issue, idea..."
        )
        note.setMaximumHeight(60)
        self._note_inputs.append(note)
        self._notes_container.addWidget(note)

    def _collect_checkout_notes(self) -> dict:
        """Gather all checklist data into a JSON-serializable dict."""
        notes_list = [
            n.toPlainText().strip()
            for n in self._note_inputs
            if n.toPlainText().strip()
        ]
        return {
            "orders_done": self.chk_orders.isChecked(),
            "owner_notes_done": self.chk_owner_notes.isChecked(),
            "materials_received": self.chk_materials.isChecked(),
            "work_left": self.work_left_combo.currentText(),
            "plan_day1": self.plan_day1.text().strip(),
            "plan_day2": self.plan_day2.text().strip(),
            "next_big_things": self.next_big_things.toPlainText().strip(),
            "notes": notes_list,
        }

    def _on_clock_out(self):
        """Process clock-out with full validation."""
        # 1. Work description is required
        description = self.description_input.toPlainText().strip()
        if not description:
            QMessageBox.warning(
                self, "Work Description Required",
                "Please describe the work you performed today.\n"
                "This is a required field.",
            )
            self.description_input.setFocus()
            return

        # 2. Check photo requirement
        if not self.photos.has_minimum():
            QMessageBox.warning(
                self, "Photo Required",
                "Please attach at least one photo before clocking out.",
            )
            return

        # 3. Warn if orders/notes checkboxes unchecked
        warnings = []
        if not self.chk_orders.isChecked():
            warnings.append(
                "- Orders for missing parts not confirmed"
            )
        if not self.chk_owner_notes.isChecked():
            warnings.append(
                "- Owner/tenant requests not added to notes"
            )
        if warnings:
            warn_text = "\n".join(warnings)
            reply = QMessageBox.question(
                self, "Incomplete Checklist",
                f"The following items are unchecked:\n\n{warn_text}\n\n"
                "Do you want to go back and handle these first?\n\n"
                "Click 'Yes' to go back, 'No' to clock out anyway.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.Yes:
                return

        # 4. Get GPS coords
        lat, lon = self.gps_section.get_coords()

        # 5. Calculate drive time in minutes
        drive_minutes = (
            self.drive_hours.value() * 60
            + self.drive_minutes.value()
        )

        # 6. Collect checkout notes
        checkout_data = self._collect_checkout_notes()

        # 7. Copy photos to storage
        stored_photos = self.photos.copy_photos_to_storage()
        photos_json = json.dumps(stored_photos) if stored_photos else None

        try:
            result = self.repo.clock_out(
                self.entry_id,
                lat=lat,
                lon=lon,
                description=description,
            )

            # Update additional fields on the entry
            if result:
                result.drive_time_minutes = drive_minutes
                result.checkout_notes = json.dumps(checkout_data)
                if photos_json:
                    # Merge with existing photos (from clock-in)
                    existing = result.photo_list
                    existing.extend(stored_photos)
                    result.photos = json.dumps(existing)
                self.repo.update_labor_entry(result)

            if result:
                QMessageBox.information(
                    self, "Clocked Out",
                    f"Clocked out successfully.\n"
                    f"Hours worked: {result.hours:.2f}\n"
                    f"Drive time: {drive_minutes} min",
                )
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "Clock Out Error", str(e))
