"""Background agent manager — runs audit, admin, and reminder agents on timers."""

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from wired_part.agent.handler import ToolHandler
from wired_part.agent.prompts import (
    ADMIN_AGENT_PROMPT,
    AUDIT_AGENT_PROMPT,
    REMINDER_AGENT_PROMPT,
)
from wired_part.config import Config
from wired_part.database.models import User
from wired_part.database.repository import Repository
from wired_part.utils.constants import (
    ADMIN_AGENT_INTERVAL,
    AUDIT_AGENT_INTERVAL,
    REMINDER_AGENT_INTERVAL,
)


class AgentWorker(QThread):
    """Runs a single background agent task in a thread."""

    finished = Signal(str, str)  # agent_name, result_text
    error = Signal(str, str)  # agent_name, error_text

    def __init__(self, agent_name: str, system_prompt: str,
                 task_prompt: str, tool_handler: ToolHandler):
        super().__init__()
        self.agent_name = agent_name
        self.system_prompt = system_prompt
        self.task_prompt = task_prompt
        self.tool_handler = tool_handler

    def run(self):
        try:
            from openai import OpenAI
            client = OpenAI(
                base_url=Config.LM_STUDIO_BASE_URL,
                api_key=Config.LM_STUDIO_API_KEY,
                timeout=Config.LM_STUDIO_TIMEOUT,
            )

            from wired_part.agent.tools import AGENT_TOOLS

            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": self.task_prompt},
            ]

            # Agentic loop — up to 5 rounds of tool calls
            for _ in range(5):
                response = client.chat.completions.create(
                    model=Config.LM_STUDIO_MODEL,
                    messages=messages,
                    tools=AGENT_TOOLS,
                    tool_choice="auto",
                )
                msg = response.choices[0].message

                if not msg.tool_calls:
                    content = msg.content or "Agent completed with no output."
                    self.finished.emit(self.agent_name, content)
                    return

                messages.append(msg.model_dump())
                for tc in msg.tool_calls:
                    result = self.tool_handler.execute(
                        tc.function.name, tc.function.arguments
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })

            self.finished.emit(
                self.agent_name, "Agent completed (max rounds reached)."
            )
        except Exception as e:
            self.error.emit(self.agent_name, str(e))


class AgentManager(QObject):
    """Manages background agents with QTimer scheduling."""

    agent_completed = Signal(str, str)  # agent_name, result
    agent_error = Signal(str, str)  # agent_name, error

    def __init__(self, repo: Repository, current_user: User,
                 parent=None):
        super().__init__(parent)
        self.repo = repo
        self.current_user = current_user
        self._workers: dict[str, AgentWorker] = {}
        self._timers: dict[str, QTimer] = {}
        self._enabled = False
        self._last_results: dict[str, str] = {}

        # Agent configurations
        self._agents = {
            "audit_agent": {
                "prompt": AUDIT_AGENT_PROMPT,
                "task": "Run your audit checks now and report any issues found.",
                "interval": AUDIT_AGENT_INTERVAL,
                "source": "audit_agent",
            },
            "admin_agent": {
                "prompt": ADMIN_AGENT_PROMPT,
                "task": "Generate a daily activity summary now.",
                "interval": ADMIN_AGENT_INTERVAL,
                "source": "admin_agent",
            },
            "reminder_agent": {
                "prompt": REMINDER_AGENT_PROMPT,
                "task": "Check for items needing attention and create reminders.",
                "interval": REMINDER_AGENT_INTERVAL,
                "source": "reminder_agent",
            },
        }

    def start(self):
        """Start all background agent timers."""
        self._enabled = True
        for name, config in self._agents.items():
            timer = QTimer(self)
            timer.timeout.connect(lambda n=name: self._run_agent(n))
            timer.start(config["interval"])
            self._timers[name] = timer

    def stop(self):
        """Stop all background agent timers."""
        self._enabled = False
        for timer in self._timers.values():
            timer.stop()
        self._timers.clear()

    def run_now(self, agent_name: str):
        """Manually trigger an agent run."""
        if agent_name in self._agents:
            self._run_agent(agent_name)

    def is_running(self, agent_name: str) -> bool:
        """Check if an agent is currently executing."""
        return agent_name in self._workers

    def get_last_result(self, agent_name: str) -> str:
        """Get the last result from an agent."""
        return self._last_results.get(agent_name, "Not run yet")

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _run_agent(self, agent_name: str):
        """Execute a background agent in a thread."""
        if agent_name in self._workers:
            return  # Already running

        config = self._agents[agent_name]
        handler = ToolHandler(self.repo, agent_source=config["source"])
        worker = AgentWorker(
            agent_name=agent_name,
            system_prompt=config["prompt"],
            task_prompt=config["task"],
            tool_handler=handler,
        )
        worker.finished.connect(self._on_agent_finished)
        worker.error.connect(self._on_agent_error)
        self._workers[agent_name] = worker
        worker.start()

    def _on_agent_finished(self, agent_name: str, result: str):
        """Handle agent completion."""
        self._last_results[agent_name] = result
        if agent_name in self._workers:
            del self._workers[agent_name]
        self.agent_completed.emit(agent_name, result)

    def _on_agent_error(self, agent_name: str, error: str):
        """Handle agent errors."""
        self._last_results[agent_name] = f"Error: {error}"
        if agent_name in self._workers:
            del self._workers[agent_name]
        self.agent_error.emit(agent_name, error)
