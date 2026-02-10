"""Repository layer — all CRUD operations and queries."""

from typing import Optional

from .connection import DatabaseConnection
from .models import Category, Job, JobPart, Part


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
                "INSERT INTO categories (name, description) VALUES (?, ?)",
                (category.name, category.description),
            )
            return cursor.lastrowid

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
        """Full-text search across parts."""
        if not query.strip():
            return self.get_all_parts()
        # FTS5 query — append * for prefix matching
        fts_query = " ".join(f"{term}*" for term in query.split())
        rows = self.db.execute("""
            SELECT p.*, COALESCE(c.name, '') AS category_name
            FROM parts p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.id IN (
                SELECT rowid FROM parts_fts WHERE parts_fts MATCH ?
            )
            ORDER BY p.part_number
        """, (fts_query,))
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

    # ── Jobs ────────────────────────────────────────────────────

    def get_all_jobs(self, status: Optional[str] = None) -> list[Job]:
        if status and status != "all":
            rows = self.db.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC",
                (status,),
            )
        else:
            rows = self.db.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC"
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
                    (job_number, name, customer, address, status, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                job.job_number, job.name, job.customer,
                job.address, job.status, job.notes,
            ))
            return cursor.lastrowid

    def update_job(self, job: Job):
        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE jobs SET
                    job_number = ?, name = ?, customer = ?,
                    address = ?, status = ?, notes = ?,
                    completed_at = ?
                WHERE id = ?
            """, (
                job.job_number, job.name, job.customer,
                job.address, job.status, job.notes,
                job.completed_at, job.id,
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
