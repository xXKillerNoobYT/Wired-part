"""Database schema definition, initialization, and migrations."""

SCHEMA_VERSION = 6

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

    # Labor entries (time tracking)
    """CREATE TABLE IF NOT EXISTS labor_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        job_id INTEGER NOT NULL,
        start_time TIMESTAMP NOT NULL,
        end_time TIMESTAMP,
        hours REAL DEFAULT 0.0,
        description TEXT,
        sub_task_category TEXT NOT NULL DEFAULT 'General',
        photos TEXT DEFAULT '[]',
        clock_in_lat REAL,
        clock_in_lon REAL,
        clock_out_lat REAL,
        clock_out_lon REAL,
        rate_per_hour REAL DEFAULT 0.0,
        is_overtime INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
    )""",

    # Job locations (cached geocoding)
    """CREATE TABLE IF NOT EXISTS job_locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL UNIQUE,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        geocoded_address TEXT,
        cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
    )""",

    # Job notebooks (one per job, auto-created)
    """CREATE TABLE IF NOT EXISTS job_notebooks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL UNIQUE,
        title TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
    )""",

    # Notebook sections
    """CREATE TABLE IF NOT EXISTS notebook_sections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        notebook_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        sort_order INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (notebook_id) REFERENCES job_notebooks(id) ON DELETE CASCADE
    )""",

    # Notebook pages (individual entries with rich text)
    """CREATE TABLE IF NOT EXISTS notebook_pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        section_id INTEGER NOT NULL,
        title TEXT NOT NULL DEFAULT 'Untitled',
        content TEXT DEFAULT '',
        photos TEXT DEFAULT '[]',
        part_references TEXT DEFAULT '[]',
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (section_id) REFERENCES notebook_sections(id) ON DELETE CASCADE,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
    )""",

    # Hats (role-based permission groups)
    """CREATE TABLE IF NOT EXISTS hats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        permissions TEXT NOT NULL DEFAULT '[]',
        is_system INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",

    # User-hat assignments (many-to-many)
    """CREATE TABLE IF NOT EXISTS user_hats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        hat_id INTEGER NOT NULL,
        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        assigned_by INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (hat_id) REFERENCES hats(id) ON DELETE CASCADE,
        FOREIGN KEY (assigned_by) REFERENCES users(id) ON DELETE SET NULL,
        UNIQUE(user_id, hat_id)
    )""",

    # Purchase orders
    """CREATE TABLE IF NOT EXISTS purchase_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT NOT NULL UNIQUE,
        supplier_id INTEGER NOT NULL,
        parts_list_id INTEGER,
        status TEXT NOT NULL DEFAULT 'draft'
            CHECK (status IN ('draft', 'submitted', 'partial',
                              'received', 'closed', 'cancelled')),
        notes TEXT,
        created_by INTEGER,
        submitted_at TIMESTAMP,
        expected_delivery TIMESTAMP,
        closed_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE RESTRICT,
        FOREIGN KEY (parts_list_id) REFERENCES parts_lists(id) ON DELETE SET NULL,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
    )""",

    # Purchase order line items
    """CREATE TABLE IF NOT EXISTS purchase_order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        part_id INTEGER NOT NULL,
        quantity_ordered INTEGER NOT NULL CHECK (quantity_ordered > 0),
        quantity_received INTEGER NOT NULL DEFAULT 0
            CHECK (quantity_received >= 0),
        unit_cost REAL NOT NULL DEFAULT 0.0 CHECK (unit_cost >= 0),
        notes TEXT,
        FOREIGN KEY (order_id) REFERENCES purchase_orders(id) ON DELETE CASCADE,
        FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT
    )""",

    # Receive log (each receiving event with allocation)
    """CREATE TABLE IF NOT EXISTS receive_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_item_id INTEGER NOT NULL,
        quantity_received INTEGER NOT NULL CHECK (quantity_received > 0),
        allocate_to TEXT NOT NULL DEFAULT 'warehouse'
            CHECK (allocate_to IN ('warehouse', 'truck', 'job')),
        allocate_truck_id INTEGER,
        allocate_job_id INTEGER,
        received_by INTEGER,
        notes TEXT,
        received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_item_id)
            REFERENCES purchase_order_items(id) ON DELETE CASCADE,
        FOREIGN KEY (allocate_truck_id) REFERENCES trucks(id) ON DELETE SET NULL,
        FOREIGN KEY (allocate_job_id) REFERENCES jobs(id) ON DELETE SET NULL,
        FOREIGN KEY (received_by) REFERENCES users(id) ON DELETE SET NULL
    )""",

    # Return authorizations
    """CREATE TABLE IF NOT EXISTS return_authorizations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ra_number TEXT NOT NULL UNIQUE,
        order_id INTEGER,
        supplier_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'initiated'
            CHECK (status IN ('initiated', 'picked_up',
                              'credit_received', 'cancelled')),
        reason TEXT NOT NULL DEFAULT 'wrong_part'
            CHECK (reason IN ('wrong_part', 'damaged', 'overstock',
                              'defective', 'other')),
        notes TEXT,
        created_by INTEGER,
        credit_amount REAL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        picked_up_at TIMESTAMP,
        credit_received_at TIMESTAMP,
        FOREIGN KEY (order_id)
            REFERENCES purchase_orders(id) ON DELETE SET NULL,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE RESTRICT,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
    )""",

    # Return authorization line items
    """CREATE TABLE IF NOT EXISTS return_authorization_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ra_id INTEGER NOT NULL,
        part_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL CHECK (quantity > 0),
        unit_cost REAL NOT NULL DEFAULT 0.0 CHECK (unit_cost >= 0),
        reason TEXT,
        FOREIGN KEY (ra_id)
            REFERENCES return_authorizations(id) ON DELETE CASCADE,
        FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT
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
    "CREATE INDEX IF NOT EXISTS idx_labor_user ON labor_entries(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_labor_job ON labor_entries(job_id)",
    "CREATE INDEX IF NOT EXISTS idx_labor_start ON labor_entries(start_time)",
    "CREATE INDEX IF NOT EXISTS idx_job_locations_job ON job_locations(job_id)",
    "CREATE INDEX IF NOT EXISTS idx_notebooks_job ON job_notebooks(job_id)",
    "CREATE INDEX IF NOT EXISTS idx_sections_notebook ON notebook_sections(notebook_id)",
    "CREATE INDEX IF NOT EXISTS idx_pages_section ON notebook_pages(section_id)",
    "CREATE INDEX IF NOT EXISTS idx_hats_name ON hats(name)",
    "CREATE INDEX IF NOT EXISTS idx_user_hats_user ON user_hats(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_user_hats_hat ON user_hats(hat_id)",
    "CREATE INDEX IF NOT EXISTS idx_po_number ON purchase_orders(order_number)",
    "CREATE INDEX IF NOT EXISTS idx_po_supplier ON purchase_orders(supplier_id)",
    "CREATE INDEX IF NOT EXISTS idx_po_status ON purchase_orders(status)",
    "CREATE INDEX IF NOT EXISTS idx_po_created_by ON purchase_orders(created_by)",
    "CREATE INDEX IF NOT EXISTS idx_poi_order ON purchase_order_items(order_id)",
    "CREATE INDEX IF NOT EXISTS idx_poi_part ON purchase_order_items(part_id)",
    "CREATE INDEX IF NOT EXISTS idx_receive_log_item ON receive_log(order_item_id)",
    "CREATE INDEX IF NOT EXISTS idx_receive_log_date ON receive_log(received_at)",
    "CREATE INDEX IF NOT EXISTS idx_ra_number ON return_authorizations(ra_number)",
    "CREATE INDEX IF NOT EXISTS idx_ra_order ON return_authorizations(order_id)",
    "CREATE INDEX IF NOT EXISTS idx_ra_supplier ON return_authorizations(supplier_id)",
    "CREATE INDEX IF NOT EXISTS idx_ra_status ON return_authorizations(status)",
    "CREATE INDEX IF NOT EXISTS idx_rai_ra ON return_authorization_items(ra_id)",
    "CREATE INDEX IF NOT EXISTS idx_rai_part ON return_authorization_items(part_id)",

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

    """CREATE TRIGGER IF NOT EXISTS update_hats_timestamp AFTER UPDATE ON hats
    WHEN NEW.updated_at = OLD.updated_at BEGIN
        UPDATE hats SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END""",

    """CREATE TRIGGER IF NOT EXISTS update_purchase_orders_timestamp
    AFTER UPDATE ON purchase_orders
    WHEN NEW.updated_at = OLD.updated_at BEGIN
        UPDATE purchase_orders SET updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.id;
    END""",

    """CREATE TRIGGER IF NOT EXISTS update_return_authorizations_timestamp
    AFTER UPDATE ON return_authorizations
    WHEN NEW.updated_at = OLD.updated_at BEGIN
        UPDATE return_authorizations SET updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.id;
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


# ── Migration from v3 → v4 ──────────────────────────────────────
_MIGRATION_V4_STATEMENTS = [
    # Labor entries table
    """CREATE TABLE IF NOT EXISTS labor_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        job_id INTEGER NOT NULL,
        start_time TIMESTAMP NOT NULL,
        end_time TIMESTAMP,
        hours REAL DEFAULT 0.0,
        description TEXT,
        sub_task_category TEXT NOT NULL DEFAULT 'General',
        photos TEXT DEFAULT '[]',
        clock_in_lat REAL,
        clock_in_lon REAL,
        clock_out_lat REAL,
        clock_out_lon REAL,
        rate_per_hour REAL DEFAULT 0.0,
        is_overtime INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
    )""",

    # Job locations (cached geocoding)
    """CREATE TABLE IF NOT EXISTS job_locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL UNIQUE,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        geocoded_address TEXT,
        cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
    )""",

    # Job notebooks
    """CREATE TABLE IF NOT EXISTS job_notebooks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL UNIQUE,
        title TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
    )""",

    # Notebook sections
    """CREATE TABLE IF NOT EXISTS notebook_sections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        notebook_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        sort_order INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (notebook_id) REFERENCES job_notebooks(id) ON DELETE CASCADE
    )""",

    # Notebook pages
    """CREATE TABLE IF NOT EXISTS notebook_pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        section_id INTEGER NOT NULL,
        title TEXT NOT NULL DEFAULT 'Untitled',
        content TEXT DEFAULT '',
        photos TEXT DEFAULT '[]',
        part_references TEXT DEFAULT '[]',
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (section_id) REFERENCES notebook_sections(id) ON DELETE CASCADE,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
    )""",

    # New indexes
    "CREATE INDEX IF NOT EXISTS idx_labor_user ON labor_entries(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_labor_job ON labor_entries(job_id)",
    "CREATE INDEX IF NOT EXISTS idx_labor_start ON labor_entries(start_time)",
    "CREATE INDEX IF NOT EXISTS idx_job_locations_job ON job_locations(job_id)",
    "CREATE INDEX IF NOT EXISTS idx_notebooks_job ON job_notebooks(job_id)",
    "CREATE INDEX IF NOT EXISTS idx_sections_notebook ON notebook_sections(notebook_id)",
    "CREATE INDEX IF NOT EXISTS idx_pages_section ON notebook_pages(section_id)",

    # Update schema version
    "INSERT OR REPLACE INTO schema_version (version) VALUES (4)",
]


def _migrate_v3_to_v4(conn):
    """Upgrade schema from v3 to v4."""
    for stmt in _MIGRATION_V4_STATEMENTS:
        conn.execute(stmt)


# ── Migration from v4 → v5 ──────────────────────────────────────
_MIGRATION_V5_STATEMENTS = [
    # Hats (role-based permission groups)
    """CREATE TABLE IF NOT EXISTS hats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        permissions TEXT NOT NULL DEFAULT '[]',
        is_system INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",

    # User-hat assignments (many-to-many)
    """CREATE TABLE IF NOT EXISTS user_hats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        hat_id INTEGER NOT NULL,
        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        assigned_by INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (hat_id) REFERENCES hats(id) ON DELETE CASCADE,
        FOREIGN KEY (assigned_by) REFERENCES users(id) ON DELETE SET NULL,
        UNIQUE(user_id, hat_id)
    )""",

    # Indexes
    "CREATE INDEX IF NOT EXISTS idx_hats_name ON hats(name)",
    "CREATE INDEX IF NOT EXISTS idx_user_hats_user ON user_hats(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_user_hats_hat ON user_hats(hat_id)",

    # Trigger
    """CREATE TRIGGER IF NOT EXISTS update_hats_timestamp AFTER UPDATE ON hats
    WHEN NEW.updated_at = OLD.updated_at BEGIN
        UPDATE hats SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END""",

    # Update schema version
    "INSERT OR REPLACE INTO schema_version (version) VALUES (5)",
]


def _migrate_v4_to_v5(conn):
    """Upgrade schema from v4 to v5."""
    for stmt in _MIGRATION_V5_STATEMENTS:
        conn.execute(stmt)
    # Seed default hats
    _seed_default_hats(conn)
    # Auto-assign Admin hat to existing admin users
    _assign_hats_to_existing_admins(conn)


def _seed_default_hats(conn):
    """Create the default hat roles with their permissions."""
    import json
    from wired_part.utils.constants import HAT_NAMES, DEFAULT_HAT_PERMISSIONS
    for hat_name in HAT_NAMES:
        perms = DEFAULT_HAT_PERMISSIONS.get(hat_name, [])
        conn.execute(
            "INSERT OR IGNORE INTO hats (name, permissions, is_system) "
            "VALUES (?, ?, 1)",
            (hat_name, json.dumps(perms)),
        )


def _assign_hats_to_existing_admins(conn):
    """Auto-assign Admin hat to existing users with role='admin'."""
    admin_hat = conn.execute(
        "SELECT id FROM hats WHERE name = 'Admin'"
    ).fetchone()
    worker_hat = conn.execute(
        "SELECT id FROM hats WHERE name = 'Worker'"
    ).fetchone()
    if not admin_hat:
        return

    # All existing admin users get Admin hat
    admin_users = conn.execute(
        "SELECT id FROM users WHERE role = 'admin'"
    ).fetchall()
    for user in admin_users:
        conn.execute(
            "INSERT OR IGNORE INTO user_hats (user_id, hat_id) "
            "VALUES (?, ?)",
            (user["id"], admin_hat["id"]),
        )

    # All existing non-admin users get Worker hat
    if worker_hat:
        non_admin_users = conn.execute(
            "SELECT id FROM users WHERE role = 'user'"
        ).fetchall()
        for user in non_admin_users:
            conn.execute(
                "INSERT OR IGNORE INTO user_hats (user_id, hat_id) "
                "VALUES (?, ?)",
                (user["id"], worker_hat["id"]),
            )


# ── Migration from v5 → v6 ──────────────────────────────────────
_MIGRATION_V6_STATEMENTS = [
    # Purchase orders
    """CREATE TABLE IF NOT EXISTS purchase_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT NOT NULL UNIQUE,
        supplier_id INTEGER NOT NULL,
        parts_list_id INTEGER,
        status TEXT NOT NULL DEFAULT 'draft'
            CHECK (status IN ('draft', 'submitted', 'partial',
                              'received', 'closed', 'cancelled')),
        notes TEXT,
        created_by INTEGER,
        submitted_at TIMESTAMP,
        expected_delivery TIMESTAMP,
        closed_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE RESTRICT,
        FOREIGN KEY (parts_list_id) REFERENCES parts_lists(id) ON DELETE SET NULL,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
    )""",

    # Purchase order line items
    """CREATE TABLE IF NOT EXISTS purchase_order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        part_id INTEGER NOT NULL,
        quantity_ordered INTEGER NOT NULL CHECK (quantity_ordered > 0),
        quantity_received INTEGER NOT NULL DEFAULT 0
            CHECK (quantity_received >= 0),
        unit_cost REAL NOT NULL DEFAULT 0.0 CHECK (unit_cost >= 0),
        notes TEXT,
        FOREIGN KEY (order_id) REFERENCES purchase_orders(id) ON DELETE CASCADE,
        FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT
    )""",

    # Receive log
    """CREATE TABLE IF NOT EXISTS receive_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_item_id INTEGER NOT NULL,
        quantity_received INTEGER NOT NULL CHECK (quantity_received > 0),
        allocate_to TEXT NOT NULL DEFAULT 'warehouse'
            CHECK (allocate_to IN ('warehouse', 'truck', 'job')),
        allocate_truck_id INTEGER,
        allocate_job_id INTEGER,
        received_by INTEGER,
        notes TEXT,
        received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_item_id)
            REFERENCES purchase_order_items(id) ON DELETE CASCADE,
        FOREIGN KEY (allocate_truck_id) REFERENCES trucks(id) ON DELETE SET NULL,
        FOREIGN KEY (allocate_job_id) REFERENCES jobs(id) ON DELETE SET NULL,
        FOREIGN KEY (received_by) REFERENCES users(id) ON DELETE SET NULL
    )""",

    # Return authorizations
    """CREATE TABLE IF NOT EXISTS return_authorizations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ra_number TEXT NOT NULL UNIQUE,
        order_id INTEGER,
        supplier_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'initiated'
            CHECK (status IN ('initiated', 'picked_up',
                              'credit_received', 'cancelled')),
        reason TEXT NOT NULL DEFAULT 'wrong_part'
            CHECK (reason IN ('wrong_part', 'damaged', 'overstock',
                              'defective', 'other')),
        notes TEXT,
        created_by INTEGER,
        credit_amount REAL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        picked_up_at TIMESTAMP,
        credit_received_at TIMESTAMP,
        FOREIGN KEY (order_id)
            REFERENCES purchase_orders(id) ON DELETE SET NULL,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE RESTRICT,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
    )""",

    # Return authorization line items
    """CREATE TABLE IF NOT EXISTS return_authorization_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ra_id INTEGER NOT NULL,
        part_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL CHECK (quantity > 0),
        unit_cost REAL NOT NULL DEFAULT 0.0 CHECK (unit_cost >= 0),
        reason TEXT,
        FOREIGN KEY (ra_id)
            REFERENCES return_authorizations(id) ON DELETE CASCADE,
        FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT
    )""",

    # Indexes
    "CREATE INDEX IF NOT EXISTS idx_po_number ON purchase_orders(order_number)",
    "CREATE INDEX IF NOT EXISTS idx_po_supplier ON purchase_orders(supplier_id)",
    "CREATE INDEX IF NOT EXISTS idx_po_status ON purchase_orders(status)",
    "CREATE INDEX IF NOT EXISTS idx_po_created_by ON purchase_orders(created_by)",
    "CREATE INDEX IF NOT EXISTS idx_poi_order ON purchase_order_items(order_id)",
    "CREATE INDEX IF NOT EXISTS idx_poi_part ON purchase_order_items(part_id)",
    "CREATE INDEX IF NOT EXISTS idx_receive_log_item ON receive_log(order_item_id)",
    "CREATE INDEX IF NOT EXISTS idx_receive_log_date ON receive_log(received_at)",
    "CREATE INDEX IF NOT EXISTS idx_ra_number ON return_authorizations(ra_number)",
    "CREATE INDEX IF NOT EXISTS idx_ra_order ON return_authorizations(order_id)",
    "CREATE INDEX IF NOT EXISTS idx_ra_supplier ON return_authorizations(supplier_id)",
    "CREATE INDEX IF NOT EXISTS idx_ra_status ON return_authorizations(status)",
    "CREATE INDEX IF NOT EXISTS idx_rai_ra ON return_authorization_items(ra_id)",
    "CREATE INDEX IF NOT EXISTS idx_rai_part ON return_authorization_items(part_id)",

    # Triggers
    """CREATE TRIGGER IF NOT EXISTS update_purchase_orders_timestamp
    AFTER UPDATE ON purchase_orders
    WHEN NEW.updated_at = OLD.updated_at BEGIN
        UPDATE purchase_orders SET updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.id;
    END""",

    """CREATE TRIGGER IF NOT EXISTS update_return_authorizations_timestamp
    AFTER UPDATE ON return_authorizations
    WHEN NEW.updated_at = OLD.updated_at BEGIN
        UPDATE return_authorizations SET updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.id;
    END""",

    # Update schema version
    "INSERT OR REPLACE INTO schema_version (version) VALUES (6)",
]


def _migrate_v5_to_v6(conn):
    """Upgrade schema from v5 to v6."""
    for stmt in _MIGRATION_V6_STATEMENTS:
        conn.execute(stmt)
    # Update hat permissions for order-related keys
    _seed_order_permissions(conn)


def _seed_order_permissions(conn):
    """Update existing hats with new order-related permissions."""
    import json
    from wired_part.utils.constants import DEFAULT_HAT_PERMISSIONS

    for hat_name, perms in DEFAULT_HAT_PERMISSIONS.items():
        # Get the hat's current permissions
        row = conn.execute(
            "SELECT id, permissions FROM hats WHERE name = ?",
            (hat_name,),
        ).fetchone()
        if not row:
            continue

        current = json.loads(row["permissions"]) if row["permissions"] else []
        # Add any new order permissions not already present
        order_perms = [p for p in perms if p.startswith("orders_") or p == "tab_orders"]
        updated = False
        for perm in order_perms:
            if perm not in current:
                current.append(perm)
                updated = True
        if updated:
            conn.execute(
                "UPDATE hats SET permissions = ? WHERE id = ?",
                (json.dumps(current), row["id"]),
            )


def initialize_database(db_connection):
    """Create all tables, indexes, triggers, and seed data.

    On a fresh database, creates the full v6 schema directly.
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
            # Seed default hats
            _seed_default_hats(conn)
        elif version < SCHEMA_VERSION:
            # Existing database: apply migrations
            if version < 2:
                _migrate_v1_to_v2(conn)
            if version < 3:
                _migrate_v2_to_v3(conn)
            if version < 4:
                _migrate_v3_to_v4(conn)
            if version < 5:
                _migrate_v4_to_v5(conn)
            if version < 6:
                _migrate_v5_to_v6(conn)
