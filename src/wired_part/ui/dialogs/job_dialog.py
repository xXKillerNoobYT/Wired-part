"""Add / Edit Job dialog with GPS location support."""

import re
import subprocess
from typing import Optional

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from wired_part.config import Config
from wired_part.database.models import Job
from wired_part.database.repository import Repository
from wired_part.utils.constants import JOB_STATUSES


class _JobLocationWorker(QThread):
    """Background thread to fetch device GPS for job location."""

    location_found = Signal(float, float)
    location_error = Signal(str)

    def run(self):
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
            # Strip ANSI / VS Code terminal escape sequences
            raw = result.stdout
            output = re.sub(
                r"\x1b\].*?\x07"
                r"|\x1b\[[0-9;]*[A-Za-z]"
                r"|\x1b[^[\]].?",
                "", raw,
            ).strip()
            if output and output != "FAILED" and "," in output:
                parts = output.split(",")
                self.location_found.emit(float(parts[0]), float(parts[1]))
            else:
                self.location_error.emit("Location unavailable.")
        except Exception as e:
            self.location_error.emit(f"Could not get location: {e}")


class JobDialog(QDialog):
    """Dialog for creating or editing a job."""

    def __init__(
        self,
        repo: Repository,
        job: Optional[Job] = None,
        parent=None,
        show_bro: bool = True,
    ):
        super().__init__(parent)
        self.repo = repo
        self.job = job
        self._show_bro = show_bro
        self.setWindowTitle("Edit Job" if job else "New Job")
        self.setMinimumWidth(460)
        self._setup_ui()
        if job:
            self._populate(job)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.job_number_input = QLineEdit()
        self.job_number_input.setMaxLength(20)
        if not self.job:
            self.job_number_input.setText(self.repo.generate_job_number())
            self.job_number_input.setReadOnly(True)
        form.addRow("Job Number:", self.job_number_input)

        self.name_input = QLineEdit()
        self.name_input.setMaxLength(100)
        form.addRow("Job Name:", self.name_input)

        self.customer_input = QLineEdit()
        self.customer_input.setMaxLength(100)
        form.addRow("Customer:", self.customer_input)

        self.address_input = QLineEdit()
        self.address_input.setMaxLength(200)
        form.addRow("Address:", self.address_input)

        self.status_input = QComboBox()
        for s in JOB_STATUSES:
            self.status_input.addItem(s.title(), s)
        form.addRow("Status:", self.status_input)

        self.priority_input = QSpinBox()
        self.priority_input.setRange(1, 5)
        self.priority_input.setValue(3)
        self.priority_input.setToolTip(
            "1 = Highest priority, 5 = Lowest priority"
        )
        self.priority_input.setSuffix(
            "  (1=Highest, 5=Lowest)"
        )
        form.addRow("Priority:", self.priority_input)

        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(80)
        form.addRow("Notes:", self.notes_input)

        self.bro_combo = QComboBox()
        self.bro_combo.setEditable(False)
        self.bro_combo.setToolTip(
            "Bill Out Rate category — bookkeeper classification "
            "(e.g. C, T&M, SERVICE, EMERGENCY)"
        )
        self.bro_combo.addItem("(None)", "")
        for cat in Config.get_bro_categories():
            self.bro_combo.addItem(cat, cat)
        if self._show_bro:
            form.addRow("BRO:", self.bro_combo)
        else:
            self.bro_combo.setVisible(False)

        layout.addLayout(form)

        # ── GPS Job Site Location ────────────────────────────────
        gps_group = QGroupBox("Job Site GPS Location")
        gps_layout = QFormLayout()

        self.lat_input = QLineEdit()
        self.lat_input.setPlaceholderText("e.g. 40.7128")
        self.lat_input.setToolTip(
            "GPS latitude of the job site. Used for clock-in/out "
            "proximity verification."
        )
        gps_layout.addRow("Latitude:", self.lat_input)

        self.lon_input = QLineEdit()
        self.lon_input.setPlaceholderText("e.g. -74.0060")
        self.lon_input.setToolTip(
            "GPS longitude of the job site. Used for clock-in/out "
            "proximity verification."
        )
        gps_layout.addRow("Longitude:", self.lon_input)

        self.locate_btn = QPushButton("Use My Current Location")
        self.locate_btn.setToolTip(
            "Set the job site GPS to your current device location"
        )
        self.locate_btn.clicked.connect(self._on_get_location)
        gps_layout.addRow("", self.locate_btn)

        self.gps_status = QLabel("")
        gps_layout.addRow("", self.gps_status)

        gps_group.setLayout(gps_layout)
        layout.addWidget(gps_group)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self, job: Job):
        self.job_number_input.setText(job.job_number)
        self.name_input.setText(job.name)
        self.customer_input.setText(job.customer or "")
        self.address_input.setText(job.address or "")
        self.notes_input.setPlainText(job.notes or "")
        idx = self.status_input.findData(job.status)
        if idx >= 0:
            self.status_input.setCurrentIndex(idx)
        self.priority_input.setValue(job.priority or 3)
        bro_idx = self.bro_combo.findData(job.bill_out_rate or "")
        if bro_idx >= 0:
            self.bro_combo.setCurrentIndex(bro_idx)
        else:
            # Value not in current list — add it so it's not lost
            if job.bill_out_rate:
                self.bro_combo.addItem(job.bill_out_rate, job.bill_out_rate)
                self.bro_combo.setCurrentIndex(self.bro_combo.count() - 1)

        # Load existing GPS location
        location = self.repo.get_job_location(job.id)
        if location:
            self.lat_input.setText(str(location.latitude))
            self.lon_input.setText(str(location.longitude))

    def _on_get_location(self):
        """Detect current GPS to set as job site location."""
        self.locate_btn.setEnabled(False)
        self.gps_status.setText("Detecting location...")
        self.gps_status.setStyleSheet("color: #fab387;")

        self._loc_worker = _JobLocationWorker()
        self._loc_worker.location_found.connect(self._on_location_found)
        self._loc_worker.location_error.connect(self._on_location_error)
        self._loc_worker.start()

    def _on_location_found(self, lat: float, lon: float):
        self.lat_input.setText(f"{lat:.6f}")
        self.lon_input.setText(f"{lon:.6f}")
        self.locate_btn.setEnabled(True)
        self.gps_status.setText(f"Location set: {lat:.4f}, {lon:.4f}")
        self.gps_status.setStyleSheet("color: #a6e3a1;")

    def _on_location_error(self, error: str):
        self.locate_btn.setEnabled(True)
        self.gps_status.setText(error)
        self.gps_status.setStyleSheet("color: #a6adc8;")

    def _on_save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Job name is required.")
            return

        data = Job(
            id=self.job.id if self.job else None,
            job_number=self.job_number_input.text().strip(),
            name=name,
            customer=self.customer_input.text().strip(),
            address=self.address_input.text().strip(),
            status=self.status_input.currentData(),
            priority=self.priority_input.value(),
            notes=self.notes_input.toPlainText().strip(),
            bill_out_rate=self.bro_combo.currentData() or "",
        )

        if self.job:
            data.completed_at = self.job.completed_at
            self.repo.update_job(data)
            job_id = self.job.id
        else:
            job_id = self.repo.create_job(data)

        # Save GPS location if provided
        lat_text = self.lat_input.text().strip()
        lon_text = self.lon_input.text().strip()
        if lat_text and lon_text:
            try:
                lat = float(lat_text)
                lon = float(lon_text)
                self.repo.set_job_location(
                    job_id, lat, lon,
                    geocoded_address=self.address_input.text().strip(),
                )
            except ValueError:
                pass  # Invalid GPS, skip silently
        elif not lat_text and not lon_text:
            # If GPS was cleared, delete the location
            if self.job:
                self.repo.delete_job_location(self.job.id)

        self.accept()
