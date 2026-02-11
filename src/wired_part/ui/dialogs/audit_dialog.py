"""Fast inventory audit dialog — card-swipe interface for quick audits."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from wired_part.database.repository import Repository


class AuditDialog(QDialog):
    """Card-swipe audit interface for warehouse, truck, or job inventory.

    Users see one item at a time and can:
    - Confirm (actual = expected)
    - Mark discrepancy (enter actual count)
    - Skip for now
    """

    def __init__(
        self, repo: Repository,
        audit_type: str = "warehouse",
        target_id: int = None,
        target_name: str = "",
        current_user_id: int = None,
        parent=None,
    ):
        super().__init__(parent)
        self.repo = repo
        self.audit_type = audit_type
        self.target_id = target_id
        self.current_user_id = current_user_id
        self._items: list[dict] = []
        self._current_idx = 0
        self._results = {"confirmed": 0, "discrepancy": 0, "skipped": 0}

        title = f"Fast Audit: {target_name or audit_type.title()}"
        self.setWindowTitle(title)
        self.setMinimumSize(500, 450)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Mode selector ───────────────────────────────────────
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Audit Mode:"))

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("10 Oldest Items", 10)
        self.mode_combo.addItem("25 Items", 25)
        self.mode_combo.addItem("Full Audit", 0)
        mode_layout.addWidget(self.mode_combo)

        start_btn = QPushButton("Start Audit")
        start_btn.clicked.connect(self._start_audit)
        mode_layout.addWidget(start_btn)

        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # ── Progress bar ────────────────────────────────────────
        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setFormat("%v / %m items")
        layout.addWidget(self.progress)

        # ── Card view ───────────────────────────────────────────
        self.card_frame = QFrame()
        self.card_frame.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.card_frame.setStyleSheet(
            "QFrame { background: #313244; border-radius: 8px; padding: 16px; }"
        )
        card_layout = QVBoxLayout(self.card_frame)

        self.part_name_label = QLabel("Select mode and click Start Audit")
        self.part_name_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #cdd6f4;"
        )
        self.part_name_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.part_name_label)

        self.part_number_label = QLabel("")
        self.part_number_label.setStyleSheet(
            "font-size: 14px; color: #a6adc8;"
        )
        self.part_number_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.part_number_label)

        self.location_label = QLabel("")
        self.location_label.setStyleSheet("font-size: 13px; color: #6c7086;")
        self.location_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.location_label)

        # Expected quantity
        self.expected_label = QLabel("")
        self.expected_label.setStyleSheet(
            "font-size: 24px; font-weight: bold; color: #89b4fa;"
        )
        self.expected_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.expected_label)

        # Actual quantity input (for discrepancies)
        actual_layout = QHBoxLayout()
        actual_layout.addStretch()
        actual_layout.addWidget(QLabel("Actual Count:"))
        self.actual_spin = QSpinBox()
        self.actual_spin.setRange(0, 99999)
        self.actual_spin.setMinimumWidth(100)
        self.actual_spin.setStyleSheet("font-size: 16px;")
        actual_layout.addWidget(self.actual_spin)
        actual_layout.addStretch()
        card_layout.addLayout(actual_layout)

        layout.addWidget(self.card_frame, 1)

        # ── Action buttons ──────────────────────────────────────
        btn_layout = QHBoxLayout()

        self.skip_btn = QPushButton("Skip (Up)")
        self.skip_btn.setMinimumHeight(50)
        self.skip_btn.setStyleSheet(
            "background-color: #585b70; color: white; font-size: 14px;"
        )
        self.skip_btn.clicked.connect(self._on_skip)
        btn_layout.addWidget(self.skip_btn)

        self.discrep_btn = QPushButton("Discrepancy (Left)")
        self.discrep_btn.setMinimumHeight(50)
        self.discrep_btn.setStyleSheet(
            "background-color: #f38ba8; color: black; font-size: 14px;"
        )
        self.discrep_btn.clicked.connect(self._on_discrepancy)
        btn_layout.addWidget(self.discrep_btn)

        self.confirm_btn = QPushButton("Confirm (Right)")
        self.confirm_btn.setMinimumHeight(50)
        self.confirm_btn.setStyleSheet(
            "background-color: #a6e3a1; color: black; "
            "font-size: 14px; font-weight: bold;"
        )
        self.confirm_btn.clicked.connect(self._on_confirm)
        btn_layout.addWidget(self.confirm_btn)

        layout.addLayout(btn_layout)

        # ── Summary bar ─────────────────────────────────────────
        self.summary_label = QLabel("")
        self.summary_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.summary_label)

        # Disable action buttons until audit starts
        self._set_buttons_enabled(False)

    def _set_buttons_enabled(self, enabled: bool):
        self.confirm_btn.setEnabled(enabled)
        self.discrep_btn.setEnabled(enabled)
        self.skip_btn.setEnabled(enabled)
        self.actual_spin.setEnabled(enabled)

    def _start_audit(self):
        """Load items and begin the audit."""
        limit = self.mode_combo.currentData()
        self._items = self.repo.get_audit_items(
            self.audit_type, self.target_id, limit
        )

        if not self._items:
            QMessageBox.information(
                self, "No Items",
                "No items found to audit for this inventory.",
            )
            return

        self._current_idx = 0
        self._results = {"confirmed": 0, "discrepancy": 0, "skipped": 0}
        self.progress.setMaximum(len(self._items))
        self.progress.setValue(0)
        self._set_buttons_enabled(True)
        self._show_current_item()

    def _show_current_item(self):
        """Display the current audit item."""
        if self._current_idx >= len(self._items):
            self._show_summary()
            return

        item = self._items[self._current_idx]
        name = item.get("name") or item.get("part_number", "Unknown")
        pn = item.get("part_number", "")
        expected = item.get("expected_quantity", 0)
        location = item.get("location", "")

        self.part_name_label.setText(name)
        self.part_number_label.setText(f"P/N: {pn}" if pn else "")
        self.location_label.setText(
            f"Location: {location}" if location else ""
        )
        self.expected_label.setText(f"Expected: {expected}")
        self.actual_spin.setValue(expected)
        self._update_summary_bar()

    def _record_and_advance(self, status: str, actual: int):
        """Record the result and move to next item."""
        item = self._items[self._current_idx]
        self.repo.record_audit_result(
            audit_type=self.audit_type,
            target_id=self.target_id,
            part_id=item["part_id"],
            expected_quantity=item.get("expected_quantity", 0),
            actual_quantity=actual,
            status=status,
            audited_by=self.current_user_id,
        )
        self._results[status] += 1
        self._current_idx += 1
        self.progress.setValue(self._current_idx)
        self._show_current_item()

    def _on_confirm(self):
        """Confirm: actual = expected."""
        item = self._items[self._current_idx]
        expected = item.get("expected_quantity", 0)
        self._record_and_advance("confirmed", expected)

    def _on_discrepancy(self):
        """Mark discrepancy with the entered actual count."""
        actual = self.actual_spin.value()
        self._record_and_advance("discrepancy", actual)

    def _on_skip(self):
        """Skip this item."""
        self._record_and_advance("skipped", 0)

    def _update_summary_bar(self):
        """Update the running summary."""
        r = self._results
        total = self._current_idx
        remaining = len(self._items) - total
        self.summary_label.setText(
            f"Confirmed: {r['confirmed']}  |  "
            f"Discrepancies: {r['discrepancy']}  |  "
            f"Skipped: {r['skipped']}  |  "
            f"Remaining: {remaining}"
        )

    def _show_summary(self):
        """Show final audit summary."""
        self._set_buttons_enabled(False)
        r = self._results
        total = r["confirmed"] + r["discrepancy"] + r["skipped"]

        self.part_name_label.setText("Audit Complete!")
        self.part_number_label.setText("")
        self.location_label.setText("")
        self.expected_label.setText(
            f"Confirmed: {r['confirmed']}\n"
            f"Discrepancies: {r['discrepancy']}\n"
            f"Skipped: {r['skipped']}\n"
            f"Total: {total}"
        )
        self.summary_label.setText("Audit complete. Close to return.")

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts for audit actions."""
        if not self.confirm_btn.isEnabled():
            super().keyPressEvent(event)
            return

        key = event.key()
        if key == Qt.Key_Right or key == Qt.Key_Return:
            self._on_confirm()
        elif key == Qt.Key_Left:
            self._on_discrepancy()
        elif key == Qt.Key_Up:
            self._on_skip()
        else:
            super().keyPressEvent(event)
