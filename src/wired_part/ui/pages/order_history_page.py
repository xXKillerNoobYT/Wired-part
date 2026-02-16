"""Order History page — searchable history with analytics summary."""

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.repository import Repository
from wired_part.utils.constants import ORDER_STATUS_LABELS
from wired_part.utils.formatters import format_currency

ORDER_STATUS_COLORS = {
    "draft": QColor("#a6adc8"),
    "submitted": QColor("#89b4fa"),
    "partial": QColor("#fab387"),
    "received": QColor("#a6e3a1"),
    "closed": QColor("#6c7086"),
    "cancelled": QColor("#f38ba8"),
}


class OrderHistoryPage(QWidget):
    """Full order history with filtering and analytics."""

    COLUMNS = [
        "Order #", "Supplier", "Status", "Items", "Total Cost",
        "Created By", "Submitted", "Closed", "Notes",
    ]

    def __init__(self, repo: Repository, current_user=None):
        super().__init__()
        self.repo = repo
        self.current_user = current_user
        self._perms: set[str] = set()
        if current_user:
            self._perms = repo.get_user_permissions(current_user.id)
        self._can_see_dollars = "show_dollar_values" in self._perms
        self._orders = []
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Filters ────────────────────────────────────────────
        filter_row = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search orders...")
        self.search_input.textChanged.connect(self._on_search)
        filter_row.addWidget(self.search_input, 2)

        self.status_filter = QComboBox()
        self.status_filter.addItem("All Statuses", None)
        for status, label in ORDER_STATUS_LABELS.items():
            self.status_filter.addItem(label, status)
        self.status_filter.currentIndexChanged.connect(self._on_filter)
        filter_row.addWidget(self.status_filter, 1)

        self.supplier_filter = QComboBox()
        self.supplier_filter.addItem("All Suppliers", None)
        self.supplier_filter.currentIndexChanged.connect(self._on_filter)
        filter_row.addWidget(self.supplier_filter, 1)

        filter_row.addWidget(QLabel("From:"))
        self.date_from = QDateEdit()
        self.date_from.setDate(QDate.currentDate().addMonths(-3))
        self.date_from.setCalendarPopup(True)
        self.date_from.dateChanged.connect(self._on_filter)
        filter_row.addWidget(self.date_from)

        filter_row.addWidget(QLabel("To:"))
        self.date_to = QDateEdit()
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.dateChanged.connect(self._on_filter)
        filter_row.addWidget(self.date_to)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        filter_row.addWidget(self.refresh_btn)

        layout.addLayout(filter_row)

        # ── Table ──────────────────────────────────────────────
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
        self.table.doubleClicked.connect(self._on_view_detail)
        layout.addWidget(self.table)

        # ── Analytics Summary ──────────────────────────────────
        analytics_row = QHBoxLayout()
        analytics_row.setSpacing(24)

        self.total_orders_label = QLabel("")
        self.total_orders_label.setStyleSheet(
            "font-weight: bold; color: #cdd6f4;"
        )
        analytics_row.addWidget(self.total_orders_label)

        self.total_spent_label = QLabel("")
        self.total_spent_label.setStyleSheet(
            "font-weight: bold; color: #a6e3a1;"
        )
        analytics_row.addWidget(self.total_spent_label)

        self.avg_order_label = QLabel("")
        self.avg_order_label.setStyleSheet(
            "font-weight: bold; color: #89b4fa;"
        )
        analytics_row.addWidget(self.avg_order_label)

        self.top_supplier_label = QLabel("")
        self.top_supplier_label.setStyleSheet(
            "font-weight: bold; color: #f9e2af;"
        )
        analytics_row.addWidget(self.top_supplier_label)

        self.returns_label = QLabel("")
        self.returns_label.setStyleSheet(
            "font-weight: bold; color: #f38ba8;"
        )
        analytics_row.addWidget(self.returns_label)

        analytics_row.addStretch()
        layout.addLayout(analytics_row)

    def refresh(self):
        """Reload all orders and analytics."""
        # Load suppliers for filter
        self.supplier_filter.blockSignals(True)
        current_supplier = self.supplier_filter.currentData()
        self.supplier_filter.clear()
        self.supplier_filter.addItem("All Suppliers", None)
        suppliers = self.repo.get_all_suppliers()
        for s in suppliers:
            self.supplier_filter.addItem(s.name, s.id)
        # Restore selection
        for i in range(self.supplier_filter.count()):
            if self.supplier_filter.itemData(i) == current_supplier:
                self.supplier_filter.setCurrentIndex(i)
                break
        self.supplier_filter.blockSignals(False)

        self._load_orders()
        self._load_analytics()

    def _load_orders(self):
        status = self.status_filter.currentData()
        self._orders = self.repo.get_all_purchase_orders(status=status)

        # Apply supplier filter
        supplier_id = self.supplier_filter.currentData()
        if supplier_id:
            self._orders = [
                o for o in self._orders if o.supplier_id == supplier_id
            ]

        # Apply date filter
        date_from = self.date_from.date().toString("yyyy-MM-dd")
        date_to = self.date_to.date().toString("yyyy-MM-dd")
        self._orders = [
            o for o in self._orders
            if (not o.created_at or str(o.created_at)[:10] >= date_from)
            and (not o.created_at or str(o.created_at)[:10] <= date_to)
        ]

        self._on_search()

    def _on_search(self):
        search = self.search_input.text().strip().lower()
        if search:
            filtered = [
                o for o in self._orders
                if search in o.order_number.lower()
                or search in o.supplier_name.lower()
                or search in (o.notes or "").lower()
            ]
        else:
            filtered = self._orders
        self._populate_table(filtered)

    def _on_filter(self):
        self._load_orders()

    def _populate_table(self, orders):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(orders))

        for row, order in enumerate(orders):
            status_label = ORDER_STATUS_LABELS.get(
                order.status, order.status
            )
            submitted = str(order.submitted_at)[:10] if order.submitted_at else ""
            closed = str(order.closed_at)[:10] if order.closed_at else ""

            cells = [
                QTableWidgetItem(order.order_number),
                QTableWidgetItem(order.supplier_name),
                QTableWidgetItem(status_label),
                self._num_item(order.item_count),
                QTableWidgetItem(
                    format_currency(order.total_cost)
                    if self._can_see_dollars else "\u2014"
                ),
                QTableWidgetItem(order.created_by_name),
                QTableWidgetItem(submitted),
                QTableWidgetItem(closed),
                QTableWidgetItem(order.notes or ""),
            ]

            status_color = ORDER_STATUS_COLORS.get(order.status)
            if status_color:
                cells[2].setForeground(status_color)

            for col, cell in enumerate(cells):
                cell.setData(Qt.ItemDataRole.UserRole, order.id)
                self.table.setItem(row, col, cell)

        self.table.setSortingEnabled(True)

    def _load_analytics(self):
        analytics = self.repo.get_order_analytics()

        self.total_orders_label.setText(
            f"Total Orders: {analytics['total_orders']}"
        )
        self.total_spent_label.setText(
            f"Total Spent: {format_currency(analytics['total_spent'])}"
            if self._can_see_dollars
            else "Total Spent: \u2014"
        )
        self.avg_order_label.setText(
            f"Avg Order: {format_currency(analytics['avg_order_size'])}"
            if self._can_see_dollars
            else "Avg Order: \u2014"
        )
        self.top_supplier_label.setText(
            f"Top Supplier: {analytics['top_supplier']}"
        )
        self.returns_label.setText(
            f"Returns: {analytics['total_returns']}"
        )

    def _on_view_detail(self):
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        if not item:
            return
        order_id = item.data(Qt.ItemDataRole.UserRole)

        from wired_part.ui.dialogs.order_detail_dialog import (
            OrderDetailDialog,
        )
        dlg = OrderDetailDialog(self.repo, order_id, parent=self)
        dlg.exec()

    @staticmethod
    def _num_item(value: int) -> QTableWidgetItem:
        item = QTableWidgetItem()
        item.setData(Qt.ItemDataRole.DisplayRole, value)
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        return item
