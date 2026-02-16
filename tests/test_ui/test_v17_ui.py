"""UI tests for v17 features: dashboard buttons, clock dialog updates."""

import pytest

from wired_part.database.models import Job, JobAssignment, User
from wired_part.database.repository import Repository
from wired_part.ui.pages.dashboard_page import DashboardPage


class TestDashboardClockInButton:
    """Test the Clock In button on the dashboard."""

    def test_clock_in_btn_exists(self, qtbot, repo, admin_user):
        page = DashboardPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert hasattr(page, "clock_in_btn")

    def test_clock_in_btn_disabled_when_no_selection(
        self, qtbot, repo, admin_user
    ):
        page = DashboardPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert not page.clock_in_btn.isEnabled()

    def test_clock_in_btn_disabled_when_clocked_in(
        self, qtbot, repo, admin_user, sample_job
    ):
        """When already clocked in, Clock In button should be disabled."""
        # Assign user to job
        repo.assign_user_to_job(JobAssignment(
            job_id=sample_job.id, user_id=admin_user.id, role="lead",
        ))
        # Clock in
        repo.clock_in(
            user_id=admin_user.id,
            job_id=sample_job.id,
            category="Rough-in",
        )
        page = DashboardPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert not page.clock_in_btn.isEnabled()

    def test_my_jobs_list_shows_assigned_jobs(
        self, qtbot, repo, admin_user, sample_job
    ):
        """My Active Jobs list shows jobs user is assigned to."""
        repo.assign_user_to_job(JobAssignment(
            job_id=sample_job.id, user_id=admin_user.id, role="worker",
        ))
        page = DashboardPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        # List should have at least 1 item with the job number
        items = [
            page.my_jobs_list.item(i).text()
            for i in range(page.my_jobs_list.count())
        ]
        assert any("J-UI-001" in item for item in items)


class TestDashboardMakeOrderButton:
    """Test the Make Order button on the dashboard."""

    def test_make_order_btn_exists(self, qtbot, repo, admin_user):
        page = DashboardPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert hasattr(page, "make_order_btn")

    def test_make_order_btn_disabled_when_not_clocked_in(
        self, qtbot, repo, admin_user
    ):
        page = DashboardPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert not page.make_order_btn.isEnabled()

    def test_make_order_btn_enabled_when_clocked_in(
        self, qtbot, repo, admin_user, sample_job
    ):
        """Make Order button is enabled when the user is clocked in."""
        repo.assign_user_to_job(JobAssignment(
            job_id=sample_job.id, user_id=admin_user.id, role="worker",
        ))
        repo.clock_in(
            user_id=admin_user.id,
            job_id=sample_job.id,
            category="Rough-in",
        )
        page = DashboardPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.make_order_btn.isEnabled()


class TestDashboardJobNotesButton:
    """Test the Job Notes button on the dashboard."""

    def test_job_notes_btn_exists(self, qtbot, repo, admin_user):
        page = DashboardPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert hasattr(page, "job_notes_btn")

    def test_job_notes_btn_disabled_when_not_clocked_in(
        self, qtbot, repo, admin_user
    ):
        page = DashboardPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert not page.job_notes_btn.isEnabled()

    def test_job_notes_btn_enabled_when_clocked_in(
        self, qtbot, repo, admin_user, sample_job
    ):
        """Job Notes button is enabled when the user is clocked in."""
        repo.assign_user_to_job(JobAssignment(
            job_id=sample_job.id, user_id=admin_user.id, role="worker",
        ))
        repo.clock_in(
            user_id=admin_user.id,
            job_id=sample_job.id,
            category="Rough-in",
        )
        page = DashboardPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page.job_notes_btn.isEnabled()


class TestDashboardActiveJobTracking:
    """Test that dashboard tracks active job ID correctly."""

    def test_no_active_job_when_not_clocked_in(
        self, qtbot, repo, admin_user
    ):
        page = DashboardPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page._active_entry_id is None
        assert page._active_job_id is None

    def test_active_job_tracked_when_clocked_in(
        self, qtbot, repo, admin_user, sample_job
    ):
        repo.assign_user_to_job(JobAssignment(
            job_id=sample_job.id, user_id=admin_user.id, role="worker",
        ))
        eid = repo.clock_in(
            user_id=admin_user.id,
            job_id=sample_job.id,
            category="Testing",
        )
        page = DashboardPage(repo, current_user=admin_user)
        qtbot.addWidget(page)
        assert page._active_entry_id == eid
        assert page._active_job_id == sample_job.id


class TestClockDialogGPSSection:
    """Test that GPS fields are read-only (GPS-only input)."""

    def test_gps_section_exists_on_clock_in(
        self, qtbot, repo, admin_user, sample_job, monkeypatch
    ):
        from wired_part.ui.dialogs.clock_dialog import (
            ClockInDialog, _GPSSection,
        )
        monkeypatch.setattr(
            _GPSSection, "auto_detect", lambda self: None,
        )
        dlg = ClockInDialog(
            repo, user_id=admin_user.id, job_id=sample_job.id,
        )
        qtbot.addWidget(dlg)
        assert hasattr(dlg, "gps_section")
        assert isinstance(dlg.gps_section, _GPSSection)

    def test_gps_fields_are_read_only(
        self, qtbot, repo, admin_user, sample_job, monkeypatch
    ):
        """Lat/lon fields should be read-only — no manual entry."""
        from wired_part.ui.dialogs.clock_dialog import (
            ClockInDialog, _GPSSection,
        )
        monkeypatch.setattr(
            _GPSSection, "auto_detect", lambda self: None,
        )
        dlg = ClockInDialog(
            repo, user_id=admin_user.id, job_id=sample_job.id,
        )
        qtbot.addWidget(dlg)
        assert dlg.gps_section.lat_input.isReadOnly()
        assert dlg.gps_section.lon_input.isReadOnly()


class TestClockOutDialogV17:
    """Test ClockOutDialog v17 features."""

    def _make_clock_out_dialog(self, qtbot, repo, admin_user, sample_job,
                                monkeypatch):
        """Helper to create a ClockOutDialog with an active clock-in."""
        from wired_part.ui.dialogs.clock_dialog import (
            ClockOutDialog, _GPSSection,
        )
        monkeypatch.setattr(
            _GPSSection, "auto_detect", lambda self: None,
        )
        eid = repo.clock_in(
            user_id=admin_user.id,
            job_id=sample_job.id,
            category="Rough-in",
        )
        dlg = ClockOutDialog(repo, eid, parent=None)
        qtbot.addWidget(dlg)
        return dlg, eid

    def test_clock_out_has_work_description(
        self, qtbot, repo, admin_user, sample_job, monkeypatch
    ):
        dlg, _ = self._make_clock_out_dialog(
            qtbot, repo, admin_user, sample_job, monkeypatch,
        )
        assert hasattr(dlg, "description_input")

    def test_clock_out_has_drive_time_spinboxes(
        self, qtbot, repo, admin_user, sample_job, monkeypatch
    ):
        dlg, _ = self._make_clock_out_dialog(
            qtbot, repo, admin_user, sample_job, monkeypatch,
        )
        assert hasattr(dlg, "drive_hours")
        assert hasattr(dlg, "drive_minutes")
        # Check ranges
        assert dlg.drive_hours.minimum() == 0
        assert dlg.drive_hours.maximum() == 12
        assert dlg.drive_minutes.minimum() == 0
        assert dlg.drive_minutes.maximum() == 59

    def test_clock_out_has_no_overtime_checkbox(
        self, qtbot, repo, admin_user, sample_job, monkeypatch
    ):
        """Overtime checkbox was removed in v17."""
        dlg, _ = self._make_clock_out_dialog(
            qtbot, repo, admin_user, sample_job, monkeypatch,
        )
        assert not hasattr(dlg, "overtime_cb")

    def test_clock_out_has_checkout_checklist(
        self, qtbot, repo, admin_user, sample_job, monkeypatch
    ):
        dlg, _ = self._make_clock_out_dialog(
            qtbot, repo, admin_user, sample_job, monkeypatch,
        )
        assert hasattr(dlg, "chk_orders")
        assert hasattr(dlg, "chk_owner_notes")
        assert hasattr(dlg, "chk_materials")
        assert hasattr(dlg, "work_left_combo")
        assert hasattr(dlg, "plan_day1")
        assert hasattr(dlg, "plan_day2")
        assert hasattr(dlg, "next_big_things")

    def test_clock_out_has_freeform_notes(
        self, qtbot, repo, admin_user, sample_job, monkeypatch
    ):
        """User can add freeform notes — starts with one note field."""
        dlg, _ = self._make_clock_out_dialog(
            qtbot, repo, admin_user, sample_job, monkeypatch,
        )
        assert hasattr(dlg, "_note_inputs")
        assert len(dlg._note_inputs) >= 1  # Starts with at least one

    def test_clock_out_gps_is_read_only(
        self, qtbot, repo, admin_user, sample_job, monkeypatch
    ):
        """Clock-out GPS fields should also be read-only."""
        dlg, _ = self._make_clock_out_dialog(
            qtbot, repo, admin_user, sample_job, monkeypatch,
        )
        assert dlg.gps_section.lat_input.isReadOnly()
        assert dlg.gps_section.lon_input.isReadOnly()

    def test_collect_checkout_notes_returns_dict(
        self, qtbot, repo, admin_user, sample_job, monkeypatch
    ):
        """_collect_checkout_notes() returns a dict with checklist data."""
        dlg, _ = self._make_clock_out_dialog(
            qtbot, repo, admin_user, sample_job, monkeypatch,
        )
        notes = dlg._collect_checkout_notes()
        assert isinstance(notes, dict)
        assert "orders_done" in notes
        assert "owner_notes_done" in notes
        assert "materials_received" in notes
        assert "work_left" in notes
        assert "plan_day1" in notes
        assert "plan_day2" in notes
        assert "next_big_things" in notes
        assert "notes" in notes


class TestWorkDescriptionPrompts:
    """Test that construction prompt list exists."""

    def test_prompts_list_exists(self):
        from wired_part.ui.dialogs.clock_dialog import WORK_DESCRIPTION_PROMPTS
        assert isinstance(WORK_DESCRIPTION_PROMPTS, list)
        assert len(WORK_DESCRIPTION_PROMPTS) >= 5

    def test_prompts_are_strings(self):
        from wired_part.ui.dialogs.clock_dialog import WORK_DESCRIPTION_PROMPTS
        for prompt in WORK_DESCRIPTION_PROMPTS:
            assert isinstance(prompt, str)
            assert len(prompt) > 10  # Meaningful prompts
