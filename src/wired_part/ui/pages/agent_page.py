"""LLM Agent chat page — connects to LM Studio for natural language queries."""

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
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
        self._setup_ui()
        self._try_connect()

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
        # Convert newlines to <br> for HTML display
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
