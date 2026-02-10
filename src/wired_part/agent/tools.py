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
]
