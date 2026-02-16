"""pytest-qt tests for the Jobs Page widget."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QLineEdit, QPushButton

from wired_part.database.models import Job
from wired_part.ui.pages.jobs_page import JobsPage


class TestJobsPageWidget:
    """Test the JobsPage widget instantiation and behavior."""

    def test_creates_without_crash(self, qtbot, repo, admin_user):
        """JobsPage can be instantiated."""
        page = JobsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page is not None

    def test_has_add_button(self, qtbot, repo, admin_user):
        """Page has a '+ New Job' button."""
        page = JobsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.add_btn.text() == "+ New Job"

    def test_status_filter_has_all_option(self, qtbot, repo, admin_user):
        """Status filter combo starts with 'All'."""
        page = JobsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.status_filter.itemText(0) == "All"

    def test_search_input_exists(self, qtbot, repo, admin_user):
        """Search input is present and has placeholder."""
        page = JobsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.search_input.placeholderText() == "Search jobs..."

    def test_empty_job_list(self, qtbot, repo, admin_user):
        """With no jobs, the job list should be empty."""
        page = JobsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page._jobs == []

    def test_job_appears_in_list(
        self, qtbot, repo, admin_user, sample_job
    ):
        """After creating a job, it appears in the page."""
        page = JobsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        page.refresh()
        assert len(page._jobs) >= 1
        job_numbers = [j.job_number for j in page._jobs]
        assert "J-UI-001" in job_numbers

    def test_multiple_jobs_all_visible(self, qtbot, repo, admin_user):
        """Multiple jobs all show up."""
        for i in range(5):
            repo.create_job(Job(
                job_number=f"J-MULTI-{i:03d}",
                name=f"Multi Job {i}",
                status="active",
            ))
        page = JobsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        page.refresh()
        assert len(page._jobs) >= 5

    def test_refresh_does_not_crash(self, qtbot, repo, admin_user):
        """Calling refresh on empty DB is safe."""
        page = JobsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        page.refresh()

    def test_users_list_has_context_menu_policy(
        self, qtbot, repo, admin_user
    ):
        """Users list supports right-click context menu."""
        page = JobsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert (
            page.users_list.contextMenuPolicy()
            == Qt.ContextMenuPolicy.CustomContextMenu
        )

    def test_current_assignments_stored(
        self, qtbot, repo, admin_user, sample_job
    ):
        """Selecting a job populates _current_assignments."""
        from wired_part.database.models import JobAssignment
        repo.assign_user_to_job(JobAssignment(
            job_id=sample_job.id, user_id=admin_user.id, role="lead",
        ))
        page = JobsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        page.refresh()
        # Select the first job in the list
        page.job_list.setCurrentRow(0)
        assert len(page._current_assignments) >= 1
        assert page._current_assignments[0].user_name == admin_user.display_name

    def test_change_role_toggles(
        self, qtbot, repo, admin_user, sample_job
    ):
        """_on_change_role toggles lead ↔ worker."""
        from wired_part.database.models import JobAssignment
        repo.assign_user_to_job(JobAssignment(
            job_id=sample_job.id, user_id=admin_user.id, role="lead",
        ))
        page = JobsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        page.refresh()
        page.job_list.setCurrentRow(0)
        # Should be "lead" initially
        assert page._current_assignments[0].role == "lead"
        # Toggle to worker
        page._on_change_role(page._current_assignments[0])
        assert page._current_assignments[0].role == "worker"

    def test_remove_user_from_job(
        self, qtbot, repo, admin_user, sample_job, monkeypatch
    ):
        """_on_remove_user removes the user after confirmation."""
        from wired_part.database.models import JobAssignment
        repo.assign_user_to_job(JobAssignment(
            job_id=sample_job.id, user_id=admin_user.id, role="lead",
        ))
        page = JobsPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        page.refresh()
        page.job_list.setCurrentRow(0)
        assert len(page._current_assignments) == 1
        # Auto-confirm the dialog
        from PySide6.QtWidgets import QMessageBox
        monkeypatch.setattr(
            QMessageBox, "question",
            lambda *a, **kw: QMessageBox.Yes,
        )
        page._on_remove_user(page._current_assignments[0])
        # After removal, assignments should be empty
        assert len(page._current_assignments) == 0
