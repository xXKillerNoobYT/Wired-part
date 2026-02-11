"""Truck Inventory Manager — per-truck stock management with min/max levels."""

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
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.models import TruckInventory, User
from wired_part.database.repository import Repository
from wired_part.utils.formatters import format_currency


class TruckInventoryManagerPage(QWidget):
    """Manager for truck stock levels — add parts, set min/max, set qty."""

    COLUMNS = [
        "Part #", "Description", "On Hand", "Min", "Max",
        "Unit Cost", "Status",
    ]

    # Status colors
    COLOR_UNDER = QColor("#f38ba8")   # Red: under minimum
    COLOR_OVER = QColor("#f9e2af")    # Yellow: over maximum
    COLOR_OK = QColor("#a6e3a1")      # Green: within range

    def __init__(self, repo: Repository, current_user: User = None):
        super().__init__()
        self.repo = repo
        self.current_user = current_user
        self._items: list[TruckInventory] = []
        self._setup_ui()
        self._load_trucks()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # ── Header ────────────────────────────────────────────────
        header = QHBoxLayout()

        header.addWidget(QLabel("Truck:"))
        self.truck_combo = QComboBox()
        self.truck_combo.setMinimumWidth(250)
        self.truck_combo.currentIndexChanged.connect(self._on_truck_changed)
        header.addWidget(self.truck_combo)

        header.addSpacing(16)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search parts on truck...")
        self.search_input.textChanged.connect(self._on_search)
        header.addWidget(self.search_input, 1)

        header.addSpacing(16)

        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("color: #a6adc8;")
        header.addWidget(self.summary_label)

        layout.addLayout(header)

        # ── Action bar ────────────────────────────────────────────
        actions = QHBoxLayout()

        self.add_part_btn = QPushButton("+ Add Part to Truck")
        self.add_part_btn.setToolTip(
            "Add a part from the catalog to this truck's inventory"
        )
        self.add_part_btn.clicked.connect(self._on_add_part)
        actions.addWidget(self.add_part_btn)

        self.set_qty_btn = QPushButton("Set Qty")
        self.set_qty_btn.setToolTip(
            "Set the current quantity for the selected part"
        )
        self.set_qty_btn.clicked.connect(self._on_set_qty)
        self.set_qty_btn.setEnabled(False)
        actions.addWidget(self.set_qty_btn)

        self.set_levels_btn = QPushButton("Set Min/Max")
        self.set_levels_btn.setToolTip(
            "Set min/max stock levels for the selected part"
        )
        self.set_levels_btn.clicked.connect(self._on_set_levels)
        self.set_levels_btn.setEnabled(False)
        actions.addWidget(self.set_levels_btn)

        self.audit_btn = QPushButton("Fast Audit")
        self.audit_btn.setToolTip("Run a fast audit on this truck")
        self.audit_btn.clicked.connect(self._on_audit)
        actions.addWidget(self.audit_btn)

        actions.addStretch()
        layout.addLayout(actions)

        # ── Table ─────────────────────────────────────────────────
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
            1, QHeaderView.Stretch,
        )
        self.table.selectionModel().selectionChanged.connect(
            self._on_selection_changed,
        )
        layout.addWidget(self.table, 1)

    def _load_trucks(self):
        """Populate the truck selector."""
        trucks = self.repo.get_all_trucks(active_only=True)
        self.truck_combo.blockSignals(True)
        self.truck_combo.clear()
        self.truck_combo.addItem("— Select Truck —", None)
        for truck in trucks:
            label = f"{truck.truck_number} — {truck.name}"
            if truck.assigned_user_name:
                label += f" ({truck.assigned_user_name})"
            self.truck_combo.addItem(label, truck.id)
        self.truck_combo.blockSignals(False)

    def refresh(self):
        """Reload data."""
        self._load_trucks()
        self._on_truck_changed()

    def _on_truck_changed(self, _index=None):
        """Load inventory for the selected truck."""
        truck_id = self.truck_combo.currentData()
        if not truck_id:
            self._items = []
            self._populate_table([])
            return

        self._items = self.repo.get_truck_inventory_with_levels(truck_id)
        self._on_search()

    def _on_search(self):
        """Filter displayed items by search text."""
        search = self.search_input.text().strip().lower()
        if search:
            filtered = [
                i for i in self._items
                if search in i.part_number.lower()
                or search in i.part_description.lower()
            ]
        else:
            filtered = self._items
        self._populate_table(filtered)

    def _populate_table(self, items: list[TruckInventory]):
        """Fill the table with truck inventory items."""
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(items))

        total_value = 0.0
        under_count = 0
        over_count = 0

        for row, item in enumerate(items):
            value = item.quantity * item.unit_cost
            total_value += value

            # Determine status
            if item.min_quantity > 0 and item.quantity < item.min_quantity:
                status_text = "Under Min"
                status_color = self.COLOR_UNDER
                under_count += 1
            elif item.max_quantity > 0 and item.quantity > item.max_quantity:
                status_text = "Over Max"
                status_color = self.COLOR_OVER
                over_count += 1
            else:
                status_text = "OK"
                status_color = self.COLOR_OK

            cells = [
                QTableWidgetItem(item.part_number),
                QTableWidgetItem(item.part_description),
                self._num_item(item.quantity),
                self._num_item(item.min_quantity),
                self._num_item(item.max_quantity),
                QTableWidgetItem(format_currency(item.unit_cost)),
                QTableWidgetItem(status_text),
            ]

            # Color the row based on status
            for cell in cells:
                cell.setForeground(status_color)

            for col, cell in enumerate(cells):
                self.table.setItem(row, col, cell)

        self.table.setSortingEnabled(True)

        self.summary_label.setText(
            f"{len(items)} parts  |  "
            f"Value: {format_currency(total_value)}  |  "
            f"Under: {under_count}  |  Over: {over_count}"
        )

    @staticmethod
    def _num_item(value: int) -> QTableWidgetItem:
        """Create a right-aligned numeric table item."""
        item = QTableWidgetItem()
        item.setData(Qt.ItemDataRole.DisplayRole, value)
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        return item

    def _selected_item(self) -> TruckInventory | None:
        """Return the currently selected truck inventory item."""
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        # Find matching item by part number (visible in column 0)
        pn = self.table.item(rows[0].row(), 0)
        if not pn:
            return None
        part_number = pn.text()
        for item in self._items:
            if item.part_number == part_number:
                return item
        return None

    def _on_selection_changed(self):
        has_sel = bool(self.table.selectionModel().selectedRows())
        self.set_qty_btn.setEnabled(has_sel)
        self.set_levels_btn.setEnabled(has_sel)

    def _on_add_part(self):
        """Add a part from catalog to this truck."""
        truck_id = self.truck_combo.currentData()
        if not truck_id:
            QMessageBox.information(
                self, "No Truck", "Select a truck first.",
            )
            return

        from wired_part.ui.dialogs.part_picker_dialog import PartPickerDialog
        dlg = PartPickerDialog(self.repo, parent=self)
        if dlg.exec():
            part = dlg.selected_part
            if part:
                # Check if already on truck
                existing = [
                    i for i in self._items if i.part_id == part.id
                ]
                if existing:
                    QMessageBox.information(
                        self, "Already On Truck",
                        f"{part.part_number} is already on this truck.",
                    )
                    return
                self.repo.add_to_truck_inventory(truck_id, part.id, 0)
                self._on_truck_changed()

    def _on_set_qty(self):
        """Set the current quantity for the selected part."""
        item = self._selected_item()
        if not item:
            return

        truck_id = self.truck_combo.currentData()
        if not truck_id:
            return

        from PySide6.QtWidgets import QInputDialog
        qty, ok = QInputDialog.getInt(
            self, "Set Quantity",
            f"Set current quantity for {item.part_number}:",
            value=item.quantity, min=0, max=99999,
        )
        if ok:
            self.repo.set_truck_inventory_quantity(truck_id, item.part_id, qty)
            self._on_truck_changed()

    def _on_set_levels(self):
        """Set min/max stock levels for the selected part."""
        item = self._selected_item()
        if not item:
            return

        truck_id = self.truck_combo.currentData()
        if not truck_id:
            return

        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Min/Max for {item.part_number}")
        form = QFormLayout(dlg)

        min_spin = QSpinBox()
        min_spin.setRange(0, 99999)
        min_spin.setValue(item.min_quantity)
        form.addRow("Minimum:", min_spin)

        max_spin = QSpinBox()
        max_spin.setRange(0, 99999)
        max_spin.setValue(item.max_quantity)
        form.addRow("Maximum:", max_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec():
            self.repo.set_truck_inventory_levels(
                truck_id, item.part_id,
                min_spin.value(), max_spin.value(),
            )
            self._on_truck_changed()

    def _on_audit(self):
        """Run a fast audit for the selected truck."""
        truck_id = self.truck_combo.currentData()
        if not truck_id:
            QMessageBox.information(
                self, "No Truck", "Select a truck first.",
            )
            return

        from wired_part.ui.dialogs.audit_dialog import AuditDialog
        dlg = AuditDialog(self.repo, "truck", target_id=truck_id, parent=self)
        dlg.exec()
        self._on_truck_changed()
