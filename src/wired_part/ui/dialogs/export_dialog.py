"""Export dialog — format and destination selection."""

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)

from wired_part.database.repository import Repository
from wired_part.io.csv_handler import export_parts_csv, export_jobs_csv
from wired_part.io.excel_handler import export_parts_excel, export_jobs_excel


class ExportDialog(QDialog):
    """Export parts or jobs to CSV or Excel."""

    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.setWindowTitle("Export Data")
        self.setMinimumWidth(400)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.data_type = QComboBox()
        self.data_type.addItems(["Parts", "Jobs"])
        form.addRow("Data:", self.data_type)

        self.format_type = QComboBox()
        self.format_type.addItems(["CSV (.csv)", "Excel (.xlsx)"])
        form.addRow("Format:", self.format_type)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_export)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_export(self):
        data = self.data_type.currentText().lower()
        fmt = "csv" if "csv" in self.format_type.currentText().lower() else "xlsx"
        ext = f".{fmt}"

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export To", f"{data}_export{ext}",
            f"{'CSV' if fmt == 'csv' else 'Excel'} Files (*{ext})",
        )
        if not filepath:
            return

        try:
            if data == "parts" and fmt == "csv":
                count = export_parts_csv(self.repo, filepath)
            elif data == "parts" and fmt == "xlsx":
                count = export_parts_excel(self.repo, filepath)
            elif data == "jobs" and fmt == "csv":
                count = export_jobs_csv(self.repo, filepath)
            elif data == "jobs" and fmt == "xlsx":
                count = export_jobs_excel(self.repo, filepath)
            else:
                count = 0

            QMessageBox.information(
                self, "Export Complete",
                f"Exported {count} {data} to {filepath}",
            )
            self.accept()

        except Exception as e:
            QMessageBox.warning(self, "Export Failed", str(e))
