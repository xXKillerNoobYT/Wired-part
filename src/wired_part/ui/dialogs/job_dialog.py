"""Add / Edit Job dialog."""

from typing import Optional

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
)

from wired_part.database.models import Job
from wired_part.database.repository import Repository
from wired_part.utils.constants import JOB_STATUSES


class JobDialog(QDialog):
    """Dialog for creating or editing a job."""

    def __init__(
        self,
        repo: Repository,
        job: Optional[Job] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.repo = repo
        self.job = job
        self.setWindowTitle("Edit Job" if job else "New Job")
        self.setMinimumWidth(450)
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

        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(80)
        form.addRow("Notes:", self.notes_input)

        layout.addLayout(form)

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
            notes=self.notes_input.toPlainText().strip(),
        )

        if self.job:
            data.completed_at = self.job.completed_at
            self.repo.update_job(data)
        else:
            self.repo.create_job(data)

        self.accept()
