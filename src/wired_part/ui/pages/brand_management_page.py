"""Brand Management page — browse brands and their parts."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.models import Brand, User
from wired_part.database.repository import Repository
from wired_part.utils.formatters import format_currency


class BrandManagementPage(QWidget):
    """Split view: brand list on left, parts for selected brand on right.

    Actions: add, edit, delete brands. Edit parts via the part dialog.
    """

    def __init__(self, repo: Repository, current_user: User = None):
        super().__init__()
        self.repo = repo
        self.current_user = current_user
        self._perms: set[str] = set()
        if current_user:
            self._perms = repo.get_user_permissions(current_user.id)
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Header ──────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("Brand Management")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("color: #a6adc8;")
        header.addWidget(self.summary_label)
        layout.addLayout(header)

        # ── Button row ──────────────────────────────────────────
        btn_row = QHBoxLayout()

        self.add_btn = QPushButton("+ Add Brand")
        self.add_btn.setStyleSheet(
            "background-color: #a6e3a1; color: #1e1e2e; "
            "font-weight: bold; padding: 6px 14px;"
        )
        self.add_btn.clicked.connect(self._on_add_brand)
        self.add_btn.setVisible("parts_brands" in self._perms)
        btn_row.addWidget(self.add_btn)

        self.edit_brand_btn = QPushButton("Edit Brand")
        self.edit_brand_btn.clicked.connect(self._on_edit_brand)
        self.edit_brand_btn.setEnabled(False)
        self.edit_brand_btn.setVisible("parts_brands" in self._perms)
        btn_row.addWidget(self.edit_brand_btn)

        self.delete_brand_btn = QPushButton("Delete Brand")
        self.delete_brand_btn.setStyleSheet("color: #f38ba8;")
        self.delete_brand_btn.clicked.connect(self._on_delete_brand)
        self.delete_brand_btn.setEnabled(False)
        self.delete_brand_btn.setVisible("parts_brands" in self._perms)
        btn_row.addWidget(self.delete_brand_btn)

        btn_row.addStretch()

        self.edit_part_btn = QPushButton("Edit Part")
        self.edit_part_btn.clicked.connect(self._on_edit_part)
        self.edit_part_btn.setEnabled(False)
        self.edit_part_btn.setVisible("parts_edit" in self._perms)
        btn_row.addWidget(self.edit_part_btn)

        layout.addLayout(btn_row)

        # ── Splitter: brands list | parts table ─────────────────
        splitter = QSplitter(Qt.Horizontal)

        # Left: brands list
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        brand_search = QLineEdit()
        brand_search.setPlaceholderText("Filter brands...")
        brand_search.textChanged.connect(self._on_brand_filter)
        left_layout.addWidget(brand_search)

        self.brand_list = QListWidget()
        self.brand_list.currentItemChanged.connect(self._on_brand_selected)
        left_layout.addWidget(self.brand_list)

        splitter.addWidget(left_panel)

        # Right: parts for selected brand
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.parts_header = QLabel("Select a brand to see its parts")
        self.parts_header.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #cdd6f4;"
        )
        right_layout.addWidget(self.parts_header)

        self.parts_table = QTableWidget()
        self.parts_table.setColumnCount(7)
        self.parts_table.setHorizontalHeaderLabels([
            "Name", "Part #", "Description", "Brand Part #",
            "Unit Cost", "Qty", "Variants",
        ])
        self.parts_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.parts_table.setSelectionMode(QTableWidget.SingleSelection)
        self.parts_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.parts_table.setAlternatingRowColors(True)
        self.parts_table.setSortingEnabled(True)
        self.parts_table.horizontalHeader().setStretchLastSection(True)
        self.parts_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch  # Description column stretches
        )
        self.parts_table.selectionModel().selectionChanged.connect(
            self._on_part_selected
        )
        self.parts_table.doubleClicked.connect(self._on_edit_part)
        right_layout.addWidget(self.parts_table)

        splitter.addWidget(right_panel)
        splitter.setSizes([200, 500])
        layout.addWidget(splitter)

    def refresh(self):
        """Reload brands list."""
        self._load_brands()

    def _load_brands(self):
        """Populate the brands list."""
        current_name = None
        if self.brand_list.currentItem():
            current_name = self.brand_list.currentItem().text()

        self.brand_list.clear()
        brands = self.repo.get_all_brands()
        self.summary_label.setText(f"{len(brands)} brand(s)")

        for brand in brands:
            item = QListWidgetItem(brand.name)
            item.setData(Qt.ItemDataRole.UserRole, brand.id)
            self.brand_list.addItem(item)
            if brand.name == current_name:
                self.brand_list.setCurrentItem(item)

    def _on_brand_filter(self, text: str):
        """Filter brand list by search text."""
        text = text.strip().lower()
        for i in range(self.brand_list.count()):
            item = self.brand_list.item(i)
            item.setHidden(
                text != "" and text not in item.text().lower()
            )

    def _on_brand_selected(self, current, previous):
        """Load parts for the selected brand."""
        has_brand = current is not None
        self.edit_brand_btn.setEnabled(has_brand)
        self.delete_brand_btn.setEnabled(has_brand)

        if not has_brand:
            self.parts_header.setText("Select a brand to see its parts")
            self.parts_table.setRowCount(0)
            return

        brand_id = current.data(Qt.ItemDataRole.UserRole)
        brand_name = current.text()
        self.parts_header.setText(f"Parts for: {brand_name}")
        self._load_parts_for_brand(brand_id)

    def _load_parts_for_brand(self, brand_id: int):
        """Populate the parts table for a given brand."""
        parts = self.repo.get_parts_by_brand(brand_id)
        self.parts_table.setSortingEnabled(False)
        self.parts_table.setRowCount(len(parts))

        for row, part in enumerate(parts):
            variants = self.repo.get_part_variants(part.id)
            variant_count = len(variants)

            items = [
                QTableWidgetItem(part.display_name),
                QTableWidgetItem(part.part_number),
                QTableWidgetItem(part.description),
                QTableWidgetItem(part.brand_part_number),
                QTableWidgetItem(format_currency(part.unit_cost)),
                QTableWidgetItem(str(part.quantity)),
                QTableWidgetItem(
                    f"{variant_count} variant(s)"
                    if variant_count > 0 else "None"
                ),
            ]

            items[0].setData(Qt.ItemDataRole.UserRole, part.id)

            for col, item in enumerate(items):
                self.parts_table.setItem(row, col, item)

        self.parts_table.setSortingEnabled(True)

    def _on_part_selected(self):
        """Enable/disable part edit button."""
        has_sel = len(
            self.parts_table.selectionModel().selectedRows()
        ) > 0
        self.edit_part_btn.setEnabled(has_sel)

    def _selected_brand_id(self) -> int | None:
        item = self.brand_list.currentItem()
        if item:
            return item.data(Qt.ItemDataRole.UserRole)
        return None

    def _selected_part_id(self) -> int | None:
        rows = self.parts_table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.parts_table.item(rows[0].row(), 0)
        if item:
            return item.data(Qt.ItemDataRole.UserRole)
        return None

    # ── Actions ─────────────────────────────────────────────────

    def _on_add_brand(self):
        name, ok = QInputDialog.getText(
            self, "New Brand", "Brand name:"
        )
        if ok and name.strip():
            try:
                self.repo.create_brand(Brand(name=name.strip()))
                self.refresh()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def _on_edit_brand(self):
        brand_id = self._selected_brand_id()
        if brand_id is None:
            return
        brand = self.repo.get_brand_by_id(brand_id)
        if not brand:
            return
        name, ok = QInputDialog.getText(
            self, "Edit Brand", "Brand name:", text=brand.name
        )
        if ok and name.strip():
            try:
                brand.name = name.strip()
                self.repo.update_brand(brand)
                self.refresh()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def _on_delete_brand(self):
        brand_id = self._selected_brand_id()
        if brand_id is None:
            return
        brand = self.repo.get_brand_by_id(brand_id)
        if not brand:
            return

        parts = self.repo.get_parts_by_brand(brand_id)
        msg = f"Delete brand '{brand.name}'?"
        if parts:
            msg += (
                f"\n\n{len(parts)} part(s) reference this brand. "
                "Their brand will be set to None."
            )

        reply = QMessageBox.question(
            self, "Delete Brand", msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                self.repo.delete_brand(brand_id)
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _on_edit_part(self):
        part_id = self._selected_part_id()
        if part_id is None:
            return
        part = self.repo.get_part_by_id(part_id)
        if not part:
            return
        from wired_part.ui.dialogs.part_dialog import PartDialog
        dialog = PartDialog(self.repo, part=part, parent=self)
        if dialog.exec():
            # Refresh the parts table for the current brand
            brand_id = self._selected_brand_id()
            if brand_id:
                self._load_parts_for_brand(brand_id)
