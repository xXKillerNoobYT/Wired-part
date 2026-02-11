"""Application-wide constants."""

APP_NAME = "Wired-Part"
APP_VERSION = "10.0.0"
APP_ORGANIZATION = "WeirdToo LLC"

# Job statuses
JOB_STATUSES = ["active", "completed", "on_hold", "cancelled"]

# Job priorities (1=highest, 5=lowest)
JOB_PRIORITIES = {
    1: "Urgent",
    2: "High",
    3: "Normal",
    4: "Low",
    5: "Deferred",
}

# User roles (legacy — kept for DB compatibility)
USER_ROLES = ["admin", "user"]

# ── Hats (role-based permissions) ────────────────────────────────
# Ordered by privilege level (highest first)
HAT_NAMES = [
    "Admin",
    "IT",
    "Office",
    "Job Manager",
    "Foreman",
    "Worker",
    "Grunt",
]

# Admin & IT are equivalent — full access to everything
FULL_ACCESS_HATS = ["Admin", "IT"]

# Permission keys: each maps to a capability in the app
PERMISSION_KEYS = [
    # Tab access
    "tab_dashboard",
    "tab_parts_catalog",
    "tab_warehouse",
    "tab_trucks_inventory",
    "tab_jobs_inventory",
    "tab_job_tracking",
    "tab_trucks",
    "tab_labor",
    "tab_agent",
    "tab_settings",
    # Parts & Inventory actions
    "parts_add",
    "parts_edit",
    "parts_delete",
    "parts_import",
    "parts_export",
    "parts_lists",
    "parts_brands",
    "parts_variants",
    "parts_qr_tags",
    # Job actions
    "jobs_add",
    "jobs_edit",
    "jobs_delete",
    "jobs_assign",
    "jobs_billing",
    "jobs_notes",
    "jobs_report",
    # Labor actions
    "labor_clock_in",
    "labor_clock_out",
    "labor_manual_entry",
    "labor_view_all",
    # Truck actions
    "trucks_add",
    "trucks_edit",
    "trucks_transfer",
    # Orders & Returns actions
    "tab_orders",
    "orders_create",
    "orders_edit",
    "orders_submit",
    "orders_receive",
    "orders_return",
    "orders_history",
    # Settings actions
    "settings_users",
    "settings_hats",
    "settings_categories",
    "settings_suppliers",
    "settings_llm",
    "settings_agent",
    "settings_labor",
    "settings_notebook",
    "settings_general",
]

# Human-readable labels for each permission
PERMISSION_LABELS = {
    "tab_dashboard": "View Dashboard",
    "tab_parts_catalog": "View Parts Catalog",
    "tab_warehouse": "View Warehouse Inventory",
    "tab_trucks_inventory": "View Trucks Inventory",
    "tab_jobs_inventory": "View Jobs Inventory",
    "tab_job_tracking": "View Job Tracking",
    "tab_trucks": "View Trucks",
    "tab_labor": "View Labor Overview",
    "tab_agent": "View Agent",
    "tab_settings": "View Settings",
    "parts_add": "Add Parts",
    "parts_edit": "Edit Parts",
    "parts_delete": "Delete Parts",
    "parts_import": "Import Parts",
    "parts_export": "Export Parts",
    "parts_lists": "Manage Parts Lists",
    "parts_brands": "Manage Brands",
    "parts_variants": "Manage Part Variants",
    "parts_qr_tags": "Manage QR Tags",
    "jobs_add": "Add Jobs",
    "jobs_edit": "Edit Jobs",
    "jobs_delete": "Delete Jobs",
    "jobs_assign": "Assign Users to Jobs",
    "jobs_billing": "View/Generate Billing",
    "jobs_notes": "View/Edit Job Notes",
    "jobs_report": "Generate Work Reports",
    "labor_clock_in": "Clock In",
    "labor_clock_out": "Clock Out",
    "labor_manual_entry": "Manual Labor Entry",
    "labor_view_all": "View All Labor Entries",
    "trucks_add": "Add Trucks",
    "trucks_edit": "Edit Trucks",
    "trucks_transfer": "Create/Receive Transfers",
    "tab_orders": "View Orders & Returns",
    "orders_create": "Create Purchase Orders",
    "orders_edit": "Edit Purchase Orders",
    "orders_submit": "Submit Purchase Orders",
    "orders_receive": "Receive Orders",
    "orders_return": "Manage Returns",
    "orders_history": "View Order History",
    "settings_users": "Manage Users",
    "settings_hats": "Manage Hats & Permissions",
    "settings_categories": "Manage Categories",
    "settings_suppliers": "Manage Suppliers",
    "settings_llm": "Configure LLM",
    "settings_agent": "Configure Agents",
    "settings_labor": "Configure Labor Settings",
    "settings_notebook": "Configure Notebook Template",
    "settings_general": "General Settings",
}

# Permission groups for organized display
PERMISSION_GROUPS = {
    "Tab Access": [k for k in PERMISSION_KEYS if k.startswith("tab_")],
    "Parts & Inventory": [k for k in PERMISSION_KEYS if k.startswith("parts_")],
    "Jobs": [k for k in PERMISSION_KEYS if k.startswith("jobs_")],
    "Labor": [k for k in PERMISSION_KEYS if k.startswith("labor_")],
    "Trucks": [k for k in PERMISSION_KEYS if k.startswith("trucks_")],
    "Orders & Returns": [
        k for k in PERMISSION_KEYS
        if k.startswith("orders_") or k == "tab_orders"
    ],
    "Settings": [k for k in PERMISSION_KEYS if k.startswith("settings_")],
}

# Default permissions for each hat (True = granted)
DEFAULT_HAT_PERMISSIONS: dict[str, list[str]] = {
    "Admin": list(PERMISSION_KEYS),  # All permissions
    "IT": list(PERMISSION_KEYS),     # All permissions (same as Admin)
    "Office": [
        "tab_dashboard", "tab_parts_catalog", "tab_warehouse",
        "tab_trucks_inventory", "tab_jobs_inventory", "tab_job_tracking",
        "tab_trucks", "tab_labor", "tab_orders", "tab_settings",
        "parts_add", "parts_edit", "parts_import", "parts_export",
        "parts_lists", "parts_brands", "parts_variants", "parts_qr_tags",
        "jobs_add", "jobs_edit", "jobs_assign", "jobs_billing",
        "jobs_notes", "jobs_report",
        "labor_view_all", "labor_manual_entry",
        "trucks_add", "trucks_edit", "trucks_transfer",
        "orders_create", "orders_edit", "orders_submit",
        "orders_receive", "orders_return", "orders_history",
        "settings_categories", "settings_suppliers",
        "settings_labor", "settings_notebook", "settings_general",
    ],
    "Job Manager": [
        "tab_dashboard", "tab_parts_catalog", "tab_warehouse",
        "tab_trucks_inventory", "tab_jobs_inventory", "tab_job_tracking",
        "tab_trucks", "tab_labor", "tab_orders",
        "parts_add", "parts_edit", "parts_export", "parts_lists",
        "parts_brands", "parts_variants",
        "jobs_add", "jobs_edit", "jobs_assign", "jobs_billing",
        "jobs_notes", "jobs_report",
        "labor_clock_in", "labor_clock_out", "labor_manual_entry",
        "labor_view_all",
        "trucks_transfer",
        "orders_create", "orders_receive", "orders_history",
    ],
    "Foreman": [
        "tab_dashboard", "tab_parts_catalog", "tab_warehouse",
        "tab_trucks_inventory", "tab_jobs_inventory", "tab_job_tracking",
        "tab_trucks", "tab_labor", "tab_orders",
        "parts_add", "parts_edit", "parts_lists", "parts_qr_tags",
        "jobs_edit", "jobs_assign", "jobs_notes",
        "labor_clock_in", "labor_clock_out", "labor_manual_entry",
        "labor_view_all",
        "trucks_transfer",
        "orders_receive",
    ],
    "Worker": [
        "tab_dashboard", "tab_parts_catalog",
        "tab_job_tracking", "tab_labor",
        "jobs_notes",
        "labor_clock_in", "labor_clock_out",
    ],
    "Grunt": [
        "tab_dashboard",
        "labor_clock_in", "labor_clock_out",
    ],
}

# ── Orders & Returns ──────────────────────────────────────────
# Purchase order statuses
ORDER_STATUSES = ["draft", "submitted", "partial", "received", "closed", "cancelled"]

ORDER_STATUS_LABELS = {
    "draft": "Draft",
    "submitted": "Submitted",
    "partial": "Partially Received",
    "received": "Fully Received",
    "closed": "Closed",
    "cancelled": "Cancelled",
}

# Return authorization statuses
RETURN_STATUSES = ["initiated", "picked_up", "credit_received", "cancelled"]

RETURN_STATUS_LABELS = {
    "initiated": "Initiated",
    "picked_up": "Picked Up",
    "credit_received": "Credit Received",
    "cancelled": "Cancelled",
}

# Return reasons
RETURN_REASONS = ["wrong_part", "damaged", "overstock", "defective", "other"]

RETURN_REASON_LABELS = {
    "wrong_part": "Wrong Part",
    "damaged": "Damaged",
    "overstock": "Overstock",
    "defective": "Defective",
    "other": "Other",
}

# Receive allocation targets
ALLOCATION_TARGETS = ["warehouse", "truck", "job"]

# Transfer directions
TRANSFER_DIRECTIONS = ["outbound", "return"]

# Transfer statuses
TRANSFER_STATUSES = ["pending", "received", "cancelled"]

# Job assignment roles
JOB_ASSIGNMENT_ROLES = ["lead", "worker"]

# Notification severities
NOTIFICATION_SEVERITIES = ["info", "warning", "critical"]

# Notification sources
NOTIFICATION_SOURCES = [
    "system",
    "audit_agent",
    "admin_agent",
    "reminder_agent",
]

# Parts list types
PARTS_LIST_TYPES = ["general", "specific", "fast"]

# Labor sub-task categories
LABOR_SUBTASK_CATEGORIES = [
    "Rough-in",
    "Trim-out",
    "Service Call",
    "Testing",
    "Travel",
    "Admin",
    "General",
]

# Default notebook sections (created with each new job notebook)
DEFAULT_NOTEBOOK_SECTIONS = [
    "Daily Logs",
    "Safety Notes",
    "Change Orders",
    "Punch List",
    "General",
]

# Locked notebook sections (cannot be renamed or deleted)
LOCKED_NOTEBOOK_SECTIONS = ["Daily Logs"]

# Geolocation
GEOFENCE_RADIUS_MILES = 0.5

# Report types
REPORT_TYPES = ["internal", "client"]

# Default window size
DEFAULT_WINDOW_WIDTH = 1200
DEFAULT_WINDOW_HEIGHT = 800
MIN_WINDOW_WIDTH = 900
MIN_WINDOW_HEIGHT = 600

# Background agent intervals (minutes) — defaults, overridable via Config
AUDIT_AGENT_INTERVAL_DEFAULT = 30
ADMIN_AGENT_INTERVAL_DEFAULT = 60
REMINDER_AGENT_INTERVAL_DEFAULT = 15

# ── Parts Catalog types ──────────────────────────────────────────
PART_TYPES = ["general", "specific"]

PART_TYPE_LABELS = {
    "general": "General (Commodity)",
    "specific": "Specific (Branded)",
}

# Suggested subcategories grouped by category name
COMMON_SUBCATEGORIES: dict[str, list[str]] = {
    "Switches & Outlets": [
        "GFCI", "Tamper-Resistant", "Duplex", "Decorator",
        "Toggle", "Dimmer", "Fan Control", "Smart Switch",
    ],
    "Wire & Cable": [
        "NM-B (Romex)", "THHN", "UF-B", "MC Cable",
        "BX Cable", "Low Voltage", "Coax",
    ],
    "Lighting": [
        "Recessed", "Surface Mount", "Pendant", "Track",
        "Emergency", "LED Driver", "Flood/Spot",
    ],
    "Breakers & Fuses": [
        "Standard", "GFCI", "AFCI", "Dual Function", "GFPE",
    ],
    "Conduit & Fittings": [
        "EMT", "Rigid", "PVC", "Flex", "Liquidtight",
    ],
    "Boxes & Enclosures": [
        "Old Work", "New Work", "Weatherproof", "Junction",
    ],
    "Connectors & Terminals": [
        "Wire Nut", "Push-In", "Crimp", "Lug",
    ],
}

# Common color options for general parts
COMMON_COLORS = [
    "White", "Ivory", "Light Almond", "Black",
    "Gray", "Brown", "Red", "Blue",
]

# Common type/style options for general parts
COMMON_STYLES = [
    "Decora", "Standard", "Commercial", "Residential",
    "Industrial", "Tamper-Resistant", "Weather-Resistant",
]
