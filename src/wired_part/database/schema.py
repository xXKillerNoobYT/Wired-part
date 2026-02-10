"""Database schema definition, initialization, and migrations."""

SCHEMA_VERSION = 3

# Each statement is a separate string to avoid executescript issues
_SCHEMA_STATEMENTS = [
    # Categories table
    """CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        is_custom INTEGER NOT NULL DEFAULT 0,
        color TEXT DEFAULT '#6c7086',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",

    # Parts table (warehouse inventory)
    """CREATE TABLE IF NOT EXISTS parts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part_number TEXT NOT NULL UNIQUE,
        description TEXT NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
        location TEXT,
        category_id INTEGER,
        unit_cost REAL DEFAULT 0.00 CHECK (unit_cost >= 0),
        min_quantity INTEGER DEFAULT 0 CHECK (min_quantity >= 0),
        supplier TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
    )""",

    # Suppliers table
    """CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        contact_name TEXT,
        email TEXT,
        phone TEXT,
        address TEXT,
        notes TEXT,
        preference_score INTEGER NOT NULL DEFAULT 50
            CHECK (preference_score BETWEEN 0 AND 100),
        delivery_schedule TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",

    # Parts lists (templates and specific instances)
    """CREATE TABLE IF NOT EXISTS parts_lists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        list_type TEXT NOT NULL DEFAULT 'general'
            CHECK (list_type IN ('general', 'specific', 'fast')),
        job_id INTEGER,
        notes TEXT,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE SET NULL,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
    )""",

    # Parts list items
    """CREATE TABLE IF NOT EXISTS parts_list_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        list_id INTEGER NOT NULL,
        part_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
        notes TEXT,
        FOREIGN KEY (list_id) REFERENCES parts_lists(id) ON DELETE CASCADE,
        FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT
    )""",

    # Users table (before jobs/trucks so FKs resolve)
    """CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        display_name TEXT NOT NULL,
        pin_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('admin', 'user')),
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",

    # Jobs table
    """CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_number TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        customer TEXT,
        address TEXT,
        status TEXT NOT NULL DEFAULT 'active'
            CHECK (status IN ('active', 'completed', 'on_hold', 'cancelled')),
        priority INTEGER NOT NULL DEFAULT 3
            CHECK (priority BETWEEN 1 AND 5),
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP
    )""",

    # Trucks table
    """CREATE TABLE IF NOT EXISTS trucks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        truck_number TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        assigned_user_id INTEGER,
        notes TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (assigned_user_id) REFERENCES users(id) ON DELETE SET NULL
    )""",

    # Junction table: parts assigned to jobs
    """CREATE TABLE IF NOT EXISTS job_parts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        part_id INTEGER NOT NULL,
        quantity_used INTEGER NOT NULL DEFAULT 1 CHECK (quantity_used > 0),
        unit_cost_at_use REAL,
        consumed_from_truck_id INTEGER,
        consumed_by INTEGER,
        notes TEXT,
        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
        FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT,
        FOREIGN KEY (consumed_from_truck_id) REFERENCES trucks(id) ON DELETE SET NULL,
        FOREIGN KEY (consumed_by) REFERENCES users(id) ON DELETE SET NULL,
        UNIQUE(job_id, part_id)
    )""",

    # Truck on-hand inventory
    """CREATE TABLE IF NOT EXISTS truck_inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        truck_id INTEGER NOT NULL,
        part_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
        FOREIGN KEY (truck_id) REFERENCES trucks(id) ON DELETE CASCADE,
        FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT,
        UNIQUE(truck_id, part_id)
    )""",

    # Truck transfers: warehouse↔truck movement
    """CREATE TABLE IF NOT EXISTS truck_transfers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        truck_id INTEGER NOT NULL,
        part_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL CHECK (quantity > 0),
        direction TEXT NOT NULL CHECK (direction IN ('outbound', 'return')),
        status TEXT NOT NULL DEFAULT 'pending'
            CHECK (status IN ('pending', 'received', 'cancelled')),
        created_by INTEGER,
        received_by INTEGER,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        received_at TIMESTAMP,
        FOREIGN KEY (truck_id) REFERENCES trucks(id) ON DELETE CASCADE,
        FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY (received_by) REFERENCES users(id) ON DELETE SET NULL
    )""",

    # Job assignments: many-to-many users↔jobs
    """CREATE TABLE IF NOT EXISTS job_assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        role TEXT NOT NULL DEFAULT 'worker' CHECK (role IN ('lead', 'worker')),
        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        UNIQUE(job_id, user_id)
    )""",

    # Notifications
    """CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        severity TEXT NOT NULL DEFAULT 'info'
            CHECK (severity IN ('info', 'warning', 'critical')),
        source TEXT DEFAULT 'system',
        is_read INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )""",

    # Consumption log: truck→job part usage
    """CREATE TABLE IF NOT EXISTS consumption_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        truck_id INTEGER NOT NULL,
        part_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL CHECK (quantity > 0),
        unit_cost_at_use REAL DEFAULT 0.0,
        consumed_by INTEGER,
        notes TEXT,
        consumed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
        FOREIGN KEY (truck_id) REFERENCES trucks(id) ON DELETE CASCADE,
        FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT,
        FOREIGN KEY (consumed_by) REFERENCES users(id) ON DELETE SET NULL
    )""",

    # Schema version tracking
    """CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",

    # ── Indexes ──────────────────────────────────────────────────
    "CREATE INDEX IF NOT EXISTS idx_parts_part_number ON parts(part_number)",
    "CREATE INDEX IF NOT EXISTS idx_parts_category ON parts(category_id)",
    "CREATE INDEX IF NOT EXISTS idx_parts_location ON parts(location)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_priority ON jobs(priority)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_job_number ON jobs(job_number)",
    "CREATE INDEX IF NOT EXISTS idx_job_parts_job ON job_parts(job_id)",
    "CREATE INDEX IF NOT EXISTS idx_job_parts_part ON job_parts(part_id)",
    "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
    "CREATE INDEX IF NOT EXISTS idx_trucks_number ON trucks(truck_number)",
    "CREATE INDEX IF NOT EXISTS idx_trucks_user ON trucks(assigned_user_id)",
    "CREATE INDEX IF NOT EXISTS idx_truck_inv_truck ON truck_inventory(truck_id)",
    "CREATE INDEX IF NOT EXISTS idx_truck_inv_part ON truck_inventory(part_id)",
    "CREATE INDEX IF NOT EXISTS idx_transfers_truck ON truck_transfers(truck_id)",
    "CREATE INDEX IF NOT EXISTS idx_transfers_status ON truck_transfers(status)",
    "CREATE INDEX IF NOT EXISTS idx_job_assign_job ON job_assignments(job_id)",
    "CREATE INDEX IF NOT EXISTS idx_job_assign_user ON job_assignments(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(is_read)",
    "CREATE INDEX IF NOT EXISTS idx_consumption_job ON consumption_log(job_id)",
    "CREATE INDEX IF NOT EXISTS idx_consumption_truck ON consumption_log(truck_id)",
    "CREATE INDEX IF NOT EXISTS idx_suppliers_name ON suppliers(name)",
    "CREATE INDEX IF NOT EXISTS idx_parts_lists_job ON parts_lists(job_id)",
    "CREATE INDEX IF NOT EXISTS idx_parts_list_items_list ON parts_list_items(list_id)",

    # ── Triggers ─────────────────────────────────────────────────
    """CREATE TRIGGER IF NOT EXISTS update_jobs_timestamp AFTER UPDATE ON jobs
    WHEN NEW.updated_at = OLD.updated_at BEGIN
        UPDATE jobs SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END""",

    """CREATE TRIGGER IF NOT EXISTS update_categories_timestamp AFTER UPDATE ON categories
    WHEN NEW.updated_at = OLD.updated_at BEGIN
        UPDATE categories SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END""",

    """CREATE TRIGGER IF NOT EXISTS update_users_timestamp AFTER UPDATE ON users
    WHEN NEW.updated_at = OLD.updated_at BEGIN
        UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END""",

    """CREATE TRIGGER IF NOT EXISTS update_trucks_timestamp AFTER UPDATE ON trucks
    WHEN NEW.updated_at = OLD.updated_at BEGIN
        UPDATE trucks SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END""",

    # Record schema version
    f"INSERT OR IGNORE INTO schema_version (version) VALUES ({SCHEMA_VERSION})",
]

_SEED_CATEGORIES = [
    ("Wire & Cable", "Electrical wiring, cables, and conductors"),
    ("Conduit & Fittings", "Conduit, connectors, and fittings"),
    ("Boxes & Enclosures", "Junction boxes, panels, and enclosures"),
    ("Switches & Outlets", "Switches, receptacles, and plates"),
    ("Breakers & Fuses", "Circuit breakers, fuses, and protection devices"),
    ("Lighting", "Light fixtures, bulbs, and components"),
    ("Connectors & Terminals", "Wire nuts, terminals, and connectors"),
    ("Tools & Supplies", "Tape, lubricant, and consumables"),
    ("Motors & Controls", "Motors, starters, and control equipment"),
    ("Miscellaneous", "Other electrical parts"),
]

# ── Migration from v1 → v2 ──────────────────────────────────────
_MIGRATION_V2_STATEMENTS = [
    # Add new columns to categories
    "ALTER TABLE categories ADD COLUMN is_custom INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE categories ADD COLUMN color TEXT DEFAULT '#6c7086'",

    # Create users and trucks first (referenced by later ALTER/CREATE statements)
    """CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        display_name TEXT NOT NULL,
        pin_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('admin', 'user')),
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",

    """CREATE TABLE IF NOT EXISTS trucks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        truck_number TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        assigned_user_id INTEGER,
        notes TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (assigned_user_id) REFERENCES users(id) ON DELETE SET NULL
    )""",

    # Now safe to alter job_parts (users and trucks exist)
    "ALTER TABLE job_parts ADD COLUMN consumed_from_truck_id INTEGER REFERENCES trucks(id)",
    "ALTER TABLE job_parts ADD COLUMN consumed_by INTEGER REFERENCES users(id)",

    """CREATE TABLE IF NOT EXISTS truck_inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        truck_id INTEGER NOT NULL,
        part_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
        FOREIGN KEY (truck_id) REFERENCES trucks(id) ON DELETE CASCADE,
        FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT,
        UNIQUE(truck_id, part_id)
    )""",

    """CREATE TABLE IF NOT EXISTS truck_transfers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        truck_id INTEGER NOT NULL,
        part_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL CHECK (quantity > 0),
        direction TEXT NOT NULL CHECK (direction IN ('outbound', 'return')),
        status TEXT NOT NULL DEFAULT 'pending'
            CHECK (status IN ('pending', 'received', 'cancelled')),
        created_by INTEGER,
        received_by INTEGER,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        received_at TIMESTAMP,
        FOREIGN KEY (truck_id) REFERENCES trucks(id) ON DELETE CASCADE,
        FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY (received_by) REFERENCES users(id) ON DELETE SET NULL
    )""",

    """CREATE TABLE IF NOT EXISTS job_assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        role TEXT NOT NULL DEFAULT 'worker' CHECK (role IN ('lead', 'worker')),
        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        UNIQUE(job_id, user_id)
    )""",

    """CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        severity TEXT NOT NULL DEFAULT 'info'
            CHECK (severity IN ('info', 'warning', 'critical')),
        source TEXT DEFAULT 'system',
        is_read INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )""",

    """CREATE TABLE IF NOT EXISTS consumption_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        truck_id INTEGER NOT NULL,
        part_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL CHECK (quantity > 0),
        unit_cost_at_use REAL DEFAULT 0.0,
        consumed_by INTEGER,
        notes TEXT,
        consumed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
        FOREIGN KEY (truck_id) REFERENCES trucks(id) ON DELETE CASCADE,
        FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT,
        FOREIGN KEY (consumed_by) REFERENCES users(id) ON DELETE SET NULL
    )""",

    # New indexes
    "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
    "CREATE INDEX IF NOT EXISTS idx_trucks_number ON trucks(truck_number)",
    "CREATE INDEX IF NOT EXISTS idx_trucks_user ON trucks(assigned_user_id)",
    "CREATE INDEX IF NOT EXISTS idx_truck_inv_truck ON truck_inventory(truck_id)",
    "CREATE INDEX IF NOT EXISTS idx_truck_inv_part ON truck_inventory(part_id)",
    "CREATE INDEX IF NOT EXISTS idx_transfers_truck ON truck_transfers(truck_id)",
    "CREATE INDEX IF NOT EXISTS idx_transfers_status ON truck_transfers(status)",
    "CREATE INDEX IF NOT EXISTS idx_job_assign_job ON job_assignments(job_id)",
    "CREATE INDEX IF NOT EXISTS idx_job_assign_user ON job_assignments(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(is_read)",
    "CREATE INDEX IF NOT EXISTS idx_consumption_job ON consumption_log(job_id)",
    "CREATE INDEX IF NOT EXISTS idx_consumption_truck ON consumption_log(truck_id)",

    # New triggers
    """CREATE TRIGGER IF NOT EXISTS update_users_timestamp AFTER UPDATE ON users
    WHEN NEW.updated_at = OLD.updated_at BEGIN
        UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END""",

    """CREATE TRIGGER IF NOT EXISTS update_trucks_timestamp AFTER UPDATE ON trucks
    WHEN NEW.updated_at = OLD.updated_at BEGIN
        UPDATE trucks SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END""",

    # Update schema version
    "INSERT OR REPLACE INTO schema_version (version) VALUES (2)",
]


def _get_schema_version(conn) -> int:
    """Get the current schema version, or 0 if no schema exists."""
    try:
        row = conn.execute(
            "SELECT MAX(version) as v FROM schema_version"
        ).fetchone()
        return row["v"] if row and row["v"] else 0
    except Exception:
        return 0


# ── Migration from v2 → v3 ──────────────────────────────────────
_MIGRATION_V3_STATEMENTS = [
    # Add priority column to jobs (1=highest, 5=lowest, default=3)
    "ALTER TABLE jobs ADD COLUMN priority INTEGER NOT NULL DEFAULT 3",

    # Add index for priority sorting
    "CREATE INDEX IF NOT EXISTS idx_jobs_priority ON jobs(priority)",

    # Suppliers table
    """CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        contact_name TEXT,
        email TEXT,
        phone TEXT,
        address TEXT,
        notes TEXT,
        preference_score INTEGER NOT NULL DEFAULT 50
            CHECK (preference_score BETWEEN 0 AND 100),
        delivery_schedule TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",

    # Parts lists table
    """CREATE TABLE IF NOT EXISTS parts_lists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        list_type TEXT NOT NULL DEFAULT 'general'
            CHECK (list_type IN ('general', 'specific', 'fast')),
        job_id INTEGER,
        notes TEXT,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE SET NULL,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
    )""",

    # Parts list items
    """CREATE TABLE IF NOT EXISTS parts_list_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        list_id INTEGER NOT NULL,
        part_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
        notes TEXT,
        FOREIGN KEY (list_id) REFERENCES parts_lists(id) ON DELETE CASCADE,
        FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT
    )""",

    # New indexes
    "CREATE INDEX IF NOT EXISTS idx_suppliers_name ON suppliers(name)",
    "CREATE INDEX IF NOT EXISTS idx_parts_lists_job ON parts_lists(job_id)",
    "CREATE INDEX IF NOT EXISTS idx_parts_list_items_list ON parts_list_items(list_id)",

    # Update schema version
    "INSERT OR REPLACE INTO schema_version (version) VALUES (3)",
]


def _migrate_v1_to_v2(conn):
    """Upgrade schema from v1 to v2."""
    for stmt in _MIGRATION_V2_STATEMENTS:
        conn.execute(stmt)


def _migrate_v2_to_v3(conn):
    """Upgrade schema from v2 to v3."""
    for stmt in _MIGRATION_V3_STATEMENTS:
        conn.execute(stmt)


def initialize_database(db_connection):
    """Create all tables, indexes, triggers, and seed data.

    On a fresh database, creates the full v3 schema directly.
    On an existing database, applies migrations incrementally.
    """
    with db_connection.get_connection() as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        # Check if this is an existing database
        version = _get_schema_version(conn)

        if version == 0:
            # Fresh database: create full schema
            for stmt in _SCHEMA_STATEMENTS:
                conn.execute(stmt)
            for name, desc in _SEED_CATEGORIES:
                conn.execute(
                    "INSERT OR IGNORE INTO categories (name, description) "
                    "VALUES (?, ?)",
                    (name, desc),
                )
        elif version < SCHEMA_VERSION:
            # Existing database: apply migrations
            if version < 2:
                _migrate_v1_to_v2(conn)
            if version < 3:
                _migrate_v2_to_v3(conn)
