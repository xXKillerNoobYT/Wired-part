"""Part picker dialog — search and select a part from the catalog."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from wired_part.database.models import Part
from wired_part.database.repository import Repository


class PartPickerDialog(QDialog):
    """Simple dialog to search for and select a single part."""

    COLUMNS = ["Part #", "Description", "Qty", "Location", "Category"]

    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.selected_part: Part | None = None
        self._parts: list[Part] = []

        self.setWindowTitle("Select Part")
        self.setMinimumSize(600, 400)
        self._setup_ui()
        self._load_parts()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Search
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to search parts...")
        self.search_input.textChanged.connect(self._on_search)
        search_layout.addWidget(self.search_input, 1)
        layout.addLayout(search_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch,
        )
        self.table.doubleClicked.connect(self.accept)
        layout.addWidget(self.table, 1)

        # Buttons
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _load_parts(self):
        """Load all parts from the catalog."""
        self._parts = self.repo.get_all_parts()
        self._populate_table(self._parts)

    def _on_search(self):
        """Filter parts by search text."""
        search = self.search_input.text().strip().lower()
        if search:
            filtered = [
                p for p in self._parts
                if search in p.part_number.lower()
                or search in (p.description or "").lower()
                or search in (p.name or "").lower()
            ]
        else:
            filtered = self._parts
        self._populate_table(filtered)

    def _populate_table(self, parts: list[Part]):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(parts))
        for row, part in enumerate(parts):
            cells = [
                QTableWidgetItem(part.part_number),
                QTableWidgetItem(part.description or part.name),
                QTableWidgetItem(str(part.quantity)),
                QTableWidgetItem(part.location),
                QTableWidgetItem(part.category_name),
            ]
            for col, cell in enumerate(cells):
                self.table.setItem(row, col, cell)
        self.table.setSortingEnabled(True)

    def accept(self):
        """Store the selected part and close."""
        rows = self.table.selectionModel().selectedRows()
        if rows:
            pn = self.table.item(rows[0].row(), 0).text()
            for part in self._parts:
                if part.part_number == pn:
                    self.selected_part = part
                    break
        super().accept()
