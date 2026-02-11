"""Dialog for creating/editing purchase orders with line items."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from wired_part.database.models import PurchaseOrder, PurchaseOrderItem
from wired_part.database.repository import Repository
from wired_part.utils.formatters import format_currency


class OrderDialog(QDialog):
    """Create or edit a purchase order with line items."""

    def __init__(self, repo: Repository, order=None, current_user=None,
                 parent=None):
        super().__init__(parent)
        self.repo = repo
        self.order = order
        self.current_user = current_user
        self._items = []  # PurchaseOrderItem list
        self._editing = order is not None

        self.setWindowTitle(
            "Edit Purchase Order" if self._editing else "New Purchase Order"
        )
        self.setMinimumSize(700, 500)
        self._setup_ui()
        if self._editing:
            self._populate()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Order header form ──────────────────────────────────
        form = QFormLayout()
        form.setSpacing(8)

        self.supplier_combo = QComboBox()
        suppliers = self.repo.get_all_suppliers()
        for s in suppliers:
            self.supplier_combo.addItem(s.name, s.id)
        form.addRow("Supplier:", self.supplier_combo)

        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(60)
        self.notes_input.setPlaceholderText("Order notes...")
        form.addRow("Notes:", self.notes_input)

        layout.addLayout(form)

        # ── Items section ──────────────────────────────────────
        items_header = QHBoxLayout()
        items_label = QLabel("Line Items")
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

        # Items table
        self.items_table = QTableWidget()
        columns = ["Part #", "Description", "Qty", "Unit Cost", "Line Total"]
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

        # Total
        self.total_label = QLabel("Total: $0.00")
        self.total_label.setStyleSheet(
            "font-weight: bold; font-size: 13px; color: #a6e3a1;"
        )
        self.total_label.setAlignment(Qt.AlignRight)
        layout.addWidget(self.total_label)

        # ── Dialog buttons ─────────────────────────────────────
        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self):
        """Fill form with existing order data."""
        # Set supplier
        for i in range(self.supplier_combo.count()):
            if self.supplier_combo.itemData(i) == self.order.supplier_id:
                self.supplier_combo.setCurrentIndex(i)
                break

        self.notes_input.setPlainText(self.order.notes or "")

        # Load items
        self._items = self.repo.get_order_items(self.order.id)
        self._refresh_items_table()

    def _refresh_items_table(self):
        self.items_table.setRowCount(len(self._items))
        total = 0.0

        for row, item in enumerate(self._items):
            line_total = item.quantity_ordered * item.unit_cost
            total += line_total

            self.items_table.setItem(
                row, 0, QTableWidgetItem(item.part_number)
            )
            self.items_table.setItem(
                row, 1, QTableWidgetItem(item.part_description)
            )

            qty_item = QTableWidgetItem()
            qty_item.setData(Qt.ItemDataRole.DisplayRole, item.quantity_ordered)
            qty_item.setTextAlignment(
                Qt.AlignRight | Qt.AlignVCenter
            )
            self.items_table.setItem(row, 2, qty_item)

            self.items_table.setItem(
                row, 3, QTableWidgetItem(format_currency(item.unit_cost))
            )
            self.items_table.setItem(
                row, 4, QTableWidgetItem(format_currency(line_total))
            )

        self.total_label.setText(f"Total: {format_currency(total)}")

    def _on_add_item(self):
        """Show a dialog to pick a part and set qty/cost."""
        from PySide6.QtWidgets import QInputDialog

        parts = self.repo.get_all_parts()
        if not parts:
            QMessageBox.warning(self, "No Parts", "No parts in inventory.")
            return

        # Build part list for selection
        part_labels = [
            f"{p.part_number} — {p.description} "
            f"(${p.unit_cost:.2f})"
            for p in parts
        ]
        label, ok = QInputDialog.getItem(
            self, "Select Part", "Part:", part_labels, 0, False
        )
        if not ok:
            return

        idx = part_labels.index(label)
        part = parts[idx]

        qty, ok = QInputDialog.getInt(
            self, "Quantity", f"Quantity for {part.part_number}:",
            1, 1, 99999,
        )
        if not ok:
            return

        cost, ok = QInputDialog.getDouble(
            self, "Unit Cost", f"Unit cost for {part.part_number}:",
            part.unit_cost, 0.0, 999999.99, 2,
        )
        if not ok:
            return

        item = PurchaseOrderItem(
            order_id=self.order.id if self.order else 0,
            part_id=part.id,
            quantity_ordered=qty,
            unit_cost=cost,
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

        notes = self.notes_input.toPlainText().strip()

        if self._editing:
            self.order.supplier_id = supplier_id
            self.order.notes = notes
            self.repo.update_purchase_order(self.order)

            # Sync items: remove old, add new
            old_items = self.repo.get_order_items(self.order.id)
            for oi in old_items:
                self.repo.remove_order_item(oi.id)
            for item in self._items:
                item.order_id = self.order.id
                self.repo.add_order_item(item)
        else:
            order = PurchaseOrder(
                order_number=self.repo.generate_order_number(),
                supplier_id=supplier_id,
                status="draft",
                notes=notes,
                created_by=(
                    self.current_user.id if self.current_user else None
                ),
            )
            order_id = self.repo.create_purchase_order(order)

            for item in self._items:
                item.order_id = order_id
                self.repo.add_order_item(item)

        self.accept()
