"""Add / Edit Part dialog — dynamic form for General vs Specific parts."""

import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.models import Brand, Part, PartSupplier, PartVariant
from wired_part.database.repository import Repository


class PartDialog(QDialog):
    """Dialog for adding or editing a part.

    Features:
    - Type toggle (General / Specific) that shows/hides relevant fields
    - Name field (always required) separate from Part Number
    - Part Number required for Specific, recommended for General
    - Quantity Window (min / max) instead of just min qty
    - Auto-generate local part number
    - Brand dropdown with quick-add (Specific only)
    - Supplier checkboxes from DB for BOTH types
    - Type/Style → Color hierarchy in a QTreeWidget (BOTH types)
    - Subcategory field (moved to common area)
    - Soft save: allows incomplete data, shows warnings
    - Scrollable layout — whole dialog grows, no fixed section heights
    """

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
        self.setMinimumWidth(650)
        self.setMinimumHeight(600)
        self._setup_ui()
        if part:
            self._populate(part)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Header
        header = QLabel("Edit Part" if self.part else "Add New Part")
        header.setStyleSheet("font-size: 14px; font-weight: bold;")
        main_layout.addWidget(header)

        hint = QLabel(
            "Fields marked with * are required. "
            "You can save incomplete parts and finish later."
        )
        hint.setStyleSheet("color: #a6adc8; font-size: 11px;")
        hint.setWordWrap(True)
        main_layout.addWidget(hint)

        # Scrollable content — the whole form scrolls, no fixed heights
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)

        # ── Type Selection ──────────────────────────────────────
        type_group = QHBoxLayout()
        type_label = QLabel("Part Type:")
        type_label.setStyleSheet("font-weight: bold;")
        type_group.addWidget(type_label)

        self.general_radio = QRadioButton("General (Commodity)")
        self.specific_radio = QRadioButton("Specific (Branded)")
        self.general_radio.setChecked(True)
        self.general_radio.toggled.connect(self._on_type_changed)
        type_group.addWidget(self.general_radio)
        type_group.addWidget(self.specific_radio)
        type_group.addStretch()
        layout.addLayout(type_group)

        # ── Common Fields ───────────────────────────────────────
        common_form = QFormLayout()
        common_form.setSpacing(8)

        # Name (always required)
        self.name_input = QLineEdit()
        self.name_input.setMaxLength(100)
        self.name_input.setPlaceholderText(
            "e.g. Duplex Outlet, 12/2 NM-B Wire"
        )
        common_form.addRow("Name *:", self.name_input)

        # Local Part Number
        lpn_row = QHBoxLayout()
        self.auto_lpn_check = QCheckBox("Auto-generate")
        self.auto_lpn_check.setChecked(True)
        self.auto_lpn_check.toggled.connect(self._on_auto_lpn_toggled)
        self.local_pn_input = QLineEdit()
        self.local_pn_input.setMaxLength(20)
        self.local_pn_input.setPlaceholderText("e.g. LP-0001")
        self.local_pn_input.setEnabled(False)
        lpn_row.addWidget(self.auto_lpn_check)
        lpn_row.addWidget(self.local_pn_input)
        common_form.addRow("Local Part #:", lpn_row)

        # Part Number — label updates based on type
        self.part_number_label = QLabel("Part Number:")
        self.part_number_input = QLineEdit()
        self.part_number_input.setMaxLength(50)
        self.part_number_input.setPlaceholderText("e.g. WIRE-12/2-NM")
        common_form.addRow(self.part_number_label, self.part_number_input)

        # Description
        self.description_input = QLineEdit()
        self.description_input.setMaxLength(200)
        self.description_input.setPlaceholderText(
            "e.g. 12/2 NM-B Romex Wire, 250ft"
        )
        common_form.addRow("Description:", self.description_input)

        # Category
        self.category_input = QComboBox()
        self.category_input.addItem("(None)", None)
        for cat in self.repo.get_all_categories():
            self.category_input.addItem(cat.name, cat.id)
        common_form.addRow("Category:", self.category_input)

        # Subcategory (editable dropdown — moved from general-only)
        self.subcategory_input = QComboBox()
        self.subcategory_input.setEditable(True)
        self.subcategory_input.setInsertPolicy(QComboBox.NoInsert)
        self.subcategory_input.addItem("")
        self._populate_subcategory_suggestions()
        self.subcategory_input.lineEdit().setPlaceholderText(
            "Select or type subcategory"
        )
        common_form.addRow("Subcategory:", self.subcategory_input)

        # Image
        img_row = QHBoxLayout()
        self.image_path_input = QLineEdit()
        self.image_path_input.setPlaceholderText("No image selected")
        self.image_path_input.setReadOnly(True)
        img_row.addWidget(self.image_path_input)
        img_btn = QPushButton("Browse...")
        img_btn.clicked.connect(self._on_browse_image)
        img_row.addWidget(img_btn)
        clear_img_btn = QPushButton("Clear")
        clear_img_btn.clicked.connect(
            lambda: self.image_path_input.clear()
        )
        img_row.addWidget(clear_img_btn)
        common_form.addRow("Image:", img_row)

        # Quantity + Quantity Window (min / max)
        qty_row = QHBoxLayout()
        self.quantity_input = QSpinBox()
        self.quantity_input.setRange(0, 999999)
        qty_row.addWidget(QLabel("Qty:"))
        qty_row.addWidget(self.quantity_input)

        qty_row.addWidget(QLabel("  Window:"))
        self.min_quantity_input = QSpinBox()
        self.min_quantity_input.setRange(0, 999999)
        self.min_quantity_input.setToolTip("Minimum quantity to maintain")
        qty_row.addWidget(self.min_quantity_input)

        qty_row.addWidget(QLabel("/"))

        self.max_quantity_input = QSpinBox()
        self.max_quantity_input.setRange(0, 999999)
        self.max_quantity_input.setToolTip("Maximum quantity to maintain")
        qty_row.addWidget(self.max_quantity_input)
        common_form.addRow("Quantity:", qty_row)

        # Unit Cost
        self.unit_cost_input = QDoubleSpinBox()
        self.unit_cost_input.setRange(0, 999999.99)
        self.unit_cost_input.setDecimals(2)
        self.unit_cost_input.setPrefix("$")
        common_form.addRow("Unit Cost:", self.unit_cost_input)

        # Location
        self.location_input = QLineEdit()
        self.location_input.setMaxLength(100)
        self.location_input.setPlaceholderText("e.g. Shelf A-3, Bin 12")
        common_form.addRow("Location:", self.location_input)

        # Suppliers — checkboxes from the database for BOTH types
        self.supplier_checks: dict[int, QCheckBox] = {}
        supp_widget = QWidget()
        supp_layout = QVBoxLayout(supp_widget)
        supp_layout.setContentsMargins(2, 2, 2, 2)
        supp_layout.setSpacing(2)
        for s in self.repo.get_all_suppliers():
            cb = QCheckBox(s.name)
            supp_layout.addWidget(cb)
            self.supplier_checks[s.id] = cb
        supp_layout.addStretch()
        common_form.addRow("Suppliers:", supp_widget)

        # QR Tag
        self.qr_tag_check = QCheckBox("QR tag printed and on shelf")
        common_form.addRow("QR Tag:", self.qr_tag_check)

        # Notes
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText(
            "Optional notes about this part"
        )
        self.notes_input.setMinimumHeight(50)
        common_form.addRow("Notes:", self.notes_input)

        layout.addLayout(common_form)

        # ── Specific-Only Fields ────────────────────────────────
        self.specific_group = QGroupBox("Specific Part Details")
        specific_form = QFormLayout(self.specific_group)

        # Brand dropdown + Add New
        brand_row = QHBoxLayout()
        self.brand_input = QComboBox()
        self.brand_input.addItem("(None)", None)
        self._load_brands()
        brand_row.addWidget(self.brand_input, 1)
        add_brand_btn = QPushButton("+ New Brand")
        add_brand_btn.clicked.connect(self._on_add_brand)
        brand_row.addWidget(add_brand_btn)
        specific_form.addRow("Brand *:", brand_row)

        # Brand Part Number
        self.brand_pn_input = QLineEdit()
        self.brand_pn_input.setMaxLength(100)
        self.brand_pn_input.setPlaceholderText("Manufacturer part number")
        specific_form.addRow("Brand Part # *:", self.brand_pn_input)

        # PDFs
        pdf_row = QHBoxLayout()
        self.pdf_list_label = QLabel("No PDFs attached")
        self.pdf_list_label.setStyleSheet("color: #a6adc8;")
        pdf_row.addWidget(self.pdf_list_label, 1)
        add_pdf_btn = QPushButton("Add PDF...")
        add_pdf_btn.clicked.connect(self._on_add_pdf)
        pdf_row.addWidget(add_pdf_btn)
        clear_pdf_btn = QPushButton("Clear All")
        clear_pdf_btn.clicked.connect(self._on_clear_pdfs)
        pdf_row.addWidget(clear_pdf_btn)
        specific_form.addRow("PDFs:", pdf_row)
        self._pdf_paths: list[str] = []

        layout.addWidget(self.specific_group)

        # Initially hide specific (General is default)
        self.specific_group.setVisible(False)

        # ── Type / Style & Color Hierarchy ──────────────────────
        ts_group = QGroupBox("Type / Style & Colors")
        ts_layout = QVBoxLayout(ts_group)

        # Type/Style add row
        ts_add_row = QHBoxLayout()
        self.ts_combo = QComboBox()
        self.ts_combo.setEditable(True)
        self.ts_combo.setInsertPolicy(QComboBox.NoInsert)
        self.ts_combo.addItem("")
        from wired_part.utils.constants import COMMON_STYLES
        for s in COMMON_STYLES:
            self.ts_combo.addItem(s)
        self.ts_combo.lineEdit().setPlaceholderText(
            "Pick a preset or type a custom type/style"
        )
        ts_add_row.addWidget(self.ts_combo, 1)
        add_ts_btn = QPushButton("+ Add Type/Style")
        add_ts_btn.clicked.connect(self._on_add_type_style)
        ts_add_row.addWidget(add_ts_btn)
        ts_layout.addLayout(ts_add_row)

        # Tree widget
        self.variant_tree = QTreeWidget()
        self.variant_tree.setHeaderLabels([
            "Name", "Part Number", "Image", "Notes",
        ])
        self.variant_tree.setColumnCount(4)
        self.variant_tree.header().setStretchLastSection(True)
        self.variant_tree.header().setSectionResizeMode(
            0, QHeaderView.Stretch
        )
        self.variant_tree.setSelectionMode(QTreeWidget.SingleSelection)
        self.variant_tree.setAlternatingRowColors(True)
        self.variant_tree.itemSelectionChanged.connect(
            self._on_tree_selection_changed
        )
        ts_layout.addWidget(self.variant_tree)

        # Color add row (below tree, enabled when type/style selected)
        self.color_add_widget = QWidget()
        color_add_row = QHBoxLayout(self.color_add_widget)
        color_add_row.setContentsMargins(0, 0, 0, 0)
        self.color_combo = QComboBox()
        self.color_combo.setEditable(True)
        self.color_combo.setInsertPolicy(QComboBox.NoInsert)
        self.color_combo.addItem("")
        from wired_part.utils.constants import COMMON_COLORS
        for c in COMMON_COLORS:
            self.color_combo.addItem(c)
        self.color_combo.lineEdit().setPlaceholderText(
            "Select a type/style above, then add colors here"
        )
        color_add_row.addWidget(self.color_combo, 1)
        add_color_btn = QPushButton("+ Add Color")
        add_color_btn.clicked.connect(self._on_add_color_to_type)
        color_add_row.addWidget(add_color_btn)
        self.color_add_widget.setEnabled(False)
        ts_layout.addWidget(self.color_add_widget)

        # Remove button
        remove_row = QHBoxLayout()
        remove_row.addStretch()
        self.remove_tree_btn = QPushButton("Remove Selected")
        self.remove_tree_btn.setStyleSheet("color: #f38ba8;")
        self.remove_tree_btn.clicked.connect(self._on_remove_tree_item)
        self.remove_tree_btn.setEnabled(False)
        remove_row.addWidget(self.remove_tree_btn)
        ts_layout.addLayout(remove_row)

        layout.addWidget(ts_group)

        scroll.setWidget(content)
        main_layout.addWidget(scroll, 1)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

        # Update the PN label for the default type
        self._update_pn_label()

    # ── Helpers ─────────────────────────────────────────────────

    def _update_pn_label(self):
        """Update the Part Number label based on selected type."""
        if self.specific_radio.isChecked():
            self.part_number_label.setText("Part Number *:")
        else:
            self.part_number_label.setText("Part Number:")

    def _populate_subcategory_suggestions(self):
        """Populate subcategory dropdown with suggestions."""
        from wired_part.utils.constants import COMMON_SUBCATEGORIES
        all_subs = set()
        for subs in COMMON_SUBCATEGORIES.values():
            all_subs.update(subs)
        for sub in sorted(all_subs):
            self.subcategory_input.addItem(sub)

    def _load_brands(self):
        """Reload brands into the dropdown."""
        current_id = self.brand_input.currentData()
        self.brand_input.blockSignals(True)
        self.brand_input.clear()
        self.brand_input.addItem("(None)", None)
        for brand in self.repo.get_all_brands():
            self.brand_input.addItem(brand.name, brand.id)
        if current_id is not None:
            idx = self.brand_input.findData(current_id)
            if idx >= 0:
                self.brand_input.setCurrentIndex(idx)
        self.brand_input.blockSignals(False)

    def _on_type_changed(self, checked: bool):
        """Toggle visibility of Specific field group + update highlights."""
        is_general = self.general_radio.isChecked()
        self.specific_group.setVisible(not is_general)
        self._update_pn_label()
        self._highlight_missing_part_numbers()

    def _on_auto_lpn_toggled(self, checked: bool):
        """Enable/disable local PN field based on auto-generate checkbox."""
        self.local_pn_input.setEnabled(not checked)
        if checked:
            self.local_pn_input.setText(
                self.repo.generate_local_part_number()
            )

    def _on_browse_image(self):
        """Open file dialog to select an image."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Part Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if path:
            self.image_path_input.setText(path)

    def _on_add_brand(self):
        """Quick-create a new brand."""
        name, ok = QInputDialog.getText(
            self, "New Brand", "Brand name:"
        )
        if ok and name.strip():
            try:
                brand_id = self.repo.create_brand(Brand(name=name.strip()))
                self._load_brands()
                idx = self.brand_input.findData(brand_id)
                if idx >= 0:
                    self.brand_input.setCurrentIndex(idx)
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    # ── PDF helpers ─────────────────────────────────────────────

    def _on_add_pdf(self):
        """Select a PDF file to attach."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select PDF", "", "PDF Files (*.pdf)"
        )
        if path and path not in self._pdf_paths:
            self._pdf_paths.append(path)
            self._update_pdf_label()

    def _on_clear_pdfs(self):
        self._pdf_paths.clear()
        self._update_pdf_label()

    def _update_pdf_label(self):
        if self._pdf_paths:
            names = [Path(p).name for p in self._pdf_paths]
            self.pdf_list_label.setText(", ".join(names))
            self.pdf_list_label.setStyleSheet("color: #cdd6f4;")
        else:
            self.pdf_list_label.setText("No PDFs attached")
            self.pdf_list_label.setStyleSheet("color: #a6adc8;")

    # ── Tree helpers ────────────────────────────────────────────

    def _on_add_type_style(self):
        """Add a new top-level type/style node to the tree."""
        text = self.ts_combo.currentText().strip()
        if not text:
            return
        # Check for duplicates at top level
        for i in range(self.variant_tree.topLevelItemCount()):
            if self.variant_tree.topLevelItem(i).text(0) == text:
                return
        item = QTreeWidgetItem([text, "", "", ""])
        # Top-level items are not directly editable
        item.setFlags(
            (item.flags() | Qt.ItemIsSelectable)
            & ~Qt.ItemIsEditable
        )
        self.variant_tree.addTopLevelItem(item)
        item.setExpanded(True)
        self.ts_combo.setCurrentIndex(0)

    def _on_add_color_to_type(self):
        """Add a color child under the selected type/style node."""
        color = self.color_combo.currentText().strip()
        if not color:
            return
        selected = self.variant_tree.currentItem()
        if not selected:
            return
        # Resolve to the type/style parent
        parent = selected if selected.parent() is None else selected.parent()
        # Prevent duplicate color under this type
        for i in range(parent.childCount()):
            if parent.child(i).text(0) == color:
                return
        child = QTreeWidgetItem([color, "", "", ""])
        child.setFlags(child.flags() | Qt.ItemIsEditable)
        parent.addChild(child)
        parent.setExpanded(True)
        self.color_combo.setCurrentIndex(0)
        self._highlight_missing_part_numbers()

    def _on_tree_selection_changed(self):
        """Enable/disable color add row and remove button."""
        selected = self.variant_tree.currentItem()
        has_sel = selected is not None
        self.color_add_widget.setEnabled(has_sel)
        self.remove_tree_btn.setEnabled(has_sel)

    def _on_remove_tree_item(self):
        """Remove the selected item from the tree."""
        selected = self.variant_tree.currentItem()
        if not selected:
            return
        if selected.parent() is None:
            # Removing a top-level type/style
            if selected.childCount() > 0:
                reply = QMessageBox.question(
                    self, "Remove Type/Style",
                    f"Remove '{selected.text(0)}' and all its "
                    f"{selected.childCount()} color(s)?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
                )
                if reply != QMessageBox.Yes:
                    return
            idx = self.variant_tree.indexOfTopLevelItem(selected)
            self.variant_tree.takeTopLevelItem(idx)
        else:
            # Removing a child color
            parent = selected.parent()
            parent.removeChild(selected)
        self._highlight_missing_part_numbers()

    def _highlight_missing_part_numbers(self):
        """For specific parts, highlight leaf nodes missing part numbers."""
        is_specific = self.specific_radio.isChecked()
        normal_color = QColor("#cdd6f4")
        warning_color = QColor("#f9e2af")

        for ts_idx in range(self.variant_tree.topLevelItemCount()):
            ts_item = self.variant_tree.topLevelItem(ts_idx)
            for c_idx in range(ts_item.childCount()):
                child = ts_item.child(c_idx)
                if is_specific and not child.text(1).strip():
                    child.setForeground(1, warning_color)
                else:
                    child.setForeground(1, normal_color)

    # ── Populate ────────────────────────────────────────────────

    def _populate(self, part: Part):
        """Fill all fields from an existing part."""
        # Type
        if part.is_specific:
            self.specific_radio.setChecked(True)
        else:
            self.general_radio.setChecked(True)

        # Name
        self.name_input.setText(part.name or "")

        # Local PN
        if part.local_part_number:
            self.auto_lpn_check.setChecked(False)
            self.local_pn_input.setText(part.local_part_number)
        else:
            self.auto_lpn_check.setChecked(True)

        # Common fields
        self.part_number_input.setText(part.part_number)
        self.description_input.setText(part.description)
        self.quantity_input.setValue(part.quantity)
        self.min_quantity_input.setValue(part.min_quantity)
        self.max_quantity_input.setValue(part.max_quantity)
        self.location_input.setText(part.location or "")
        self.unit_cost_input.setValue(part.unit_cost)
        self.notes_input.setPlainText(part.notes or "")
        self.image_path_input.setText(part.image_path or "")
        self.qr_tag_check.setChecked(bool(part.has_qr_tag))

        # Category
        if part.category_id is not None:
            idx = self.category_input.findData(part.category_id)
            if idx >= 0:
                self.category_input.setCurrentIndex(idx)

        # Subcategory
        if part.subcategory:
            idx = self.subcategory_input.findText(part.subcategory)
            if idx >= 0:
                self.subcategory_input.setCurrentIndex(idx)
            else:
                self.subcategory_input.setEditText(part.subcategory)

        # Suppliers
        if part.id:
            linked = self.repo.get_part_suppliers(part.id)
            linked_ids = {ps.supplier_id for ps in linked}
            for sid, cb in self.supplier_checks.items():
                cb.setChecked(sid in linked_ids)
            if not linked_ids and part.supplier:
                for sid, cb in self.supplier_checks.items():
                    if cb.text() == part.supplier:
                        cb.setChecked(True)
                        break

        # Specific fields
        if part.brand_id:
            idx = self.brand_input.findData(part.brand_id)
            if idx >= 0:
                self.brand_input.setCurrentIndex(idx)
        self.brand_pn_input.setText(part.brand_part_number or "")

        # PDFs
        self._pdf_paths = part.pdf_list[:]
        self._update_pdf_label()

        # Variants → tree view
        if part.id:
            variants = self.repo.get_part_variants(part.id)
            # Group by type_style
            style_map: dict[str, list[PartVariant]] = {}
            for v in variants:
                ts_key = v.type_style or "(No Type)"
                style_map.setdefault(ts_key, []).append(v)

            for style_name in sorted(style_map.keys()):
                ts_item = QTreeWidgetItem([style_name, "", "", ""])
                ts_item.setFlags(
                    (ts_item.flags() | Qt.ItemIsSelectable)
                    & ~Qt.ItemIsEditable
                )
                self.variant_tree.addTopLevelItem(ts_item)

                for v in sorted(
                    style_map[style_name], key=lambda x: x.color_finish
                ):
                    child = QTreeWidgetItem([
                        v.color_finish,
                        v.brand_part_number,
                        v.image_path,
                        v.notes,
                    ])
                    child.setFlags(child.flags() | Qt.ItemIsEditable)
                    child.setData(0, Qt.UserRole, v.id)
                    ts_item.addChild(child)

                ts_item.setExpanded(True)

        self._highlight_missing_part_numbers()

    # ── Save ────────────────────────────────────────────────────

    def _on_save(self):
        """Save the part — soft save allows incomplete data with warnings."""
        name = self.name_input.text().strip()
        pn = self.part_number_input.text().strip()
        is_specific = self.specific_radio.isChecked()

        # Minimum required: name
        if not name:
            QMessageBox.warning(
                self, "Validation",
                "Part name is required. This is how the part appears "
                "in the system."
            )
            return

        # Check part number uniqueness if provided
        if pn:
            existing = self.repo.get_part_by_number(pn)
            if existing and (
                self.part is None or existing.id != self.part.id
            ):
                QMessageBox.warning(
                    self, "Duplicate",
                    f"Part number '{pn}' already exists.",
                )
                return

        # Build warnings for incomplete data (soft save)
        warnings = []
        if self.unit_cost_input.value() <= 0:
            warnings.append("• Unit cost is $0.00")
        if self.category_input.currentData() is None:
            warnings.append("• No category selected")
        if is_specific:
            if not pn:
                warnings.append(
                    "• Part number is missing (required for specific)"
                )
            if self.brand_input.currentData() is None:
                warnings.append(
                    "• Brand is not set (required for specific)"
                )
            if not self.brand_pn_input.text().strip():
                warnings.append(
                    "• Brand part # is missing (required for specific)"
                )
            # Check for missing variant part numbers
            missing_pn = self._count_missing_variant_pns()
            if missing_pn > 0:
                warnings.append(
                    f"• {missing_pn} variant(s) missing part numbers"
                )
        else:
            if not pn:
                warnings.append("• Part number is empty (recommended)")

        # Show warning but don't block save
        if warnings:
            msg = (
                "This part has incomplete data:\n\n"
                + "\n".join(warnings)
                + "\n\nYou can save now and complete it later.\n"
                "Save anyway?"
            )
            reply = QMessageBox.question(
                self, "Incomplete Data", msg,
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
            )
            if reply != QMessageBox.Yes:
                return

        # Build supplier text from checked suppliers
        checked_names = [
            cb.text() for cb in self.supplier_checks.values()
            if cb.isChecked()
        ]
        supplier_text = checked_names[0] if checked_names else ""

        # Build part data — color_options and type_style are now "[]"
        # (variant tree replaces the old JSON fields)
        data = Part(
            id=self.part.id if self.part else None,
            name=name,
            part_number=pn,
            description=self.description_input.text().strip(),
            quantity=self.quantity_input.value(),
            min_quantity=self.min_quantity_input.value(),
            max_quantity=self.max_quantity_input.value(),
            location=self.location_input.text().strip(),
            category_id=self.category_input.currentData(),
            unit_cost=self.unit_cost_input.value(),
            supplier=supplier_text,
            notes=self.notes_input.toPlainText().strip(),
            part_type="specific" if is_specific else "general",
            brand_id=(
                self.brand_input.currentData() if is_specific else None
            ),
            brand_part_number=(
                self.brand_pn_input.text().strip() if is_specific else ""
            ),
            local_part_number=self.local_pn_input.text().strip(),
            image_path=self.image_path_input.text().strip(),
            subcategory=self.subcategory_input.currentText().strip(),
            color_options="[]",
            type_style="[]",
            has_qr_tag=1 if self.qr_tag_check.isChecked() else 0,
            pdfs=json.dumps(self._pdf_paths) if is_specific else "[]",
        )

        if self.part:
            self.repo.update_part(data)
            part_id = self.part.id
        else:
            part_id = self.repo.create_part(data)

        # Save linked suppliers (for BOTH types)
        if part_id:
            current_links = {
                ps.supplier_id
                for ps in self.repo.get_part_suppliers(part_id)
            }
            desired_links = {
                sid for sid, cb in self.supplier_checks.items()
                if cb.isChecked()
            }
            for sid in desired_links - current_links:
                self.repo.link_part_supplier(
                    PartSupplier(part_id=part_id, supplier_id=sid)
                )
            for sid in current_links - desired_links:
                self.repo.unlink_part_supplier(part_id, sid)

        # Save variants from tree (for BOTH types)
        if part_id:
            self._save_variants(part_id)

        self.accept()

    def _count_missing_variant_pns(self) -> int:
        """Count leaf nodes in the tree that are missing a part number."""
        count = 0
        for ts_idx in range(self.variant_tree.topLevelItemCount()):
            ts_item = self.variant_tree.topLevelItem(ts_idx)
            for c_idx in range(ts_item.childCount()):
                child = ts_item.child(c_idx)
                if not child.text(1).strip():
                    count += 1
        return count

    def _save_variants(self, part_id: int):
        """Sync variant tree to the database."""
        existing = self.repo.get_part_variants(part_id)
        existing_by_id = {v.id: v for v in existing}
        seen_ids = set()

        for ts_idx in range(self.variant_tree.topLevelItemCount()):
            ts_item = self.variant_tree.topLevelItem(ts_idx)
            type_style = ts_item.text(0)
            if type_style == "(No Type)":
                type_style = ""

            for c_idx in range(ts_item.childCount()):
                child = ts_item.child(c_idx)
                color = child.text(0).strip()
                if not color:
                    continue
                brand_pn = child.text(1).strip()
                img = child.text(2).strip()
                notes = child.text(3).strip()
                variant_id = child.data(0, Qt.UserRole)

                if variant_id and variant_id in existing_by_id:
                    # Update existing variant
                    v = existing_by_id[variant_id]
                    v.type_style = type_style
                    v.color_finish = color
                    v.brand_part_number = brand_pn
                    v.image_path = img
                    v.notes = notes
                    self.repo.update_part_variant(v)
                    seen_ids.add(variant_id)
                else:
                    # Create new variant
                    new_id = self.repo.create_part_variant(PartVariant(
                        part_id=part_id,
                        type_style=type_style,
                        color_finish=color,
                        brand_part_number=brand_pn,
                        image_path=img,
                        notes=notes,
                    ))
                    seen_ids.add(new_id)

        # Delete variants that are no longer in the tree
        for vid in existing_by_id:
            if vid not in seen_ids:
                self.repo.delete_part_variant(vid)
