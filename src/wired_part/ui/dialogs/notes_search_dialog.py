"""Notes search results dialog — shows matching notebook pages."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from wired_part.database.models import NotebookPage
from wired_part.database.repository import Repository


class NotesSearchDialog(QDialog):
    """Display search results from notebook page searches."""

    COLUMNS = ["Title", "Section", "Created By", "Updated"]

    def __init__(self, repo: Repository, results: list[NotebookPage],
                 query: str = "", parent=None):
        super().__init__(parent)
        self.repo = repo
        self.results = results
        self.setWindowTitle(
            f"Search Results: '{query}'" if query else "Search Results"
        )
        self.resize(750, 500)
        self._setup_ui()
        self._populate()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Results header
        self.header_label = QLabel("")
        layout.addWidget(self.header_label)

        # Results table
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )
        self.table.selectionModel().selectionChanged.connect(
            self._on_result_selected
        )
        layout.addWidget(self.table)

        # Preview area
        preview_label = QLabel("Preview:")
        layout.addWidget(preview_label)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMaximumHeight(150)
        layout.addWidget(self.preview)

        # Bottom
        bottom = QHBoxLayout()
        bottom.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

    def _populate(self):
        """Fill the table with search results."""
        self.header_label.setText(
            f"{len(self.results)} result{'s' if len(self.results) != 1 else ''} found"
        )

        self.table.setRowCount(len(self.results))
        for row, page in enumerate(self.results):
            cells = [
                QTableWidgetItem(page.title or "Untitled"),
                QTableWidgetItem(page.section_name or ""),
                QTableWidgetItem(page.created_by_name or ""),
                QTableWidgetItem(str(page.updated_at or "")[:16]),
            ]
            for col, cell in enumerate(cells):
                self.table.setItem(row, col, cell)

    def _on_result_selected(self):
        """Show preview of the selected search result."""
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self.preview.clear()
            return

        page = self.results[rows[0].row()]
        # Show content preview (strip HTML for readability)
        content = page.content or ""
        # Simple HTML strip for preview
        import re
        text = re.sub(r"<[^>]+>", " ", content)
        text = re.sub(r"\s+", " ", text).strip()
        self.preview.setPlainText(text[:500] if text else "(empty page)")
