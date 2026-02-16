# Copilot Instructions — Wired-Part

> Electrician's desktop inventory, job tracking, and order management app. 100% local, no server. See `AGENTS.md` for the 3-layer architecture (directives → orchestration → execution scripts).

## Architecture at a Glance

```
PySide6 UI (src/wired_part/ui/)  →  Repository (single class, ~180 methods, raw SQL)
                                          →  DatabaseConnection (sqlite3 + context manager)
                                                →  Schema v12, forward-only migrations
```

- **All DB access** goes through `database/repository.py`. Never write raw SQL outside this file.
- **Models** are Python `@dataclass` classes in `database/models.py` with optional "joined" fields (e.g. `category_name`) populated by SELECT queries, not by ORM.
- **Schema migrations** are incremental functions in `database/schema.py` (`_migrate_vN_to_vN+1`). Bump `SCHEMA_VERSION` and add a new migration function — never edit existing migrations.
- **Config** loads `.env` first, then `data/settings.json` overrides at runtime. Use `Config.update_*()` class methods to persist runtime changes.

## Project Layout

| Path | Purpose |
|------|---------|
| `src/wired_part/database/` | `connection.py`, `schema.py`, `models.py`, `repository.py` |
| `src/wired_part/ui/pages/` | One file per tab page (e.g. `parts_catalog_page.py`, `jobs_page.py`) |
| `src/wired_part/ui/dialogs/` | Modal dialogs (e.g. `part_dialog.py`, `order_dialog.py`) |
| `src/wired_part/agent/` | LM Studio LLM integration — `tools.py` (OpenAI function defs), `handler.py` (dispatch), `client.py` |
| `src/wired_part/utils/constants.py` | Hats, permissions (48+ keys), job statuses, BRO categories |
| `directives/` | SOPs — read these before implementing a feature in that domain |
| `execution/` | Standalone CLI scripts (`db_backup.py`, `import_csv.py`, `export_csv.py`, `llm_query.py`) |

## Build & Run

```bash
pip install -e .              # editable install
python -m wired_part          # launch app (or: wired-part)
python -m pytest tests/ -v    # full test suite (215+ tests)
python -m pytest tests/test_database/test_orders.py -v  # single module
```

## Testing Conventions

- **Fixtures**: `tests/conftest.py` provides `db` (in-memory SQLite via `tmp_path`) and `repo` (initialized `Repository`). E2E tests in `tests/test_e2e/conftest.py` add `admin_user`, `foreman_user`, `parts`, `truck_a`, etc.
- Tests are **pure repository-level** — no Qt/UI mocking. They exercise `Repository` methods against a fresh in-memory DB per test.
- Test files map to features: `test_orders.py`, `test_returns.py`, `test_trucks.py`, `test_shortfall.py`, etc.
- E2E tests validate **multi-step business flows** (warehouse→truck→job→return) with stock quantity assertions at each step.

## Key Patterns

### Repository Method Pattern
```python
# Read: returns model or list
def get_part_by_id(self, part_id: int) -> Optional[Part]:
    rows = self.db.execute("SELECT ... WHERE id = ?", (part_id,))
    return Part(**dict(rows[0])) if rows else None

# Write: uses context manager for auto-commit/rollback
def create_part(self, part: Part) -> int:
    with self.db.get_connection() as conn:
        cursor = conn.execute("INSERT INTO ...", (...))
        return cursor.lastrowid
```

### Supply Chain Data Flow
`Supplier → PurchaseOrder → receive_order_items() → Warehouse/Truck/Job → consume_from_truck() → job_parts → ReturnAuthorization`. The `supplier_id` is propagated at every stage so returns route to the correct supplier.

### Hat-Based Permissions
7 hats defined in `constants.py` → `DEFAULT_HAT_PERMISSIONS` maps each hat to a list of permission keys. Admin & IT get all keys. Check permissions via `repo.user_has_permission(user_id, "orders_create")`. Locked hats (ids 1–3) cannot be deleted or have permissions edited.

### Adding a New Agent Tool
1. Add the function schema dict to `AGENT_TOOLS` in `agent/tools.py`
2. Add a `_method_name` handler in `agent/handler.py` and register it in the `dispatch` dict
3. Agent tools are **read-only** — never mutate data from the LLM path

### Adding a New DB Table / Column
1. Add the `CREATE TABLE` / column to `_SCHEMA_STATEMENTS` in `schema.py`
2. Bump `SCHEMA_VERSION` and write `_migrate_vN_to_vN+1()` with `ALTER TABLE` statements
3. Add a `@dataclass` model in `models.py`
4. Add CRUD methods to `repository.py`
5. Add tests in `tests/test_database/`

## Conventions

- **Formatting**: `format_currency()` from `utils/formatters.py` for all money display.
- **UI**: PySide6 with QSS themes (`ui/styles/dark.qss`, `light.qss`). Font placeholder `{{FONT_FAMILY}}` is replaced at load time per platform.
- **Directives before code**: Read the matching `directives/*.md` SOP before implementing a feature. Update directives with learnings.
- **No ORM**: All SQL is explicit in `repository.py`. Use parameterized queries exclusively.
- **Dataclass defaults**: All model fields have defaults so `Model(**dict(row))` works even if SELECT doesn't return every column.
