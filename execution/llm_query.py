"""Standalone LLM query script — ask inventory questions from command line."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from wired_part.config import Config
from wired_part.database.connection import DatabaseConnection
from wired_part.database.schema import initialize_database
from wired_part.database.repository import Repository
from wired_part.agent.handler import ToolHandler
from wired_part.agent.client import LMStudioClient


def main():
    db = DatabaseConnection(Config.DATABASE_PATH)
    initialize_database(db)
    repo = Repository(db)
    handler = ToolHandler(repo)

    client = LMStudioClient(tool_executor=handler.execute)

    if not client.is_connected():
        print(f"Cannot connect to LM Studio at {Config.LM_STUDIO_BASE_URL}")
        print("Make sure LM Studio is running with a model loaded.")
        sys.exit(1)

    print("Connected to LM Studio. Type 'quit' to exit.\n")

    while True:
        try:
            query = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if query.lower() in ("quit", "exit", "q"):
            break
        if not query:
            continue

        response = client.chat(query)
        print(f"\nAgent: {response}\n")


if __name__ == "__main__":
    main()
