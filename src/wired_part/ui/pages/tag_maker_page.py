"""Tag Maker page — track and batch-mark QR tag status for parts."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.models import User
from wired_part.database.repository import Repository


class TagMakerPage(QWidget):
    """View and batch-update QR tag status for parts.

    Features:
    - Filter: Needs Tag / Has Tag / All
    - Search bar
    - Checkbox column for batch selection
    - Mark selected as tagged / untagged
    - Summary stats
    """

    COLUMNS = [
        "", "Name", "Part #", "Description", "Type", "Category",
        "Location", "QR Status",
    ]

    def __init__(self, repo: Repository, current_user: User = None):
        super().__init__()
        self.repo = repo
        self.current_user = current_user
        self._perms: set[str] = set()
        if current_user:
            self._perms = repo.get_user_permissions(current_user.id)
        self._parts = []
        self._checks: list[QCheckBox] = []
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Header ──────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("Tag Maker")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("color: #a6adc8;")
        header.addWidget(self.summary_label)
        layout.addLayout(header)

        # ── Toolbar ─────────────────────────────────────────────
        toolbar = QHBoxLayout()

        self.tag_filter = QComboBox()
        self.tag_filter.addItem("Needs Tag", "needs")
        self.tag_filter.addItem("Has Tag", "has")
        self.tag_filter.addItem("All Parts", "all")
        self.tag_filter.currentIndexChanged.connect(self._on_filter)
        toolbar.addWidget(self.tag_filter)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search parts...")
        self.search_input.textChanged.connect(self._on_filter)
        toolbar.addWidget(self.search_input, 1)

        layout.addLayout(toolbar)

        # ── Action buttons ──────────────────────────────────────
        btn_row = QHBoxLayout()

        self.select_all_btn = QPushButton("Select All Visible")
        self.select_all_btn.clicked.connect(self._on_select_all)
        btn_row.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(self._on_deselect_all)
        btn_row.addWidget(self.deselect_all_btn)

        btn_row.addStretch()

        self.mark_tagged_btn = QPushButton("Mark Selected as Tagged")
        self.mark_tagged_btn.setStyleSheet(
            "background-color: #a6e3a1; color: #1e1e2e; "
            "font-weight: bold; padding: 6px 14px;"
        )
        self.mark_tagged_btn.clicked.connect(
            lambda: self._batch_update_tags(1)
        )
        can_tag = "parts_qr_tags" in self._perms
        self.mark_tagged_btn.setVisible(can_tag)
        btn_row.addWidget(self.mark_tagged_btn)

        self.mark_untagged_btn = QPushButton("Mark Selected as Untagged")
        self.mark_untagged_btn.setStyleSheet("color: #f38ba8;")
        self.mark_untagged_btn.clicked.connect(
            lambda: self._batch_update_tags(0)
        )
        self.mark_untagged_btn.setVisible(can_tag)
        btn_row.addWidget(self.mark_untagged_btn)

        layout.addLayout(btn_row)

        # ── Table ───────────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.Stretch  # Description stretches
        )
        # Narrow checkbox column
        self.table.setColumnWidth(0, 40)
        layout.addWidget(self.table)

        # ── Print tags ───────────────────────────────────────────
        print_row = QHBoxLayout()
        print_row.addStretch()
        self.print_btn = QPushButton("Print Tags")
        self.print_btn.setStyleSheet(
            "background-color: #89b4fa; color: #1e1e2e; "
            "font-weight: bold; padding: 6px 14px;"
        )
        self.print_btn.setToolTip(
            "Generate a printable PDF of QR tags for selected parts"
        )
        self.print_btn.clicked.connect(self._on_print_tags)
        self.print_btn.setVisible(can_tag)
        print_row.addWidget(self.print_btn)
        layout.addLayout(print_row)

    def refresh(self):
        """Reload parts data."""
        self._parts = self.repo.get_all_parts()
        self._on_filter()

    def _on_filter(self):
        """Apply tag filter and search."""
        tag_mode = self.tag_filter.currentData()
        search = self.search_input.text().strip().lower()

        filtered = []
        for part in self._parts:
            # Tag filter
            if tag_mode == "needs" and part.has_qr_tag:
                continue
            elif tag_mode == "has" and not part.has_qr_tag:
                continue

            # Search filter
            if search:
                searchable = (
                    f"{part.name} {part.part_number} {part.description} "
                    f"{part.category_name} {part.location}"
                ).lower()
                if search not in searchable:
                    continue

            filtered.append(part)

        self._populate_table(filtered)

    def _populate_table(self, parts):
        """Fill the table with filtered parts."""
        self.table.setRowCount(len(parts))
        self._checks.clear()

        needs_count = sum(1 for p in self._parts if not p.has_qr_tag)
        has_count = sum(1 for p in self._parts if p.has_qr_tag)

        for row, part in enumerate(parts):
            # Checkbox
            cb = QCheckBox()
            self._checks.append(cb)
            cb_widget = QWidget()
            cb_layout = QHBoxLayout(cb_widget)
            cb_layout.addWidget(cb)
            cb_layout.setAlignment(Qt.AlignCenter)
            cb_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 0, cb_widget)

            type_badge = "S" if part.is_specific else "G"
            tag_status = "Tagged" if part.has_qr_tag else "Needs Tag"

            items = [
                None,  # checkbox column
                QTableWidgetItem(part.display_name),
                QTableWidgetItem(part.part_number),
                QTableWidgetItem(part.description),
                QTableWidgetItem(type_badge),
                QTableWidgetItem(part.category_name),
                QTableWidgetItem(part.location or ""),
                QTableWidgetItem(tag_status),
            ]

            # Store part_id on the Name column
            items[1].setData(Qt.ItemDataRole.UserRole, part.id)

            # Color the status
            if part.has_qr_tag:
                items[7].setForeground(QColor("#a6e3a1"))  # Green
            else:
                items[7].setForeground(QColor("#f9e2af"))  # Yellow

            # Type badge color
            if part.is_specific:
                items[4].setForeground(QColor("#89b4fa"))
            else:
                items[4].setForeground(QColor("#a6e3a1"))

            for col in range(1, len(items)):
                if items[col]:
                    self.table.setItem(row, col, items[col])

        self.summary_label.setText(
            f"{needs_count} need tags  |  {has_count} have tags  |  "
            f"{len(self._parts)} total"
        )

    def _on_select_all(self):
        for cb in self._checks:
            cb.setChecked(True)

    def _on_deselect_all(self):
        for cb in self._checks:
            cb.setChecked(False)

    def _batch_update_tags(self, value: int):
        """Set has_qr_tag for all checked rows."""
        action = "tagged" if value else "untagged"
        updated = 0

        for row, cb in enumerate(self._checks):
            if not cb.isChecked():
                continue
            item = self.table.item(row, 1)  # Name column
            if not item:
                continue
            part_id = item.data(Qt.ItemDataRole.UserRole)
            if part_id is None:
                continue
            part = self.repo.get_part_by_id(part_id)
            if part and part.has_qr_tag != value:
                part.has_qr_tag = value
                self.repo.update_part(part)
                updated += 1

        if updated > 0:
            QMessageBox.information(
                self, "Tags Updated",
                f"Marked {updated} part(s) as {action}.",
            )
            self.refresh()
        else:
            QMessageBox.information(
                self, "No Changes",
                "No parts were selected or needed updating.",
            )

    def _on_print_tags(self):
        """Generate QR tag PDF for all checked parts."""
        selected_parts = []
        for row, cb in enumerate(self._checks):
            if not cb.isChecked():
                continue
            item = self.table.item(row, 1)  # Name column
            if not item:
                continue
            part_id = item.data(Qt.ItemDataRole.UserRole)
            if part_id is None:
                continue
            part = self.repo.get_part_by_id(part_id)
            if part:
                selected_parts.append({
                    "part_id": part.id,
                    "name": part.display_name,
                    "part_number": part.part_number,
                    "local_part_number": part.local_part_number,
                    "location": part.location or "",
                    "category_name": part.category_name,
                })

        if not selected_parts:
            QMessageBox.information(
                self, "No Selection",
                "Select one or more parts to generate QR tags.",
            )
            return

        try:
            from wired_part.utils.qr_generator import generate_qr_tags

            pdf_path = generate_qr_tags(selected_parts)

            # Open the PDF for the user
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices

            QDesktopServices.openUrl(QUrl.fromLocalFile(pdf_path))

            # Ask if user wants to mark these as tagged
            reply = QMessageBox.question(
                self, "Tags Generated",
                f"QR tags PDF generated with {len(selected_parts)} "
                f"tag(s).\n\nMark these parts as tagged?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
            )
            if reply == QMessageBox.Yes:
                for part_data in selected_parts:
                    part = self.repo.get_part_by_id(part_data["part_id"])
                    if part and not part.has_qr_tag:
                        part.has_qr_tag = 1
                        self.repo.update_part(part)
                self.refresh()

        except ImportError as e:
            QMessageBox.critical(
                self, "Missing Dependencies",
                "QR tag generation requires 'qrcode' and "
                "'reportlab' packages.\n\n"
                "Install them with:\n"
                "  pip install qrcode[pil] reportlab\n\n"
                f"Error: {e}",
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Generation Error",
                f"Failed to generate QR tags:\n\n{e}",
            )
