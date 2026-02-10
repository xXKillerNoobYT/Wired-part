"""Application-wide constants."""

APP_NAME = "Wired-Part"
APP_VERSION = "2.0.0"
APP_ORGANIZATION = "WeirdToo LLC"

# Job statuses
JOB_STATUSES = ["active", "completed", "on_hold", "cancelled"]

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

# Default window size
DEFAULT_WINDOW_WIDTH = 1200
DEFAULT_WINDOW_HEIGHT = 800
MIN_WINDOW_WIDTH = 900
MIN_WINDOW_HEIGHT = 600

# Background agent intervals (milliseconds)
AUDIT_AGENT_INTERVAL = 30 * 60 * 1000      # 30 minutes
ADMIN_AGENT_INTERVAL = 60 * 60 * 1000      # 60 minutes
REMINDER_AGENT_INTERVAL = 15 * 60 * 1000   # 15 minutes
