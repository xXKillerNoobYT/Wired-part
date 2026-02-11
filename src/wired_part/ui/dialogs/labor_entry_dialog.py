"""Manual labor entry dialog — add/edit labor entries with full details."""

from datetime import datetime
from typing import Optional

from PySide6.QtCore import QDate, QTime, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
)

from wired_part.database.models import LaborEntry
from wired_part.database.repository import Repository
from wired_part.utils.constants import LABOR_SUBTASK_CATEGORIES


class LaborEntryDialog(QDialog):
    """Dialog for manually creating or editing a labor entry."""

    def __init__(
        self,
        repo: Repository,
        user_id: int = None,
        job_id: int = None,
        entry: Optional[LaborEntry] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.repo = repo
        self.user_id = user_id
        self.entry = entry
        self.setWindowTitle(
            "Edit Labor Entry" if entry else "Add Labor Entry"
        )
        self.setMinimumWidth(450)
        self._setup_ui()
        if entry:
            self._populate(entry)
        elif job_id:
            idx = self.job_selector.findData(job_id)
            if idx >= 0:
                self.job_selector.setCurrentIndex(idx)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Job
        self.job_selector = QComboBox()
        self.job_selector.addItem("— Select a job —", None)
        for job in self.repo.get_all_jobs():
            self.job_selector.addItem(
                f"{job.job_number} — {job.name}", job.id
            )
        form.addRow("Job:", self.job_selector)

        # Date
        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        form.addRow("Date:", self.date_input)

        # Start time
        self.start_time_input = QTimeEdit()
        self.start_time_input.setDisplayFormat("HH:mm")
        self.start_time_input.setTime(QTime(7, 0))
        form.addRow("Start Time:", self.start_time_input)

        # End time
        self.end_time_input = QTimeEdit()
        self.end_time_input.setDisplayFormat("HH:mm")
        self.end_time_input.setTime(QTime(15, 30))
        form.addRow("End Time:", self.end_time_input)

        # Hours (auto-calculated or manual)
        self.hours_input = QDoubleSpinBox()
        self.hours_input.setRange(0, 24)
        self.hours_input.setDecimals(2)
        self.hours_input.setValue(8.5)
        self.hours_input.setSuffix(" hrs")
        form.addRow("Hours:", self.hours_input)

        # Auto-calculate hours when times change
        self.start_time_input.timeChanged.connect(self._calc_hours)
        self.end_time_input.timeChanged.connect(self._calc_hours)

        # Category
        self.category_selector = QComboBox()
        for cat in LABOR_SUBTASK_CATEGORIES:
            self.category_selector.addItem(cat)
        form.addRow("Category:", self.category_selector)

        # Overtime
        self.overtime_check = QCheckBox("Overtime")
        form.addRow("", self.overtime_check)

        # Description
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText(
            "Describe the work performed..."
        )
        self.description_input.setMaximumHeight(80)
        form.addRow("Description:", self.description_input)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _calc_hours(self):
        """Auto-calculate hours from start/end times."""
        start = self.start_time_input.time()
        end = self.end_time_input.time()
        start_secs = start.hour() * 3600 + start.minute() * 60
        end_secs = end.hour() * 3600 + end.minute() * 60
        if end_secs > start_secs:
            hours = (end_secs - start_secs) / 3600.0
            self.hours_input.setValue(round(hours, 2))

    def _populate(self, entry: LaborEntry):
        """Fill fields from an existing entry."""
        if entry.job_id:
            idx = self.job_selector.findData(entry.job_id)
            if idx >= 0:
                self.job_selector.setCurrentIndex(idx)

        if entry.start_time:
            try:
                dt = datetime.fromisoformat(str(entry.start_time))
                self.date_input.setDate(
                    QDate(dt.year, dt.month, dt.day)
                )
                self.start_time_input.setTime(
                    QTime(dt.hour, dt.minute)
                )
            except (ValueError, TypeError):
                pass

        if entry.end_time:
            try:
                dt = datetime.fromisoformat(str(entry.end_time))
                self.end_time_input.setTime(
                    QTime(dt.hour, dt.minute)
                )
            except (ValueError, TypeError):
                pass

        self.hours_input.setValue(entry.hours or 0)
        self.overtime_check.setChecked(bool(entry.is_overtime))
        self.description_input.setPlainText(entry.description or "")

        if entry.sub_task_category:
            idx = self.category_selector.findText(entry.sub_task_category)
            if idx >= 0:
                self.category_selector.setCurrentIndex(idx)

    def _on_save(self):
        """Validate and save the labor entry."""
        job_id = self.job_selector.currentData()
        if not job_id:
            QMessageBox.warning(
                self, "Validation", "Please select a job."
            )
            return

        date = self.date_input.date()
        start = self.start_time_input.time()
        end = self.end_time_input.time()

        start_dt = datetime(
            date.year(), date.month(), date.day(),
            start.hour(), start.minute()
        )
        end_dt = datetime(
            date.year(), date.month(), date.day(),
            end.hour(), end.minute()
        )

        user_id = self.entry.user_id if self.entry else self.user_id

        data = LaborEntry(
            id=self.entry.id if self.entry else None,
            user_id=user_id,
            job_id=job_id,
            start_time=start_dt.isoformat(),
            end_time=end_dt.isoformat(),
            hours=self.hours_input.value(),
            description=self.description_input.toPlainText().strip(),
            sub_task_category=self.category_selector.currentText(),
            is_overtime=1 if self.overtime_check.isChecked() else 0,
        )

        try:
            if self.entry:
                self.repo.update_labor_entry(data)
            else:
                self.repo.create_labor_entry(data)
            self.accept()
        except Exception as e:
            QMessageBox.warning(
                self, "Save Error", f"Failed to save: {e}"
            )
