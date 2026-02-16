"""Procurement Planner — drag-plan reorder items across supplier columns."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.models import (
    PurchaseOrder,
    PurchaseOrderItem,
    User,
)
from wired_part.database.repository import Repository


class ProcurementPlannerPage(QWidget):
    """Plan purchases by assigning low-stock parts to suppliers."""

    def __init__(self, repo: Repository, current_user: User, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.current_user = current_user
        if current_user:
            self._perms = repo.get_user_permissions(current_user.id)
        else:
            self._perms = set()
        self._can_see_dollars = "show_dollar_values" in self._perms
        self._parts_data: list = []  # Part objects for the table
        self._supplier_columns: dict[int, QListWidget] = {}  # sid → list
        self._supplier_names: dict[int, str] = {}
        self._setup_ui()

    # ── UI ──────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("Procurement Planner")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        # Top controls
        top_row = QHBoxLayout()

        load_low_btn = QPushButton("Load Low Stock Parts")
        load_low_btn.setToolTip(
            "Populate the table with parts below min quantity"
        )
        load_low_btn.clicked.connect(self._load_low_stock)
        top_row.addWidget(load_low_btn)

        auto_assign_btn = QPushButton("Auto-Assign to Suppliers")
        auto_assign_btn.setToolTip(
            "Automatically assign parts to their linked suppliers"
        )
        auto_assign_btn.clicked.connect(self._auto_assign)
        top_row.addWidget(auto_assign_btn)

        generate_btn = QPushButton("Generate Draft POs")
        generate_btn.setToolTip(
            "Create draft purchase orders from the current assignment"
        )
        generate_btn.clicked.connect(self._generate_pos)
        top_row.addWidget(generate_btn)

        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_all)
        top_row.addWidget(clear_btn)

        top_row.addStretch()
        layout.addLayout(top_row)

        # Main split: parts table (left) + supplier columns (right)
        content_row = QHBoxLayout()

        # Left: Parts needing reorder
        left_group = QGroupBox("Parts Needing Reorder")
        left_layout = QVBoxLayout()

        self.parts_table = QTableWidget()
        self.parts_table.setColumnCount(5)
        self.parts_table.setHorizontalHeaderLabels([
            "Part", "Current Qty", "Min Qty", "Need Qty", "Unit Cost",
        ])
        self.parts_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.parts_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.parts_table.setMinimumHeight(3 * 30 + 30 + 2)
        self.parts_table.horizontalHeader().setStretchLastSection(True)
        self.parts_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch,
        )

        left_layout.addWidget(self.parts_table)

        self.parts_count_label = QLabel("0 parts")
        left_layout.addWidget(self.parts_count_label)

        left_group.setLayout(left_layout)
        content_row.addWidget(left_group, 3)

        # Right: Supplier columns in a scroll area
        right_group = QGroupBox("Supplier Assignments")
        right_layout = QVBoxLayout()

        self.suppliers_scroll = QScrollArea()
        self.suppliers_scroll.setWidgetResizable(True)

        self.suppliers_container = QWidget()
        self.suppliers_row = QHBoxLayout(self.suppliers_container)
        self.suppliers_row.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Unassigned column always present
        unassigned_col = QVBoxLayout()
        unassigned_col.addWidget(QLabel("Unassigned"))
        self.unassigned_list = QListWidget()
        self.unassigned_list.setMinimumWidth(160)
        self.unassigned_list.setMinimumHeight(3 * 30 + 2)
        unassigned_col.addWidget(self.unassigned_list)
        self.unassigned_total = QLabel("$0.00" if self._can_see_dollars else "")
        self.unassigned_total.setVisible(self._can_see_dollars)
        unassigned_col.addWidget(self.unassigned_total)
        self.suppliers_row.addLayout(unassigned_col)

        self.suppliers_scroll.setWidget(self.suppliers_container)
        right_layout.addWidget(self.suppliers_scroll)

        right_group.setLayout(right_layout)
        content_row.addWidget(right_group, 4)

        layout.addLayout(content_row, 1)

        # Status
        self.status_label = QLabel("")
        self.status_label.setObjectName("SettingsStatusLabel")
        layout.addWidget(self.status_label)

    # ── Data ────────────────────────────────────────────────────

    def refresh(self):
        """Called when tab is selected."""
        pass  # Don't auto-load — user clicks "Load Low Stock"

    def _load_low_stock(self):
        """Populate table with parts below min quantity."""
        self._parts_data = self.repo.get_low_stock_parts()
        self._populate_parts_table()
        self._build_supplier_columns()
        self._clear_assignments()
        self.status_label.setText(
            f"Loaded {len(self._parts_data)} low-stock parts."
        )

    def _populate_parts_table(self):
        self.parts_table.setRowCount(len(self._parts_data))
        for row, p in enumerate(self._parts_data):
            name = p.name or p.part_number or f"#{p.id}"
            self.parts_table.setItem(row, 0, QTableWidgetItem(name))

            qty_item = QTableWidgetItem(str(p.quantity))
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            self.parts_table.setItem(row, 1, qty_item)

            min_item = QTableWidgetItem(str(p.min_quantity))
            min_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            self.parts_table.setItem(row, 2, min_item)

            need = max(0, p.min_quantity - p.quantity)
            need_item = QTableWidgetItem(str(need))
            need_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            self.parts_table.setItem(row, 3, need_item)

            cost_text = f"${p.unit_cost:.2f}" if self._can_see_dollars else "—"
            cost_item = QTableWidgetItem(cost_text)
            cost_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            self.parts_table.setItem(row, 4, cost_item)

        self.parts_count_label.setText(
            f"{len(self._parts_data)} parts"
        )

    def _build_supplier_columns(self):
        """Create a list widget per active supplier."""
        # Clear existing supplier columns (not unassigned)
        for sid, lw in self._supplier_columns.items():
            lw.parent().deleteLater()  # delete the container widget

        self._supplier_columns.clear()
        self._supplier_names.clear()

        suppliers = [
            s for s in self.repo.get_all_suppliers() if s.is_supply_house
        ]
        if not suppliers:
            suppliers = self.repo.get_all_suppliers()

        for s in suppliers:
            self._supplier_names[s.id] = s.name

            col_widget = QWidget()
            col_layout = QVBoxLayout(col_widget)
            col_layout.setContentsMargins(4, 0, 4, 0)

            header = QLabel(s.name)
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col_layout.addWidget(header)

            lw = QListWidget()
            lw.setMinimumWidth(160)
            lw.setMinimumHeight(3 * 30 + 2)
            col_layout.addWidget(lw)

            total_label = QLabel("$0.00" if self._can_see_dollars else "")
            total_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            total_label.setObjectName(f"supplier_total_{s.id}")
            total_label.setVisible(self._can_see_dollars)
            col_layout.addWidget(total_label)

            self.suppliers_row.addWidget(col_widget)
            self._supplier_columns[s.id] = lw

    def _clear_assignments(self):
        """Clear all supplier lists and unassigned list."""
        self.unassigned_list.clear()
        for lw in self._supplier_columns.values():
            lw.clear()
        self._update_totals()

    # ── Auto-Assign ─────────────────────────────────────────────

    def _auto_assign(self):
        """Assign parts to suppliers based on part_suppliers links."""
        self._clear_assignments()

        assigned = 0
        unassigned = 0

        for p in self._parts_data:
            need = max(0, p.min_quantity - p.quantity)
            if need <= 0:
                continue

            part_label = f"{p.name or p.part_number} x{need}"
            links = self.repo.get_part_suppliers(p.id)

            # Filter to suppliers we have columns for
            valid = [
                lnk for lnk in links
                if lnk.supplier_id in self._supplier_columns
            ]

            if len(valid) == 1:
                # Single supplier — assign directly
                sid = valid[0].supplier_id
                item = QListWidgetItem(part_label)
                item.setData(Qt.UserRole, {
                    "part_id": p.id,
                    "quantity": need,
                    "unit_cost": p.unit_cost,
                })
                self._supplier_columns[sid].addItem(item)
                assigned += 1
            elif len(valid) > 1:
                # Multiple — assign to first (highest alphabetical)
                sid = valid[0].supplier_id
                item = QListWidgetItem(part_label)
                item.setData(Qt.UserRole, {
                    "part_id": p.id,
                    "quantity": need,
                    "unit_cost": p.unit_cost,
                })
                self._supplier_columns[sid].addItem(item)
                assigned += 1
            else:
                # No link — unassigned
                item = QListWidgetItem(part_label)
                item.setData(Qt.UserRole, {
                    "part_id": p.id,
                    "quantity": need,
                    "unit_cost": p.unit_cost,
                })
                self.unassigned_list.addItem(item)
                unassigned += 1

        self._update_totals()
        self.status_label.setText(
            f"Auto-assigned {assigned} parts, "
            f"{unassigned} unassigned."
        )

    def _update_totals(self):
        """Recalculate running totals for each supplier column."""
        # Unassigned total
        total = 0.0
        for i in range(self.unassigned_list.count()):
            data = self.unassigned_list.item(i).data(Qt.UserRole)
            if data:
                total += data.get("quantity", 0) * data.get("unit_cost", 0)
        if self._can_see_dollars:
            self.unassigned_total.setText(f"${total:,.2f}")

        # Supplier totals
        for sid, lw in self._supplier_columns.items():
            total = 0.0
            for i in range(lw.count()):
                data = lw.item(i).data(Qt.UserRole)
                if data:
                    total += (
                        data.get("quantity", 0) * data.get("unit_cost", 0)
                    )
            # Find the total label
            container = lw.parent()
            if container:
                label = container.findChild(
                    QLabel, f"supplier_total_{sid}"
                )
                if label and self._can_see_dollars:
                    label.setText(f"${total:,.2f}")

    # ── Generate POs ────────────────────────────────────────────

    def _generate_pos(self):
        """Create draft purchase orders from current assignments."""
        created = 0
        for sid, lw in self._supplier_columns.items():
            if lw.count() == 0:
                continue

            # Create draft PO
            order_number = self.repo.generate_order_number()
            order = PurchaseOrder(
                order_number=order_number,
                supplier_id=sid,
                status="draft",
                notes="Generated by Procurement Planner",
                created_by=self.current_user.id,
            )
            oid = self.repo.create_purchase_order(order)

            # Add line items
            for i in range(lw.count()):
                data = lw.item(i).data(Qt.UserRole)
                if data:
                    item = PurchaseOrderItem(
                        order_id=oid,
                        part_id=data["part_id"],
                        quantity_ordered=data["quantity"],
                        unit_cost=data["unit_cost"],
                    )
                    self.repo.add_order_item(item)

            created += 1

        if created:
            self.status_label.setText(
                f"Created {created} draft purchase order(s). "
                f"View them in Warehouse \u2192 Supplier Orders."
            )
        else:
            self.status_label.setText(
                "No supplier assignments to generate POs from."
            )

    def _clear_all(self):
        """Clear all parts and assignments."""
        self._parts_data = []
        self.parts_table.setRowCount(0)
        self.parts_count_label.setText("0 parts")
        self._clear_assignments()
        self.status_label.setText("Cleared.")
