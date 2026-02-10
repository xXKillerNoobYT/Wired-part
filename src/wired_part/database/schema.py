"""Database schema definition and initialization."""

SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- Categories table
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Parts table (main inventory)
CREATE TABLE IF NOT EXISTS parts (
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
);

-- Jobs table
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_number TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    customer TEXT,
    address TEXT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'completed', 'on_hold', 'cancelled')),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Junction table: parts assigned to jobs
CREATE TABLE IF NOT EXISTS job_parts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    part_id INTEGER NOT NULL,
    quantity_used INTEGER NOT NULL DEFAULT 1 CHECK (quantity_used > 0),
    unit_cost_at_use REAL,
    notes TEXT,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE RESTRICT,
    UNIQUE(job_id, part_id)
);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_parts_part_number ON parts(part_number);
CREATE INDEX IF NOT EXISTS idx_parts_category ON parts(category_id);
CREATE INDEX IF NOT EXISTS idx_parts_location ON parts(location);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_job_number ON jobs(job_number);
CREATE INDEX IF NOT EXISTS idx_job_parts_job ON job_parts(job_id);
CREATE INDEX IF NOT EXISTS idx_job_parts_part ON job_parts(part_id);

-- Full-text search for parts
CREATE VIRTUAL TABLE IF NOT EXISTS parts_fts USING fts5(
    part_number,
    description,
    location,
    supplier,
    notes,
    content='parts',
    content_rowid='id'
);

-- Triggers: keep FTS in sync
CREATE TRIGGER IF NOT EXISTS parts_fts_insert AFTER INSERT ON parts BEGIN
    INSERT INTO parts_fts(rowid, part_number, description, location, supplier, notes)
    VALUES (new.id, new.part_number, new.description, new.location, new.supplier, new.notes);
END;

CREATE TRIGGER IF NOT EXISTS parts_fts_delete AFTER DELETE ON parts BEGIN
    INSERT INTO parts_fts(parts_fts, rowid, part_number, description, location, supplier, notes)
    VALUES('delete', old.id, old.part_number, old.description, old.location, old.supplier, old.notes);
END;

CREATE TRIGGER IF NOT EXISTS parts_fts_update AFTER UPDATE ON parts BEGIN
    INSERT INTO parts_fts(parts_fts, rowid, part_number, description, location, supplier, notes)
    VALUES('delete', old.id, old.part_number, old.description, old.location, old.supplier, old.notes);
    INSERT INTO parts_fts(rowid, part_number, description, location, supplier, notes)
    VALUES (new.id, new.part_number, new.description, new.location, new.supplier, new.notes);
END;

-- Triggers: auto-update timestamps
CREATE TRIGGER IF NOT EXISTS update_parts_timestamp AFTER UPDATE ON parts BEGIN
    UPDATE parts SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_jobs_timestamp AFTER UPDATE ON jobs BEGIN
    UPDATE jobs SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_categories_timestamp AFTER UPDATE ON categories BEGIN
    UPDATE categories SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Record schema version
INSERT OR IGNORE INTO schema_version (version) VALUES (1);
"""

SEED_CATEGORIES_SQL = """
INSERT OR IGNORE INTO categories (name, description) VALUES
    ('Wire & Cable', 'Electrical wiring, cables, and conductors'),
    ('Conduit & Fittings', 'Conduit, connectors, and fittings'),
    ('Boxes & Enclosures', 'Junction boxes, panels, and enclosures'),
    ('Switches & Outlets', 'Switches, receptacles, and plates'),
    ('Breakers & Fuses', 'Circuit breakers, fuses, and protection devices'),
    ('Lighting', 'Light fixtures, bulbs, and components'),
    ('Connectors & Terminals', 'Wire nuts, terminals, and connectors'),
    ('Tools & Supplies', 'Tape, lubricant, and consumables'),
    ('Motors & Controls', 'Motors, starters, and control equipment'),
    ('Miscellaneous', 'Other electrical parts');
"""


def initialize_database(db_connection):
    """Create all tables, indexes, triggers, and seed data."""
    db_connection.execute_script(SCHEMA_SQL)
    db_connection.execute_script(SEED_CATEGORIES_SQL)
