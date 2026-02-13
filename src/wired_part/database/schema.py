"""Database schema definition, initialization, and migrations."""

SCHEMA_VERSION = 12

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
        part_number TEXT DEFAULT '',
        description TEXT DEFAULT '',
        quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
        location TEXT,
        category_id INTEGER,
        unit_cost REAL DEFAULT 0.00 CHECK (unit_cost >= 0),
        min_quantity INTEGER DEFAULT 0 CHECK (min_quantity >= 0),
        max_quantity INTEGER DEFAULT 0 CHECK (max_quantity >= 0),
        supplier TEXT,
        notes TEXT,
        name TEXT DEFAULT '',
        part_type TEXT NOT NULL DEFAULT 'general'
            CHECK (part_type IN ('general', 'specific')),
        brand_id INTEGER,
        brand_part_number TEXT DEFAULT '',
        local_part_number TEXT DEFAULT '',
        image_path TEXT DEFAULT '',
        subcategory TEXT DEFAULT '',
        color_options TEXT DEFAULT '[]',
        type_style TEXT DEFAULT '[]',
        has_qr_tag INTEGER NOT NULL DEFAULT 0,
        pdfs TEXT DEFAULT '[]',
        deprecation_status TEXT DEFAULT NULL,
        deprecation_started_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL,
        FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL
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
        is_supply_house INTEGER NOT NULL DEFAULT 0,
        operating_hours TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",

    # Brands table (v8)
    """CREATE TABLE IF NOT EXISTS brands (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        website TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",

    # Part-supplier links: many-to-many for specific parts (v8)
    """CREATE TABLE IF NOT EXISTS part_suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part_id INTEGER NOT NULL,
        supplier_id INTEGER NOT NULL,
        supplier_part_number TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE,
        UNIQUE(part_id, supplier_id)
    )""",

    # Part variants: type/style + color variants for parts (v9)
    """CREATE TABLE IF NOT EXISTS part_variants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part_id INTEGER NOT NULL,
        type_style TEXT NOT NULL DEFAULT '',
        color_finish TEXT NOT NULL,
        brand_part_number TEXT DEFAULT '',
        image_path TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE,
        UNIQUE(part_id, type_style, color_finish)
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
        bill_out_rate TEXT NOT NULL DEFAULT '',
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
        supplier_id INTEGER,
        source_order_id INTEGER,
        notes TEXT,
        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
        FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT,
        FOREIGN KEY (consumed_from_truck_id) REFERENCES trucks(id) ON DELETE SET NULL,
        FOREIGN KEY (consumed_by) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL,
        FOREIGN KEY (source_order_id) REFERENCES purchase_orders(id) ON DELETE SET NULL,
        UNIQUE(job_id, part_id)
    )""",

    # Truck on-hand inventory
    """CREATE TABLE IF NOT EXISTS truck_inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        truck_id INTEGER NOT NULL,
        part_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
        min_quantity INTEGER NOT NULL DEFAULT 0,
        max_quantity INTEGER NOT NULL DEFAULT 0,
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
        parts_list_id INTEGER,
        job_id INTEGER,
        source_order_id INTEGER,
        supplier_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        received_at TIMESTAMP,
        FOREIGN KEY (truck_id) REFERENCES trucks(id) ON DELETE CASCADE,
        FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY (received_by) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY (parts_list_id) REFERENCES parts_lists(id) ON DELETE SET NULL,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE SET NULL,
        FOREIGN KEY (source_order_id) REFERENCES purchase_orders(id) ON DELETE SET NULL,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL
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
        target_tab TEXT DEFAULT '',
        target_data TEXT DEFAULT '',
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
        supplier_id INTEGER,
        source_order_id INTEGER,
        notes TEXT,
        consumed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
        FOREIGN KEY (truck_id) REFERENCES trucks(id) ON DELETE CASCADE,
        FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT,
        FOREIGN KEY (consumed_by) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL,
        FOREIGN KEY (source_order_id) REFERENCES purchase_orders(id) ON DELETE SET NULL
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
        bill_out_rate TEXT NOT NULL DEFAULT '',
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
        supplier_id INTEGER,
        notes TEXT,
        received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_item_id)
            REFERENCES purchase_order_items(id) ON DELETE CASCADE,
        FOREIGN KEY (allocate_truck_id) REFERENCES trucks(id) ON DELETE SET NULL,
        FOREIGN KEY (allocate_job_id) REFERENCES jobs(id) ON DELETE SET NULL,
        FOREIGN KEY (received_by) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL
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

    # Billing cycles
    """CREATE TABLE IF NOT EXISTS billing_cycles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER,
        cycle_type TEXT NOT NULL DEFAULT 'monthly'
            CHECK (cycle_type IN ('weekly', 'biweekly', 'monthly', 'quarterly')),
        billing_day INTEGER NOT NULL DEFAULT 1,
        next_billing_date TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
    )""",

    # Billing periods
    """CREATE TABLE IF NOT EXISTS billing_periods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        billing_cycle_id INTEGER NOT NULL,
        period_start TEXT NOT NULL,
        period_end TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open'
            CHECK (status IN ('open', 'closed')),
        total_parts_cost REAL NOT NULL DEFAULT 0.0,
        total_hours REAL NOT NULL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (billing_cycle_id) REFERENCES billing_cycles(id) ON DELETE CASCADE
    )""",

    # Inventory audits
    """CREATE TABLE IF NOT EXISTS inventory_audits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        audit_type TEXT NOT NULL DEFAULT 'warehouse'
            CHECK (audit_type IN ('warehouse', 'truck', 'job')),
        target_id INTEGER,
        part_id INTEGER NOT NULL,
        expected_quantity INTEGER NOT NULL DEFAULT 0,
        actual_quantity INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'confirmed'
            CHECK (status IN ('confirmed', 'discrepancy', 'skipped')),
        audited_by INTEGER,
        audited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE,
        FOREIGN KEY (audited_by) REFERENCES users(id) ON DELETE SET NULL
    )""",

    # AI order suggestions
    """CREATE TABLE IF NOT EXISTS order_suggestions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trigger_part_id INTEGER NOT NULL,
        suggested_part_id INTEGER NOT NULL,
        score REAL NOT NULL DEFAULT 0.0,
        source TEXT NOT NULL DEFAULT 'co_occurrence',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (trigger_part_id) REFERENCES parts(id) ON DELETE CASCADE,
        FOREIGN KEY (suggested_part_id) REFERENCES parts(id) ON DELETE CASCADE,
        UNIQUE(trigger_part_id, suggested_part_id)
    )""",

    """CREATE TABLE IF NOT EXISTS order_patterns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part_id_a INTEGER NOT NULL,
        part_id_b INTEGER NOT NULL,
        co_occurrence_count INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (part_id_a) REFERENCES parts(id) ON DELETE CASCADE,
        FOREIGN KEY (part_id_b) REFERENCES parts(id) ON DELETE CASCADE,
        UNIQUE(part_id_a, part_id_b)
    )""",

    # Activity log: audit trail for all major actions (v12)
    """CREATE TABLE IF NOT EXISTS activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id INTEGER,
        entity_label TEXT DEFAULT '',
        details TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
    )""",

    # Job updates: team communication per job (v12)
    """CREATE TABLE IF NOT EXISTS job_updates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        update_type TEXT NOT NULL DEFAULT 'comment'
            CHECK (update_type IN ('comment', 'status_change',
                                   'assignment', 'milestone')),
        is_pinned INTEGER NOT NULL DEFAULT 0,
        photos TEXT DEFAULT '[]',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
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
    "CREATE INDEX IF NOT EXISTS idx_transfers_list ON truck_transfers(parts_list_id)",
    "CREATE INDEX IF NOT EXISTS idx_transfers_job ON truck_transfers(job_id)",
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

    # v8 indexes
    "CREATE INDEX IF NOT EXISTS idx_parts_part_type ON parts(part_type)",
    "CREATE INDEX IF NOT EXISTS idx_parts_brand ON parts(brand_id)",
    "CREATE INDEX IF NOT EXISTS idx_parts_local_pn ON parts(local_part_number)",
    "CREATE INDEX IF NOT EXISTS idx_parts_qr_tag ON parts(has_qr_tag)",
    "CREATE INDEX IF NOT EXISTS idx_brands_name ON brands(name)",
    "CREATE INDEX IF NOT EXISTS idx_part_suppliers_part ON part_suppliers(part_id)",
    "CREATE INDEX IF NOT EXISTS idx_part_suppliers_supplier ON part_suppliers(supplier_id)",
    "CREATE INDEX IF NOT EXISTS idx_part_variants_part ON part_variants(part_id)",

    # v12 indexes: supplier tracking
    "CREATE INDEX IF NOT EXISTS idx_transfers_supplier ON truck_transfers(supplier_id)",
    "CREATE INDEX IF NOT EXISTS idx_transfers_source_order ON truck_transfers(source_order_id)",
    "CREATE INDEX IF NOT EXISTS idx_consumption_supplier ON consumption_log(supplier_id)",
    "CREATE INDEX IF NOT EXISTS idx_consumption_source_order ON consumption_log(source_order_id)",
    "CREATE INDEX IF NOT EXISTS idx_job_parts_supplier ON job_parts(supplier_id)",
    "CREATE INDEX IF NOT EXISTS idx_receive_log_supplier ON receive_log(supplier_id)",
    # v12 indexes: activity log
    "CREATE INDEX IF NOT EXISTS idx_activity_user ON activity_log(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_activity_entity ON activity_log(entity_type, entity_id)",
    "CREATE INDEX IF NOT EXISTS idx_activity_action ON activity_log(action)",
    "CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_log(created_at)",
    # v12 indexes: job updates
    "CREATE INDEX IF NOT EXISTS idx_job_updates_job ON job_updates(job_id)",
    "CREATE INDEX IF NOT EXISTS idx_job_updates_user ON job_updates(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_job_updates_created ON job_updates(created_at)",

    # v10 indexes
    "CREATE INDEX IF NOT EXISTS idx_parts_deprecation ON parts(deprecation_status)",
    "CREATE INDEX IF NOT EXISTS idx_billing_cycles_job ON billing_cycles(job_id)",
    "CREATE INDEX IF NOT EXISTS idx_billing_periods_cycle ON billing_periods(billing_cycle_id)",
    "CREATE INDEX IF NOT EXISTS idx_billing_periods_status ON billing_periods(status)",
    "CREATE INDEX IF NOT EXISTS idx_audits_type ON inventory_audits(audit_type)",
    "CREATE INDEX IF NOT EXISTS idx_audits_part ON inventory_audits(part_id)",
    "CREATE INDEX IF NOT EXISTS idx_audits_at ON inventory_audits(audited_at)",
    "CREATE INDEX IF NOT EXISTS idx_suggestions_trigger ON order_suggestions(trigger_part_id)",
    "CREATE INDEX IF NOT EXISTS idx_patterns_a ON order_patterns(part_id_a)",

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

    """CREATE TRIGGER IF NOT EXISTS update_brands_timestamp AFTER UPDATE ON brands
    WHEN NEW.updated_at = OLD.updated_at BEGIN
        UPDATE brands SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
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
        min_quantity INTEGER NOT NULL DEFAULT 0,
        max_quantity INTEGER NOT NULL DEFAULT 0,
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
        parts_list_id INTEGER,
        job_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        received_at TIMESTAMP,
        FOREIGN KEY (truck_id) REFERENCES trucks(id) ON DELETE CASCADE,
        FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY (received_by) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY (parts_list_id) REFERENCES parts_lists(id) ON DELETE SET NULL,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE SET NULL
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
        target_tab TEXT DEFAULT '',
        target_data TEXT DEFAULT '',
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
    "CREATE INDEX IF NOT EXISTS idx_transfers_list ON truck_transfers(parts_list_id)",
    "CREATE INDEX IF NOT EXISTS idx_transfers_job ON truck_transfers(job_id)",
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
        bill_out_rate TEXT NOT NULL DEFAULT '',
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


def _rename_legacy_hats(conn):
    """Rename legacy system hats to their new display names (idempotent)."""
    from wired_part.utils.constants import _HAT_RENAME_MAP
    for old_name, new_name in _HAT_RENAME_MAP.items():
        conn.execute(
            "UPDATE hats SET name = ? WHERE name = ? AND is_system = 1",
            (new_name, old_name),
        )


def _refresh_system_hat_permissions(conn):
    """Ensure all system hats have the latest default permissions.

    Merges any new permission keys from DEFAULT_HAT_PERMISSIONS into
    the stored hat JSON.  This keeps migrated databases in sync when
    new features add new permission keys.

    Matches hats by is_system=1 and uses a name→defaults lookup.
    """
    import json
    from wired_part.utils.constants import DEFAULT_HAT_PERMISSIONS

    rows = conn.execute(
        "SELECT id, name, permissions FROM hats WHERE is_system = 1"
    ).fetchall()

    for row in rows:
        hat_name = row["name"]
        defaults = DEFAULT_HAT_PERMISSIONS.get(hat_name, [])
        if not defaults:
            continue

        current = json.loads(row["permissions"]) if row["permissions"] else []
        merged = list(current)
        updated = False
        for perm in defaults:
            if perm not in merged:
                merged.append(perm)
                updated = True
        if updated:
            conn.execute(
                "UPDATE hats SET permissions = ? WHERE id = ?",
                (json.dumps(merged), row["id"]),
            )


def _assign_hats_to_existing_admins(conn):
    """Auto-assign Admin hat to existing users with role='admin'."""
    # Find admin hat by id=1 (reliable) or by current name (fallback)
    admin_hat = conn.execute(
        "SELECT id FROM hats WHERE id = 1"
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


# ── v7 migration: supply house support on suppliers ─────────────
_MIGRATION_V7_STATEMENTS = [
    "ALTER TABLE suppliers ADD COLUMN is_supply_house INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE suppliers ADD COLUMN operating_hours TEXT",
    # Update schema version
    "INSERT OR REPLACE INTO schema_version (version) VALUES (7)",
]


def _migrate_v6_to_v7(conn):
    """Upgrade schema from v6 to v7 — add supply house columns."""
    for stmt in _MIGRATION_V7_STATEMENTS:
        try:
            conn.execute(stmt)
        except Exception:
            pass  # Column may already exist


    # ── Migration from v7 → v8: Parts Catalog overhaul ─────────────
_MIGRATION_V8_ALTER_STATEMENTS = [
    "ALTER TABLE parts ADD COLUMN part_type TEXT NOT NULL DEFAULT 'general'",
    "ALTER TABLE parts ADD COLUMN brand_id INTEGER REFERENCES brands(id) ON DELETE SET NULL",
    "ALTER TABLE parts ADD COLUMN brand_part_number TEXT DEFAULT ''",
    "ALTER TABLE parts ADD COLUMN local_part_number TEXT DEFAULT ''",
    "ALTER TABLE parts ADD COLUMN image_path TEXT DEFAULT ''",
    "ALTER TABLE parts ADD COLUMN subcategory TEXT DEFAULT ''",
    "ALTER TABLE parts ADD COLUMN color_options TEXT DEFAULT '[]'",
    "ALTER TABLE parts ADD COLUMN type_style TEXT DEFAULT '[]'",
    "ALTER TABLE parts ADD COLUMN has_qr_tag INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE parts ADD COLUMN name TEXT DEFAULT ''",
    "ALTER TABLE parts ADD COLUMN max_quantity INTEGER DEFAULT 0",
    "ALTER TABLE parts ADD COLUMN pdfs TEXT DEFAULT '[]'",
]

_MIGRATION_V8_STATEMENTS = [
    # New tables
    """CREATE TABLE IF NOT EXISTS brands (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        website TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",

    """CREATE TABLE IF NOT EXISTS part_suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part_id INTEGER NOT NULL,
        supplier_id INTEGER NOT NULL,
        supplier_part_number TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE,
        UNIQUE(part_id, supplier_id)
    )""",

    """CREATE TABLE IF NOT EXISTS part_variants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part_id INTEGER NOT NULL,
        color_finish TEXT NOT NULL,
        brand_part_number TEXT DEFAULT '',
        image_path TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE,
        UNIQUE(part_id, color_finish)
    )""",

    # Indexes
    "CREATE INDEX IF NOT EXISTS idx_parts_part_type ON parts(part_type)",
    "CREATE INDEX IF NOT EXISTS idx_parts_brand ON parts(brand_id)",
    "CREATE INDEX IF NOT EXISTS idx_parts_local_pn ON parts(local_part_number)",
    "CREATE INDEX IF NOT EXISTS idx_parts_qr_tag ON parts(has_qr_tag)",
    "CREATE INDEX IF NOT EXISTS idx_brands_name ON brands(name)",
    "CREATE INDEX IF NOT EXISTS idx_part_suppliers_part ON part_suppliers(part_id)",
    "CREATE INDEX IF NOT EXISTS idx_part_suppliers_supplier ON part_suppliers(supplier_id)",
    "CREATE INDEX IF NOT EXISTS idx_part_variants_part ON part_variants(part_id)",

    # Trigger
    """CREATE TRIGGER IF NOT EXISTS update_brands_timestamp AFTER UPDATE ON brands
    WHEN NEW.updated_at = OLD.updated_at BEGIN
        UPDATE brands SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END""",

    # Update schema version
    "INSERT OR REPLACE INTO schema_version (version) VALUES (8)",
]


def _migrate_v7_to_v8(conn):
    """Upgrade schema from v7 to v8 — Parts Catalog overhaul.

    Adds brands table, part_suppliers table, part_variants table,
    and 10 new columns on parts.

    Order matters:
    1. Create new tables (brands must exist before parts.brand_id FK)
    2. ALTER TABLE parts to add new columns (must exist before indexes)
    3. Create indexes, triggers, and update schema version
    """
    # 1. Create new tables only (not indexes yet — columns don't exist)
    for stmt in _MIGRATION_V8_STATEMENTS:
        # Skip indexes on parts columns that don't exist yet
        if stmt.strip().startswith("CREATE INDEX") and "parts(" in stmt:
            continue
        conn.execute(stmt)

    # 2. ALTER TABLE for each new column — wrapped individually so
    #    already-existing columns don't block the rest
    for stmt in _MIGRATION_V8_ALTER_STATEMENTS:
        try:
            conn.execute(stmt)
        except Exception:
            pass  # Column may already exist

    # 3. Now create the indexes on the newly-added parts columns
    for stmt in _MIGRATION_V8_STATEMENTS:
        if stmt.strip().startswith("CREATE INDEX") and "parts(" in stmt:
            conn.execute(stmt)


def _migrate_v8_to_v9(conn):
    """Upgrade schema from v8 to v9 — type_style on part_variants.

    Rebuilds part_variants table to add type_style column and change
    the unique constraint from UNIQUE(part_id, color_finish) to
    UNIQUE(part_id, type_style, color_finish).

    Also migrates color_options/type_style JSON from parts into
    variant rows as a cross-product.
    """
    import json as _json

    # Temporarily disable foreign keys for the table rebuild
    conn.execute("PRAGMA foreign_keys = OFF")

    # 1. Rename old table
    conn.execute("ALTER TABLE part_variants RENAME TO _part_variants_old")

    # 2. Create new table with type_style column and new unique constraint
    conn.execute("""
        CREATE TABLE part_variants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_id INTEGER NOT NULL,
            type_style TEXT NOT NULL DEFAULT '',
            color_finish TEXT NOT NULL,
            brand_part_number TEXT DEFAULT '',
            image_path TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE,
            UNIQUE(part_id, type_style, color_finish)
        )
    """)

    # 3. Copy existing variants with type_style = ''
    conn.execute("""
        INSERT INTO part_variants
            (id, part_id, type_style, color_finish, brand_part_number,
             image_path, notes, created_at)
        SELECT id, part_id, '', color_finish, brand_part_number,
               image_path, notes, created_at
        FROM _part_variants_old
    """)

    # 4. Drop old table
    conn.execute("DROP TABLE _part_variants_old")

    # 5. Recreate index
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_part_variants_part "
        "ON part_variants(part_id)"
    )

    # 6. Migrate JSON data from parts.type_style and parts.color_options
    #    into variant rows for parts that have these JSON arrays populated.
    rows = conn.execute("""
        SELECT id, type_style, color_options FROM parts
        WHERE (type_style != '[]' AND type_style != '')
           OR (color_options != '[]' AND color_options != '')
    """).fetchall()

    for row in rows:
        part_id = row["id"]
        try:
            styles = _json.loads(row["type_style"]) if row["type_style"] else []
        except (_json.JSONDecodeError, TypeError):
            styles = []
        try:
            colors = _json.loads(row["color_options"]) if row["color_options"] else []
        except (_json.JSONDecodeError, TypeError):
            colors = []

        if not styles and not colors:
            continue

        # Check if this part already has variants copied from step 3
        existing = conn.execute(
            "SELECT COUNT(*) as cnt FROM part_variants WHERE part_id = ?",
            (part_id,)
        ).fetchone()

        if existing["cnt"] > 0:
            # Part already has variants — if exactly one style, assign it
            if len(styles) == 1:
                conn.execute("""
                    UPDATE part_variants SET type_style = ?
                    WHERE part_id = ? AND type_style = ''
                """, (styles[0], part_id))
        else:
            # No existing variants — create from cross-product
            if styles and colors:
                for style in styles:
                    for color in colors:
                        try:
                            conn.execute("""
                                INSERT OR IGNORE INTO part_variants
                                    (part_id, type_style, color_finish)
                                VALUES (?, ?, ?)
                            """, (part_id, style, color))
                        except Exception:
                            pass
            elif styles:
                for style in styles:
                    try:
                        conn.execute("""
                            INSERT OR IGNORE INTO part_variants
                                (part_id, type_style, color_finish)
                            VALUES (?, ?, '')
                        """, (part_id, style))
                    except Exception:
                        pass
            elif colors:
                for color in colors:
                    try:
                        conn.execute("""
                            INSERT OR IGNORE INTO part_variants
                                (part_id, type_style, color_finish)
                            VALUES (?, '', ?)
                        """, (part_id, color))
                    except Exception:
                        pass

    # Re-enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")

    # 7. Update schema version
    conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (9)")


def _migrate_v9_to_v10(conn):
    """v9 → v10: Billing cycles, zero labor rates, part deprecation."""
    stmts = [
        # Zero out unused rate_per_hour column (keep column for backward compat)
        "UPDATE labor_entries SET rate_per_hour = 0",

        # Parts: soft-delete deprecation columns
        "ALTER TABLE parts ADD COLUMN deprecation_status TEXT DEFAULT NULL",
        "ALTER TABLE parts ADD COLUMN deprecation_started_at TIMESTAMP",
        "CREATE INDEX IF NOT EXISTS idx_parts_deprecation ON parts(deprecation_status)",

        # Billing cycles table
        """CREATE TABLE IF NOT EXISTS billing_cycles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            cycle_type TEXT NOT NULL DEFAULT 'monthly'
                CHECK (cycle_type IN ('weekly', 'biweekly', 'monthly', 'quarterly')),
            billing_day INTEGER NOT NULL DEFAULT 1,
            next_billing_date TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
        )""",

        # Billing periods table
        """CREATE TABLE IF NOT EXISTS billing_periods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            billing_cycle_id INTEGER NOT NULL,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'closed')),
            total_parts_cost REAL NOT NULL DEFAULT 0.0,
            total_hours REAL NOT NULL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (billing_cycle_id) REFERENCES billing_cycles(id) ON DELETE CASCADE
        )""",

        # Indexes
        "CREATE INDEX IF NOT EXISTS idx_billing_cycles_job ON billing_cycles(job_id)",
        "CREATE INDEX IF NOT EXISTS idx_billing_periods_cycle ON billing_periods(billing_cycle_id)",
        "CREATE INDEX IF NOT EXISTS idx_billing_periods_status ON billing_periods(status)",

        # Inventory audits table
        """CREATE TABLE IF NOT EXISTS inventory_audits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            audit_type TEXT NOT NULL DEFAULT 'warehouse'
                CHECK (audit_type IN ('warehouse', 'truck', 'job')),
            target_id INTEGER,
            part_id INTEGER NOT NULL,
            expected_quantity INTEGER NOT NULL DEFAULT 0,
            actual_quantity INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'confirmed'
                CHECK (status IN ('confirmed', 'discrepancy', 'skipped')),
            audited_by INTEGER,
            audited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE,
            FOREIGN KEY (audited_by) REFERENCES users(id) ON DELETE SET NULL
        )""",
        "CREATE INDEX IF NOT EXISTS idx_audits_type ON inventory_audits(audit_type)",
        "CREATE INDEX IF NOT EXISTS idx_audits_part ON inventory_audits(part_id)",
        "CREATE INDEX IF NOT EXISTS idx_audits_at ON inventory_audits(audited_at)",

        # Truck inventory: min/max quantities
        "ALTER TABLE truck_inventory ADD COLUMN min_quantity INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE truck_inventory ADD COLUMN max_quantity INTEGER NOT NULL DEFAULT 0",

        # Transfers: link to parts lists and jobs
        "ALTER TABLE truck_transfers ADD COLUMN parts_list_id INTEGER",
        "ALTER TABLE truck_transfers ADD COLUMN job_id INTEGER",
        "CREATE INDEX IF NOT EXISTS idx_transfers_list ON truck_transfers(parts_list_id)",
        "CREATE INDEX IF NOT EXISTS idx_transfers_job ON truck_transfers(job_id)",

        # AI order suggestions
        """CREATE TABLE IF NOT EXISTS order_suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger_part_id INTEGER NOT NULL,
            suggested_part_id INTEGER NOT NULL,
            score REAL NOT NULL DEFAULT 0.0,
            source TEXT NOT NULL DEFAULT 'co_occurrence',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (trigger_part_id) REFERENCES parts(id) ON DELETE CASCADE,
            FOREIGN KEY (suggested_part_id) REFERENCES parts(id) ON DELETE CASCADE,
            UNIQUE(trigger_part_id, suggested_part_id)
        )""",
        """CREATE TABLE IF NOT EXISTS order_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_id_a INTEGER NOT NULL,
            part_id_b INTEGER NOT NULL,
            co_occurrence_count INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (part_id_a) REFERENCES parts(id) ON DELETE CASCADE,
            FOREIGN KEY (part_id_b) REFERENCES parts(id) ON DELETE CASCADE,
            UNIQUE(part_id_a, part_id_b)
        )""",
        "CREATE INDEX IF NOT EXISTS idx_suggestions_trigger ON order_suggestions(trigger_part_id)",
        "CREATE INDEX IF NOT EXISTS idx_patterns_a ON order_patterns(part_id_a)",

        # Notifications: navigation targets
        "ALTER TABLE notifications ADD COLUMN target_tab TEXT DEFAULT ''",
        "ALTER TABLE notifications ADD COLUMN target_data TEXT DEFAULT ''",

        # Update schema version
        "INSERT OR REPLACE INTO schema_version (version) VALUES (10)",
    ]
    for stmt in stmts:
        conn.execute(stmt)


def _migrate_v10_to_v11(conn):
    """v10 → v11: Bill out rate on jobs + BRO snapshot on labor entries."""
    stmts = [
        # Jobs: bill out rate — text category code (e.g. 'C', 'T&M', 'SERVICE')
        "ALTER TABLE jobs ADD COLUMN bill_out_rate TEXT NOT NULL DEFAULT ''",

        # Labor entries: BRO snapshot — captures the job's BRO at time of entry
        "ALTER TABLE labor_entries ADD COLUMN bill_out_rate TEXT NOT NULL DEFAULT ''",

        # Update schema version
        "INSERT OR REPLACE INTO schema_version (version) VALUES (11)",
    ]
    for stmt in stmts:
        conn.execute(stmt)

    # Backfill existing labor entries with their job's current BRO
    conn.execute("""
        UPDATE labor_entries SET bill_out_rate = (
            SELECT COALESCE(j.bill_out_rate, '')
            FROM jobs j WHERE j.id = labor_entries.job_id
        ) WHERE bill_out_rate = ''
    """)


def _migrate_v11_to_v12(conn):
    """v11 → v12: Supply chain supplier tracking, activity log, job updates."""
    stmts = [
        # ── Supplier tracking: new columns on existing tables ──
        "ALTER TABLE truck_transfers ADD COLUMN source_order_id INTEGER",
        "ALTER TABLE truck_transfers ADD COLUMN supplier_id INTEGER",
        "ALTER TABLE consumption_log ADD COLUMN supplier_id INTEGER",
        "ALTER TABLE consumption_log ADD COLUMN source_order_id INTEGER",
        "ALTER TABLE job_parts ADD COLUMN supplier_id INTEGER",
        "ALTER TABLE job_parts ADD COLUMN source_order_id INTEGER",
        "ALTER TABLE receive_log ADD COLUMN supplier_id INTEGER",

        # ── New indexes for supplier tracking ──
        "CREATE INDEX IF NOT EXISTS idx_transfers_supplier ON truck_transfers(supplier_id)",
        "CREATE INDEX IF NOT EXISTS idx_transfers_source_order ON truck_transfers(source_order_id)",
        "CREATE INDEX IF NOT EXISTS idx_consumption_supplier ON consumption_log(supplier_id)",
        "CREATE INDEX IF NOT EXISTS idx_consumption_source_order ON consumption_log(source_order_id)",
        "CREATE INDEX IF NOT EXISTS idx_job_parts_supplier ON job_parts(supplier_id)",
        "CREATE INDEX IF NOT EXISTS idx_receive_log_supplier ON receive_log(supplier_id)",

        # ── Activity log table ──
        """CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id INTEGER,
            entity_label TEXT DEFAULT '',
            details TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )""",
        "CREATE INDEX IF NOT EXISTS idx_activity_user ON activity_log(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_activity_entity ON activity_log(entity_type, entity_id)",
        "CREATE INDEX IF NOT EXISTS idx_activity_action ON activity_log(action)",
        "CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_log(created_at)",

        # ── Job updates table (team communication) ──
        """CREATE TABLE IF NOT EXISTS job_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            update_type TEXT NOT NULL DEFAULT 'comment'
                CHECK (update_type IN ('comment', 'status_change',
                                       'assignment', 'milestone')),
            is_pinned INTEGER NOT NULL DEFAULT 0,
            photos TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )""",
        "CREATE INDEX IF NOT EXISTS idx_job_updates_job ON job_updates(job_id)",
        "CREATE INDEX IF NOT EXISTS idx_job_updates_user ON job_updates(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_job_updates_created ON job_updates(created_at)",

        # ── Backfill supplier_id on receive_log from PO chain ──
        """UPDATE receive_log SET supplier_id = (
            SELECT po.supplier_id
            FROM purchase_order_items poi
            JOIN purchase_orders po ON poi.order_id = po.id
            WHERE poi.id = receive_log.order_item_id
        ) WHERE supplier_id IS NULL""",

        # Update schema version
        "INSERT OR REPLACE INTO schema_version (version) VALUES (12)",
    ]
    for stmt in stmts:
        try:
            conn.execute(stmt)
        except Exception:
            pass  # Column/table may already exist


def _ensure_required_columns(conn):
    """Safety net: ensure all required columns exist on every table.

    Some ALTER TABLE statements in earlier migrations may have silently
    failed (wrapped in try/except).  This function checks the actual
    table schemas and adds any missing columns.
    """
    # (table, column, definition) — added via ALTER if missing
    _REQUIRED_COLUMNS = [
        # Parts table — v8 columns
        ("parts", "part_type", "TEXT NOT NULL DEFAULT 'general'"),
        ("parts", "brand_id", "INTEGER"),
        ("parts", "brand_part_number", "TEXT DEFAULT ''"),
        ("parts", "local_part_number", "TEXT DEFAULT ''"),
        ("parts", "image_path", "TEXT DEFAULT ''"),
        ("parts", "subcategory", "TEXT DEFAULT ''"),
        ("parts", "color_options", "TEXT DEFAULT '[]'"),
        ("parts", "type_style", "TEXT DEFAULT '[]'"),
        ("parts", "has_qr_tag", "INTEGER NOT NULL DEFAULT 0"),
        ("parts", "name", "TEXT DEFAULT ''"),
        ("parts", "max_quantity", "INTEGER DEFAULT 0"),
        ("parts", "pdfs", "TEXT DEFAULT '[]'"),
        # Parts — v10 deprecation
        ("parts", "deprecation_status", "TEXT DEFAULT NULL"),
        ("parts", "deprecation_started_at", "TIMESTAMP"),
        # Jobs — v11
        ("jobs", "bill_out_rate", "TEXT NOT NULL DEFAULT ''"),
        # Suppliers — v7
        ("suppliers", "is_supply_house", "INTEGER NOT NULL DEFAULT 0"),
        ("suppliers", "operating_hours", "TEXT"),
        # Truck inventory — v10
        ("truck_inventory", "min_quantity", "INTEGER NOT NULL DEFAULT 0"),
        ("truck_inventory", "max_quantity", "INTEGER NOT NULL DEFAULT 0"),
        # Notifications — v10
        ("notifications", "target_tab", "TEXT DEFAULT ''"),
        ("notifications", "target_data", "TEXT DEFAULT ''"),
        # Truck transfers — v10
        ("truck_transfers", "parts_list_id", "INTEGER"),
        ("truck_transfers", "job_id", "INTEGER"),
        # Labor entries — v11 BRO snapshot
        ("labor_entries", "bill_out_rate", "TEXT NOT NULL DEFAULT ''"),
        # Truck transfers — v12 supplier tracking
        ("truck_transfers", "source_order_id", "INTEGER"),
        ("truck_transfers", "supplier_id", "INTEGER"),
        # Consumption log — v12 supplier tracking
        ("consumption_log", "supplier_id", "INTEGER"),
        ("consumption_log", "source_order_id", "INTEGER"),
        # Job parts — v12 supplier tracking
        ("job_parts", "supplier_id", "INTEGER"),
        ("job_parts", "source_order_id", "INTEGER"),
        # Receive log — v12 denormalized supplier
        ("receive_log", "supplier_id", "INTEGER"),
    ]

    for table, column, definition in _REQUIRED_COLUMNS:
        # Check if column exists using PRAGMA
        existing = {
            row["name"]
            for row in conn.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()
        }
        if column not in existing:
            try:
                conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
                )
            except Exception:
                pass  # Table might not exist yet (shouldn't happen)


def initialize_database(db_connection):
    """Create all tables, indexes, triggers, and seed data.

    On a fresh database, creates the full v11 schema directly.
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
            if version < 7:
                _migrate_v6_to_v7(conn)
            if version < 8:
                _migrate_v7_to_v8(conn)
            if version < 9:
                _migrate_v8_to_v9(conn)
            if version < 10:
                _migrate_v9_to_v10(conn)
            if version < 11:
                _migrate_v10_to_v11(conn)
            if version < 12:
                _migrate_v11_to_v12(conn)

        # Ensure all required columns exist (safety net for edge-case
        # migrations that may have silently failed on ALTER TABLE)
        _ensure_required_columns(conn)

        # Rename legacy system hats to new names (idempotent)
        _rename_legacy_hats(conn)

        # Always refresh system hats to latest permissions
        _refresh_system_hat_permissions(conn)
