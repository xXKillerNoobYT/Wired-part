# Testing Strategy

## Overview

Wired-Part maintains a strict 100% coverage mandate. Every code change must come with tests, and all tests must pass before committing.

**Current stats**: 635 tests, 100% passing

## Running Tests

```bash
# Full suite
python -m pytest tests/ -x --tb=short

# Specific test file
python -m pytest tests/test_e2e/test_supply_chain_tracking.py -v

# Specific test class
python -m pytest tests/test_database/test_activity_log.py::TestLogActivity -v
```

## Test Structure

```
tests/
  test_config.py                    # Config class, settings persistence
  test_database/
    test_activity_log.py            # Activity log CRUD, filtering
    test_audit.py                   # Audit/notification system
    test_billing.py                 # Billing data, BRO categories
    test_brands.py                  # Part brands CRUD
    test_categories.py              # Part categories CRUD
    test_comprehensive.py           # Cross-cutting repository tests
    test_consumption.py             # Part consumption workflows
    test_deprecation.py             # Deprecation pipeline
    test_geolocation.py             # Geofence, clock location
    test_hats.py                    # Hat permissions, assignment
    test_job_bill_rate.py           # BRO snapshot, rate management
    test_jobs_extended.py           # Job lifecycle, reactivation
    test_labor.py                   # Labor entries, clock in/out
    test_models.py                  # Model properties, computed fields
    test_new_features.py            # Miscellaneous new features
    test_notebooks.py               # Notebook sections, pages
    test_order_analytics.py         # Order analytics queries
    test_order_permissions.py       # Order access control
    test_orders.py                  # PO lifecycle CRUD
    test_orders_extended.py         # Extended order scenarios
    test_part_suppliers.py          # Part-supplier linking
    test_part_types.py              # General vs specific parts
    test_part_variants.py           # Part variants CRUD
    test_parts_lists.py             # Parts lists CRUD
    test_repo_coverage.py           # Coverage gap tests
    test_repository.py              # Core repository methods
    test_returns.py                 # Return authorization lifecycle
    test_search.py                  # Global search functionality
    test_shortfall.py               # Inventory shortfall detection
    test_suppliers.py               # Supplier CRUD
    test_trucks.py                  # Truck CRUD, transfers
    test_users.py                   # User CRUD, authentication
  test_e2e/
    conftest.py                     # Shared fixtures (repo, users, trucks, jobs, parts)
    test_complete_workflow.py        # Full lifecycle workflows
    test_labor_and_jobs.py          # Labor + job integration
    test_supply_and_billing.py      # Supply chain + billing integration
    test_supply_chain_tracking.py   # Supplier tracking E2E + enforcement
    test_truck_verification.py      # Truck inventory verification
  test_io/
    test_csv_handler.py             # CSV import/export
  test_utils/
    test_formatters.py              # Currency/quantity formatting
    test_geo.py                     # Geolocation utilities
    test_qr_generator.py            # QR code generation
```

## Test Isolation

- Each test file creates its own temporary database via `tmp_path` fixture
- Config tests save/restore ALL modified attributes to prevent pollution
- E2E tests use shared fixtures defined in `conftest.py`

## Writing New Tests

1. **New repository method** -> at least one test in appropriate `test_database/` file
2. **New E2E workflow** -> test in `test_e2e/` with full chain verification
3. **Bug fix** -> regression test that reproduces the bug first
4. **ORDER BY queries** -> always add `id DESC` tiebreaker for deterministic results in tests
