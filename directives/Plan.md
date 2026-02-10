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