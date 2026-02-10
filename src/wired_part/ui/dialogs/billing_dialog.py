"""Billing report dialog — generate and export job billing reports."""

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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

from wired_part.database.repository import Repository
from wired_part.utils.formatters import format_currency


class BillingDialog(QDialog):
    """Generate billing reports for a job."""

    def __init__(self, repo: Repository, job_id: int, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.job_id = job_id
        self.setWindowTitle("Generate Billing Report")
        self.resize(700, 600)
        self._setup_ui()
        self._generate_preview()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Configuration
        config_group = QGroupBox("Report Settings")
        config_layout = QFormLayout()

        # Date range for progress billing
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(
            self.date_from.date().addMonths(-12)
        )
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        config_layout.addRow("From:", self.date_from)

        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(self.date_to.date())
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        config_layout.addRow("To:", self.date_to)

        # Markup
        self.markup_spin = QDoubleSpinBox()
        self.markup_spin.setRange(0, 500)
        self.markup_spin.setValue(0)
        self.markup_spin.setSuffix(" %")
        self.markup_spin.setToolTip("Markup percentage on parts cost")
        config_layout.addRow("Markup:", self.markup_spin)

        # Tax rate
        self.tax_spin = QDoubleSpinBox()
        self.tax_spin.setRange(0, 50)
        self.tax_spin.setValue(0)
        self.tax_spin.setSuffix(" %")
        self.tax_spin.setToolTip("Tax rate on subtotal + markup")
        config_layout.addRow("Tax Rate:", self.tax_spin)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # Buttons
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("Refresh Preview")
        refresh_btn.clicked.connect(self._generate_preview)
        btn_layout.addWidget(refresh_btn)

        export_btn = QPushButton("Export as Text File")
        export_btn.clicked.connect(self._export_text)
        btn_layout.addWidget(export_btn)

        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(self._copy_to_clipboard)
        btn_layout.addWidget(copy_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

        # Preview area
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        layout.addWidget(self.preview, 1)

    def _generate_preview(self):
        """Generate billing report text."""
        date_from = self.date_from.date().toString("yyyy-MM-dd")
        date_to = self.date_to.date().toString("yyyy-MM-dd")

        data = self.repo.get_billing_data(
            self.job_id, date_from, date_to
        )
        if not data:
            self.preview.setPlainText("No billing data found.")
            return

        markup_pct = self.markup_spin.value()
        tax_pct = self.tax_spin.value()

        # Build report text
        job = data["job"]
        lines = []
        lines.append("=" * 60)
        lines.append("BILLING REPORT")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Job:      {job['job_number']} — {job['name']}")
        if job["customer"]:
            lines.append(f"Customer: {job['customer']}")
        if job["address"]:
            lines.append(f"Address:  {job['address']}")
        lines.append(f"Status:   {job['status'].title()}")
        lines.append(f"Period:   {date_from} to {date_to}")
        lines.append(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        lines.append("")

        if data["assigned_users"]:
            lines.append("Assigned Personnel:")
            for u in data["assigned_users"]:
                lines.append(f"  - {u['name']} ({u['role'].title()})")
            lines.append("")

        # Parts by category
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

        # Totals
        lines.append("")
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
        lines.append("=" * 60)

        self._report_text = "\n".join(lines)
        self.preview.setPlainText(self._report_text)

    def _export_text(self):
        """Export report as a text file."""
        if not hasattr(self, "_report_text"):
            self._generate_preview()

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
        if not hasattr(self, "_report_text"):
            self._generate_preview()
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self._report_text)
        QMessageBox.information(
            self, "Copied", "Report copied to clipboard."
        )
