"""Trucks page — truck list, on-hand inventory, transfers."""

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
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.models import User
from wired_part.database.repository import Repository
from wired_part.utils.formatters import format_currency


class TrucksPage(QWidget):
    """Truck management with inventory and transfer views."""

    def __init__(self, repo: Repository, current_user: User, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.current_user = current_user
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()
        add_btn = QPushButton("Add Truck")
        add_btn.clicked.connect(self._add_truck)
        edit_btn = QPushButton("Edit Truck")
        edit_btn.clicked.connect(self._edit_truck)
        transfer_btn = QPushButton("New Transfer")
        transfer_btn.clicked.connect(self._new_transfer)
        receive_btn = QPushButton("Receive Transfer")
        receive_btn.clicked.connect(self._receive_transfers)
        return_btn = QPushButton("Return to Warehouse")
        return_btn.clicked.connect(self._return_to_warehouse)

        toolbar.addWidget(add_btn)
        toolbar.addWidget(edit_btn)
        toolbar.addWidget(transfer_btn)
        toolbar.addWidget(receive_btn)
        toolbar.addWidget(return_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Splitter: truck list | detail panel
        splitter = QSplitter(Qt.Horizontal)

        # Left: truck list
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Trucks"))
        self.truck_list = QListWidget()
        self.truck_list.currentRowChanged.connect(self._on_truck_selected)
        left_layout.addWidget(self.truck_list)
        splitter.addWidget(left)

        # Right: detail tabs
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Truck info
        self.info_label = QLabel("Select a truck")
        self.info_label.setStyleSheet("font-size: 14px; padding: 8px;")
        right_layout.addWidget(self.info_label)

        # Sub-tabs
        self.detail_tabs = QTabWidget()

        # On-hand inventory tab
        self.inv_table = QTableWidget()
        self.inv_table.setColumnCount(4)
        self.inv_table.setHorizontalHeaderLabels(
            ["Part #", "Description", "Qty", "Value"]
        )
        self.inv_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.inv_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.inv_table.horizontalHeader().setStretchLastSection(True)
        self.detail_tabs.addTab(self.inv_table, "On-Hand Inventory")

        # Pending transfers tab
        self.pending_table = QTableWidget()
        self.pending_table.setColumnCount(5)
        self.pending_table.setHorizontalHeaderLabels(
            ["ID", "Part #", "Description", "Qty", "Created"]
        )
        self.pending_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.pending_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.pending_table.horizontalHeader().setStretchLastSection(True)
        self.pending_table.setColumnHidden(0, True)
        self.detail_tabs.addTab(self.pending_table, "Pending Transfers")

        # Transfer history tab
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels(
            ["Part #", "Qty", "Direction", "Status", "Created By", "Date"]
        )
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.detail_tabs.addTab(self.history_table, "Transfer History")

        right_layout.addWidget(self.detail_tabs)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter)

    def refresh(self):
        self._refresh_truck_list()

    def _refresh_truck_list(self):
        trucks = self.repo.get_all_trucks(active_only=True)
        self.truck_list.clear()
        self._trucks = trucks
        for truck in trucks:
            label = f"{truck.truck_number} — {truck.name}"
            if truck.assigned_user_name:
                label += f" ({truck.assigned_user_name})"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, truck.id)
            self.truck_list.addItem(item)

    def _get_selected_truck_id(self):
        item = self.truck_list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _on_truck_selected(self, row):
        if row < 0:
            return
        truck_id = self._get_selected_truck_id()
        if not truck_id:
            return
        truck = self.repo.get_truck_by_id(truck_id)
        if not truck:
            return

        # Update info
        info = (
            f"<b>{truck.truck_number}</b> — {truck.name}<br>"
            f"Assigned to: {truck.assigned_user_name or 'Unassigned'}<br>"
            f"Notes: {truck.notes or 'None'}"
        )
        self.info_label.setText(info)

        # Refresh inventory
        inv = self.repo.get_truck_inventory(truck_id)
        self.inv_table.setRowCount(len(inv))
        for r, item in enumerate(inv):
            self.inv_table.setItem(
                r, 0, QTableWidgetItem(item.part_number)
            )
            self.inv_table.setItem(
                r, 1, QTableWidgetItem(item.part_description)
            )
            self.inv_table.setItem(
                r, 2, QTableWidgetItem(str(item.quantity))
            )
            self.inv_table.setItem(
                r, 3, QTableWidgetItem(
                    format_currency(item.quantity * item.unit_cost)
                )
            )

        # Refresh pending transfers
        pending = self.repo.get_truck_transfers(truck_id, status="pending")
        self.pending_table.setRowCount(len(pending))
        for r, t in enumerate(pending):
            self.pending_table.setItem(
                r, 0, QTableWidgetItem(str(t.id))
            )
            self.pending_table.setItem(
                r, 1, QTableWidgetItem(t.part_number)
            )
            self.pending_table.setItem(
                r, 2, QTableWidgetItem(t.part_description)
            )
            self.pending_table.setItem(
                r, 3, QTableWidgetItem(str(t.quantity))
            )
            self.pending_table.setItem(
                r, 4, QTableWidgetItem(str(t.created_at or ""))
            )

        # Refresh history
        all_transfers = self.repo.get_truck_transfers(truck_id)
        self.history_table.setRowCount(len(all_transfers))
        for r, t in enumerate(all_transfers):
            self.history_table.setItem(
                r, 0, QTableWidgetItem(t.part_number)
            )
            self.history_table.setItem(
                r, 1, QTableWidgetItem(str(t.quantity))
            )
            self.history_table.setItem(
                r, 2, QTableWidgetItem(t.direction)
            )
            self.history_table.setItem(
                r, 3, QTableWidgetItem(t.status)
            )
            self.history_table.setItem(
                r, 4, QTableWidgetItem(t.created_by_name)
            )
            self.history_table.setItem(
                r, 5, QTableWidgetItem(str(t.created_at or ""))
            )

    def _add_truck(self):
        from wired_part.ui.dialogs.truck_dialog import TruckDialog
        dlg = TruckDialog(self.repo, parent=self)
        if dlg.exec() == TruckDialog.Accepted:
            self._refresh_truck_list()

    def _edit_truck(self):
        truck_id = self._get_selected_truck_id()
        if not truck_id:
            QMessageBox.information(self, "Info", "Select a truck to edit.")
            return
        truck = self.repo.get_truck_by_id(truck_id)
        from wired_part.ui.dialogs.truck_dialog import TruckDialog
        dlg = TruckDialog(self.repo, truck=truck, parent=self)
        if dlg.exec() == TruckDialog.Accepted:
            self._refresh_truck_list()

    def _new_transfer(self):
        truck_id = self._get_selected_truck_id()
        if not truck_id:
            QMessageBox.information(
                self, "Info", "Select a truck first."
            )
            return
        from wired_part.ui.dialogs.transfer_dialog import TransferDialog
        dlg = TransferDialog(
            self.repo, truck_id, self.current_user, parent=self
        )
        if dlg.exec() == TransferDialog.Accepted:
            self._on_truck_selected(self.truck_list.currentRow())

    def _receive_transfers(self):
        truck_id = self._get_selected_truck_id()
        if not truck_id:
            QMessageBox.information(
                self, "Info", "Select a truck first."
            )
            return
        from wired_part.ui.dialogs.receive_dialog import ReceiveDialog
        dlg = ReceiveDialog(
            self.repo, truck_id, self.current_user, parent=self
        )
        if dlg.exec() == ReceiveDialog.Accepted:
            self._on_truck_selected(self.truck_list.currentRow())

    def _return_to_warehouse(self):
        truck_id = self._get_selected_truck_id()
        if not truck_id:
            QMessageBox.information(
                self, "Info", "Select a truck first."
            )
            return
        # Get selected part from inventory table
        row = self.inv_table.currentRow()
        if row < 0:
            QMessageBox.information(
                self, "Info",
                "Select a part from the on-hand inventory to return."
            )
            return
        part_number = self.inv_table.item(row, 0).text()
        qty_str = self.inv_table.item(row, 2).text()
        part = self.repo.get_part_by_number(part_number)
        if not part:
            return

        from PySide6.QtWidgets import QInputDialog
        qty, ok = QInputDialog.getInt(
            self, "Return Quantity",
            f"How many '{part_number}' to return? (on-hand: {qty_str})",
            value=1, min=1, max=int(qty_str),
        )
        if ok and qty > 0:
            try:
                self.repo.return_to_warehouse(
                    truck_id, part.id, qty, self.current_user.id
                )
                self._on_truck_selected(self.truck_list.currentRow())
            except ValueError as e:
                QMessageBox.warning(self, "Error", str(e))
