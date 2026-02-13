"""Dialog for adding and editing trucks."""

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from wired_part.database.models import Truck
from wired_part.database.repository import Repository


class TruckDialog(QDialog):
    """Add or edit a truck."""

    def __init__(self, repo: Repository, truck: Truck = None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.truck = truck
        self.editing = truck is not None

        self.setWindowTitle("Edit Truck" if self.editing else "Add Truck")
        self.setMinimumSize(400, 320)
        self._setup_ui()
        if self.editing:
            self._populate()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self.number_input = QLineEdit()
        self.number_input.setPlaceholderText("e.g. TRUCK-001")
        self.number_input.setMinimumHeight(30)
        form.addRow("Truck #:", self.number_input)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. White Ford F-250")
        self.name_input.setMinimumHeight(30)
        form.addRow("Name:", self.name_input)

        self.user_combo = QComboBox()
        self.user_combo.setMinimumHeight(30)
        self.user_combo.addItem("Unassigned", None)
        for user in self.repo.get_all_users():
            self.user_combo.addItem(user.display_name, user.id)
        form.addRow("Assigned To:", self.user_combo)

        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(80)
        self.notes_input.setPlaceholderText("Notes (optional)")
        form.addRow("Notes:", self.notes_input)

        layout.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #f38ba8;")
        layout.addWidget(self.error_label)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setMinimumHeight(34)
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(34)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _populate(self):
        self.number_input.setText(self.truck.truck_number)
        self.name_input.setText(self.truck.name)
        self.notes_input.setPlainText(self.truck.notes or "")
        if self.truck.assigned_user_id:
            idx = self.user_combo.findData(self.truck.assigned_user_id)
            if idx >= 0:
                self.user_combo.setCurrentIndex(idx)

    def _save(self):
        number = self.number_input.text().strip()
        name = self.name_input.text().strip()
        user_id = self.user_combo.currentData()
        notes = self.notes_input.toPlainText().strip()

        if not number:
            self.error_label.setText("Truck number is required")
            return
        if not name:
            self.error_label.setText("Name is required")
            return

        try:
            if self.editing:
                self.truck.truck_number = number
                self.truck.name = name
                self.truck.assigned_user_id = user_id
                self.truck.notes = notes
                self.repo.update_truck(self.truck)
            else:
                truck = Truck(
                    truck_number=number,
                    name=name,
                    assigned_user_id=user_id,
                    notes=notes,
                )
                truck.id = self.repo.create_truck(truck)
                self.truck = truck
            self.accept()
        except Exception as e:
            self.error_label.setText(str(e))
