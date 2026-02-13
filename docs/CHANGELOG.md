# Changelog

All notable changes to Wired-Part are documented here.

---

## [13.0.0] - 2026-02-12

### Added
- **File-based cloud sync** (`sync/sync_manager.py`) — synchronize databases between devices via any shared folder (Google Drive, OneDrive, Dropbox, local network). Each device exports/imports JSON sync files with last-write-wins merge, lock file management, and schema version checking.
- **Config: sync settings** — `SYNC_ENABLED`, `SYNC_FOLDER_PATH`, `SYNC_INTERVAL_MINUTES`, `DEVICE_ID` (auto-generated UUID), `LAST_SYNC_TIMESTAMP`
- **Notebook attachments** — new `notebook_attachments` table for file attachments per notebook page. Cascade delete removes attachments when pages are deleted.
- **Rich text editor: hyperlinks** — Insert Link button with URL + display text dialog
- **Rich text editor: image embedding** — Insert Image button with file picker and auto-scale to 600px max width
- **Notebook widget: attachment panel** — add/remove/open file attachments per page
- **Global search dialog (Ctrl+K)** — spotlight-style floating search across jobs, parts, users, orders, and notebook pages with category-colored results
- **Toast notifications** (`ToastManager`) — non-intrusive slide-in alerts with severity coloring (info/success/warning/error) and auto-dismiss
- **Team-aware labor filtering** — workers only see their own labor entries unless granted `labor_view_all` permission
- **Enhanced status bar** — clock-in status with job name and time, search hint (Ctrl+K), notification count
- 35 new tests for sync (23) and attachments (12)

### Schema Changes
| Table | Change |
|-------|--------|
| `notebook_attachments` | New table (page_id, filename, file_path, file_type, file_size) |
| Schema version | 12 -> 13 |

### Tests
- 706 tests total (up from 671)

---

## [12.1.0] - 2026-02-12

### Added
- **Cross-platform GPS module** (`utils/gps.py`) — unified GPS interface for Windows (PowerShell), macOS (CoreLocation), and Linux (GeoClue2) with graceful fallback to manual entry
- **Platform utilities** (`utils/platform.py`) — font family detection, primary font name, and platform identification
- **Cross-platform font stack** — QSS uses `{{FONT_FAMILY}}` placeholder, resolved at runtime to Segoe UI (Windows), .AppleSystemUIFont (macOS), or Ubuntu/Noto Sans (Linux)
- 36 new tests for GPS module and platform utilities

### Changed
- `clock_dialog.py` — replaced inline PowerShell GPS with shared `fetch_gps()` from `utils/gps.py`
- `job_dialog.py` — replaced inline PowerShell GPS with shared `fetch_gps()` from `utils/gps.py`
- `app.py` — uses `get_primary_font_name()` for QFont and injects platform font into QSS
- Converted all dialog-level `setFixedSize()` to `setMinimumSize()` for DPI flexibility (login, category, job assign, truck dialogs)
- QSS themes use `{{FONT_FAMILY}}` placeholder instead of hardcoded "Segoe UI"

### Platform Support
| Platform | GPS Auto-Detect | Font | Status |
|----------|----------------|------|--------|
| Windows | PowerShell Location API | Segoe UI | Full support |
| macOS | CoreLocation (optional pyobjc) | .AppleSystemUIFont | GPS needs pyobjc |
| Linux | GeoClue2 (where-am-i) | Ubuntu/Noto Sans | GPS needs geoclue-2.0 |

---

## [12.0.0] - 2026-02-12

### Added
- **Supply chain supplier tracking** — `supplier_id` propagated through every stage: `receive_log` -> `truck_transfers` -> `consumption_log` -> `job_parts`
- **One-supplier-per-part-per-job enforcement** — prevents mixing suppliers for the same part on a single job
- **Activity log** (`activity_log` table) — audit trail for all user actions with filtering by entity, user, and date range
- **Job updates/comments** (`job_updates` table) — team communication system with pinning, update types (comment, status_change, assignment, milestone)
- **Global search** (`search_all`) — search across jobs, parts, users, orders, and notebook pages with ranked results
- **Supplier chain audit** (`get_part_supplier_chain`) — complete movement history showing supplier at each stage
- **Smart return suggestions** (`get_suggested_return_supplier`) — auto-suggests correct supplier for returns based on job context
- **Auto-detect supplier on transfers** — `create_transfer()` looks up supplier from receive history
- **Office page** — new UI page for office workflows
- **Part types and variants** — general vs specific parts with brand/variant support
- 13 new database indexes for supplier tracking and activity log performance
- Schema migration v11 -> v12 with automatic backfill of existing records

### Changed
- `receive_order_items()` now captures and propagates `supplier_id` to all allocation targets
- `consume_from_truck()` looks up supplier from most recent truck transfer
- `create_transfer()` auto-detects supplier from `receive_log` when not explicitly set
- Settings page expanded with labor, notebook, and general configuration sections
- Parts catalog enhanced with type filtering and variant management

### Schema Changes
| Table | Change |
|-------|--------|
| `truck_transfers` | +`source_order_id`, +`supplier_id` |
| `job_parts` | +`supplier_id`, +`source_order_id` |
| `consumption_log` | +`supplier_id`, +`source_order_id` |
| `receive_log` | +`supplier_id` |
| `activity_log` | New table |
| `job_updates` | New table |

### Tests
- 635 tests total (up from 587)
- New: supply chain E2E tracking (21 tests)
- New: activity log CRUD (12 tests)
- New: global search (13 tests)

---

## [11.0.0] - 2026-02-10

### Added
- Deprecation pipeline with `job_quantity` check
- BRO (Bill Out Rate) snapshot on labor entries
- BRO deletion protection for active jobs
- Job reactivation (completed/cancelled -> active)
- Quick time filters on Labor Overview and Office pages
- QR code generation for parts

### Fixed
- Date filtering using SQLite `DATE()` function
- GPS escape code stripping for VS Code terminal
- Clock-in photos made optional (clock-out still required)
- QThread lifecycle management on dialog close
- KeyError 'category' in labor_log_dialog.py

---

## [10.0.0] - 2026-02-09

### Added
- Billing cycle settings and truck inventory management
- Supplier management with supply house designation
- LLM/Agent settings and configuration
- Labor tracking with GPS geofencing
- Notebook system per job with sections
- Purchase orders and returns workflow
- Hat-based permission system (7 roles, 48+ permissions)
