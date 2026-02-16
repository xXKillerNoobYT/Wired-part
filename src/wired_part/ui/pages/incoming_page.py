"""Incoming / Receive page — fast checklist for receiving purchase orders."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.repository import Repository
from wired_part.utils.constants import ORDER_STATUS_LABELS
from wired_part.utils.formatters import format_currency


class IncomingPage(QWidget):
    """Receive items from submitted/partial purchase orders."""

    def __init__(self, repo: Repository, current_user=None):
        super().__init__()
        self.repo = repo
        self.current_user = current_user
        self._perms: set[str] = set()
        if current_user:
            self._perms = repo.get_user_permissions(current_user.id)
        self._orders = []
        self._current_order = None
        self._items = []
        self._receive_widgets = []  # (checkbox, spinbox, combo, secondary_combo)
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Header ─────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("Receive Incoming Orders")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("color: #a6adc8;")
        header.addWidget(self.summary_label)
        layout.addLayout(header)

        # ── Splitter: order list | items checklist ─────────────
        splitter = QSplitter(Qt.Horizontal)

        # Left: order list
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_label = QLabel("Awaiting Receipt")
        left_label.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(left_label)

        self.order_list = QListWidget()
        self.order_list.currentRowChanged.connect(self._on_order_selected)
        left_layout.addWidget(self.order_list)

        splitter.addWidget(left)

        # Right: items checklist
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.right_label = QLabel("Select an order to receive items")
        self.right_label.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(self.right_label)

        # Items table
        self.items_table = QTableWidget()
        cols = [
            "", "Part #", "Description", "Ordered", "Received",
            "Remaining", "Qty to Receive", "Allocate To", "Target",
        ]
        self.items_table.setColumnCount(len(cols))
        self.items_table.setHorizontalHeaderLabels(cols)
        self.items_table.setSelectionMode(QTableWidget.NoSelection)
        self.items_table.setAlternatingRowColors(True)
        self.items_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch
        )
        self.items_table.setColumnWidth(0, 30)   # Checkbox
        self.items_table.setColumnWidth(6, 100)  # Qty spinner
        self.items_table.setColumnWidth(7, 120)  # Allocate combo
        self.items_table.setColumnWidth(8, 150)  # Target combo
        right_layout.addWidget(self.items_table)

        # Bottom buttons
        btn_row = QHBoxLayout()

        self.suggest_btn = QPushButton("Smart Suggest")
        self.suggest_btn.setToolTip(
            "Auto-suggest allocation targets based on pending transfers, "
            "job needs, and low stock"
        )
        self.suggest_btn.clicked.connect(self._on_smart_suggest)
        self.suggest_btn.setEnabled(False)
        btn_row.addWidget(self.suggest_btn)

        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self._on_select_all)
        self.select_all_btn.setEnabled(False)
        btn_row.addWidget(self.select_all_btn)

        self.flag_wrong_btn = QPushButton("Flag Wrong Part")
        self.flag_wrong_btn.setToolTip(
            "Flag checked items as wrong parts and create a return"
        )
        self.flag_wrong_btn.setStyleSheet(
            "color: #f38ba8; font-weight: bold;"
        )
        self.flag_wrong_btn.clicked.connect(self._on_flag_wrong)
        self.flag_wrong_btn.setEnabled(False)
        btn_row.addWidget(self.flag_wrong_btn)

        btn_row.addStretch()

        self.receive_btn = QPushButton("Receive Selected")
        self.receive_btn.setStyleSheet(
            "background-color: #a6e3a1; color: #1e1e2e; font-weight: bold; "
            "padding: 8px 16px;"
        )
        self.receive_btn.clicked.connect(self._on_receive)
        self.receive_btn.setEnabled(False)
        self.receive_btn.setVisible("orders_receive" in self._perms)
        btn_row.addWidget(self.receive_btn)

        right_layout.addLayout(btn_row)
        splitter.addWidget(right)

        splitter.setSizes([250, 650])
        layout.addWidget(splitter)

    def refresh(self):
        """Reload receivable orders."""
        submitted = self.repo.get_all_purchase_orders(status="submitted")
        partial = self.repo.get_all_purchase_orders(status="partial")
        self._orders = submitted + partial

        self.order_list.clear()
        for order in self._orders:
            summary = self.repo.get_order_receive_summary(order.id)
            remaining = summary["total_ordered"] - summary["total_received"]
            status = ORDER_STATUS_LABELS.get(order.status, order.status)

            text = (
                f"{order.order_number} — {order.supplier_name}\n"
                f"  {status} | {remaining} items remaining"
            )
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, order.id)
            self.order_list.addItem(item)

        self.summary_label.setText(f"{len(self._orders)} orders awaiting receipt")

        # Clear right side
        if not self._orders:
            self.right_label.setText("No orders awaiting receipt")
            self.items_table.setRowCount(0)
            self._enable_buttons(False)

    def _on_order_selected(self, index):
        if index < 0 or index >= len(self._orders):
            self._current_order = None
            self.items_table.setRowCount(0)
            self._enable_buttons(False)
            return

        order_id = self.order_list.item(index).data(
            Qt.ItemDataRole.UserRole
        )
        self._current_order = self.repo.get_purchase_order_by_id(order_id)
        if not self._current_order:
            return

        self.right_label.setText(
            f"Items for {self._current_order.order_number} — "
            f"{self._current_order.supplier_name}"
        )
        self._load_order_items()
        self._enable_buttons(True)

    def _load_order_items(self):
        """Populate the items table with receivable line items."""
        self._items = self.repo.get_order_items(self._current_order.id)
        self._receive_widgets = []

        # Filter to only items with remaining quantity
        receivable = [i for i in self._items if i.quantity_remaining > 0]

        self.items_table.setRowCount(len(receivable))

        trucks = self.repo.get_all_trucks(active_only=True)
        active_jobs = self.repo.get_all_jobs(status="active")

        for row, item in enumerate(receivable):
            # Checkbox
            cb = QCheckBox()
            cb_widget = QWidget()
            cb_layout = QHBoxLayout(cb_widget)
            cb_layout.addWidget(cb)
            cb_layout.setAlignment(Qt.AlignCenter)
            cb_layout.setContentsMargins(0, 0, 0, 0)
            self.items_table.setCellWidget(row, 0, cb_widget)

            # Part info
            self.items_table.setItem(
                row, 1, QTableWidgetItem(item.part_number)
            )
            self.items_table.setItem(
                row, 2, QTableWidgetItem(item.part_description)
            )
            self.items_table.setItem(
                row, 3, self._num_item(item.quantity_ordered)
            )
            self.items_table.setItem(
                row, 4, self._num_item(item.quantity_received)
            )
            self.items_table.setItem(
                row, 5, self._num_item(item.quantity_remaining)
            )

            # Qty to receive spinner
            spin = QSpinBox()
            spin.setMinimum(0)
            spin.setMaximum(item.quantity_remaining)
            spin.setValue(item.quantity_remaining)
            self.items_table.setCellWidget(row, 6, spin)

            # Allocation combo
            alloc_combo = QComboBox()
            alloc_combo.addItem("Warehouse", "warehouse")
            alloc_combo.addItem("Truck", "truck")
            alloc_combo.addItem("Job", "job")
            self.items_table.setCellWidget(row, 7, alloc_combo)

            # Target combo (dynamic based on allocation)
            target_combo = QComboBox()
            target_combo.addItem("— N/A —", None)
            for t in trucks:
                target_combo.addItem(
                    f"{t.truck_number} — {t.name}", ("truck", t.id)
                )
            for j in active_jobs:
                target_combo.addItem(
                    f"{j.job_number} — {j.name}", ("job", j.id)
                )
            target_combo.setEnabled(False)
            self.items_table.setCellWidget(row, 8, target_combo)

            # Connect allocation change
            alloc_combo.currentIndexChanged.connect(
                lambda _, r=row, ac=alloc_combo, tc=target_combo:
                    self._on_alloc_changed(r, ac, tc)
            )

            self._receive_widgets.append(
                (cb, spin, alloc_combo, target_combo, item)
            )

    def _on_alloc_changed(self, row, alloc_combo, target_combo):
        alloc_type = alloc_combo.currentData()
        if alloc_type == "warehouse":
            target_combo.setEnabled(False)
            target_combo.setCurrentIndex(0)
        else:
            target_combo.setEnabled(True)
            # Auto-select first matching target type
            for i in range(target_combo.count()):
                data = target_combo.itemData(i)
                if data and data[0] == alloc_type:
                    target_combo.setCurrentIndex(i)
                    break

    def _on_smart_suggest(self):
        """Auto-fill allocation targets using smart suggestions."""
        for cb, spin, alloc_combo, target_combo, item in self._receive_widgets:
            suggestions = self.repo.get_allocation_suggestions(item.part_id)
            if suggestions:
                best = suggestions[0]
                if best["target"] == "warehouse":
                    alloc_combo.setCurrentIndex(0)
                    self._on_alloc_changed(0, alloc_combo, target_combo)
                elif best["target"] == "truck":
                    alloc_combo.setCurrentIndex(1)
                    self._on_alloc_changed(0, alloc_combo, target_combo)
                    # Find matching truck in target combo
                    for i in range(target_combo.count()):
                        data = target_combo.itemData(i)
                        if (data and data[0] == "truck"
                                and data[1] == best["target_id"]):
                            target_combo.setCurrentIndex(i)
                            break
                elif best["target"] == "job":
                    alloc_combo.setCurrentIndex(2)
                    self._on_alloc_changed(0, alloc_combo, target_combo)
                    for i in range(target_combo.count()):
                        data = target_combo.itemData(i)
                        if (data and data[0] == "job"
                                and data[1] == best["target_id"]):
                            target_combo.setCurrentIndex(i)
                            break
            cb.setChecked(True)

    def _on_select_all(self):
        for cb, spin, alloc_combo, target_combo, item in self._receive_widgets:
            cb.setChecked(True)

    def _on_receive(self):
        """Process checked items and receive them."""
        if not self._current_order:
            return

        receipts = []
        for cb, spin, alloc_combo, target_combo, item in self._receive_widgets:
            if not cb.isChecked():
                continue
            qty = spin.value()
            if qty <= 0:
                continue

            alloc_to = alloc_combo.currentData()
            truck_id = None
            job_id = None

            if alloc_to in ("truck", "job"):
                target_data = target_combo.currentData()
                if target_data and target_data[0] == "truck":
                    truck_id = target_data[1]
                elif target_data and target_data[0] == "job":
                    job_id = target_data[1]
                elif alloc_to != "warehouse":
                    # No target selected for truck/job
                    alloc_to = "warehouse"

            receipts.append({
                "order_item_id": item.id,
                "quantity_received": qty,
                "allocate_to": alloc_to,
                "allocate_truck_id": truck_id,
                "allocate_job_id": job_id,
            })

        if not receipts:
            QMessageBox.information(
                self, "No Items",
                "No items selected for receiving.",
            )
            return

        reply = QMessageBox.question(
            self, "Confirm Receive",
            f"Receive {len(receipts)} item(s) from "
            f"{self._current_order.order_number}?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            user_id = self.current_user.id if self.current_user else None
            count = self.repo.receive_order_items(
                self._current_order.id, receipts, user_id
            )
            QMessageBox.information(
                self, "Received",
                f"Successfully received {count} item(s).",
            )
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_flag_wrong(self):
        """Flag checked items as wrong parts and create a return."""
        if not self._current_order:
            return

        checked_items = []
        for cb, spin, alloc_combo, target_combo, item in self._receive_widgets:
            if cb.isChecked():
                checked_items.append(item)

        if not checked_items:
            QMessageBox.information(
                self, "No Items",
                "Check the items you want to flag as wrong parts.",
            )
            return

        part_names = ", ".join(i.part_number for i in checked_items[:5])
        if len(checked_items) > 5:
            part_names += f" (+{len(checked_items) - 5} more)"

        reply = QMessageBox.question(
            self, "Flag Wrong Parts",
            f"Flag {len(checked_items)} item(s) as wrong parts?\n"
            f"Parts: {part_names}\n\n"
            f"This will open the Return dialog pre-filled with these items.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        # Open ReturnDialog pre-filled with the wrong parts
        from wired_part.ui.dialogs.return_dialog import ReturnDialog
        from wired_part.database.models import ReturnAuthorizationItem

        dlg = ReturnDialog(
            self.repo, current_user=self.current_user, parent=self
        )

        # Pre-select the supplier from the order
        for i in range(dlg.supplier_combo.count()):
            if dlg.supplier_combo.itemData(i) == self._current_order.supplier_id:
                dlg.supplier_combo.setCurrentIndex(i)
                break

        # Pre-select the order in the related order combo
        for i in range(dlg.order_combo.count()):
            if dlg.order_combo.itemData(i) == self._current_order.id:
                dlg.order_combo.setCurrentIndex(i)
                break

        # Set reason to "wrong_part"
        for i in range(dlg.reason_combo.count()):
            if dlg.reason_combo.itemData(i) == "wrong_part":
                dlg.reason_combo.setCurrentIndex(i)
                break

        # Pre-fill items
        for item in checked_items:
            part = self.repo.get_part_by_id(item.part_id)
            if part:
                ra_item = ReturnAuthorizationItem(
                    ra_id=0,
                    part_id=part.id,
                    quantity=item.quantity_remaining,
                    unit_cost=item.unit_cost,
                    reason="wrong_part",
                    part_number=part.part_number,
                    part_description=part.description,
                )
                dlg._items.append(ra_item)

        dlg._refresh_items_table()

        if dlg.exec():
            self.refresh()

    def _enable_buttons(self, enabled):
        self.suggest_btn.setEnabled(enabled)
        self.select_all_btn.setEnabled(enabled)
        self.receive_btn.setEnabled(enabled)
        self.flag_wrong_btn.setEnabled(enabled)

    @staticmethod
    def _num_item(value: int) -> QTableWidgetItem:
        item = QTableWidgetItem()
        item.setData(Qt.ItemDataRole.DisplayRole, value)
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        return item
