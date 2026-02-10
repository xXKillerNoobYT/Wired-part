"""Manage items within a parts list — add, view, remove parts."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from wired_part.database.models import PartsListItem
from wired_part.database.repository import Repository
from wired_part.utils.formatters import format_currency


class PartsListItemsDialog(QDialog):
    """Dialog for managing items in a single parts list."""

    COLUMNS = ["Part #", "Description", "Qty", "Unit Cost", "Line Total", "Notes"]

    def __init__(self, repo: Repository, list_id: int, list_name: str = "",
                 parent=None):
        super().__init__(parent)
        self.repo = repo
        self.list_id = list_id
        self.setWindowTitle(f"Parts List: {list_name}" if list_name else "Parts List Items")
        self.resize(750, 500)
        self._items: list[PartsListItem] = []
        self._setup_ui()
        self._refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Add item toolbar ──────────────────────────────────────
        add_layout = QHBoxLayout()
        add_layout.addWidget(QLabel("Add Part:"))

        self.part_selector = QComboBox()
        self.part_selector.setMinimumWidth(250)
        self._load_parts_combo()
        add_layout.addWidget(self.part_selector, 2)

        add_layout.addWidget(QLabel("Qty:"))
        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 99999)
        self.qty_spin.setValue(1)
        add_layout.addWidget(self.qty_spin)

        add_btn = QPushButton("+ Add")
        add_btn.clicked.connect(self._on_add_item)
        add_layout.addWidget(add_btn)

        layout.addLayout(add_layout)

        # ── Items table ───────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        layout.addWidget(self.table, 1)

        # ── Bottom bar ────────────────────────────────────────────
        bottom = QHBoxLayout()

        self.total_label = QLabel("Total: $0.00")
        self.total_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        bottom.addWidget(self.total_label)

        bottom.addStretch()

        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._on_remove_item)
        bottom.addWidget(remove_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)

        layout.addLayout(bottom)

    def _load_parts_combo(self):
        """Populate the part selector with all available parts."""
        self.part_selector.clear()
        self.part_selector.addItem("— Select a part —", None)
        for part in self.repo.get_all_parts():
            self.part_selector.addItem(
                f"{part.part_number} — {part.description}", part.id
            )

    def _refresh(self):
        """Reload items from the database."""
        self._items = self.repo.get_parts_list_items(self.list_id)
        self._populate_table()

    def _populate_table(self):
        """Fill the table with current items."""
        self.table.setRowCount(len(self._items))
        total = 0.0
        for row, item in enumerate(self._items):
            line_total = item.quantity * item.unit_cost
            total += line_total
            cells = [
                QTableWidgetItem(item.part_number),
                QTableWidgetItem(item.part_description),
                QTableWidgetItem(str(item.quantity)),
                QTableWidgetItem(format_currency(item.unit_cost)),
                QTableWidgetItem(format_currency(line_total)),
                QTableWidgetItem(item.notes),
            ]
            for col, cell in enumerate(cells):
                if col in (2, 3, 4):  # Right-align numbers
                    cell.setTextAlignment(
                        Qt.AlignRight | Qt.AlignVCenter
                    )
                self.table.setItem(row, col, cell)

        self.total_label.setText(f"Total: {format_currency(total)}")

    def _on_add_item(self):
        """Add selected part to the list."""
        part_id = self.part_selector.currentData()
        if part_id is None:
            QMessageBox.warning(self, "Select Part", "Please select a part to add.")
            return

        # Check if already in list
        for existing in self._items:
            if existing.part_id == part_id:
                QMessageBox.information(
                    self, "Already Added",
                    "This part is already in the list. "
                    "Remove and re-add to change quantity.",
                )
                return

        item = PartsListItem(
            list_id=self.list_id,
            part_id=part_id,
            quantity=self.qty_spin.value(),
        )
        self.repo.add_item_to_parts_list(item)
        self.qty_spin.setValue(1)
        self.part_selector.setCurrentIndex(0)
        self._refresh()

    def _on_remove_item(self):
        """Remove the selected item from the list."""
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(
                self, "No Selection", "Select an item to remove."
            )
            return

        item = self._items[rows[0].row()]
        reply = QMessageBox.question(
            self, "Remove Item",
            f"Remove '{item.part_number}' from this list?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.repo.remove_item_from_parts_list(item.id)
            self._refresh()
