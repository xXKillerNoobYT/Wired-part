"""Dialog for creating warehouse-to-truck transfers."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from wired_part.database.models import TruckTransfer, User
from wired_part.database.repository import Repository


class TransferDialog(QDialog):
    """Select parts from warehouse to transfer to a truck."""

    def __init__(self, repo: Repository, truck_id: int,
                 current_user: User, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.truck_id = truck_id
        self.current_user = current_user

        truck = self.repo.get_truck_by_id(truck_id)
        self.setWindowTitle(
            f"Transfer to {truck.truck_number}" if truck else "Transfer"
        )
        self.resize(600, 400)
        self._setup_ui()
        self._load_parts()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            "Select parts and quantities to transfer from warehouse:"
        ))

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Part #", "Description", "Warehouse Qty", "Transfer Qty", ""]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        # Buttons
        btn_layout = QHBoxLayout()
        transfer_btn = QPushButton("Create Transfer(s)")
        transfer_btn.setMinimumHeight(34)
        transfer_btn.clicked.connect(self._create_transfers)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(34)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(transfer_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _load_parts(self):
        parts = self.repo.get_all_parts()
        # Only show parts with stock > 0
        parts = [p for p in parts if p.quantity > 0]
        self.table.setRowCount(len(parts))
        self._spinboxes = []

        for row, part in enumerate(parts):
            self.table.setItem(
                row, 0, QTableWidgetItem(part.part_number)
            )
            self.table.setItem(
                row, 1, QTableWidgetItem(part.description)
            )
            self.table.setItem(
                row, 2, QTableWidgetItem(str(part.quantity))
            )

            spin = QSpinBox()
            spin.setRange(0, part.quantity)
            spin.setValue(0)
            self.table.setCellWidget(row, 3, spin)
            self._spinboxes.append((part.id, spin))

            self.table.setItem(row, 4, QTableWidgetItem(""))

    def _create_transfers(self):
        created = 0
        errors = []
        for part_id, spin in self._spinboxes:
            qty = spin.value()
            if qty <= 0:
                continue
            try:
                transfer = TruckTransfer(
                    truck_id=self.truck_id,
                    part_id=part_id,
                    quantity=qty,
                    created_by=self.current_user.id,
                )
                self.repo.create_transfer(transfer)
                created += 1
            except ValueError as e:
                errors.append(str(e))

        if errors:
            QMessageBox.warning(
                self, "Errors",
                f"Created {created} transfer(s), but had errors:\n"
                + "\n".join(errors)
            )
        elif created == 0:
            QMessageBox.information(
                self, "Info", "No quantities specified."
            )
            return
        else:
            QMessageBox.information(
                self, "Success",
                f"Created {created} transfer(s). "
                "Parts deducted from warehouse."
            )
        if created > 0:
            self.accept()
