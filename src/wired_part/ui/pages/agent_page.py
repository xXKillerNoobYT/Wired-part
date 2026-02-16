"""LLM Agent chat page — connects to LM Studio for natural language queries."""

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
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
        """Set reference to the background AgentManager (kept for compat)."""
        self._agent_manager = manager

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QHBoxLayout()
        header.addWidget(QLabel("AI Assistant"))
        header.addStretch()

        self.status_label = QLabel("Disconnected")
        self.status_label.setObjectName("AgentConnectionLabel")
        self.status_label.setProperty("status", "disconnected")
        header.addWidget(self.status_label)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._try_connect)
        header.addWidget(self.connect_btn)

        self.clear_btn = QPushButton("Clear Chat")
        self.clear_btn.clicked.connect(self._clear_chat)
        header.addWidget(self.clear_btn)

        layout.addLayout(header)

        # Model selector row — quick model switching without leaving Agent tab
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setMinimumWidth(300)
        self.model_combo.lineEdit().setPlaceholderText(
            "Type a model name or click Refresh to load from server"
        )
        self.model_combo.addItem(Config.LM_STUDIO_MODEL)
        self.model_combo.setCurrentText(Config.LM_STUDIO_MODEL)
        model_row.addWidget(self.model_combo, 1)

        refresh_models_btn = QPushButton("Refresh Models")
        refresh_models_btn.setToolTip("Fetch available models from LM Studio")
        refresh_models_btn.clicked.connect(self._fetch_and_populate_models)
        model_row.addWidget(refresh_models_btn)

        apply_model_btn = QPushButton("Apply")
        apply_model_btn.setToolTip("Switch to the selected model")
        apply_model_btn.clicked.connect(self._apply_model_selection)
        model_row.addWidget(apply_model_btn)

        layout.addLayout(model_row)

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
        self.connection_label.setObjectName("AgentConnectionInfo")
        layout.addWidget(self.connection_label)

    def refresh(self):
        """Called when tab is selected — reconnect if settings changed."""
        # Update the connection info label to reflect current config
        self.connection_label.setText(
            f"LM Studio @ {Config.LM_STUDIO_BASE_URL}  |  "
            f"Model: {Config.LM_STUDIO_MODEL}"
        )
        # Sync the model combo if the model was changed in Settings.
        # Ensure the configured model is in the combo list first —
        # setCurrentText() silently fails if the text isn't in the list.
        configured = Config.LM_STUDIO_MODEL
        if self.model_combo.findText(configured) < 0:
            self.model_combo.insertItem(0, configured)
        if self.model_combo.currentText() != configured:
            self.model_combo.setCurrentText(configured)

        # Auto-reconnect if config changed since last connect
        current_url = Config.LM_STUDIO_BASE_URL
        if (not self.client
                or getattr(self, "_last_url", None) != current_url):
            self._try_connect()
        else:
            self._check_connection()

    def _try_connect(self):
        """Initialize or reconnect the LLM client."""
        self._last_url = Config.LM_STUDIO_BASE_URL
        self.client = LMStudioClient(
            tool_executor=self.tool_handler.execute
        )
        self._check_connection()

    def _check_connection(self):
        """Update the connection status label."""
        if self.client and self.client.is_connected():
            self.status_label.setText("Connected")
            self.status_label.setProperty("status", "connected")
            self.send_btn.setEnabled(True)
            self.message_input.setEnabled(True)
        else:
            self.status_label.setText("Disconnected")
            self.status_label.setProperty("status", "disconnected")
            self.send_btn.setEnabled(False)
            self.message_input.setEnabled(False)
        self.status_label.style().polish(self.status_label)

    def _fetch_and_populate_models(self):
        """Fetch available models from the LLM server and populate combo."""
        if not self.client:
            self.chat_display.append(
                "<br><i style='color: red;'>Not connected. "
                "Click Connect first.</i>"
            )
            return
        try:
            from openai import OpenAI
            import httpx
            oc = OpenAI(
                base_url=Config.LM_STUDIO_BASE_URL,
                api_key=Config.LM_STUDIO_API_KEY,
                timeout=httpx.Timeout(10.0),
            )
            models = oc.models.list()
            model_names = sorted([m.id for m in models.data])

            if not model_names:
                self.chat_display.append(
                    "<br><i style='color: orange;'>No models found "
                    "on the server.</i>"
                )
                return

            current = self.model_combo.currentText()
            self.model_combo.blockSignals(True)
            self.model_combo.clear()
            for name in model_names:
                self.model_combo.addItem(name)
            # Restore user's selection or keep the first
            idx = self.model_combo.findText(current)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
            elif current:
                self.model_combo.insertItem(0, current)
                self.model_combo.setCurrentIndex(0)
            self.model_combo.blockSignals(False)

            self.chat_display.append(
                f"<br><i style='color: green;'>Found {len(model_names)} "
                f"model(s). Select one and click Apply.</i>"
            )
        except Exception as e:
            self.chat_display.append(
                f"<br><i style='color: red;'>Failed to fetch models: "
                f"{e}</i>"
            )

    def _apply_model_selection(self):
        """Apply the selected model — saves to Config and reconnects."""
        model = self.model_combo.currentText().strip()
        if not model:
            return
        Config.update_llm_settings(
            Config.LM_STUDIO_BASE_URL,
            Config.LM_STUDIO_API_KEY,
            model,
            Config.LM_STUDIO_TIMEOUT,
        )
        self.connection_label.setText(
            f"LM Studio @ {Config.LM_STUDIO_BASE_URL}  |  "
            f"Model: {model}"
        )
        self._try_connect()
        self.chat_display.append(
            f"<br><i style='color: green;'>Switched to model: "
            f"<b>{model}</b></i>"
        )

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

