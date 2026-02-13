"""Repository layer — all CRUD operations and queries."""

import hashlib
from typing import Optional

from .connection import DatabaseConnection
from .models import (
    Brand,
    Category,
    ConsumptionLog,
    Hat,
    Job,
    JobAssignment,
    JobLocation,
    JobNotebook,
    JobPart,
    LaborEntry,
    NotebookAttachment,
    NotebookPage,
    NotebookSection,
    Notification,
    Part,
    PartsList,
    PartsListItem,
    PartSupplier,
    PartVariant,
    PurchaseOrder,
    PurchaseOrderItem,
    ReceiveLogEntry,
    ReturnAuthorization,
    ReturnAuthorizationItem,
    Supplier,
    Truck,
    TruckInventory,
    TruckTransfer,
    User,
    UserHat,
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

    _PARTS_SELECT = """
        SELECT p.*,
               COALESCE(c.name, '') AS category_name,
               COALESCE(b.name, '') AS brand_name
        FROM parts p
        LEFT JOIN categories c ON p.category_id = c.id
        LEFT JOIN brands b ON p.brand_id = b.id
    """

    def get_all_parts(self) -> list[Part]:
        rows = self.db.execute(
            self._PARTS_SELECT + " ORDER BY p.part_number"
        )
        return [Part(**dict(r)) for r in rows]

    def get_part_by_id(self, part_id: int) -> Optional[Part]:
        rows = self.db.execute(
            self._PARTS_SELECT + " WHERE p.id = ?", (part_id,)
        )
        return Part(**dict(rows[0])) if rows else None

    def get_part_by_number(self, part_number: str) -> Optional[Part]:
        rows = self.db.execute(
            self._PARTS_SELECT + " WHERE p.part_number = ?",
            (part_number,),
        )
        return Part(**dict(rows[0])) if rows else None

    def search_parts(self, query: str) -> list[Part]:
        """Search parts by keyword across multiple fields."""
        if not query.strip():
            return self.get_all_parts()
        pattern = f"%{query.strip()}%"
        rows = self.db.execute(
            self._PARTS_SELECT + """
            WHERE p.part_number LIKE ?
               OR p.description LIKE ?
               OR p.name LIKE ?
               OR p.location LIKE ?
               OR p.supplier LIKE ?
               OR p.notes LIKE ?
               OR p.brand_part_number LIKE ?
               OR p.local_part_number LIKE ?
               OR p.subcategory LIKE ?
               OR COALESCE(b.name, '') LIKE ?
            ORDER BY p.name, p.part_number
        """, (pattern,) * 10)
        return [Part(**dict(r)) for r in rows]

    def get_parts_by_category(self, category_id: int) -> list[Part]:
        rows = self.db.execute(
            self._PARTS_SELECT + """
            WHERE p.category_id = ?
            ORDER BY p.part_number
        """, (category_id,))
        return [Part(**dict(r)) for r in rows]

    def get_low_stock_parts(self) -> list[Part]:
        rows = self.db.execute(
            self._PARTS_SELECT + """
            WHERE p.quantity < p.min_quantity AND p.min_quantity > 0
            ORDER BY (p.min_quantity - p.quantity) DESC
        """)
        return [Part(**dict(r)) for r in rows]

    def get_parts_by_type(self, part_type: str) -> list[Part]:
        """Get all parts of a specific type ('general' or 'specific')."""
        rows = self.db.execute(
            self._PARTS_SELECT + """
            WHERE p.part_type = ?
            ORDER BY p.part_number
        """, (part_type,))
        return [Part(**dict(r)) for r in rows]

    def get_parts_by_brand(self, brand_id: int) -> list[Part]:
        """Get all parts linked to a specific brand."""
        rows = self.db.execute(
            self._PARTS_SELECT + """
            WHERE p.brand_id = ?
            ORDER BY p.part_number
        """, (brand_id,))
        return [Part(**dict(r)) for r in rows]

    def get_parts_needing_qr_tags(self) -> list[Part]:
        """Get all parts that don't have a QR tag printed."""
        rows = self.db.execute(
            self._PARTS_SELECT + """
            WHERE p.has_qr_tag = 0
            ORDER BY p.part_number
        """)
        return [Part(**dict(r)) for r in rows]

    def get_incomplete_parts_count(self) -> int:
        """Count parts with incomplete required data (type-aware)."""
        rows = self.db.execute("""
            SELECT COUNT(*) as cnt FROM parts
            WHERE name = '' OR name IS NULL
               OR unit_cost <= 0
               OR category_id IS NULL
               OR (part_type = 'specific' AND (
                   (part_number = '' OR part_number IS NULL)
                   OR brand_id IS NULL
                   OR brand_part_number = ''
                   OR brand_part_number IS NULL
               ))
        """)
        return rows[0]["cnt"] if rows else 0

    def generate_local_part_number(self) -> str:
        """Generate the next local part number (e.g. LP-0001)."""
        from wired_part.config import Config
        prefix = Config.LOCAL_PN_PREFIX
        rows = self.db.execute("""
            SELECT local_part_number FROM parts
            WHERE local_part_number LIKE ?
            ORDER BY local_part_number DESC LIMIT 1
        """, (f"{prefix}-%",))
        if rows and rows[0]["local_part_number"]:
            last = rows[0]["local_part_number"]
            try:
                num = int(last.split("-", 1)[1]) + 1
            except (ValueError, IndexError):
                num = 1
        else:
            num = 1
        return f"{prefix}-{num:04d}"

    def create_part(self, part: Part) -> int:
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO parts
                    (part_number, description, quantity, location,
                     category_id, unit_cost, min_quantity, max_quantity,
                     supplier, notes, name,
                     part_type, brand_id, brand_part_number,
                     local_part_number, image_path, subcategory,
                     color_options, type_style, has_qr_tag, pdfs)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                part.part_number, part.description, part.quantity,
                part.location, part.category_id, part.unit_cost,
                part.min_quantity, part.max_quantity,
                part.supplier, part.notes, part.name,
                part.part_type, part.brand_id, part.brand_part_number,
                part.local_part_number, part.image_path, part.subcategory,
                part.color_options, part.type_style, part.has_qr_tag,
                part.pdfs,
            ))
            return cursor.lastrowid

    def update_part(self, part: Part):
        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE parts SET
                    part_number = ?, description = ?, quantity = ?,
                    location = ?, category_id = ?, unit_cost = ?,
                    min_quantity = ?, max_quantity = ?,
                    supplier = ?, notes = ?, name = ?,
                    part_type = ?, brand_id = ?, brand_part_number = ?,
                    local_part_number = ?, image_path = ?, subcategory = ?,
                    color_options = ?, type_style = ?, has_qr_tag = ?,
                    pdfs = ?, deprecation_status = ?,
                    deprecation_started_at = ?
                WHERE id = ?
            """, (
                part.part_number, part.description, part.quantity,
                part.location, part.category_id, part.unit_cost,
                part.min_quantity, part.max_quantity,
                part.supplier, part.notes, part.name,
                part.part_type, part.brand_id, part.brand_part_number,
                part.local_part_number, part.image_path, part.subcategory,
                part.color_options, part.type_style, part.has_qr_tag,
                part.pdfs, part.deprecation_status,
                part.deprecation_started_at, part.id,
            ))
        self._try_advance_if_deprecating(part.id)

    def delete_part(self, part_id: int):
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM parts WHERE id = ?", (part_id,))

    # ── Brands ────────────────────────────────────────────────────

    def create_brand(self, brand: Brand) -> int:
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO brands (name, website, notes)
                VALUES (?, ?, ?)
            """, (brand.name, brand.website, brand.notes))
            return cursor.lastrowid

    def get_all_brands(self) -> list[Brand]:
        rows = self.db.execute(
            "SELECT * FROM brands ORDER BY name"
        )
        return [Brand(**dict(r)) for r in rows]

    def get_brand_by_id(self, brand_id: int) -> Optional[Brand]:
        rows = self.db.execute(
            "SELECT * FROM brands WHERE id = ?", (brand_id,)
        )
        return Brand(**dict(rows[0])) if rows else None

    def get_brand_by_name(self, name: str) -> Optional[Brand]:
        rows = self.db.execute(
            "SELECT * FROM brands WHERE name = ?", (name,)
        )
        return Brand(**dict(rows[0])) if rows else None

    def update_brand(self, brand: Brand):
        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE brands SET name = ?, website = ?, notes = ?
                WHERE id = ?
            """, (brand.name, brand.website, brand.notes, brand.id))

    def delete_brand(self, brand_id: int):
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM brands WHERE id = ?", (brand_id,))

    # ── Part-Supplier links ──────────────────────────────────────

    def link_part_supplier(self, ps: PartSupplier) -> int:
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO part_suppliers
                    (part_id, supplier_id, supplier_part_number, notes)
                VALUES (?, ?, ?, ?)
            """, (ps.part_id, ps.supplier_id,
                  ps.supplier_part_number, ps.notes))
            return cursor.lastrowid

    def unlink_part_supplier(self, part_id: int, supplier_id: int):
        with self.db.get_connection() as conn:
            conn.execute("""
                DELETE FROM part_suppliers
                WHERE part_id = ? AND supplier_id = ?
            """, (part_id, supplier_id))

    def get_part_suppliers(self, part_id: int) -> list[PartSupplier]:
        """Get all suppliers linked to a part."""
        rows = self.db.execute("""
            SELECT ps.*, COALESCE(s.name, '') AS supplier_name
            FROM part_suppliers ps
            LEFT JOIN suppliers s ON ps.supplier_id = s.id
            WHERE ps.part_id = ?
            ORDER BY s.name
        """, (part_id,))
        return [PartSupplier(**dict(r)) for r in rows]

    def get_supplier_parts(self, supplier_id: int) -> list[PartSupplier]:
        """Get all parts linked to a supplier."""
        rows = self.db.execute("""
            SELECT ps.*, COALESCE(s.name, '') AS supplier_name
            FROM part_suppliers ps
            LEFT JOIN suppliers s ON ps.supplier_id = s.id
            WHERE ps.supplier_id = ?
            ORDER BY ps.part_id
        """, (supplier_id,))
        return [PartSupplier(**dict(r)) for r in rows]

    # ── Part Variants ────────────────────────────────────────────

    def create_part_variant(self, variant: PartVariant) -> int:
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO part_variants
                    (part_id, type_style, color_finish,
                     brand_part_number, image_path, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (variant.part_id, variant.type_style,
                  variant.color_finish, variant.brand_part_number,
                  variant.image_path, variant.notes))
            return cursor.lastrowid

    def get_part_variants(self, part_id: int) -> list[PartVariant]:
        rows = self.db.execute("""
            SELECT * FROM part_variants
            WHERE part_id = ?
            ORDER BY type_style, color_finish
        """, (part_id,))
        return [PartVariant(**dict(r)) for r in rows]

    def get_part_variant_by_id(self, variant_id: int) -> Optional[PartVariant]:
        rows = self.db.execute(
            "SELECT * FROM part_variants WHERE id = ?", (variant_id,)
        )
        return PartVariant(**dict(rows[0])) if rows else None

    def update_part_variant(self, variant: PartVariant):
        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE part_variants SET
                    type_style = ?, color_finish = ?,
                    brand_part_number = ?,
                    image_path = ?, notes = ?
                WHERE id = ?
            """, (variant.type_style, variant.color_finish,
                  variant.brand_part_number,
                  variant.image_path, variant.notes, variant.id))

    def delete_part_variant(self, variant_id: int):
        with self.db.get_connection() as conn:
            conn.execute(
                "DELETE FROM part_variants WHERE id = ?", (variant_id,)
            )

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
                     priority, notes, bill_out_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.job_number, job.name, job.customer,
                job.address, job.status, job.priority, job.notes,
                job.bill_out_rate,
            ))
            return cursor.lastrowid

    def update_job(self, job: Job):
        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE jobs SET
                    job_number = ?, name = ?, customer = ?,
                    address = ?, status = ?, priority = ?,
                    notes = ?, bill_out_rate = ?, completed_at = ?
                WHERE id = ?
            """, (
                job.job_number, job.name, job.customer,
                job.address, job.status, job.priority,
                job.notes, job.bill_out_rate, job.completed_at,
                job.id,
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

    def get_trucks_for_job(self, job_id: int) -> list[Truck]:
        """Get active trucks whose assigned user is also assigned to this job.

        Only trucks owned by users who are assigned to the same job
        will appear in the consume-from-truck dropdown.
        """
        rows = self.db.execute("""
            SELECT t.*, COALESCE(u.display_name, '') AS assigned_user_name
            FROM trucks t
            LEFT JOIN users u ON t.assigned_user_id = u.id
            WHERE t.is_active = 1
              AND t.assigned_user_id IN (
                  SELECT user_id FROM job_assignments WHERE job_id = ?
              )
            ORDER BY t.truck_number
        """, (job_id,))
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

    def add_to_truck_inventory(
        self, truck_id: int, part_id: int, quantity: int,
    ):
        """Directly add/upsert quantity into truck on-hand inventory."""
        self.db.execute("""
            INSERT INTO truck_inventory (truck_id, part_id, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(truck_id, part_id) DO UPDATE SET
                quantity = quantity + excluded.quantity
        """, (truck_id, part_id, quantity))

    def set_truck_inventory_levels(
        self, truck_id: int, part_id: int,
        min_quantity: int = 0, max_quantity: int = 0,
    ):
        """Set min/max stock levels for a part on a truck."""
        self.db.execute("""
            UPDATE truck_inventory
            SET min_quantity = ?, max_quantity = ?
            WHERE truck_id = ? AND part_id = ?
        """, (min_quantity, max_quantity, truck_id, part_id))

    def set_truck_inventory_quantity(
        self, truck_id: int, part_id: int, quantity: int,
    ):
        """Directly set current quantity (does NOT affect warehouse)."""
        self.db.execute("""
            INSERT INTO truck_inventory (truck_id, part_id, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(truck_id, part_id) DO UPDATE SET
                quantity = excluded.quantity
        """, (truck_id, part_id, quantity))

    def get_truck_inventory_with_levels(
        self, truck_id: int,
    ) -> list[TruckInventory]:
        """Get truck inventory including min/max levels (all items, even 0)."""
        rows = self.db.execute("""
            SELECT ti.*, p.part_number, p.description AS part_description,
                   p.unit_cost, t.truck_number
            FROM truck_inventory ti
            JOIN parts p ON ti.part_id = p.id
            JOIN trucks t ON ti.truck_id = t.id
            WHERE ti.truck_id = ?
            ORDER BY p.part_number
        """, (truck_id,))
        return [TruckInventory(**dict(r)) for r in rows]

    # ── Truck Transfers ─────────────────────────────────────────

    def create_transfer(self, transfer: TruckTransfer) -> int:
        """Create an outbound transfer (warehouse -> truck).

        Immediately deducts from warehouse stock. Transfer starts as 'pending'.
        If supplier_id/source_order_id are set on the transfer, they are
        preserved for supply chain traceability (v12).
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

            # v12: If no supplier set, try to find the most recent supplier
            # for this part from the receive log
            supplier_id = transfer.supplier_id
            source_order_id = transfer.source_order_id
            if not supplier_id:
                recent = conn.execute("""
                    SELECT rl.supplier_id, poi.order_id
                    FROM receive_log rl
                    JOIN purchase_order_items poi
                        ON rl.order_item_id = poi.id
                    WHERE poi.part_id = ? AND rl.supplier_id IS NOT NULL
                    ORDER BY rl.received_at DESC LIMIT 1
                """, (transfer.part_id,)).fetchone()
                if recent:
                    supplier_id = recent["supplier_id"]
                    source_order_id = recent["order_id"]

            # Create transfer record (v12: with supplier tracking)
            cursor = conn.execute("""
                INSERT INTO truck_transfers
                    (truck_id, part_id, quantity, direction, status,
                     created_by, notes, source_order_id, supplier_id)
                VALUES (?, ?, ?, 'outbound', 'pending', ?, ?, ?, ?)
            """, (
                transfer.truck_id, transfer.part_id, transfer.quantity,
                transfer.created_by, transfer.notes,
                source_order_id, supplier_id,
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
            _part_id = row["part_id"]
        self._try_advance_if_deprecating(_part_id)

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
            transfer_id = cursor.lastrowid
        self._try_advance_if_deprecating(part_id)
        return transfer_id

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

    def get_recent_returns(self, limit: int = 50) -> list[TruckTransfer]:
        """Get recently completed return transfers."""
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
            WHERE tt.direction = 'return'
            ORDER BY tt.created_at DESC
            LIMIT ?
        """, (limit,))
        return [TruckTransfer(**dict(r)) for r in rows]

    # ── Part Consumption (Truck -> Job) ─────────────────────────

    def consume_from_truck(self, job_id: int, truck_id: int, part_id: int,
                           quantity: int, user_id: int = None,
                           notes: str = "") -> int:
        """Consume parts from a truck's on-hand inventory for a job.

        Deducts from truck_inventory, creates job_parts record and
        consumption_log entry. Propagates supplier origin from the
        most recent truck transfer for this part (v12).
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

            # v12: Look up supplier origin from most recent received
            # transfer for this part on this truck
            supplier_row = conn.execute("""
                SELECT supplier_id, source_order_id
                FROM truck_transfers
                WHERE truck_id = ? AND part_id = ?
                  AND status = 'received' AND direction = 'outbound'
                  AND supplier_id IS NOT NULL
                ORDER BY received_at DESC LIMIT 1
            """, (truck_id, part_id)).fetchone()
            supplier_id = supplier_row["supplier_id"] if supplier_row else None
            source_order_id = (
                supplier_row["source_order_id"] if supplier_row else None
            )

            # Deduct from truck on-hand
            conn.execute(
                "UPDATE truck_inventory SET quantity = quantity - ? "
                "WHERE truck_id = ? AND part_id = ?",
                (quantity, truck_id, part_id),
            )

            # v12: Enforce one-supplier-per-part-per-job rule
            existing_jp = conn.execute(
                "SELECT supplier_id FROM job_parts "
                "WHERE job_id = ? AND part_id = ?",
                (job_id, part_id),
            ).fetchone()
            if (existing_jp and existing_jp["supplier_id"]
                    and supplier_id
                    and existing_jp["supplier_id"] != supplier_id):
                raise ValueError(
                    f"Supplier conflict: part {part_id} on job "
                    f"{job_id} is already supplied by supplier "
                    f"{existing_jp['supplier_id']}; cannot consume "
                    f"from supplier {supplier_id}. A part must "
                    f"come from the same supplier for the entire job."
                )

            # Add to job_parts (or update existing) — v12: with supplier
            conn.execute("""
                INSERT INTO job_parts
                    (job_id, part_id, quantity_used, unit_cost_at_use,
                     consumed_from_truck_id, consumed_by,
                     supplier_id, source_order_id, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id, part_id) DO UPDATE SET
                    quantity_used = quantity_used + excluded.quantity_used,
                    supplier_id = COALESCE(excluded.supplier_id,
                                           job_parts.supplier_id),
                    source_order_id = COALESCE(excluded.source_order_id,
                                               job_parts.source_order_id)
            """, (
                job_id, part_id, quantity, unit_cost,
                truck_id, user_id, supplier_id, source_order_id, notes,
            ))

            # Create consumption log entry — v12: with supplier
            cursor = conn.execute("""
                INSERT INTO consumption_log
                    (job_id, truck_id, part_id, quantity,
                     unit_cost_at_use, consumed_by,
                     supplier_id, source_order_id, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id, truck_id, part_id, quantity,
                unit_cost, user_id,
                supplier_id, source_order_id, notes,
            ))

            # Notify truck owner if someone else consumed from their truck
            truck_row = conn.execute(
                "SELECT t.assigned_user_id, t.truck_number, t.name, "
                "       u.display_name AS owner_name "
                "FROM trucks t "
                "LEFT JOIN users u ON t.assigned_user_id = u.id "
                "WHERE t.id = ?",
                (truck_id,),
            ).fetchone()
            if (truck_row and truck_row["assigned_user_id"]
                    and user_id
                    and truck_row["assigned_user_id"] != user_id):
                # Get consuming user's name and part info
                consumer_row = conn.execute(
                    "SELECT display_name FROM users WHERE id = ?",
                    (user_id,),
                ).fetchone()
                consumer_name = (consumer_row["display_name"]
                                 if consumer_row else "Unknown")
                part_info = conn.execute(
                    "SELECT part_number, name FROM parts WHERE id = ?",
                    (part_id,),
                ).fetchone()
                part_desc = (f"{part_info['part_number']} "
                             f"({part_info['name']})"
                             if part_info else f"Part #{part_id}")
                job_row = conn.execute(
                    "SELECT job_number, name FROM jobs WHERE id = ?",
                    (job_id,),
                ).fetchone()
                job_desc = (f"{job_row['job_number']} - {job_row['name']}"
                            if job_row else f"Job #{job_id}")
                truck_desc = (f"{truck_row['truck_number']} "
                              f"({truck_row['name']})")
                conn.execute("""
                    INSERT INTO notifications
                        (user_id, title, message, severity, source,
                         target_tab, target_data)
                    VALUES (?, ?, ?, 'info', 'system', ?, ?)
                """, (
                    truck_row["assigned_user_id"],
                    f"Parts consumed from your truck {truck_desc}",
                    f"{consumer_name} consumed {quantity}x {part_desc} "
                    f"from your truck {truck_desc} for job {job_desc}.",
                    "trucks",
                    f'{{"truck_id": {truck_id}}}',
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

            log_id = cursor.lastrowid
        self._try_advance_if_deprecating(part_id)
        return log_id

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
                    (user_id, title, message, severity, source,
                     target_tab, target_data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                notification.user_id, notification.title,
                notification.message, notification.severity,
                notification.source,
                notification.target_tab or "",
                notification.target_data or "",
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
                     notes, preference_score, delivery_schedule,
                     is_supply_house, operating_hours, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                supplier.name, supplier.contact_name, supplier.email,
                supplier.phone, supplier.address, supplier.notes,
                supplier.preference_score, supplier.delivery_schedule,
                supplier.is_supply_house, supplier.operating_hours,
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
                    delivery_schedule = ?, is_supply_house = ?,
                    operating_hours = ?, is_active = ?
                WHERE id = ?
            """, (
                supplier.name, supplier.contact_name, supplier.email,
                supplier.phone, supplier.address, supplier.notes,
                supplier.preference_score, supplier.delivery_schedule,
                supplier.is_supply_house, supplier.operating_hours,
                supplier.is_active, supplier.id,
            ))

    def delete_supplier(self, supplier_id: int):
        with self.db.get_connection() as conn:
            conn.execute(
                "DELETE FROM suppliers WHERE id = ?", (supplier_id,)
            )

    # ── Inventory Audits ────────────────────────────────────────

    def get_audit_items(
        self, audit_type: str, target_id: int = None,
        limit: int = 10
    ) -> list[dict]:
        """Get items to audit, sorted by oldest audit.

        audit_type: 'warehouse', 'truck', or 'job'
        target_id: truck_id or job_id (None for warehouse)
        limit: number of items (10, 25, or 0 for all)
        """
        if audit_type == "warehouse":
            query = """
                SELECT p.id AS part_id, p.part_number,
                       p.description AS name,
                       p.quantity AS expected_quantity,
                       p.image_path, p.location,
                       MAX(ia.audited_at) AS last_audited
                FROM parts p
                LEFT JOIN inventory_audits ia
                    ON ia.part_id = p.id
                    AND ia.audit_type = 'warehouse'
                WHERE p.quantity > 0
                GROUP BY p.id
                ORDER BY last_audited ASC NULLS FIRST
            """
            params: tuple = ()
        elif audit_type == "truck":
            query = """
                SELECT ti.part_id, p.part_number,
                       p.description AS name,
                       ti.quantity AS expected_quantity,
                       p.image_path, p.location,
                       MAX(ia.audited_at) AS last_audited
                FROM truck_inventory ti
                JOIN parts p ON ti.part_id = p.id
                LEFT JOIN inventory_audits ia
                    ON ia.part_id = ti.part_id
                    AND ia.audit_type = 'truck'
                    AND ia.target_id = ?
                WHERE ti.truck_id = ? AND ti.quantity > 0
                GROUP BY ti.part_id
                ORDER BY last_audited ASC NULLS FIRST
            """
            params = (target_id, target_id)
        else:  # job
            query = """
                SELECT jp.part_id, p.part_number,
                       p.description AS name,
                       jp.quantity_used AS expected_quantity,
                       p.image_path, p.location,
                       MAX(ia.audited_at) AS last_audited
                FROM job_parts jp
                JOIN parts p ON jp.part_id = p.id
                LEFT JOIN inventory_audits ia
                    ON ia.part_id = jp.part_id
                    AND ia.audit_type = 'job'
                    AND ia.target_id = ?
                WHERE jp.job_id = ?
                GROUP BY jp.part_id
                ORDER BY last_audited ASC NULLS FIRST
            """
            params = (target_id, target_id)

        if limit > 0:
            query += f" LIMIT {limit}"

        rows = self.db.execute(query, params)
        return [dict(r) for r in rows]

    def record_audit_result(
        self, audit_type: str, target_id: int,
        part_id: int, expected_quantity: int,
        actual_quantity: int, status: str,
        audited_by: int = None
    ) -> int:
        """Record a single audit result."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO inventory_audits
                    (audit_type, target_id, part_id,
                     expected_quantity, actual_quantity,
                     status, audited_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                audit_type, target_id, part_id,
                expected_quantity, actual_quantity,
                status, audited_by,
            ))
            return cursor.lastrowid

    def get_audit_summary(
        self, audit_type: str, target_id: int = None
    ) -> dict:
        """Get audit summary: last audit date, discrepancy count."""
        if target_id:
            rows = self.db.execute("""
                SELECT MAX(audited_at) AS last_audit,
                       COUNT(CASE WHEN status = 'discrepancy' THEN 1 END)
                           AS discrepancy_count,
                       COUNT(CASE WHEN status = 'confirmed' THEN 1 END)
                           AS confirmed_count,
                       COUNT(CASE WHEN status = 'skipped' THEN 1 END)
                           AS skipped_count,
                       COUNT(*) AS total_count
                FROM inventory_audits
                WHERE audit_type = ? AND target_id = ?
            """, (audit_type, target_id))
        else:
            rows = self.db.execute("""
                SELECT MAX(audited_at) AS last_audit,
                       COUNT(CASE WHEN status = 'discrepancy' THEN 1 END)
                           AS discrepancy_count,
                       COUNT(CASE WHEN status = 'confirmed' THEN 1 END)
                           AS confirmed_count,
                       COUNT(CASE WHEN status = 'skipped' THEN 1 END)
                           AS skipped_count,
                       COUNT(*) AS total_count
                FROM inventory_audits
                WHERE audit_type = ?
            """, (audit_type,))

        if rows:
            return dict(rows[0])
        return {
            "last_audit": None,
            "discrepancy_count": 0,
            "confirmed_count": 0,
            "skipped_count": 0,
            "total_count": 0,
        }

    # ── Part Deprecation ────────────────────────────────────────

    def start_part_deprecation(self, part_id: int):
        """Begin the deprecation pipeline for a part."""
        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE parts
                SET deprecation_status = 'pending',
                    deprecation_started_at = CURRENT_TIMESTAMP
                WHERE id = ? AND deprecation_status IS NULL
            """, (part_id,))

    def check_deprecation_progress(self, part_id: int) -> dict:
        """Check the current state of a part's deprecation."""
        # Count open jobs that have this part AND how many units
        job_rows = self.db.execute("""
            SELECT COUNT(DISTINCT jp.job_id) AS job_count,
                   COALESCE(SUM(jp.quantity_used), 0) AS job_qty
            FROM job_parts jp
            JOIN jobs j ON jp.job_id = j.id
            WHERE jp.part_id = ? AND j.status IN ('active', 'on_hold')
        """, (part_id,))
        open_job_count = job_rows[0]["job_count"] if job_rows else 0
        job_quantity = job_rows[0]["job_qty"] if job_rows else 0

        # Count truck inventory
        truck_rows = self.db.execute("""
            SELECT COALESCE(SUM(quantity), 0) AS qty
            FROM truck_inventory
            WHERE part_id = ?
        """, (part_id,))
        truck_qty = truck_rows[0]["qty"] if truck_rows else 0

        # Warehouse qty
        part = self.get_part_by_id(part_id)
        warehouse_qty = part.quantity if part else 0

        return {
            "open_jobs": open_job_count,
            "job_quantity": job_quantity,
            "truck_quantity": truck_qty,
            "warehouse_quantity": warehouse_qty,
            "deprecation_status": part.deprecation_status if part else None,
        }

    def advance_deprecation(self, part_id: int) -> str:
        """Try to advance a part's deprecation as far as possible.

        Loops through all stages until blocked or fully archived.
        Returns the final status after all possible advances.

        Pipeline:
          pending → winding_down (all open jobs closed or part removed)
          winding_down → zero_stock (truck qty = 0)
          zero_stock → archived (warehouse qty = 0)
        """
        # Loop so we advance through multiple stages in one call
        # when conditions are already met (e.g. qty already 0)
        for _ in range(4):  # max 4 iterations (safety bound)
            progress = self.check_deprecation_progress(part_id)
            current = progress["deprecation_status"]

            if current == "pending" and progress["job_quantity"] == 0:
                with self.db.get_connection() as conn:
                    conn.execute(
                        "UPDATE parts SET deprecation_status = 'winding_down' "
                        "WHERE id = ?", (part_id,)
                    )
                continue  # Try next stage

            elif current == "winding_down" and progress["truck_quantity"] == 0:
                with self.db.get_connection() as conn:
                    conn.execute(
                        "UPDATE parts SET deprecation_status = 'zero_stock' "
                        "WHERE id = ?", (part_id,)
                    )
                continue  # Try next stage

            elif current == "zero_stock" and progress["warehouse_quantity"] == 0:
                with self.db.get_connection() as conn:
                    conn.execute(
                        "UPDATE parts SET deprecation_status = 'archived' "
                        "WHERE id = ?", (part_id,)
                    )
                return "archived"

            else:
                # Can't advance further
                break

        # Re-check final status
        final = self.check_deprecation_progress(part_id)
        return final["deprecation_status"] or ""

    def _try_advance_if_deprecating(self, part_id: int):
        """Auto-advance deprecation if the part is in the pipeline.

        Called automatically whenever part inventory changes
        (update_part, receive_transfer, return_to_warehouse,
        consume_from_truck) so the deprecation pipeline stays current.
        """
        try:
            part = self.get_part_by_id(part_id)
            if part and part.deprecation_status and \
               part.deprecation_status != "archived":
                self.advance_deprecation(part_id)
        except Exception:
            pass  # Never let deprecation logic break normal operations

    def cancel_deprecation(self, part_id: int):
        """Cancel an in-progress deprecation."""
        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE parts
                SET deprecation_status = NULL,
                    deprecation_started_at = NULL
                WHERE id = ? AND deprecation_status != 'archived'
            """, (part_id,))

    def get_deprecated_parts(self) -> list[Part]:
        """Get all parts with an active deprecation status."""
        rows = self.db.execute(
            self._PARTS_SELECT
            + " WHERE p.deprecation_status IS NOT NULL "
            "ORDER BY p.deprecation_started_at"
        )
        return [Part(**{
            k: r[k] for k in r.keys()
            if k in Part.__dataclass_fields__
        }) for r in rows]

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

    # ── Billing Cycles & Periods ────────────────────────────────

    def get_or_create_billing_cycle(
        self, job_id: int = None, cycle_type: str = "monthly",
        billing_day: int = 1
    ) -> "BillingCycle":
        """Get existing billing cycle for a job, or create one."""
        from wired_part.database.models import BillingCycle
        if job_id:
            rows = self.db.execute(
                "SELECT * FROM billing_cycles WHERE job_id = ?",
                (job_id,),
            )
        else:
            rows = self.db.execute(
                "SELECT * FROM billing_cycles WHERE job_id IS NULL",
            )
        if rows:
            return BillingCycle(**{
                k: rows[0][k] for k in rows[0].keys()
                if k in BillingCycle.__dataclass_fields__
            })
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO billing_cycles (job_id, cycle_type, billing_day)
                VALUES (?, ?, ?)
            """, (job_id, cycle_type, billing_day))
            return BillingCycle(
                id=cursor.lastrowid, job_id=job_id,
                cycle_type=cycle_type, billing_day=billing_day,
            )

    def get_billing_cycles(self) -> list:
        """Get all billing cycles with optional job info."""
        from wired_part.database.models import BillingCycle
        rows = self.db.execute("""
            SELECT bc.*,
                   COALESCE(j.job_number, '') AS job_number,
                   COALESCE(j.name, '') AS job_name
            FROM billing_cycles bc
            LEFT JOIN jobs j ON bc.job_id = j.id
            ORDER BY bc.created_at DESC
        """)
        return [BillingCycle(**{
            k: r[k] for k in r.keys()
            if k in BillingCycle.__dataclass_fields__
        }) for r in rows]

    def create_billing_period(
        self, cycle_id: int, period_start: str, period_end: str
    ) -> int:
        """Create a new billing period for a cycle."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO billing_periods
                    (billing_cycle_id, period_start, period_end)
                VALUES (?, ?, ?)
            """, (cycle_id, period_start, period_end))
            return cursor.lastrowid

    def get_billing_periods(self, cycle_id: int) -> list:
        """Get all billing periods for a cycle."""
        from wired_part.database.models import BillingPeriod
        rows = self.db.execute("""
            SELECT bp.*,
                   bc.cycle_type,
                   bc.job_id,
                   COALESCE(j.job_number, '') AS job_number
            FROM billing_periods bp
            JOIN billing_cycles bc ON bp.billing_cycle_id = bc.id
            LEFT JOIN jobs j ON bc.job_id = j.id
            WHERE bp.billing_cycle_id = ?
            ORDER BY bp.period_start DESC
        """, (cycle_id,))
        return [BillingPeriod(**{
            k: r[k] for k in r.keys()
            if k in BillingPeriod.__dataclass_fields__
        }) for r in rows]

    def close_billing_period(self, period_id: int):
        """Close a billing period, calculating totals."""
        from wired_part.database.models import BillingPeriod
        rows = self.db.execute(
            "SELECT bp.*, bc.job_id, bc.cycle_type, "
            "COALESCE(j.job_number, '') AS job_number "
            "FROM billing_periods bp "
            "JOIN billing_cycles bc ON bp.billing_cycle_id = bc.id "
            "LEFT JOIN jobs j ON bc.job_id = j.id "
            "WHERE bp.id = ?", (period_id,)
        )
        if not rows:
            raise ValueError(f"Billing period {period_id} not found")
        period = BillingPeriod(**{
            k: rows[0][k] for k in rows[0].keys()
            if k in BillingPeriod.__dataclass_fields__
        })

        # Calculate total parts cost for period
        job_id = rows[0]["job_id"]
        if job_id:
            billing = self.get_billing_data(
                job_id, period.period_start, period.period_end
            )
            total_parts = billing.get("subtotal", 0.0)

            labor_summary = self.get_labor_summary_for_job(job_id)
            total_hours = labor_summary.get("total_hours", 0.0)
        else:
            total_parts = 0.0
            total_hours = 0.0

        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE billing_periods
                SET status = 'closed',
                    total_parts_cost = ?,
                    total_hours = ?
                WHERE id = ?
            """, (total_parts, total_hours, period_id))

    def get_billing_data_for_period(
        self, job_id: int, period_start: str, period_end: str
    ) -> dict:
        """Get billing data filtered by a specific period."""
        return self.get_billing_data(job_id, period_start, period_end)

    # ── Labor Entries ─────────────────────────────────────────────

    def create_labor_entry(self, entry: LaborEntry) -> int:
        with self.db.get_connection() as conn:
            # Snapshot the job's current BRO at time of entry creation
            bro = entry.bill_out_rate
            if not bro and entry.job_id:
                job_row = conn.execute(
                    "SELECT bill_out_rate FROM jobs WHERE id = ?",
                    (entry.job_id,),
                ).fetchone()
                if job_row:
                    bro = job_row["bill_out_rate"] or ""

            cursor = conn.execute("""
                INSERT INTO labor_entries
                    (user_id, job_id, start_time, end_time, hours,
                     description, sub_task_category, photos,
                     clock_in_lat, clock_in_lon, clock_out_lat, clock_out_lon,
                     is_overtime, bill_out_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.user_id, entry.job_id, entry.start_time,
                entry.end_time, entry.hours, entry.description,
                entry.sub_task_category, entry.photos,
                entry.clock_in_lat, entry.clock_in_lon,
                entry.clock_out_lat, entry.clock_out_lon,
                entry.is_overtime, bro,
            ))
            return cursor.lastrowid

    def update_labor_entry(self, entry: LaborEntry):
        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE labor_entries SET
                    user_id = ?, job_id = ?, start_time = ?, end_time = ?,
                    hours = ?, description = ?, sub_task_category = ?,
                    photos = ?, clock_in_lat = ?, clock_in_lon = ?,
                    clock_out_lat = ?, clock_out_lon = ?,
                    is_overtime = ?
                WHERE id = ?
            """, (
                entry.user_id, entry.job_id, entry.start_time,
                entry.end_time, entry.hours, entry.description,
                entry.sub_task_category, entry.photos,
                entry.clock_in_lat, entry.clock_in_lon,
                entry.clock_out_lat, entry.clock_out_lon,
                entry.is_overtime, entry.id,
            ))

    def delete_labor_entry(self, entry_id: int):
        with self.db.get_connection() as conn:
            conn.execute(
                "DELETE FROM labor_entries WHERE id = ?", (entry_id,)
            )

    def get_labor_entry_by_id(self, entry_id: int) -> Optional[LaborEntry]:
        rows = self.db.execute("""
            SELECT le.*,
                   u.display_name AS user_name,
                   j.job_number, j.name AS job_name
            FROM labor_entries le
            JOIN users u ON le.user_id = u.id
            JOIN jobs j ON le.job_id = j.id
            WHERE le.id = ?
        """, (entry_id,))
        return LaborEntry(**{k: rows[0][k] for k in rows[0].keys() if k in LaborEntry.__dataclass_fields__}) if rows else None

    def get_labor_entries_for_job(
        self, job_id: int,
        date_from: str = None, date_to: str = None
    ) -> list[LaborEntry]:
        conditions = ["le.job_id = ?"]
        params: list = [job_id]
        if date_from:
            # Use DATE() so "2026-02-11" matches datetimes on that day
            conditions.append("DATE(le.start_time) >= ?")
            params.append(date_from[:10])  # Ensure date-only
        if date_to:
            conditions.append("DATE(le.start_time) <= ?")
            params.append(date_to[:10])
        where = " AND ".join(conditions)
        rows = self.db.execute(f"""
            SELECT le.*,
                   u.display_name AS user_name,
                   j.job_number, j.name AS job_name
            FROM labor_entries le
            JOIN users u ON le.user_id = u.id
            JOIN jobs j ON le.job_id = j.id
            WHERE {where}
            ORDER BY le.start_time DESC
        """, tuple(params))
        return [LaborEntry(**{k: r[k] for k in r.keys() if k in LaborEntry.__dataclass_fields__}) for r in rows]

    def get_labor_entries_for_user(
        self, user_id: int,
        date_from: str = None, date_to: str = None
    ) -> list[LaborEntry]:
        conditions = ["le.user_id = ?"]
        params: list = [user_id]
        if date_from:
            conditions.append("DATE(le.start_time) >= ?")
            params.append(date_from[:10])
        if date_to:
            conditions.append("DATE(le.start_time) <= ?")
            params.append(date_to[:10])
        where = " AND ".join(conditions)
        rows = self.db.execute(f"""
            SELECT le.*,
                   u.display_name AS user_name,
                   j.job_number, j.name AS job_name
            FROM labor_entries le
            JOIN users u ON le.user_id = u.id
            JOIN jobs j ON le.job_id = j.id
            WHERE {where}
            ORDER BY le.start_time DESC
        """, tuple(params))
        return [LaborEntry(**{k: r[k] for k in r.keys() if k in LaborEntry.__dataclass_fields__}) for r in rows]

    def get_active_clock_in(self, user_id: int) -> Optional[LaborEntry]:
        """Get the active (un-clocked-out) labor entry for a user."""
        rows = self.db.execute("""
            SELECT le.*,
                   u.display_name AS user_name,
                   j.job_number, j.name AS job_name
            FROM labor_entries le
            JOIN users u ON le.user_id = u.id
            JOIN jobs j ON le.job_id = j.id
            WHERE le.user_id = ? AND le.end_time IS NULL
            ORDER BY le.start_time DESC LIMIT 1
        """, (user_id,))
        return LaborEntry(**{k: rows[0][k] for k in rows[0].keys() if k in LaborEntry.__dataclass_fields__}) if rows else None

    def clock_in(self, user_id: int, job_id: int,
                 category: str = "General",
                 lat: float = None, lon: float = None,
                 photos: str = None) -> int:
        """Start a clock-in entry for a user on a job."""
        from datetime import datetime
        # Check for existing active clock-in
        active = self.get_active_clock_in(user_id)
        if active:
            raise ValueError(
                f"Already clocked in to job {active.job_number} "
                f"since {active.start_time}"
            )
        entry = LaborEntry(
            user_id=user_id,
            job_id=job_id,
            start_time=datetime.now().isoformat(),
            sub_task_category=category,
            clock_in_lat=lat,
            clock_in_lon=lon,
            photos=photos or "[]",
        )
        entry_id = self.create_labor_entry(entry)

        # Create clock-in notification for all users on this job
        job = self.get_job_by_id(job_id)
        user = self.get_user_by_id(user_id)
        job_label = job.job_number if job else f"Job #{job_id}"
        user_name = user.display_name if user else f"User #{user_id}"

        self.create_notification(Notification(
            user_id=None,  # broadcast to all users
            title="Clock In",
            message=(
                f"{user_name} clocked in to {job_label} — "
                f"{category}"
            ),
            severity="info",
            source="labor",
        ))
        return entry_id

    def clock_out(self, entry_id: int,
                  lat: float = None, lon: float = None,
                  description: str = "",
                  photos: str = "[]") -> Optional[LaborEntry]:
        """Clock out from an active entry, computing hours."""
        from datetime import datetime
        entry = self.get_labor_entry_by_id(entry_id)
        if not entry:
            raise ValueError(f"Labor entry {entry_id} not found")
        if entry.end_time:
            raise ValueError(f"Entry {entry_id} is already clocked out")

        now = datetime.now()
        start = datetime.fromisoformat(str(entry.start_time))
        hours = (now - start).total_seconds() / 3600.0

        entry.end_time = now.isoformat()
        entry.hours = round(hours, 2)
        entry.description = description
        entry.clock_out_lat = lat
        entry.clock_out_lon = lon
        entry.photos = photos
        self.update_labor_entry(entry)

        # Create clock-out notification
        refreshed = self.get_labor_entry_by_id(entry_id)
        user = self.get_user_by_id(entry.user_id)
        user_name = user.display_name if user else f"User #{entry.user_id}"
        job_label = refreshed.job_number if refreshed else f"Job #{entry.job_id}"

        self.create_notification(Notification(
            user_id=None,  # broadcast to all users
            title="Clock Out",
            message=(
                f"{user_name} clocked out of {job_label} — "
                f"{entry.hours:.1f}h worked"
            ),
            severity="info",
            source="labor",
        ))
        return refreshed

    def get_labor_summary_for_job(self, job_id: int) -> dict:
        """Get labor summary: total hours, breakdown by category/user."""
        rows = self.db.execute("""
            SELECT
                COALESCE(SUM(hours), 0) AS total_hours,
                COUNT(*) AS entry_count
            FROM labor_entries WHERE job_id = ?
        """, (job_id,))
        summary = dict(rows[0]) if rows else {
            "total_hours": 0, "entry_count": 0
        }

        # By category
        cat_rows = self.db.execute("""
            SELECT sub_task_category,
                   COALESCE(SUM(hours), 0) AS hours,
                   COUNT(*) AS entries
            FROM labor_entries WHERE job_id = ?
            GROUP BY sub_task_category
            ORDER BY hours DESC
        """, (job_id,))
        summary["by_category"] = [dict(r) for r in cat_rows]

        # By user
        user_rows = self.db.execute("""
            SELECT u.display_name AS user_name,
                   COALESCE(SUM(le.hours), 0) AS hours,
                   COUNT(*) AS entries
            FROM labor_entries le
            JOIN users u ON le.user_id = u.id
            WHERE le.job_id = ?
            GROUP BY le.user_id
            ORDER BY hours DESC
        """, (job_id,))
        summary["by_user"] = [dict(r) for r in user_rows]

        return summary

    # ── Job Locations ─────────────────────────────────────────────

    def get_job_location(self, job_id: int) -> Optional[JobLocation]:
        rows = self.db.execute(
            "SELECT * FROM job_locations WHERE job_id = ?", (job_id,)
        )
        return JobLocation(**dict(rows[0])) if rows else None

    def set_job_location(self, location: JobLocation) -> int:
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO job_locations
                    (job_id, latitude, longitude, geocoded_address)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    latitude = excluded.latitude,
                    longitude = excluded.longitude,
                    geocoded_address = excluded.geocoded_address,
                    cached_at = CURRENT_TIMESTAMP
            """, (
                location.job_id, location.latitude,
                location.longitude, location.geocoded_address,
            ))
            return cursor.lastrowid

    def delete_job_location(self, job_id: int):
        with self.db.get_connection() as conn:
            conn.execute(
                "DELETE FROM job_locations WHERE job_id = ?", (job_id,)
            )

    def check_proximity(self, lat: float, lon: float,
                        job_id: int) -> dict:
        """Check if coordinates are within geofence radius of a job.

        Returns dict with 'within_radius' (bool) and 'distance_miles' (float).
        """
        from wired_part.utils.geo import haversine_miles
        from wired_part.utils.constants import GEOFENCE_RADIUS_MILES

        location = self.get_job_location(job_id)
        if not location:
            return {"within_radius": True, "distance_miles": 0.0,
                    "no_location": True}

        distance = haversine_miles(lat, lon,
                                   location.latitude, location.longitude)
        return {
            "within_radius": distance <= GEOFENCE_RADIUS_MILES,
            "distance_miles": round(distance, 2),
        }

    # ── Job Notebooks ─────────────────────────────────────────────

    def get_or_create_notebook(self, job_id: int) -> JobNotebook:
        """Get or auto-create a notebook for a job with default sections."""
        notebook = self.get_notebook_for_job(job_id)
        if notebook:
            return notebook

        from wired_part.config import Config

        job = self.get_job_by_id(job_id)
        title = f"Notebook — {job.job_number}" if job else "Notebook"
        sections_template = Config.get_notebook_sections()

        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO job_notebooks (job_id, title)
                VALUES (?, ?)
            """, (job_id, title))
            notebook_id = cursor.lastrowid

            for idx, section_name in enumerate(sections_template):
                conn.execute("""
                    INSERT INTO notebook_sections
                        (notebook_id, name, sort_order)
                    VALUES (?, ?, ?)
                """, (notebook_id, section_name, idx))

        return self.get_notebook_for_job(job_id)

    def get_notebook_for_job(self, job_id: int) -> Optional[JobNotebook]:
        rows = self.db.execute("""
            SELECT nb.*, COALESCE(j.job_number, '') AS job_number
            FROM job_notebooks nb
            LEFT JOIN jobs j ON nb.job_id = j.id
            WHERE nb.job_id = ?
        """, (job_id,))
        return JobNotebook(**dict(rows[0])) if rows else None

    def create_section(self, section: NotebookSection) -> int:
        with self.db.get_connection() as conn:
            # Get max sort_order for this notebook
            row = conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) AS mx "
                "FROM notebook_sections WHERE notebook_id = ?",
                (section.notebook_id,),
            ).fetchone()
            sort_order = (row["mx"] + 1) if row else 0

            cursor = conn.execute("""
                INSERT INTO notebook_sections
                    (notebook_id, name, sort_order)
                VALUES (?, ?, ?)
            """, (section.notebook_id, section.name, sort_order))
            return cursor.lastrowid

    def update_section(self, section: NotebookSection):
        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE notebook_sections SET name = ?, sort_order = ?
                WHERE id = ?
            """, (section.name, section.sort_order, section.id))

    def delete_section(self, section_id: int):
        with self.db.get_connection() as conn:
            conn.execute(
                "DELETE FROM notebook_sections WHERE id = ?",
                (section_id,),
            )

    def get_sections(self, notebook_id: int) -> list[NotebookSection]:
        rows = self.db.execute("""
            SELECT * FROM notebook_sections
            WHERE notebook_id = ?
            ORDER BY sort_order, name
        """, (notebook_id,))
        return [NotebookSection(**dict(r)) for r in rows]

    def reorder_sections(self, notebook_id: int, section_ids: list[int]):
        """Reorder sections by updating sort_order based on position."""
        with self.db.get_connection() as conn:
            for idx, sid in enumerate(section_ids):
                conn.execute(
                    "UPDATE notebook_sections SET sort_order = ? "
                    "WHERE id = ? AND notebook_id = ?",
                    (idx, sid, notebook_id),
                )

    def create_page(self, page: NotebookPage) -> int:
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO notebook_pages
                    (section_id, title, content, photos,
                     part_references, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                page.section_id, page.title, page.content,
                page.photos, page.part_references, page.created_by,
            ))
            return cursor.lastrowid

    def update_page(self, page: NotebookPage):
        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE notebook_pages SET
                    title = ?, content = ?, photos = ?,
                    part_references = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                page.title, page.content, page.photos,
                page.part_references, page.id,
            ))

    def delete_page(self, page_id: int):
        with self.db.get_connection() as conn:
            conn.execute(
                "DELETE FROM notebook_pages WHERE id = ?", (page_id,)
            )

    def get_pages(self, section_id: int) -> list[NotebookPage]:
        rows = self.db.execute("""
            SELECT np.*, ns.name AS section_name,
                   COALESCE(u.display_name, '') AS created_by_name
            FROM notebook_pages np
            JOIN notebook_sections ns ON np.section_id = ns.id
            LEFT JOIN users u ON np.created_by = u.id
            WHERE np.section_id = ?
            ORDER BY np.created_at DESC
        """, (section_id,))
        return [NotebookPage(**dict(r)) for r in rows]

    def get_page_by_id(self, page_id: int) -> Optional[NotebookPage]:
        rows = self.db.execute("""
            SELECT np.*, ns.name AS section_name,
                   COALESCE(u.display_name, '') AS created_by_name
            FROM notebook_pages np
            JOIN notebook_sections ns ON np.section_id = ns.id
            LEFT JOIN users u ON np.created_by = u.id
            WHERE np.id = ?
        """, (page_id,))
        return NotebookPage(**dict(rows[0])) if rows else None

    def search_notebook_pages(
        self, query: str, job_id: int = None
    ) -> list[NotebookPage]:
        """Search notebook pages by title or content."""
        if not query.strip():
            return []
        pattern = f"%{query.strip()}%"
        params: list = [pattern, pattern]
        job_filter = ""
        if job_id is not None:
            job_filter = "AND nb.job_id = ?"
            params.append(job_id)
        rows = self.db.execute(f"""
            SELECT np.*, ns.name AS section_name,
                   COALESCE(u.display_name, '') AS created_by_name
            FROM notebook_pages np
            JOIN notebook_sections ns ON np.section_id = ns.id
            JOIN job_notebooks nb ON ns.notebook_id = nb.id
            LEFT JOIN users u ON np.created_by = u.id
            WHERE (np.title LIKE ? OR np.content LIKE ?)
            {job_filter}
            ORDER BY np.updated_at DESC
        """, tuple(params))
        return [NotebookPage(**dict(r)) for r in rows]

    # ── Notebook Attachments ───────────────────────────────────────

    def create_attachment(self, att: NotebookAttachment) -> int:
        """Create a notebook page attachment. Returns the new ID."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO notebook_attachments "
                "(page_id, filename, file_path, file_type, file_size, "
                "created_by) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (att.page_id, att.filename, att.file_path,
                 att.file_type, att.file_size, att.created_by),
            )
            return cursor.lastrowid

    def get_attachments(self, page_id: int) -> list[NotebookAttachment]:
        """Get all attachments for a notebook page."""
        rows = self.db.execute(
            "SELECT * FROM notebook_attachments "
            "WHERE page_id = ? ORDER BY created_at DESC, id DESC",
            (page_id,),
        )
        return [
            NotebookAttachment(**{
                k: r[k] for k in r.keys()
                if k in NotebookAttachment.__dataclass_fields__
            })
            for r in rows
        ]

    def get_attachment_by_id(
        self, attachment_id: int
    ) -> Optional[NotebookAttachment]:
        """Get a single attachment by ID."""
        rows = self.db.execute(
            "SELECT * FROM notebook_attachments WHERE id = ?",
            (attachment_id,),
        )
        if not rows:
            return None
        r = rows[0]
        return NotebookAttachment(**{
            k: r[k] for k in r.keys()
            if k in NotebookAttachment.__dataclass_fields__
        })

    def delete_attachment(self, attachment_id: int):
        """Delete a notebook attachment by ID."""
        self.db.execute(
            "DELETE FROM notebook_attachments WHERE id = ?",
            (attachment_id,),
        )

    # ── Work Reports ──────────────────────────────────────────────

    def get_work_report_data(
        self, job_id: int,
        date_from: str = None, date_to: str = None,
        report_type: str = "internal"
    ) -> dict:
        """Aggregate labor, parts, notes, and photos for a work report."""
        job = self.get_job_by_id(job_id)
        if not job:
            return {}

        # Labor entries
        labor = self.get_labor_entries_for_job(
            job_id, date_from=date_from, date_to=date_to
        )
        labor_summary = self.get_labor_summary_for_job(job_id)

        # Parts / billing data
        billing = self.get_billing_data(job_id, date_from, date_to)

        # Notes (all pages from this job's notebook)
        notebook = self.get_notebook_for_job(job_id)
        notes_pages = []
        if notebook:
            sections = self.get_sections(notebook.id)
            for section in sections:
                pages = self.get_pages(section.id)
                for page in pages:
                    notes_pages.append({
                        "section": section.name,
                        "title": page.title,
                        "content": page.content,
                        "photos": page.photo_list,
                        "created_at": str(page.created_at or ""),
                        "created_by": page.created_by_name,
                    })

        # Collect all photos from labor entries
        labor_photos = []
        for le in labor:
            labor_photos.extend(le.photo_list)

        # Assigned users
        assignments = self.get_job_assignments(job_id)

        result = {
            "job": {
                "job_number": job.job_number,
                "name": job.name,
                "customer": job.customer or "",
                "address": job.address or "",
                "status": job.status,
                "priority": job.priority,
                "created_at": str(job.created_at or ""),
            },
            "date_range": {
                "from": date_from or "",
                "to": date_to or "",
            },
            "labor": {
                "entries": [
                    {
                        "user": le.user_name,
                        "date": str(le.start_time or ""),
                        "hours": le.hours,
                        "category": le.sub_task_category,
                        "description": le.description or "",
                        "photos": le.photo_list,
                    }
                    for le in labor
                ],
                "summary": labor_summary,
            },
            "materials": billing.get("categories", {}),
            "materials_subtotal": billing.get("subtotal", 0.0),
            "notes": notes_pages,
            "photos": labor_photos,
            "assigned_users": [
                {"name": a.user_name, "role": a.role}
                for a in assignments
            ],
        }

        # For client reports, strip internal details
        if report_type == "client":
            for entry in result["labor"]["entries"]:
                entry.pop("photos", None)
            result.pop("photos", None)
            if "by_user" in result["labor"]["summary"]:
                for u in result["labor"]["summary"]["by_user"]:
                    u.pop("entries", None)

        return result

    # ── Hats & Permissions ─────────────────────────────────────────

    def get_all_hats(self) -> list[Hat]:
        """Get all hats ordered by id (privilege level)."""
        rows = self.db.execute(
            "SELECT * FROM hats ORDER BY id"
        )
        return [Hat(**dict(r)) for r in rows]

    def get_hat_by_id(self, hat_id: int) -> Optional[Hat]:
        rows = self.db.execute(
            "SELECT * FROM hats WHERE id = ?", (hat_id,)
        )
        return Hat(**dict(rows[0])) if rows else None

    def get_hat_by_name(self, name: str) -> Optional[Hat]:
        rows = self.db.execute(
            "SELECT * FROM hats WHERE name = ?", (name,)
        )
        return Hat(**dict(rows[0])) if rows else None

    def create_hat(self, hat: Hat) -> int:
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO hats (name, permissions, is_system) "
                "VALUES (?, ?, ?)",
                (hat.name, hat.permissions, hat.is_system),
            )
            return cursor.lastrowid

    def update_hat(self, hat: Hat):
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE hats SET name = ?, permissions = ?, "
                "is_system = ? WHERE id = ?",
                (hat.name, hat.permissions, hat.is_system, hat.id),
            )

    def update_hat_permissions(self, hat_id: int, permissions: list[str]):
        """Update the permissions for a hat.

        Raises ValueError if the hat is locked (Admin, IT, Office).
        """
        from wired_part.utils.constants import LOCKED_HAT_IDS
        if hat_id in LOCKED_HAT_IDS:
            raise ValueError(
                "Cannot modify permissions for a locked system hat."
            )
        import json
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE hats SET permissions = ? WHERE id = ?",
                (json.dumps(permissions), hat_id),
            )

    def delete_hat(self, hat_id: int):
        """Delete a hat (removes all user assignments too via CASCADE).

        Raises ValueError if the hat is locked (Admin, IT, Office).
        """
        from wired_part.utils.constants import LOCKED_HAT_IDS
        if hat_id in LOCKED_HAT_IDS:
            raise ValueError("Cannot delete a locked system hat.")
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM hats WHERE id = ?", (hat_id,))

    def rename_hat(self, hat_id: int, new_name: str):
        """Rename a hat. Allowed even for locked hats."""
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE hats SET name = ? WHERE id = ?",
                (new_name, hat_id),
            )

    # ── User Hat Assignments ──────────────────────────────────────

    def get_user_hats(self, user_id: int) -> list[UserHat]:
        """Get all hats assigned to a user."""
        rows = self.db.execute("""
            SELECT uh.*, h.name AS hat_name,
                   u.display_name AS user_name,
                   COALESCE(ab.display_name, '') AS assigned_by_name
            FROM user_hats uh
            JOIN hats h ON uh.hat_id = h.id
            JOIN users u ON uh.user_id = u.id
            LEFT JOIN users ab ON uh.assigned_by = ab.id
            WHERE uh.user_id = ?
            ORDER BY h.id
        """, (user_id,))
        return [UserHat(**dict(r)) for r in rows]

    def get_user_hat_names(self, user_id: int) -> list[str]:
        """Get just the hat names for a user."""
        rows = self.db.execute("""
            SELECT h.name
            FROM user_hats uh
            JOIN hats h ON uh.hat_id = h.id
            WHERE uh.user_id = ?
            ORDER BY h.id
        """, (user_id,))
        return [r["name"] for r in rows]

    def assign_hat(self, user_id: int, hat_id: int,
                   assigned_by: int = None):
        """Assign a hat to a user."""
        with self.db.get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO user_hats "
                "(user_id, hat_id, assigned_by) VALUES (?, ?, ?)",
                (user_id, hat_id, assigned_by),
            )

    def remove_hat(self, user_id: int, hat_id: int):
        """Remove a hat from a user."""
        with self.db.get_connection() as conn:
            conn.execute(
                "DELETE FROM user_hats WHERE user_id = ? AND hat_id = ?",
                (user_id, hat_id),
            )

    def set_user_hats(self, user_id: int, hat_ids: list[int],
                      assigned_by: int = None):
        """Replace all of a user's hats with the given list."""
        with self.db.get_connection() as conn:
            conn.execute(
                "DELETE FROM user_hats WHERE user_id = ?", (user_id,)
            )
            for hat_id in hat_ids:
                conn.execute(
                    "INSERT INTO user_hats "
                    "(user_id, hat_id, assigned_by) VALUES (?, ?, ?)",
                    (user_id, hat_id, assigned_by),
                )

    def get_user_permissions(self, user_id: int) -> set[str]:
        """Get the effective permissions for a user.

        A user's permissions = union of all their hats' permissions.
        Admin and IT hats grant all permissions automatically.
        """
        import json
        from wired_part.utils.constants import (
            FULL_ACCESS_HATS, PERMISSION_KEYS,
        )

        hats = self.get_user_hats(user_id)
        permissions = set()

        for uh in hats:
            # Full access hats get everything
            if uh.hat_name in FULL_ACCESS_HATS:
                return set(PERMISSION_KEYS)

            hat = self.get_hat_by_id(uh.hat_id)
            if hat:
                permissions.update(hat.permission_list)

        return permissions

    def user_has_permission(self, user_id: int, permission: str) -> bool:
        """Check if a user has a specific permission."""
        return permission in self.get_user_permissions(user_id)

    def user_has_any_full_access_hat(self, user_id: int) -> bool:
        """Check if user has Admin or IT hat (can assign hats)."""
        from wired_part.utils.constants import FULL_ACCESS_HATS
        hat_names = self.get_user_hat_names(user_id)
        return any(h in FULL_ACCESS_HATS for h in hat_names)

    # ── Purchase Orders ─────────────────────────────────────────────

    def generate_order_number(self) -> str:
        """Generate next sequential PO number like PO-2026-001."""
        from datetime import datetime
        from wired_part.config import Config
        prefix = Config.ORDER_NUMBER_PREFIX
        year = datetime.now().year
        rows = self.db.execute(
            "SELECT COUNT(*) as cnt FROM purchase_orders "
            "WHERE order_number LIKE ?",
            (f"{prefix}-{year}-%",),
        )
        count = rows[0]["cnt"] + 1 if rows else 1
        return f"{prefix}-{year}-{count:03d}"

    def create_purchase_order(self, order: PurchaseOrder) -> int:
        """Create a new purchase order (draft status)."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO purchase_orders "
                "(order_number, supplier_id, parts_list_id, status, notes, "
                "created_by, expected_delivery) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    order.order_number,
                    order.supplier_id,
                    order.parts_list_id,
                    order.status,
                    order.notes,
                    order.created_by,
                    order.expected_delivery,
                ),
            )
            return cursor.lastrowid

    def get_purchase_order_by_id(self, order_id: int) -> Optional[PurchaseOrder]:
        """Get a single order with joined info and aggregates."""
        rows = self.db.execute(
            """SELECT po.*,
                s.name AS supplier_name,
                COALESCE(u.display_name, '') AS created_by_name,
                COALESCE(pl.name, '') AS parts_list_name,
                COALESCE(agg.item_count, 0) AS item_count,
                COALESCE(agg.total_cost, 0.0) AS total_cost
            FROM purchase_orders po
            JOIN suppliers s ON po.supplier_id = s.id
            LEFT JOIN users u ON po.created_by = u.id
            LEFT JOIN parts_lists pl ON po.parts_list_id = pl.id
            LEFT JOIN (
                SELECT order_id,
                       COUNT(*) AS item_count,
                       SUM(quantity_ordered * unit_cost) AS total_cost
                FROM purchase_order_items
                GROUP BY order_id
            ) agg ON agg.order_id = po.id
            WHERE po.id = ?""",
            (order_id,),
        )
        if not rows:
            return None
        return PurchaseOrder(**{
            k: rows[0][k] for k in rows[0].keys()
            if k in PurchaseOrder.__dataclass_fields__
        })

    def get_all_purchase_orders(
        self, status: Optional[str] = None
    ) -> list[PurchaseOrder]:
        """Get all orders, optionally filtered by status."""
        query = """SELECT po.*,
                s.name AS supplier_name,
                COALESCE(u.display_name, '') AS created_by_name,
                COALESCE(pl.name, '') AS parts_list_name,
                COALESCE(agg.item_count, 0) AS item_count,
                COALESCE(agg.total_cost, 0.0) AS total_cost
            FROM purchase_orders po
            JOIN suppliers s ON po.supplier_id = s.id
            LEFT JOIN users u ON po.created_by = u.id
            LEFT JOIN parts_lists pl ON po.parts_list_id = pl.id
            LEFT JOIN (
                SELECT order_id,
                       COUNT(*) AS item_count,
                       SUM(quantity_ordered * unit_cost) AS total_cost
                FROM purchase_order_items
                GROUP BY order_id
            ) agg ON agg.order_id = po.id"""
        params = []
        if status:
            query += " WHERE po.status = ?"
            params.append(status)
        query += " ORDER BY po.created_at DESC"
        rows = self.db.execute(query, tuple(params))
        return [
            PurchaseOrder(**{
                k: r[k] for k in r.keys()
                if k in PurchaseOrder.__dataclass_fields__
            })
            for r in rows
        ]

    def search_purchase_orders(self, query: str) -> list[PurchaseOrder]:
        """Search orders by order_number, supplier name, or notes."""
        pattern = f"%{query}%"
        sql = """SELECT po.*,
                s.name AS supplier_name,
                COALESCE(u.display_name, '') AS created_by_name,
                COALESCE(pl.name, '') AS parts_list_name,
                COALESCE(agg.item_count, 0) AS item_count,
                COALESCE(agg.total_cost, 0.0) AS total_cost
            FROM purchase_orders po
            JOIN suppliers s ON po.supplier_id = s.id
            LEFT JOIN users u ON po.created_by = u.id
            LEFT JOIN parts_lists pl ON po.parts_list_id = pl.id
            LEFT JOIN (
                SELECT order_id,
                       COUNT(*) AS item_count,
                       SUM(quantity_ordered * unit_cost) AS total_cost
                FROM purchase_order_items
                GROUP BY order_id
            ) agg ON agg.order_id = po.id
            WHERE po.order_number LIKE ?
                OR s.name LIKE ?
                OR po.notes LIKE ?
            ORDER BY po.created_at DESC"""
        rows = self.db.execute(sql, (pattern, pattern, pattern))
        return [
            PurchaseOrder(**{
                k: r[k] for k in r.keys()
                if k in PurchaseOrder.__dataclass_fields__
            })
            for r in rows
        ]

    def update_purchase_order(self, order: PurchaseOrder):
        """Update an order (only draft orders can be fully edited)."""
        self.db.execute(
            "UPDATE purchase_orders SET supplier_id = ?, parts_list_id = ?, "
            "notes = ?, expected_delivery = ? WHERE id = ?",
            (
                order.supplier_id,
                order.parts_list_id,
                order.notes,
                order.expected_delivery,
                order.id,
            ),
        )

    def submit_purchase_order(self, order_id: int):
        """Transition order from draft to submitted."""
        from datetime import datetime
        self.db.execute(
            "UPDATE purchase_orders SET status = 'submitted', "
            "submitted_at = ? WHERE id = ? AND status = 'draft'",
            (datetime.now().isoformat(), order_id),
        )

    def cancel_purchase_order(self, order_id: int):
        """Cancel an order (only draft or submitted with no receipts)."""
        self.db.execute(
            "UPDATE purchase_orders SET status = 'cancelled' "
            "WHERE id = ? AND status IN ('draft', 'submitted')",
            (order_id,),
        )

    def close_purchase_order(self, order_id: int):
        """Manually close an order."""
        from datetime import datetime
        self.db.execute(
            "UPDATE purchase_orders SET status = 'closed', "
            "closed_at = ? WHERE id = ?",
            (datetime.now().isoformat(), order_id),
        )

    def delete_purchase_order(self, order_id: int):
        """Delete a draft order. Raises ValueError if not draft."""
        order = self.get_purchase_order_by_id(order_id)
        if not order:
            raise ValueError("Order not found")
        if order.status != "draft":
            raise ValueError("Only draft orders can be deleted")
        self.db.execute(
            "DELETE FROM purchase_orders WHERE id = ?", (order_id,)
        )

    # ── Purchase Order Items ────────────────────────────────────────

    def add_order_item(self, item: PurchaseOrderItem) -> int:
        """Add a line item to an order."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO purchase_order_items "
                "(order_id, part_id, quantity_ordered, unit_cost, notes) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    item.order_id,
                    item.part_id,
                    item.quantity_ordered,
                    item.unit_cost,
                    item.notes,
                ),
            )
            return cursor.lastrowid

    def update_order_item(self, item: PurchaseOrderItem):
        """Update a line item quantity, cost, or notes."""
        self.db.execute(
            "UPDATE purchase_order_items SET quantity_ordered = ?, "
            "unit_cost = ?, notes = ? WHERE id = ?",
            (item.quantity_ordered, item.unit_cost, item.notes, item.id),
        )

    def remove_order_item(self, item_id: int):
        """Remove a line item from an order."""
        self.db.execute(
            "DELETE FROM purchase_order_items WHERE id = ?", (item_id,)
        )

    def get_order_items(self, order_id: int) -> list[PurchaseOrderItem]:
        """Get all items for an order with joined part info."""
        rows = self.db.execute(
            """SELECT poi.*,
                p.part_number, p.description AS part_description
            FROM purchase_order_items poi
            JOIN parts p ON poi.part_id = p.id
            WHERE poi.order_id = ?
            ORDER BY p.part_number""",
            (order_id,),
        )
        return [
            PurchaseOrderItem(**{
                k: r[k] for k in r.keys()
                if k in PurchaseOrderItem.__dataclass_fields__
            })
            for r in rows
        ]

    def create_order_from_parts_list(
        self, parts_list_id: int, supplier_id: int, created_by: int
    ) -> int:
        """Create a PO pre-populated with items from a parts list."""
        items = self.get_parts_list_items(parts_list_id)
        if not items:
            raise ValueError("Parts list has no items")

        order = PurchaseOrder(
            order_number=self.generate_order_number(),
            supplier_id=supplier_id,
            parts_list_id=parts_list_id,
            status="draft",
            created_by=created_by,
        )
        order_id = self.create_purchase_order(order)

        for item in items:
            # Use current unit_cost from the part
            part = self.get_part_by_id(item.part_id)
            oi = PurchaseOrderItem(
                order_id=order_id,
                part_id=item.part_id,
                quantity_ordered=item.quantity,
                unit_cost=part.unit_cost if part else 0.0,
                notes=item.notes,
            )
            self.add_order_item(oi)

        return order_id

    # ── Order Receiving ─────────────────────────────────────────────

    def receive_order_items(
        self, order_id: int, receipts: list[dict], received_by: int
    ) -> int:
        """Receive items against an order.

        Each receipt dict has:
            order_item_id, quantity_received, allocate_to,
            allocate_truck_id (optional), allocate_job_id (optional), notes

        Returns the number of items processed.
        """
        count = 0
        with self.db.get_connection() as conn:
            # Fetch the supplier_id from the PO (v12: supplier tracking)
            po_row = conn.execute(
                "SELECT supplier_id FROM purchase_orders WHERE id = ?",
                (order_id,),
            ).fetchone()
            supplier_id = po_row["supplier_id"] if po_row else None

            for receipt in receipts:
                item_id = receipt["order_item_id"]
                qty = receipt["quantity_received"]
                allocate_to = receipt.get("allocate_to", "warehouse")
                truck_id = receipt.get("allocate_truck_id")
                job_id = receipt.get("allocate_job_id")
                notes = receipt.get("notes", "")

                # Update the order item's received quantity
                conn.execute(
                    "UPDATE purchase_order_items "
                    "SET quantity_received = quantity_received + ? "
                    "WHERE id = ?",
                    (qty, item_id),
                )

                # Create receive log entry (v12: includes supplier_id)
                conn.execute(
                    "INSERT INTO receive_log "
                    "(order_item_id, quantity_received, allocate_to, "
                    "allocate_truck_id, allocate_job_id, received_by, "
                    "supplier_id, notes) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (item_id, qty, allocate_to, truck_id, job_id,
                     received_by, supplier_id, notes),
                )

                # Get the part_id for this order item
                oi_row = conn.execute(
                    "SELECT part_id, unit_cost FROM purchase_order_items "
                    "WHERE id = ?",
                    (item_id,),
                ).fetchone()
                part_id = oi_row["part_id"]
                unit_cost = oi_row["unit_cost"]

                # Allocate to the target
                if allocate_to == "warehouse":
                    conn.execute(
                        "UPDATE parts SET quantity = quantity + ? "
                        "WHERE id = ?",
                        (qty, part_id),
                    )
                elif allocate_to == "truck" and truck_id:
                    # Create pending truck transfer (v12: with supplier tracking)
                    conn.execute(
                        "INSERT INTO truck_transfers "
                        "(truck_id, part_id, quantity, direction, status, "
                        "created_by, source_order_id, supplier_id) "
                        "VALUES (?, ?, ?, 'outbound', 'pending', ?, ?, ?)",
                        (truck_id, part_id, qty, received_by,
                         order_id, supplier_id),
                    )
                    # Also add to warehouse first (transfer will deduct)
                    conn.execute(
                        "UPDATE parts SET quantity = quantity + ? "
                        "WHERE id = ?",
                        (qty, part_id),
                    )
                elif allocate_to == "job" and job_id:
                    # Add to warehouse then consume for job
                    conn.execute(
                        "UPDATE parts SET quantity = quantity + ? "
                        "WHERE id = ?",
                        (qty, part_id),
                    )
                    # v12: Enforce one-supplier-per-part-per-job rule
                    existing = conn.execute(
                        "SELECT id, quantity_used, supplier_id "
                        "FROM job_parts "
                        "WHERE job_id = ? AND part_id = ?",
                        (job_id, part_id),
                    ).fetchone()
                    if (existing and existing["supplier_id"]
                            and supplier_id
                            and existing["supplier_id"] != supplier_id):
                        raise ValueError(
                            f"Supplier conflict: part {part_id} on job "
                            f"{job_id} is already supplied by supplier "
                            f"{existing['supplier_id']}; cannot receive "
                            f"from supplier {supplier_id}. A part must "
                            f"come from the same supplier for the "
                            f"entire job."
                        )
                    if existing:
                        conn.execute(
                            "UPDATE job_parts SET quantity_used = "
                            "quantity_used + ?, supplier_id = "
                            "COALESCE(?, supplier_id), "
                            "source_order_id = COALESCE(?, "
                            "source_order_id) WHERE id = ?",
                            (qty, supplier_id, order_id, existing["id"]),
                        )
                    else:
                        conn.execute(
                            "INSERT INTO job_parts "
                            "(job_id, part_id, quantity_used, "
                            "unit_cost_at_use, supplier_id, "
                            "source_order_id, notes) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (job_id, part_id, qty, unit_cost,
                             supplier_id, order_id,
                             "Received from PO"),
                        )

                count += 1

            # Update order status based on receipt progress
            all_items = conn.execute(
                "SELECT quantity_ordered, quantity_received "
                "FROM purchase_order_items WHERE order_id = ?",
                (order_id,),
            ).fetchall()

            all_received = all(
                r["quantity_received"] >= r["quantity_ordered"]
                for r in all_items
            )
            any_received = any(
                r["quantity_received"] > 0 for r in all_items
            )

            if all_received:
                from wired_part.config import Config
                if Config.AUTO_CLOSE_RECEIVED_ORDERS:
                    from datetime import datetime as _dt
                    conn.execute(
                        "UPDATE purchase_orders SET status = 'closed', "
                        "closed_at = ? WHERE id = ?",
                        (_dt.now().isoformat(), order_id),
                    )
                else:
                    conn.execute(
                        "UPDATE purchase_orders SET status = 'received' "
                        "WHERE id = ?",
                        (order_id,),
                    )
            elif any_received:
                conn.execute(
                    "UPDATE purchase_orders SET status = 'partial' "
                    "WHERE id = ?",
                    (order_id,),
                )

        return count

    def get_receive_log(
        self,
        order_id: Optional[int] = None,
        order_item_id: Optional[int] = None,
    ) -> list[ReceiveLogEntry]:
        """Get receiving history with joined fields."""
        query = """SELECT rl.*,
                p.part_number, p.description AS part_description,
                COALESCE(t.truck_number, '') AS truck_number,
                COALESCE(j.job_number, '') AS job_number,
                COALESCE(u.display_name, '') AS received_by_name
            FROM receive_log rl
            JOIN purchase_order_items poi ON rl.order_item_id = poi.id
            JOIN parts p ON poi.part_id = p.id
            LEFT JOIN trucks t ON rl.allocate_truck_id = t.id
            LEFT JOIN jobs j ON rl.allocate_job_id = j.id
            LEFT JOIN users u ON rl.received_by = u.id"""
        params = []
        conditions = []
        if order_id:
            conditions.append("poi.order_id = ?")
            params.append(order_id)
        if order_item_id:
            conditions.append("rl.order_item_id = ?")
            params.append(order_item_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY rl.received_at DESC"

        rows = self.db.execute(query, tuple(params))
        return [
            ReceiveLogEntry(**{
                k: r[k] for k in r.keys()
                if k in ReceiveLogEntry.__dataclass_fields__
            })
            for r in rows
        ]

    def get_allocation_suggestions(self, part_id: int) -> list[dict]:
        """Suggest where a received part should go.

        Checks pending truck transfers, active job needs, and warehouse
        low stock. Returns list of dicts: {target, target_id, target_name,
        reason, priority}.
        """
        suggestions = []

        # 1. Pending truck transfers for this part (highest priority)
        pending = self.db.execute(
            "SELECT tt.truck_id, t.truck_number, tt.quantity "
            "FROM truck_transfers tt "
            "JOIN trucks t ON tt.truck_id = t.id "
            "WHERE tt.part_id = ? AND tt.status = 'pending' "
            "AND tt.direction = 'outbound'",
            (part_id,),
        )
        for row in pending:
            suggestions.append({
                "target": "truck",
                "target_id": row["truck_id"],
                "target_name": f"Truck {row['truck_number']}",
                "reason": f"Pending transfer ({row['quantity']} units)",
                "priority": 1,
            })

        # 2. Active jobs with parts_lists containing this part
        job_needs = self.db.execute(
            """SELECT j.id, j.job_number, j.name, pli.quantity
            FROM parts_list_items pli
            JOIN parts_lists pl ON pli.list_id = pl.id
            JOIN jobs j ON pl.job_id = j.id
            WHERE pli.part_id = ? AND j.status = 'active'""",
            (part_id,),
        )
        for row in job_needs:
            suggestions.append({
                "target": "job",
                "target_id": row["id"],
                "target_name": f"{row['job_number']} — {row['name']}",
                "reason": f"Job needs {row['quantity']} units",
                "priority": 2,
            })

        # 3. Low warehouse stock (default)
        part = self.get_part_by_id(part_id)
        if part and part.is_low_stock:
            suggestions.append({
                "target": "warehouse",
                "target_id": None,
                "target_name": "Warehouse",
                "reason": f"Low stock ({part.quantity}/{part.min_quantity})",
                "priority": 3,
            })
        else:
            suggestions.append({
                "target": "warehouse",
                "target_id": None,
                "target_name": "Warehouse",
                "reason": "Default allocation",
                "priority": 4,
            })

        suggestions.sort(key=lambda s: s["priority"])
        return suggestions

    def get_order_receive_summary(self, order_id: int) -> dict:
        """Get summary of receiving status for an order."""
        rows = self.db.execute(
            "SELECT COUNT(*) as total_items, "
            "SUM(quantity_ordered) as total_ordered, "
            "SUM(quantity_received) as total_received, "
            "SUM(quantity_ordered * unit_cost) as total_cost "
            "FROM purchase_order_items WHERE order_id = ?",
            (order_id,),
        )
        if not rows:
            return {
                "total_items": 0, "total_ordered": 0,
                "total_received": 0, "total_cost": 0.0,
            }
        r = rows[0]
        return {
            "total_items": r["total_items"] or 0,
            "total_ordered": r["total_ordered"] or 0,
            "total_received": r["total_received"] or 0,
            "total_cost": r["total_cost"] or 0.0,
        }

    # ── Return Authorizations ──────────────────────────────────────

    def generate_ra_number(self) -> str:
        """Generate next sequential RA number like RA-2026-001."""
        from datetime import datetime
        from wired_part.config import Config
        prefix = Config.RA_NUMBER_PREFIX
        year = datetime.now().year
        rows = self.db.execute(
            "SELECT COUNT(*) as cnt FROM return_authorizations "
            "WHERE ra_number LIKE ?",
            (f"{prefix}-{year}-%",),
        )
        count = rows[0]["cnt"] + 1 if rows else 1
        return f"{prefix}-{year}-{count:03d}"

    def create_return_authorization(
        self, ra: ReturnAuthorization, items: list[ReturnAuthorizationItem]
    ) -> int:
        """Create a return authorization with items.

        Deducts returned quantities from warehouse inventory immediately.
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO return_authorizations "
                "(ra_number, order_id, supplier_id, status, reason, "
                "notes, created_by, credit_amount) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    ra.ra_number,
                    ra.order_id,
                    ra.supplier_id,
                    ra.status,
                    ra.reason,
                    ra.notes,
                    ra.created_by,
                    ra.credit_amount,
                ),
            )
            ra_id = cursor.lastrowid

            for item in items:
                conn.execute(
                    "INSERT INTO return_authorization_items "
                    "(ra_id, part_id, quantity, unit_cost, reason) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (ra_id, item.part_id, item.quantity,
                     item.unit_cost, item.reason),
                )
                # Deduct from warehouse
                conn.execute(
                    "UPDATE parts SET quantity = MAX(0, quantity - ?) "
                    "WHERE id = ?",
                    (item.quantity, item.part_id),
                )

            return ra_id

    def get_return_authorization_by_id(
        self, ra_id: int
    ) -> Optional[ReturnAuthorization]:
        """Get an RA with joined supplier/order/user info."""
        rows = self.db.execute(
            """SELECT ra.*,
                s.name AS supplier_name,
                COALESCE(po.order_number, '') AS order_number,
                COALESCE(u.display_name, '') AS created_by_name,
                COALESCE(agg.item_count, 0) AS item_count
            FROM return_authorizations ra
            JOIN suppliers s ON ra.supplier_id = s.id
            LEFT JOIN purchase_orders po ON ra.order_id = po.id
            LEFT JOIN users u ON ra.created_by = u.id
            LEFT JOIN (
                SELECT ra_id, COUNT(*) AS item_count
                FROM return_authorization_items
                GROUP BY ra_id
            ) agg ON agg.ra_id = ra.id
            WHERE ra.id = ?""",
            (ra_id,),
        )
        if not rows:
            return None
        return ReturnAuthorization(**{
            k: rows[0][k] for k in rows[0].keys()
            if k in ReturnAuthorization.__dataclass_fields__
        })

    def get_all_return_authorizations(
        self, status: Optional[str] = None
    ) -> list[ReturnAuthorization]:
        """Get all RAs, optionally filtered by status."""
        query = """SELECT ra.*,
                s.name AS supplier_name,
                COALESCE(po.order_number, '') AS order_number,
                COALESCE(u.display_name, '') AS created_by_name,
                COALESCE(agg.item_count, 0) AS item_count
            FROM return_authorizations ra
            JOIN suppliers s ON ra.supplier_id = s.id
            LEFT JOIN purchase_orders po ON ra.order_id = po.id
            LEFT JOIN users u ON ra.created_by = u.id
            LEFT JOIN (
                SELECT ra_id, COUNT(*) AS item_count
                FROM return_authorization_items
                GROUP BY ra_id
            ) agg ON agg.ra_id = ra.id"""
        params = []
        if status:
            query += " WHERE ra.status = ?"
            params.append(status)
        query += " ORDER BY ra.created_at DESC"
        rows = self.db.execute(query, tuple(params))
        return [
            ReturnAuthorization(**{
                k: r[k] for k in r.keys()
                if k in ReturnAuthorization.__dataclass_fields__
            })
            for r in rows
        ]

    def get_return_items(self, ra_id: int) -> list[ReturnAuthorizationItem]:
        """Get items for a return with joined part info."""
        rows = self.db.execute(
            """SELECT rai.*,
                p.part_number, p.description AS part_description
            FROM return_authorization_items rai
            JOIN parts p ON rai.part_id = p.id
            WHERE rai.ra_id = ?
            ORDER BY p.part_number""",
            (ra_id,),
        )
        return [
            ReturnAuthorizationItem(**{
                k: r[k] for k in r.keys()
                if k in ReturnAuthorizationItem.__dataclass_fields__
            })
            for r in rows
        ]

    def update_return_status(
        self, ra_id: int, new_status: str,
        credit_amount: Optional[float] = None
    ):
        """Transition RA status with appropriate timestamps."""
        from datetime import datetime
        now = datetime.now().isoformat()

        if new_status == "picked_up":
            self.db.execute(
                "UPDATE return_authorizations SET status = ?, "
                "picked_up_at = ? WHERE id = ?",
                (new_status, now, ra_id),
            )
        elif new_status == "credit_received":
            params = [new_status, now]
            set_clause = "status = ?, credit_received_at = ?"
            if credit_amount is not None:
                set_clause += ", credit_amount = ?"
                params.append(credit_amount)
            params.append(ra_id)
            self.db.execute(
                f"UPDATE return_authorizations SET {set_clause} "
                f"WHERE id = ?",
                tuple(params),
            )
        else:
            self.db.execute(
                "UPDATE return_authorizations SET status = ? "
                "WHERE id = ?",
                (new_status, ra_id),
            )

    def delete_return_authorization(self, ra_id: int):
        """Delete an RA (only if initiated). Restores inventory."""
        ra = self.get_return_authorization_by_id(ra_id)
        if not ra:
            raise ValueError("Return authorization not found")
        if ra.status != "initiated":
            raise ValueError("Only initiated returns can be deleted")

        with self.db.get_connection() as conn:
            # Restore inventory for each item
            items = conn.execute(
                "SELECT part_id, quantity FROM return_authorization_items "
                "WHERE ra_id = ?",
                (ra_id,),
            ).fetchall()
            for item in items:
                conn.execute(
                    "UPDATE parts SET quantity = quantity + ? "
                    "WHERE id = ?",
                    (item["quantity"], item["part_id"]),
                )
            conn.execute(
                "DELETE FROM return_authorizations WHERE id = ?",
                (ra_id,),
            )

    # ── Order Analytics ─────────────────────────────────────────────

    def get_order_analytics(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> dict:
        """Get order analytics: total spent, avg order size, etc."""
        conditions = []
        params = []
        if date_from:
            conditions.append("po.created_at >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("po.created_at <= ?")
            params.append(date_to)

        where = " WHERE " + " AND ".join(conditions) if conditions else ""

        # Total orders and spending
        rows = self.db.execute(
            f"""SELECT COUNT(*) as total_orders,
                COALESCE(SUM(agg.total_cost), 0) AS total_spent,
                COALESCE(AVG(agg.total_cost), 0) AS avg_order_size
            FROM purchase_orders po
            LEFT JOIN (
                SELECT order_id,
                       SUM(quantity_ordered * unit_cost) AS total_cost
                FROM purchase_order_items
                GROUP BY order_id
            ) agg ON agg.order_id = po.id
            {where}""",
            tuple(params),
        )
        result = {
            "total_orders": rows[0]["total_orders"] if rows else 0,
            "total_spent": rows[0]["total_spent"] if rows else 0.0,
            "avg_order_size": rows[0]["avg_order_size"] if rows else 0.0,
        }

        # Orders by status
        status_rows = self.db.execute(
            f"SELECT status, COUNT(*) as cnt "
            f"FROM purchase_orders po {where} GROUP BY status",
            tuple(params),
        )
        result["by_status"] = {
            r["status"]: r["cnt"] for r in status_rows
        }

        # Top supplier
        supplier_rows = self.db.execute(
            f"""SELECT s.name, COUNT(*) as order_count
            FROM purchase_orders po
            JOIN suppliers s ON po.supplier_id = s.id
            {where}
            GROUP BY po.supplier_id
            ORDER BY order_count DESC
            LIMIT 1""",
            tuple(params),
        )
        result["top_supplier"] = (
            supplier_rows[0]["name"] if supplier_rows else "N/A"
        )

        # Return rate
        total_returns = self.db.execute(
            "SELECT COUNT(*) as cnt FROM return_authorizations"
        )
        result["total_returns"] = (
            total_returns[0]["cnt"] if total_returns else 0
        )

        return result

    def get_supplier_order_history(
        self, supplier_id: int
    ) -> list[PurchaseOrder]:
        """Get all orders for a specific supplier."""
        rows = self.db.execute(
            """SELECT po.*,
                s.name AS supplier_name,
                COALESCE(u.display_name, '') AS created_by_name,
                COALESCE(pl.name, '') AS parts_list_name,
                COALESCE(agg.item_count, 0) AS item_count,
                COALESCE(agg.total_cost, 0.0) AS total_cost
            FROM purchase_orders po
            JOIN suppliers s ON po.supplier_id = s.id
            LEFT JOIN users u ON po.created_by = u.id
            LEFT JOIN parts_lists pl ON po.parts_list_id = pl.id
            LEFT JOIN (
                SELECT order_id,
                       COUNT(*) AS item_count,
                       SUM(quantity_ordered * unit_cost) AS total_cost
                FROM purchase_order_items
                GROUP BY order_id
            ) agg ON agg.order_id = po.id
            WHERE po.supplier_id = ?
            ORDER BY po.created_at DESC""",
            (supplier_id,),
        )
        return [
            PurchaseOrder(**{
                k: r[k] for k in r.keys()
                if k in PurchaseOrder.__dataclass_fields__
            })
            for r in rows
        ]

    def get_orders_summary(self) -> dict:
        """Quick summary for dashboard display."""
        pending = self.db.execute(
            "SELECT COUNT(*) as cnt FROM purchase_orders "
            "WHERE status IN ('submitted', 'partial')"
        )
        draft = self.db.execute(
            "SELECT COUNT(*) as cnt FROM purchase_orders "
            "WHERE status = 'draft'"
        )
        # Items awaiting receipt
        awaiting = self.db.execute(
            "SELECT COALESCE(SUM(quantity_ordered - quantity_received), 0) "
            "as cnt FROM purchase_order_items poi "
            "JOIN purchase_orders po ON poi.order_id = po.id "
            "WHERE po.status IN ('submitted', 'partial') "
            "AND poi.quantity_received < poi.quantity_ordered"
        )
        open_returns = self.db.execute(
            "SELECT COUNT(*) as cnt FROM return_authorizations "
            "WHERE status IN ('initiated', 'picked_up')"
        )
        return {
            "pending_orders": pending[0]["cnt"] if pending else 0,
            "draft_orders": draft[0]["cnt"] if draft else 0,
            "items_awaiting": awaiting[0]["cnt"] if awaiting else 0,
            "open_returns": open_returns[0]["cnt"] if open_returns else 0,
        }

    # ── Shortfall Detection ──────────────────────────────────────

    def check_shortfall(self, list_id: int) -> list[dict]:
        """Check warehouse stock shortfalls for a parts list.

        Compares each item's required quantity against current warehouse
        stock. Returns a list of dicts for items where stock is
        insufficient:
            {part_id, part_number, description, required, in_stock,
             shortfall, unit_cost}
        """
        items = self.get_parts_list_items(list_id)
        shortfalls = []

        for item in items:
            part = self.get_part_by_id(item.part_id)
            if not part:
                continue

            if part.quantity < item.quantity:
                shortfalls.append({
                    "part_id": part.id,
                    "part_number": part.part_number,
                    "description": part.description,
                    "required": item.quantity,
                    "in_stock": part.quantity,
                    "shortfall": item.quantity - part.quantity,
                    "unit_cost": part.unit_cost,
                })

        return shortfalls

    def check_shortfall_for_job(self, job_id: int) -> list[dict]:
        """Check warehouse stock shortfalls for all parts lists linked
        to a specific job.

        Returns combined shortfalls across all job-specific lists.
        """
        lists = self.get_all_parts_lists(list_type="specific")
        job_lists = [pl for pl in lists if pl.job_id == job_id]

        all_shortfalls = {}
        for pl in job_lists:
            shortfalls = self.check_shortfall(pl.id)
            for sf in shortfalls:
                key = sf["part_id"]
                if key in all_shortfalls:
                    all_shortfalls[key]["required"] += sf["required"]
                    all_shortfalls[key]["shortfall"] = max(
                        0,
                        all_shortfalls[key]["required"]
                        - all_shortfalls[key]["in_stock"],
                    )
                else:
                    all_shortfalls[key] = dict(sf)

        return list(all_shortfalls.values())

    # ── Order Suggestions ──────────────────────────────────────

    def get_suggestions_for_part(self, part_id: int, limit: int = 5
                                 ) -> list[dict]:
        """Get AI-suggested parts to order alongside the given part."""
        rows = self.db.execute("""
            SELECT os.suggested_part_id, os.score, os.source,
                   p.part_number, p.name, p.description,
                   p.quantity, p.unit_cost
            FROM order_suggestions os
            JOIN parts p ON os.suggested_part_id = p.id
            WHERE os.trigger_part_id = ?
            ORDER BY os.score DESC
            LIMIT ?
        """, (part_id, limit))
        return [dict(r) for r in rows]

    def update_co_occurrence(self, part_a: int, part_b: int):
        """Increment co-occurrence count between two parts."""
        # Ensure consistent ordering (smaller ID first)
        a, b = min(part_a, part_b), max(part_a, part_b)
        self.db.execute("""
            INSERT INTO order_patterns (part_id_a, part_id_b, co_occurrence_count)
            VALUES (?, ?, 1)
            ON CONFLICT(part_id_a, part_id_b) DO UPDATE SET
                co_occurrence_count = co_occurrence_count + 1
        """, (a, b))

    def rebuild_order_patterns(self):
        """Rebuild co-occurrence matrix from closed POs (full history)."""
        with self.db.get_connection() as conn:
            # Clear existing patterns
            conn.execute("DELETE FROM order_patterns")
            conn.execute("DELETE FROM order_suggestions")

            # Find all part pairs that appeared on the same PO
            rows = conn.execute("""
                SELECT poi1.part_id AS part_a,
                       poi2.part_id AS part_b,
                       COUNT(*) AS cnt
                FROM purchase_order_items poi1
                JOIN purchase_order_items poi2
                    ON poi1.order_id = poi2.order_id
                    AND poi1.part_id < poi2.part_id
                JOIN purchase_orders po ON poi1.order_id = po.id
                WHERE po.status IN ('received', 'closed')
                GROUP BY poi1.part_id, poi2.part_id
                HAVING cnt >= 2
            """).fetchall()

            for row in rows:
                conn.execute("""
                    INSERT INTO order_patterns
                        (part_id_a, part_id_b, co_occurrence_count)
                    VALUES (?, ?, ?)
                """, (row["part_a"], row["part_b"], row["cnt"]))

            # Build suggestions from patterns
            conn.execute("""
                INSERT OR REPLACE INTO order_suggestions
                    (trigger_part_id, suggested_part_id, score, source)
                SELECT part_id_a, part_id_b,
                       CAST(co_occurrence_count AS REAL), 'co_occurrence'
                FROM order_patterns
                WHERE co_occurrence_count >= 2
            """)
            conn.execute("""
                INSERT OR REPLACE INTO order_suggestions
                    (trigger_part_id, suggested_part_id, score, source)
                SELECT part_id_b, part_id_a,
                       CAST(co_occurrence_count AS REAL), 'co_occurrence'
                FROM order_patterns
                WHERE co_occurrence_count >= 2
            """)

    # ── v12: Activity Log ──────────────────────────────────────────

    def log_activity(
        self, user_id: int | None, action: str, entity_type: str,
        entity_id: int | None = None, entity_label: str = "",
        details: str = "",
    ) -> int:
        """Record an activity log entry.

        Args:
            user_id: User who performed the action (None for system actions).
            action: Verb — 'created', 'updated', 'deleted', 'received',
                    'transferred', 'clocked_in', 'clocked_out', etc.
            entity_type: 'job', 'part', 'order', 'labor', 'transfer',
                         'return', 'user', 'truck', etc.
            entity_id: Primary key of the affected entity.
            entity_label: Human-readable label, e.g. "Job #4521 - Main St".
            details: Optional JSON or text with extra context.

        Returns:
            The id of the created log entry.
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO activity_log "
                "(user_id, action, entity_type, entity_id, "
                "entity_label, details) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, action, entity_type, entity_id,
                 entity_label, details),
            )
            return cursor.lastrowid

    def get_activity_log(
        self, entity_type: str | None = None,
        entity_id: int | None = None,
        user_id: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 50,
    ) -> list:
        """Retrieve activity log entries with optional filters.

        Returns list of ActivityLogEntry objects.
        """
        from wired_part.database.models import ActivityLogEntry

        clauses = []
        params: list = []
        if entity_type:
            clauses.append("al.entity_type = ?")
            params.append(entity_type)
        if entity_id is not None:
            clauses.append("al.entity_id = ?")
            params.append(entity_id)
        if user_id is not None:
            clauses.append("al.user_id = ?")
            params.append(user_id)
        if date_from:
            clauses.append("DATE(al.created_at) >= DATE(?)")
            params.append(date_from)
        if date_to:
            clauses.append("DATE(al.created_at) <= DATE(?)")
            params.append(date_to)

        where = " AND ".join(clauses) if clauses else "1=1"
        params.append(limit)

        rows = self.db.execute(f"""
            SELECT al.*,
                   COALESCE(u.display_name, '') AS user_name
            FROM activity_log al
            LEFT JOIN users u ON al.user_id = u.id
            WHERE {where}
            ORDER BY al.created_at DESC
            LIMIT ?
        """, tuple(params))
        return [
            ActivityLogEntry(**{
                k: r[k] for k in r.keys()
                if k in ActivityLogEntry.__dataclass_fields__
            })
            for r in rows
        ]

    def get_recent_activity(self, limit: int = 20) -> list:
        """Shortcut: get the most recent activity log entries."""
        return self.get_activity_log(limit=limit)

    def get_entity_activity(
        self, entity_type: str, entity_id: int, limit: int = 20
    ) -> list:
        """Get activity log for a specific entity (e.g. a job)."""
        return self.get_activity_log(
            entity_type=entity_type, entity_id=entity_id, limit=limit
        )

    # ── v12: Global Search ─────────────────────────────────────────

    def search_all(self, query: str) -> dict:
        """Search across all major entities.

        Returns dict with keys: jobs, parts, users, orders, pages.
        Each value is a list of dicts with id, label, sublabel, type.
        """
        if not query or not query.strip():
            return {
                "jobs": [], "parts": [], "users": [],
                "orders": [], "pages": [],
            }

        q = f"%{query.strip()}%"

        # Jobs
        jobs = self.db.execute("""
            SELECT id, job_number, name, customer, status
            FROM jobs
            WHERE job_number LIKE ? OR name LIKE ? OR customer LIKE ?
            ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END,
                     created_at DESC
            LIMIT 10
        """, (q, q, q))
        job_results = [{
            "id": r["id"],
            "label": f"#{r['job_number']} - {r['name']}",
            "sublabel": f"{r['customer'] or ''} [{r['status']}]",
            "type": "job",
        } for r in jobs]

        # Parts
        parts = self.db.execute("""
            SELECT id, part_number, name, description, quantity
            FROM parts
            WHERE part_number LIKE ? OR name LIKE ?
               OR description LIKE ? OR local_part_number LIKE ?
            ORDER BY name, part_number
            LIMIT 10
        """, (q, q, q, q))
        part_results = [{
            "id": r["id"],
            "label": r["name"] or r["description"] or r["part_number"],
            "sublabel": f"PN: {r['part_number']} | Stock: {r['quantity']}",
            "type": "part",
        } for r in parts]

        # Users
        users = self.db.execute("""
            SELECT id, username, display_name, is_active
            FROM users
            WHERE display_name LIKE ? OR username LIKE ?
            ORDER BY is_active DESC, display_name
            LIMIT 10
        """, (q, q))
        user_results = [{
            "id": r["id"],
            "label": r["display_name"],
            "sublabel": f"@{r['username']}"
                        + ("" if r["is_active"] else " [inactive]"),
            "type": "user",
        } for r in users]

        # Orders
        orders = self.db.execute("""
            SELECT po.id, po.order_number, po.status,
                   COALESCE(s.name, '') AS supplier_name
            FROM purchase_orders po
            LEFT JOIN suppliers s ON po.supplier_id = s.id
            WHERE po.order_number LIKE ? OR s.name LIKE ?
            ORDER BY po.created_at DESC
            LIMIT 10
        """, (q, q))
        order_results = [{
            "id": r["id"],
            "label": r["order_number"],
            "sublabel": f"{r['supplier_name']} [{r['status']}]",
            "type": "order",
        } for r in orders]

        # Notebook pages
        pages = self.db.execute("""
            SELECT np.id, np.title, ns.name AS section_name,
                   jn.job_id
            FROM notebook_pages np
            JOIN notebook_sections ns ON np.section_id = ns.id
            JOIN job_notebooks jn ON ns.notebook_id = jn.id
            WHERE np.title LIKE ? OR np.content LIKE ?
            ORDER BY np.updated_at DESC
            LIMIT 10
        """, (q, q))
        page_results = [{
            "id": r["id"],
            "label": r["title"],
            "sublabel": f"Job #{r['job_id']} / {r['section_name']}",
            "type": "page",
        } for r in pages]

        return {
            "jobs": job_results,
            "parts": part_results,
            "users": user_results,
            "orders": order_results,
            "pages": page_results,
        }

    # ── v12: Supplier Chain Tracking ────────────────────────────────

    def get_part_supplier_chain(self, part_id: int) -> list[dict]:
        """Get the full supply chain history for a part.

        Returns chronological list of movements: received, transferred,
        consumed, returned — each with supplier info where available.
        """
        rows = self.db.execute("""
            SELECT 'received' AS event,
                   rl.received_at AS event_at,
                   rl.quantity_received AS quantity,
                   rl.allocate_to,
                   po.order_number,
                   s.name AS supplier_name,
                   s.id AS supplier_id,
                   COALESCE(u.display_name, '') AS user_name
            FROM receive_log rl
            JOIN purchase_order_items poi ON rl.order_item_id = poi.id
            JOIN purchase_orders po ON poi.order_id = po.id
            JOIN suppliers s ON po.supplier_id = s.id
            LEFT JOIN users u ON rl.received_by = u.id
            WHERE poi.part_id = ?

            UNION ALL

            SELECT 'transferred' AS event,
                   tt.created_at AS event_at,
                   tt.quantity,
                   tt.direction AS allocate_to,
                   '' AS order_number,
                   COALESCE(s.name, '') AS supplier_name,
                   tt.supplier_id,
                   COALESCE(u.display_name, '') AS user_name
            FROM truck_transfers tt
            LEFT JOIN suppliers s ON tt.supplier_id = s.id
            LEFT JOIN users u ON tt.created_by = u.id
            WHERE tt.part_id = ?

            UNION ALL

            SELECT 'consumed' AS event,
                   cl.consumed_at AS event_at,
                   cl.quantity,
                   'job' AS allocate_to,
                   '' AS order_number,
                   COALESCE(s.name, '') AS supplier_name,
                   cl.supplier_id,
                   COALESCE(u.display_name, '') AS user_name
            FROM consumption_log cl
            LEFT JOIN suppliers s ON cl.supplier_id = s.id
            LEFT JOIN users u ON cl.consumed_by = u.id
            WHERE cl.part_id = ?

            ORDER BY event_at DESC
        """, (part_id, part_id, part_id))

        return [dict(r) for r in rows]

    def get_suggested_return_supplier(
        self, part_id: int, job_id: int | None = None
    ) -> int | None:
        """Suggest which supplier to return a part to.

        Looks at the supply chain to find the most recent supplier
        that provided this part. If job_id is given, prioritizes
        the supplier that sent parts to that specific job.
        """
        if job_id:
            # First: check job_parts for direct supplier link
            row = self.db.execute("""
                SELECT supplier_id FROM job_parts
                WHERE job_id = ? AND part_id = ? AND supplier_id IS NOT NULL
                LIMIT 1
            """, (job_id, part_id))
            if row and row[0]["supplier_id"]:
                return row[0]["supplier_id"]

            # Second: check consumption log for this job
            row = self.db.execute("""
                SELECT supplier_id FROM consumption_log
                WHERE job_id = ? AND part_id = ? AND supplier_id IS NOT NULL
                ORDER BY consumed_at DESC LIMIT 1
            """, (job_id, part_id))
            if row and row[0]["supplier_id"]:
                return row[0]["supplier_id"]

        # Fallback: most recent supplier for this part from any source
        row = self.db.execute("""
            SELECT rl.supplier_id
            FROM receive_log rl
            JOIN purchase_order_items poi ON rl.order_item_id = poi.id
            WHERE poi.part_id = ? AND rl.supplier_id IS NOT NULL
            ORDER BY rl.received_at DESC, rl.id DESC LIMIT 1
        """, (part_id,))
        if row and row[0]["supplier_id"]:
            return row[0]["supplier_id"]

        return None

    # ── v12: Job Updates (Team Communication) ───────────────────────

    def create_job_update(
        self, job_id: int, user_id: int, message: str,
        update_type: str = "comment", photos: str = "[]",
    ) -> int:
        """Post a comment or update on a job."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO job_updates "
                "(job_id, user_id, message, update_type, photos) "
                "VALUES (?, ?, ?, ?, ?)",
                (job_id, user_id, message, update_type, photos),
            )
            return cursor.lastrowid

    def get_job_updates(
        self, job_id: int, limit: int = 50
    ) -> list:
        """Get updates/comments for a job, pinned first then by date."""
        from wired_part.database.models import JobUpdate

        rows = self.db.execute("""
            SELECT ju.*,
                   COALESCE(u.display_name, '') AS user_name,
                   j.job_number, j.name AS job_name
            FROM job_updates ju
            LEFT JOIN users u ON ju.user_id = u.id
            LEFT JOIN jobs j ON ju.job_id = j.id
            WHERE ju.job_id = ?
            ORDER BY ju.is_pinned DESC, ju.created_at DESC, ju.id DESC
            LIMIT ?
        """, (job_id, limit))
        return [
            JobUpdate(**{
                k: r[k] for k in r.keys()
                if k in JobUpdate.__dataclass_fields__
            })
            for r in rows
        ]

    def get_latest_updates_across_jobs(self, limit: int = 20) -> list:
        """Get the most recent job updates across all jobs (for dashboard)."""
        from wired_part.database.models import JobUpdate

        rows = self.db.execute("""
            SELECT ju.*,
                   COALESCE(u.display_name, '') AS user_name,
                   j.job_number, j.name AS job_name
            FROM job_updates ju
            LEFT JOIN users u ON ju.user_id = u.id
            LEFT JOIN jobs j ON ju.job_id = j.id
            ORDER BY ju.created_at DESC, ju.id DESC
            LIMIT ?
        """, (limit,))
        return [
            JobUpdate(**{
                k: r[k] for k in r.keys()
                if k in JobUpdate.__dataclass_fields__
            })
            for r in rows
        ]

    def pin_job_update(self, update_id: int, pinned: bool = True):
        """Pin or unpin a job update."""
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE job_updates SET is_pinned = ? WHERE id = ?",
                (1 if pinned else 0, update_id),
            )

    def delete_job_update(self, update_id: int):
        """Delete a job update."""
        with self.db.get_connection() as conn:
            conn.execute(
                "DELETE FROM job_updates WHERE id = ?", (update_id,)
            )
