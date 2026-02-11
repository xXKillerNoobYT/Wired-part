"""Dialog for creating a purchase order from an existing parts list."""

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
    QSpinBox,
    QDoubleSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from wired_part.database.models import PurchaseOrderItem
from wired_part.database.repository import Repository
from wired_part.utils.formatters import format_currency


class OrderFromListDialog(QDialog):
    """Create a purchase order pre-populated from a parts list."""

    def __init__(self, repo: Repository, current_user=None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.current_user = current_user
        self._preview_items = []  # list of dicts: {part_id, part_number, description, qty, cost}

        self.setWindowTitle("Create Order from Parts List")
        self.setMinimumSize(750, 550)
        self._setup_ui()
        self._on_list_changed()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Selection form ────────────────────────────────────────
        form = QFormLayout()
        form.setSpacing(8)

        self.list_combo = QComboBox()
        parts_lists = self.repo.get_all_parts_lists()
        if not parts_lists:
            self.list_combo.addItem("(No parts lists available)", None)
        for pl in parts_lists:
            label = f"{pl.name}"
            if pl.job_number:
                label += f" [{pl.job_number}]"
            label += f" ({pl.list_type})"
            self.list_combo.addItem(label, pl.id)
        self.list_combo.currentIndexChanged.connect(self._on_list_changed)
        form.addRow("Parts List:", self.list_combo)

        self.supplier_combo = QComboBox()
        suppliers = self.repo.get_all_suppliers()
        for s in suppliers:
            self.supplier_combo.addItem(s.name, s.id)
        form.addRow("Supplier:", self.supplier_combo)

        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(50)
        self.notes_input.setPlaceholderText("Order notes...")
        form.addRow("Notes:", self.notes_input)

        layout.addLayout(form)

        # ── Preview label ─────────────────────────────────────────
        preview_header = QHBoxLayout()
        lbl = QLabel("Preview Items")
        lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
        preview_header.addWidget(lbl)
        preview_header.addStretch()

        info_lbl = QLabel("Double-click qty/cost to edit")
        info_lbl.setStyleSheet("color: #a6adc8; font-size: 11px;")
        preview_header.addWidget(info_lbl)
        layout.addLayout(preview_header)

        # ── Preview table ─────────────────────────────────────────
        columns = ["Part #", "Description", "Qty", "Unit Cost", "Line Total"]
        self.preview_table = QTableWidget()
        self.preview_table.setColumnCount(len(columns))
        self.preview_table.setHorizontalHeaderLabels(columns)
        self.preview_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.preview_table.setSelectionMode(QTableWidget.SingleSelection)
        self.preview_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        self.preview_table.cellDoubleClicked.connect(self._on_cell_double_click)
        layout.addWidget(self.preview_table)

        # ── Total ─────────────────────────────────────────────────
        self.total_label = QLabel("Total: $0.00")
        self.total_label.setStyleSheet(
            "font-weight: bold; font-size: 13px; color: #a6e3a1;"
        )
        self.total_label.setAlignment(Qt.AlignRight)
        layout.addWidget(self.total_label)

        # ── Dialog buttons ────────────────────────────────────────
        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Save).setText("Create Order")
        buttons.accepted.connect(self._on_create)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_list_changed(self):
        """Load items from the selected parts list into the preview."""
        list_id = self.list_combo.currentData()
        self._preview_items.clear()

        if list_id:
            items = self.repo.get_parts_list_items(list_id)
            for item in items:
                part = self.repo.get_part_by_id(item.part_id)
                self._preview_items.append({
                    "part_id": item.part_id,
                    "part_number": item.part_number or (
                        part.part_number if part else ""
                    ),
                    "description": item.part_description or (
                        part.description if part else ""
                    ),
                    "qty": item.quantity,
                    "cost": part.unit_cost if part else 0.0,
                })

        self._refresh_preview()

    def _refresh_preview(self):
        """Redraw the preview table from _preview_items."""
        self.preview_table.setRowCount(len(self._preview_items))
        total = 0.0

        for row, item in enumerate(self._preview_items):
            line_total = item["qty"] * item["cost"]
            total += line_total

            self.preview_table.setItem(
                row, 0, QTableWidgetItem(item["part_number"])
            )
            self.preview_table.setItem(
                row, 1, QTableWidgetItem(item["description"])
            )

            qty_item = QTableWidgetItem()
            qty_item.setData(Qt.ItemDataRole.DisplayRole, item["qty"])
            qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.preview_table.setItem(row, 2, qty_item)

            self.preview_table.setItem(
                row, 3, QTableWidgetItem(format_currency(item["cost"]))
            )
            self.preview_table.setItem(
                row, 4, QTableWidgetItem(format_currency(line_total))
            )

        self.total_label.setText(f"Total: {format_currency(total)}")

    def _on_cell_double_click(self, row, col):
        """Allow editing qty (col 2) or cost (col 3) inline."""
        if row < 0 or row >= len(self._preview_items):
            return

        item = self._preview_items[row]

        if col == 2:
            from PySide6.QtWidgets import QInputDialog
            qty, ok = QInputDialog.getInt(
                self, "Edit Quantity",
                f"Quantity for {item['part_number']}:",
                item["qty"], 1, 99999,
            )
            if ok:
                item["qty"] = qty
                self._refresh_preview()

        elif col == 3:
            from PySide6.QtWidgets import QInputDialog
            cost, ok = QInputDialog.getDouble(
                self, "Edit Unit Cost",
                f"Unit cost for {item['part_number']}:",
                item["cost"], 0.0, 999999.99, 2,
            )
            if ok:
                item["cost"] = cost
                self._refresh_preview()

    def _on_create(self):
        """Create the purchase order from the previewed items."""
        list_id = self.list_combo.currentData()
        supplier_id = self.supplier_combo.currentData()

        if not list_id:
            QMessageBox.warning(
                self, "Error", "Please select a parts list."
            )
            return
        if not supplier_id:
            QMessageBox.warning(
                self, "Error", "Please select a supplier."
            )
            return
        if not self._preview_items:
            QMessageBox.warning(
                self, "Error", "No items to order."
            )
            return

        notes = self.notes_input.toPlainText().strip()
        user_id = self.current_user.id if self.current_user else None

        try:
            # Create the order manually so we can use edited qty/cost
            from wired_part.database.models import PurchaseOrder

            order = PurchaseOrder(
                order_number=self.repo.generate_order_number(),
                supplier_id=supplier_id,
                parts_list_id=list_id,
                status="draft",
                notes=notes,
                created_by=user_id,
            )
            order_id = self.repo.create_purchase_order(order)

            for item in self._preview_items:
                oi = PurchaseOrderItem(
                    order_id=order_id,
                    part_id=item["part_id"],
                    quantity_ordered=item["qty"],
                    unit_cost=item["cost"],
                )
                self.repo.add_order_item(oi)

            self.accept()

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to create order:\n{e}"
            )
