# Supply Chain: Part Lifecycle

This document traces a part from supplier purchase through job consumption and back to return.

## The Full Chain

```
1. CREATE PO          supplier_id set on purchase_orders
2. SUBMIT PO          status: submitted
3. RECEIVE ORDER      supplier_id captured in receive_log
   |
   ├── to WAREHOUSE   parts.quantity += qty
   ├── to TRUCK       truck_transfers created (with supplier_id)
   └── to JOB         job_parts created (with supplier_id)
4. TRANSFER           warehouse -> truck (supplier auto-detected)
5. RECEIVE TRANSFER   truck_inventory updated
6. CONSUME            truck -> job (supplier propagated from transfer)
7. RETURN             suggested supplier from job_parts history
```

## Supplier Tracking Details

### At Receive (receive_order_items)
When items are received against a PO:
- `supplier_id` is fetched from `purchase_orders`
- Written to `receive_log.supplier_id`
- If allocating to truck: written to `truck_transfers.supplier_id` and `truck_transfers.source_order_id`
- If allocating to job: written to `job_parts.supplier_id` and `job_parts.source_order_id`

### At Manual Transfer (create_transfer)
When parts are manually moved warehouse -> truck:
- System auto-detects `supplier_id` from `receive_log` (most recent receive of that part)
- Written to `truck_transfers.supplier_id` and `truck_transfers.source_order_id`

### At Consumption (consume_from_truck)
When parts are consumed from truck for a job:
- System looks up `supplier_id` from `truck_transfers` (most recent received outbound transfer for that part on that truck)
- Written to `job_parts.supplier_id` and `consumption_log.supplier_id`

### At Return
- `get_suggested_return_supplier(part_id, job_id)` checks in order:
  1. `job_parts` for that specific job
  2. `consumption_log` for that job
  3. `receive_log` (most recent receive of that part, any context)

## One-Supplier-Per-Part-Per-Job Rule

**Business rule**: A given part on a given job must always come from the same supplier. Different parts can come from different suppliers on the same job.

**Enforcement points**:
- `receive_order_items()` — when `allocate_to="job"`, checks if `job_parts` already has that part from a different supplier. Raises `ValueError` if conflict.
- `consume_from_truck()` — before creating/updating `job_parts`, checks for supplier conflict. Raises `ValueError` if conflict.

**Example**: If Job #123 already has WIRE-12-2 from Supplier A, and you try to receive WIRE-12-2 from Supplier B to Job #123, the system rejects it with: "Supplier conflict: part X on job Y is already supplied by supplier Z."

## Querying the Chain

### Full History
```python
chain = repo.get_part_supplier_chain(part_id)
# Returns list of dicts with: supplier_name, event_type, quantity, event_date
# event_type: "received", "transferred", "consumed"
```

### Suggested Return Supplier
```python
supplier_id = repo.get_suggested_return_supplier(part_id, job_id=optional)
# Returns the supplier_id that should receive the return
```
