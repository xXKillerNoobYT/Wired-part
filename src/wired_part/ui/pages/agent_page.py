"""LLM Agent chat page — connects to LM Studio for natural language queries."""

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wired_part.agent.client import LMStudioClient
from wired_part.agent.handler import ToolHandler
from wired_part.config import Config
from wired_part.database.repository import Repository


class ChatWorker(QThread):
    """Runs LLM chat in a background thread to keep UI responsive."""

    finished = Signal(str)
    error = Signal(str)

    def __init__(self, client: LMStudioClient, message: str):
        super().__init__()
        self._client = client
        self._message = message

    def run(self):
        try:
            response = self._client.chat(self._message)
            self.finished.emit(response)
        except Exception as e:
            self.error.emit(str(e))


class AgentPage(QWidget):
    """Chat interface for the LLM agent."""

    def __init__(self, repo: Repository):
        super().__init__()
        self.repo = repo
        self.tool_handler = ToolHandler(repo)
        self.client: LMStudioClient | None = None
        self._worker: ChatWorker | None = None
        self._agent_manager = None
        self._setup_ui()
        self._try_connect()

    def set_agent_manager(self, manager):
        """Set reference to the background AgentManager."""
        self._agent_manager = manager
        if manager:
            manager.agent_completed.connect(self._on_bg_agent_done)
            manager.agent_error.connect(self._on_bg_agent_error)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QHBoxLayout()
        header.addWidget(QLabel("AI Assistant"))
        header.addStretch()

        self.status_label = QLabel("Disconnected")
        header.addWidget(self.status_label)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._try_connect)
        header.addWidget(self.connect_btn)

        self.clear_btn = QPushButton("Clear Chat")
        self.clear_btn.clicked.connect(self._clear_chat)
        header.addWidget(self.clear_btn)

        layout.addLayout(header)

        # Background agents status panel
        bg_group = QGroupBox("Background Agents")
        bg_layout = QVBoxLayout()

        agents_row = QHBoxLayout()

        # Audit agent
        audit_col = QVBoxLayout()
        audit_col.addWidget(QLabel("Audit Agent"))
        self.audit_status = QLabel("Idle")
        self.audit_status.setStyleSheet("color: #6c7086;")
        audit_col.addWidget(self.audit_status)
        audit_run = QPushButton("Run Now")
        audit_run.clicked.connect(lambda: self._run_bg_agent("audit_agent"))
        audit_col.addWidget(audit_run)
        agents_row.addLayout(audit_col)

        # Admin agent
        admin_col = QVBoxLayout()
        admin_col.addWidget(QLabel("Admin Helper"))
        self.admin_status = QLabel("Idle")
        self.admin_status.setStyleSheet("color: #6c7086;")
        admin_col.addWidget(self.admin_status)
        admin_run = QPushButton("Run Now")
        admin_run.clicked.connect(lambda: self._run_bg_agent("admin_agent"))
        admin_col.addWidget(admin_run)
        agents_row.addLayout(admin_col)

        # Reminder agent
        reminder_col = QVBoxLayout()
        reminder_col.addWidget(QLabel("Reminder Agent"))
        self.reminder_status = QLabel("Idle")
        self.reminder_status.setStyleSheet("color: #6c7086;")
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

        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display, 1)

        # Welcome message
        self.chat_display.append(
            "<b>Agent:</b> Hello! I can help you with your inventory. "
            "Try asking things like:<br>"
            "- \"How many 12/2 Romex rolls do I have?\"<br>"
            "- \"What parts are low on stock?\"<br>"
            "- \"Show me all parts for job JOB-2026-001\"<br>"
            "- \"What trucks have pending transfers?\"<br>"
        )

        # Input area
        input_row = QHBoxLayout()
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Ask about your inventory...")
        self.message_input.returnPressed.connect(self._on_send)
        input_row.addWidget(self.message_input, 1)

        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self._on_send)
        input_row.addWidget(self.send_btn)

        layout.addLayout(input_row)

        # Connection info
        self.connection_label = QLabel(
            f"LM Studio @ {Config.LM_STUDIO_BASE_URL}"
        )
        self.connection_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.connection_label)

    def refresh(self):
        """Called when tab is selected — re-check connection."""
        self._check_connection()
        self._update_bg_status()

    def _try_connect(self):
        """Initialize or reconnect the LLM client."""
        self.client = LMStudioClient(
            tool_executor=self.tool_handler.execute
        )
        self._check_connection()

    def _check_connection(self):
        """Update the connection status label."""
        if self.client and self.client.is_connected():
            self.status_label.setText("Connected")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            self.send_btn.setEnabled(True)
            self.message_input.setEnabled(True)
        else:
            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            self.send_btn.setEnabled(False)
            self.message_input.setEnabled(False)

    def _on_send(self):
        """Send the user's message to the LLM."""
        text = self.message_input.text().strip()
        if not text or not self.client:
            return

        # Show user message
        self.chat_display.append(f"<br><b>You:</b> {text}")
        self.message_input.clear()
        self.send_btn.setEnabled(False)
        self.message_input.setEnabled(False)

        # Run in background thread
        self._worker = ChatWorker(self.client, text)
        self._worker.finished.connect(self._on_response)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_response(self, response: str):
        """Display the LLM's response."""
        formatted = response.replace("\n", "<br>")
        self.chat_display.append(f"<br><b>Agent:</b> {formatted}")
        self.send_btn.setEnabled(True)
        self.message_input.setEnabled(True)
        self.message_input.setFocus()

    def _on_error(self, error: str):
        """Display an error message."""
        self.chat_display.append(
            f"<br><b style='color:red;'>Error:</b> {error}"
        )
        self.send_btn.setEnabled(True)
        self.message_input.setEnabled(True)

    def _clear_chat(self):
        """Reset the conversation."""
        self.chat_display.clear()
        if self.client:
            self.client.reset()
        self.chat_display.append(
            "<b>Agent:</b> Chat cleared. How can I help?"
        )

    # ── Background agent controls ────────────────────────────

    def _run_bg_agent(self, agent_name: str):
        """Manually trigger a background agent."""
        if not self._agent_manager:
            return
        status_label = self._get_status_label(agent_name)
        if status_label:
            status_label.setText("Running...")
            status_label.setStyleSheet("color: #fab387;")
        self._agent_manager.run_now(agent_name)

    def _toggle_bg_agents(self):
        """Start or stop the background agents."""
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
        """Refresh the status labels for each background agent."""
        if not self._agent_manager:
            return
        for name in ("audit_agent", "admin_agent", "reminder_agent"):
            label = self._get_status_label(name)
            if not label:
                continue
            if self._agent_manager.is_running(name):
                label.setText("Running...")
                label.setStyleSheet("color: #fab387;")
            else:
                result = self._agent_manager.get_last_result(name)
                if result.startswith("Error:"):
                    label.setText("Error")
                    label.setStyleSheet("color: #f38ba8;")
                elif result == "Not run yet":
                    label.setText("Idle")
                    label.setStyleSheet("color: #6c7086;")
                else:
                    label.setText("Completed")
                    label.setStyleSheet("color: #a6e3a1;")

        if self._agent_manager.enabled:
            self.bg_toggle_btn.setText("Stop Background Agents")
        else:
            self.bg_toggle_btn.setText("Start Background Agents")

    def _on_bg_agent_done(self, agent_name: str, result: str):
        """Handle background agent completion."""
        label = self._get_status_label(agent_name)
        if label:
            label.setText("Completed")
            label.setStyleSheet("color: #a6e3a1;")

    def _on_bg_agent_error(self, agent_name: str, error: str):
        """Handle background agent error."""
        label = self._get_status_label(agent_name)
        if label:
            label.setText("Error")
            label.setStyleSheet("color: #f38ba8;")
            label.setToolTip(error)

    def _get_status_label(self, agent_name: str) -> QLabel | None:
        labels = {
            "audit_agent": self.audit_status,
            "admin_agent": self.admin_status,
            "reminder_agent": self.reminder_status,
        }
        return labels.get(agent_name)
