# Inventory Management SOP

## Purpose
Manage electrical parts inventory including CRUD operations, stock tracking, and search.

## Inputs
- Part details (number, description, quantity, location, category, cost)
- Search queries
- Category filters

## Tools
- `src/wired_part/database/repository.py` — all CRUD operations
- UI: Inventory page for interactive management

## Operations

### Add Part
1. Validate part number uniqueness
2. Validate category exists (or select None)
3. Insert into database
4. FTS index updates automatically via trigger

### Edit Part
1. Load existing part data into dialog
2. User applies changes
3. Update database record
4. Triggers update `updated_at` timestamp

### Delete Part
1. Check if part is assigned to active jobs (RESTRICT FK)
2. If assigned, warn user — cannot delete
3. If not assigned, remove from database

### Search Parts
1. Use FTS5 for natural language search (prefix matching)
2. Filter by category if specified
3. Results update in real-time as user types

## Edge Cases
- Duplicate part numbers: Rejected at DB level (UNIQUE constraint)
- Negative quantities: Prevented by CHECK constraint
- Delete with job references: Blocked by FOREIGN KEY RESTRICT

## Outputs
- Updated parts table view
- Status bar counts refresh
