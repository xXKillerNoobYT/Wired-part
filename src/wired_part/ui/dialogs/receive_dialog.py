"""Dialog for receiving pending transfers into truck on-hand inventory."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from wired_part.database.models import User
from wired_part.database.repository import Repository


class ReceiveDialog(QDialog):
    """Confirm receipt of pending transfers for a truck."""

    def __init__(self, repo: Repository, truck_id: int,
                 current_user: User, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.truck_id = truck_id
        self.current_user = current_user

        truck = self.repo.get_truck_by_id(truck_id)
        self.setWindowTitle(
            f"Receive Transfers — {truck.truck_number}" if truck
            else "Receive Transfers"
        )
        self.resize(550, 350)
        self._setup_ui()
        self._load_pending()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Check transfers to confirm receipt:"
        ))

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Receive", "ID", "Part #", "Description", "Qty"]
        )
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnHidden(1, True)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all)
        receive_btn = QPushButton("Receive Selected")
        receive_btn.setMinimumHeight(34)
        receive_btn.clicked.connect(self._receive)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(34)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(select_all_btn)
        btn_layout.addWidget(receive_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _load_pending(self):
        pending = self.repo.get_truck_transfers(
            self.truck_id, status="pending"
        )
        self.table.setRowCount(len(pending))
        self._checkboxes = []

        for row, t in enumerate(pending):
            cb = QCheckBox()
            self.table.setCellWidget(row, 0, cb)
            self._checkboxes.append((t.id, cb))

            self.table.setItem(row, 1, QTableWidgetItem(str(t.id)))
            self.table.setItem(row, 2, QTableWidgetItem(t.part_number))
            self.table.setItem(
                row, 3, QTableWidgetItem(t.part_description)
            )
            self.table.setItem(row, 4, QTableWidgetItem(str(t.quantity)))

        if not pending:
            self.table.setRowCount(0)

    def _select_all(self):
        for _, cb in self._checkboxes:
            cb.setChecked(True)

    def _receive(self):
        received = 0
        for transfer_id, cb in self._checkboxes:
            if cb.isChecked():
                try:
                    self.repo.receive_transfer(
                        transfer_id, self.current_user.id
                    )
                    received += 1
                except ValueError as e:
                    QMessageBox.warning(self, "Error", str(e))

        if received > 0:
            QMessageBox.information(
                self, "Success",
                f"Received {received} transfer(s) into truck inventory."
            )
            self.accept()
        else:
            QMessageBox.information(
                self, "Info", "No transfers selected."
            )
