"""pytest-qt tests for UI widgets: notebook, search, toast."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget


# ── Notebook Widget ───────────────────────────────────────────

class TestNotebookWidget:
    def test_creates_without_crash(self, qtbot, repo, sample_job, admin_user):
        from wired_part.ui.widgets.notebook_widget import NotebookWidget
        w = NotebookWidget(
            repo, job_id=sample_job.id, user_id=admin_user.id,
        )
        qtbot.addWidget(w)
        assert w is not None

    def test_has_sections_list(self, qtbot, repo, sample_job, admin_user):
        from wired_part.ui.widgets.notebook_widget import NotebookWidget
        w = NotebookWidget(
            repo, job_id=sample_job.id, user_id=admin_user.id,
        )
        qtbot.addWidget(w)
        assert isinstance(w.sections_list, QListWidget)

    def test_has_pages_list(self, qtbot, repo, sample_job, admin_user):
        from wired_part.ui.widgets.notebook_widget import NotebookWidget
        w = NotebookWidget(
            repo, job_id=sample_job.id, user_id=admin_user.id,
        )
        qtbot.addWidget(w)
        assert isinstance(w.pages_list, QListWidget)

    def test_has_editor(self, qtbot, repo, sample_job, admin_user):
        from wired_part.ui.widgets.notebook_widget import NotebookWidget
        w = NotebookWidget(
            repo, job_id=sample_job.id, user_id=admin_user.id,
        )
        qtbot.addWidget(w)
        assert w.editor is not None

    def test_loads_default_sections(
        self, qtbot, repo, sample_job, admin_user
    ):
        from wired_part.ui.widgets.notebook_widget import NotebookWidget
        w = NotebookWidget(
            repo, job_id=sample_job.id, user_id=admin_user.id,
        )
        qtbot.addWidget(w)
        # Should have at least the default sections
        assert w.sections_list.count() >= 1


# ── Search Dialog ─────────────────────────────────────────────

class TestSearchDialog:
    def test_creates_without_crash(self, qtbot, repo):
        from wired_part.ui.widgets.search_dialog import SearchDialog
        dlg = SearchDialog(repo)
        qtbot.addWidget(dlg)
        assert dlg is not None

    def test_has_search_input(self, qtbot, repo):
        from wired_part.ui.widgets.search_dialog import SearchDialog
        dlg = SearchDialog(repo)
        qtbot.addWidget(dlg)
        assert dlg.search_input is not None

    def test_has_results_list(self, qtbot, repo):
        from wired_part.ui.widgets.search_dialog import SearchDialog
        dlg = SearchDialog(repo)
        qtbot.addWidget(dlg)
        assert dlg.results_list is not None

    def test_short_query_no_results(self, qtbot, repo):
        from wired_part.ui.widgets.search_dialog import SearchDialog
        dlg = SearchDialog(repo)
        qtbot.addWidget(dlg)
        dlg.search_input.setText("a")
        dlg._do_search()
        assert dlg.results_list.count() == 0

    def test_search_finds_jobs(self, qtbot, repo, sample_job):
        from wired_part.ui.widgets.search_dialog import SearchDialog
        dlg = SearchDialog(repo)
        qtbot.addWidget(dlg)
        dlg.search_input.setText("UI Test")
        dlg._do_search()
        assert dlg.results_list.count() >= 1

    def test_search_finds_parts(self, qtbot, repo, sample_parts):
        from wired_part.ui.widgets.search_dialog import SearchDialog
        dlg = SearchDialog(repo)
        qtbot.addWidget(dlg)
        dlg.search_input.setText("Wire")
        dlg._do_search()
        assert dlg.results_list.count() >= 1

    def test_object_names_set(self, qtbot, repo):
        """Verify QSS object names are assigned (no inline styles)."""
        from wired_part.ui.widgets.search_dialog import SearchDialog
        dlg = SearchDialog(repo)
        qtbot.addWidget(dlg)
        assert dlg.objectName() == "SearchDialog"
        assert dlg.search_input.objectName() == "SearchInput"
        assert dlg.results_list.objectName() == "SearchResultsList"

    def test_no_inline_stylesheets(self, qtbot, repo):
        """Search dialog should use QSS object names, not setStyleSheet()."""
        import inspect
        from wired_part.ui.widgets import search_dialog
        source = inspect.getsource(search_dialog)
        assert "setStyleSheet(" not in source


# ── Toast Widget ──────────────────────────────────────────────

class TestToast:
    def test_creates_without_crash(self, qtbot):
        from wired_part.ui.widgets.toast_widget import Toast
        t = Toast("Hello world")
        qtbot.addWidget(t)
        assert t is not None

    def test_displays_message(self, qtbot):
        from wired_part.ui.widgets.toast_widget import Toast
        t = Toast("Test message")
        qtbot.addWidget(t)
        assert "Test message" in t.label.text()

    def test_info_severity(self, qtbot):
        from wired_part.ui.widgets.toast_widget import Toast
        t = Toast("Info", severity="info")
        qtbot.addWidget(t)
        assert t is not None

    def test_error_severity(self, qtbot):
        from wired_part.ui.widgets.toast_widget import Toast
        t = Toast("Error", severity="error")
        qtbot.addWidget(t)
        assert t is not None

    def test_warning_severity(self, qtbot):
        from wired_part.ui.widgets.toast_widget import Toast
        t = Toast("Warning", severity="warning")
        qtbot.addWidget(t)
        assert t is not None

    def test_success_severity(self, qtbot):
        from wired_part.ui.widgets.toast_widget import Toast
        t = Toast("Success", severity="success")
        qtbot.addWidget(t)
        assert t is not None


class TestToastManager:
    def test_creates_without_crash(self, qtbot):
        from PySide6.QtWidgets import QMainWindow
        from wired_part.ui.widgets.toast_widget import ToastManager
        win = QMainWindow()
        qtbot.addWidget(win)
        mgr = ToastManager(win)
        assert mgr is not None

    def test_show_toast(self, qtbot):
        from PySide6.QtWidgets import QMainWindow
        from wired_part.ui.widgets.toast_widget import ToastManager
        win = QMainWindow()
        win.resize(800, 600)
        qtbot.addWidget(win)
        win.show()
        mgr = ToastManager(win)
        mgr.show_toast("Test toast")
        assert len(mgr._active_toasts) == 1

    def test_multiple_toasts_stack(self, qtbot):
        from PySide6.QtWidgets import QMainWindow
        from wired_part.ui.widgets.toast_widget import ToastManager
        win = QMainWindow()
        win.resize(800, 600)
        qtbot.addWidget(win)
        win.show()
        mgr = ToastManager(win)
        mgr.show_toast("Toast 1")
        mgr.show_toast("Toast 2")
        assert len(mgr._active_toasts) == 2
