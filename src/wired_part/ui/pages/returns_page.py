"""Returns & Pickups page — manage return authorizations."""

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

from wired_part.database.repository import Repository
from wired_part.utils.constants import (
    RETURN_REASON_LABELS,
    RETURN_STATUS_LABELS,
)
from wired_part.utils.formatters import format_currency

# Status colors
RA_STATUS_COLORS = {
    "initiated": QColor("#f9e2af"),      # Yellow
    "picked_up": QColor("#89b4fa"),      # Blue
    "credit_received": QColor("#a6e3a1"),  # Green
    "cancelled": QColor("#f38ba8"),      # Red
}


class ReturnsPage(QWidget):
    """View and manage return authorizations."""

    COLUMNS = [
        "RA #", "Supplier", "Status", "Reason", "Items",
        "Credit", "Created", "Notes",
    ]

    def __init__(self, repo: Repository, current_user=None):
        super().__init__()
        self.repo = repo
        self.current_user = current_user
        self._perms: set[str] = set()
        if current_user:
            self._perms = repo.get_user_permissions(current_user.id)
        self._can_see_dollars = "show_dollar_values" in self._perms
        self._returns = []
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Toolbar ────────────────────────────────────────────
        toolbar = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search returns...")
        self.search_input.textChanged.connect(self._on_search)
        toolbar.addWidget(self.search_input, 2)

        self.status_filter = QComboBox()
        self.status_filter.addItem("All Statuses", None)
        for status, label in RETURN_STATUS_LABELS.items():
            self.status_filter.addItem(label, status)
        self.status_filter.currentIndexChanged.connect(self._on_filter)
        toolbar.addWidget(self.status_filter, 1)

        self.new_btn = QPushButton("+ New Return")
        self.new_btn.clicked.connect(self._on_new_return)
        toolbar.addWidget(self.new_btn)

        self.status_btn = QPushButton("Update Status")
        self.status_btn.clicked.connect(self._on_update_status)
        self.status_btn.setEnabled(False)
        toolbar.addWidget(self.status_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._on_delete)
        self.delete_btn.setEnabled(False)
        toolbar.addWidget(self.delete_btn)

        # Apply permission visibility
        p = self._perms
        self.new_btn.setVisible("orders_return" in p)
        self.status_btn.setVisible("orders_return" in p)
        self.delete_btn.setVisible("orders_return" in p)

        layout.addLayout(toolbar)

        # ── Summary ───────────────────────────────────────────
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("color: #a6adc8; padding: 2px;")
        layout.addWidget(self.summary_label)

        # ── Table ─────────────────────────────────────────────
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
        layout.addWidget(self.table)

    def refresh(self):
        status = self.status_filter.currentData()
        self._returns = self.repo.get_all_return_authorizations(status=status)
        self._on_search()

    def _on_search(self):
        search = self.search_input.text().strip().lower()
        if search:
            filtered = [
                r for r in self._returns
                if search in r.ra_number.lower()
                or search in r.supplier_name.lower()
                or search in (r.notes or "").lower()
            ]
        else:
            filtered = self._returns
        self._populate_table(filtered)

    def _on_filter(self):
        self.refresh()

    def _populate_table(self, returns):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(returns))

        total_credit = 0.0
        for row, ra in enumerate(returns):
            total_credit += ra.credit_amount
            status_label = RETURN_STATUS_LABELS.get(ra.status, ra.status)
            reason_label = RETURN_REASON_LABELS.get(ra.reason, ra.reason)
            date_str = str(ra.created_at)[:10] if ra.created_at else ""

            cells = [
                QTableWidgetItem(ra.ra_number),
                QTableWidgetItem(ra.supplier_name),
                QTableWidgetItem(status_label),
                QTableWidgetItem(reason_label),
                self._num_item(ra.item_count),
                QTableWidgetItem(
                    format_currency(ra.credit_amount)
                    if self._can_see_dollars else "\u2014"
                ),
                QTableWidgetItem(date_str),
                QTableWidgetItem(ra.notes or ""),
            ]

            status_color = RA_STATUS_COLORS.get(ra.status)
            if status_color:
                cells[2].setForeground(status_color)

            for col, cell in enumerate(cells):
                cell.setData(Qt.ItemDataRole.UserRole, ra.id)
                self.table.setItem(row, col, cell)

        self.table.setSortingEnabled(True)
        credit_str = (
            format_currency(total_credit)
            if self._can_see_dollars else "\u2014"
        )
        self.summary_label.setText(
            f"{len(returns)} returns  |  "
            f"Total credit: {credit_str}"
        )

    def _on_selection_changed(self):
        row = self.table.currentRow()
        if row < 0:
            self.status_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            return

        ra = self._get_selected_ra()
        if ra:
            self.status_btn.setEnabled(
                ra.status in ("initiated", "picked_up")
            )
            self.delete_btn.setEnabled(ra.status == "initiated")

    def _get_selected_ra(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if not item:
            return None
        ra_id = item.data(Qt.ItemDataRole.UserRole)
        return self.repo.get_return_authorization_by_id(ra_id)

    def _on_new_return(self):
        from wired_part.ui.dialogs.return_dialog import ReturnDialog
        dlg = ReturnDialog(
            self.repo, current_user=self.current_user, parent=self
        )
        if dlg.exec():
            self.refresh()

    def _on_update_status(self):
        ra = self._get_selected_ra()
        if not ra:
            return

        if ra.status == "initiated":
            reply = QMessageBox.question(
                self, "Mark Picked Up",
                f"Mark {ra.ra_number} as picked up by supplier?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.repo.update_return_status(ra.id, "picked_up")
                self.refresh()
        elif ra.status == "picked_up":
            from PySide6.QtWidgets import QInputDialog
            credit, ok = QInputDialog.getDouble(
                self, "Credit Amount",
                f"Enter credit amount for {ra.ra_number}:",
                0.0, 0.0, 999999.99, 2,
            )
            if ok:
                self.repo.update_return_status(
                    ra.id, "credit_received", credit_amount=credit
                )
                self.refresh()

    def _on_delete(self):
        ra = self._get_selected_ra()
        if not ra:
            return
        reply = QMessageBox.question(
            self, "Delete Return",
            f"Delete return {ra.ra_number}?\n"
            f"Inventory will be restored.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                self.repo.delete_return_authorization(ra.id)
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
