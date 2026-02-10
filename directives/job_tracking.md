# Job Tracking SOP

## Purpose
Track electrical jobs/projects and the parts assigned to them.

## Inputs
- Job details (number, name, customer, address, status)
- Part assignments (part_id, quantity)

## Tools
- `src/wired_part/database/repository.py` — CRUD and assignment operations
- UI: Jobs page with list/detail split view

## Operations

### Create Job
1. Auto-generate job number (JOB-YYYY-NNN format)
2. Validate required fields (name)
3. Insert into database with status "active"

### Assign Parts to Job
1. Select job, then pick parts from available inventory
2. Specify quantity for each part
3. Check stock availability (quantity >= requested)
4. Deduct from parts.quantity
5. Record in job_parts with unit_cost snapshot
6. If part already assigned, quantity_used is incremented (UPSERT)

### Complete Job
1. Update status to "completed"
2. Set completed_at timestamp
3. Parts remain assigned for cost tracking / history

### Delete Job
1. Return all assigned parts to inventory (restore quantities)
2. Delete job_parts records (CASCADE)
3. Delete job record

## Edge Cases
- Insufficient stock: Error shown, assignment blocked
- Duplicate job numbers: Auto-increment prevents this
- Long-running jobs: Status can be set to "on_hold"

## Outputs
- Job list with status filtering
- Detail panel with assigned parts and total cost
