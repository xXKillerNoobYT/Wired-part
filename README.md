# Wired-Part

Electrician's Parts Manager — desktop inventory, job tracking, and order management application with AI assistant.

## Features

- **Inventory Management** — Add, edit, delete, and search parts with full-text search. Track quantities, locations, categories, costs, and suppliers. Low-stock alerts when parts fall below minimum thresholds.
- **Job Tracking** — Create and manage electrical jobs/projects. Assign parts to jobs with automatic stock deduction and cost snapshots. Track job status, labor hours, and geolocation clock-in/out.
- **Truck Management** — Assign trucks to users, manage on-truck inventory, process transfers between warehouse and trucks with checklist workflows.
- **Labor & Timesheets** — Clock in/out with GPS radius verification, attach photos, log sub-task categories, generate work reports with LLM narrative summaries.
- **OneNote-Style Notes** — Hierarchical job notebooks with sections and pages, rich text, photo attachments, and cross-job search.
- **Orders & Returns** — Full purchase order lifecycle: create orders (manual or from parts lists), submit to suppliers, receive with smart allocation (warehouse/truck/job), and manage return authorizations. Includes supply house quick-order, intelligent supplier splitting, email draft generation, and wrong-part flagging.
- **Supply House Orders** — Quick pickup orders for local supply houses with phone script generation, pick list creation, and one-click PO creation.
- **Intelligent Supplier Splitting** — Automatically split a parts list across multiple suppliers based on part preferences. Creates separate draft POs per supplier.
- **Email Draft Generation** — Generate and open email drafts for purchase orders with full line item details, sent via your default email client.
- **Shortfall Auto-Detection** — Check warehouse stock against parts list requirements. Detects shortfalls and offers to auto-generate purchase orders for missing items.
- **Parts Lists** — Reusable templates and job-specific lists for organizing materials needed per project. Includes shortfall detection.
- **Suppliers** — Manage supplier contacts, preference scores, delivery schedules, supply house designation, operating hours, and order history.
- **Hat-Based Permissions** — Role system with 7 hats (Admin, IT, Office, Job Manager, Foreman, Worker, Grunt) controlling access to 47+ permissions across all features.
- **AI Assistant** — Natural language queries powered by a local LLM via LM Studio. Background agents for inventory audits, admin assistance, and reminders. Fully offline — no data leaves your machine.
- **Import/Export** — Bulk import parts from CSV or Excel files. Export inventory and job data for reporting or backup.
- **Billing & Reports** — Generate billing reports with materials, labor, markup, and tax. Export to PDF/CSV.

## Tab Structure

| Tab | Description |
|-----|------------|
| **Dashboard** | Personal overview: summary cards, active jobs, truck status, clock-in/out, notifications, low stock alerts, pending orders, open returns |
| **Parts Catalog** | Browse, search, add/edit parts with categories, costs, and supplier info. Parts list manager with shortfall detection. |
| **Job Tracking** | Jobs, Trucks, Labor Overview (sub-tabs) |
| **Warehouse & Trucks** | Warehouse inventory, Trucks Inventory, Jobs Inventory (sub-tabs) |
| **Orders & Returns** | Pending Orders, Incoming/Receive, Returns & Pickups, Order History (sub-tabs) |
| **Agent** | AI assistant chat, background agent controls |
| **Settings** | User management, hat/permissions, categories, suppliers (with supply house support), LLM config, theme, labor settings |

## Quick Start

### Requirements

- Python 3.10+
- [LM Studio](https://lmstudio.ai/) (optional, for AI assistant)

### Installation

```bash
# Clone the repo
git clone https://github.com/WeirdTooLLC/Wired-part.git
cd Wired-part

# Install dependencies
pip install -e .

# Copy environment config
cp .env.example .env
```

### Run

```bash
python -m wired_part
```

Or use the installed command:

```bash
wired-part
```

### LM Studio Setup (Optional)

1. Download and install [LM Studio](https://lmstudio.ai/)
2. Load a model (7B+ parameters recommended)
3. Start the local server (default: `http://localhost:1234`)
4. The Agent tab in Wired-Part will auto-connect

## Command Line Tools

Standalone scripts in `execution/` for automation:

```bash
# Backup the database
python execution/db_backup.py

# Import parts from CSV
python execution/import_csv.py parts.csv
python execution/import_csv.py parts.csv --update  # update existing

# Export data to CSV
python execution/export_csv.py parts output.csv
python execution/export_csv.py jobs output.csv

# Query inventory via LLM (requires LM Studio)
python execution/llm_query.py
```

## Project Structure

```
src/wired_part/       # Main application package
  database/           # SQLite connection, schema (v7), models, repository
  ui/                 # PySide6 interface (pages, dialogs, styles)
    pages/            # Tab pages (dashboard, catalog, jobs, warehouse, orders, etc.)
    dialogs/          # Modal dialogs (part, job, order, return, supply house, etc.)
  agent/              # LM Studio LLM integration (tools, handler, background)
  io/                 # CSV and Excel import/export
  utils/              # Formatters, constants, geo utilities
directives/           # Standard operating procedures
execution/            # Standalone automation scripts
data/                 # SQLite database (auto-created on first run)
tests/                # Test suite (215+ tests)
```

## Database Schema

Version 7 with 27 tables:

| Area | Tables |
|------|--------|
| **Core** | categories, parts, parts_fts |
| **Jobs** | jobs, job_parts, job_assignments |
| **Trucks** | trucks, truck_inventory, truck_transfers |
| **Users** | users, hats, user_hats |
| **Labor** | labor_entries, job_locations |
| **Notebooks** | job_notebooks, notebook_sections, notebook_pages |
| **Suppliers** | suppliers (with supply house support) |
| **Parts Lists** | parts_lists, parts_list_items |
| **Orders** | purchase_orders, purchase_order_items, receive_log |
| **Returns** | return_authorizations, return_authorization_items |
| **System** | notifications, consumption_log |

## Configuration

Edit `.env` to customize:

```env
LM_STUDIO_BASE_URL=http://localhost:1234/v1
DATABASE_PATH=data/wired_part.db
APP_THEME=dark   # or: light
ORDER_NUMBER_PREFIX=PO
RA_NUMBER_PREFIX=RA
```

Runtime settings are stored in `data/settings.json` and can be updated through the Settings tab.

## Testing

```bash
# Run full test suite
python -m pytest tests/ -v

# Run specific test areas
python -m pytest tests/test_database/test_orders.py -v
python -m pytest tests/test_database/test_returns.py -v
python -m pytest tests/test_database/test_shortfall.py -v
```

## Licensing

This software is licensed under the **Functional Source License (FSL) v1.1** (see [LICENSE.md](LICENSE.md)).

You may use, modify, and distribute the code subject to FSL terms. The FSL permits all non-competing, personal, and internal use. Each version automatically converts to the **Apache License 2.0** two years after release.

If you intend to **charge money** for this software (or a derivative/modified version), including via one-time sales, subscriptions, SaaS hosting, or bundling into a paid product/service, you must obtain a **separate commercial license** from the copyright holder.

**Commercial License Terms:**
- 10% of gross revenue from sales/subscriptions related to this software (or derivatives)
- Paid quarterly, with reasonable reporting/audit rights
- Contact: [bob@weirdtoocompany.com](mailto:bob@weirdtoocompany.com)
- See [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md) for full terms

Copyright 2026 [WeirdToo LLC](https://github.com/WeirdTooLLC)
