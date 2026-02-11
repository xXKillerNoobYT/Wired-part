"""Tool definitions exposed to the LLM for function calling."""

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_parts",
            "description": (
                "Search for parts in the inventory by keyword, "
                "part number, or description."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term (part number, description, keyword)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_part_details",
            "description": "Get full details for a specific part by part number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "part_number": {
                        "type": "string",
                        "description": "The part number to look up",
                    },
                },
                "required": ["part_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_job_parts",
            "description": "Get all parts assigned to a specific job.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_number": {
                        "type": "string",
                        "description": "The job number to look up",
                    },
                },
                "required": ["job_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_low_stock_parts",
            "description": (
                "Get all parts that are below their minimum quantity threshold."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_inventory_summary",
            "description": (
                "Get a summary of the entire inventory: total parts, "
                "total value, low stock count."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_job_summary",
            "description": "Get summary of jobs by status (active, completed, etc).",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": [
                            "active", "completed", "on_hold",
                            "cancelled", "all",
                        ],
                        "description": "Filter by job status",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_truck_inventory",
            "description": "Get on-hand inventory for a specific truck.",
            "parameters": {
                "type": "object",
                "properties": {
                    "truck_number": {
                        "type": "string",
                        "description": "The truck number to look up",
                    },
                },
                "required": ["truck_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pending_transfers",
            "description": (
                "Get all pending transfers across all trucks "
                "that have not yet been received."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_all_trucks",
            "description": "Get a list of all active trucks with their details.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_notification",
            "description": (
                "Create a notification for the system. "
                "Use this to alert users about issues found during audits."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Short notification title",
                    },
                    "message": {
                        "type": "string",
                        "description": "Detailed notification message",
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["info", "warning", "critical"],
                        "description": "Notification severity level",
                    },
                },
                "required": ["title", "message", "severity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_jobs_without_users",
            "description": (
                "Get all active jobs that have no users assigned to them."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_consumption_log",
            "description": "Get recent part consumption log entries.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_labor_summary",
            "description": (
                "Get labor summary for a specific job: total hours, "
                "breakdown by category and user."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "job_number": {
                        "type": "string",
                        "description": "The job number to get labor summary for",
                    },
                },
                "required": ["job_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_clockins",
            "description": (
                "Get all currently active clock-ins across all users. "
                "Returns entries where end_time is NULL."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_notes",
            "description": (
                "Search across all job notebook pages by keyword. "
                "Returns matching page titles, content snippets, and job info."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term to find in page titles and content",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pending_orders",
            "description": (
                "Get all pending purchase orders (draft, submitted, or "
                "partially received). Includes supplier, item count, "
                "total cost, and status."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_orders_summary",
            "description": (
                "Get a quick summary of orders: counts by status, "
                "total spent, items awaiting receipt, open returns."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_reorder",
            "description": (
                "Suggest parts that should be reordered based on current "
                "stock levels, minimum quantities, and recent consumption. "
                "Returns a list of parts needing reorder with suggested "
                "quantities."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_all_suppliers",
            "description": "Get a list of all active suppliers.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_all_categories",
            "description": "Get a list of all part categories.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_all_users",
            "description": "Get a list of all active users in the system.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_job_details",
            "description": "Get detailed information about a specific job.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_number": {
                        "type": "string",
                        "description": "The job number to look up",
                    },
                },
                "required": ["job_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_deprecated_parts",
            "description": (
                "Get all parts currently in the deprecation pipeline. "
                "Returns parts with their deprecation status and progress."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_audit_summary",
            "description": (
                "Get inventory audit summary: total audits, discrepancies, "
                "last audit date. Specify type ('warehouse', 'truck', 'job')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "audit_type": {
                        "type": "string",
                        "enum": ["warehouse", "truck", "job"],
                        "description": "Type of audit to summarize",
                    },
                },
                "required": ["audit_type"],
            },
        },
    },
]
