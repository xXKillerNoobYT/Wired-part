"""Notebook dialog — wraps the 3-panel NotebookWidget for a specific job.

Opens as a non-modal window so the user can continue working in the
main application while notes are open.  Includes a job selector to
switch between jobs without closing.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from wired_part.database.repository import Repository
from wired_part.ui.widgets.notebook_widget import NotebookWidget


class NotebookDialog(QDialog):
    """Full notebook dialog for a job — sections, pages, rich text editing.

    Non-modal: does not block the parent window.
    """

    def __init__(self, repo: Repository, job_id: int,
                 job_name: str = "", user_id: int = None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.job_id = job_id
        self.user_id = user_id
        self._job_name = job_name
        self._update_title(job_name)
        self.resize(950, 650)

        # Non-modal so rest of program stays usable
        self.setWindowModality(Qt.NonModal)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self._setup_ui(user_id)

    def _update_title(self, job_name: str = ""):
        self.setWindowTitle(
            f"Job Notes: {job_name}" if job_name else "Job Notes"
        )

    # ── UI setup ───────────────────────────────────────────────

    def _setup_ui(self, user_id):
        layout = QVBoxLayout(self)

        # ── Job selector + search bar ──────────────────────────
        top_row = QHBoxLayout()

        top_row.addWidget(QLabel("Job:"))
        self.job_combo = QComboBox()
        self.job_combo.setEditable(True)
        self.job_combo.setMinimumWidth(250)
        self.job_combo.setInsertPolicy(QComboBox.NoInsert)
        self._populate_jobs()
        # Enable search-as-you-type
        completer = QCompleter(
            [self.job_combo.itemText(i)
             for i in range(self.job_combo.count())]
        )
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        self.job_combo.setCompleter(completer)
        self.job_combo.currentIndexChanged.connect(self._on_job_changed)
        top_row.addWidget(self.job_combo, 1)

        top_row.addWidget(QLabel("  "))  # spacer

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Search pages in this notebook..."
        )
        self.search_input.returnPressed.connect(self._on_search)
        top_row.addWidget(self.search_input, 1)

        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._on_search)
        top_row.addWidget(search_btn)

        global_search_btn = QPushButton("Search All Jobs")
        global_search_btn.clicked.connect(self._on_global_search)
        top_row.addWidget(global_search_btn)

        layout.addLayout(top_row)

        # ── Notebook widget ────────────────────────────────────
        self.notebook_widget = NotebookWidget(
            self.repo, self.job_id, user_id=user_id, parent=self
        )
        layout.addWidget(self.notebook_widget, 1)

        # ── Bottom bar ─────────────────────────────────────────
        bottom = QHBoxLayout()
        bottom.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self._on_close)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

    # ── Job management ─────────────────────────────────────────

    def _populate_jobs(self):
        """Fill the job combo with all jobs."""
        self.job_combo.blockSignals(True)
        self.job_combo.clear()
        jobs = self.repo.get_all_jobs()
        selected_idx = 0
        for i, job in enumerate(jobs):
            label = (
                f"{job.job_number} — {job.name}"
                if job.name else job.job_number
            )
            self.job_combo.addItem(label, job.id)
            if job.id == self.job_id:
                selected_idx = i
        self.job_combo.setCurrentIndex(selected_idx)
        self.job_combo.blockSignals(False)

    def _on_job_changed(self, index: int):
        """Switch to a different job's notebook."""
        new_job_id = self.job_combo.itemData(index)
        if new_job_id is None or new_job_id == self.job_id:
            return
        # Save current work
        self.notebook_widget._save_current_page()
        # Switch
        self.job_id = new_job_id
        job_label = self.job_combo.currentText()
        self._update_title(job_label)
        self.notebook_widget.switch_job(new_job_id)

    # ── Search ─────────────────────────────────────────────────

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

    # ── Close ──────────────────────────────────────────────────

    def _on_close(self):
        """Save current page before closing."""
        self.notebook_widget._save_current_page()
        self.close()

    def closeEvent(self, event):
        """Save on window close."""
        self.notebook_widget._save_current_page()
        super().closeEvent(event)
