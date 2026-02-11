"""Pending Orders page — manage purchase orders (draft/submitted/partial)."""

import webbrowser
from urllib.parse import quote

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
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

from wired_part.database.models import PurchaseOrder
from wired_part.database.repository import Repository
from wired_part.utils.constants import ORDER_STATUS_LABELS
from wired_part.utils.formatters import format_currency

# Color palette for order statuses
ORDER_STATUS_COLORS = {
    "draft": QColor("#a6adc8"),       # Gray
    "submitted": QColor("#89b4fa"),   # Blue
    "partial": QColor("#fab387"),     # Orange
    "received": QColor("#a6e3a1"),    # Green
    "closed": QColor("#6c7086"),      # Dark gray
    "cancelled": QColor("#f38ba8"),   # Red
}


class PendingOrdersPage(QWidget):
    """View and manage purchase orders."""

    COLUMNS = [
        "Order #", "Supplier", "Status", "Items", "Total Cost",
        "Created By", "Date", "Notes",
    ]

    def __init__(self, repo: Repository, current_user=None):
        super().__init__()
        self.repo = repo
        self.current_user = current_user
        self._orders: list[PurchaseOrder] = []
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Toolbar row 1 ─────────────────────────────────────────
        toolbar = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search orders...")
        self.search_input.textChanged.connect(self._on_search)
        toolbar.addWidget(self.search_input, 2)

        self.status_filter = QComboBox()
        self.status_filter.addItem("All Statuses", None)
        self.status_filter.addItem("Draft", "draft")
        self.status_filter.addItem("Submitted", "submitted")
        self.status_filter.addItem("Partial", "partial")
        self.status_filter.currentIndexChanged.connect(self._on_filter)
        toolbar.addWidget(self.status_filter, 1)

        self.new_btn = QPushButton("+ New Order")
        self.new_btn.clicked.connect(self._on_new_order)
        toolbar.addWidget(self.new_btn)

        self.from_list_btn = QPushButton("From Parts List")
        self.from_list_btn.setToolTip("Create order from an existing parts list")
        self.from_list_btn.clicked.connect(self._on_from_parts_list)
        toolbar.addWidget(self.from_list_btn)

        self.supply_house_btn = QPushButton("Supply House")
        self.supply_house_btn.setToolTip(
            "Quick pickup order from a local supply house"
        )
        self.supply_house_btn.setStyleSheet(
            "color: #f9e2af; font-weight: bold;"
        )
        self.supply_house_btn.clicked.connect(self._on_supply_house)
        toolbar.addWidget(self.supply_house_btn)

        self.split_btn = QPushButton("Split Order")
        self.split_btn.setToolTip(
            "Split a parts list across multiple suppliers based on "
            "preference and availability"
        )
        self.split_btn.clicked.connect(self._on_split_order)
        toolbar.addWidget(self.split_btn)

        layout.addLayout(toolbar)

        # ── Toolbar row 2 (action buttons) ────────────────────────
        action_row = QHBoxLayout()

        self.view_btn = QPushButton("View Details")
        self.view_btn.setToolTip("View full order details and receiving history")
        self.view_btn.clicked.connect(self._on_view_detail)
        self.view_btn.setEnabled(False)
        action_row.addWidget(self.view_btn)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self._on_edit)
        self.edit_btn.setEnabled(False)
        action_row.addWidget(self.edit_btn)

        self.submit_btn = QPushButton("Submit")
        self.submit_btn.setToolTip("Submit draft order for processing")
        self.submit_btn.clicked.connect(self._on_submit)
        self.submit_btn.setEnabled(False)
        action_row.addWidget(self.submit_btn)

        self.email_btn = QPushButton("Email Draft")
        self.email_btn.setToolTip(
            "Generate an email draft for the selected order"
        )
        self.email_btn.clicked.connect(self._on_email_draft)
        self.email_btn.setEnabled(False)
        action_row.addWidget(self.email_btn)

        action_row.addStretch()

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._on_delete)
        self.delete_btn.setEnabled(False)
        action_row.addWidget(self.delete_btn)

        layout.addLayout(action_row)

        # ── Summary ────────────────────────────────────────────
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("color: #a6adc8; padding: 2px;")
        layout.addWidget(self.summary_label)

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
        self.table.selectionModel().selectionChanged.connect(
            self._on_selection_changed
        )
        self.table.doubleClicked.connect(self._on_view_detail)
        layout.addWidget(self.table)

    def refresh(self):
        """Reload orders from database."""
        status = self.status_filter.currentData()
        if status:
            self._orders = self.repo.get_all_purchase_orders(status=status)
        else:
            # Show draft, submitted, partial (active orders)
            all_orders = self.repo.get_all_purchase_orders()
            self._orders = [
                o for o in all_orders
                if o.status in ("draft", "submitted", "partial")
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
        self.refresh()

    def _populate_table(self, orders):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(orders))

        total_cost = 0.0
        for row, order in enumerate(orders):
            total_cost += order.total_cost
            status_label = ORDER_STATUS_LABELS.get(
                order.status, order.status
            )
            date_str = ""
            if order.created_at:
                date_str = str(order.created_at)[:10]

            cells = [
                QTableWidgetItem(order.order_number),
                QTableWidgetItem(order.supplier_name),
                QTableWidgetItem(status_label),
                self._num_item(order.item_count),
                QTableWidgetItem(format_currency(order.total_cost)),
                QTableWidgetItem(order.created_by_name),
                QTableWidgetItem(date_str),
                QTableWidgetItem(order.notes or ""),
            ]

            # Color-code status
            status_color = ORDER_STATUS_COLORS.get(order.status)
            if status_color:
                cells[2].setForeground(status_color)

            for col, cell in enumerate(cells):
                cell.setData(Qt.ItemDataRole.UserRole, order.id)
                self.table.setItem(row, col, cell)

        self.table.setSortingEnabled(True)
        self.summary_label.setText(
            f"{len(orders)} orders  |  "
            f"Total: {format_currency(total_cost)}"
        )

    def _on_selection_changed(self):
        selected = self.table.currentRow() >= 0
        order = self._get_selected_order()

        self.view_btn.setEnabled(selected and order is not None)
        self.edit_btn.setEnabled(selected and order and order.is_editable)
        self.submit_btn.setEnabled(
            selected and order and order.status == "draft"
        )
        self.email_btn.setEnabled(selected and order is not None)
        self.delete_btn.setEnabled(
            selected and order and order.status == "draft"
        )

    def _get_selected_order(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if not item:
            return None
        order_id = item.data(Qt.ItemDataRole.UserRole)
        return self.repo.get_purchase_order_by_id(order_id)

    def _on_view_detail(self):
        order = self._get_selected_order()
        if not order:
            return
        from wired_part.ui.dialogs.order_detail_dialog import (
            OrderDetailDialog,
        )
        dlg = OrderDetailDialog(self.repo, order.id, parent=self)
        dlg.exec()

    def _on_new_order(self):
        from wired_part.ui.dialogs.order_dialog import OrderDialog
        dlg = OrderDialog(self.repo, current_user=self.current_user,
                          parent=self)
        if dlg.exec():
            self.refresh()

    def _on_from_parts_list(self):
        from wired_part.ui.dialogs.order_from_list_dialog import (
            OrderFromListDialog,
        )
        dlg = OrderFromListDialog(
            self.repo, current_user=self.current_user, parent=self
        )
        if dlg.exec():
            self.refresh()

    def _on_supply_house(self):
        """Open the supply house quick-order dialog."""
        from wired_part.ui.dialogs.supply_house_dialog import (
            SupplyHouseDialog,
        )
        dlg = SupplyHouseDialog(
            self.repo, current_user=self.current_user, parent=self
        )
        if dlg.exec():
            self.refresh()

    def _on_split_order(self):
        """Open the supplier-splitting dialog."""
        from wired_part.ui.dialogs.split_order_dialog import (
            SplitOrderDialog,
        )
        dlg = SplitOrderDialog(
            self.repo, current_user=self.current_user, parent=self
        )
        if dlg.exec():
            self.refresh()

    def _on_email_draft(self):
        """Generate and open an email draft for the selected order."""
        order = self._get_selected_order()
        if not order:
            return

        supplier = self.repo.get_supplier_by_id(order.supplier_id)
        if not supplier:
            QMessageBox.warning(self, "Error", "Supplier not found.")
            return

        items = self.repo.get_order_items(order.id)
        if not items:
            QMessageBox.warning(
                self, "No Items",
                "This order has no line items.",
            )
            return

        # Build email
        to_email = supplier.email or ""
        subject = f"Purchase Order {order.order_number} — Wired Electrical"

        # Build body
        lines = []
        lines.append(f"Hi {supplier.contact_name or supplier.name},")
        lines.append("")
        lines.append(
            f"Please find below our purchase order "
            f"{order.order_number}."
        )
        lines.append("")
        lines.append("Items ordered:")
        lines.append("-" * 50)

        total = 0.0
        for i, item in enumerate(items, 1):
            line_total = item.quantity_ordered * item.unit_cost
            total += line_total
            lines.append(
                f"  {i}. {item.part_number} — {item.part_description}"
            )
            lines.append(
                f"     Qty: {item.quantity_ordered}  |  "
                f"Unit: {format_currency(item.unit_cost)}  |  "
                f"Total: {format_currency(line_total)}"
            )

        lines.append("-" * 50)
        lines.append(f"Order Total: {format_currency(total)}")
        lines.append("")

        if order.notes:
            lines.append(f"Notes: {order.notes}")
            lines.append("")

        lines.append("Please confirm receipt and expected delivery date.")
        lines.append("")
        lines.append("Thank you,")
        lines.append("Wired Electrical")

        body = "\n".join(lines)

        # Open mailto link
        mailto_url = (
            f"mailto:{quote(to_email)}"
            f"?subject={quote(subject)}"
            f"&body={quote(body)}"
        )

        try:
            webbrowser.open(mailto_url)
            QMessageBox.information(
                self, "Email Draft",
                f"Email draft opened in your default email client.\n"
                f"To: {to_email or '(no email on file)'}\n"
                f"Subject: {subject}",
            )
        except Exception as e:
            # Fallback: show the email content for copy
            QMessageBox.information(
                self, "Email Draft",
                f"Could not open email client.\n\n"
                f"To: {to_email}\n"
                f"Subject: {subject}\n\n"
                f"{body}",
            )

    def _on_edit(self):
        order = self._get_selected_order()
        if not order:
            return
        from wired_part.ui.dialogs.order_dialog import OrderDialog
        dlg = OrderDialog(self.repo, order=order,
                          current_user=self.current_user, parent=self)
        if dlg.exec():
            self.refresh()

    def _on_submit(self):
        order = self._get_selected_order()
        if not order or order.status != "draft":
            return

        items = self.repo.get_order_items(order.id)
        if not items:
            QMessageBox.warning(
                self, "No Items",
                "Cannot submit an order with no line items.",
            )
            return

        reply = QMessageBox.question(
            self, "Submit Order",
            f"Submit order {order.order_number} to {order.supplier_name}?\n"
            f"({len(items)} items, "
            f"{format_currency(order.total_cost)} total)",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.repo.submit_purchase_order(order.id)
            self.refresh()

    def _on_delete(self):
        order = self._get_selected_order()
        if not order:
            return
        reply = QMessageBox.question(
            self, "Delete Order",
            f"Delete draft order {order.order_number}?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                self.repo.delete_purchase_order(order.id)
                self.refresh()
            except ValueError as e:
                QMessageBox.warning(self, "Error", str(e))

    @staticmethod
    def _num_item(value: int) -> QTableWidgetItem:
        item = QTableWidgetItem()
        item.setData(Qt.ItemDataRole.DisplayRole, value)
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        return item
