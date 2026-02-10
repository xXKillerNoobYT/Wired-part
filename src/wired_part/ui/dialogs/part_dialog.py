"""Add / Edit Part dialog."""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from wired_part.database.models import Part
from wired_part.database.repository import Repository


class PartDialog(QDialog):
    """Dialog for adding or editing a part."""

    def __init__(
        self,
        repo: Repository,
        part: Optional[Part] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.repo = repo
        self.part = part
        self.setWindowTitle("Edit Part" if part else "Add Part")
        self.setMinimumWidth(450)
        self._setup_ui()
        if part:
            self._populate(part)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.part_number_input = QLineEdit()
        self.part_number_input.setMaxLength(50)
        form.addRow("Part Number:", self.part_number_input)

        self.description_input = QLineEdit()
        self.description_input.setMaxLength(200)
        form.addRow("Description:", self.description_input)

        self.quantity_input = QSpinBox()
        self.quantity_input.setRange(0, 999999)
        form.addRow("Quantity:", self.quantity_input)

        self.min_quantity_input = QSpinBox()
        self.min_quantity_input.setRange(0, 999999)
        form.addRow("Min Quantity:", self.min_quantity_input)

        self.location_input = QLineEdit()
        self.location_input.setMaxLength(100)
        form.addRow("Location:", self.location_input)

        self.category_input = QComboBox()
        self.category_input.addItem("(None)", None)
        for cat in self.repo.get_all_categories():
            self.category_input.addItem(cat.name, cat.id)
        form.addRow("Category:", self.category_input)

        self.unit_cost_input = QDoubleSpinBox()
        self.unit_cost_input.setRange(0, 999999.99)
        self.unit_cost_input.setDecimals(2)
        self.unit_cost_input.setPrefix("$")
        form.addRow("Unit Cost:", self.unit_cost_input)

        self.supplier_input = QLineEdit()
        self.supplier_input.setMaxLength(100)
        form.addRow("Supplier:", self.supplier_input)

        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(80)
        form.addRow("Notes:", self.notes_input)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self, part: Part):
        """Fill fields from an existing part."""
        self.part_number_input.setText(part.part_number)
        self.description_input.setText(part.description)
        self.quantity_input.setValue(part.quantity)
        self.min_quantity_input.setValue(part.min_quantity)
        self.location_input.setText(part.location or "")
        self.unit_cost_input.setValue(part.unit_cost)
        self.supplier_input.setText(part.supplier or "")
        self.notes_input.setPlainText(part.notes or "")
        if part.category_id is not None:
            idx = self.category_input.findData(part.category_id)
            if idx >= 0:
                self.category_input.setCurrentIndex(idx)

    def _on_save(self):
        """Validate and save the part."""
        pn = self.part_number_input.text().strip()
        desc = self.description_input.text().strip()

        if not pn:
            QMessageBox.warning(self, "Validation", "Part number is required.")
            return
        if not desc:
            QMessageBox.warning(self, "Validation", "Description is required.")
            return

        # Check uniqueness
        existing = self.repo.get_part_by_number(pn)
        if existing and (self.part is None or existing.id != self.part.id):
            QMessageBox.warning(
                self, "Duplicate",
                f"Part number '{pn}' already exists.",
            )
            return

        data = Part(
            id=self.part.id if self.part else None,
            part_number=pn,
            description=desc,
            quantity=self.quantity_input.value(),
            min_quantity=self.min_quantity_input.value(),
            location=self.location_input.text().strip(),
            category_id=self.category_input.currentData(),
            unit_cost=self.unit_cost_input.value(),
            supplier=self.supplier_input.text().strip(),
            notes=self.notes_input.toPlainText().strip(),
        )

        if self.part:
            self.repo.update_part(data)
        else:
            self.repo.create_part(data)

        self.accept()
