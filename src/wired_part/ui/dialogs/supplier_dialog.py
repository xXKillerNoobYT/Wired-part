"""Add / Edit Supplier dialog."""

from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from wired_part.database.models import Supplier
from wired_part.database.repository import Repository


class SupplierDialog(QDialog):
    """Dialog for creating or editing a supplier."""

    def __init__(
        self,
        repo: Repository,
        supplier: Optional[Supplier] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.repo = repo
        self.supplier = supplier
        self.setWindowTitle("Edit Supplier" if supplier else "New Supplier")
        self.setMinimumWidth(450)
        self._setup_ui()
        if supplier:
            self._populate(supplier)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setMaxLength(100)
        form.addRow("Company Name:", self.name_input)

        self.contact_input = QLineEdit()
        self.contact_input.setMaxLength(100)
        form.addRow("Contact Name:", self.contact_input)

        self.email_input = QLineEdit()
        self.email_input.setMaxLength(150)
        self.email_input.setPlaceholderText("orders@example.com")
        form.addRow("Email:", self.email_input)

        self.phone_input = QLineEdit()
        self.phone_input.setMaxLength(30)
        form.addRow("Phone:", self.phone_input)

        self.address_input = QLineEdit()
        self.address_input.setMaxLength(200)
        form.addRow("Address:", self.address_input)

        self.preference_input = QSpinBox()
        self.preference_input.setRange(0, 100)
        self.preference_input.setValue(50)
        self.preference_input.setSuffix("  (0=Lowest, 100=Preferred)")
        self.preference_input.setToolTip(
            "Higher score = more preferred supplier for ordering"
        )
        form.addRow("Preference:", self.preference_input)

        self.delivery_input = QLineEdit()
        self.delivery_input.setPlaceholderText(
            "e.g., Mon-Fri, 2-day delivery"
        )
        form.addRow("Delivery Schedule:", self.delivery_input)

        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(80)
        form.addRow("Notes:", self.notes_input)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self, supplier: Supplier):
        self.name_input.setText(supplier.name)
        self.contact_input.setText(supplier.contact_name or "")
        self.email_input.setText(supplier.email or "")
        self.phone_input.setText(supplier.phone or "")
        self.address_input.setText(supplier.address or "")
        self.preference_input.setValue(supplier.preference_score or 50)
        self.delivery_input.setText(supplier.delivery_schedule or "")
        self.notes_input.setPlainText(supplier.notes or "")

    def _on_save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(
                self, "Validation", "Supplier name is required."
            )
            return

        data = Supplier(
            id=self.supplier.id if self.supplier else None,
            name=name,
            contact_name=self.contact_input.text().strip(),
            email=self.email_input.text().strip(),
            phone=self.phone_input.text().strip(),
            address=self.address_input.text().strip(),
            preference_score=self.preference_input.value(),
            delivery_schedule=self.delivery_input.text().strip(),
            notes=self.notes_input.toPlainText().strip(),
        )

        try:
            if self.supplier:
                self.repo.update_supplier(data)
            else:
                self.repo.create_supplier(data)
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
