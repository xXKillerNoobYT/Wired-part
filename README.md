# Wired-Part

Electrician's Parts Manager — desktop inventory and job tracking application with AI assistant.

## Features

- **Inventory Management** — Add, edit, delete, and search parts with full-text search. Track quantities, locations, categories, costs, and suppliers. Low-stock alerts when parts fall below minimum thresholds.
- **Job Tracking** — Create and manage electrical jobs/projects. Assign parts to jobs with automatic stock deduction and cost snapshots. Track job status (active, completed, on hold, cancelled).
- **AI Assistant** — Natural language queries powered by a local LLM via LM Studio. Ask questions like "What parts are running low?" or "Show me parts for the Smith job." Fully offline — no data leaves your machine.
- **Import/Export** — Bulk import parts from CSV or Excel files. Export inventory and job data for reporting or backup.
- **Dark/Light Themes** — Professional UI with configurable themes.

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
  database/           # SQLite connection, schema, models, repository
  ui/                 # PySide6 interface (pages, dialogs, styles)
  agent/              # LM Studio LLM integration
  io/                 # CSV and Excel import/export
  utils/              # Formatters, constants
directives/           # Standard operating procedures
execution/            # Standalone automation scripts
data/                 # SQLite database (auto-created on first run)
```

## Configuration

Edit `.env` to customize:

```env
LM_STUDIO_BASE_URL=http://localhost:1234/v1
DATABASE_PATH=data/wired_part.db
APP_THEME=dark   # or: light
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
