"""Dialog for consuming parts from a truck's on-hand inventory to a job."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
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

from wired_part.database.models import User
from wired_part.database.repository import Repository


class ConsumeDialog(QDialog):
    """Select parts from a truck's on-hand inventory to consume onto a job."""

    def __init__(self, repo: Repository, job_id: int,
                 current_user: User, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.job_id = job_id
        self.current_user = current_user

        self.setWindowTitle("Consume Parts from Truck")
        self.resize(650, 450)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Truck selector
        truck_layout = QHBoxLayout()
        truck_layout.addWidget(QLabel("Select Truck:"))
        self.truck_combo = QComboBox()
        self.truck_combo.setMinimumHeight(30)

        trucks = self.repo.get_all_trucks(active_only=True)
        for truck in trucks:
            label = f"{truck.truck_number} — {truck.name}"
            self.truck_combo.addItem(label, truck.id)
        self.truck_combo.currentIndexChanged.connect(self._load_inventory)
        truck_layout.addWidget(self.truck_combo, 1)
        layout.addLayout(truck_layout)

        layout.addWidget(QLabel(
            "Select parts and quantities to consume from truck on-hand:"
        ))

        # Inventory table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Part #", "Description", "On-Hand Qty", "Consume Qty", ""]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        layout.addWidget(self.table)

        # Buttons
        btn_layout = QHBoxLayout()
        consume_btn = QPushButton("Consume Selected")
        consume_btn.setMinimumHeight(34)
        consume_btn.clicked.connect(self._consume)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(34)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(consume_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        # Load initial truck inventory
        if self.truck_combo.count() > 0:
            self._load_inventory()

    def _load_inventory(self):
        self.table.setRowCount(0)
        self._spinboxes = []

        truck_id = self.truck_combo.currentData()
        if not truck_id:
            return

        inventory = self.repo.get_truck_inventory(truck_id)
        # Only show items with quantity > 0
        inventory = [item for item in inventory if item.quantity > 0]
        self.table.setRowCount(len(inventory))

        for row, item in enumerate(inventory):
            self.table.setItem(
                row, 0, QTableWidgetItem(item.part_number)
            )
            self.table.setItem(
                row, 1, QTableWidgetItem(item.part_description)
            )
            self.table.setItem(
                row, 2, QTableWidgetItem(str(item.quantity))
            )

            spin = QSpinBox()
            spin.setRange(0, item.quantity)
            spin.setValue(0)
            self.table.setCellWidget(row, 3, spin)
            self._spinboxes.append((item.part_id, spin))

            self.table.setItem(row, 4, QTableWidgetItem(""))

    def _consume(self):
        truck_id = self.truck_combo.currentData()
        if not truck_id:
            QMessageBox.information(
                self, "Info", "No truck selected."
            )
            return

        consumed = 0
        errors = []
        for part_id, spin in self._spinboxes:
            qty = spin.value()
            if qty <= 0:
                continue
            try:
                self.repo.consume_from_truck(
                    job_id=self.job_id,
                    truck_id=truck_id,
                    part_id=part_id,
                    quantity=qty,
                    user_id=self.current_user.id if self.current_user else None,
                )
                consumed += 1
            except ValueError as e:
                errors.append(str(e))

        if errors:
            QMessageBox.warning(
                self, "Errors",
                f"Consumed {consumed} part(s), but had errors:\n"
                + "\n".join(errors)
            )
        elif consumed == 0:
            QMessageBox.information(
                self, "Info", "No quantities specified."
            )
            return
        else:
            QMessageBox.information(
                self, "Success",
                f"Consumed {consumed} part(s) from truck to job."
            )
        if consumed > 0:
            self.accept()
