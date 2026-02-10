"""Tool execution handler — dispatches LLM tool calls to the repository."""

import json

from wired_part.database.repository import Repository
from wired_part.utils.formatters import format_currency


class ToolHandler:
    """Executes tool calls from the LLM against the repository."""

    def __init__(self, repo: Repository):
        self.repo = repo

    def execute(self, tool_name: str, arguments: str) -> str:
        """Run a tool and return a JSON string result."""
        args = json.loads(arguments) if arguments else {}

        dispatch = {
            "search_parts": self._search_parts,
            "get_part_details": self._get_part_details,
            "get_job_parts": self._get_job_parts,
            "get_low_stock_parts": self._get_low_stock_parts,
            "get_inventory_summary": self._get_inventory_summary,
            "get_job_summary": self._get_job_summary,
        }

        handler = dispatch.get(tool_name)
        if not handler:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        try:
            result = handler(**args)
            return json.dumps(result, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _search_parts(self, query: str = "") -> list[dict]:
        parts = self.repo.search_parts(query)
        return [
            {
                "part_number": p.part_number,
                "description": p.description,
                "quantity": p.quantity,
                "min_quantity": p.min_quantity,
                "location": p.location,
                "category": p.category_name,
                "unit_cost": format_currency(p.unit_cost),
                "low_stock": p.is_low_stock,
            }
            for p in parts
        ]

    def _get_part_details(self, part_number: str = "") -> dict:
        part = self.repo.get_part_by_number(part_number)
        if not part:
            return {"error": f"Part '{part_number}' not found"}
        return {
            "part_number": part.part_number,
            "description": part.description,
            "quantity": part.quantity,
            "min_quantity": part.min_quantity,
            "location": part.location,
            "category": part.category_name,
            "unit_cost": format_currency(part.unit_cost),
            "supplier": part.supplier,
            "notes": part.notes,
            "total_value": format_currency(part.total_value),
            "low_stock": part.is_low_stock,
        }

    def _get_job_parts(self, job_number: str = "") -> dict:
        job = self.repo.get_job_by_number(job_number)
        if not job:
            return {"error": f"Job '{job_number}' not found"}
        parts = self.repo.get_job_parts(job.id)
        total = self.repo.get_job_total_cost(job.id)
        return {
            "job_number": job.job_number,
            "job_name": job.name,
            "customer": job.customer,
            "status": job.status,
            "parts": [
                {
                    "part_number": jp.part_number,
                    "description": jp.part_description,
                    "quantity_used": jp.quantity_used,
                    "cost": format_currency(jp.total_cost),
                }
                for jp in parts
            ],
            "total_cost": format_currency(total),
        }

    def _get_low_stock_parts(self) -> list[dict]:
        parts = self.repo.get_low_stock_parts()
        return [
            {
                "part_number": p.part_number,
                "description": p.description,
                "quantity": p.quantity,
                "min_quantity": p.min_quantity,
                "deficit": p.min_quantity - p.quantity,
                "supplier": p.supplier,
            }
            for p in parts
        ]

    def _get_inventory_summary(self) -> dict:
        summary = self.repo.get_inventory_summary()
        return {
            "total_unique_parts": summary.get("total_parts", 0),
            "total_quantity": summary.get("total_quantity", 0),
            "total_value": format_currency(summary.get("total_value", 0)),
            "low_stock_items": summary.get("low_stock_count", 0),
        }

    def _get_job_summary(self, status: str = "all") -> dict:
        summary = self.repo.get_job_summary(status)
        return {
            "filter": status,
            "total_jobs": summary.get("total_jobs", 0),
            "total_cost": format_currency(summary.get("total_cost", 0)),
        }
