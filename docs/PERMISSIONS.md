# Permissions & Hat System

## Overview

Wired-Part uses a **hat-based** permission system. Each user is assigned a "hat" (role) that determines what they can see and do. There are 7 predefined hats ordered by privilege level.

## Hats (Highest to Lowest)

| Hat | Access Level | Locked |
|-----|-------------|--------|
| Admin / CEO / Owner | Full access to everything | Yes |
| IT / Tech Junkie | Full access (same as Admin) | Yes |
| Office / HR | Everything except agent/LLM settings, can't delete jobs | Yes |
| Job Manager | Field + office operations, no settings management | No |
| Foreman | Field operations, team oversight | No |
| Worker | Basic field tasks: clock in/out, view jobs | No |
| Grunt | Minimal: clock in/out only | No |

**Locked hats** (Admin, IT, Office) cannot have their permissions edited or be deleted.

## Permission Keys (48+)

### Tab Access
`tab_dashboard`, `tab_parts_catalog`, `tab_warehouse`, `tab_trucks_inventory`, `tab_jobs_inventory`, `tab_job_tracking`, `tab_trucks`, `tab_labor`, `tab_office`, `tab_agent`, `tab_settings`

### Parts & Inventory
`parts_add`, `parts_edit`, `parts_delete`, `parts_import`, `parts_export`, `parts_lists`, `parts_brands`, `parts_variants`, `parts_qr_tags`

### Jobs
`jobs_add`, `jobs_edit`, `jobs_delete`, `jobs_assign`, `jobs_billing`, `jobs_notes`, `jobs_report`

### Labor
`labor_clock_in`, `labor_clock_out`, `labor_manual_entry`, `labor_view_all`

### Trucks
`trucks_add`, `trucks_edit`, `trucks_transfer`

### Orders & Returns
`tab_orders`, `orders_create`, `orders_edit`, `orders_submit`, `orders_receive`, `orders_return`, `orders_history`

### Settings
`settings_users`, `settings_hats`, `settings_categories`, `settings_suppliers`, `settings_llm`, `settings_agent`, `settings_labor`, `settings_notebook`, `settings_general`

## How Permissions are Checked

```python
# In UI code:
if repo.user_has_permission(current_user.id, "jobs_edit"):
    show_edit_button()
```

The Admin and IT hats bypass permission checks entirely — they always have full access.

## Custom Hats

Users can create custom hats (beyond the 7 defaults) with any combination of permissions. Custom hats can be freely edited and deleted.
