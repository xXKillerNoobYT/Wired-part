"""Tests for the agent module: prompts, tools, handler, suggestions."""

import json
import pytest

from wired_part.database.connection import DatabaseConnection
from wired_part.database.models import (
    Job,
    Part,
    Supplier,
    Truck,
    User,
)
from wired_part.database.repository import Repository
from wired_part.database.schema import initialize_database


@pytest.fixture
def repo(tmp_path):
    db = DatabaseConnection(str(tmp_path / "agent_test.db"))
    initialize_database(db)
    return Repository(db)


@pytest.fixture
def admin_user(repo):
    user = User(
        username="admin", display_name="Admin",
        pin_hash=Repository.hash_pin("1234"), role="admin",
    )
    user.id = repo.create_user(user)
    return user


@pytest.fixture
def sample_data(repo, admin_user):
    """Create sample parts, jobs, suppliers, trucks for agent tools."""
    cat = repo.get_all_categories()[0]
    parts = []
    for pn, name, qty, cost in [
        ("AGT-001", "Agent Wire", 50, 10.0),
        ("AGT-002", "Agent Breaker", 5, 25.0),
    ]:
        p = Part(
            part_number=pn, name=name, quantity=qty,
            unit_cost=cost, category_id=cat.id, min_quantity=10,
        )
        p.id = repo.create_part(p)
        parts.append(p)

    job = Job(
        job_number="J-AGT-001", name="Agent Test Job", status="active",
    )
    job.id = repo.create_job(job)

    supplier = Supplier(name="Agent Supplier")
    supplier.id = repo.create_supplier(supplier)

    truck = Truck(
        truck_number="T-AGT-001", name="Agent Truck",
        assigned_user_id=admin_user.id,
    )
    truck.id = repo.create_truck(truck)

    return {
        "parts": parts, "job": job, "supplier": supplier,
        "truck": truck, "user": admin_user,
    }


# ── Prompts ───────────────────────────────────────────────────

class TestPrompts:
    def test_system_prompt_non_empty(self):
        from wired_part.agent.prompts import SYSTEM_PROMPT
        assert len(SYSTEM_PROMPT) > 100

    def test_audit_prompt_non_empty(self):
        from wired_part.agent.prompts import AUDIT_AGENT_PROMPT
        assert len(AUDIT_AGENT_PROMPT) > 50

    def test_admin_prompt_non_empty(self):
        from wired_part.agent.prompts import ADMIN_AGENT_PROMPT
        assert len(ADMIN_AGENT_PROMPT) > 50

    def test_reminder_prompt_non_empty(self):
        from wired_part.agent.prompts import REMINDER_AGENT_PROMPT
        assert len(REMINDER_AGENT_PROMPT) > 50


# ── Tool Definitions ──────────────────────────────────────────

class TestToolDefinitions:
    def test_tools_list_is_non_empty(self):
        from wired_part.agent.tools import AGENT_TOOLS
        assert len(AGENT_TOOLS) > 10

    def test_all_tools_have_function_type(self):
        from wired_part.agent.tools import AGENT_TOOLS
        for tool in AGENT_TOOLS:
            assert tool["type"] == "function"

    def test_all_tools_have_name(self):
        from wired_part.agent.tools import AGENT_TOOLS
        for tool in AGENT_TOOLS:
            assert "name" in tool["function"]
            assert len(tool["function"]["name"]) > 0

    def test_no_duplicate_tool_names(self):
        from wired_part.agent.tools import AGENT_TOOLS
        names = [t["function"]["name"] for t in AGENT_TOOLS]
        assert len(names) == len(set(names))

    def test_all_tools_have_description(self):
        from wired_part.agent.tools import AGENT_TOOLS
        for tool in AGENT_TOOLS:
            assert "description" in tool["function"]
            assert len(tool["function"]["description"]) > 0


# ── Tool Handler ──────────────────────────────────────────────

class TestToolHandler:
    def test_creates_without_crash(self, repo):
        from wired_part.agent.handler import ToolHandler
        handler = ToolHandler(repo)
        assert handler is not None

    def test_invalid_tool_returns_error(self, repo):
        from wired_part.agent.handler import ToolHandler
        handler = ToolHandler(repo)
        result = handler.execute("nonexistent_tool", "{}")
        parsed = json.loads(result)
        assert "error" in parsed

    def test_search_parts(self, repo, sample_data):
        from wired_part.agent.handler import ToolHandler
        handler = ToolHandler(repo)
        result = handler.execute(
            "search_parts", json.dumps({"query": "Agent"})
        )
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) >= 1

    def test_get_low_stock_parts(self, repo, sample_data):
        from wired_part.agent.handler import ToolHandler
        handler = ToolHandler(repo)
        result = handler.execute("get_low_stock_parts", "{}")
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        pns = [p["part_number"] for p in parsed]
        assert "AGT-002" in pns

    def test_get_inventory_summary(self, repo, sample_data):
        from wired_part.agent.handler import ToolHandler
        handler = ToolHandler(repo)
        result = handler.execute("get_inventory_summary", "{}")
        parsed = json.loads(result)
        assert "total_unique_parts" in parsed
        assert parsed["total_unique_parts"] >= 2

    def test_get_job_summary(self, repo, sample_data):
        from wired_part.agent.handler import ToolHandler
        handler = ToolHandler(repo)
        result = handler.execute(
            "get_job_summary", json.dumps({"status": "active"})
        )
        parsed = json.loads(result)
        assert "total_jobs" in parsed

    def test_get_all_trucks(self, repo, sample_data):
        from wired_part.agent.handler import ToolHandler
        handler = ToolHandler(repo)
        result = handler.execute("get_all_trucks", "{}")
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) >= 1

    def test_get_all_suppliers(self, repo, sample_data):
        from wired_part.agent.handler import ToolHandler
        handler = ToolHandler(repo)
        result = handler.execute("get_all_suppliers", "{}")
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    def test_get_all_categories(self, repo):
        from wired_part.agent.handler import ToolHandler
        handler = ToolHandler(repo)
        result = handler.execute("get_all_categories", "{}")
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) >= 1

    def test_get_all_users(self, repo, admin_user):
        from wired_part.agent.handler import ToolHandler
        handler = ToolHandler(repo)
        result = handler.execute("get_all_users", "{}")
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) >= 1

    def test_get_pending_orders(self, repo, sample_data):
        from wired_part.agent.handler import ToolHandler
        handler = ToolHandler(repo)
        result = handler.execute("get_pending_orders", "{}")
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    def test_get_orders_summary(self, repo, sample_data):
        from wired_part.agent.handler import ToolHandler
        handler = ToolHandler(repo)
        result = handler.execute("get_orders_summary", "{}")
        parsed = json.loads(result)
        assert "pending_orders" in parsed

    def test_create_notification(self, repo, sample_data):
        from wired_part.agent.handler import ToolHandler
        handler = ToolHandler(repo)
        result = handler.execute("create_notification", json.dumps({
            "title": "Test Alert",
            "message": "Low stock detected",
            "severity": "warning",
        }))
        parsed = json.loads(result)
        assert "status" in parsed

    def test_search_notes(self, repo, sample_data):
        from wired_part.agent.handler import ToolHandler
        handler = ToolHandler(repo)
        result = handler.execute(
            "search_notes", json.dumps({"query": "test"})
        )
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    def test_suggest_reorder(self, repo, sample_data):
        from wired_part.agent.handler import ToolHandler
        handler = ToolHandler(repo)
        result = handler.execute("suggest_reorder", "{}")
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    def test_get_deprecated_parts(self, repo, sample_data):
        from wired_part.agent.handler import ToolHandler
        handler = ToolHandler(repo)
        result = handler.execute("get_deprecated_parts", "{}")
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    def test_get_active_clockins(self, repo, sample_data):
        from wired_part.agent.handler import ToolHandler
        handler = ToolHandler(repo)
        result = handler.execute("get_active_clockins", "{}")
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    def test_get_pending_transfers(self, repo, sample_data):
        from wired_part.agent.handler import ToolHandler
        handler = ToolHandler(repo)
        result = handler.execute("get_pending_transfers", "{}")
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    def test_get_consumption_log(self, repo, sample_data):
        from wired_part.agent.handler import ToolHandler
        handler = ToolHandler(repo)
        result = handler.execute("get_consumption_log", "{}")
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    def test_get_job_details(self, repo, sample_data):
        from wired_part.agent.handler import ToolHandler
        handler = ToolHandler(repo)
        result = handler.execute(
            "get_job_details",
            json.dumps({"job_number": "J-AGT-001"}),
        )
        parsed = json.loads(result)
        assert "name" in parsed

    def test_get_part_details(self, repo, sample_data):
        from wired_part.agent.handler import ToolHandler
        handler = ToolHandler(repo)
        result = handler.execute(
            "get_part_details",
            json.dumps({"part_number": "AGT-001"}),
        )
        parsed = json.loads(result)
        assert "part_number" in parsed or "category" in parsed

    def test_get_truck_inventory(self, repo, sample_data):
        from wired_part.agent.handler import ToolHandler
        handler = ToolHandler(repo)
        result = handler.execute(
            "get_truck_inventory",
            json.dumps({"truck_number": "T-AGT-001"}),
        )
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_get_audit_summary(self, repo, sample_data):
        from wired_part.agent.handler import ToolHandler
        handler = ToolHandler(repo)
        result = handler.execute(
            "get_audit_summary",
            json.dumps({"audit_type": "warehouse"}),
        )
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_get_jobs_without_users(self, repo, sample_data):
        from wired_part.agent.handler import ToolHandler
        handler = ToolHandler(repo)
        result = handler.execute("get_jobs_without_users", "{}")
        parsed = json.loads(result)
        assert isinstance(parsed, list)


# ── Suggestions Module ────────────────────────────────────────

class TestSuggestions:
    def test_get_suggestions_empty_ids(self, repo):
        from wired_part.agent.suggestions import get_suggestions
        result = get_suggestions(repo, [])
        assert result == []

    def test_get_suggestions_with_parts(self, repo, sample_data):
        from wired_part.agent.suggestions import get_suggestions
        part_ids = [p.id for p in sample_data["parts"]]
        result = get_suggestions(repo, part_ids)
        assert isinstance(result, list)

    def test_rebuild_suggestions_no_crash(self, repo, sample_data):
        from wired_part.agent.suggestions import rebuild_suggestions
        rebuild_suggestions(repo)


# ── LMStudio Client ──────────────────────────────────────────

class TestLMStudioClient:
    def test_creates_without_crash(self):
        from wired_part.agent.client import LMStudioClient
        client = LMStudioClient(tool_executor=lambda n, a: "{}")
        assert client is not None

    def test_reset_clears_state(self):
        from wired_part.agent.client import LMStudioClient
        client = LMStudioClient(tool_executor=lambda n, a: "{}")
        client.reset()

    def test_is_connected_returns_bool(self):
        from wired_part.agent.client import LMStudioClient
        client = LMStudioClient(tool_executor=lambda n, a: "{}")
        result = client.is_connected()
        assert isinstance(result, bool)
