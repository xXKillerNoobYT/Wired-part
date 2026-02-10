"""Import dialog — file picker with preview and validation."""

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from wired_part.database.repository import Repository
from wired_part.io.csv_handler import import_parts_csv
from wired_part.io.excel_handler import import_parts_excel


class ImportDialog(QDialog):
    """Import wizard for CSV or Excel files."""

    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.filepath: str | None = None
        self.setWindowTitle("Import Parts")
        self.setMinimumSize(500, 350)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # File picker
        file_row = QHBoxLayout()
        self.file_label = QLabel("No file selected")
        file_row.addWidget(self.file_label, 1)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        file_row.addWidget(browse_btn)
        layout.addLayout(file_row)

        # Options
        self.update_existing = QCheckBox(
            "Update existing parts (matched by part number)"
        )
        layout.addWidget(self.update_existing)

        # Results area
        layout.addWidget(QLabel("Results:"))
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        layout.addWidget(self.results_text)

        # Buttons
        btn_row = QHBoxLayout()
        self.import_btn = QPushButton("Import")
        self.import_btn.clicked.connect(self._on_import)
        self.import_btn.setEnabled(False)
        btn_row.addWidget(self.import_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _browse(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select Import File", "",
            "All Supported (*.csv *.xlsx);;CSV Files (*.csv);;Excel Files (*.xlsx)",
        )
        if filepath:
            self.filepath = filepath
            self.file_label.setText(Path(filepath).name)
            self.import_btn.setEnabled(True)

    def _on_import(self):
        if not self.filepath:
            return

        ext = Path(self.filepath).suffix.lower()
        update = self.update_existing.isChecked()

        if ext == ".csv":
            results = import_parts_csv(self.repo, self.filepath, update)
        elif ext == ".xlsx":
            results = import_parts_excel(self.repo, self.filepath, update)
        else:
            QMessageBox.warning(self, "Error", f"Unsupported file type: {ext}")
            return

        # Display results
        lines = [
            f"Imported: {results['imported']}",
            f"Updated: {results['updated']}",
            f"Skipped: {results['skipped']}",
        ]
        if results["errors"]:
            lines.append(f"\nErrors ({len(results['errors'])}):")
            lines.extend(f"  - {e}" for e in results["errors"][:20])
            if len(results["errors"]) > 20:
                lines.append(f"  ... and {len(results['errors']) - 20} more")

        self.results_text.setPlainText("\n".join(lines))

        total = results["imported"] + results["updated"]
        if total > 0:
            QMessageBox.information(
                self, "Import Complete",
                f"Successfully processed {total} parts.",
            )
