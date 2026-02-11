"""Billing report dialog — generate and export job billing reports."""

from datetime import datetime, timedelta

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from wired_part.config import Config
from wired_part.database.repository import Repository
from wired_part.utils.formatters import format_currency


# ── Helper to compute period boundaries ──────────────────────

def _compute_periods(cycle_type: str, billing_day: int,
                     ref_date: datetime = None):
    """Return (period_start, period_end) for the current period."""
    ref = ref_date or datetime.now()
    if cycle_type == "weekly":
        # billing_day: 1=Mon … 7=Sun
        weekday_target = (billing_day - 1) % 7
        days_since = (ref.weekday() - weekday_target) % 7
        start = ref - timedelta(days=days_since)
        end = start + timedelta(days=6)
    elif cycle_type == "biweekly":
        weekday_target = (billing_day - 1) % 7
        days_since = (ref.weekday() - weekday_target) % 7
        start = ref - timedelta(days=days_since)
        # Go back one more week if in second week
        week_num = start.isocalendar()[1]
        if week_num % 2 != 0:
            start = start - timedelta(days=7)
        end = start + timedelta(days=13)
    elif cycle_type == "quarterly":
        quarter_start_month = ((ref.month - 1) // 3) * 3 + 1
        start = ref.replace(month=quarter_start_month, day=1)
        if quarter_start_month + 3 > 12:
            end = ref.replace(year=ref.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end = ref.replace(month=quarter_start_month + 3, day=1) - timedelta(days=1)
    else:  # monthly (default)
        day = min(billing_day, 28)  # Avoid month-end issues
        if ref.day >= day:
            start = ref.replace(day=day)
            if ref.month == 12:
                end = ref.replace(year=ref.year + 1, month=1, day=day) - timedelta(days=1)
            else:
                end = ref.replace(month=ref.month + 1, day=day) - timedelta(days=1)
        else:
            if ref.month == 1:
                start = ref.replace(year=ref.year - 1, month=12, day=day)
            else:
                start = ref.replace(month=ref.month - 1, day=day)
            end = ref.replace(day=day) - timedelta(days=1)

    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


class BillingDialog(QDialog):
    """Generate billing reports for a job with billing cycle support."""

    def __init__(self, repo: Repository, job_id: int, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.job_id = job_id
        self.setWindowTitle("Generate Billing Report")
        self.resize(750, 650)
        self._report_text = ""
        self._setup_ui()
        self._on_period_changed()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Billing Period ──────────────────────────────────────
        period_group = QGroupBox("Billing Period")
        period_layout = QFormLayout()

        self.cycle_type_combo = QComboBox()
        self.cycle_type_combo.addItem("Weekly", "weekly")
        self.cycle_type_combo.addItem("Biweekly", "biweekly")
        self.cycle_type_combo.addItem("Monthly", "monthly")
        self.cycle_type_combo.addItem("Quarterly", "quarterly")
        # Set default from config
        idx = self.cycle_type_combo.findData(Config.DEFAULT_BILLING_CYCLE)
        if idx >= 0:
            self.cycle_type_combo.setCurrentIndex(idx)
        self.cycle_type_combo.currentIndexChanged.connect(
            self._on_period_changed
        )
        period_layout.addRow("Cycle:", self.cycle_type_combo)

        # Period selector: auto-populates based on cycle
        self.period_combo = QComboBox()
        self.period_combo.currentIndexChanged.connect(
            self._on_period_selected
        )
        period_layout.addRow("Period:", self.period_combo)

        # Manual date override
        date_row = QHBoxLayout()
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        date_row.addWidget(QLabel("From:"))
        date_row.addWidget(self.date_from)

        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        date_row.addWidget(QLabel("To:"))
        date_row.addWidget(self.date_to)
        period_layout.addRow("Custom Range:", date_row)

        period_group.setLayout(period_layout)
        layout.addWidget(period_group)

        # ── Report Settings ─────────────────────────────────────
        config_group = QGroupBox("Report Settings")
        config_layout = QFormLayout()

        self.markup_spin = QDoubleSpinBox()
        self.markup_spin.setRange(0, 500)
        self.markup_spin.setValue(0)
        self.markup_spin.setSuffix(" %")
        self.markup_spin.setToolTip("Markup percentage on parts cost")
        config_layout.addRow("Markup:", self.markup_spin)

        self.tax_spin = QDoubleSpinBox()
        self.tax_spin.setRange(0, 50)
        self.tax_spin.setValue(0)
        self.tax_spin.setSuffix(" %")
        self.tax_spin.setToolTip("Tax rate on subtotal + markup")
        config_layout.addRow("Tax Rate:", self.tax_spin)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # ── Buttons ──────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("Generate Report")
        refresh_btn.clicked.connect(self._generate_preview)
        btn_layout.addWidget(refresh_btn)

        export_btn = QPushButton("Export as Text File")
        export_btn.clicked.connect(self._export_text)
        btn_layout.addWidget(export_btn)

        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(self._copy_to_clipboard)
        btn_layout.addWidget(copy_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

        # ── Preview ──────────────────────────────────────────────
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        layout.addWidget(self.preview, 1)

    def _on_period_changed(self):
        """Rebuild period options when cycle type changes."""
        cycle_type = self.cycle_type_combo.currentData() or "monthly"
        billing_day = Config.DEFAULT_BILLING_DAY

        self.period_combo.blockSignals(True)
        self.period_combo.clear()

        now = datetime.now()
        # Generate current + previous 5 periods
        for i in range(6):
            if cycle_type == "weekly":
                ref = now - timedelta(weeks=i)
            elif cycle_type == "biweekly":
                ref = now - timedelta(weeks=i * 2)
            elif cycle_type == "quarterly":
                ref = now - timedelta(days=i * 91)
            else:  # monthly
                month = now.month - i
                year = now.year
                while month < 1:
                    month += 12
                    year -= 1
                ref = now.replace(year=year, month=month, day=min(now.day, 28))

            start, end = _compute_periods(cycle_type, billing_day, ref)
            label = f"{start} → {end}"
            if i == 0:
                label += " (Current)"
            self.period_combo.addItem(label, (start, end))

        self.period_combo.blockSignals(False)
        self._on_period_selected()

    def _on_period_selected(self):
        """Update date range when a period is selected."""
        data = self.period_combo.currentData()
        if data:
            start, end = data
            self.date_from.setDate(QDate.fromString(start, "yyyy-MM-dd"))
            self.date_to.setDate(QDate.fromString(end, "yyyy-MM-dd"))

    def _generate_preview(self):
        """Generate billing report text."""
        date_from = self.date_from.date().toString("yyyy-MM-dd")
        date_to = self.date_to.date().toString("yyyy-MM-dd")
        cycle_type = self.cycle_type_combo.currentText()

        data = self.repo.get_billing_data(
            self.job_id, date_from, date_to
        )
        if not data:
            self.preview.setPlainText("No billing data found.")
            return

        # Also get labor summary
        labor_summary = self.repo.get_labor_summary_for_job(self.job_id)

        markup_pct = self.markup_spin.value()
        tax_pct = self.tax_spin.value()

        job = data["job"]
        lines = []
        lines.append("=" * 60)
        lines.append("BILLING REPORT")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Job:        {job['job_number']} — {job['name']}")
        if job["customer"]:
            lines.append(f"Customer:   {job['customer']}")
        if job["address"]:
            lines.append(f"Address:    {job['address']}")
        lines.append(f"Status:     {job['status'].title()}")
        lines.append(f"Cycle:      {cycle_type}")
        lines.append(f"Period:     {date_from} to {date_to}")
        lines.append(
            f"Generated:  {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        lines.append("")

        if data["assigned_users"]:
            lines.append("Assigned Personnel:")
            for u in data["assigned_users"]:
                lines.append(f"  - {u['name']} ({u['role'].title()})")
            lines.append("")

        # ── Materials section ──────────────────────────────
        subtotal = data["subtotal"]
        lines.append("-" * 60)
        lines.append("MATERIALS")
        lines.append("-" * 60)

        categories = data.get("categories", {})
        if categories:
            for cat_name, items in categories.items():
                lines.append(f"\n  {cat_name}")
                lines.append(
                    f"  {'Part #':<20} {'Description':<20} "
                    f"{'Qty':>5} {'Unit':>10} {'Total':>10}"
                )
                lines.append("  " + "-" * 67)
                cat_total = 0
                for item in items:
                    line_total = item["line_total"]
                    cat_total += line_total
                    desc = item["description"][:20]
                    lines.append(
                        f"  {item['part_number']:<20} {desc:<20} "
                        f"{item['quantity']:>5} "
                        f"{format_currency(item['unit_cost']):>10} "
                        f"{format_currency(line_total):>10}"
                    )
                lines.append(
                    f"  {'':>42} Category Total: "
                    f"{format_currency(cat_total):>10}"
                )
        else:
            lines.append("  No parts billed.")

        lines.append("")

        # ── Labor section ──────────────────────────────────
        lines.append("-" * 60)
        lines.append("LABOR HOURS")
        lines.append("-" * 60)

        total_hours = labor_summary.get("total_hours", 0)
        entry_count = labor_summary.get("entry_count", 0)
        lines.append(f"  Total Hours: {total_hours:.2f}")
        lines.append(f"  Entries: {entry_count}")

        by_cat = labor_summary.get("by_category", [])
        if by_cat:
            lines.append("")
            lines.append("  By Category:")
            for cat in by_cat:
                lines.append(
                    f"    {cat['category']}: {cat['hours']:.2f}h"
                )

        by_user = labor_summary.get("by_user", [])
        if by_user:
            lines.append("")
            lines.append("  By Worker:")
            for user in by_user:
                lines.append(
                    f"    {user['user']}: {user['hours']:.2f}h"
                )
        lines.append("")

        # ── Totals ─────────────────────────────────────────
        lines.append("=" * 60)
        lines.append(f"  {'Materials Subtotal:':>42} "
                      f"{format_currency(subtotal):>10}")

        if markup_pct > 0:
            markup_amt = subtotal * (markup_pct / 100)
            lines.append(
                f"  {'Markup (' + str(markup_pct) + '%):':>42} "
                f"{format_currency(markup_amt):>10}"
            )
            after_markup = subtotal + markup_amt
        else:
            after_markup = subtotal

        if tax_pct > 0:
            tax_amt = after_markup * (tax_pct / 100)
            lines.append(
                f"  {'Tax (' + str(tax_pct) + '%):':>42} "
                f"{format_currency(tax_amt):>10}"
            )
            grand_total = after_markup + tax_amt
        else:
            grand_total = after_markup

        lines.append("-" * 60)
        lines.append(f"  {'TOTAL DUE:':>42} "
                      f"{format_currency(grand_total):>10}")
        lines.append(f"  {'Total Labor Hours:':>42} "
                      f"{total_hours:>10.2f}")
        lines.append("=" * 60)

        self._report_text = "\n".join(lines)
        self.preview.setPlainText(self._report_text)

    def _export_text(self):
        """Export report as a text file."""
        if not self._report_text:
            self._generate_preview()
        if not self._report_text:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Billing Report",
            f"billing_{self.job_id}.txt",
            "Text Files (*.txt);;All Files (*)",
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self._report_text)
                QMessageBox.information(
                    self, "Exported",
                    f"Report saved to: {path}"
                )
            except Exception as e:
                QMessageBox.warning(
                    self, "Error", f"Failed to save: {e}"
                )

    def _copy_to_clipboard(self):
        """Copy report text to clipboard."""
        if not self._report_text:
            self._generate_preview()
        if not self._report_text:
            return
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self._report_text)
        QMessageBox.information(
            self, "Copied", "Report copied to clipboard."
        )
