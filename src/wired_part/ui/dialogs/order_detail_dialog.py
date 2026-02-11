"""Read-only dialog showing full order details, line items, and history."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from wired_part.database.repository import Repository
from wired_part.utils.constants import ORDER_STATUS_LABELS
from wired_part.utils.formatters import format_currency


# Status colors for inline display
_STATUS_COLORS = {
    "draft": "#a6adc8",
    "submitted": "#89b4fa",
    "partial": "#fab387",
    "received": "#a6e3a1",
    "closed": "#6c7086",
    "cancelled": "#f38ba8",
}


class OrderDetailDialog(QDialog):
    """Read-only detail view for a purchase order."""

    def __init__(self, repo: Repository, order_id: int, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.order_id = order_id

        self.setWindowTitle("Order Details")
        self.setMinimumSize(750, 600)
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Order Header ──────────────────────────────────────────
        header_group = QGroupBox("Order Information")
        header_layout = QVBoxLayout(header_group)

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setTextFormat(Qt.RichText)
        header_layout.addWidget(self.info_label)

        layout.addWidget(header_group)

        # ── Line Items ────────────────────────────────────────────
        items_group = QGroupBox("Line Items")
        items_layout = QVBoxLayout(items_group)

        columns = [
            "Part #", "Description", "Ordered", "Received",
            "Remaining", "Unit Cost", "Line Total",
        ]
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(len(columns))
        self.items_table.setHorizontalHeaderLabels(columns)
        self.items_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.items_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.items_table.setAlternatingRowColors(True)
        self.items_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        items_layout.addWidget(self.items_table)

        self.items_summary = QLabel()
        self.items_summary.setStyleSheet(
            "font-weight: bold; color: #a6e3a1;"
        )
        self.items_summary.setAlignment(Qt.AlignRight)
        items_layout.addWidget(self.items_summary)

        layout.addWidget(items_group)

        # ── Receiving History ─────────────────────────────────────
        history_group = QGroupBox("Receiving History")
        history_layout = QVBoxLayout(history_group)

        history_columns = [
            "Date", "Part #", "Qty Received", "Allocated To",
            "Target", "Received By", "Notes",
        ]
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(len(history_columns))
        self.history_table.setHorizontalHeaderLabels(history_columns)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        history_layout.addWidget(self.history_table)

        layout.addWidget(history_group)

        # ── Close button ──────────────────────────────────────────
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_data(self):
        """Fetch order data and populate the dialog."""
        order = self.repo.get_purchase_order_by_id(self.order_id)
        if not order:
            self.info_label.setText(
                "<i>Order not found.</i>"
            )
            return

        # ── Header info ───────────────────────────────────────────
        status_label = ORDER_STATUS_LABELS.get(order.status, order.status)
        status_color = _STATUS_COLORS.get(order.status, "#cdd6f4")

        created = str(order.created_at)[:10] if order.created_at else "—"
        submitted = str(order.submitted_at)[:10] if order.submitted_at else "—"
        closed = str(order.closed_at)[:10] if order.closed_at else "—"

        info_html = f"""
        <table style="font-size: 13px;">
            <tr>
                <td><b>Order #:</b></td>
                <td>{order.order_number}</td>
                <td width="40"></td>
                <td><b>Status:</b></td>
                <td style="color: {status_color};
                    font-weight: bold;">{status_label}</td>
            </tr>
            <tr>
                <td><b>Supplier:</b></td>
                <td>{order.supplier_name}</td>
                <td></td>
                <td><b>Created By:</b></td>
                <td>{order.created_by_name or '—'}</td>
            </tr>
            <tr>
                <td><b>Created:</b></td>
                <td>{created}</td>
                <td></td>
                <td><b>Submitted:</b></td>
                <td>{submitted}</td>
            </tr>
            <tr>
                <td><b>Closed:</b></td>
                <td>{closed}</td>
                <td></td>
                <td><b>Parts List:</b></td>
                <td>{order.parts_list_name or '—'}</td>
            </tr>
        </table>
        """
        if order.notes:
            info_html += (
                f'<p style="margin-top: 6px;"><b>Notes:</b> '
                f'{order.notes}</p>'
            )
        self.info_label.setText(info_html)

        # ── Line items ────────────────────────────────────────────
        items = self.repo.get_order_items(self.order_id)
        self.items_table.setRowCount(len(items))
        total_cost = 0.0

        for row, item in enumerate(items):
            line_total = item.quantity_ordered * item.unit_cost
            total_cost += line_total
            remaining = item.quantity_remaining

            cells = [
                QTableWidgetItem(item.part_number),
                QTableWidgetItem(item.part_description),
                self._num_item(item.quantity_ordered),
                self._num_item(item.quantity_received),
                self._num_item(remaining),
                QTableWidgetItem(format_currency(item.unit_cost)),
                QTableWidgetItem(format_currency(line_total)),
            ]

            # Color remaining red if > 0 (not fully received)
            if remaining > 0:
                cells[4].setForeground(QColor("#f38ba8"))
            else:
                cells[4].setForeground(QColor("#a6e3a1"))

            for col, cell in enumerate(cells):
                self.items_table.setItem(row, col, cell)

        summary = self.repo.get_order_receive_summary(self.order_id)
        self.items_summary.setText(
            f"{summary['total_items']} items  |  "
            f"Ordered: {summary['total_ordered']}  |  "
            f"Received: {summary['total_received']}  |  "
            f"Total: {format_currency(total_cost)}"
        )

        # ── Receiving history ─────────────────────────────────────
        log = self.repo.get_receive_log(order_id=self.order_id)
        self.history_table.setRowCount(len(log))

        for row, entry in enumerate(log):
            date_str = (
                str(entry.received_at)[:10] if entry.received_at else "—"
            )

            # Build target label
            alloc_label = entry.allocate_to.title()
            target_label = ""
            if entry.allocate_to == "truck" and entry.truck_number:
                target_label = f"Truck {entry.truck_number}"
            elif entry.allocate_to == "job" and entry.job_number:
                target_label = f"Job {entry.job_number}"
            elif entry.allocate_to == "warehouse":
                target_label = "Main Warehouse"

            cells = [
                QTableWidgetItem(date_str),
                QTableWidgetItem(entry.part_number),
                self._num_item(entry.quantity_received),
                QTableWidgetItem(alloc_label),
                QTableWidgetItem(target_label),
                QTableWidgetItem(entry.received_by_name),
                QTableWidgetItem(entry.notes or ""),
            ]

            for col, cell in enumerate(cells):
                self.history_table.setItem(row, col, cell)

        if not log:
            self.history_table.setRowCount(1)
            no_data = QTableWidgetItem("No receiving history yet")
            no_data.setForeground(QColor("#a6adc8"))
            self.history_table.setItem(0, 0, no_data)
            self.history_table.setSpan(0, 0, 1, 7)

    @staticmethod
    def _num_item(value: int) -> QTableWidgetItem:
        item = QTableWidgetItem()
        item.setData(Qt.ItemDataRole.DisplayRole, value)
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        return item
