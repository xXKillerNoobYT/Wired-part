"""Three-panel notebook widget: sections list | pages list | page editor."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.models import NotebookPage, NotebookSection
from wired_part.database.repository import Repository
from wired_part.ui.widgets.rich_text_editor import RichTextEditor
from wired_part.utils.constants import LOCKED_NOTEBOOK_SECTIONS


class NotebookWidget(QWidget):
    """Three-panel notebook: Sections | Pages | Rich Text Editor."""

    def __init__(self, repo: Repository, job_id: int,
                 user_id: int = None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.job_id = job_id
        self.user_id = user_id
        self._current_section_id = None
        self._current_page_id = None
        self._setup_ui()
        self._load_notebook()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)

        # ── Panel 1: Sections ─────────────────────────────────────
        sections_panel = QWidget()
        sections_layout = QVBoxLayout(sections_panel)
        sections_layout.setContentsMargins(0, 0, 0, 0)

        sec_header = QLabel("Sections")
        sec_header.setStyleSheet("font-weight: bold; font-size: 12px;")
        sections_layout.addWidget(sec_header)
        self.sections_list = QListWidget()
        self.sections_list.setToolTip(
            "Organize your notes into sections.\n"
            "The 'Daily Logs' section is locked and cannot be "
            "renamed or deleted."
        )
        self.sections_list.currentItemChanged.connect(
            self._on_section_selected
        )
        sections_layout.addWidget(self.sections_list, 1)

        sec_btns = QHBoxLayout()
        sec_btns.setSpacing(4)
        add_sec_btn = QPushButton("+ Add")
        add_sec_btn.setToolTip("Add a new section to this notebook")
        add_sec_btn.clicked.connect(self._on_add_section)
        sec_btns.addWidget(add_sec_btn)

        rename_sec_btn = QPushButton("Rename")
        rename_sec_btn.setToolTip("Rename the selected section")
        rename_sec_btn.clicked.connect(self._on_rename_section)
        sec_btns.addWidget(rename_sec_btn)

        del_sec_btn = QPushButton("Delete")
        del_sec_btn.setToolTip("Delete the selected section and all its pages")
        del_sec_btn.clicked.connect(self._on_delete_section)
        sec_btns.addWidget(del_sec_btn)
        sections_layout.addLayout(sec_btns)

        splitter.addWidget(sections_panel)

        # ── Panel 2: Pages ────────────────────────────────────────
        pages_panel = QWidget()
        pages_layout = QVBoxLayout(pages_panel)
        pages_layout.setContentsMargins(0, 0, 0, 0)

        pages_header = QLabel("Pages")
        pages_header.setStyleSheet("font-weight: bold; font-size: 12px;")
        pages_layout.addWidget(pages_header)
        self.pages_list = QListWidget()
        self.pages_list.setToolTip(
            "Pages within the selected section.\n"
            "Click a page to view/edit its content."
        )
        self.pages_list.currentItemChanged.connect(
            self._on_page_selected
        )
        pages_layout.addWidget(self.pages_list, 1)

        page_btns = QHBoxLayout()
        page_btns.setSpacing(4)
        add_page_btn = QPushButton("+ New Page")
        add_page_btn.setToolTip("Create a new page in this section")
        add_page_btn.clicked.connect(self._on_add_page)
        page_btns.addWidget(add_page_btn)

        del_page_btn = QPushButton("Delete Page")
        del_page_btn.setToolTip("Delete the selected page permanently")
        del_page_btn.clicked.connect(self._on_delete_page)
        page_btns.addWidget(del_page_btn)
        pages_layout.addLayout(page_btns)

        splitter.addWidget(pages_panel)

        # ── Panel 3: Editor ───────────────────────────────────────
        editor_panel = QWidget()
        editor_layout = QVBoxLayout(editor_panel)
        editor_layout.setContentsMargins(0, 0, 0, 0)

        # Title row
        title_row = QHBoxLayout()
        title_row.addWidget(QLabel("Title:"))
        self.page_title_input = QLineEdit()
        self.page_title_input.setPlaceholderText("Page title...")
        self.page_title_input.setEnabled(False)
        title_row.addWidget(self.page_title_input, 1)
        editor_layout.addLayout(title_row)

        # Rich text editor
        self.editor = RichTextEditor()
        self.editor.set_read_only(True)
        self.editor.content_changed.connect(self._auto_save)
        editor_layout.addWidget(self.editor, 1)

        # Status label
        self.status_label = QLabel("Select a page to edit")
        self.status_label.setStyleSheet("color: #6c7086; font-size: 11px;")
        editor_layout.addWidget(self.status_label)

        splitter.addWidget(editor_panel)
        splitter.setSizes([150, 180, 500])

        layout.addWidget(splitter)

    def _load_notebook(self):
        """Load or create the notebook for this job."""
        self.notebook = self.repo.get_or_create_notebook(self.job_id)
        self._load_sections()

    def switch_job(self, job_id: int):
        """Switch to a different job's notebook.

        Saves the current page, clears the UI, and reloads for the
        new job.
        """
        self._save_current_page()
        self.job_id = job_id
        self._current_section_id = None
        self._current_page_id = None
        self.pages_list.clear()
        self.page_title_input.clear()
        self.page_title_input.setEnabled(False)
        self.editor.set_content("")
        self.editor.set_read_only(True)
        self.status_label.setText("Loading notebook...")
        self._load_notebook()

    def _is_locked_section(self, name: str) -> bool:
        """Check if a section name is a locked (protected) section."""
        return name in LOCKED_NOTEBOOK_SECTIONS

    def _load_sections(self):
        """Load sections into the sections list."""
        self.sections_list.blockSignals(True)
        self.sections_list.clear()
        self._sections = self.repo.get_sections(self.notebook.id)
        for section in self._sections:
            label = section.name
            if self._is_locked_section(section.name):
                label = f"[Locked] {section.name}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, section.id)
            # Store the actual section name for lock checks
            item.setData(Qt.UserRole + 1, section.name)
            self.sections_list.addItem(item)
        self.sections_list.blockSignals(False)

        # Select first section if available
        if self._sections:
            self.sections_list.setCurrentRow(0)

    def _on_section_selected(self, current, previous):
        """Load pages for the selected section."""
        if not current:
            self.pages_list.clear()
            self._current_section_id = None
            return

        self._current_section_id = current.data(Qt.UserRole)
        self._load_pages()

    def _load_pages(self):
        """Load pages for the current section."""
        if not self._current_section_id:
            return

        self.pages_list.blockSignals(True)
        self.pages_list.clear()
        self._pages = self.repo.get_pages(self._current_section_id)
        for page in self._pages:
            item = QListWidgetItem(page.title or "Untitled")
            item.setData(Qt.UserRole, page.id)
            self.pages_list.addItem(item)
        self.pages_list.blockSignals(False)

        # Clear editor if no pages
        if not self._pages:
            self._clear_editor()
        else:
            self.pages_list.setCurrentRow(0)

    def _on_page_selected(self, current, previous):
        """Load the selected page into the editor."""
        # Save previous page if dirty
        if previous and self._current_page_id:
            self._save_current_page()

        if not current:
            self._clear_editor()
            return

        page_id = current.data(Qt.UserRole)
        page = self.repo.get_page_by_id(page_id)
        if not page:
            self._clear_editor()
            return

        self._current_page_id = page.id
        self.page_title_input.setEnabled(True)
        self.page_title_input.setText(page.title or "")
        self.editor.set_read_only(False)
        self.editor.set_html(page.content or "")
        self.status_label.setText(
            f"Last updated: {page.updated_at or 'never'}"
        )

    def _clear_editor(self):
        """Clear the editor to empty state."""
        self._current_page_id = None
        self.page_title_input.setEnabled(False)
        self.page_title_input.setText("")
        self.editor.set_read_only(True)
        self.editor.clear()
        self.status_label.setText("Select a page to edit")

    def _auto_save(self):
        """Auto-save the current page content."""
        self._save_current_page()

    def _save_current_page(self):
        """Save the current page to the database."""
        if not self._current_page_id:
            return

        page = self.repo.get_page_by_id(self._current_page_id)
        if not page:
            return

        page.title = self.page_title_input.text().strip() or "Untitled"
        page.content = self.editor.get_html()
        self.repo.update_page(page)
        self.status_label.setText("Saved")
        self.status_label.setStyleSheet(
            "color: #a6e3a1; font-size: 11px;"
        )
        # Reset status after 3 seconds
        QTimer.singleShot(
            3000,
            lambda: self.status_label.setText("Ready")
            if self.status_label.text() == "Saved" else None,
        )
        QTimer.singleShot(
            3000,
            lambda: self.status_label.setStyleSheet(
                "color: #6c7086; font-size: 11px;"
            )
            if self.status_label.text() == "Ready" else None,
        )

        # Update the page title in the list
        current_item = self.pages_list.currentItem()
        if current_item:
            current_item.setText(page.title)

    def _on_add_section(self):
        """Add a new section to this notebook."""
        name, ok = QInputDialog.getText(
            self, "New Section", "Section name:"
        )
        if ok and name.strip():
            # Prevent duplicate locked section names
            if self._is_locked_section(name.strip()):
                QMessageBox.warning(
                    self, "Reserved Name",
                    f"'{name.strip()}' is a reserved section name "
                    "and already exists.",
                )
                return
            section = NotebookSection(
                notebook_id=self.notebook.id,
                name=name.strip(),
            )
            self.repo.create_section(section)
            self._load_sections()
            # Select the new section (last one)
            self.sections_list.setCurrentRow(
                self.sections_list.count() - 1
            )

    def _on_rename_section(self):
        """Rename the selected section (blocked for locked sections)."""
        current = self.sections_list.currentItem()
        if not current:
            return

        # Check if this is a locked section
        section_name = current.data(Qt.UserRole + 1)
        if self._is_locked_section(section_name):
            QMessageBox.information(
                self, "Locked Section",
                f"'{section_name}' is a locked section and cannot "
                "be renamed.",
            )
            return

        section_id = current.data(Qt.UserRole)
        sections = [s for s in self._sections if s.id == section_id]
        if not sections:
            return

        section = sections[0]
        name, ok = QInputDialog.getText(
            self, "Rename Section", "New name:", text=section.name
        )
        if ok and name.strip():
            # Prevent renaming to a locked name
            if self._is_locked_section(name.strip()):
                QMessageBox.warning(
                    self, "Reserved Name",
                    f"'{name.strip()}' is a reserved section name.",
                )
                return
            section.name = name.strip()
            self.repo.update_section(section)
            current.setText(section.name)
            current.setData(Qt.UserRole + 1, section.name)

    def _on_delete_section(self):
        """Delete the selected section (blocked for locked sections)."""
        current = self.sections_list.currentItem()
        if not current:
            return

        # Check if this is a locked section
        section_name = current.data(Qt.UserRole + 1)
        if self._is_locked_section(section_name):
            QMessageBox.information(
                self, "Locked Section",
                f"'{section_name}' is a locked section and cannot "
                "be deleted.",
            )
            return

        section_id = current.data(Qt.UserRole)
        reply = QMessageBox.question(
            self, "Delete Section",
            f"Delete section '{section_name}' and all its pages?\n"
            "This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.repo.delete_section(section_id)
            self._load_sections()

    def _on_add_page(self):
        """Add a new page to the current section."""
        if not self._current_section_id:
            QMessageBox.information(
                self, "No Section", "Select a section first."
            )
            return

        title, ok = QInputDialog.getText(
            self, "New Page", "Page title:"
        )
        if ok:
            page = NotebookPage(
                section_id=self._current_section_id,
                title=title.strip() or "Untitled",
                created_by=self.user_id,
            )
            pid = self.repo.create_page(page)
            self._load_pages()
            # Select the new page (last one)
            self.pages_list.setCurrentRow(self.pages_list.count() - 1)

    def _on_delete_page(self):
        """Delete the selected page."""
        current = self.pages_list.currentItem()
        if not current:
            return
        page_id = current.data(Qt.UserRole)
        reply = QMessageBox.question(
            self, "Delete Page",
            f"Delete page '{current.text()}'?\n"
            "This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._current_page_id = None
            self.repo.delete_page(page_id)
            self._load_pages()
