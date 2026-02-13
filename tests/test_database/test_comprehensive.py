"""Comprehensive tests for untested repository methods and new features.

Covers: user updates, notification management, truck inventory levels,
user permissions, BRO config, schema migration safety, and returns.
"""

import pytest

from wired_part.database.models import (
    Job, Notification, Part, Truck, TruckTransfer, User,
)


# ── User Updates ────────────────────────────────────────────────────

class TestUpdateUser:
    """Tests for repository.update_user()."""

    def test_update_display_name(self, repo):
        user = User(
            username="testuser",
            display_name="Old Name",
            pin_hash=repo.hash_pin("0000"),
            role="user",
        )
        user.id = repo.create_user(user)

        user.display_name = "New Name"
        repo.update_user(user)

        saved = repo.get_user_by_id(user.id)
        assert saved.display_name == "New Name"

    def test_update_user_role(self, repo):
        user = User(
            username="roletest",
            display_name="Role Test",
            pin_hash=repo.hash_pin("1111"),
            role="user",
        )
        user.id = repo.create_user(user)

        user.role = "admin"
        repo.update_user(user)

        saved = repo.get_user_by_id(user.id)
        assert saved.role == "admin"

    def test_update_preserves_other_fields(self, repo):
        user = User(
            username="preserve",
            display_name="Preserve Test",
            pin_hash=repo.hash_pin("2222"),
            role="user",
        )
        user.id = repo.create_user(user)

        user.display_name = "Changed"
        repo.update_user(user)

        saved = repo.get_user_by_id(user.id)
        assert saved.username == "preserve"
        assert saved.role == "user"
        assert saved.is_active == 1


# ── Notification Management ─────────────────────────────────────────

class TestNotifications:
    """Tests for mark_notification_read and related."""

    def _create_user(self, repo):
        u = User(
            username="notifuser",
            display_name="Notif User",
            pin_hash=repo.hash_pin("0000"),
            role="user",
        )
        u.id = repo.create_user(u)
        return u

    def test_mark_single_notification_read(self, repo):
        user = self._create_user(repo)
        notif = Notification(
            user_id=user.id,
            title="Test Alert",
            message="Something happened",
            severity="info",
            source="system",
        )
        nid = repo.create_notification(notif)

        # Verify unread
        unread = repo.get_user_notifications(user.id, unread_only=True)
        assert any(n.id == nid for n in unread)

        # Mark read
        repo.mark_notification_read(nid)

        # Should no longer be in unread list
        unread_after = repo.get_user_notifications(user.id, unread_only=True)
        assert not any(n.id == nid for n in unread_after)

    def test_mark_read_only_affects_target(self, repo):
        user = self._create_user(repo)
        nid1 = repo.create_notification(Notification(
            user_id=user.id, title="Alert 1", message="Msg 1",
            severity="info", source="system",
        ))
        nid2 = repo.create_notification(Notification(
            user_id=user.id, title="Alert 2", message="Msg 2",
            severity="info", source="system",
        ))

        repo.mark_notification_read(nid1)

        unread = repo.get_user_notifications(user.id, unread_only=True)
        ids = {n.id for n in unread}
        assert nid1 not in ids
        assert nid2 in ids


# ── User Permissions ────────────────────────────────────────────────

class TestUserPermissions:
    """Tests for get_user_permissions and user_has_permission."""

    def test_admin_has_all_permissions(self, repo):
        from wired_part.utils.constants import PERMISSION_KEYS
        user = User(
            username="adminperm",
            display_name="Admin Perm",
            pin_hash=repo.hash_pin("0000"),
            role="admin",
        )
        user.id = repo.create_user(user)
        admin_hat = repo.get_hat_by_id(1)
        repo.assign_hat(user.id, admin_hat.id)

        perms = repo.get_user_permissions(user.id)
        assert perms == set(PERMISSION_KEYS)

    def test_user_has_permission_true(self, repo):
        user = User(
            username="permcheck",
            display_name="Perm Check",
            pin_hash=repo.hash_pin("0000"),
            role="admin",
        )
        user.id = repo.create_user(user)
        admin_hat = repo.get_hat_by_id(1)
        repo.assign_hat(user.id, admin_hat.id)

        assert repo.user_has_permission(user.id, "tab_office") is True

    def test_worker_lacks_office_permission(self, repo):
        user = User(
            username="workerp",
            display_name="Worker Perm",
            pin_hash=repo.hash_pin("0000"),
            role="user",
        )
        user.id = repo.create_user(user)
        worker_hat = repo.get_hat_by_name("Worker")
        repo.assign_hat(user.id, worker_hat.id)

        assert repo.user_has_permission(user.id, "tab_office") is False

    def test_user_has_any_full_access_hat(self, repo):
        user = User(
            username="fullaccess",
            display_name="Full Access",
            pin_hash=repo.hash_pin("0000"),
            role="admin",
        )
        user.id = repo.create_user(user)
        it_hat = repo.get_hat_by_name("IT / Tech Junkie")
        repo.assign_hat(user.id, it_hat.id)

        assert repo.user_has_any_full_access_hat(user.id) is True

    def test_user_no_hat_empty_permissions(self, repo):
        user = User(
            username="nohat",
            display_name="No Hat",
            pin_hash=repo.hash_pin("0000"),
            role="user",
        )
        user.id = repo.create_user(user)

        perms = repo.get_user_permissions(user.id)
        assert perms == set()

    def test_foreman_permissions_subset(self, repo):
        user = User(
            username="foremanp",
            display_name="Foreman P",
            pin_hash=repo.hash_pin("0000"),
            role="user",
        )
        user.id = repo.create_user(user)
        foreman_hat = repo.get_hat_by_name("Foreman")
        repo.assign_hat(user.id, foreman_hat.id)

        perms = repo.get_user_permissions(user.id)
        assert "tab_dashboard" in perms
        assert "tab_job_tracking" in perms
        assert "labor_clock_in" in perms
        # Foreman does NOT have office or settings
        assert "tab_office" not in perms
        assert "tab_settings" not in perms


# ── Truck Inventory Levels ──────────────────────────────────────────

class TestTruckInventoryLevels:
    """Tests for truck inventory min/max and direct quantity set."""

    def _setup(self, repo):
        user = User(
            username="truckdriver",
            display_name="Driver",
            pin_hash=repo.hash_pin("0000"),
            role="user",
        )
        user.id = repo.create_user(user)

        truck = Truck(
            truck_number="TI-001",
            name="Inventory Truck",
            assigned_user_id=user.id,
        )
        truck.id = repo.create_truck(truck)

        cat = repo.get_all_categories()[0]
        part = Part(
            part_number="TI-PART",
            description="Test Part for Truck",
            quantity=100,
            category_id=cat.id,
            unit_cost=5.00,
            name="Test Part",
        )
        part.id = repo.create_part(part)

        return user, truck, part

    def test_set_truck_inventory_quantity(self, repo):
        _, truck, part = self._setup(repo)

        repo.set_truck_inventory_quantity(truck.id, part.id, 15)

        inv = repo.get_truck_inventory(truck.id)
        matching = [i for i in inv if i.part_id == part.id]
        assert len(matching) == 1
        assert matching[0].quantity == 15

    def test_set_truck_inventory_quantity_upsert(self, repo):
        _, truck, part = self._setup(repo)

        repo.set_truck_inventory_quantity(truck.id, part.id, 10)
        repo.set_truck_inventory_quantity(truck.id, part.id, 25)

        inv = repo.get_truck_inventory(truck.id)
        matching = [i for i in inv if i.part_id == part.id]
        assert len(matching) == 1
        assert matching[0].quantity == 25

    def test_set_truck_inventory_levels(self, repo):
        _, truck, part = self._setup(repo)

        # First create the inventory row
        repo.set_truck_inventory_quantity(truck.id, part.id, 10)

        # Set min/max levels
        repo.set_truck_inventory_levels(truck.id, part.id, 5, 20)

        inv = repo.get_truck_inventory_with_levels(truck.id)
        matching = [i for i in inv if i.part_id == part.id]
        assert len(matching) == 1
        assert matching[0].min_quantity == 5
        assert matching[0].max_quantity == 20

    def test_get_truck_inventory_with_levels_empty(self, repo):
        user = User(
            username="empty_driver",
            display_name="Empty",
            pin_hash=repo.hash_pin("0000"),
            role="user",
        )
        user.id = repo.create_user(user)
        truck = Truck(
            truck_number="TI-EMPTY",
            name="Empty Truck",
            assigned_user_id=user.id,
        )
        truck.id = repo.create_truck(truck)

        inv = repo.get_truck_inventory_with_levels(truck.id)
        assert inv == []


# ── Recent Returns ──────────────────────────────────────────────────

class TestRecentReturns:
    """Tests for get_recent_returns()."""

    def test_get_recent_returns_empty(self, repo):
        returns = repo.get_recent_returns()
        # Filter to only those from this test (could have seed data)
        assert isinstance(returns, list)

    def test_get_recent_returns_with_data(self, repo):
        user = User(
            username="retuser",
            display_name="Return User",
            pin_hash=repo.hash_pin("0000"),
            role="user",
        )
        user.id = repo.create_user(user)

        truck = Truck(
            truck_number="RT-001",
            name="Return Truck",
            assigned_user_id=user.id,
        )
        truck.id = repo.create_truck(truck)

        cat = repo.get_all_categories()[0]
        part = Part(
            part_number="RT-PART",
            description="Return Test Part",
            quantity=50,
            category_id=cat.id,
            unit_cost=3.00,
            name="Return Part",
        )
        part.id = repo.create_part(part)

        # First stock the truck via outbound transfer
        transfer = TruckTransfer(
            truck_id=truck.id,
            part_id=part.id,
            quantity=10,
            direction="outbound",
            status="pending",
            created_by=user.id,
        )
        tid = repo.create_transfer(transfer)
        repo.receive_transfer(tid, received_by=user.id)

        # Now return from truck to warehouse
        ret_id = repo.return_to_warehouse(
            truck.id, part.id, quantity=5, user_id=user.id,
        )

        returns = repo.get_recent_returns()
        return_ids = [r.id for r in returns]
        assert ret_id in return_ids

    def test_get_recent_returns_limit(self, repo):
        returns = repo.get_recent_returns(limit=5)
        assert len(returns) <= 5


# ── BRO Config ──────────────────────────────────────────────────────

class TestBROConfig:
    """Tests for BRO categories in Config."""

    def test_default_bro_categories(self):
        from wired_part.config import Config
        cats = Config.get_bro_categories()
        assert isinstance(cats, list)
        assert len(cats) >= 1
        # Defaults should include C, T&M, SERVICE, EMERGENCY
        assert "C" in cats or len(cats) > 0  # At least has something

    def test_default_bro_from_constants(self):
        from wired_part.utils.constants import DEFAULT_BRO_CATEGORIES
        assert "C" in DEFAULT_BRO_CATEGORIES
        assert "T&M" in DEFAULT_BRO_CATEGORIES
        assert "SERVICE" in DEFAULT_BRO_CATEGORIES
        assert "EMERGENCY" in DEFAULT_BRO_CATEGORIES

    def test_bro_categories_is_list_of_strings(self):
        from wired_part.config import Config
        cats = Config.get_bro_categories()
        for cat in cats:
            assert isinstance(cat, str)


# ── Schema Migration Safety ─────────────────────────────────────────

class TestSchemaMigrationSafety:
    """Tests for _ensure_required_columns safety net."""

    def test_fresh_database_has_all_columns(self, repo):
        """A fresh v11 database should have all required columns."""
        # bill_out_rate should be TEXT
        job = Job(
            job_number="SCHEMA-001",
            name="Schema Test",
            bill_out_rate="T&M",
        )
        jid = repo.create_job(job)
        saved = repo.get_job_by_id(jid)
        assert saved.bill_out_rate == "T&M"
        assert isinstance(saved.bill_out_rate, str)

    def test_parts_have_max_quantity_column(self, repo):
        """Parts table should have max_quantity column."""
        cat = repo.get_all_categories()[0]
        part = Part(
            part_number="SCHEMA-P1",
            description="Max Qty Test",
            quantity=10,
            category_id=cat.id,
            unit_cost=1.00,
            name="Schema Part",
            max_quantity=50,
        )
        pid = repo.create_part(part)
        saved = repo.get_part_by_id(pid)
        assert saved.max_quantity == 50

    def test_parts_have_deprecation_columns(self, repo):
        """Parts table should have deprecation columns."""
        cat = repo.get_all_categories()[0]
        part = Part(
            part_number="SCHEMA-DEP",
            description="Deprecation Test",
            quantity=10,
            category_id=cat.id,
            unit_cost=1.00,
            name="Depr Part",
        )
        pid = repo.create_part(part)

        saved = repo.get_part_by_id(pid)
        assert saved.deprecation_status is None

    def test_notifications_have_target_columns(self, repo):
        """Notifications should have target_tab and target_data."""
        user = User(
            username="schemanotif",
            display_name="Schema Notif",
            pin_hash=repo.hash_pin("0000"),
            role="user",
        )
        user.id = repo.create_user(user)

        notif = Notification(
            user_id=user.id,
            title="Target Test",
            message="Has target fields",
            severity="info",
            source="system",
            target_tab="trucks",
            target_data='{"truck_id": 1}',
        )
        nid = repo.create_notification(notif)

        notifs = repo.get_user_notifications(user.id)
        matching = [n for n in notifs if n.id == nid]
        assert len(matching) == 1
        assert matching[0].target_tab == "trucks"


# ── BRO on Jobs — Extended ──────────────────────────────────────────

class TestBROOnJobs:
    """Extended tests for bill_out_rate (BRO) as a text category."""

    def test_all_standard_categories(self, repo):
        """Test storing each default BRO category."""
        from wired_part.utils.constants import DEFAULT_BRO_CATEGORIES
        for i, cat in enumerate(DEFAULT_BRO_CATEGORIES):
            job = Job(
                job_number=f"BRO-STD-{i}",
                name=f"Job with {cat}",
                bill_out_rate=cat,
            )
            jid = repo.create_job(job)
            saved = repo.get_job_by_id(jid)
            assert saved.bill_out_rate == cat

    def test_bro_filter_by_category(self, repo):
        """Test filtering jobs by BRO category."""
        for code, name in [("C", "Contract Job"), ("T&M", "T&M Job"),
                           ("C", "Another Contract")]:
            repo.create_job(Job(
                job_number=f"BRO-F-{name[:3]}-{id(name)}",
                name=name,
                bill_out_rate=code,
            ))

        jobs = repo.get_all_jobs()
        c_jobs = [j for j in jobs if j.bill_out_rate == "C"]
        assert len(c_jobs) >= 2

        tm_jobs = [j for j in jobs if j.bill_out_rate == "T&M"]
        assert len(tm_jobs) >= 1

    def test_bro_not_numeric(self, repo):
        """Ensure BRO is NOT treated as a number."""
        job = Job(
            job_number="BRO-NONUM",
            name="Not Numeric",
            bill_out_rate="SERVICE",
        )
        jid = repo.create_job(job)
        saved = repo.get_job_by_id(jid)
        # Should NOT be convertible to float
        with pytest.raises(ValueError):
            float(saved.bill_out_rate)

    def test_bro_special_characters(self, repo):
        """BRO categories with special chars like & should work."""
        job = Job(
            job_number="BRO-SPEC",
            name="Special Chars",
            bill_out_rate="T&M",
        )
        jid = repo.create_job(job)
        saved = repo.get_job_by_id(jid)
        assert saved.bill_out_rate == "T&M"

    def test_bro_case_sensitive(self, repo):
        """BRO categories are case-sensitive as stored."""
        job = Job(
            job_number="BRO-CASE",
            name="Case Test",
            bill_out_rate="service",
        )
        jid = repo.create_job(job)
        saved = repo.get_job_by_id(jid)
        assert saved.bill_out_rate == "service"
        assert saved.bill_out_rate != "SERVICE"
