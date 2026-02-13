"""Parts Catalog page — sub-tabbed container for Catalog, Brand Mgmt, Tag Maker."""

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
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.models import User
from wired_part.database.repository import Repository
from wired_part.utils.formatters import format_currency


class PartsCatalogPage(QWidget):
    """Container with sub-tabs: Catalog, Brand Management, Tag Maker.

    Follows the same sub-tab pattern as Job Tracking (Tab 2) in main_window.
    """

    def __init__(self, repo: Repository, current_user: User = None):
        super().__init__()
        self.repo = repo
        self.current_user = current_user
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.sub_tabs = QTabWidget()

        # Tab 0: Catalog
        self.catalog_page = CatalogSubPage(self.repo, self.current_user)
        self.sub_tabs.addTab(self.catalog_page, "Catalog")

        # Tab 1: Brand Management — lazy-loaded
        self._brand_page = None
        self._brand_placeholder = QWidget()
        self.sub_tabs.addTab(self._brand_placeholder, "Brand Management")

        # Tab 2: Tag Maker — lazy-loaded
        self._tag_page = None
        self._tag_placeholder = QWidget()
        self.sub_tabs.addTab(self._tag_placeholder, "Tag Maker")

        self.sub_tabs.currentChanged.connect(self._on_subtab_changed)
        layout.addWidget(self.sub_tabs)

    def _on_subtab_changed(self, index: int):
        """Lazy-load sub-pages and refresh them."""
        if index == 1 and self._brand_page is None:
            from wired_part.ui.pages.brand_management_page import (
                BrandManagementPage,
            )
            self._brand_page = BrandManagementPage(
                self.repo, self.current_user
            )
            self.sub_tabs.removeTab(1)
            self.sub_tabs.insertTab(1, self._brand_page, "Brand Management")
            self.sub_tabs.setCurrentIndex(1)
        elif index == 2 and self._tag_page is None:
            from wired_part.ui.pages.tag_maker_page import TagMakerPage
            self._tag_page = TagMakerPage(self.repo, self.current_user)
            self.sub_tabs.removeTab(2)
            self.sub_tabs.insertTab(2, self._tag_page, "Tag Maker")
            self.sub_tabs.setCurrentIndex(2)

        widget = self.sub_tabs.widget(index)
        if hasattr(widget, "refresh"):
            widget.refresh()

    def refresh(self):
        """Refresh the currently active sub-tab."""
        widget = self.sub_tabs.currentWidget()
        if hasattr(widget, "refresh"):
            widget.refresh()


class CatalogSubPage(QWidget):
    """Unified catalog showing every part across warehouse, trucks, and jobs.

    Enhanced for v8 with type filter, name column, quantity window,
    type/brand columns, and type-aware incomplete detection.
    """

    COLUMNS = [
        "Name", "Part #", "Description", "Type", "Brand", "Local PN",
        "Category", "Supplier",
        "Warehouse Qty", "Truck Qty", "Job Qty", "Total Qty",
        "Unit Cost", "Total Value", "Qty Window", "Locations",
    ]

    def __init__(self, repo: Repository, current_user: User = None):
        super().__init__()
        self.repo = repo
        self.current_user = current_user
        self._catalog: list[dict] = []
        self._perms: set[str] = set()
        if current_user:
            self._perms = repo.get_user_permissions(current_user.id)
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Header ──────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("Parts Catalog")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        header.addWidget(title)

        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("color: #a6adc8;")
        header.addStretch()
        header.addWidget(self.summary_label)
        layout.addLayout(header)

        # ── Toolbar ─────────────────────────────────────────────
        toolbar = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Search parts by name, number, description, brand, supplier..."
        )
        self.search_input.textChanged.connect(self._on_filter)
        toolbar.addWidget(self.search_input, 2)

        self.category_filter = QComboBox()
        self.category_filter.addItem("All Categories", None)
        self.category_filter.currentIndexChanged.connect(self._on_filter)
        toolbar.addWidget(self.category_filter, 1)

        self.type_filter = QComboBox()
        self.type_filter.addItem("All Types", "all")
        self.type_filter.addItem("General Only", "general")
        self.type_filter.addItem("Specific Only", "specific")
        self.type_filter.currentIndexChanged.connect(self._on_filter)
        toolbar.addWidget(self.type_filter, 1)

        self.location_filter = QComboBox()
        self.location_filter.addItem("All Locations", "all")
        self.location_filter.addItem("Warehouse Only", "warehouse")
        self.location_filter.addItem("Trucks Only", "trucks")
        self.location_filter.addItem("Jobs Only", "jobs")
        self.location_filter.currentIndexChanged.connect(self._on_filter)
        toolbar.addWidget(self.location_filter, 1)

        self.stock_filter = QComboBox()
        self.stock_filter.addItem("All Stock Levels", "all")
        self.stock_filter.addItem("Low Stock Only", "low")
        self.stock_filter.addItem("Out of Stock", "out")
        self.stock_filter.currentIndexChanged.connect(self._on_filter)
        toolbar.addWidget(self.stock_filter, 1)

        layout.addLayout(toolbar)

        # ── Action buttons ──────────────────────────────────────
        action_row = QHBoxLayout()

        self.add_btn = QPushButton("+ Add Part")
        self.add_btn.setStyleSheet(
            "background-color: #a6e3a1; color: #1e1e2e; "
            "font-weight: bold; padding: 6px 14px;"
        )
        self.add_btn.clicked.connect(self._on_add_part)
        self.add_btn.setVisible("parts_add" in self._perms)
        action_row.addWidget(self.add_btn)

        self.edit_btn = QPushButton("Edit Part")
        self.edit_btn.clicked.connect(self._on_edit_part)
        self.edit_btn.setEnabled(False)
        self.edit_btn.setVisible("parts_edit" in self._perms)
        action_row.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Delete Part")
        self.delete_btn.setStyleSheet("color: #f38ba8;")
        self.delete_btn.clicked.connect(self._on_delete_part)
        self.delete_btn.setEnabled(False)
        self.delete_btn.setVisible("parts_delete" in self._perms)
        action_row.addWidget(self.delete_btn)

        action_row.addStretch()

        self.incomplete_label = QLabel("")
        self.incomplete_label.setStyleSheet(
            "color: #f9e2af; font-weight: bold;"
        )
        action_row.addWidget(self.incomplete_label)

        layout.addLayout(action_row)

        # ── Parts Table ─────────────────────────────────────────
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
            0, QHeaderView.Stretch  # Name column stretches
        )
        self.table.selectionModel().selectionChanged.connect(
            self._on_selection_changed
        )
        self.table.doubleClicked.connect(self._on_edit_part)
        layout.addWidget(self.table)

    def refresh(self):
        """Rebuild the full catalog from all inventory sources."""
        self._load_categories()
        self._build_catalog()
        self._on_filter()

    def _load_categories(self):
        """Populate the category filter dropdown."""
        current = self.category_filter.currentData()
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("All Categories", None)
        for cat in self.repo.get_all_categories():
            self.category_filter.addItem(cat.name, cat.id)
        if current is not None:
            idx = self.category_filter.findData(current)
            if idx >= 0:
                self.category_filter.setCurrentIndex(idx)
        self.category_filter.blockSignals(False)

    def _build_catalog(self):
        """Aggregate parts from warehouse, trucks, and jobs into one catalog."""
        catalog = {}  # part_id -> catalog entry dict

        # 1. Warehouse parts (main parts table)
        for part in self.repo.get_all_parts():
            catalog[part.id] = {
                "part_id": part.id,
                "name": part.display_name,
                "part_number": part.part_number,
                "description": part.description,
                "part_type": part.part_type,
                "brand_name": part.brand_name,
                "local_part_number": part.local_part_number,
                "category_id": part.category_id,
                "category_name": part.category_name,
                "supplier": part.supplier,
                "unit_cost": part.unit_cost,
                "min_quantity": part.min_quantity,
                "max_quantity": part.max_quantity,
                "qty_window": part.quantity_window_str,
                "warehouse_qty": part.quantity,
                "truck_qty": 0,
                "job_qty": 0,
                "locations": set(),
                "is_incomplete": part.is_incomplete,
                "deprecation_status": part.deprecation_status,
            }
            if part.quantity > 0:
                loc = part.location or "Warehouse"
                catalog[part.id]["locations"].add(f"Warehouse ({loc})")

        # 2. Truck inventory
        trucks = self.repo.get_all_trucks(active_only=False)
        for truck in trucks:
            truck_inv = self.repo.get_truck_inventory(truck.id)
            for ti in truck_inv:
                if ti.part_id not in catalog:
                    catalog[ti.part_id] = {
                        "part_id": ti.part_id,
                        "name": ti.part_description or ti.part_number,
                        "part_number": ti.part_number,
                        "description": ti.part_description,
                        "part_type": "general",
                        "brand_name": "",
                        "local_part_number": "",
                        "category_id": None,
                        "category_name": "",
                        "supplier": "",
                        "unit_cost": ti.unit_cost,
                        "min_quantity": 0,
                        "max_quantity": 0,
                        "qty_window": "",
                        "warehouse_qty": 0,
                        "truck_qty": 0,
                        "job_qty": 0,
                        "locations": set(),
                        "is_incomplete": True,
                    }
                catalog[ti.part_id]["truck_qty"] += ti.quantity
                catalog[ti.part_id]["locations"].add(
                    f"Truck {truck.truck_number}"
                )

        # 3. Job parts
        active_jobs = self.repo.get_all_jobs(status="active")
        hold_jobs = self.repo.get_all_jobs(status="on_hold")
        for job in active_jobs + hold_jobs:
            job_parts = self.repo.get_job_parts(job.id)
            for jp in job_parts:
                if jp.part_id not in catalog:
                    catalog[jp.part_id] = {
                        "part_id": jp.part_id,
                        "name": jp.part_description or jp.part_number,
                        "part_number": jp.part_number,
                        "description": jp.part_description,
                        "part_type": "general",
                        "brand_name": "",
                        "local_part_number": "",
                        "category_id": None,
                        "category_name": "",
                        "supplier": "",
                        "unit_cost": jp.unit_cost_at_use,
                        "min_quantity": 0,
                        "max_quantity": 0,
                        "qty_window": "",
                        "warehouse_qty": 0,
                        "truck_qty": 0,
                        "job_qty": 0,
                        "locations": set(),
                        "is_incomplete": True,
                    }
                catalog[jp.part_id]["job_qty"] += jp.quantity_used
                catalog[jp.part_id]["locations"].add(
                    f"Job {job.job_number}"
                )

        self._catalog = list(catalog.values())

    def _on_filter(self):
        """Apply search, category, type, location, and stock filters."""
        search = self.search_input.text().strip().lower()
        cat_id = self.category_filter.currentData()
        type_filter = self.type_filter.currentData()
        loc_filter = self.location_filter.currentData()
        stock_filter = self.stock_filter.currentData()

        filtered = []
        for entry in self._catalog:
            # Search filter — includes name
            if search:
                searchable = (
                    f"{entry['name']} {entry['part_number']} "
                    f"{entry['description']} "
                    f"{entry['supplier']} {entry['brand_name']} "
                    f"{entry['local_part_number']}"
                ).lower()
                if search not in searchable:
                    continue

            # Category filter
            if cat_id is not None and entry["category_id"] != cat_id:
                continue

            # Type filter
            if type_filter == "general" and entry["part_type"] != "general":
                continue
            elif (
                type_filter == "specific"
                and entry["part_type"] != "specific"
            ):
                continue

            # Location filter
            if loc_filter == "warehouse" and entry["warehouse_qty"] <= 0:
                continue
            elif loc_filter == "trucks" and entry["truck_qty"] <= 0:
                continue
            elif loc_filter == "jobs" and entry["job_qty"] <= 0:
                continue

            # Stock filter
            if stock_filter == "low":
                if entry["min_quantity"] <= 0:
                    continue
                if entry["warehouse_qty"] >= entry["min_quantity"]:
                    continue
            elif stock_filter == "out":
                total = (
                    entry["warehouse_qty"]
                    + entry["truck_qty"]
                    + entry["job_qty"]
                )
                if total > 0:
                    continue

            filtered.append(entry)

        self._populate_table(filtered)

    def _on_selection_changed(self):
        """Enable/disable action buttons based on selection."""
        has_selection = len(self.table.selectionModel().selectedRows()) > 0
        self.edit_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)

    def _selected_part_id(self) -> int | None:
        """Return the part_id of the currently selected row."""
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        row_idx = rows[0].row()
        item = self.table.item(row_idx, 0)
        if item:
            return item.data(Qt.ItemDataRole.UserRole)
        return None

    def _on_add_part(self):
        """Open the Add Part dialog."""
        from wired_part.ui.dialogs.part_dialog import PartDialog
        dialog = PartDialog(self.repo, parent=self)
        if dialog.exec():
            self.refresh()

    def _on_edit_part(self):
        """Open the Edit Part dialog for the selected part."""
        part_id = self._selected_part_id()
        if part_id is None:
            return
        part = self.repo.get_part_by_id(part_id)
        if not part:
            return
        from wired_part.ui.dialogs.part_dialog import PartDialog
        dialog = PartDialog(self.repo, part=part, parent=self)
        if dialog.exec():
            self.refresh()

    def _on_delete_part(self):
        """Delete or deprecate the selected part.

        If the part has zero inventory everywhere (warehouse, trucks,
        no open jobs), it can be immediately deleted.  Otherwise,
        start the deprecation pipeline.
        """
        part_id = self._selected_part_id()
        if part_id is None:
            return
        part = self.repo.get_part_by_id(part_id)
        if not part:
            return

        display = part.display_name
        progress = self.repo.check_deprecation_progress(part_id)

        all_clear = (
            progress["job_quantity"] == 0
            and progress["truck_quantity"] == 0
            and progress["warehouse_quantity"] == 0
        )

        # Already archived → offer permanent delete
        if part.deprecation_status == "archived":
            reply = QMessageBox.question(
                self, "Remove Archived Part",
                f"'{display}' is archived.\n\n"
                "Would you like to permanently remove it from the catalog?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.repo.delete_part(part_id)
                self.refresh()
            return

        # Already in deprecation pipeline → offer cancel or advance
        if part.deprecation_status:
            new_status = self.repo.advance_deprecation(part_id)
            if new_status == "archived":
                QMessageBox.information(
                    self, "Part Archived",
                    f"'{display}' has been archived.\n\n"
                    "You can remove it permanently by clicking "
                    "Delete Part again.",
                )
                self.refresh()
                return
            reply = QMessageBox.question(
                self, "Deprecation In Progress",
                f"'{display}' is being deprecated "
                f"(status: {new_status}).\n\n"
                "Would you like to cancel the deprecation?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.repo.cancel_deprecation(part_id)
                self.refresh()
            return

        # ── Part has zero inventory everywhere → offer direct delete ──
        if all_clear:
            reply = QMessageBox.question(
                self, "Delete Part",
                f"Delete '{display}' from the catalog?\n\n"
                "This part has zero inventory across warehouse, trucks, "
                "and no open jobs using it.\n\n"
                "This action cannot be undone.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.repo.delete_part(part_id)
                self.refresh()
            return

        # ── Part still has inventory → start deprecation pipeline ──
        reply = QMessageBox.question(
            self, "Deprecate Part",
            f"'{display}' still has inventory in use:\n\n"
            f"  Items on open jobs: {progress['job_quantity']}\n"
            f"  On trucks: {progress['truck_quantity']}\n"
            f"  Warehouse: {progress['warehouse_quantity']}\n\n"
            "Would you like to start deprecating this part?\n"
            "This will prevent new orders and phase it out.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.repo.start_part_deprecation(part_id)
        new_status = self.repo.advance_deprecation(part_id)

        if new_status == "archived":
            QMessageBox.information(
                self, "Part Archived",
                f"'{display}' has been archived (all inventory was zero).\n\n"
                "Click Delete Part again to permanently remove it.",
            )
        else:
            QMessageBox.information(
                self, "Deprecation Started",
                f"'{display}' deprecation started.\n"
                f"Current status: {new_status}\n\n"
                "The part will be phased out as inventory reaches zero.",
            )
        self.refresh()

    def _populate_table(self, entries: list[dict]):
        """Fill the table with filtered catalog entries."""
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(entries))

        total_parts = len(entries)
        total_value = 0.0
        incomplete_count = 0

        for row, entry in enumerate(entries):
            total_qty = (
                entry["warehouse_qty"]
                + entry["truck_qty"]
                + entry["job_qty"]
            )
            row_value = total_qty * entry["unit_cost"]
            total_value += row_value

            if entry.get("is_incomplete"):
                incomplete_count += 1

            locations_str = ", ".join(sorted(entry["locations"]))
            type_badge = "S" if entry["part_type"] == "specific" else "G"

            items = [
                QTableWidgetItem(entry["name"]),
                QTableWidgetItem(entry["part_number"]),
                QTableWidgetItem(entry["description"]),
                QTableWidgetItem(type_badge),
                QTableWidgetItem(entry["brand_name"]),
                QTableWidgetItem(entry["local_part_number"]),
                QTableWidgetItem(entry["category_name"]),
                QTableWidgetItem(entry["supplier"]),
                self._num_item(entry["warehouse_qty"]),
                self._num_item(entry["truck_qty"]),
                self._num_item(entry["job_qty"]),
                self._num_item(total_qty),
                QTableWidgetItem(format_currency(entry["unit_cost"])),
                QTableWidgetItem(format_currency(row_value)),
                QTableWidgetItem(entry["qty_window"]),
                QTableWidgetItem(locations_str),
            ]

            # Store part_id on the first column for lookups
            items[0].setData(Qt.ItemDataRole.UserRole, entry["part_id"])

            # Type badge color
            if entry["part_type"] == "specific":
                items[3].setForeground(QColor("#89b4fa"))  # Blue
            else:
                items[3].setForeground(QColor("#a6e3a1"))  # Green

            # Color code quantity columns
            if entry["warehouse_qty"] > 0:
                items[8].setForeground(Qt.GlobalColor.cyan)
            if entry["truck_qty"] > 0:
                items[9].setForeground(Qt.GlobalColor.green)
            if entry["job_qty"] > 0:
                items[10].setForeground(Qt.GlobalColor.yellow)

            # Low stock highlighting
            if (
                entry["min_quantity"] > 0
                and entry["warehouse_qty"] < entry["min_quantity"]
            ):
                for item in items:
                    item.setBackground(QColor(60, 20, 20))

            # Incomplete data highlighting
            if entry.get("is_incomplete"):
                items[0].setForeground(QColor("#f9e2af"))

            # Deprecation status highlighting
            dep_status = entry.get("deprecation_status")
            if dep_status == "pending":
                for item in items:
                    item.setForeground(QColor("#fab387"))  # Orange
            elif dep_status == "winding_down":
                for item in items:
                    item.setForeground(QColor("#f38ba8"))  # Red
            elif dep_status in ("zero_stock", "archived"):
                for item in items:
                    item.setForeground(QColor("#6c7086"))  # Gray
                    item.setBackground(QColor(30, 30, 30))

            for col, item in enumerate(items):
                self.table.setItem(row, col, item)

        self.table.setSortingEnabled(True)
        self.summary_label.setText(
            f"{total_parts} parts  |  "
            f"Total Value: {format_currency(total_value)}"
        )

        if incomplete_count > 0:
            self.incomplete_label.setText(
                f"\u26a0 Incomplete data: {incomplete_count} part(s)"
            )
        else:
            self.incomplete_label.setText("")

    @staticmethod
    def _num_item(value: int) -> QTableWidgetItem:
        """Create a right-aligned numeric table item for proper sorting."""
        item = QTableWidgetItem()
        item.setData(Qt.ItemDataRole.DisplayRole, value)
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        return item
