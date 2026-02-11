"""Dialog for creating a return authorization with line items."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from wired_part.database.models import (
    ReturnAuthorization,
    ReturnAuthorizationItem,
)
from wired_part.database.repository import Repository
from wired_part.utils.constants import RETURN_REASON_LABELS
from wired_part.utils.formatters import format_currency


class ReturnDialog(QDialog):
    """Create a return authorization with items to return."""

    def __init__(self, repo: Repository, current_user=None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.current_user = current_user
        self._items = []  # list of ReturnAuthorizationItem

        self.setWindowTitle("New Return Authorization")
        self.setMinimumSize(700, 500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Header form ───────────────────────────────────────────
        form = QFormLayout()
        form.setSpacing(8)

        self.supplier_combo = QComboBox()
        suppliers = self.repo.get_all_suppliers()
        for s in suppliers:
            self.supplier_combo.addItem(s.name, s.id)
        form.addRow("Supplier:", self.supplier_combo)

        self.order_combo = QComboBox()
        self.order_combo.addItem("(None — standalone return)", None)
        orders = self.repo.get_all_purchase_orders()
        for o in orders:
            if o.status in ("received", "closed", "partial"):
                self.order_combo.addItem(
                    f"{o.order_number} — {o.supplier_name}", o.id
                )
        form.addRow("Related Order:", self.order_combo)

        self.reason_combo = QComboBox()
        for reason, label in RETURN_REASON_LABELS.items():
            self.reason_combo.addItem(label, reason)
        form.addRow("Reason:", self.reason_combo)

        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(50)
        self.notes_input.setPlaceholderText("Return notes...")
        form.addRow("Notes:", self.notes_input)

        layout.addLayout(form)

        # ── Items section ─────────────────────────────────────────
        items_header = QHBoxLayout()
        items_label = QLabel("Return Items")
        items_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        items_header.addWidget(items_label)
        items_header.addStretch()

        self.add_item_btn = QPushButton("+ Add Part")
        self.add_item_btn.clicked.connect(self._on_add_item)
        items_header.addWidget(self.add_item_btn)

        self.remove_item_btn = QPushButton("Remove")
        self.remove_item_btn.clicked.connect(self._on_remove_item)
        self.remove_item_btn.setEnabled(False)
        items_header.addWidget(self.remove_item_btn)

        layout.addLayout(items_header)

        # ── Items table ───────────────────────────────────────────
        columns = ["Part #", "Description", "Qty", "Unit Cost",
                    "Line Total", "Reason"]
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(len(columns))
        self.items_table.setHorizontalHeaderLabels(columns)
        self.items_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.items_table.setSelectionMode(QTableWidget.SingleSelection)
        self.items_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.items_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        self.items_table.selectionModel().selectionChanged.connect(
            lambda: self.remove_item_btn.setEnabled(
                self.items_table.currentRow() >= 0
            )
        )
        layout.addWidget(self.items_table)

        # ── Total ─────────────────────────────────────────────────
        self.total_label = QLabel("Total: $0.00")
        self.total_label.setStyleSheet(
            "font-weight: bold; font-size: 13px; color: #f38ba8;"
        )
        self.total_label.setAlignment(Qt.AlignRight)
        layout.addWidget(self.total_label)

        # ── Dialog buttons ────────────────────────────────────────
        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Save).setText("Create Return")
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _refresh_items_table(self):
        self.items_table.setRowCount(len(self._items))
        total = 0.0

        for row, item in enumerate(self._items):
            line_total = item.quantity * item.unit_cost
            total += line_total

            reason_label = RETURN_REASON_LABELS.get(item.reason, item.reason)

            self.items_table.setItem(
                row, 0, QTableWidgetItem(item.part_number)
            )
            self.items_table.setItem(
                row, 1, QTableWidgetItem(item.part_description)
            )

            qty_item = QTableWidgetItem()
            qty_item.setData(Qt.ItemDataRole.DisplayRole, item.quantity)
            qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.items_table.setItem(row, 2, qty_item)

            self.items_table.setItem(
                row, 3, QTableWidgetItem(format_currency(item.unit_cost))
            )
            self.items_table.setItem(
                row, 4, QTableWidgetItem(format_currency(line_total))
            )
            self.items_table.setItem(
                row, 5, QTableWidgetItem(reason_label)
            )

        self.total_label.setText(f"Total: {format_currency(total)}")

    def _on_add_item(self):
        """Show dialogs to pick a part and set qty/cost for return."""
        from PySide6.QtWidgets import QInputDialog

        parts = self.repo.get_all_parts()
        if not parts:
            QMessageBox.warning(self, "No Parts", "No parts in inventory.")
            return

        # Build part list for selection
        part_labels = [
            f"{p.part_number} — {p.description} "
            f"(stock: {p.quantity}, ${p.unit_cost:.2f})"
            for p in parts
        ]
        label, ok = QInputDialog.getItem(
            self, "Select Part", "Part to return:", part_labels, 0, False
        )
        if not ok:
            return

        idx = part_labels.index(label)
        part = parts[idx]

        qty, ok = QInputDialog.getInt(
            self, "Quantity", f"Quantity to return for {part.part_number}:",
            1, 1, part.quantity if part.quantity > 0 else 99999,
        )
        if not ok:
            return

        cost, ok = QInputDialog.getDouble(
            self, "Unit Cost", f"Unit cost for {part.part_number}:",
            part.unit_cost, 0.0, 999999.99, 2,
        )
        if not ok:
            return

        # Item-level reason (default to the main reason)
        reason = self.reason_combo.currentData() or "other"

        item = ReturnAuthorizationItem(
            ra_id=0,
            part_id=part.id,
            quantity=qty,
            unit_cost=cost,
            reason=reason,
            part_number=part.part_number,
            part_description=part.description,
        )
        self._items.append(item)
        self._refresh_items_table()

    def _on_remove_item(self):
        row = self.items_table.currentRow()
        if 0 <= row < len(self._items):
            self._items.pop(row)
            self._refresh_items_table()

    def _on_save(self):
        supplier_id = self.supplier_combo.currentData()
        if not supplier_id:
            QMessageBox.warning(self, "Error", "Please select a supplier.")
            return

        if not self._items:
            QMessageBox.warning(
                self, "Error", "Please add at least one item."
            )
            return

        order_id = self.order_combo.currentData()
        reason = self.reason_combo.currentData() or "other"
        notes = self.notes_input.toPlainText().strip()
        user_id = self.current_user.id if self.current_user else None

        ra = ReturnAuthorization(
            ra_number=self.repo.generate_ra_number(),
            order_id=order_id,
            supplier_id=supplier_id,
            status="initiated",
            reason=reason,
            notes=notes,
            created_by=user_id,
            credit_amount=0.0,
        )

        try:
            self.repo.create_return_authorization(ra, self._items)
            self.accept()
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to create return:\n{e}"
            )
