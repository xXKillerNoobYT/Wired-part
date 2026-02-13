"""New Orders page — 3-column layout: catalog, order builder, AI suggestions."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.models import Part, User
from wired_part.database.repository import Repository
from wired_part.utils.formatters import format_currency


class NewOrdersPage(QWidget):
    """Three-column order builder.

    Left: Parts catalog browser with search
    Middle: Order list builder with quantities
    Right: AI suggestions panel
    """

    def __init__(self, repo: Repository, current_user: User = None):
        super().__init__()
        self.repo = repo
        self.current_user = current_user
        self._catalog_parts: list[Part] = []
        self._order_items: list[dict] = []  # {part, qty, job_id}
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # Header
        header = QHBoxLayout()
        title = QLabel("New Order Builder")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        header.addWidget(title)

        header.addStretch()

        # Job selector (required for order)
        header.addWidget(QLabel("Job:"))
        self.job_combo = QComboBox()
        self.job_combo.setMinimumWidth(250)
        self.job_combo.addItem("— Select Job —", None)
        header.addWidget(self.job_combo)

        layout.addLayout(header)

        # 3-column splitter
        splitter = QSplitter(Qt.Horizontal)

        # ── Left: Parts Catalog ───────────────────────────────────
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        catalog_label = QLabel("Parts Catalog")
        catalog_label.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(catalog_label)

        # Search + category filter
        search_row = QHBoxLayout()
        self.catalog_search = QLineEdit()
        self.catalog_search.setPlaceholderText("Search parts...")
        self.catalog_search.textChanged.connect(self._filter_catalog)
        search_row.addWidget(self.catalog_search, 2)

        self.category_filter = QComboBox()
        self.category_filter.addItem("All Categories", None)
        self.category_filter.currentIndexChanged.connect(self._filter_catalog)
        search_row.addWidget(self.category_filter, 1)
        left_layout.addLayout(search_row)

        self.catalog_table = QTableWidget()
        self.catalog_table.setColumnCount(4)
        self.catalog_table.setHorizontalHeaderLabels(
            ["Part #", "Description", "Stock", "Cost"],
        )
        self.catalog_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.catalog_table.setSelectionMode(QTableWidget.SingleSelection)
        self.catalog_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.catalog_table.setAlternatingRowColors(True)
        self.catalog_table.setSortingEnabled(True)
        self.catalog_table.horizontalHeader().setStretchLastSection(True)
        self.catalog_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch,
        )
        self.catalog_table.doubleClicked.connect(self._on_add_to_order)
        left_layout.addWidget(self.catalog_table, 1)

        add_btn = QPushButton("Add to Order →")
        add_btn.clicked.connect(self._on_add_to_order)
        left_layout.addWidget(add_btn)

        splitter.addWidget(left)

        # ── Middle: Order Builder ─────────────────────────────────
        middle = QWidget()
        mid_layout = QVBoxLayout(middle)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        mid_layout.setSpacing(4)

        order_label = QLabel("Order List")
        order_label.setStyleSheet("font-weight: bold;")
        mid_layout.addWidget(order_label)

        self.order_table = QTableWidget()
        self.order_table.setColumnCount(5)
        self.order_table.setHorizontalHeaderLabels(
            ["Part #", "Description", "Qty", "Unit Cost", "Subtotal"],
        )
        self.order_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.order_table.setSelectionMode(QTableWidget.SingleSelection)
        self.order_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.order_table.setAlternatingRowColors(True)
        self.order_table.horizontalHeader().setStretchLastSection(True)
        self.order_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch,
        )
        mid_layout.addWidget(self.order_table, 1)

        # Qty adjustment row
        qty_row = QHBoxLayout()
        qty_row.addWidget(QLabel("Qty:"))
        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(0, 99999)
        self.qty_spin.setValue(1)
        qty_row.addWidget(self.qty_spin)

        update_qty_btn = QPushButton("Update Qty")
        update_qty_btn.clicked.connect(self._on_update_qty)
        qty_row.addWidget(update_qty_btn)

        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._on_remove_from_order)
        qty_row.addWidget(remove_btn)

        qty_row.addStretch()
        mid_layout.addLayout(qty_row)

        # Summary + actions
        self.order_summary = QLabel("0 items | Total: $0.00")
        self.order_summary.setStyleSheet(
            "font-weight: bold; font-size: 13px;"
        )
        mid_layout.addWidget(self.order_summary)

        action_row = QHBoxLayout()

        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._on_clear_order)
        action_row.addWidget(clear_btn)

        action_row.addStretch()

        self.confirm_btn = QPushButton("Confirm Order")
        self.confirm_btn.setStyleSheet(
            "background-color: #a6e3a1; color: black; "
            "font-weight: bold; padding: 8px 16px;"
        )
        self.confirm_btn.clicked.connect(self._on_confirm_order)
        action_row.addWidget(self.confirm_btn)

        mid_layout.addLayout(action_row)
        splitter.addWidget(middle)

        # ── Right: AI Suggestions ─────────────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        suggest_header = QHBoxLayout()
        suggest_label = QLabel("AI Suggestions")
        suggest_label.setStyleSheet("font-weight: bold;")
        suggest_header.addWidget(suggest_label)

        refresh_suggest = QPushButton("Refresh")
        refresh_suggest.clicked.connect(self._refresh_suggestions)
        suggest_header.addWidget(refresh_suggest)
        right_layout.addLayout(suggest_header)

        self.suggest_table = QTableWidget()
        self.suggest_table.setColumnCount(4)
        self.suggest_table.setHorizontalHeaderLabels(
            ["Part #", "Description", "Score", "Add"],
        )
        self.suggest_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.suggest_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.suggest_table.setAlternatingRowColors(True)
        self.suggest_table.horizontalHeader().setStretchLastSection(True)
        self.suggest_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch,
        )
        self.suggest_table.doubleClicked.connect(
            self._on_add_suggestion_to_order,
        )
        right_layout.addWidget(self.suggest_table, 1)

        self.no_suggest_label = QLabel(
            "Add parts to your order to see suggestions.\n\n"
            "Suggestions are based on historical purchase patterns."
        )
        self.no_suggest_label.setAlignment(Qt.AlignCenter)
        self.no_suggest_label.setStyleSheet(
            "color: #6c7086; padding: 20px;"
        )
        right_layout.addWidget(self.no_suggest_label)

        splitter.addWidget(right)

        # Stretch factors: left=2, mid=2, right=1
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 1)

        layout.addWidget(splitter, 1)

    def refresh(self):
        """Reload catalog and jobs."""
        self._load_jobs()
        self._load_categories()
        self._load_catalog()

    def _load_jobs(self):
        """Populate the job selector."""
        self.job_combo.blockSignals(True)
        current = self.job_combo.currentData()
        self.job_combo.clear()
        self.job_combo.addItem("— Select Job —", None)
        for job in self.repo.get_all_jobs(status="active"):
            self.job_combo.addItem(
                f"{job.job_number} — {job.name}", job.id,
            )
        if current:
            idx = self.job_combo.findData(current)
            if idx >= 0:
                self.job_combo.setCurrentIndex(idx)
        self.job_combo.blockSignals(False)

    def _load_categories(self):
        """Populate the category filter."""
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("All Categories", None)
        for cat in self.repo.get_all_categories():
            self.category_filter.addItem(cat.name, cat.id)
        self.category_filter.blockSignals(False)

    def _load_catalog(self):
        """Load all parts from catalog."""
        self._catalog_parts = self.repo.get_all_parts()
        self._filter_catalog()

    def _filter_catalog(self):
        """Filter catalog by search text and category."""
        search = self.catalog_search.text().strip().lower()
        cat_id = self.category_filter.currentData()

        filtered = self._catalog_parts
        if search:
            filtered = [
                p for p in filtered
                if search in p.part_number.lower()
                or search in (p.description or "").lower()
                or search in (p.name or "").lower()
            ]
        if cat_id:
            filtered = [p for p in filtered if p.category_id == cat_id]

        # Exclude deprecated parts
        filtered = [p for p in filtered if not p.deprecation_status]

        self._populate_catalog_table(filtered)

    def _populate_catalog_table(self, parts: list[Part]):
        self.catalog_table.setSortingEnabled(False)
        self.catalog_table.setRowCount(len(parts))
        for row, part in enumerate(parts):
            cells = [
                QTableWidgetItem(part.part_number),
                QTableWidgetItem(part.description or part.name),
                QTableWidgetItem(str(part.quantity)),
                QTableWidgetItem(format_currency(part.unit_cost)),
            ]
            # Highlight low stock
            if part.is_low_stock:
                for c in cells:
                    c.setForeground(Qt.red)
            for col, cell in enumerate(cells):
                self.table_item_align(cell, col)
                self.catalog_table.setItem(row, col, cell)
        self.catalog_table.setSortingEnabled(True)

    @staticmethod
    def table_item_align(cell, col):
        """Right-align numeric columns."""
        if col in (2, 3):
            cell.setTextAlignment(
                Qt.AlignmentFlag.AlignRight
                | Qt.AlignmentFlag.AlignVCenter
            )

    def _get_selected_catalog_part(self) -> Part | None:
        rows = self.catalog_table.selectionModel().selectedRows()
        if not rows:
            return None
        pn = self.catalog_table.item(rows[0].row(), 0)
        if not pn:
            return None
        for part in self._catalog_parts:
            if part.part_number == pn.text():
                return part
        return None

    def _on_add_to_order(self):
        """Add selected catalog part to order."""
        part = self._get_selected_catalog_part()
        if not part:
            return

        # Check if already in order
        for item in self._order_items:
            if item["part"].id == part.id:
                item["qty"] += 1
                self._refresh_order_table()
                return

        self._order_items.append({"part": part, "qty": 1})
        self._refresh_order_table()
        self._refresh_suggestions()

    def _on_add_suggestion_to_order(self):
        """Add a suggested part to the order."""
        rows = self.suggest_table.selectionModel().selectedRows()
        if not rows:
            return
        pn_item = self.suggest_table.item(rows[0].row(), 0)
        if not pn_item:
            return
        pn = pn_item.text()
        # Find the part in catalog
        for part in self._catalog_parts:
            if part.part_number == pn:
                # Check if already in order
                for item in self._order_items:
                    if item["part"].id == part.id:
                        item["qty"] += 1
                        self._refresh_order_table()
                        return
                self._order_items.append({"part": part, "qty": 1})
                self._refresh_order_table()
                self._refresh_suggestions()
                return

    def _refresh_order_table(self):
        """Refresh the order list table."""
        self.order_table.setRowCount(len(self._order_items))
        total = 0.0
        for row, item in enumerate(self._order_items):
            part = item["part"]
            qty = item["qty"]
            subtotal = qty * part.unit_cost
            total += subtotal

            cells = [
                QTableWidgetItem(part.part_number),
                QTableWidgetItem(part.description or part.name),
                QTableWidgetItem(str(qty)),
                QTableWidgetItem(format_currency(part.unit_cost)),
                QTableWidgetItem(format_currency(subtotal)),
            ]
            for col, cell in enumerate(cells):
                self.table_item_align(cell, col)
                self.order_table.setItem(row, col, cell)

        count = sum(item["qty"] for item in self._order_items)
        self.order_summary.setText(
            f"{len(self._order_items)} items ({count} units) | "
            f"Total: {format_currency(total)}"
        )

    def _on_update_qty(self):
        """Update quantity for selected order item."""
        rows = self.order_table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        if 0 <= idx < len(self._order_items):
            new_qty = self.qty_spin.value()
            if new_qty == 0:
                self._order_items.pop(idx)
            else:
                self._order_items[idx]["qty"] = new_qty
            self._refresh_order_table()

    def _on_remove_from_order(self):
        """Remove selected item from order."""
        rows = self.order_table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        if 0 <= idx < len(self._order_items):
            self._order_items.pop(idx)
            self._refresh_order_table()
            self._refresh_suggestions()

    def _on_clear_order(self):
        """Clear the entire order list."""
        if not self._order_items:
            return
        reply = QMessageBox.question(
            self, "Clear Order",
            "Clear all items from the order?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._order_items.clear()
            self._refresh_order_table()
            self._refresh_suggestions()

    def _on_confirm_order(self):
        """Confirm the order — create POs."""
        if not self._order_items:
            QMessageBox.information(
                self, "Empty Order",
                "Add parts to the order first.",
            )
            return

        job_id = self.job_combo.currentData()
        if not job_id:
            QMessageBox.warning(
                self, "No Job Selected",
                "Please select a job for this order.",
            )
            return

        # Check for zero-quantity items
        zero_items = [i for i in self._order_items if i["qty"] == 0]
        if zero_items:
            reply = QMessageBox.question(
                self, "Zero Quantity",
                f"{len(zero_items)} item(s) have zero quantity. "
                "Remove them and continue?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
            self._order_items = [
                i for i in self._order_items if i["qty"] > 0
            ]

        if not self._order_items:
            return

        # Group by supplier for potential splitting
        from wired_part.database.models import PurchaseOrder, PurchaseOrderItem
        supplier_groups: dict[int | None, list[dict]] = {}
        for item in self._order_items:
            # Look up the first linked supplier for this part
            part_suppliers = self.repo.get_part_suppliers(item["part"].id)
            sid = part_suppliers[0].supplier_id if part_suppliers else None
            supplier_groups.setdefault(sid, []).append(item)

        # Create one PO per supplier group
        created_pos = []
        for supplier_id, items in supplier_groups.items():
            if not supplier_id:
                # Skip parts with no linked supplier — warn the user
                part_names = [i["part"].display_name for i in items]
                QMessageBox.warning(
                    self, "No Supplier",
                    f"The following parts have no linked supplier "
                    f"and were skipped:\n• " + "\n• ".join(part_names),
                )
                continue
            try:
                po = PurchaseOrder(
                    supplier_id=supplier_id,
                    status="draft",
                    created_by=self.current_user.id if self.current_user else None,
                )
                po_id = self.repo.create_purchase_order(po)

                for item in items:
                    poi = PurchaseOrderItem(
                        order_id=po_id,
                        part_id=item["part"].id,
                        quantity_ordered=item["qty"],
                        unit_cost=item["part"].unit_cost,
                    )
                    self.repo.add_order_item(poi)

                created_pos.append(po_id)
            except Exception as e:
                QMessageBox.warning(
                    self, "Error Creating Order",
                    f"Failed to create PO: {e}",
                )
                return

        if not created_pos:
            QMessageBox.warning(
                self, "No Orders Created",
                "No purchase orders were created. Make sure parts "
                "have linked suppliers.",
            )
            return

        QMessageBox.information(
            self, "Orders Created",
            f"Created {len(created_pos)} purchase order(s) as draft.\n"
            "Go to Pending Orders to review and submit.",
        )

        self._order_items.clear()
        self._refresh_order_table()
        self._refresh_suggestions()

    def _refresh_suggestions(self):
        """Refresh the AI suggestions panel."""
        if not self._order_items:
            self.suggest_table.setRowCount(0)
            self.no_suggest_label.setVisible(True)
            self.suggest_table.setVisible(False)
            return

        from wired_part.agent.suggestions import get_suggestions
        part_ids = [item["part"].id for item in self._order_items]
        suggestions = get_suggestions(self.repo, part_ids, limit=8)

        self.no_suggest_label.setVisible(len(suggestions) == 0)
        self.suggest_table.setVisible(len(suggestions) > 0)

        self.suggest_table.setRowCount(len(suggestions))
        for row, s in enumerate(suggestions):
            cells = [
                QTableWidgetItem(s.get("part_number", "")),
                QTableWidgetItem(
                    s.get("description") or s.get("name", ""),
                ),
                QTableWidgetItem(f"{s.get('score', 0):.1f}"),
                QTableWidgetItem("Double-click to add"),
            ]
            # Style the score
            cells[2].setTextAlignment(
                Qt.AlignmentFlag.AlignRight
                | Qt.AlignmentFlag.AlignVCenter
            )
            cells[3].setForeground(Qt.GlobalColor.cyan)

            for col, cell in enumerate(cells):
                self.suggest_table.setItem(row, col, cell)
