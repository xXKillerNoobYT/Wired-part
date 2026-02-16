"""Inventory management page — parts table with search and CRUD toolbar."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.models import Part, User
from wired_part.database.repository import Repository
from wired_part.utils.formatters import format_currency


class InventoryPage(QWidget):
    """Full inventory view with search, filter, and CRUD actions."""

    COLUMNS = [
        "Part #", "Description", "Qty", "Min", "Location",
        "Category", "Unit Cost", "Supplier",
    ]

    def __init__(self, repo: Repository, current_user: User = None):
        super().__init__()
        self.repo = repo
        self.current_user = current_user
        self._perms: set[str] = set()
        if current_user:
            self._perms = repo.get_user_permissions(current_user.id)
        self._can_see_dollars = "show_dollar_values" in self._perms
        self._parts: list[Part] = []
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Toolbar ─────────────────────────────────────────────
        toolbar = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search parts...")
        self.search_input.textChanged.connect(self._on_search)
        toolbar.addWidget(self.search_input, 2)

        self.category_filter = QComboBox()
        self.category_filter.addItem("All Categories", None)
        self.category_filter.currentIndexChanged.connect(self._on_filter)
        toolbar.addWidget(self.category_filter, 1)

        self.add_btn = QPushButton("+ Add Part")
        self.add_btn.clicked.connect(self._on_add)
        toolbar.addWidget(self.add_btn)

        self.import_btn = QPushButton("Import")
        self.import_btn.clicked.connect(self._on_import)
        toolbar.addWidget(self.import_btn)

        self.export_btn = QPushButton("Export")
        self.export_btn.clicked.connect(self._on_export)
        toolbar.addWidget(self.export_btn)

        self.lists_btn = QPushButton("Parts Lists")
        self.lists_btn.setToolTip("Manage parts lists (general, job-specific, quick pick)")
        self.lists_btn.clicked.connect(self._on_parts_lists)
        toolbar.addWidget(self.lists_btn)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self._on_edit)
        self.edit_btn.setEnabled(False)
        toolbar.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._on_delete)
        self.delete_btn.setEnabled(False)
        toolbar.addWidget(self.delete_btn)

        self.audit_btn = QPushButton("Fast Audit")
        self.audit_btn.setToolTip("Quick card-swipe inventory audit")
        self.audit_btn.clicked.connect(self._on_audit)
        toolbar.addWidget(self.audit_btn)

        # Apply permission visibility
        p = self._perms
        self.add_btn.setVisible("parts_add" in p)
        self.import_btn.setVisible("parts_import" in p)
        self.export_btn.setVisible("parts_export" in p)
        self.lists_btn.setVisible("parts_lists" in p)
        self.edit_btn.setVisible("parts_edit" in p)
        self.delete_btn.setVisible("parts_delete" in p)

        layout.addLayout(toolbar)

        # ── Parts Table ─────────────────────────────────────────
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
        self.table.selectionModel().selectionChanged.connect(
            self._on_selection_changed
        )
        self.table.doubleClicked.connect(self._on_edit)

        layout.addWidget(self.table)

    def refresh(self):
        """Reload all data from the database."""
        self._load_categories()
        self._load_parts()

    def _load_categories(self):
        """Populate the category filter dropdown."""
        current = self.category_filter.currentData()
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("All Categories", None)
        for cat in self.repo.get_all_categories():
            self.category_filter.addItem(cat.name, cat.id)
        # Restore selection
        if current is not None:
            idx = self.category_filter.findData(current)
            if idx >= 0:
                self.category_filter.setCurrentIndex(idx)
        self.category_filter.blockSignals(False)

    def _load_parts(self):
        """Fetch and display parts based on current search/filter."""
        search_text = self.search_input.text().strip()
        category_id = self.category_filter.currentData()

        if search_text:
            self._parts = self.repo.search_parts(search_text)
            if category_id is not None:
                self._parts = [
                    p for p in self._parts if p.category_id == category_id
                ]
        elif category_id is not None:
            self._parts = self.repo.get_parts_by_category(category_id)
        else:
            self._parts = self.repo.get_all_parts()

        self._populate_table()

    def _populate_table(self):
        """Fill the table widget with current parts data."""
        self.table.setRowCount(len(self._parts))
        for row, part in enumerate(self._parts):
            items = [
                QTableWidgetItem(part.part_number),
                QTableWidgetItem(part.description),
                QTableWidgetItem(str(part.quantity)),
                QTableWidgetItem(str(part.min_quantity)),
                QTableWidgetItem(part.location),
                QTableWidgetItem(part.category_name),
                QTableWidgetItem(
                    format_currency(part.unit_cost)
                    if self._can_see_dollars else "—"
                ),
                QTableWidgetItem(part.supplier),
            ]
            # Highlight low stock in red
            if part.is_low_stock:
                for item in items:
                    item.setForeground(Qt.red)

            for col, item in enumerate(items):
                self.table.setItem(row, col, item)

    def _selected_part(self) -> Part | None:
        """Return the currently selected Part, or None."""
        rows = self.table.selectionModel().selectedRows()
        if rows:
            return self._parts[rows[0].row()]
        return None

    def _on_selection_changed(self):
        has_selection = bool(self.table.selectionModel().selectedRows())
        self.edit_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)

    def _on_search(self):
        self._load_parts()

    def _on_filter(self):
        self._load_parts()

    def _on_import(self):
        from wired_part.ui.dialogs.import_dialog import ImportDialog
        dialog = ImportDialog(self.repo, parent=self)
        dialog.exec()
        self.refresh()

    def _on_export(self):
        from wired_part.ui.dialogs.export_dialog import ExportDialog
        dialog = ExportDialog(self.repo, parent=self)
        dialog.exec()

    def _on_parts_lists(self):
        from wired_part.ui.dialogs.parts_list_manager_dialog import (
            PartsListManagerDialog,
        )
        dialog = PartsListManagerDialog(self.repo, parent=self)
        dialog.exec()
        self.refresh()

    def _on_add(self):
        from wired_part.ui.dialogs.part_dialog import PartDialog
        dialog = PartDialog(self.repo, parent=self)
        if dialog.exec():
            self.refresh()

    def _on_edit(self):
        part = self._selected_part()
        if not part:
            return
        from wired_part.ui.dialogs.part_dialog import PartDialog
        dialog = PartDialog(self.repo, part=part, parent=self)
        if dialog.exec():
            self.refresh()

    def _on_audit(self):
        from wired_part.ui.dialogs.audit_dialog import AuditDialog
        dialog = AuditDialog(self.repo, "warehouse", parent=self)
        dialog.exec()
        self.refresh()

    def _on_delete(self):
        part = self._selected_part()
        if not part:
            return

        can_delete, reason = self.repo.can_delete_part(part.id)
        if not can_delete:
            QMessageBox.warning(
                self, "Cannot Delete",
                f"Cannot delete '{part.part_number}':\n{reason}",
            )
            return

        reply = QMessageBox.question(
            self,
            "Delete Part",
            f"Delete '{part.part_number} - {part.description}'?\n"
            "This will also remove associated history records.\n\n"
            "This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                self.repo.delete_part(part.id, force=True)
                self.refresh()
            except Exception as e:
                QMessageBox.warning(
                    self, "Cannot Delete",
                    f"Failed to delete part: {e}",
                )
