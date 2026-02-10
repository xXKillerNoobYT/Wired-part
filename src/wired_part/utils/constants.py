"""Application-wide constants."""

APP_NAME = "Wired-Part"
APP_VERSION = "3.0.0"
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

# User roles
USER_ROLES = ["admin", "user"]

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

# Default window size
DEFAULT_WINDOW_WIDTH = 1200
DEFAULT_WINDOW_HEIGHT = 800
MIN_WINDOW_WIDTH = 900
MIN_WINDOW_HEIGHT = 600

# Background agent intervals (minutes) — defaults, overridable via Config
AUDIT_AGENT_INTERVAL_DEFAULT = 30
ADMIN_AGENT_INTERVAL_DEFAULT = 60
REMINDER_AGENT_INTERVAL_DEFAULT = 15
