"""Split Order dialog — intelligently split a parts list across suppliers.

Analyzes parts in a selected list, groups them by preferred supplier,
and creates separate POs for each supplier.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
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

from wired_part.database.models import PurchaseOrder, PurchaseOrderItem
from wired_part.database.repository import Repository
from wired_part.utils.formatters import format_currency


class SplitOrderDialog(QDialog):
    """Split a parts list across multiple suppliers.

    Groups parts by their supplier field (from the part record) and
    by explicit supplier preference, then creates separate draft POs
    for each supplier.
    """

    def __init__(self, repo: Repository, current_user=None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.current_user = current_user
        self._splits = {}  # {supplier_id: [item_dicts]}
        self._unassigned = []  # items with no clear supplier

        self.setWindowTitle("Split Order Across Suppliers")
        self.setMinimumSize(800, 600)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Header ────────────────────────────────────────────────
        header = QLabel("Intelligent Supplier Splitting")
        header.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(header)

        subtitle = QLabel(
            "Select a parts list to analyze. Parts are grouped by their "
            "preferred supplier. You can reassign parts before creating orders."
        )
        subtitle.setStyleSheet("color: #a6adc8; margin-bottom: 8px;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # ── Selection ─────────────────────────────────────────────
        form = QFormLayout()

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
        form.addRow("Parts List:", self.list_combo)

        self.fallback_combo = QComboBox()
        self.fallback_combo.addItem("(No fallback — leave unassigned)", None)
        suppliers = self.repo.get_all_suppliers()
        for s in suppliers:
            self.fallback_combo.addItem(
                f"{s.name} (pref: {s.preference_score})", s.id
            )
        self.fallback_combo.setToolTip(
            "Fallback supplier for parts with no preferred supplier set"
        )
        form.addRow("Fallback Supplier:", self.fallback_combo)

        layout.addLayout(form)

        # Analyze button
        analyze_row = QHBoxLayout()
        self.analyze_btn = QPushButton("Analyze & Split")
        self.analyze_btn.setStyleSheet(
            "background-color: #89b4fa; color: #1e1e2e; "
            "font-weight: bold; padding: 6px 16px;"
        )
        self.analyze_btn.clicked.connect(self._on_analyze)
        analyze_row.addWidget(self.analyze_btn)
        analyze_row.addStretch()
        layout.addLayout(analyze_row)

        # ── Results table ─────────────────────────────────────────
        self.results_label = QLabel("")
        self.results_label.setStyleSheet(
            "font-weight: bold; font-size: 13px; margin-top: 8px;"
        )
        layout.addWidget(self.results_label)

        cols = [
            "Supplier", "Part #", "Description", "Qty",
            "Unit Cost", "Line Total",
        ]
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(len(cols))
        self.results_table.setHorizontalHeaderLabels(cols)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch
        )
        layout.addWidget(self.results_table)

        # Summary
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("color: #a6adc8;")
        layout.addWidget(self.summary_label)

        # ── Buttons ───────────────────────────────────────────────
        btn_row = QHBoxLayout()

        self.create_btn = QPushButton("Create Split Orders")
        self.create_btn.setStyleSheet(
            "background-color: #a6e3a1; color: #1e1e2e; "
            "font-weight: bold; padding: 8px 16px;"
        )
        self.create_btn.clicked.connect(self._on_create_orders)
        self.create_btn.setEnabled(False)
        btn_row.addWidget(self.create_btn)

        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)

    def _on_analyze(self):
        """Analyze the parts list and split by supplier."""
        list_id = self.list_combo.currentData()
        if not list_id:
            QMessageBox.warning(
                self, "Error", "Please select a parts list."
            )
            return

        items = self.repo.get_parts_list_items(list_id)
        if not items:
            QMessageBox.warning(
                self, "No Items", "Selected parts list has no items."
            )
            return

        self._splits.clear()
        self._unassigned.clear()

        # Get all suppliers for lookup
        all_suppliers = {
            s.name.lower(): s
            for s in self.repo.get_all_suppliers()
        }
        supplier_by_id = {
            s.id: s for s in self.repo.get_all_suppliers()
        }

        fallback_id = self.fallback_combo.currentData()

        for item in items:
            part = self.repo.get_part_by_id(item.part_id)
            if not part:
                continue

            item_dict = {
                "part_id": part.id,
                "part_number": part.part_number,
                "desc": part.description,
                "qty": item.quantity,
                "cost": part.unit_cost,
            }

            # Try to match by part's supplier field
            supplier_id = None
            if part.supplier:
                supplier_key = part.supplier.strip().lower()
                if supplier_key in all_suppliers:
                    supplier_id = all_suppliers[supplier_key].id

            # Fallback
            if not supplier_id and fallback_id:
                supplier_id = fallback_id

            if supplier_id:
                if supplier_id not in self._splits:
                    self._splits[supplier_id] = []
                self._splits[supplier_id].append(item_dict)
            else:
                self._unassigned.append(item_dict)

        self._refresh_results(supplier_by_id)

    def _refresh_results(self, supplier_by_id=None):
        """Populate the results table with the split analysis."""
        if supplier_by_id is None:
            supplier_by_id = {
                s.id: s for s in self.repo.get_all_suppliers()
            }

        total_rows = sum(len(v) for v in self._splits.values())
        total_rows += len(self._unassigned)
        self.results_table.setRowCount(total_rows)

        row = 0
        num_suppliers = len(self._splits)
        grand_total = 0.0

        # Alternate supplier colors for visual grouping
        colors = [
            QColor("#89b4fa"),  # Blue
            QColor("#a6e3a1"),  # Green
            QColor("#f9e2af"),  # Yellow
            QColor("#f38ba8"),  # Red
            QColor("#cba6f7"),  # Purple
            QColor("#fab387"),  # Orange
        ]

        for i, (sid, group_items) in enumerate(self._splits.items()):
            supplier = supplier_by_id.get(sid)
            supplier_name = supplier.name if supplier else f"ID {sid}"
            color = colors[i % len(colors)]

            for j, item in enumerate(group_items):
                line_total = item["qty"] * item["cost"]
                grand_total += line_total

                # Show supplier name only on first row of group
                sup_cell = QTableWidgetItem(
                    supplier_name if j == 0 else ""
                )
                sup_cell.setForeground(color)
                if j == 0:
                    sup_cell.setData(
                        Qt.ItemDataRole.FontRole, None
                    )
                self.results_table.setItem(row, 0, sup_cell)

                self.results_table.setItem(
                    row, 1, QTableWidgetItem(item["part_number"])
                )
                self.results_table.setItem(
                    row, 2, QTableWidgetItem(item["desc"])
                )

                qty_item = QTableWidgetItem()
                qty_item.setData(
                    Qt.ItemDataRole.DisplayRole, item["qty"]
                )
                qty_item.setTextAlignment(
                    Qt.AlignRight | Qt.AlignVCenter
                )
                self.results_table.setItem(row, 3, qty_item)

                self.results_table.setItem(
                    row, 4, QTableWidgetItem(
                        format_currency(item["cost"])
                    )
                )
                self.results_table.setItem(
                    row, 5, QTableWidgetItem(
                        format_currency(line_total)
                    )
                )
                row += 1

        # Unassigned items
        if self._unassigned:
            for item in self._unassigned:
                line_total = item["qty"] * item["cost"]
                grand_total += line_total

                sup_cell = QTableWidgetItem("(Unassigned)")
                sup_cell.setForeground(QColor("#f38ba8"))
                self.results_table.setItem(row, 0, sup_cell)

                self.results_table.setItem(
                    row, 1, QTableWidgetItem(item["part_number"])
                )
                self.results_table.setItem(
                    row, 2, QTableWidgetItem(item["desc"])
                )

                qty_item = QTableWidgetItem()
                qty_item.setData(
                    Qt.ItemDataRole.DisplayRole, item["qty"]
                )
                qty_item.setTextAlignment(
                    Qt.AlignRight | Qt.AlignVCenter
                )
                self.results_table.setItem(row, 3, qty_item)

                self.results_table.setItem(
                    row, 4, QTableWidgetItem(
                        format_currency(item["cost"])
                    )
                )
                self.results_table.setItem(
                    row, 5, QTableWidgetItem(
                        format_currency(line_total)
                    )
                )
                row += 1

        # Update labels
        self.results_label.setText(
            f"Split into {num_suppliers} supplier order(s)"
        )
        unassigned_text = ""
        if self._unassigned:
            unassigned_text = (
                f"  |  {len(self._unassigned)} unassigned item(s) "
                f"will be skipped"
            )
        self.summary_label.setText(
            f"{total_rows} total items  |  "
            f"Grand Total: {format_currency(grand_total)}"
            f"{unassigned_text}"
        )

        self.create_btn.setEnabled(num_suppliers > 0)

    def _on_create_orders(self):
        """Create separate draft POs for each supplier group."""
        if not self._splits:
            return

        supplier_by_id = {
            s.id: s for s in self.repo.get_all_suppliers()
        }

        reply = QMessageBox.question(
            self, "Create Split Orders",
            f"Create {len(self._splits)} separate draft order(s)?\n\n"
            + "\n".join(
                f"  - {supplier_by_id.get(sid, type('', (), {'name': f'ID {sid}'})()).name}: "
                f"{len(items)} items"
                for sid, items in self._splits.items()
            ),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        created = []
        try:
            user_id = (
                self.current_user.id if self.current_user else None
            )
            list_id = self.list_combo.currentData()

            for sid, group_items in self._splits.items():
                supplier = supplier_by_id.get(sid)
                order = PurchaseOrder(
                    order_number=self.repo.generate_order_number(),
                    supplier_id=sid,
                    parts_list_id=list_id,
                    status="draft",
                    notes=(
                        f"Split order — "
                        f"{supplier.name if supplier else sid}"
                    ),
                    created_by=user_id,
                )
                order_id = self.repo.create_purchase_order(order)

                for item in group_items:
                    oi = PurchaseOrderItem(
                        order_id=order_id,
                        part_id=item["part_id"],
                        quantity_ordered=item["qty"],
                        unit_cost=item["cost"],
                    )
                    self.repo.add_order_item(oi)

                created.append(order.order_number)

            QMessageBox.information(
                self, "Orders Created",
                f"Created {len(created)} draft order(s):\n"
                + "\n".join(f"  - {on}" for on in created),
            )
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
