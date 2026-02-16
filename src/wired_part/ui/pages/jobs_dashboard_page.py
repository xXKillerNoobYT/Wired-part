"""Jobs Dashboard — summary cards for job tracking overview."""

from datetime import datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.models import User
from wired_part.database.repository import Repository
from wired_part.ui.pages.dashboard_page import SummaryCard


class JobsDashboardPage(QWidget):
    """Jobs overview with active/on-hold counts and recent activity."""

    def __init__(self, repo: Repository, current_user: User, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.current_user = current_user
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)

        title = QLabel("Jobs Dashboard")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        # Summary cards
        cards = QGridLayout()
        self.active_jobs_card = SummaryCard("Active Jobs")
        self.on_hold_card = SummaryCard("On Hold")
        self.completed_card = SummaryCard("Recently Completed")
        self.labor_hours_card = SummaryCard("Labor Hours This Period")

        cards.addWidget(self.active_jobs_card, 0, 0)
        cards.addWidget(self.on_hold_card, 0, 1)
        cards.addWidget(self.completed_card, 0, 2)
        cards.addWidget(self.labor_hours_card, 0, 3)
        layout.addLayout(cards)

        # Bottom section
        bottom = QHBoxLayout()

        # My Active Jobs
        my_jobs_group = QGroupBox("My Active Jobs")
        my_jobs_layout = QVBoxLayout(my_jobs_group)
        self.my_jobs_list = QListWidget()
        self.my_jobs_list.setMinimumHeight(92)
        self.my_jobs_list.setMaximumHeight(240)
        my_jobs_layout.addWidget(self.my_jobs_list)
        bottom.addWidget(my_jobs_group)

        # Recent activity
        activity_group = QGroupBox("Recent Job Activity")
        activity_layout = QVBoxLayout(activity_group)
        self.activity_list = QListWidget()
        self.activity_list.setMinimumHeight(92)
        self.activity_list.setMaximumHeight(240)
        activity_layout.addWidget(self.activity_list)
        bottom.addWidget(activity_group)

        layout.addLayout(bottom)
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def refresh(self):
        """Reload all jobs dashboard data."""
        # Active jobs
        active = self.repo.get_all_jobs("active")
        self.active_jobs_card.set_value(str(len(active)))

        # On hold
        on_hold = self.repo.get_all_jobs("on_hold")
        self.on_hold_card.set_value(str(len(on_hold)))

        # Recently completed
        completed = self.repo.get_all_jobs("completed")
        self.completed_card.set_value(str(len(completed)))

        # Labor hours this period (current month)
        now = datetime.now()
        month_start = now.replace(day=1).strftime("%Y-%m-%d")
        today_str = now.strftime("%Y-%m-%d")
        try:
            entries = self.repo.get_labor_entries_for_user(
                self.current_user.id,
                date_from=month_start,
                date_to=today_str,
            )
            total_hours = sum(e.hours or 0 for e in entries)
            self.labor_hours_card.set_value(f"{total_hours:.1f}")
        except Exception:
            self.labor_hours_card.set_value("—")

        # My Active Jobs
        self.my_jobs_list.clear()
        my_jobs = []
        for job in active:
            try:
                assignments = self.repo.get_job_assignments(job.id)
                if any(a.user_id == self.current_user.id for a in assignments):
                    my_jobs.append(job)
            except Exception:
                pass
        if my_jobs:
            for job in my_jobs:
                self.my_jobs_list.addItem(
                    f"{job.job_number} — {job.name}"
                )
        else:
            self.my_jobs_list.addItem("No active job assignments")

        # Recent job activity
        self.activity_list.clear()
        try:
            recent = self.repo.get_activity_log(
                entity_type="job", limit=10
            )
            if recent:
                for entry in recent:
                    self.activity_list.addItem(
                        f"{entry.action}: {entry.description}"
                    )
            else:
                self.activity_list.addItem("No recent job activity")
        except Exception:
            self.activity_list.addItem("No recent job activity")
