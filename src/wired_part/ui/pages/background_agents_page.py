"""Background Agents management page — extracted from AgentPage."""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wired_part.database.repository import Repository

# Auto-clear error status after 5 minutes (ms)
ERROR_CLEAR_MS = 5 * 60 * 1000


class BackgroundAgentsPage(QWidget):
    """Controls and status panel for the 3 background agents."""

    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._agent_manager = None
        self._error_timers: dict[str, QTimer] = {}
        self._setup_ui()

    def set_agent_manager(self, manager):
        """Wire up the AgentManager for control signals."""
        self._agent_manager = manager
        if manager:
            manager.agent_completed.connect(self._on_bg_agent_done)
            manager.agent_error.connect(self._on_bg_agent_error)
            if hasattr(manager, "agent_status"):
                manager.agent_status.connect(self._on_bg_agent_status)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("Background Agents")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        # Agents status panel
        bg_group = QGroupBox("Agent Status & Controls")
        bg_layout = QVBoxLayout()

        agents_row = QHBoxLayout()

        # Audit agent
        audit_col = QVBoxLayout()
        audit_col.addWidget(QLabel("Audit Agent"))
        self.audit_status = QLabel("Idle")
        self.audit_status.setObjectName("AgentStatusLabel")
        self.audit_status.setProperty("status", "idle")
        audit_col.addWidget(self.audit_status)
        audit_run = QPushButton("Run Now")
        audit_run.clicked.connect(
            lambda: self._run_bg_agent("audit_agent")
        )
        audit_col.addWidget(audit_run)
        agents_row.addLayout(audit_col)

        # Admin agent
        admin_col = QVBoxLayout()
        admin_col.addWidget(QLabel("Admin Helper"))
        self.admin_status = QLabel("Idle")
        self.admin_status.setObjectName("AgentStatusLabel")
        self.admin_status.setProperty("status", "idle")
        admin_col.addWidget(self.admin_status)
        admin_run = QPushButton("Run Now")
        admin_run.clicked.connect(
            lambda: self._run_bg_agent("admin_agent")
        )
        admin_col.addWidget(admin_run)
        agents_row.addLayout(admin_col)

        # Reminder agent
        reminder_col = QVBoxLayout()
        reminder_col.addWidget(QLabel("Reminder Agent"))
        self.reminder_status = QLabel("Idle")
        self.reminder_status.setObjectName("AgentStatusLabel")
        self.reminder_status.setProperty("status", "idle")
        reminder_col.addWidget(self.reminder_status)
        reminder_run = QPushButton("Run Now")
        reminder_run.clicked.connect(
            lambda: self._run_bg_agent("reminder_agent")
        )
        reminder_col.addWidget(reminder_run)
        agents_row.addLayout(reminder_col)

        bg_layout.addLayout(agents_row)

        # Enable/disable toggle
        toggle_row = QHBoxLayout()
        self.bg_toggle_btn = QPushButton("Start Background Agents")
        self.bg_toggle_btn.clicked.connect(self._toggle_bg_agents)
        toggle_row.addWidget(self.bg_toggle_btn)
        toggle_row.addStretch()
        bg_layout.addLayout(toggle_row)

        bg_group.setLayout(bg_layout)
        layout.addWidget(bg_group)
        layout.addStretch()

    def refresh(self):
        """Called when the sub-tab is selected."""
        self._update_bg_status()

    def _run_bg_agent(self, agent_name: str):
        if not self._agent_manager:
            return
        label = self._get_status_label(agent_name)
        if label:
            label.setText("Running...")
            label.setProperty("status", "running")
            label.style().polish(label)
        self._agent_manager.run_now(agent_name)

    def _toggle_bg_agents(self):
        if not self._agent_manager:
            return
        if self._agent_manager.enabled:
            self._agent_manager.stop()
            self.bg_toggle_btn.setText("Start Background Agents")
        else:
            self._agent_manager.start()
            self.bg_toggle_btn.setText("Stop Background Agents")
        self._update_bg_status()

    def _update_bg_status(self):
        if not self._agent_manager:
            return
        for name in ("audit_agent", "admin_agent", "reminder_agent"):
            label = self._get_status_label(name)
            if not label:
                continue
            if self._agent_manager.is_running(name):
                label.setText("Running...")
                label.setProperty("status", "running")
            else:
                result = self._agent_manager.get_last_result(name)
                if result.startswith("Error:"):
                    label.setText("Error")
                    label.setProperty("status", "error")
                elif result == "Not run yet":
                    label.setText("Idle")
                    label.setProperty("status", "idle")
                else:
                    label.setText("Completed")
                    label.setProperty("status", "completed")
            label.style().polish(label)

        if self._agent_manager.enabled:
            self.bg_toggle_btn.setText("Stop Background Agents")
        else:
            self.bg_toggle_btn.setText("Start Background Agents")

    def _on_bg_agent_done(self, agent_name: str, result: str):
        self._cancel_error_timer(agent_name)
        label = self._get_status_label(agent_name)
        if label:
            label.setText("Completed")
            label.setProperty("status", "completed")
            label.style().polish(label)
            label.setToolTip(result[:200] if result else "")

    def _on_bg_agent_error(self, agent_name: str, error: str):
        label = self._get_status_label(agent_name)
        if label:
            label.setText("Error")
            label.setProperty("status", "error")
            label.style().polish(label)
            label.setToolTip(error)

        # Auto-clear error status back to Idle after 5 minutes
        self._start_error_clear_timer(agent_name)

    def _on_bg_agent_status(self, agent_name: str, status_text: str):
        """Handle interim status updates (e.g. 'Waiting for LLM')."""
        label = self._get_status_label(agent_name)
        if label:
            label.setText(status_text)
            label.setProperty("status", "running")
            label.style().polish(label)

    # ── Error auto-clear ────────────────────────────────────────

    def _start_error_clear_timer(self, agent_name: str):
        """Start a single-shot timer that clears error status after 5 min."""
        self._cancel_error_timer(agent_name)
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda n=agent_name: self._clear_error(n))
        timer.start(ERROR_CLEAR_MS)
        self._error_timers[agent_name] = timer

    def _cancel_error_timer(self, agent_name: str):
        """Cancel any pending error-clear timer for an agent."""
        timer = self._error_timers.pop(agent_name, None)
        if timer and timer.isActive():
            timer.stop()

    def _clear_error(self, agent_name: str):
        """Reset an agent label from Error back to Idle."""
        self._error_timers.pop(agent_name, None)
        label = self._get_status_label(agent_name)
        if label and label.property("status") == "error":
            label.setText("Idle")
            label.setProperty("status", "idle")
            label.style().polish(label)
            label.setToolTip("")

    def _get_status_label(self, agent_name: str) -> QLabel | None:
        labels = {
            "audit_agent": self.audit_status,
            "admin_agent": self.admin_status,
            "reminder_agent": self.reminder_status,
        }
        return labels.get(agent_name)
