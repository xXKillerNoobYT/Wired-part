# Architecture Overview

## System Design

Wired-Part is a **desktop-first** inventory and job management application built for electrical contractors. It runs 100% locally on each device with no server dependency.

```
┌──────────────────────────────────────────┐
│              PySide6 UI Layer            │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌────────┐ │
│  │ Pages│ │Dialog│ │Widget│ │ Styles │ │
│  └──┬───┘ └──┬───┘ └──┬───┘ └────────┘ │
├─────┼────────┼────────┼─────────────────┤
│     └────────┴────────┘                 │
│           Repository Layer              │
│    (Single class, ~180 methods)         │
│         Raw SQL queries                 │
├─────────────────────────────────────────┤
│         DatabaseConnection              │
│      SQLite via Python sqlite3          │
├─────────────────────────────────────────┤
│           Schema + Migrations           │
│    v1 -> v2 -> ... -> v12               │
└─────────────────────────────────────────┘
```

## Key Principles

1. **100% Local** — No web server, no API, no cloud dependency. Each device is fully standalone.
2. **Repository Pattern** — All database access goes through a single `Repository` class with explicit SQL.
3. **Schema Migrations** — Each version has migration statements + a migration function. Forward-only.
4. **Hat-Based Permissions** — 7 predefined roles with 48+ granular permission keys.
5. **Dataclass Models** — All entities are Python dataclasses with optional joined fields for SQL convenience.

## Directory Structure

```
src/wired_part/
  config.py              # Config class (env + settings.json)
  database/
    connection.py        # DatabaseConnection (SQLite wrapper)
    schema.py            # CREATE TABLE + migrations
    models.py            # Dataclass models
    repository.py        # Repository class (~180 methods)
  ui/
    main_window.py       # QMainWindow with tab navigation
    login_dialog.py      # PIN-based login
    dialogs/             # Modal dialogs (clock, consume, job, etc.)
    pages/               # Tab pages (parts, jobs, labor, etc.)
    widgets/             # Reusable widgets (notebook, rich text)
    styles/              # QSS themes (dark.qss, light.qss)
  utils/
    constants.py         # App-wide constants, permissions
    formatters.py        # Currency/quantity formatting
tests/
  test_config.py
  test_database/         # Unit tests for repository
  test_e2e/              # End-to-end workflow tests
  test_io/               # CSV import/export tests
  test_utils/            # Formatter + utility tests
```

## Data Flow: Supply Chain

```
Supplier -> PurchaseOrder -> receive_order_items()
                                    |
                    ┌───────────────┼───────────────┐
                    v               v               v
               Warehouse        Truck           Job (direct)
               (parts.qty)   (transfer)      (job_parts)
                    |               |
                    v               v
              Manual Transfer   receive_transfer()
              create_transfer()     |
                    |               v
                    └──> truck_inventory
                              |
                              v
                     consume_from_truck()
                              |
                              v
                         job_parts
                              |
                              v
                    Return Authorization
                    (suggested supplier)
```

**Supplier tracking**: `supplier_id` is propagated at every stage so returns can be routed to the correct supplier.

**Enforcement**: A given part on a given job must always come from the same supplier.

## Authentication

- PIN-based login (4-digit hash)
- Hat assignment determines permissions
- Admin and IT hats have full access
- Locked hats (Admin, IT, Office) cannot be deleted or have permissions modified

## Database

- SQLite with WAL mode
- Schema versioned (currently v12, 29 tables)
- Migrations are additive (ALTER TABLE, new tables)
- Backfill SQL runs during migration for existing data
