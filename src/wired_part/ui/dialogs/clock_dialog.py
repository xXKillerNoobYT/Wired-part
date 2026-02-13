"""Clock-in and clock-out dialogs for labor tracking."""

import json
import os
import re
import shutil
import subprocess

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
    QTextEdit,
    QVBoxLayout,
)

from wired_part.config import Config
from wired_part.database.repository import Repository
from wired_part.utils.constants import LABOR_SUBTASK_CATEGORIES


class _LocationWorker(QThread):
    """Background thread to fetch device GPS coordinates."""

    location_found = Signal(float, float)  # lat, lon
    location_error = Signal(str)           # error message

    def run(self):
        """Try to get location via Windows Location API (PowerShell)."""
        try:
            ps_script = (
                "Add-Type -AssemblyName System.Device; "
                "$w = New-Object System.Device.Location.GeoCoordinateWatcher; "
                "$w.Start(); "
                "$timeout = 10; $elapsed = 0; "
                "while ($w.Status -ne 'Ready' -and $elapsed -lt $timeout) "
                "{ Start-Sleep -Milliseconds 500; $elapsed += 0.5 }; "
                "if ($w.Status -eq 'Ready') { "
                "$c = $w.Position.Location; "
                "Write-Output \"$($c.Latitude),$($c.Longitude)\" } "
                "else { Write-Output 'FAILED' }; "
                "$w.Stop()"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True, text=True, timeout=15,
            )
            # Strip ANSI / VS Code terminal escape sequences that
            # can leak into subprocess stdout (e.g. \x1b]633;…\x07)
            raw = result.stdout
            output = re.sub(
                r"\x1b\].*?\x07"   # OSC sequences (VS Code terminal)
                r"|\x1b\[[0-9;]*[A-Za-z]"  # CSI sequences
                r"|\x1b[^[\]].?",  # Other ESC sequences
                "", raw,
            ).strip()
            if output and output != "FAILED" and "," in output:
                parts = output.split(",")
                lat = float(parts[0])
                lon = float(parts[1])
                self.location_found.emit(lat, lon)
            else:
                self.location_error.emit(
                    "Location unavailable. Enable Location Services "
                    "in Windows Settings > Privacy > Location."
                )
        except subprocess.TimeoutExpired:
            self.location_error.emit(
                "Location request timed out. Enable Location Services "
                "in Windows Settings."
            )
        except Exception as e:
            self.location_error.emit(
                f"Could not get location: {e}\n"
                "You can paste coordinates manually from Google Maps."
            )


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


class ClockInDialog(QDialog):
    """Dialog for clocking in to a job."""

    def __init__(self, repo: Repository, user_id: int,
                 job_id: int = None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.user_id = user_id
        self.result_entry_id = None
        self._loc_worker = None
        self.setWindowTitle("Clock In")
        self.setMinimumWidth(440)
        self._setup_ui()
        if job_id:
            idx = self.job_selector.findData(job_id)
            if idx >= 0:
                self.job_selector.setCurrentIndex(idx)
        # Auto-detect GPS on open
        self._auto_detect_location()

    def closeEvent(self, event):
        """Ensure GPS thread is stopped before closing."""
        if self._loc_worker and self._loc_worker.isRunning():
            self._loc_worker.quit()
            self._loc_worker.wait(2000)
        super().closeEvent(event)

    def reject(self):
        """Ensure GPS thread is stopped on cancel."""
        if self._loc_worker and self._loc_worker.isRunning():
            self._loc_worker.quit()
            self._loc_worker.wait(2000)
        super().reject()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        # Job selector
        self.job_selector = QComboBox()
        self.job_selector.addItem("— Select a job —", None)
        for job in self.repo.get_all_jobs("active"):
            self.job_selector.addItem(
                f"{job.job_number} — {job.name}", job.id
            )
        self.job_selector.currentIndexChanged.connect(self._on_job_changed)
        form.addRow("Job:", self.job_selector)

        # Category
        self.category_selector = QComboBox()
        for cat in LABOR_SUBTASK_CATEGORIES:
            self.category_selector.addItem(cat)
        form.addRow("Task Category:", self.category_selector)

        layout.addLayout(form)

        # Photo section (optional at clock-in — required at clock-out)
        self.photos = _PhotoSection(
            "Photos (optional)", required=False, parent=self
        )
        layout.addWidget(self.photos)

        # GPS section
        gps_group = QGroupBox("GPS Location")
        gps_layout = QFormLayout()

        self.lat_input = QLineEdit()
        self.lat_input.setPlaceholderText("e.g. 40.7128")
        gps_layout.addRow("Latitude:", self.lat_input)

        self.lon_input = QLineEdit()
        self.lon_input.setPlaceholderText("e.g. -74.0060")
        gps_layout.addRow("Longitude:", self.lon_input)

        self.locate_btn = QPushButton("Get My Location")
        self.locate_btn.setToolTip(
            "Auto-detect your GPS location using Windows Location Services"
        )
        self.locate_btn.clicked.connect(self._on_get_location)
        gps_layout.addRow("", self.locate_btn)

        self.proximity_label = QLabel("")
        self.proximity_label.setWordWrap(True)
        gps_layout.addRow("", self.proximity_label)

        # Trigger proximity check when GPS values change
        self.lat_input.textChanged.connect(self._check_proximity)
        self.lon_input.textChanged.connect(self._check_proximity)

        gps_group.setLayout(gps_layout)
        layout.addWidget(gps_group)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Ok).setText("Clock In")
        buttons.accepted.connect(self._on_clock_in)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _auto_detect_location(self):
        """Try to auto-detect GPS location in background."""
        self.proximity_label.setText("Detecting location...")
        self.proximity_label.setStyleSheet("color: #fab387;")
        self.locate_btn.setEnabled(False)

        self._loc_worker = _LocationWorker()
        self._loc_worker.location_found.connect(self._on_location_found)
        self._loc_worker.location_error.connect(self._on_location_error)
        self._loc_worker.start()

    def _on_get_location(self):
        """Manually trigger GPS detection."""
        self._auto_detect_location()

    def _on_location_found(self, lat: float, lon: float):
        """GPS location was found — fill in the fields."""
        self.lat_input.setText(f"{lat:.6f}")
        self.lon_input.setText(f"{lon:.6f}")
        self.locate_btn.setEnabled(True)
        self.proximity_label.setText(
            f"Location detected: {lat:.4f}, {lon:.4f}"
        )
        self.proximity_label.setStyleSheet("color: #a6e3a1;")

    def _on_location_error(self, error: str):
        """GPS detection failed — user can enter manually."""
        self.locate_btn.setEnabled(True)
        self.proximity_label.setText(error)
        self.proximity_label.setStyleSheet("color: #a6adc8;")

    def _on_job_changed(self):
        """Check proximity when job changes and GPS is entered."""
        self._check_proximity()

    def _check_proximity(self):
        """Check GPS proximity to job site if coords are provided."""
        job_id = self.job_selector.currentData()
        lat_text = self.lat_input.text().strip()
        lon_text = self.lon_input.text().strip()

        if not job_id or not lat_text or not lon_text:
            return

        try:
            lat = float(lat_text)
            lon = float(lon_text)
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
            pass  # Still typing coordinates

    def _on_clock_in(self):
        """Validate and create clock-in entry."""
        job_id = self.job_selector.currentData()
        if not job_id:
            QMessageBox.warning(
                self, "Validation", "Please select a job."
            )
            return

        # Photos are optional at clock-in (required at clock-out)

        # Check for active clock-in
        active = self.repo.get_active_clock_in(self.user_id)
        if active:
            QMessageBox.warning(
                self, "Already Clocked In",
                f"You are already clocked in to job "
                f"{active.job_number or 'unknown'}.\n"
                "Please clock out first.",
            )
            return

        # Parse optional GPS
        lat = None
        lon = None
        lat_text = self.lat_input.text().strip()
        lon_text = self.lon_input.text().strip()
        if lat_text and lon_text:
            try:
                lat = float(lat_text)
                lon = float(lon_text)
            except ValueError:
                QMessageBox.warning(
                    self, "Invalid GPS",
                    "GPS coordinates must be valid numbers.",
                )
                return

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


class ClockOutDialog(QDialog):
    """Dialog for clocking out from an active labor entry."""

    def __init__(self, repo: Repository, entry_id: int, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.entry_id = entry_id
        self._loc_worker = None
        self.setWindowTitle("Clock Out")
        self.setMinimumWidth(440)

        entry = self.repo.get_labor_entry_by_id(entry_id)
        self.entry = entry
        self._setup_ui()
        # Auto-detect GPS on open
        self._auto_detect_location()

    def closeEvent(self, event):
        """Ensure GPS thread is stopped before closing."""
        if self._loc_worker and self._loc_worker.isRunning():
            self._loc_worker.quit()
            self._loc_worker.wait(2000)
        super().closeEvent(event)

    def reject(self):
        """Ensure GPS thread is stopped on cancel."""
        if self._loc_worker and self._loc_worker.isRunning():
            self._loc_worker.quit()
            self._loc_worker.wait(2000)
        super().reject()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Show current clock-in info
        if self.entry:
            info = QLabel(
                f"<b>Job:</b> {self.entry.job_number or 'N/A'}<br>"
                f"<b>Category:</b> {self.entry.sub_task_category}<br>"
                f"<b>Clocked In:</b> {self.entry.start_time}"
            )
            info.setWordWrap(True)
            layout.addWidget(info)

        form = QFormLayout()

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText(
            "Describe the work performed..."
        )
        self.description_input.setMaximumHeight(100)
        form.addRow("Work Description:", self.description_input)

        self.overtime_check = QCheckBox("Mark as overtime")
        form.addRow("", self.overtime_check)

        layout.addLayout(form)

        # Photo section (required)
        self.photos = _PhotoSection(
            "Photos (required)", required=True, parent=self
        )
        layout.addWidget(self.photos)

        # GPS section
        gps_group = QGroupBox("GPS Location")
        gps_layout = QFormLayout()

        self.lat_input = QLineEdit()
        self.lat_input.setPlaceholderText("e.g. 40.7128")
        gps_layout.addRow("Latitude:", self.lat_input)

        self.lon_input = QLineEdit()
        self.lon_input.setPlaceholderText("e.g. -74.0060")
        gps_layout.addRow("Longitude:", self.lon_input)

        self.locate_btn = QPushButton("Get My Location")
        self.locate_btn.setToolTip(
            "Auto-detect your GPS location using Windows Location Services"
        )
        self.locate_btn.clicked.connect(self._on_get_location)
        gps_layout.addRow("", self.locate_btn)

        self.gps_status_label = QLabel("")
        self.gps_status_label.setWordWrap(True)
        gps_layout.addRow("", self.gps_status_label)

        gps_group.setLayout(gps_layout)
        layout.addWidget(gps_group)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Ok).setText("Clock Out")
        buttons.accepted.connect(self._on_clock_out)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _auto_detect_location(self):
        """Try to auto-detect GPS location in background."""
        self.gps_status_label.setText("Detecting location...")
        self.gps_status_label.setStyleSheet("color: #fab387;")
        self.locate_btn.setEnabled(False)

        self._loc_worker = _LocationWorker()
        self._loc_worker.location_found.connect(self._on_location_found)
        self._loc_worker.location_error.connect(self._on_location_error)
        self._loc_worker.start()

    def _on_get_location(self):
        """Manually trigger GPS detection."""
        self._auto_detect_location()

    def _on_location_found(self, lat: float, lon: float):
        """GPS location was found — fill in the fields."""
        self.lat_input.setText(f"{lat:.6f}")
        self.lon_input.setText(f"{lon:.6f}")
        self.locate_btn.setEnabled(True)
        self.gps_status_label.setText(
            f"Location detected: {lat:.4f}, {lon:.4f}"
        )
        self.gps_status_label.setStyleSheet("color: #a6e3a1;")

    def _on_location_error(self, error: str):
        """GPS detection failed — user can enter manually."""
        self.locate_btn.setEnabled(True)
        self.gps_status_label.setText(error)
        self.gps_status_label.setStyleSheet("color: #a6adc8;")

    def _on_clock_out(self):
        """Process clock-out."""
        # Check photo requirement
        if not self.photos.has_minimum():
            QMessageBox.warning(
                self, "Photo Required",
                "Please attach at least one photo before clocking out.",
            )
            return

        lat = None
        lon = None
        lat_text = self.lat_input.text().strip()
        lon_text = self.lon_input.text().strip()
        if lat_text and lon_text:
            try:
                lat = float(lat_text)
                lon = float(lon_text)
            except ValueError:
                QMessageBox.warning(
                    self, "Invalid GPS",
                    "GPS coordinates must be valid numbers.",
                )
                return

        # Copy photos to storage
        stored_photos = self.photos.copy_photos_to_storage()
        photos_json = json.dumps(stored_photos) if stored_photos else None

        try:
            result = self.repo.clock_out(
                self.entry_id,
                lat=lat,
                lon=lon,
                description=self.description_input.toPlainText().strip(),
            )

            # Update overtime flag and photos
            if result:
                if self.overtime_check.isChecked():
                    result.is_overtime = 1
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
                    f"Hours worked: {result.hours:.2f}",
                )
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "Clock Out Error", str(e))
