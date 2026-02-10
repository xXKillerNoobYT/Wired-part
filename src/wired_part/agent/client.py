"""OpenAI-compatible client for LM Studio integration."""

import json
from typing import Callable

from openai import OpenAI

from wired_part.agent.prompts import SYSTEM_PROMPT
from wired_part.agent.tools import AGENT_TOOLS
from wired_part.config import Config


class LMStudioClient:
    """Chat client that connects to a local LM Studio instance."""

    def __init__(self, tool_executor: Callable[[str, str], str]):
        self.client = OpenAI(
            base_url=Config.LM_STUDIO_BASE_URL,
            api_key=Config.LM_STUDIO_API_KEY,
            timeout=Config.LM_STUDIO_TIMEOUT,
        )
        self.tool_executor = tool_executor
        self.messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    def reset(self):
        """Clear conversation history."""
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    def chat(self, user_message: str) -> str:
        """Send a message and get a response, handling tool calls."""
        if user_message:
            self.messages.append({"role": "user", "content": user_message})

        try:
            response = self.client.chat.completions.create(
                model=Config.LM_STUDIO_MODEL,
                messages=self.messages,
                tools=AGENT_TOOLS,
                tool_choice="auto",
            )
        except Exception as e:
            error_msg = f"Connection error: {e}"
            return error_msg

        message = response.choices[0].message

        # Handle tool calls
        if message.tool_calls:
            self.messages.append(message.model_dump())
            for tool_call in message.tool_calls:
                result = self.tool_executor(
                    tool_call.function.name,
                    tool_call.function.arguments,
                )
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })
            # Recurse to get the final response after tool execution
            return self.chat("")

        content = message.content or ""
        self.messages.append({"role": "assistant", "content": content})
        return content

    def is_connected(self) -> bool:
        """Check if LM Studio is reachable."""
        try:
            self.client.models.list()
            return True
        except Exception:
            return False
