"""Assign parts to a job dialog."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from wired_part.database.models import Job, JobPart, Part
from wired_part.database.repository import Repository


class AssignPartsDialog(QDialog):
    """Select parts and quantities to assign to a job."""

    def __init__(self, repo: Repository, job: Job, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.job = job
        self.setWindowTitle(f"Assign Parts to {job.job_number}")
        self.setMinimumSize(600, 400)
        self._parts: list[Part] = []
        self._setup_ui()
        self._load_parts()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(
            QLabel(f"Assigning parts to: {self.job.job_number} — {self.job.name}")
        )

        # Search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search available parts...")
        self.search_input.textChanged.connect(self._load_parts)
        layout.addWidget(self.search_input)

        # Parts table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Part #", "Description", "Available", "Category", "Assign Qty"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        layout.addWidget(self.table)

        # Quantity input
        qty_row = QHBoxLayout()
        qty_row.addWidget(QLabel("Quantity to assign:"))
        self.qty_input = QSpinBox()
        self.qty_input.setRange(1, 999999)
        self.qty_input.setValue(1)
        qty_row.addWidget(self.qty_input)
        qty_row.addStretch()
        layout.addLayout(qty_row)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Ok).setText("Assign")
        buttons.accepted.connect(self._on_assign)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_parts(self):
        """Load available parts (quantity > 0)."""
        search = self.search_input.text().strip()
        if search:
            all_parts = self.repo.search_parts(search)
        else:
            all_parts = self.repo.get_all_parts()

        self._parts = [p for p in all_parts if p.quantity > 0]
        self.table.setRowCount(len(self._parts))

        for row, part in enumerate(self._parts):
            self.table.setItem(row, 0, QTableWidgetItem(part.part_number))
            self.table.setItem(row, 1, QTableWidgetItem(part.description))
            self.table.setItem(row, 2, QTableWidgetItem(str(part.quantity)))
            self.table.setItem(row, 3, QTableWidgetItem(part.category_name))
            self.table.setItem(row, 4, QTableWidgetItem(""))

    def _on_assign(self):
        """Assign the selected part to the job."""
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(
                self, "No Selection", "Select a part to assign."
            )
            return

        part = self._parts[rows[0].row()]
        qty = self.qty_input.value()

        if qty > part.quantity:
            QMessageBox.warning(
                self, "Insufficient Stock",
                f"Only {part.quantity} available. Requested {qty}.",
            )
            return

        try:
            jp = JobPart(
                job_id=self.job.id,
                part_id=part.id,
                quantity_used=qty,
            )
            self.repo.assign_part_to_job(jp)
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
