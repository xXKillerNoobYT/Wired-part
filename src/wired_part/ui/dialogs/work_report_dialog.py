"""Work report dialog — generate combined labor+parts+notes reports."""

import re
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
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


class WorkReportDialog(QDialog):
    """Generate comprehensive work reports combining labor, parts, and notes."""

    def __init__(self, repo: Repository, job_id: int, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.job_id = job_id
        self.setWindowTitle("Generate Work Report")
        self.resize(800, 700)
        self._report_text = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Configuration ─────────────────────────────────────────
        config_group = QGroupBox("Report Settings")
        config_layout = QFormLayout()

        # Report type
        self.type_selector = QComboBox()
        self.type_selector.addItem("Internal (Full Details)", "internal")
        self.type_selector.addItem("Client (Summary Only)", "client")
        config_layout.addRow("Report Type:", self.type_selector)

        # Date range
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(self.date_from.date().addMonths(-1))
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        config_layout.addRow("From:", self.date_from)

        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        config_layout.addRow("To:", self.date_to)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # ── Include sections ──────────────────────────────────────
        sections_group = QGroupBox("Include Sections")
        sections_layout = QHBoxLayout()

        self.include_labor = QCheckBox("Labor Entries")
        self.include_labor.setChecked(True)
        sections_layout.addWidget(self.include_labor)

        self.include_materials = QCheckBox("Materials / Parts")
        self.include_materials.setChecked(True)
        sections_layout.addWidget(self.include_materials)

        self.include_notes = QCheckBox("Notebook Pages")
        self.include_notes.setChecked(True)
        sections_layout.addWidget(self.include_notes)

        self.include_photos = QCheckBox("Photo References")
        self.include_photos.setChecked(False)
        sections_layout.addWidget(self.include_photos)

        sections_group.setLayout(sections_layout)
        layout.addWidget(sections_group)

        # ── Action buttons ────────────────────────────────────────
        btn_layout = QHBoxLayout()

        generate_btn = QPushButton("Generate Report")
        generate_btn.clicked.connect(self._generate)
        btn_layout.addWidget(generate_btn)

        export_btn = QPushButton("Export Text File")
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

        # ── Preview ───────────────────────────────────────────────
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        layout.addWidget(self.preview, 1)

    def _generate(self):
        """Generate the work report."""
        date_from = self.date_from.date().toString("yyyy-MM-dd")
        date_to = self.date_to.date().toString("yyyy-MM-dd")
        report_type = self.type_selector.currentData()

        data = self.repo.get_work_report_data(
            self.job_id,
            date_from=date_from,
            date_to=date_to,
            report_type=report_type,
        )

        if not data:
            self.preview.setPlainText("No data found for this job.")
            return

        lines = []
        job = data["job"]

        # Header
        lines.append("=" * 70)
        if report_type == "client":
            lines.append("WORK REPORT — CLIENT COPY")
        else:
            lines.append("WORK REPORT — INTERNAL")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"Job:        {job['job_number']} — {job['name']}")
        if job["customer"]:
            lines.append(f"Customer:   {job['customer']}")
        if job["address"]:
            lines.append(f"Address:    {job['address']}")
        lines.append(f"Status:     {job['status'].title()}")
        lines.append(f"Period:     {date_from} to {date_to}")
        lines.append(
            f"Generated:  {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        lines.append("")

        # Assigned personnel
        if data.get("assigned_users"):
            lines.append("Personnel:")
            for u in data["assigned_users"]:
                lines.append(f"  - {u['name']} ({u['role'].title()})")
            lines.append("")

        # Labor section
        if self.include_labor.isChecked():
            labor = data.get("labor", {})
            entries = labor.get("entries", [])
            summary = labor.get("summary", {})

            lines.append("-" * 70)
            lines.append("LABOR")
            lines.append("-" * 70)

            if entries:
                lines.append(
                    f"  {'Date':<20} {'Worker':<15} {'Category':<12} "
                    f"{'Hours':>6}"
                )
                lines.append("  " + "-" * 55)
                for entry in entries:
                    date_str = str(entry["date"])[:10]
                    lines.append(
                        f"  {date_str:<20} "
                        f"{entry['user'][:15]:<15} "
                        f"{entry['category'][:12]:<12} "
                        f"{entry['hours']:>6.2f}"
                    )
                    if entry.get("description"):
                        lines.append(f"    > {entry['description']}")
                lines.append("")

                # Summary
                total_hours = summary.get("total_hours", 0)
                lines.append(
                    f"  Total Hours: {total_hours:.2f}"
                )

                by_cat = summary.get("by_category", [])
                if by_cat:
                    lines.append("")
                    lines.append("  Hours by Category:")
                    for cat in by_cat:
                        lines.append(
                            f"    {cat['category']}: {cat['hours']:.2f}h"
                        )
            else:
                lines.append("  No labor entries for this period.")
            lines.append("")

        # Materials section
        if self.include_materials.isChecked():
            materials = data.get("materials", {})
            subtotal = data.get("materials_subtotal", 0)

            lines.append("-" * 70)
            lines.append("MATERIALS")
            lines.append("-" * 70)

            if materials:
                for cat_name, items in materials.items():
                    lines.append(f"\n  {cat_name}")
                    lines.append(
                        f"  {'Part #':<18} {'Description':<18} "
                        f"{'Qty':>5} {'Unit':>10} {'Total':>10}"
                    )
                    lines.append("  " + "-" * 63)
                    cat_total = 0
                    for item in items:
                        line_total = item.get("line_total", 0)
                        cat_total += line_total
                        desc = item["description"][:18]
                        lines.append(
                            f"  {item['part_number']:<18} {desc:<18} "
                            f"{item['quantity']:>5} "
                            f"{format_currency(item['unit_cost']):>10} "
                            f"{format_currency(line_total):>10}"
                        )
                    lines.append(
                        f"  {'':>42} Subtotal: "
                        f"{format_currency(cat_total):>10}"
                    )
                lines.append("")
                lines.append(
                    f"  Materials Total: {format_currency(subtotal)}"
                )
            else:
                lines.append("  No materials billed for this period.")
            lines.append("")

        # Notes section
        if self.include_notes.isChecked():
            notes = data.get("notes", [])

            lines.append("-" * 70)
            lines.append("NOTES")
            lines.append("-" * 70)

            if notes:
                for note in notes:
                    lines.append(
                        f"\n  [{note['section']}] {note['title']}"
                    )
                    if note.get("created_by"):
                        lines.append(
                            f"  By: {note['created_by']} "
                            f"({note['created_at'][:10]})"
                        )
                    # Strip HTML from content
                    content = note.get("content", "")
                    if content:
                        text = re.sub(r"<[^>]+>", " ", content)
                        text = re.sub(r"\s+", " ", text).strip()
                        if text:
                            # Wrap long text
                            for i in range(0, len(text), 65):
                                lines.append(f"    {text[i:i+65]}")
            else:
                lines.append("  No notebook pages found.")
            lines.append("")

        # Photos section
        if self.include_photos.isChecked():
            photos = data.get("photos", [])
            if photos:
                lines.append("-" * 70)
                lines.append("PHOTO REFERENCES")
                lines.append("-" * 70)
                for i, photo in enumerate(photos, 1):
                    lines.append(f"  {i}. {photo}")
                lines.append("")

        # Footer
        lines.append("=" * 70)
        lines.append("END OF REPORT")
        lines.append("=" * 70)

        self._report_text = "\n".join(lines)
        self.preview.setPlainText(self._report_text)

    def _export_text(self):
        """Export report as a text file."""
        if not self._report_text:
            self._generate()
        if not self._report_text:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Work Report",
            f"work_report_{self.job_id}.txt",
            "Text Files (*.txt);;All Files (*)",
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self._report_text)
                QMessageBox.information(
                    self, "Exported", f"Report saved to: {path}"
                )
            except Exception as e:
                QMessageBox.warning(
                    self, "Error", f"Failed to save: {e}"
                )

    def _copy_to_clipboard(self):
        """Copy report text to clipboard."""
        if not self._report_text:
            self._generate()
        if not self._report_text:
            return
        clipboard = QApplication.clipboard()
        clipboard.setText(self._report_text)
        QMessageBox.information(
            self, "Copied", "Report copied to clipboard."
        )
