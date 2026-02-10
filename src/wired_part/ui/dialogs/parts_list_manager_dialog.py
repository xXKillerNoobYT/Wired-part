"""Parts List Manager — browse, create, edit, and delete parts lists."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.models import PartsList
from wired_part.database.repository import Repository
from wired_part.utils.formatters import format_currency


class PartsListManagerDialog(QDialog):
    """Full parts list browser: lists on left, items on right."""

    LIST_COLUMNS = ["Name", "Type", "Job", "Items", "Created By"]
    ITEM_COLUMNS = ["Part #", "Description", "Qty", "Unit Cost", "Line Total"]

    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.setWindowTitle("Parts Lists Manager")
        self.resize(1000, 600)
        self._lists: list[PartsList] = []
        self._setup_ui()
        self._refresh_lists()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Top toolbar ───────────────────────────────────────────
        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("Filter:"))
        self.type_filter = QComboBox()
        self.type_filter.addItem("All Types", None)
        self.type_filter.addItem("General", "general")
        self.type_filter.addItem("Job-Specific", "specific")
        self.type_filter.addItem("Fast / Quick Pick", "fast")
        self.type_filter.currentIndexChanged.connect(self._refresh_lists)
        toolbar.addWidget(self.type_filter)

        toolbar.addStretch()

        new_btn = QPushButton("+ New List")
        new_btn.clicked.connect(self._on_new_list)
        toolbar.addWidget(new_btn)

        edit_btn = QPushButton("Edit List")
        edit_btn.clicked.connect(self._on_edit_list)
        toolbar.addWidget(edit_btn)
        self.edit_btn = edit_btn

        delete_btn = QPushButton("Delete List")
        delete_btn.clicked.connect(self._on_delete_list)
        toolbar.addWidget(delete_btn)
        self.delete_btn = delete_btn

        layout.addLayout(toolbar)

        # ── Splitter: lists table | items table ───────────────────
        splitter = QSplitter(Qt.Horizontal)

        # Left: lists table
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("Parts Lists"))
        self.lists_table = QTableWidget()
        self.lists_table.setColumnCount(len(self.LIST_COLUMNS))
        self.lists_table.setHorizontalHeaderLabels(self.LIST_COLUMNS)
        self.lists_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.lists_table.setSelectionMode(QTableWidget.SingleSelection)
        self.lists_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.lists_table.setAlternatingRowColors(True)
        self.lists_table.horizontalHeader().setStretchLastSection(True)
        self.lists_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )
        self.lists_table.selectionModel().selectionChanged.connect(
            self._on_list_selected
        )
        self.lists_table.doubleClicked.connect(self._on_manage_items)
        left_layout.addWidget(self.lists_table)

        manage_btn = QPushButton("Manage Items...")
        manage_btn.clicked.connect(self._on_manage_items)
        left_layout.addWidget(manage_btn)
        self.manage_btn = manage_btn

        splitter.addWidget(left)

        # Right: items preview
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.items_header = QLabel("Items Preview")
        right_layout.addWidget(self.items_header)

        self.items_table = QTableWidget()
        self.items_table.setColumnCount(len(self.ITEM_COLUMNS))
        self.items_table.setHorizontalHeaderLabels(self.ITEM_COLUMNS)
        self.items_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.items_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.items_table.setAlternatingRowColors(True)
        self.items_table.horizontalHeader().setStretchLastSection(True)
        self.items_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        right_layout.addWidget(self.items_table)

        self.items_total_label = QLabel("")
        self.items_total_label.setStyleSheet(
            "font-weight: bold; font-size: 13px;"
        )
        right_layout.addWidget(self.items_total_label)

        splitter.addWidget(right)
        splitter.setSizes([400, 600])
        layout.addWidget(splitter, 1)

        # ── Bottom bar ────────────────────────────────────────────
        bottom = QHBoxLayout()
        bottom.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

        # Initial button states
        self.edit_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.manage_btn.setEnabled(False)

    def _refresh_lists(self):
        """Reload the lists table from the database."""
        list_type = self.type_filter.currentData()
        if list_type:
            self._lists = self.repo.get_all_parts_lists(list_type=list_type)
        else:
            self._lists = self.repo.get_all_parts_lists()

        self.lists_table.setRowCount(len(self._lists))
        for row, pl in enumerate(self._lists):
            # Get item count for this list
            items = self.repo.get_parts_list_items(pl.id)
            item_count = len(items)

            type_label = {
                "general": "General",
                "specific": "Job-Specific",
                "fast": "Fast",
            }.get(pl.list_type, pl.list_type)

            cells = [
                QTableWidgetItem(pl.name),
                QTableWidgetItem(type_label),
                QTableWidgetItem(pl.job_number or "—"),
                QTableWidgetItem(str(item_count)),
                QTableWidgetItem(pl.created_by_name or "—"),
            ]
            for col, cell in enumerate(cells):
                if col == 3:  # Right-align item count
                    cell.setTextAlignment(Qt.AlignCenter)
                self.lists_table.setItem(row, col, cell)

        # Clear items preview
        self.items_table.setRowCount(0)
        self.items_header.setText("Items Preview")
        self.items_total_label.setText("")
        self.edit_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.manage_btn.setEnabled(False)

    def _selected_list(self) -> PartsList | None:
        """Return the currently selected parts list, or None."""
        rows = self.lists_table.selectionModel().selectedRows()
        if rows:
            return self._lists[rows[0].row()]
        return None

    def _on_list_selected(self):
        """When a list is selected, show its items preview."""
        pl = self._selected_list()
        has_selection = pl is not None
        self.edit_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)
        self.manage_btn.setEnabled(has_selection)

        if not pl:
            self.items_table.setRowCount(0)
            self.items_header.setText("Items Preview")
            self.items_total_label.setText("")
            return

        self.items_header.setText(f"Items in: {pl.name}")
        items = self.repo.get_parts_list_items(pl.id)
        self.items_table.setRowCount(len(items))
        total = 0.0
        for row, item in enumerate(items):
            line_total = item.quantity * item.unit_cost
            total += line_total
            cells = [
                QTableWidgetItem(item.part_number),
                QTableWidgetItem(item.part_description),
                QTableWidgetItem(str(item.quantity)),
                QTableWidgetItem(format_currency(item.unit_cost)),
                QTableWidgetItem(format_currency(line_total)),
            ]
            for col, cell in enumerate(cells):
                if col in (2, 3, 4):
                    cell.setTextAlignment(
                        Qt.AlignRight | Qt.AlignVCenter
                    )
                self.items_table.setItem(row, col, cell)

        count = len(items)
        self.items_total_label.setText(
            f"{count} item{'s' if count != 1 else ''} — "
            f"Total: {format_currency(total)}"
        )

    def _on_new_list(self):
        """Create a new parts list."""
        from wired_part.ui.dialogs.parts_list_dialog import PartsListDialog
        dialog = PartsListDialog(self.repo, parent=self)
        if dialog.exec():
            self._refresh_lists()

    def _on_edit_list(self):
        """Edit the selected parts list."""
        pl = self._selected_list()
        if not pl:
            return
        # Re-fetch full data
        full_pl = self.repo.get_parts_list_by_id(pl.id)
        if not full_pl:
            return
        from wired_part.ui.dialogs.parts_list_dialog import PartsListDialog
        dialog = PartsListDialog(self.repo, parts_list=full_pl, parent=self)
        if dialog.exec():
            self._refresh_lists()

    def _on_delete_list(self):
        """Delete the selected parts list."""
        pl = self._selected_list()
        if not pl:
            return
        reply = QMessageBox.question(
            self, "Delete Parts List",
            f"Delete '{pl.name}' and all its items?\n"
            "This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.repo.delete_parts_list(pl.id)
            self._refresh_lists()

    def _on_manage_items(self):
        """Open the items management dialog for the selected list."""
        pl = self._selected_list()
        if not pl:
            return
        from wired_part.ui.dialogs.parts_list_items_dialog import (
            PartsListItemsDialog,
        )
        dialog = PartsListItemsDialog(
            self.repo, pl.id, list_name=pl.name, parent=self
        )
        dialog.exec()
        # Refresh to update item counts
        self._refresh_lists()
        # Re-select the same list to update preview
        for i, lst in enumerate(self._lists):
            if lst.id == pl.id:
                self.lists_table.selectRow(i)
                break
