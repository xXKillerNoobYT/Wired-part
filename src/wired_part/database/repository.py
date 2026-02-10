"""Repository layer — all CRUD operations and queries."""

import hashlib
from typing import Optional

from .connection import DatabaseConnection
from .models import (
    Category,
    ConsumptionLog,
    Job,
    JobAssignment,
    JobPart,
    Notification,
    Part,
    PartsList,
    PartsListItem,
    Supplier,
    Truck,
    TruckInventory,
    TruckTransfer,
    User,
)


class Repository:
    """Provides all database operations for the application."""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    # ── Categories ──────────────────────────────────────────────

    def get_all_categories(self) -> list[Category]:
        rows = self.db.execute(
            "SELECT * FROM categories ORDER BY name"
        )
        return [Category(**dict(r)) for r in rows]

    def get_category_by_id(self, category_id: int) -> Optional[Category]:
        rows = self.db.execute(
            "SELECT * FROM categories WHERE id = ?", (category_id,)
        )
        return Category(**dict(rows[0])) if rows else None

    def create_category(self, category: Category) -> int:
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO categories (name, description, is_custom, color) "
                "VALUES (?, ?, ?, ?)",
                (category.name, category.description,
                 category.is_custom, category.color),
            )
            return cursor.lastrowid

    def update_category(self, category: Category):
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE categories SET name = ?, description = ?, "
                "is_custom = ?, color = ? WHERE id = ?",
                (category.name, category.description,
                 category.is_custom, category.color, category.id),
            )

    def delete_category(self, category_id: int, reassign_to: int = None):
        """Delete a category and reassign its parts.

        If reassign_to is None, finds the 'Miscellaneous' category.
        """
        with self.db.get_connection() as conn:
            if reassign_to is None:
                row = conn.execute(
                    "SELECT id FROM categories WHERE name = 'Miscellaneous'"
                ).fetchone()
                reassign_to = row["id"] if row else None
            if reassign_to:
                conn.execute(
                    "UPDATE parts SET category_id = ? WHERE category_id = ?",
                    (reassign_to, category_id),
                )
            else:
                conn.execute(
                    "UPDATE parts SET category_id = NULL WHERE category_id = ?",
                    (category_id,),
                )
            conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))

    def get_category_part_count(self, category_id: int) -> int:
        rows = self.db.execute(
            "SELECT COUNT(*) as cnt FROM parts WHERE category_id = ?",
            (category_id,),
        )
        return rows[0]["cnt"] if rows else 0

    # ── Parts ───────────────────────────────────────────────────

    def get_all_parts(self) -> list[Part]:
        rows = self.db.execute("""
            SELECT p.*, COALESCE(c.name, '') AS category_name
            FROM parts p
            LEFT JOIN categories c ON p.category_id = c.id
            ORDER BY p.part_number
        """)
        return [Part(**dict(r)) for r in rows]

    def get_part_by_id(self, part_id: int) -> Optional[Part]:
        rows = self.db.execute("""
            SELECT p.*, COALESCE(c.name, '') AS category_name
            FROM parts p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.id = ?
        """, (part_id,))
        return Part(**dict(rows[0])) if rows else None

    def get_part_by_number(self, part_number: str) -> Optional[Part]:
        rows = self.db.execute("""
            SELECT p.*, COALESCE(c.name, '') AS category_name
            FROM parts p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.part_number = ?
        """, (part_number,))
        return Part(**dict(rows[0])) if rows else None

    def search_parts(self, query: str) -> list[Part]:
        """Search parts by keyword across multiple fields."""
        if not query.strip():
            return self.get_all_parts()
        pattern = f"%{query.strip()}%"
        rows = self.db.execute("""
            SELECT p.*, COALESCE(c.name, '') AS category_name
            FROM parts p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.part_number LIKE ?
               OR p.description LIKE ?
               OR p.location LIKE ?
               OR p.supplier LIKE ?
               OR p.notes LIKE ?
            ORDER BY p.part_number
        """, (pattern, pattern, pattern, pattern, pattern))
        return [Part(**dict(r)) for r in rows]

    def get_parts_by_category(self, category_id: int) -> list[Part]:
        rows = self.db.execute("""
            SELECT p.*, COALESCE(c.name, '') AS category_name
            FROM parts p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.category_id = ?
            ORDER BY p.part_number
        """, (category_id,))
        return [Part(**dict(r)) for r in rows]

    def get_low_stock_parts(self) -> list[Part]:
        rows = self.db.execute("""
            SELECT p.*, COALESCE(c.name, '') AS category_name
            FROM parts p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.quantity < p.min_quantity AND p.min_quantity > 0
            ORDER BY (p.min_quantity - p.quantity) DESC
        """)
        return [Part(**dict(r)) for r in rows]

    def create_part(self, part: Part) -> int:
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO parts
                    (part_number, description, quantity, location,
                     category_id, unit_cost, min_quantity, supplier, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                part.part_number, part.description, part.quantity,
                part.location, part.category_id, part.unit_cost,
                part.min_quantity, part.supplier, part.notes,
            ))
            return cursor.lastrowid

    def update_part(self, part: Part):
        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE parts SET
                    part_number = ?, description = ?, quantity = ?,
                    location = ?, category_id = ?, unit_cost = ?,
                    min_quantity = ?, supplier = ?, notes = ?
                WHERE id = ?
            """, (
                part.part_number, part.description, part.quantity,
                part.location, part.category_id, part.unit_cost,
                part.min_quantity, part.supplier, part.notes,
                part.id,
            ))

    def delete_part(self, part_id: int):
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM parts WHERE id = ?", (part_id,))

    # ── Users ────────────────────────────────────────────────────

    @staticmethod
    def hash_pin(pin: str) -> str:
        """Hash a PIN using SHA-256."""
        return hashlib.sha256(pin.encode("utf-8")).hexdigest()

    def create_user(self, user: User) -> int:
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO users
                    (username, display_name, pin_hash, role, is_active)
                VALUES (?, ?, ?, ?, ?)
            """, (
                user.username, user.display_name, user.pin_hash,
                user.role, user.is_active,
            ))
            return cursor.lastrowid

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        rows = self.db.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        )
        return User(**dict(rows[0])) if rows else None

    def get_user_by_username(self, username: str) -> Optional[User]:
        rows = self.db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        )
        return User(**dict(rows[0])) if rows else None

    def authenticate_user(self, username: str, pin: str) -> Optional[User]:
        """Authenticate a user by username and PIN. Returns User or None."""
        user = self.get_user_by_username(username)
        if user and user.is_active and user.pin_hash == self.hash_pin(pin):
            return user
        return None

    def get_all_users(self, active_only: bool = True) -> list[User]:
        if active_only:
            rows = self.db.execute(
                "SELECT * FROM users WHERE is_active = 1 ORDER BY display_name"
            )
        else:
            rows = self.db.execute(
                "SELECT * FROM users ORDER BY display_name"
            )
        return [User(**dict(r)) for r in rows]

    def update_user(self, user: User):
        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE users SET
                    username = ?, display_name = ?, pin_hash = ?,
                    role = ?, is_active = ?
                WHERE id = ?
            """, (
                user.username, user.display_name, user.pin_hash,
                user.role, user.is_active, user.id,
            ))

    def deactivate_user(self, user_id: int):
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE users SET is_active = 0 WHERE id = ?", (user_id,)
            )

    def user_count(self) -> int:
        rows = self.db.execute("SELECT COUNT(*) as cnt FROM users")
        return rows[0]["cnt"] if rows else 0

    # ── Jobs ────────────────────────────────────────────────────

    def get_all_jobs(self, status: Optional[str] = None) -> list[Job]:
        if status and status != "all":
            rows = self.db.execute(
                "SELECT * FROM jobs WHERE status = ? "
                "ORDER BY priority ASC, created_at DESC",
                (status,),
            )
        else:
            rows = self.db.execute(
                "SELECT * FROM jobs ORDER BY priority ASC, created_at DESC"
            )
        return [Job(**dict(r)) for r in rows]

    def get_job_by_id(self, job_id: int) -> Optional[Job]:
        rows = self.db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        return Job(**dict(rows[0])) if rows else None

    def get_job_by_number(self, job_number: str) -> Optional[Job]:
        rows = self.db.execute(
            "SELECT * FROM jobs WHERE job_number = ?", (job_number,)
        )
        return Job(**dict(rows[0])) if rows else None

    def create_job(self, job: Job) -> int:
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO jobs
                    (job_number, name, customer, address, status,
                     priority, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                job.job_number, job.name, job.customer,
                job.address, job.status, job.priority, job.notes,
            ))
            return cursor.lastrowid

    def update_job(self, job: Job):
        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE jobs SET
                    job_number = ?, name = ?, customer = ?,
                    address = ?, status = ?, priority = ?,
                    notes = ?, completed_at = ?
                WHERE id = ?
            """, (
                job.job_number, job.name, job.customer,
                job.address, job.status, job.priority,
                job.notes, job.completed_at, job.id,
            ))

    def delete_job(self, job_id: int):
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))

    def generate_job_number(self) -> str:
        """Generate next sequential job number like JOB-2026-001."""
        from datetime import datetime
        year = datetime.now().year
        rows = self.db.execute(
            "SELECT COUNT(*) as cnt FROM jobs WHERE job_number LIKE ?",
            (f"JOB-{year}-%",),
        )
        count = rows[0]["cnt"] + 1 if rows else 1
        return f"JOB-{year}-{count:03d}"

    # ── Job Parts ───────────────────────────────────────────────

    def get_job_parts(self, job_id: int) -> list[JobPart]:
        rows = self.db.execute("""
            SELECT jp.*, p.part_number, p.description AS part_description
            FROM job_parts jp
            JOIN parts p ON jp.part_id = p.id
            WHERE jp.job_id = ?
            ORDER BY jp.assigned_at DESC
        """, (job_id,))
        return [JobPart(**dict(r)) for r in rows]

    def assign_part_to_job(self, job_part: JobPart) -> int:
        """Assign a part to a job and deduct from inventory."""
        with self.db.get_connection() as conn:
            # Snapshot the current unit cost
            part_row = conn.execute(
                "SELECT unit_cost, quantity FROM parts WHERE id = ?",
                (job_part.part_id,),
            ).fetchone()
            if not part_row:
                raise ValueError(f"Part {job_part.part_id} not found")
            if part_row["quantity"] < job_part.quantity_used:
                raise ValueError(
                    f"Insufficient stock: have {part_row['quantity']}, "
                    f"need {job_part.quantity_used}"
                )

            job_part.unit_cost_at_use = part_row["unit_cost"]

            # Insert or update the assignment
            cursor = conn.execute("""
                INSERT INTO job_parts
                    (job_id, part_id, quantity_used, unit_cost_at_use, notes)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(job_id, part_id) DO UPDATE SET
                    quantity_used = quantity_used + excluded.quantity_used
            """, (
                job_part.job_id, job_part.part_id,
                job_part.quantity_used, job_part.unit_cost_at_use,
                job_part.notes,
            ))

            # Deduct from inventory
            conn.execute(
                "UPDATE parts SET quantity = quantity - ? WHERE id = ?",
                (job_part.quantity_used, job_part.part_id),
            )
            return cursor.lastrowid

    def remove_part_from_job(self, job_part_id: int):
        """Remove a part assignment and restore inventory."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT part_id, quantity_used FROM job_parts WHERE id = ?",
                (job_part_id,),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE parts SET quantity = quantity + ? WHERE id = ?",
                    (row["quantity_used"], row["part_id"]),
                )
                conn.execute(
                    "DELETE FROM job_parts WHERE id = ?", (job_part_id,)
                )

    def get_job_total_cost(self, job_id: int) -> float:
        rows = self.db.execute("""
            SELECT COALESCE(SUM(quantity_used * unit_cost_at_use), 0) AS total
            FROM job_parts WHERE job_id = ?
        """, (job_id,))
        return rows[0]["total"] if rows else 0.0

    # ── Job Assignments ─────────────────────────────────────────

    def assign_user_to_job(self, assignment: JobAssignment) -> int:
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO job_assignments (job_id, user_id, role)
                VALUES (?, ?, ?)
                ON CONFLICT(job_id, user_id) DO UPDATE SET role = excluded.role
            """, (assignment.job_id, assignment.user_id, assignment.role))
            return cursor.lastrowid

    def remove_user_from_job(self, assignment_id: int):
        with self.db.get_connection() as conn:
            conn.execute(
                "DELETE FROM job_assignments WHERE id = ?", (assignment_id,)
            )

    def get_job_assignments(self, job_id: int) -> list[JobAssignment]:
        rows = self.db.execute("""
            SELECT ja.*, u.display_name AS user_name,
                   j.job_number, j.name AS job_name
            FROM job_assignments ja
            JOIN users u ON ja.user_id = u.id
            JOIN jobs j ON ja.job_id = j.id
            WHERE ja.job_id = ?
            ORDER BY ja.role, u.display_name
        """, (job_id,))
        return [JobAssignment(**dict(r)) for r in rows]

    def get_user_jobs(self, user_id: int,
                      status: Optional[str] = None) -> list[JobAssignment]:
        if status and status != "all":
            rows = self.db.execute("""
                SELECT ja.*, u.display_name AS user_name,
                       j.job_number, j.name AS job_name
                FROM job_assignments ja
                JOIN users u ON ja.user_id = u.id
                JOIN jobs j ON ja.job_id = j.id
                WHERE ja.user_id = ? AND j.status = ?
                ORDER BY j.created_at DESC
            """, (user_id, status))
        else:
            rows = self.db.execute("""
                SELECT ja.*, u.display_name AS user_name,
                       j.job_number, j.name AS job_name
                FROM job_assignments ja
                JOIN users u ON ja.user_id = u.id
                JOIN jobs j ON ja.job_id = j.id
                WHERE ja.user_id = ?
                ORDER BY j.created_at DESC
            """, (user_id,))
        return [JobAssignment(**dict(r)) for r in rows]

    # ── Trucks ──────────────────────────────────────────────────

    def create_truck(self, truck: Truck) -> int:
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO trucks
                    (truck_number, name, assigned_user_id, notes, is_active)
                VALUES (?, ?, ?, ?, ?)
            """, (
                truck.truck_number, truck.name, truck.assigned_user_id,
                truck.notes, truck.is_active,
            ))
            return cursor.lastrowid

    def get_all_trucks(self, active_only: bool = True) -> list[Truck]:
        if active_only:
            rows = self.db.execute("""
                SELECT t.*, COALESCE(u.display_name, '') AS assigned_user_name
                FROM trucks t
                LEFT JOIN users u ON t.assigned_user_id = u.id
                WHERE t.is_active = 1
                ORDER BY t.truck_number
            """)
        else:
            rows = self.db.execute("""
                SELECT t.*, COALESCE(u.display_name, '') AS assigned_user_name
                FROM trucks t
                LEFT JOIN users u ON t.assigned_user_id = u.id
                ORDER BY t.truck_number
            """)
        return [Truck(**dict(r)) for r in rows]

    def get_truck_by_id(self, truck_id: int) -> Optional[Truck]:
        rows = self.db.execute("""
            SELECT t.*, COALESCE(u.display_name, '') AS assigned_user_name
            FROM trucks t
            LEFT JOIN users u ON t.assigned_user_id = u.id
            WHERE t.id = ?
        """, (truck_id,))
        return Truck(**dict(rows[0])) if rows else None

    def update_truck(self, truck: Truck):
        # Check if assignment changed to create notification
        old_truck = self.get_truck_by_id(truck.id)
        old_user_id = old_truck.assigned_user_id if old_truck else None

        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE trucks SET
                    truck_number = ?, name = ?, assigned_user_id = ?,
                    notes = ?, is_active = ?
                WHERE id = ?
            """, (
                truck.truck_number, truck.name, truck.assigned_user_id,
                truck.notes, truck.is_active, truck.id,
            ))

        # Notify affected users of assignment changes
        if old_user_id != truck.assigned_user_id:
            if old_user_id:
                self.create_notification(Notification(
                    user_id=old_user_id,
                    title="Truck Unassigned",
                    message=(
                        f"You have been unassigned from truck "
                        f"{truck.truck_number} ({truck.name})."
                    ),
                    severity="info",
                    source="system",
                ))
            if truck.assigned_user_id:
                self.create_notification(Notification(
                    user_id=truck.assigned_user_id,
                    title="Truck Assigned",
                    message=(
                        f"You have been assigned to truck "
                        f"{truck.truck_number} ({truck.name})."
                    ),
                    severity="info",
                    source="system",
                ))

    # ── Truck Inventory (On-Hand) ───────────────────────────────

    def get_truck_inventory(self, truck_id: int) -> list[TruckInventory]:
        rows = self.db.execute("""
            SELECT ti.*, p.part_number, p.description AS part_description,
                   p.unit_cost, t.truck_number
            FROM truck_inventory ti
            JOIN parts p ON ti.part_id = p.id
            JOIN trucks t ON ti.truck_id = t.id
            WHERE ti.truck_id = ? AND ti.quantity > 0
            ORDER BY p.part_number
        """, (truck_id,))
        return [TruckInventory(**dict(r)) for r in rows]

    def get_truck_part_quantity(self, truck_id: int, part_id: int) -> int:
        rows = self.db.execute("""
            SELECT quantity FROM truck_inventory
            WHERE truck_id = ? AND part_id = ?
        """, (truck_id, part_id))
        return rows[0]["quantity"] if rows else 0

    # ── Truck Transfers ─────────────────────────────────────────

    def create_transfer(self, transfer: TruckTransfer) -> int:
        """Create an outbound transfer (warehouse -> truck).

        Immediately deducts from warehouse stock. Transfer starts as 'pending'.
        """
        with self.db.get_connection() as conn:
            # Validate warehouse stock
            part_row = conn.execute(
                "SELECT quantity FROM parts WHERE id = ?",
                (transfer.part_id,),
            ).fetchone()
            if not part_row:
                raise ValueError(f"Part {transfer.part_id} not found")
            if part_row["quantity"] < transfer.quantity:
                raise ValueError(
                    f"Insufficient warehouse stock: have "
                    f"{part_row['quantity']}, need {transfer.quantity}"
                )

            # Deduct from warehouse
            conn.execute(
                "UPDATE parts SET quantity = quantity - ? WHERE id = ?",
                (transfer.quantity, transfer.part_id),
            )

            # Create transfer record
            cursor = conn.execute("""
                INSERT INTO truck_transfers
                    (truck_id, part_id, quantity, direction, status,
                     created_by, notes)
                VALUES (?, ?, ?, 'outbound', 'pending', ?, ?)
            """, (
                transfer.truck_id, transfer.part_id, transfer.quantity,
                transfer.created_by, transfer.notes,
            ))
            return cursor.lastrowid

    def receive_transfer(self, transfer_id: int, received_by: int):
        """Receive a pending transfer — adds to truck on-hand inventory."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM truck_transfers "
                "WHERE id = ? AND status = 'pending'",
                (transfer_id,),
            ).fetchone()
            if not row:
                raise ValueError(
                    f"Transfer {transfer_id} not found or not pending"
                )

            # Add to truck on-hand inventory
            conn.execute("""
                INSERT INTO truck_inventory (truck_id, part_id, quantity)
                VALUES (?, ?, ?)
                ON CONFLICT(truck_id, part_id) DO UPDATE SET
                    quantity = quantity + excluded.quantity
            """, (row["truck_id"], row["part_id"], row["quantity"]))

            # Mark transfer as received
            conn.execute("""
                UPDATE truck_transfers
                SET status = 'received', received_by = ?,
                    received_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (received_by, transfer_id))

    def cancel_transfer(self, transfer_id: int):
        """Cancel a pending transfer — restores warehouse stock."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM truck_transfers "
                "WHERE id = ? AND status = 'pending'",
                (transfer_id,),
            ).fetchone()
            if not row:
                raise ValueError(
                    f"Transfer {transfer_id} not found or not pending"
                )

            # Restore warehouse stock
            conn.execute(
                "UPDATE parts SET quantity = quantity + ? WHERE id = ?",
                (row["quantity"], row["part_id"]),
            )

            # Mark as cancelled
            conn.execute(
                "UPDATE truck_transfers SET status = 'cancelled' WHERE id = ?",
                (transfer_id,),
            )

    def return_to_warehouse(self, truck_id: int, part_id: int,
                            quantity: int, user_id: int = None) -> int:
        """Return parts from truck on-hand back to warehouse."""
        with self.db.get_connection() as conn:
            # Validate truck has enough
            inv_row = conn.execute(
                "SELECT quantity FROM truck_inventory "
                "WHERE truck_id = ? AND part_id = ?",
                (truck_id, part_id),
            ).fetchone()
            on_hand = inv_row["quantity"] if inv_row else 0
            if on_hand < quantity:
                raise ValueError(
                    f"Insufficient truck stock: have {on_hand}, "
                    f"need {quantity}"
                )

            # Deduct from truck
            conn.execute(
                "UPDATE truck_inventory SET quantity = quantity - ? "
                "WHERE truck_id = ? AND part_id = ?",
                (quantity, truck_id, part_id),
            )

            # Add back to warehouse
            conn.execute(
                "UPDATE parts SET quantity = quantity + ? WHERE id = ?",
                (quantity, part_id),
            )

            # Create return transfer record (immediately received)
            cursor = conn.execute("""
                INSERT INTO truck_transfers
                    (truck_id, part_id, quantity, direction, status,
                     created_by, received_by, received_at)
                VALUES (?, ?, ?, 'return', 'received', ?, ?,
                        CURRENT_TIMESTAMP)
            """, (truck_id, part_id, quantity, user_id, user_id))
            return cursor.lastrowid

    def get_truck_transfers(self, truck_id: int,
                            status: Optional[str] = None
                            ) -> list[TruckTransfer]:
        if status:
            rows = self.db.execute("""
                SELECT tt.*,
                       p.part_number, p.description AS part_description,
                       t.truck_number,
                       COALESCE(uc.display_name, '') AS created_by_name,
                       COALESCE(ur.display_name, '') AS received_by_name
                FROM truck_transfers tt
                JOIN parts p ON tt.part_id = p.id
                JOIN trucks t ON tt.truck_id = t.id
                LEFT JOIN users uc ON tt.created_by = uc.id
                LEFT JOIN users ur ON tt.received_by = ur.id
                WHERE tt.truck_id = ? AND tt.status = ?
                ORDER BY tt.created_at DESC
            """, (truck_id, status))
        else:
            rows = self.db.execute("""
                SELECT tt.*,
                       p.part_number, p.description AS part_description,
                       t.truck_number,
                       COALESCE(uc.display_name, '') AS created_by_name,
                       COALESCE(ur.display_name, '') AS received_by_name
                FROM truck_transfers tt
                JOIN parts p ON tt.part_id = p.id
                JOIN trucks t ON tt.truck_id = t.id
                LEFT JOIN users uc ON tt.created_by = uc.id
                LEFT JOIN users ur ON tt.received_by = ur.id
                WHERE tt.truck_id = ?
                ORDER BY tt.created_at DESC
            """, (truck_id,))
        return [TruckTransfer(**dict(r)) for r in rows]

    def get_all_pending_transfers(self) -> list[TruckTransfer]:
        rows = self.db.execute("""
            SELECT tt.*,
                   p.part_number, p.description AS part_description,
                   t.truck_number,
                   COALESCE(uc.display_name, '') AS created_by_name,
                   COALESCE(ur.display_name, '') AS received_by_name
            FROM truck_transfers tt
            JOIN parts p ON tt.part_id = p.id
            JOIN trucks t ON tt.truck_id = t.id
            LEFT JOIN users uc ON tt.created_by = uc.id
            LEFT JOIN users ur ON tt.received_by = ur.id
            WHERE tt.status = 'pending'
            ORDER BY tt.created_at DESC
        """)
        return [TruckTransfer(**dict(r)) for r in rows]

    # ── Part Consumption (Truck -> Job) ─────────────────────────

    def consume_from_truck(self, job_id: int, truck_id: int, part_id: int,
                           quantity: int, user_id: int = None,
                           notes: str = "") -> int:
        """Consume parts from a truck's on-hand inventory for a job.

        Deducts from truck_inventory, creates job_parts record and
        consumption_log entry.
        """
        with self.db.get_connection() as conn:
            # Validate truck has enough on-hand
            inv_row = conn.execute(
                "SELECT quantity FROM truck_inventory "
                "WHERE truck_id = ? AND part_id = ?",
                (truck_id, part_id),
            ).fetchone()
            on_hand = inv_row["quantity"] if inv_row else 0
            if on_hand < quantity:
                raise ValueError(
                    f"Insufficient truck stock: have {on_hand}, "
                    f"need {quantity}"
                )

            # Get unit cost for snapshot
            part_row = conn.execute(
                "SELECT unit_cost FROM parts WHERE id = ?", (part_id,)
            ).fetchone()
            unit_cost = part_row["unit_cost"] if part_row else 0.0

            # Deduct from truck on-hand
            conn.execute(
                "UPDATE truck_inventory SET quantity = quantity - ? "
                "WHERE truck_id = ? AND part_id = ?",
                (quantity, truck_id, part_id),
            )

            # Add to job_parts (or update existing)
            conn.execute("""
                INSERT INTO job_parts
                    (job_id, part_id, quantity_used, unit_cost_at_use,
                     consumed_from_truck_id, consumed_by, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id, part_id) DO UPDATE SET
                    quantity_used = quantity_used + excluded.quantity_used
            """, (
                job_id, part_id, quantity, unit_cost,
                truck_id, user_id, notes,
            ))

            # Create consumption log entry
            cursor = conn.execute("""
                INSERT INTO consumption_log
                    (job_id, truck_id, part_id, quantity,
                     unit_cost_at_use, consumed_by, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id, truck_id, part_id, quantity,
                unit_cost, user_id, notes,
            ))

            # Check for low warehouse stock and create alert
            stock_row = conn.execute(
                "SELECT part_number, quantity, min_quantity "
                "FROM parts WHERE id = ?",
                (part_id,),
            ).fetchone()
            if stock_row and stock_row["min_quantity"] > 0:
                if stock_row["quantity"] < stock_row["min_quantity"]:
                    deficit = stock_row["min_quantity"] - stock_row["quantity"]
                    conn.execute("""
                        INSERT INTO notifications
                            (user_id, title, message, severity, source)
                        VALUES (NULL, ?, ?, 'warning', 'system')
                    """, (
                        f"Low Stock: {stock_row['part_number']}",
                        f"Warehouse stock for {stock_row['part_number']} "
                        f"is at {stock_row['quantity']} "
                        f"(min: {stock_row['min_quantity']}, "
                        f"need {deficit} more). "
                        f"Consider reordering.",
                    ))

            return cursor.lastrowid

    def get_consumption_log(self, job_id: int = None,
                            truck_id: int = None) -> list[ConsumptionLog]:
        """Get consumption log entries, optionally filtered."""
        conditions = []
        params = []
        if job_id is not None:
            conditions.append("cl.job_id = ?")
            params.append(job_id)
        if truck_id is not None:
            conditions.append("cl.truck_id = ?")
            params.append(truck_id)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self.db.execute(f"""
            SELECT cl.*,
                   p.part_number, p.description AS part_description,
                   t.truck_number, j.job_number,
                   COALESCE(u.display_name, '') AS consumed_by_name
            FROM consumption_log cl
            JOIN parts p ON cl.part_id = p.id
            JOIN trucks t ON cl.truck_id = t.id
            JOIN jobs j ON cl.job_id = j.id
            LEFT JOIN users u ON cl.consumed_by = u.id
            {where}
            ORDER BY cl.consumed_at DESC
        """, tuple(params))
        return [ConsumptionLog(**dict(r)) for r in rows]

    # ── Notifications ───────────────────────────────────────────

    def create_notification(self, notification: Notification) -> int:
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO notifications
                    (user_id, title, message, severity, source)
                VALUES (?, ?, ?, ?, ?)
            """, (
                notification.user_id, notification.title,
                notification.message, notification.severity,
                notification.source,
            ))
            return cursor.lastrowid

    def get_user_notifications(self, user_id: int,
                               unread_only: bool = False,
                               limit: int = 50) -> list[Notification]:
        if unread_only:
            rows = self.db.execute("""
                SELECT * FROM notifications
                WHERE (user_id = ? OR user_id IS NULL) AND is_read = 0
                ORDER BY created_at DESC LIMIT ?
            """, (user_id, limit))
        else:
            rows = self.db.execute("""
                SELECT * FROM notifications
                WHERE user_id = ? OR user_id IS NULL
                ORDER BY created_at DESC LIMIT ?
            """, (user_id, limit))
        return [Notification(**dict(r)) for r in rows]

    def mark_notification_read(self, notification_id: int):
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE notifications SET is_read = 1 WHERE id = ?",
                (notification_id,),
            )

    def mark_all_notifications_read(self, user_id: int):
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE notifications SET is_read = 1 "
                "WHERE (user_id = ? OR user_id IS NULL) AND is_read = 0",
                (user_id,),
            )

    def get_unread_count(self, user_id: int) -> int:
        rows = self.db.execute("""
            SELECT COUNT(*) as cnt FROM notifications
            WHERE (user_id = ? OR user_id IS NULL) AND is_read = 0
        """, (user_id,))
        return rows[0]["cnt"] if rows else 0

    # ── Summaries ───────────────────────────────────────────────

    def get_inventory_summary(self) -> dict:
        rows = self.db.execute("""
            SELECT
                COUNT(*) AS total_parts,
                COALESCE(SUM(quantity), 0) AS total_quantity,
                COALESCE(SUM(quantity * unit_cost), 0) AS total_value,
                COUNT(CASE WHEN quantity < min_quantity AND min_quantity > 0
                      THEN 1 END) AS low_stock_count
            FROM parts
        """)
        return dict(rows[0]) if rows else {}

    def get_job_summary(self, status: Optional[str] = None) -> dict:
        if status and status != "all":
            rows = self.db.execute("""
                SELECT COUNT(*) AS total_jobs,
                       COALESCE(SUM(
                           (SELECT COALESCE(SUM(quantity_used * unit_cost_at_use), 0)
                            FROM job_parts WHERE job_id = jobs.id)
                       ), 0) AS total_cost
                FROM jobs WHERE status = ?
            """, (status,))
        else:
            rows = self.db.execute("""
                SELECT COUNT(*) AS total_jobs,
                       COALESCE(SUM(
                           (SELECT COALESCE(SUM(quantity_used * unit_cost_at_use), 0)
                            FROM job_parts WHERE job_id = jobs.id)
                       ), 0) AS total_cost
                FROM jobs
            """)
        return dict(rows[0]) if rows else {}

    def get_truck_summary(self, truck_id: int) -> dict:
        """Get summary info for a specific truck."""
        inv_rows = self.db.execute("""
            SELECT COUNT(*) AS unique_parts,
                   COALESCE(SUM(ti.quantity), 0) AS total_quantity,
                   COALESCE(SUM(ti.quantity * p.unit_cost), 0) AS total_value
            FROM truck_inventory ti
            JOIN parts p ON ti.part_id = p.id
            WHERE ti.truck_id = ? AND ti.quantity > 0
        """, (truck_id,))
        pending_rows = self.db.execute("""
            SELECT COUNT(*) AS pending_transfers
            FROM truck_transfers
            WHERE truck_id = ? AND status = 'pending'
        """, (truck_id,))

        result = dict(inv_rows[0]) if inv_rows else {}
        if pending_rows:
            result["pending_transfers"] = pending_rows[0]["pending_transfers"]
        return result

    # ── Suppliers ─────────────────────────────────────────────────

    def create_supplier(self, supplier: Supplier) -> int:
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO suppliers
                    (name, contact_name, email, phone, address,
                     notes, preference_score, delivery_schedule, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                supplier.name, supplier.contact_name, supplier.email,
                supplier.phone, supplier.address, supplier.notes,
                supplier.preference_score, supplier.delivery_schedule,
                supplier.is_active,
            ))
            return cursor.lastrowid

    def get_all_suppliers(self, active_only: bool = True) -> list[Supplier]:
        if active_only:
            rows = self.db.execute(
                "SELECT * FROM suppliers WHERE is_active = 1 "
                "ORDER BY preference_score DESC, name"
            )
        else:
            rows = self.db.execute(
                "SELECT * FROM suppliers ORDER BY preference_score DESC, name"
            )
        return [Supplier(**dict(r)) for r in rows]

    def get_supplier_by_id(self, supplier_id: int) -> Optional[Supplier]:
        rows = self.db.execute(
            "SELECT * FROM suppliers WHERE id = ?", (supplier_id,)
        )
        return Supplier(**dict(rows[0])) if rows else None

    def update_supplier(self, supplier: Supplier):
        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE suppliers SET
                    name = ?, contact_name = ?, email = ?, phone = ?,
                    address = ?, notes = ?, preference_score = ?,
                    delivery_schedule = ?, is_active = ?
                WHERE id = ?
            """, (
                supplier.name, supplier.contact_name, supplier.email,
                supplier.phone, supplier.address, supplier.notes,
                supplier.preference_score, supplier.delivery_schedule,
                supplier.is_active, supplier.id,
            ))

    def delete_supplier(self, supplier_id: int):
        with self.db.get_connection() as conn:
            conn.execute(
                "DELETE FROM suppliers WHERE id = ?", (supplier_id,)
            )

    # ── Parts Lists ──────────────────────────────────────────────

    def create_parts_list(self, parts_list: PartsList) -> int:
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO parts_lists
                    (name, list_type, job_id, notes, created_by)
                VALUES (?, ?, ?, ?, ?)
            """, (
                parts_list.name, parts_list.list_type,
                parts_list.job_id, parts_list.notes,
                parts_list.created_by,
            ))
            return cursor.lastrowid

    def get_all_parts_lists(
        self, list_type: Optional[str] = None
    ) -> list[PartsList]:
        if list_type:
            rows = self.db.execute("""
                SELECT pl.*,
                       COALESCE(j.job_number, '') AS job_number,
                       COALESCE(u.display_name, '') AS created_by_name
                FROM parts_lists pl
                LEFT JOIN jobs j ON pl.job_id = j.id
                LEFT JOIN users u ON pl.created_by = u.id
                WHERE pl.list_type = ?
                ORDER BY pl.created_at DESC
            """, (list_type,))
        else:
            rows = self.db.execute("""
                SELECT pl.*,
                       COALESCE(j.job_number, '') AS job_number,
                       COALESCE(u.display_name, '') AS created_by_name
                FROM parts_lists pl
                LEFT JOIN jobs j ON pl.job_id = j.id
                LEFT JOIN users u ON pl.created_by = u.id
                ORDER BY pl.created_at DESC
            """)
        return [PartsList(**dict(r)) for r in rows]

    def get_parts_list_by_id(
        self, list_id: int
    ) -> Optional[PartsList]:
        rows = self.db.execute("""
            SELECT pl.*,
                   COALESCE(j.job_number, '') AS job_number,
                   COALESCE(u.display_name, '') AS created_by_name
            FROM parts_lists pl
            LEFT JOIN jobs j ON pl.job_id = j.id
            LEFT JOIN users u ON pl.created_by = u.id
            WHERE pl.id = ?
        """, (list_id,))
        return PartsList(**dict(rows[0])) if rows else None

    def update_parts_list(self, parts_list: PartsList):
        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE parts_lists SET
                    name = ?, list_type = ?, job_id = ?, notes = ?
                WHERE id = ?
            """, (
                parts_list.name, parts_list.list_type,
                parts_list.job_id, parts_list.notes,
                parts_list.id,
            ))

    def delete_parts_list(self, list_id: int):
        with self.db.get_connection() as conn:
            conn.execute(
                "DELETE FROM parts_lists WHERE id = ?", (list_id,)
            )

    def add_item_to_parts_list(
        self, item: PartsListItem
    ) -> int:
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO parts_list_items
                    (list_id, part_id, quantity, notes)
                VALUES (?, ?, ?, ?)
            """, (
                item.list_id, item.part_id,
                item.quantity, item.notes,
            ))
            return cursor.lastrowid

    def get_parts_list_items(
        self, list_id: int
    ) -> list[PartsListItem]:
        rows = self.db.execute("""
            SELECT pli.*,
                   p.part_number, p.description AS part_description,
                   p.unit_cost
            FROM parts_list_items pli
            JOIN parts p ON pli.part_id = p.id
            WHERE pli.list_id = ?
            ORDER BY p.part_number
        """, (list_id,))
        return [PartsListItem(**dict(r)) for r in rows]

    def remove_item_from_parts_list(self, item_id: int):
        with self.db.get_connection() as conn:
            conn.execute(
                "DELETE FROM parts_list_items WHERE id = ?",
                (item_id,),
            )

    # ── Billing / Reports ────────────────────────────────────────

    def get_billing_data(self, job_id: int,
                         date_from: str = None,
                         date_to: str = None) -> dict:
        """Get comprehensive billing data for a job.

        Returns job info, consumed parts with costs, and totals.
        Optionally filtered by date range for progress billing.
        """
        job = self.get_job_by_id(job_id)
        if not job:
            return {}

        # Get consumption records for the job
        conditions = ["cl.job_id = ?"]
        params: list = [job_id]
        if date_from:
            conditions.append("cl.consumed_at >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("cl.consumed_at <= ?")
            params.append(date_to)

        where = " AND ".join(conditions)
        rows = self.db.execute(f"""
            SELECT cl.*,
                   p.part_number, p.description AS part_description,
                   t.truck_number, j.job_number,
                   COALESCE(u.display_name, '') AS consumed_by_name,
                   COALESCE(c.name, 'Uncategorized') AS category_name
            FROM consumption_log cl
            JOIN parts p ON cl.part_id = p.id
            JOIN trucks t ON cl.truck_id = t.id
            JOIN jobs j ON cl.job_id = j.id
            LEFT JOIN users u ON cl.consumed_by = u.id
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE {where}
            ORDER BY c.name, p.part_number
        """, tuple(params))

        # Also include directly assigned parts (from warehouse)
        jp_rows = self.db.execute("""
            SELECT jp.*, p.part_number, p.description AS part_description,
                   COALESCE(c.name, 'Uncategorized') AS category_name
            FROM job_parts jp
            JOIN parts p ON jp.part_id = p.id
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE jp.job_id = ?
            ORDER BY c.name, p.part_number
        """, (job_id,))

        # Build line items grouped by category
        categories_dict: dict = {}
        subtotal = 0.0

        for r in jp_rows:
            cat = r["category_name"]
            if cat not in categories_dict:
                categories_dict[cat] = []
            line_total = r["quantity_used"] * (r["unit_cost_at_use"] or 0)
            categories_dict[cat].append({
                "part_number": r["part_number"],
                "description": r["part_description"],
                "quantity": r["quantity_used"],
                "unit_cost": r["unit_cost_at_use"] or 0,
                "line_total": line_total,
            })
            subtotal += line_total

        # Get assigned users
        assignments = self.get_job_assignments(job_id)

        return {
            "job": {
                "job_number": job.job_number,
                "name": job.name,
                "customer": job.customer or "",
                "address": job.address or "",
                "status": job.status,
                "priority": job.priority,
                "created_at": str(job.created_at or ""),
                "completed_at": str(job.completed_at or ""),
            },
            "date_range": {
                "from": date_from or "",
                "to": date_to or "",
            },
            "categories": categories_dict,
            "subtotal": subtotal,
            "assigned_users": [
                {
                    "name": a.user_name,
                    "role": a.role,
                }
                for a in assignments
            ],
            "consumption_count": len(rows),
        }
