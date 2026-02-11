"""Supply House Quick Order dialog — for local pickup orders.

Generates a pick list and optional phone script for calling in orders
to a local electrical supply house.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
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
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.models import PurchaseOrder, PurchaseOrderItem
from wired_part.database.repository import Repository
from wired_part.utils.formatters import format_currency


class SupplyHouseDialog(QDialog):
    """Quick pickup order for a local supply house.

    Shows only supply-house suppliers, lets the user build a pick list,
    generates a phone script, and creates a draft PO.
    """

    def __init__(self, repo: Repository, current_user=None,
                 parts_list_id=None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.current_user = current_user
        self._items = []  # list of dicts: {part_id, part_number, desc, qty, cost}
        self._parts_list_id = parts_list_id

        self.setWindowTitle("Supply House Pickup Order")
        self.setMinimumSize(750, 600)
        self._setup_ui()

        # Pre-populate from parts list if provided
        if parts_list_id:
            self._load_from_parts_list(parts_list_id)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Header ────────────────────────────────────────────────
        header = QLabel("Supply House Quick Order")
        header.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(header)

        subtitle = QLabel(
            "Build a pick list for a local supply house pickup. "
            "Generate a phone script to call in the order."
        )
        subtitle.setStyleSheet("color: #a6adc8; margin-bottom: 8px;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # ── Supplier selection ────────────────────────────────────
        form = QFormLayout()
        form.setSpacing(6)

        self.supplier_combo = QComboBox()
        supply_houses = [
            s for s in self.repo.get_all_suppliers()
            if s.is_supply_house
        ]
        if not supply_houses:
            self.supplier_combo.addItem(
                "(No supply houses configured — mark a supplier "
                "as Supply House in Settings)", None
            )
        for s in supply_houses:
            label = s.name
            if s.operating_hours:
                label += f"  ({s.operating_hours})"
            self.supplier_combo.addItem(label, s.id)
        self.supplier_combo.currentIndexChanged.connect(
            self._on_supplier_changed
        )
        form.addRow("Supply House:", self.supplier_combo)

        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: #89b4fa; font-size: 11px;")
        form.addRow("", self.info_label)

        layout.addLayout(form)

        # ── Items table ───────────────────────────────────────────
        items_header = QHBoxLayout()
        lbl = QLabel("Pick List")
        lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
        items_header.addWidget(lbl)
        items_header.addStretch()

        add_btn = QPushButton("+ Add Part")
        add_btn.clicked.connect(self._on_add_part)
        items_header.addWidget(add_btn)

        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._on_remove_part)
        items_header.addWidget(remove_btn)

        layout.addLayout(items_header)

        cols = ["", "Part #", "Description", "Qty", "Est. Cost", "Line Total"]
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(len(cols))
        self.items_table.setHorizontalHeaderLabels(cols)
        self.items_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.items_table.setSelectionMode(QTableWidget.SingleSelection)
        self.items_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.items_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch
        )
        self.items_table.setColumnWidth(0, 30)
        layout.addWidget(self.items_table)

        # Total
        self.total_label = QLabel("Estimated Total: $0.00")
        self.total_label.setStyleSheet(
            "font-weight: bold; font-size: 13px; color: #a6e3a1;"
        )
        self.total_label.setAlignment(Qt.AlignRight)
        layout.addWidget(self.total_label)

        # ── Phone script ──────────────────────────────────────────
        script_header = QHBoxLayout()
        script_lbl = QLabel("Phone Script")
        script_lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
        script_header.addWidget(script_lbl)
        script_header.addStretch()

        self.gen_script_btn = QPushButton("Generate Script")
        self.gen_script_btn.clicked.connect(self._generate_phone_script)
        script_header.addWidget(self.gen_script_btn)

        self.copy_btn = QPushButton("Copy to Clipboard")
        self.copy_btn.clicked.connect(self._copy_script)
        self.copy_btn.setEnabled(False)
        script_header.addWidget(self.copy_btn)

        layout.addLayout(script_header)

        self.script_text = QTextEdit()
        self.script_text.setMaximumHeight(120)
        self.script_text.setReadOnly(True)
        self.script_text.setStyleSheet(
            "background-color: #313244; color: #cdd6f4; "
            "font-family: monospace; font-size: 12px; "
            "border: 1px solid #45475a; border-radius: 4px;"
        )
        layout.addWidget(self.script_text)

        # ── Buttons ───────────────────────────────────────────────
        btn_row = QHBoxLayout()

        self.create_po_btn = QPushButton("Create PO & Print Pick List")
        self.create_po_btn.setStyleSheet(
            "background-color: #a6e3a1; color: #1e1e2e; "
            "font-weight: bold; padding: 8px 16px;"
        )
        self.create_po_btn.clicked.connect(self._on_create_po)
        btn_row.addWidget(self.create_po_btn)

        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)

        # Initial supplier info
        self._on_supplier_changed()

    def _on_supplier_changed(self):
        sid = self.supplier_combo.currentData()
        if not sid:
            self.info_label.setText("")
            return
        supplier = self.repo.get_supplier_by_id(sid)
        if supplier:
            parts = []
            if supplier.phone:
                parts.append(f"Phone: {supplier.phone}")
            if supplier.address:
                parts.append(f"Address: {supplier.address}")
            self.info_label.setText("  |  ".join(parts))

    def _load_from_parts_list(self, list_id):
        """Pre-populate items from a parts list."""
        items = self.repo.get_parts_list_items(list_id)
        for item in items:
            part = self.repo.get_part_by_id(item.part_id)
            if part:
                self._items.append({
                    "part_id": item.part_id,
                    "part_number": part.part_number,
                    "desc": part.description,
                    "qty": item.quantity,
                    "cost": part.unit_cost,
                })
        self._refresh_table()

    def _on_add_part(self):
        from PySide6.QtWidgets import QInputDialog

        parts = self.repo.get_all_parts()
        if not parts:
            QMessageBox.warning(self, "No Parts", "No parts in inventory.")
            return

        labels = [
            f"{p.part_number} -- {p.description} (${p.unit_cost:.2f})"
            for p in parts
        ]
        label, ok = QInputDialog.getItem(
            self, "Select Part", "Part:", labels, 0, False
        )
        if not ok:
            return

        idx = labels.index(label)
        part = parts[idx]

        qty, ok = QInputDialog.getInt(
            self, "Quantity", f"Quantity for {part.part_number}:",
            1, 1, 99999,
        )
        if not ok:
            return

        self._items.append({
            "part_id": part.id,
            "part_number": part.part_number,
            "desc": part.description,
            "qty": qty,
            "cost": part.unit_cost,
        })
        self._refresh_table()

    def _on_remove_part(self):
        row = self.items_table.currentRow()
        if 0 <= row < len(self._items):
            self._items.pop(row)
            self._refresh_table()

    def _refresh_table(self):
        self.items_table.setRowCount(len(self._items))
        total = 0.0

        for row, item in enumerate(self._items):
            line = item["qty"] * item["cost"]
            total += line

            # Row number
            num_item = QTableWidgetItem(str(row + 1))
            num_item.setTextAlignment(Qt.AlignCenter)
            self.items_table.setItem(row, 0, num_item)

            self.items_table.setItem(
                row, 1, QTableWidgetItem(item["part_number"])
            )
            self.items_table.setItem(
                row, 2, QTableWidgetItem(item["desc"])
            )

            qty_item = QTableWidgetItem()
            qty_item.setData(Qt.ItemDataRole.DisplayRole, item["qty"])
            qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.items_table.setItem(row, 3, qty_item)

            self.items_table.setItem(
                row, 4, QTableWidgetItem(format_currency(item["cost"]))
            )
            self.items_table.setItem(
                row, 5, QTableWidgetItem(format_currency(line))
            )

        self.total_label.setText(
            f"Estimated Total: {format_currency(total)}"
        )

    def _generate_phone_script(self):
        """Generate a readable phone call script for the order."""
        sid = self.supplier_combo.currentData()
        if not sid:
            self.script_text.setPlainText(
                "(Select a supply house first)"
            )
            return

        supplier = self.repo.get_supplier_by_id(sid)

        if not self._items:
            self.script_text.setPlainText("(Add items to generate a script)")
            return

        phone_warning = ""
        if supplier and not supplier.phone:
            phone_warning = (
                "NOTE: No phone number on file for "
                f"{supplier.name}.\n"
                "Add a phone number in Settings > Suppliers.\n\n"
            )

        company_name = "Wired Electrical"  # Could be config-driven
        lines = []
        if phone_warning:
            lines.append(phone_warning)
        lines.append(
            f"Hi, this is {company_name} calling to place a "
            f"pickup order."
        )
        if supplier and supplier.contact_name:
            lines.append(
                f"Contact: {supplier.contact_name}"
            )
        lines.append("")
        lines.append(f"I need {len(self._items)} item(s):")
        lines.append("")

        for i, item in enumerate(self._items, 1):
            lines.append(
                f"  {i}. {item['part_number']} — "
                f"{item['desc']}, qty {item['qty']}"
            )

        lines.append("")
        total = sum(it["qty"] * it["cost"] for it in self._items)
        lines.append(
            f"Estimated total: {format_currency(total)}"
        )
        lines.append("")
        lines.append("When can I pick this up?")

        self.script_text.setPlainText("\n".join(lines))
        self.copy_btn.setEnabled(True)

    def _copy_script(self):
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self.script_text.toPlainText())
        QMessageBox.information(
            self, "Copied",
            "Phone script copied to clipboard.",
        )

    def _on_create_po(self):
        """Create a draft PO from the pick list and accept."""
        sid = self.supplier_combo.currentData()
        if not sid:
            QMessageBox.warning(
                self, "Error", "Please select a supply house."
            )
            return
        if not self._items:
            QMessageBox.warning(
                self, "Error", "Add at least one item to the pick list."
            )
            return

        try:
            user_id = self.current_user.id if self.current_user else None
            order = PurchaseOrder(
                order_number=self.repo.generate_order_number(),
                supplier_id=sid,
                parts_list_id=self._parts_list_id,
                status="draft",
                notes="Supply house pickup order",
                created_by=user_id,
            )
            order_id = self.repo.create_purchase_order(order)

            for item in self._items:
                oi = PurchaseOrderItem(
                    order_id=order_id,
                    part_id=item["part_id"],
                    quantity_ordered=item["qty"],
                    unit_cost=item["cost"],
                )
                self.repo.add_order_item(oi)

            QMessageBox.information(
                self, "Order Created",
                f"Purchase order {order.order_number} created as draft.\n"
                f"{len(self._items)} item(s) added.\n\n"
                f"Submit the order from Pending Orders when ready.",
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
