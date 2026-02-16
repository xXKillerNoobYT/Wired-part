"""Trucks Inventory page — dynamic sub-tabs per truck showing on-hand parts."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.repository import Repository
from wired_part.utils.formatters import format_currency


class _TruckInventoryTab(QWidget):
    """Single truck's inventory view with search and part table."""

    COLUMNS = [
        "Part #", "Description", "Qty On Hand", "Unit Cost", "Total Value",
    ]

    def __init__(self, repo: Repository, truck_id: int, truck_label: str,
                 can_see_dollars: bool = True):
        super().__init__()
        self.repo = repo
        self.truck_id = truck_id
        self.truck_label = truck_label
        self._can_see_dollars = can_see_dollars
        self._items: list = []
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Header ──────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel(f"Inventory for {self.truck_label}")
        title.setStyleSheet("font-size: 13px; font-weight: bold;")
        header.addWidget(title)

        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("color: #a6adc8;")
        header.addStretch()
        header.addWidget(self.summary_label)

        self.audit_btn = QPushButton("Fast Audit")
        self.audit_btn.setToolTip("Quick card-swipe audit for this truck")
        self.audit_btn.clicked.connect(self._on_audit)
        header.addWidget(self.audit_btn)

        layout.addLayout(header)

        # ── Search ──────────────────────────────────────────────
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search this truck's parts...")
        self.search_input.textChanged.connect(self._on_search)
        layout.addWidget(self.search_input)

        # ── Table ───────────────────────────────────────────────
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
            1, QHeaderView.Stretch
        )
        layout.addWidget(self.table)

    def _on_audit(self):
        from wired_part.ui.dialogs.audit_dialog import AuditDialog
        dialog = AuditDialog(
            self.repo, "truck", target_id=self.truck_id, parent=self,
        )
        dialog.exec()
        self.refresh()

    def refresh(self):
        """Reload inventory for this truck."""
        self._items = self.repo.get_truck_inventory(self.truck_id)
        self._on_search()

    def _on_search(self):
        """Filter displayed items by search text."""
        search = self.search_input.text().strip().lower()
        if search:
            filtered = [
                i for i in self._items
                if search in i.part_number.lower()
                or search in i.part_description.lower()
            ]
        else:
            filtered = self._items
        self._populate_table(filtered)

    def _populate_table(self, items):
        """Fill table with truck inventory items."""
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(items))

        total_value = 0.0
        total_qty = 0

        for row, item in enumerate(items):
            value = item.quantity * item.unit_cost
            total_value += value
            total_qty += item.quantity

            cells = [
                QTableWidgetItem(item.part_number),
                QTableWidgetItem(item.part_description),
                self._num_item(item.quantity),
                QTableWidgetItem(
                    format_currency(item.unit_cost)
                    if self._can_see_dollars else "—"
                ),
                QTableWidgetItem(
                    format_currency(value)
                    if self._can_see_dollars else "—"
                ),
            ]

            for col, cell in enumerate(cells):
                self.table.setItem(row, col, cell)

        self.table.setSortingEnabled(True)
        if self._can_see_dollars:
            self.summary_label.setText(
                f"{len(items)} parts  |  {total_qty} total items  |  "
                f"Value: {format_currency(total_value)}"
            )
        else:
            self.summary_label.setText(
                f"{len(items)} parts  |  {total_qty} total items"
            )

    @staticmethod
    def _num_item(value: int) -> QTableWidgetItem:
        """Create a right-aligned numeric table item for proper sorting."""
        item = QTableWidgetItem()
        item.setData(Qt.ItemDataRole.DisplayRole, value)
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        return item


class TrucksInventoryPage(QWidget):
    """Container page with dynamic sub-tabs for each truck's inventory."""

    def __init__(self, repo: Repository, current_user=None):
        super().__init__()
        self.repo = repo
        self.current_user = current_user
        self._can_see_dollars = True
        if current_user:
            perms = repo.get_user_permissions(current_user.id)
            self._can_see_dollars = "show_dollar_values" in perms
        self._truck_tabs: dict[int, _TruckInventoryTab] = {}
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── Header ──────────────────────────────────────────────
        header = QHBoxLayout()
        header.setContentsMargins(8, 4, 8, 4)
        title = QLabel("Trucks Inventory")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        header.addWidget(title)

        self.truck_count_label = QLabel("")
        self.truck_count_label.setStyleSheet("color: #a6adc8;")
        header.addStretch()
        header.addWidget(self.truck_count_label)
        layout.addLayout(header)

        # ── Truck sub-tabs ──────────────────────────────────────
        self.truck_tabs = QTabWidget()
        self.truck_tabs.currentChanged.connect(self._on_truck_tab_changed)
        layout.addWidget(self.truck_tabs)

        # ── Empty state ─────────────────────────────────────────
        self.empty_label = QLabel(
            "No trucks found.\n\n"
            "Add trucks in the Job Tracking > Trucks tab."
        )
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet(
            "color: #6c7086; font-size: 12px; padding: 40px;"
        )
        layout.addWidget(self.empty_label)
        self.empty_label.setVisible(False)

    def refresh(self):
        """Rebuild truck tabs from database."""
        trucks = self.repo.get_all_trucks(active_only=True)

        # Track which trucks still exist
        current_truck_ids = {t.id for t in trucks}
        existing_ids = set(self._truck_tabs.keys())

        # Remove tabs for trucks that no longer exist
        for truck_id in existing_ids - current_truck_ids:
            tab = self._truck_tabs.pop(truck_id)
            idx = self.truck_tabs.indexOf(tab)
            if idx >= 0:
                self.truck_tabs.removeTab(idx)

        # Add/update tabs for each truck
        for truck in trucks:
            label = f"{truck.truck_number} — {truck.name}"
            if truck.id in self._truck_tabs:
                # Update existing tab
                tab = self._truck_tabs[truck.id]
                idx = self.truck_tabs.indexOf(tab)
                if idx >= 0:
                    self.truck_tabs.setTabText(idx, label)
                tab.refresh()
            else:
                # Create new tab
                tab = _TruckInventoryTab(
                    self.repo, truck.id, label,
                    can_see_dollars=self._can_see_dollars,
                )
                self._truck_tabs[truck.id] = tab
                self.truck_tabs.addTab(tab, label)

        has_trucks = len(trucks) > 0
        self.truck_tabs.setVisible(has_trucks)
        self.empty_label.setVisible(not has_trucks)
        self.truck_count_label.setText(
            f"{len(trucks)} active truck{'s' if len(trucks) != 1 else ''}"
        )

    def _on_truck_tab_changed(self, index: int):
        """Refresh the selected truck tab."""
        widget = self.truck_tabs.widget(index)
        if hasattr(widget, "refresh"):
            widget.refresh()
