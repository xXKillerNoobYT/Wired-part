"""Notebook dialog — wraps the 3-panel NotebookWidget for a specific job."""

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from wired_part.database.repository import Repository
from wired_part.ui.widgets.notebook_widget import NotebookWidget


class NotebookDialog(QDialog):
    """Full notebook dialog for a job — sections, pages, rich text editing."""

    def __init__(self, repo: Repository, job_id: int,
                 job_name: str = "", user_id: int = None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.job_id = job_id
        self.setWindowTitle(
            f"Job Notes: {job_name}" if job_name else "Job Notes"
        )
        self.resize(950, 650)
        self._setup_ui(user_id)

    def _setup_ui(self, user_id):
        layout = QVBoxLayout(self)

        # ── Search bar ────────────────────────────────────────────
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Search pages in this notebook..."
        )
        self.search_input.returnPressed.connect(self._on_search)
        search_layout.addWidget(self.search_input, 1)

        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._on_search)
        search_layout.addWidget(search_btn)

        global_search_btn = QPushButton("Search All Jobs")
        global_search_btn.clicked.connect(self._on_global_search)
        search_layout.addWidget(global_search_btn)

        layout.addLayout(search_layout)

        # ── Notebook widget ───────────────────────────────────────
        self.notebook_widget = NotebookWidget(
            self.repo, self.job_id, user_id=user_id, parent=self
        )
        layout.addWidget(self.notebook_widget, 1)

        # ── Bottom bar ────────────────────────────────────────────
        bottom = QHBoxLayout()
        bottom.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self._on_close)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

    def _on_search(self):
        """Search within this job's notebook pages."""
        query = self.search_input.text().strip()
        if not query:
            return

        results = self.repo.search_notebook_pages(
            query, job_id=self.job_id
        )
        if not results:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "No Results",
                f"No pages matching '{query}' found in this notebook."
            )
            return

        # Show search results dialog
        from wired_part.ui.dialogs.notes_search_dialog import (
            NotesSearchDialog,
        )
        dialog = NotesSearchDialog(
            self.repo, results, query=query, parent=self
        )
        dialog.exec()

    def _on_global_search(self):
        """Search across all job notebooks."""
        query = self.search_input.text().strip()
        if not query:
            return

        results = self.repo.search_notebook_pages(query)
        if not results:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "No Results",
                f"No pages matching '{query}' found across all notebooks."
            )
            return

        from wired_part.ui.dialogs.notes_search_dialog import (
            NotesSearchDialog,
        )
        dialog = NotesSearchDialog(
            self.repo, results, query=query, parent=self
        )
        dialog.exec()

    def _on_close(self):
        """Save current page before closing."""
        self.notebook_widget._save_current_page()
        self.accept()

    def closeEvent(self, event):
        """Save on window close."""
        self.notebook_widget._save_current_page()
        super().closeEvent(event)
