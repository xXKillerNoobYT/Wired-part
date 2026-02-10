"""Parts Catalog page — unified view of ALL parts across every location."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.repository import Repository
from wired_part.utils.formatters import format_currency


class PartsCatalogPage(QWidget):
    """Unified catalog showing every part across warehouse, trucks, and jobs.

    Each row represents a unique part with columns showing where it exists
    and the total quantity across all locations.
    """

    COLUMNS = [
        "Part #", "Description", "Category", "Supplier",
        "Warehouse Qty", "Truck Qty", "Job Qty", "Total Qty",
        "Unit Cost", "Total Value", "Locations",
    ]

    def __init__(self, repo: Repository):
        super().__init__()
        self.repo = repo
        self._catalog: list[dict] = []
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
            "Search all parts by number, description, or supplier..."
        )
        self.search_input.textChanged.connect(self._on_filter)
        toolbar.addWidget(self.search_input, 2)

        self.category_filter = QComboBox()
        self.category_filter.addItem("All Categories", None)
        self.category_filter.currentIndexChanged.connect(self._on_filter)
        toolbar.addWidget(self.category_filter, 1)

        self.location_filter = QComboBox()
        self.location_filter.addItem("All Locations", "all")
        self.location_filter.addItem("Warehouse Only", "warehouse")
        self.location_filter.addItem("Trucks Only", "trucks")
        self.location_filter.addItem("Jobs Only", "jobs")
        self.location_filter.currentIndexChanged.connect(self._on_filter)
        toolbar.addWidget(self.location_filter, 1)

        layout.addLayout(toolbar)

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
            1, QHeaderView.Stretch
        )
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
                "part_number": part.part_number,
                "description": part.description,
                "category_id": part.category_id,
                "category_name": part.category_name,
                "supplier": part.supplier,
                "unit_cost": part.unit_cost,
                "warehouse_qty": part.quantity,
                "truck_qty": 0,
                "job_qty": 0,
                "locations": set(),
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
                    # Part exists only on truck, not in main inventory
                    catalog[ti.part_id] = {
                        "part_id": ti.part_id,
                        "part_number": ti.part_number,
                        "description": ti.part_description,
                        "category_id": None,
                        "category_name": "",
                        "supplier": "",
                        "unit_cost": ti.unit_cost,
                        "warehouse_qty": 0,
                        "truck_qty": 0,
                        "job_qty": 0,
                        "locations": set(),
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
                        "part_number": jp.part_number,
                        "description": jp.part_description,
                        "category_id": None,
                        "category_name": "",
                        "supplier": "",
                        "unit_cost": jp.unit_cost_at_use,
                        "warehouse_qty": 0,
                        "truck_qty": 0,
                        "job_qty": 0,
                        "locations": set(),
                    }
                catalog[jp.part_id]["job_qty"] += jp.quantity_used
                catalog[jp.part_id]["locations"].add(
                    f"Job {job.job_number}"
                )

        self._catalog = list(catalog.values())

    def _on_filter(self):
        """Apply search, category, and location filters."""
        search = self.search_input.text().strip().lower()
        cat_id = self.category_filter.currentData()
        loc_filter = self.location_filter.currentData()

        filtered = []
        for entry in self._catalog:
            # Search filter
            if search:
                searchable = (
                    f"{entry['part_number']} {entry['description']} "
                    f"{entry['supplier']}"
                ).lower()
                if search not in searchable:
                    continue

            # Category filter
            if cat_id is not None and entry["category_id"] != cat_id:
                continue

            # Location filter
            if loc_filter == "warehouse" and entry["warehouse_qty"] <= 0:
                continue
            elif loc_filter == "trucks" and entry["truck_qty"] <= 0:
                continue
            elif loc_filter == "jobs" and entry["job_qty"] <= 0:
                continue

            filtered.append(entry)

        self._populate_table(filtered)

    def _populate_table(self, entries: list[dict]):
        """Fill the table with filtered catalog entries."""
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(entries))

        total_parts = len(entries)
        total_value = 0.0

        for row, entry in enumerate(entries):
            total_qty = (
                entry["warehouse_qty"]
                + entry["truck_qty"]
                + entry["job_qty"]
            )
            row_value = total_qty * entry["unit_cost"]
            total_value += row_value

            locations_str = ", ".join(sorted(entry["locations"]))

            items = [
                QTableWidgetItem(entry["part_number"]),
                QTableWidgetItem(entry["description"]),
                QTableWidgetItem(entry["category_name"]),
                QTableWidgetItem(entry["supplier"]),
                self._num_item(entry["warehouse_qty"]),
                self._num_item(entry["truck_qty"]),
                self._num_item(entry["job_qty"]),
                self._num_item(total_qty),
                QTableWidgetItem(format_currency(entry["unit_cost"])),
                QTableWidgetItem(format_currency(row_value)),
                QTableWidgetItem(locations_str),
            ]

            # Color code quantity columns
            if entry["warehouse_qty"] > 0:
                items[4].setForeground(Qt.GlobalColor.cyan)
            if entry["truck_qty"] > 0:
                items[5].setForeground(Qt.GlobalColor.green)
            if entry["job_qty"] > 0:
                items[6].setForeground(Qt.GlobalColor.yellow)

            for col, item in enumerate(items):
                self.table.setItem(row, col, item)

        self.table.setSortingEnabled(True)
        self.summary_label.setText(
            f"{total_parts} parts  |  "
            f"Total Value: {format_currency(total_value)}"
        )

    @staticmethod
    def _num_item(value: int) -> QTableWidgetItem:
        """Create a right-aligned numeric table item for proper sorting."""
        item = QTableWidgetItem()
        item.setData(Qt.ItemDataRole.DisplayRole, value)
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        return item
