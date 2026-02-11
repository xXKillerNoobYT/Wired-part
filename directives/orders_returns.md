# Orders & Returns Management SOP

## Purpose
Manage the full purchase order lifecycle: create orders, submit to suppliers, receive parts with smart allocation, handle returns, track order history with analytics, and leverage advanced ordering features (supply house orders, supplier splitting, email drafts, shortfall detection).

## Schema (v7)
- `purchase_orders` — Order header (order_number, supplier_id, status, notes, dates)
- `purchase_order_items` — Line items (part_id, quantity_ordered, quantity_received, unit_cost)
- `receive_log` — Receiving history (order_item_id, quantity, allocation target, timestamps)
- `return_authorizations` — Return header (ra_number, supplier_id, reason, status, credit_amount)
- `return_authorization_items` — Return line items (part_id, quantity, unit_cost, reason)
- `suppliers` — Now includes `is_supply_house` and `operating_hours` columns (v7)

## Tools
- `src/wired_part/database/repository.py` — ~32 methods for orders/returns/shortfall
- UI: Orders & Returns tab with 4 sub-tabs
- Agent: `get_pending_orders`, `get_orders_summary`, `suggest_reorder` tools

## Order Workflow

### Create Purchase Order
1. Navigate to Orders & Returns > Pending Orders > "+ New Order"
2. Select supplier, add notes
3. Add line items (parts with qty and unit cost)
4. Save as draft
5. Alternative: "From Parts List" button auto-populates items from existing parts list

### Submit Order
1. Select draft order > Click "Submit"
2. System validates at least one line item exists
3. Status transitions: draft > submitted
4. submitted_at timestamp recorded

### Receive Order Items
1. Navigate to Orders & Returns > Incoming / Receive
2. Select submitted/partial order from left panel
3. Right panel shows checklist of line items with:
   - Checkbox to include in this receive batch
   - Qty spinbox (defaults to remaining quantity)
   - Allocation combo: Warehouse (default), Truck, or Job
   - Target combo: specific truck/job if applicable
4. Click "Smart Suggest" to auto-fill allocations based on:
   - Priority 1: Pending truck transfers for this part
   - Priority 2: Active jobs needing this part (via parts lists)
   - Priority 3: Warehouse (default/low stock)
5. Click "Receive Selected" to process
6. System updates quantities based on allocation:
   - Warehouse: increments parts.quantity
   - Truck: adds to warehouse then creates pending truck_transfer
   - Job: adds to warehouse then creates job_parts + consumption_log entry

### Flag Wrong Parts
1. On the Incoming/Receive page, check items that are wrong
2. Click "Flag Wrong Part" button
3. System opens Return Dialog pre-filled with:
   - Supplier from the current order
   - Related order reference
   - Reason set to "wrong_part"
   - All checked items with their quantities

### Order Status Auto-Transitions
- draft > submitted (manual submit)
- submitted > partial (some items received, not all)
- partial > received (all items fully received)
- Any > cancelled (manual cancel)
- received > closed (manual close)

### Create from Parts List
1. Orders & Returns > Pending Orders > "From Parts List"
2. Select parts list > Select supplier
3. Preview items (double-click to edit qty/cost)
4. Click "Create Order"
5. Order created as draft with parts_list_id link

## Supply House Orders (v7)

### Setup
1. Settings > Suppliers > Add/Edit a supplier
2. Check "This is a local supply house"
3. Enter operating hours (e.g., "Mon-Fri 6am-5pm, Sat 7am-12pm")

### Quick Pickup Order
1. Orders & Returns > Pending Orders > "Supply House" button
2. Select supply house from dropdown (only supply house suppliers shown)
3. Supplier info (phone, address) displayed
4. Add parts to the pick list
5. Click "Generate Script" to create a phone call script
6. Click "Copy to Clipboard" to copy the script
7. Click "Create PO & Print Pick List" to create a draft PO

### Phone Script Format
```
Hi, this is Wired Electrical calling to place a pickup order.
Contact: [Supplier Contact Name]

I need [N] item(s):

  1. [Part Number] -- [Description], qty [Qty]
  2. ...

Estimated total: $[Total]

When can I pick this up?
```

## Intelligent Supplier Splitting (v7)

### Split a Parts List Across Suppliers
1. Orders & Returns > Pending Orders > "Split Order" button
2. Select a parts list
3. Optionally select a fallback supplier for unassigned parts
4. Click "Analyze & Split"
5. System groups parts by their `supplier` field (matching against supplier names)
6. Results table shows color-coded supplier groups
7. Review the split, then click "Create Split Orders"
8. Creates separate draft POs for each supplier

### How Splitting Works
- Each part's `supplier` text field is matched against the suppliers table `name`
- Unmatched parts go to the fallback supplier (if selected) or remain unassigned
- Unassigned items are skipped during PO creation
- Visual: each supplier group is color-coded in the results table

## Email Draft Generation (v7)

### Generate Email for an Order
1. Select any order in Pending Orders table
2. Click "Email Draft" button
3. System generates a formatted email with:
   - To: supplier's email (from supplier record)
   - Subject: "Purchase Order [PO Number] -- Wired Electrical"
   - Body: greeting, full line item list, totals, notes, delivery request
4. Opens in default email client via mailto: link

### Email Template Contents
- Greeting with supplier contact name
- Line-by-line item list (part number, description, qty, unit cost, line total)
- Order total
- Order notes (if any)
- Delivery confirmation request

## Shortfall Auto-Detection (v7)

### Check Shortfall on a Parts List
1. Parts Catalog > Parts Lists button > Parts List Manager
2. Select a parts list from the left panel
3. Click "Check Shortfall" button
4. System compares each item's required quantity against warehouse stock
5. If all items are in stock: "No Shortfalls" message
6. If shortfalls exist: detailed report showing:
   - Part number, description
   - Required quantity, in-stock quantity, shortfall quantity
   - Estimated shortfall cost
7. Prompt: "Would you like to generate a purchase order for the shortfall items?"
8. If yes: opens Order From List dialog pre-filled with only shortfall quantities

### Repository Method
```python
repo.check_shortfall(list_id) -> list[dict]
# Returns: [{part_id, part_number, description, required, in_stock, shortfall, unit_cost}]
```

## Return Authorization Workflow

### Create Return
1. Orders & Returns > Returns & Pickups > "+ New Return"
2. Select supplier, optional related order, reason, notes
3. Add parts to return with quantities and cost
4. Click "Create Return"
5. **Inventory is immediately deducted** from warehouse

### Status Transitions
- initiated > picked_up (supplier pickup confirmed)
- picked_up > credit_received (credit amount entered)
- initiated > cancelled (only initiated RAs can be cancelled)

### Delete Return
- Only initiated RAs can be deleted
- **Inventory is restored** to warehouse on deletion

## Return Reasons
- wrong_part, damaged, overstock, defective, other

## Allocation Targets
- warehouse -- Default, adds to parts.quantity
- truck -- Creates pending truck transfer (follows existing transfer workflow)
- job -- Creates job_parts + consumption_log (follows existing consumption workflow)

## Permissions (Hat-Based)
| Permission | Description | Hats |
|-----------|-------------|------|
| tab_orders | Access Orders & Returns tab | Office, Job Manager, Foreman |
| orders_create | Create/edit purchase orders | Office, Job Manager |
| orders_edit | Edit existing orders | Office |
| orders_submit | Submit orders to suppliers | Office |
| orders_receive | Receive order items | Office, Job Manager, Foreman |
| orders_return | Manage return authorizations | Office |
| orders_history | View order history & analytics | Office, Job Manager |

## Analytics
- Total orders, total spent, average order size
- Top supplier by order count
- Total returns count
- Dashboard cards: Pending Orders, Open Returns

## Number Formats
- Purchase Orders: `PO-YYYY-NNN` (e.g., PO-2026-001)
- Return Authorizations: `RA-YYYY-NNN` (e.g., RA-2026-001)

## Edge Cases
- Empty orders: Cannot submit an order with no line items
- Over-receive: Quantity received can exceed ordered (no hard cap)
- Delete submitted: Only draft orders can be deleted
- Delete return: Only initiated returns can be deleted (inventory restored)
- Partial receives: Any receive on a submitted order transitions to partial
- Full receive: When all items fully received, order transitions to received
- Supply house without suppliers: "No supply houses configured" message with setup instructions
- Split with no matching suppliers: Parts shown as "(Unassigned)" and skipped
- Email without supplier email: Opens mailto: with empty "to" field
- Shortfall with zero stock: Full quantity shown as shortfall

## Agent Integration
- `get_pending_orders` -- List all active orders (draft/submitted/partial)
- `get_orders_summary` -- Dashboard quick stats (counts by status, total spent)
- `suggest_reorder` -- Low stock parts with suggested order quantities (2x deficit)

## Outputs
- Updated order tables with color-coded status
- Receiving history timeline in order detail view
- Analytics summary in Order History page
- Dashboard summary cards for orders and returns
- Phone scripts for supply house orders
- Email drafts for supplier communication
- Shortfall reports for parts list planning

## Files Added/Modified in v7
- `src/wired_part/ui/dialogs/supply_house_dialog.py` — Supply house quick-order dialog
- `src/wired_part/ui/dialogs/split_order_dialog.py` — Intelligent supplier splitting
- `src/wired_part/ui/dialogs/supplier_dialog.py` — Added supply house checkbox + hours
- `src/wired_part/ui/pages/pending_orders_page.py` — Added Supply House, Split, Email buttons
- `src/wired_part/ui/dialogs/parts_list_manager_dialog.py` — Added Check Shortfall button
- `src/wired_part/database/schema.py` — v7 migration (supply house columns)
- `src/wired_part/database/models.py` — Supplier: is_supply_house, operating_hours
- `src/wired_part/database/repository.py` — check_shortfall(), supply house CRUD updates
- `tests/test_database/test_shortfall.py` — 9 tests for shortfall + supply house
