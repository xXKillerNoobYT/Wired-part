"""Tool execution handler — dispatches LLM tool calls to the repository."""

import json

from wired_part.database.models import Notification
from wired_part.database.repository import Repository
from wired_part.utils.formatters import format_currency


class ToolHandler:
    """Executes tool calls from the LLM against the repository."""

    def __init__(self, repo: Repository, agent_source: str = "system"):
        self.repo = repo
        self.agent_source = agent_source

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
            "get_truck_inventory": self._get_truck_inventory,
            "get_pending_transfers": self._get_pending_transfers,
            "get_all_trucks": self._get_all_trucks,
            "create_notification": self._create_notification,
            "get_jobs_without_users": self._get_jobs_without_users,
            "get_consumption_log": self._get_consumption_log,
            "get_labor_summary": self._get_labor_summary,
            "get_active_clockins": self._get_active_clockins,
            "search_notes": self._search_notes,
            "get_pending_orders": self._get_pending_orders,
            "get_orders_summary": self._get_orders_summary,
            "suggest_reorder": self._suggest_reorder,
            "get_all_suppliers": self._get_all_suppliers,
            "get_all_categories": self._get_all_categories,
            "get_all_users": self._get_all_users,
            "get_job_details": self._get_job_details,
            "get_deprecated_parts": self._get_deprecated_parts,
            "get_audit_summary": self._get_audit_summary,
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

    def _get_truck_inventory(self, truck_number: str = "") -> dict:
        trucks = self.repo.get_all_trucks(active_only=False)
        truck = next(
            (t for t in trucks if t.truck_number == truck_number), None
        )
        if not truck:
            return {"error": f"Truck '{truck_number}' not found"}
        inventory = self.repo.get_truck_inventory(truck.id)
        return {
            "truck_number": truck.truck_number,
            "truck_name": truck.name,
            "assigned_to": truck.assigned_user_name or "Unassigned",
            "parts": [
                {
                    "part_number": item.part_number,
                    "description": item.part_description,
                    "quantity": item.quantity,
                    "value": format_currency(item.quantity * item.unit_cost),
                }
                for item in inventory
            ],
        }

    def _get_pending_transfers(self) -> list[dict]:
        transfers = self.repo.get_all_pending_transfers()
        return [
            {
                "id": t.id,
                "truck_number": t.truck_number,
                "part_number": t.part_number,
                "description": t.part_description,
                "quantity": t.quantity,
                "created_by": t.created_by_name,
                "created_at": str(t.created_at or ""),
            }
            for t in transfers
        ]

    def _get_all_trucks(self) -> list[dict]:
        trucks = self.repo.get_all_trucks(active_only=True)
        result = []
        for truck in trucks:
            summary = self.repo.get_truck_summary(truck.id)
            result.append({
                "truck_number": truck.truck_number,
                "name": truck.name,
                "assigned_to": truck.assigned_user_name or "Unassigned",
                "on_hand_parts": summary.get("unique_parts", 0),
                "total_quantity": summary.get("total_quantity", 0),
                "total_value": format_currency(
                    summary.get("total_value", 0)
                ),
                "pending_transfers": summary.get("pending_transfers", 0),
            })
        return result

    def _create_notification(self, title: str = "", message: str = "",
                             severity: str = "info") -> dict:
        notification = Notification(
            user_id=None,  # Broadcast to all
            title=title,
            message=message,
            severity=severity,
            source=self.agent_source,
        )
        nid = self.repo.create_notification(notification)
        return {"status": "created", "notification_id": nid}

    def _get_jobs_without_users(self) -> list[dict]:
        jobs = self.repo.get_all_jobs(status="active")
        unassigned = []
        for job in jobs:
            assignments = self.repo.get_job_assignments(job.id)
            if not assignments:
                unassigned.append({
                    "job_number": job.job_number,
                    "name": job.name,
                    "customer": job.customer or "",
                    "status": job.status,
                })
        return unassigned

    def _get_consumption_log(self) -> list[dict]:
        logs = self.repo.get_consumption_log()
        return [
            {
                "job_number": cl.job_number,
                "truck_number": cl.truck_number,
                "part_number": cl.part_number,
                "description": cl.part_description,
                "quantity": cl.quantity,
                "cost": format_currency(
                    cl.quantity * cl.unit_cost_at_use
                ),
                "consumed_by": cl.consumed_by_name,
                "consumed_at": str(cl.consumed_at or ""),
            }
            for cl in logs[:20]  # Limit to last 20
        ]

    def _get_labor_summary(self, job_number: str = "") -> dict:
        job = self.repo.get_job_by_number(job_number)
        if not job:
            return {"error": f"Job '{job_number}' not found"}
        summary = self.repo.get_labor_summary_for_job(job.id)
        return {
            "job_number": job.job_number,
            "job_name": job.name,
            "total_hours": summary.get("total_hours", 0),
            "entry_count": summary.get("entry_count", 0),
            "by_category": summary.get("by_category", []),
            "by_user": summary.get("by_user", []),
        }

    def _get_active_clockins(self) -> list[dict]:
        users = self.repo.get_all_users(active_only=True)
        active = []
        for user in users:
            entry = self.repo.get_active_clock_in(user.id)
            if entry:
                active.append({
                    "user": user.display_name,
                    "job_number": entry.job_number or "N/A",
                    "category": entry.sub_task_category,
                    "since": str(entry.start_time or ""),
                })
        return active

    def _search_notes(self, query: str = "") -> list[dict]:
        if not query:
            return []
        import re
        pages = self.repo.search_notebook_pages(query)
        results = []
        for page in pages[:15]:  # Limit results
            # Strip HTML for snippet
            content = page.content or ""
            text = re.sub(r"<[^>]+>", " ", content)
            text = re.sub(r"\s+", " ", text).strip()
            results.append({
                "title": page.title,
                "section": page.section_name or "",
                "created_by": page.created_by_name or "",
                "snippet": text[:200] if text else "",
                "updated_at": str(page.updated_at or ""),
            })
        return results

    def _get_pending_orders(self) -> list[dict]:
        orders = self.repo.get_all_purchase_orders()
        pending = [
            o for o in orders
            if o.status in ("draft", "submitted", "partial")
        ]
        return [
            {
                "order_number": o.order_number,
                "supplier": o.supplier_name,
                "status": o.status,
                "item_count": o.item_count,
                "total_cost": format_currency(o.total_cost),
                "created_by": o.created_by_name,
                "created_at": str(o.created_at or ""),
                "notes": o.notes or "",
            }
            for o in pending
        ]

    def _get_orders_summary(self) -> dict:
        summary = self.repo.get_orders_summary()
        return {
            "draft_orders": summary.get("draft_orders", 0),
            "pending_orders": summary.get("pending_orders", 0),
            "awaiting_receipt": summary.get("awaiting_receipt", 0),
            "open_returns": summary.get("open_returns", 0),
            "total_spent": format_currency(
                summary.get("total_spent", 0)
            ),
        }

    def _suggest_reorder(self) -> list[dict]:
        """Suggest parts to reorder based on low stock levels."""
        low_stock = self.repo.get_low_stock_parts()
        suggestions = []
        for part in low_stock:
            deficit = part.min_quantity - part.quantity
            # Suggest ordering 2x the deficit to build buffer
            suggested_qty = max(deficit * 2, part.min_quantity)
            suggestions.append({
                "part_number": part.part_number,
                "description": part.description,
                "current_stock": part.quantity,
                "min_quantity": part.min_quantity,
                "deficit": deficit,
                "suggested_order_qty": suggested_qty,
                "estimated_cost": format_currency(
                    suggested_qty * part.unit_cost
                ),
                "supplier": part.supplier or "Not specified",
            })
        return suggestions

    def _get_all_suppliers(self) -> list[dict]:
        suppliers = self.repo.get_all_suppliers()
        return [
            {
                "name": s.name,
                "contact_name": s.contact_name,
                "email": s.email,
                "phone": s.phone,
                "is_supply_house": bool(s.is_supply_house),
            }
            for s in suppliers
        ]

    def _get_all_categories(self) -> list[dict]:
        categories = self.repo.get_all_categories()
        return [{"id": c.id, "name": c.name} for c in categories]

    def _get_all_users(self) -> list[dict]:
        users = self.repo.get_all_users(active_only=True)
        return [
            {
                "username": u.username,
                "display_name": u.display_name,
                "role": u.role,
            }
            for u in users
        ]

    def _get_job_details(self, job_number: str = "") -> dict:
        jobs = self.repo.get_all_jobs()
        for job in jobs:
            if job.job_number == job_number:
                parts = self.repo.get_job_parts(job.id)
                return {
                    "job_number": job.job_number,
                    "name": job.name,
                    "status": job.status,
                    "customer": job.customer,
                    "address": job.address,
                    "priority": job.priority,
                    "notes": job.notes,
                    "parts_count": len(parts),
                    "total_cost": format_currency(
                        sum(p.quantity_used * p.unit_cost_at_use for p in parts)
                    ),
                }
        return {"error": f"Job {job_number} not found"}

    def _get_deprecated_parts(self) -> list[dict]:
        parts = self.repo.get_deprecated_parts()
        return [
            {
                "part_number": p.part_number,
                "name": p.name,
                "deprecation_status": p.deprecation_status,
                "quantity": p.quantity,
            }
            for p in parts
        ]

    def _get_audit_summary(self, audit_type: str = "warehouse") -> dict:
        summary = self.repo.get_audit_summary(audit_type)
        return summary
