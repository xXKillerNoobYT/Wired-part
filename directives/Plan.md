# Comprehensive Breakdown of the Parts Manager Program

This is the most thorough and accurate breakdown I can provide of the **Parts Manager** program, based on all requirements discussed. The program is a **desktop-only, offline-first inventory and job management system tailored for electricians**. It tracks electrical parts through a strict flow (Supplier → Warehouse → Truck → Job), enforces policies like "warehouse-first" and accurate consumption, supports multi-user/multi-truck/multi-job workflows (including multi-year jobs), and uses a **local LLM** for intelligent automation and background administrative tasks.

The system is designed for **small electrician teams** using a shared high-powered desktop (heavy local processing, GPU-optional for LLM). It is fully functional offline, with optional syncing via Google Drive or a local folder.

## 1. Program Overview

| Aspect                  | Details |
|-------------------------|---------|
| **Purpose**             | Comprehensive parts/inventory management for electricians, with full traceability, intelligent ordering, job-focused workflows, and proactive accuracy checks to prevent lost parts. |
| **Target Users**        | Electricians (field users), managers/admins (oversight, ordering, audits). Multi-user on shared desktop. |
| **Core Principles**     | - Offline-first<br>- Warehouse-first policy<br>- Full parts tracking end-to-end<br>- Quick, easy consumption logging<br>- Intelligent but user-overridable automation<br>- Local-only LLM for privacy and speed |
| **Key Differentiators** | - Electrician-specific (wire/outlet grouping, bundles like "outlet + cover plate")<br>- Active jobs/trucks with user assignments<br>- Background LLM agents for hard-to-code admin tasks (audits, inconsistency detection)<br>- Intelligent order splitting with email drafts |

## 2. Architecture & Tech Stack

| Layer                   | Technology Choices | Rationale |
|-------------------------|--------------------|-----------|
| **Frontend/UI**         | Electron (or Tauri for lighter) + React/Vite for desktop app | Cross-platform desktop, mobile-friendly forms for field use |
| **Backend/Logic**       | Node.js (Electron) or Rust (Tauri) + local SQLite | Heavy local processing, simple file-based DB |
| **Database**            | SQLite (local file) with transactions/locking for multi-user | Offline-first, concurrent reads, serialized writes |
| **LLM Integration**     | Local-only: Ollama, LM Studio, or LocalAI (OpenAI-compatible API on localhost) | Desktop-only models (e.g., Llama 3.2 8B–32B), background threading |
| **Agents**              | Based on copilot-orchestration-extension concepts (Planning/Answer/Verification + SQLite tickets) with custom "MCP" tools (simple DB/notification hooks) | Small, focused agents for special tasks |
| **Syncing**             | Google Drive API or watched desktop folder (JSON/SQL dumps) | Optional multi-device backup, eventual consistency |
| **Deployment**          | Single executable installer, local only (no server) | Easy setup for small teams |

## 3. Data Model (High-Level Schema)

Key tables with critical fields (SQLite):

- **Users**: id, username, password_hash, assigned_truck_id, role (admin/electrician)
- **Trucks**: id, name, assigned_user_id (primary), current_location/notes
- **Parts**: id, internal_number (unique), brand_number, supplier_numbers (JSON array per brand), description, images (local paths/URLs per brand), type_group (e.g., "Wire", "Outlet"), cost_mix fields, general_vs_specific flag
- **Suppliers**: id, name, preferences_score (per user/group), delivery_schedule (JSON days/dates), contact_info
- **WarehouseStock**: part_id, quantity, location/bin, non_returnable_flag
- **TruckStock**: truck_id, part_id, quantity
- **Jobs**: id, name, start/end_date, status (active/inactive), assigned_users (many-to-many), assigned_truck_id, timeline_history (JSON logs), preferences (brand/color etc.)
- **PartsLists**: id, job_id (or general template), items (JSON: part_id, quantity, specific overrides), type (general/specific/fast)
- **Orders/Returns**: id, supplier_id, items, status, delivery_date, email_draft_log
- **ConsumptionLogs/AuditLogs**: timestamp, user_id, job_id, part_id, quantity, action (consume/return/transfer)

All movements timestamped and logged for full traceability.

## 4. Core Flow & Policies

Strict flow with automatic tracking:

1. **Supplier → Warehouse**: Incoming orders confirmed, stock added (non-returnable focus).
2. **Warehouse → Truck**: Checklist transfers, warehouse-first policy enforced.
3. **Truck → Job**: Offload/consume parts (quick logging deducts from truck stock).
4. **Returns**: Prefer original supplier, easy restock to warehouse in reverse order. 

Policies:
- Warehouse stock used **first** for all lists/orders.
- Consumption logged **immediately** on jobs to prevent losses.

## 5. Key Features Breakdown

### A. Parts Catalog
- Multiple part numbers (internal/brand/supplier per brand)
- Images per brand variant or warehouse slot
- Easy merging of duplicates (LLM-assisted suggestions)
- Type grouping for mixing/searches
- General vs. Specific parts distinction

### B. Parts Lists
- General templates (reusable, easy add/edit)
- Specific instances created from general or "fast lists"
- Intelligent suggestions (bundles like wire + nuts, based on history)
- Auto-fill job preferences (brand, color, etc.)

### C. Ordering System
- Take any parts list → intelligent split by supplier (preferences, schedule, cost, delivery alignment)
- User-friendly overrides (drag-drop, bulk reassign)
- One-click email drafts per supplier (templated, editable, mailto: launch)

### D. Job & Truck Management
- User-truck assignments ("signed vehicle")
- Active Jobs dashboard (personal priority list, restricted access to inactive)
- Multi-user/multi-job (including multi-year with timelines)
- Quick consumption logging from truck to job

### E. LLM Background Agents
Small, focused agents running periodically/in background:
- **Audit Agent**: Scan for inconsistencies (e.g., stock vs. consumption mismatches) → notify/flag
- **Admin Helper**: Lookups, add new parts/cards, clarify ambiguities via prompts
- **Reminder Agent**: Audit reminders, questions for users
Custom MCP tools: DB query/insert, user notification, ticket creation

Uses repo-style orchestration + local LLM for tasks hard to hard-code.

## 6. User Interface Highlights
- Dashboard: My Truck + My Active Jobs priority view
- Parts search/filter by any number, group, image preview
- Checklist modes for transfers/deliveries
- Editable grids for order splitting
- Progress bars for heavy LLM tasks
- Notifications for agent findings

## 7. Security & Multi-User
- Simple login with roles
- Audit logs per action/user
- DB file locking for concurrency
- All data local/encrypted optional

## 8. Licensing (As Discussed)
Source-available via **Functional Source License (FSL)** with automatic conversion to MIT/Apache after ~2 years. Commercial use requiring charging money needs separate license with **10% revenue share** (contact @WeirdTooLLC).

This breakdown captures every requirement in detail. The program is practical, focused, and powerful for real electrician teams while remaining fully local and private. If anything is missing or needs expansion (e.g., wireframes, sample code, or schema SQL), let me know!


# NEW

# Fully Updated Parts Manager System Plan

This is the **complete, consolidated plan** for the **Parts Manager** — a full **Parts and Job Management Program** tailored for electricians.  
The program has two clearly separated but tightly integrated sides:

- **Parts Side** — Inventory, ordering, stock movement, traceability, warehouse-first policy, intelligent supplier splitting.
- **Job Tracking Side** — Jobs, active job focus, user/truck assignments, labor tracking, work reporting, notes, photos, geolocation clock-in/out, billing.

The app remains **desktop-only, offline-first, multi-user, heavy local processing, local LLM only**.

Below, I separate **Existing Features** (everything we had before this update) from **New/Enhanced Features** (labor photos, task descriptions, geolocation clock-in/out, full work reporting, OneNote-style notes, and clearer parts/job separation).

## Existing Features Recap (Pre-Update)

### Core Architecture
- Electron/Tauri desktop app + SQLite local database
- Local LLM (Ollama/LM Studio) for background agents
- Optional sync via Google Drive or watched folder
- Multi-user with login, roles, truck assignments ("signed vehicle")
- Active jobs priority dashboard (access restricted to active jobs only)
- Full traceability with audit logs

### Parts Side
- Parts catalog with internal/brand/supplier numbers (multiple per brand), images, type groups, general vs. specific, cost mix
- Strict flow: Supplier → Warehouse → Truck → Job (with returns backward)
- Warehouse-first policy, non-returnable focus
- Intelligent ordering: Split parts lists by supplier (preferences, schedule, cost, delivery), user overrides, email drafts
- Easy part merging, bundles ("often together" suggestions)

### Job Tracking Side (Pre-Update)
- Jobs with multi-year timelines, assigned users/trucks, active/inactive status
- Parts lists (general templates, specific instances, fast lists) tied to jobs
- Quick parts consumption logging (deducts from truck stock)
- Billing reports: Materials costs from consumption + markup + tax, PDF export
- Basic labor tracking: Timer/manual entry, hours per job/user/date/sub-task, rates/overtime, integration into billing

### LLM Background Agents
- Audit, admin helper, reminder agents with custom tools
- Inconsistency detection, notifications, tickets

## New & Enhanced Features

### Clear Separation of Parts Side vs. Job Tracking Side
- UI now has **two main tabs/sections** in the dashboard:
  - **Parts Side** — Catalog, warehouse, trucks, ordering, stock views
  - **Job Tracking Side** — Active jobs list, labor logs, work notes, photos, reporting, billing
- Data is shared (e.g., consumption links both sides), but navigation and workflows are distinctly separated for clarity.

### Enhanced Labor Tracking & Timesheets
- **Photos of Work**
  - Users can attach multiple photos directly to any labor entry (date/session)
  - Photos stored locally (file paths in DB), with thumbnails in timesheet view
  - Drag-drop or camera access (Electron webcam integration) for quick on-site shots
  - Photos visible in timesheet, work reports, and billing exports

- **What Was Done (Task Descriptions)**
  - Mandatory or optional rich-text field per labor entry: "Describe work completed"
  - Pre-filled suggestions from LLM (e.g., based on sub-task category or parts consumed that day)
  - Sub-task categories expanded (e.g., Rough-in, Trim-out, Service Call, Testing)

- **Geolocation Clock-In/Out with ½-Mile Radius**
  - Each job has an **address field** (required for activation)
  - Address is geocoded once (using local offline map data or optional one-time online lookup cached forever)
  - Clock-in/out options:
    - Manual (as before)
    - **Auto-detect mode**: When starting timer, app checks current device location (via Electron geolocation API)
    - Only allows clock-in if within **0.5 mile radius** of job address
    - Prompts user if outside radius ("You appear to be off-site — confirm clock-in anyway?")
    - Logs actual GPS coordinates with each entry for audit
    - Works offline after initial address cache (uses last known location if GPS unavailable)

### Full Work Reporting
- New **Work Report** generator (separate from billing, or combinable):
  - Combines:
    - Labor hours & descriptions
    - Photos attached to entries
    - Parts consumed that day/week
    - Notes (see below)
    - Timeline events
  - Date-range selectable (ideal for daily/weekly reports or progress on multi-year jobs)
  - Sections: Summary, Daily Logs, Issues/Noted Problems, Photos Gallery, Parts Used
  - LLM-assisted narrative summary (e.g., "Completed rough-in for kitchen; installed 12 outlets, used 500ft wire")
  - Export PDF/CSV with embedded photos
  - Client-facing version (clean, branded) and internal version (full audit details)

### OneNote-Style Notes System (Job Tracking Side)
- Hierarchical notes per job:
  - **Notebooks** → One per job (auto-created)
  - **Sections** → User-defined groups (e.g., Daily Logs, Safety Notes, Change Orders, Client Communication, Issues)
  - **Pages** → Individual dated entries or topics within a section
  - Rich text, bullet points, checklists, embedded photos, part references (link to parts catalog)
  - Quick-add from labor entry ("Add note for today")
  - Searchable across all notes
  - Visible in work reports and billing (optional inclusion)
  - LLM can suggest section organization or summarize notes

## Consolidated Feature List (Full Program)

### Parts Side (Unchanged except UI separation)
- All inventory, ordering, stock movement features as previously defined

### Job Tracking Side (Now Fully Featured)
- Active jobs dashboard with truck assignment
- Parts assignment/consumption (links to Parts Side)
- Enhanced labor tracking with timer, photos, descriptions, geolocation radius clock-in/out
- OneNote-style hierarchical notes
- Full work reports (daily/weekly/progress) with photos, descriptions, parts, notes
- Billing reports (materials + labor + markup) — can now embed selected photos/notes

### Shared / Cross-Side Integration
- Consumption logs trigger updates on both sides
- LLM agents monitor both (e.g., flag if high labor but low parts, or vice versa)
- Dashboard toggle between Parts Side and Job Tracking Side views

This plan now delivers a **complete electrician business tool**: precise parts management + comprehensive job/labor/work documentation and reporting — all offline, local, and private. Ready for implementation or further tweaks!

### Supply House Order System for Urgent/Low-Stock Scenarios

This new subsystem enhances the existing **Ordering System** to handle cases where warehouse stock is insufficient for a job parts list, truck loadout, or direct query. It introduces a dedicated **Supply House Order** mode tailored for electricians' real-world needs: quick orders/pickups from local supply houses (e.g., Home Depot, Graybar, local electrical distributors) when time is critical and full supplier deliveries won't arrive fast enough.

Key distinctions:
- **Regular Suppliers**: Scheduled deliveries, intelligent splitting (preferences, cost, multi-supplier), email drafts — for planned/replenishment orders.
- **Supply Houses**: Marked as "local/fast" suppliers in DB. Focus on **immediate or same-day pickup**, simple lists, driving directions, phone scripts — bypassing full splitting for speed.

Triggers automatically when:
- Warehouse stock < required (during parts list creation, truck transfer checklist, or consumption attempt).
- User manually checks "Urgent/Supply House Needed" flag.
- Low-stock alerts from LLM agents.

The system respects **warehouse-first policy** (always deduct available warehouse stock first, only order the shortfall).

#### Features & Goals (User & Developer Perspectives)

| Perspective | Features | Goals |
|-------------|----------|-------|
| User | - **Auto-Detection of Shortages**: When building/assigning a parts list (job or truck), system flags insufficient warehouse stock and prompts: "X parts short — Generate Supply House Order?"<br>- **Quick Supply House Selection**: Pre-defined list of local supply houses (user-added with address/phone/hours).<br>- **Shortfall-Only Orders**: Auto-populate order with only missing quantities (after maxing warehouse).<br>- **Simple Output Formats**:<br>  - Printable pick list (part numbers, descriptions, quantities, images).<br>  - Phone call script (e.g., "Hi, this is [User] from [Company] — picking up: 10x GFCI outlets (Brand X #123)").<br>  - Basic email/text draft if house supports it.<br>  - Offline maps/directions (cached or manual address copy; optional one-time online integration for routing).<br>- **Pickup Confirmation**: Log when parts picked up → add directly to truck stock (bypassing warehouse for urgency).<br>- **Integration Points**:<br>  - From job dashboard (urgent job needs).<br>  - From truck checklist (loading for day).<br>  - Manual "Quick Shortage Check" tool (search part → see stock → order shortfall).<br>- **History**: Track supply house runs for cost analysis (e.g., "Avoid frequent urgents by better forecasting"). | - Handle real emergencies without delaying jobs.<br>- Minimize downtime when warehouse is short.<br>- Keep it faster/simpler than full ordering.<br>- Reduce lost productivity from manual lists/phone calls.<br>- Maintain accuracy (no double-ordering). |
| Developer | - **DB Extensions**: Add "is_supply_house" flag + fields (address, phone, hours, notes) to Suppliers table.<br>- **Shortage Logic**: Queries calculate shortfall (required - warehouse available); auto-fill order.<br>- **Templates**: Simple printable views (HTML-to-PDF) for pick lists/scripts.<br>- **LLM Boost**: Agent suggests best local house (e.g., based on user/truck location if geolocation enabled, or past usage); flags frequent shortages for forecasting improvements.<br>- **Workflow**: Separate "Supply House Order" button/path in UI; results log as special order type (tracks pickup vs. delivery).<br>- **Offline Focus**: All generation local; optional cached maps (e.g., static images from initial setup).<br>- **Integration**: Hooks into existing low-stock alerts, parts lists, and truck transfers. | - Fast execution (no heavy splitting needed).<br>- Reuse existing parts/supplier data.<br>- Easy to distinguish from regular orders in logs/reports.<br>- Scalable for multiple local houses per region.<br>- Enhance LLM audits (e.g., "Too many supply house runs — suggest bulk reorder"). |

#### Example Workflow
1. Electrician assigns parts list to job/truck → System: "Short 50ft wire and 10 outlets in warehouse."
2. Click "Supply House Order" → Select nearest house (e.g., "Graybar Jackson") → Auto-generate pick list.
3. Print/take photo of list → Pickup parts → Confirm in app → Parts added to truck stock.
4. Later: Full replenishment order (regular system) restocks warehouse.

This keeps urgent needs separate from planned ordering while maintaining full traceability. It rounds out the Parts Side for real-world electrician flexibility (especially in areas like Jackson, WY with limited local options).

If you want to add inventory reservation, forecasting to reduce shortages, or specific supply house integrations, let me know—we can build on this!

### Enhanced Workflow & UI for Parts List → Ordering → Delivery to Job

This update focuses on streamlining the **end-to-end workflow** from creating a parts list to ordering, receiving, and delivering parts to jobs — with smart, fast handling for incoming orders, multi-job trucks, returns (including wrong parts), and pickups. It introduces a dedicated **Orders & Returns Management** tab to centralize these processes, keeping the UI focused and efficient.

The app's overall navigation now uses **clear top-level tabs** for separation:
- **Dashboard** (My Truck + My Active Jobs priority view)
- **Parts Catalog** (Search, add/edit parts, merging, images, groups)
- **Job Tracking** (Active jobs, labor/photos/notes, work reports, billing)
- **Warehouse & Trucks** (Stock views, transfers/checklists)
- **Orders & Returns** (New focused tab — detailed below)

This keeps the **Parts Side** (catalog, stock, transfers) distinct from **Job Tracking Side** (labor, reports) while giving ordering/returns its own high-visibility space.

#### New: Orders & Returns Management Tab
This tab is the "control center" for all ordering, receiving, and returns. It has **sub-tabs** for focused workflows:

1. **Pending Orders** (Sub-Tab)
   - List of generated orders (regular supplier or supply house)
   - Status: Draft → Sent → In Transit → Ready for Receive
   - Actions: Edit/send email drafts, track expected dates, cancel

2. **Incoming / Receive** (Sub-Tab) — **Fast & Smart Receiving Workflow**
   - Real-time list of expected arrivals (from orders)
   - **Quick Receive Checklist**:
     - Scan/select order → Auto-load expected parts list
     - Check off received quantities (partial OK)
     - Flag **wrong parts** → Auto-initiate return (populate reason "Incorrect Item", suggest original supplier)
     - Upload photos of delivery/packaging for audit
     - LLM smart assist: Suggest discrepancies (e.g., "Expected 50 outlets, received 45 — flag shortage?")
   - **Smart Allocation on Receive**:
     - After confirming receipt → Prompt: "Allocate to Trucks/Jobs?"
     - Auto-suggest based on active jobs needing those parts (prioritizes user's assigned jobs/truck first)
     - For multi-job trucks: Split allocation intelligently (e.g., "Truck #3 heading to Job A, B, C — allocate 30ft wire to Job A, 20ft to Job B")
     - Options: Direct to warehouse (default), bypass to specific truck (for urgency), or hold for pickup
     - One-click transfer to truck checklist (with quantities pre-filled)

3. **Returns & Pickups** (Sub-Tab)
   - List of pending returns (wrong parts, defects, overstock)
   - Actions: Generate return labels/scripts, schedule supplier pickup
   - Pickup coordination: Flag parts for driver pickup during job runs ("On way back from Job B — pick up return at warehouse")
   - Wrong part handling: Dedicated "Flag Wrong" button during receive → Auto-move to returns queue

4. **Order History** (Sub-Tab)
   - Searchable archive with filters (date, supplier, job-linked)
   - Analytics: Frequent shortages, supply house usage, return reasons

#### Full Workflow: Parts List → Ordering → Parts to Job

This is the optimized, step-by-step process (fast path for daily use, with smart automation):

1. **Create Parts List** (Job Tracking Tab → Specific Job → Parts List Editor)
   - Build from general template, fast list, or manual
   - Auto-suggest bundles, preferences, and check warehouse availability
   - Flag shortages immediately → Option: "Generate Order Now?"

2. **Generate & Send Order** (Auto-prompt or Orders & Returns Tab → Pending Orders)
   - System checks warehouse-first → Calculates shortfall
   - Choose mode:
     - **Regular Order**: Intelligent split across suppliers → Edit → Email drafts → Send
     - **Supply House Order**: Quick mode for urgents → Pick list + phone script → Print/go
   - Order tagged to job(s) for traceability

3. **Track In-Transit** (Orders & Returns Tab → Pending Orders)
   - Update expected date manually or note delivery window

4. **Receive & Smart Allocate** (Orders & Returns Tab → Incoming / Receive — **Fastest Step**)
   - Select arriving order → Checklist receive
   - Handle issues (wrong/short) instantly
   - **Smart Allocation Prompt**:
     - "These parts needed for: Job A (urgent), Job B (tomorrow), Job C (next week)"
     - Suggest: Allocate to Truck #X (assigned to jobs A/B) or hold in warehouse
     - For multi-job runs: "Driver heading to Jobs A → B → C — allocate proportionally?"
     - LLM assist: "Best allocation: Prioritize Job A (deadline today)"
   - Confirm → Auto-transfer to truck(s) or warehouse stock
   - If pickup/return needed: Flag for driver's route

5. **Deliver to Job** (Warehouse & Trucks Tab → Truck Checklist or Job View)
   - Load truck (warehouse-first pull)
   - On-site: Quick consumption logging → Deduct from truck → Log to job

6. **Post-Delivery** (Auto-background)
   - Update stock everywhere
   - LLM agent scans for issues (e.g., frequent shortages → suggest bulk reorder)
   - Returns auto-tracked if wrong parts flagged earlier

#### Benefits of This Design
- **Speed**: Receiving/allocation in <2 minutes via checklists and auto-suggestions
- **Smart but Simple**: LLM handles complex multi-job decisions without overwhelming UI
- **Focused**: All order/return actions in one tab — no hunting across screens
- **Real-World Fit**: Handles Jackson-area realities (limited local supply houses, weather delays, multi-site jobs in remote areas)
- **Accuracy**: Wrong parts caught early, returns seamless, full traceability

This workflow closes the loop perfectly while keeping the app intuitive for busy electricians. If you want wireframes, Mermaid updates, or tweaks (e.g., mobile-friendly checklists), let me know!

