"""Create / Edit parts list dialog."""

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

from wired_part.database.models import PartsList
from wired_part.database.repository import Repository


class PartsListDialog(QDialog):
    """Dialog for creating or editing a parts list."""

    LIST_TYPES = [
        ("general", "General"),
        ("specific", "Job-Specific"),
        ("fast", "Fast / Quick Pick"),
    ]

    def __init__(
        self,
        repo: Repository,
        parts_list: Optional[PartsList] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.repo = repo
        self.parts_list = parts_list
        self.setWindowTitle(
            "Edit Parts List" if parts_list else "New Parts List"
        )
        self.setMinimumWidth(420)
        self._setup_ui()
        if parts_list:
            self._populate(parts_list)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setMaxLength(100)
        self.name_input.setPlaceholderText("e.g. Kitchen Remodel Parts")
        form.addRow("List Name:", self.name_input)

        self.type_input = QComboBox()
        for value, label in self.LIST_TYPES:
            self.type_input.addItem(label, value)
        form.addRow("Type:", self.type_input)

        self.job_input = QComboBox()
        self.job_input.addItem("(None — general list)", None)
        for job in self.repo.get_all_jobs():
            self.job_input.addItem(
                f"{job.job_number} — {job.name}", job.id
            )
        form.addRow("Job:", self.job_input)

        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(80)
        self.notes_input.setPlaceholderText("Optional notes about this list")
        form.addRow("Notes:", self.notes_input)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self, pl: PartsList):
        """Fill fields from an existing parts list."""
        self.name_input.setText(pl.name)
        idx = self.type_input.findData(pl.list_type)
        if idx >= 0:
            self.type_input.setCurrentIndex(idx)
        if pl.job_id is not None:
            jidx = self.job_input.findData(pl.job_id)
            if jidx >= 0:
                self.job_input.setCurrentIndex(jidx)
        self.notes_input.setPlainText(pl.notes or "")

    def _on_save(self):
        """Validate and save the parts list."""
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "List name is required.")
            return

        data = PartsList(
            id=self.parts_list.id if self.parts_list else None,
            name=name,
            list_type=self.type_input.currentData(),
            job_id=self.job_input.currentData(),
            notes=self.notes_input.toPlainText().strip(),
            created_by=self.parts_list.created_by
            if self.parts_list else None,
        )

        if self.parts_list:
            self.repo.update_parts_list(data)
        else:
            self.repo.create_parts_list(data)

        self.accept()
