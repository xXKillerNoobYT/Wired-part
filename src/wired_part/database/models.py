"""Data models for the database layer."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Category:
    id: Optional[int] = None
    name: str = ""
    description: str = ""
    is_custom: int = 0
    color: str = "#6c7086"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Part:
    id: Optional[int] = None
    part_number: str = ""
    description: str = ""
    quantity: int = 0
    location: str = ""
    category_id: Optional[int] = None
    unit_cost: float = 0.0
    min_quantity: int = 0
    max_quantity: int = 0
    supplier: str = ""
    notes: str = ""
    name: str = ""  # Short display name (e.g. "Duplex Outlet")
    # v8 fields
    part_type: str = "general"  # 'general' or 'specific'
    brand_id: Optional[int] = None
    brand_part_number: str = ""
    local_part_number: str = ""
    image_path: str = ""
    subcategory: str = ""
    color_options: str = "[]"  # JSON array
    type_style: str = "[]"     # JSON array
    has_qr_tag: int = 0
    pdfs: str = "[]"           # JSON array of PDF file paths
    # v10 deprecation fields
    deprecation_status: Optional[str] = None  # NULL, pending, winding_down, zero_stock, archived
    deprecation_started_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Joined fields (not stored directly)
    category_name: str = field(default="", repr=False)
    brand_name: str = field(default="", repr=False)

    @property
    def display_name(self) -> str:
        """The name to show in UI — name if set, else description."""
        return self.name or self.description or self.part_number or "(Unnamed)"

    @property
    def is_low_stock(self) -> bool:
        return self.min_quantity > 0 and self.quantity < self.min_quantity

    @property
    def is_over_stock(self) -> bool:
        return self.max_quantity > 0 and self.quantity > self.max_quantity

    @property
    def quantity_window_str(self) -> str:
        """Format the quantity window as 'min / max' for display."""
        if self.min_quantity > 0 or self.max_quantity > 0:
            lo = str(self.min_quantity) if self.min_quantity > 0 else "—"
            hi = str(self.max_quantity) if self.max_quantity > 0 else "—"
            return f"{lo} / {hi}"
        return ""

    @property
    def total_value(self) -> float:
        return self.quantity * self.unit_cost

    @property
    def is_specific(self) -> bool:
        return self.part_type == "specific"

    @property
    def is_general(self) -> bool:
        return self.part_type == "general"

    @property
    def color_option_list(self) -> list[str]:
        import json
        try:
            return json.loads(self.color_options) if self.color_options else []
        except (json.JSONDecodeError, TypeError):
            return []

    @property
    def type_style_list(self) -> list[str]:
        import json
        try:
            return json.loads(self.type_style) if self.type_style else []
        except (json.JSONDecodeError, TypeError):
            return []

    @property
    def pdf_list(self) -> list[str]:
        import json
        try:
            return json.loads(self.pdfs) if self.pdfs else []
        except (json.JSONDecodeError, TypeError):
            return []

    @property
    def is_incomplete(self) -> bool:
        """Check if this part has incomplete required data based on type."""
        # Name is always required
        if not self.name or not self.name.strip():
            return True
        if self.unit_cost <= 0:
            return True
        if self.category_id is None:
            return True
        if self.part_type == "specific":
            # Specific parts need part_number, brand, and brand_part_number
            if not self.part_number or not self.part_number.strip():
                return True
            if not self.brand_id:
                return True
            if not self.brand_part_number or not self.brand_part_number.strip():
                return True
        return False


@dataclass
class Job:
    id: Optional[int] = None
    job_number: str = ""
    name: str = ""
    customer: str = ""
    address: str = ""
    status: str = "active"
    priority: int = 3  # 1=highest, 5=lowest
    notes: str = ""
    bill_out_rate: str = ""  # BRO category code (e.g. 'C', 'T&M', 'SERVICE')
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class JobPart:
    id: Optional[int] = None
    job_id: int = 0
    part_id: int = 0
    quantity_used: int = 1
    unit_cost_at_use: float = 0.0
    consumed_from_truck_id: Optional[int] = None
    consumed_by: Optional[int] = None
    supplier_id: Optional[int] = None       # v12: supplier origin tracking
    source_order_id: Optional[int] = None   # v12: PO that supplied this part
    notes: str = ""
    assigned_at: Optional[datetime] = None
    # Joined fields
    part_number: str = field(default="", repr=False)
    part_description: str = field(default="", repr=False)
    supplier_name: str = field(default="", repr=False)

    @property
    def total_cost(self) -> float:
        return self.quantity_used * self.unit_cost_at_use


@dataclass
class User:
    id: Optional[int] = None
    username: str = ""
    display_name: str = ""
    pin_hash: str = ""
    role: str = "user"
    is_active: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Truck:
    id: Optional[int] = None
    truck_number: str = ""
    name: str = ""
    assigned_user_id: Optional[int] = None
    notes: str = ""
    is_active: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Joined fields
    assigned_user_name: str = field(default="", repr=False)


@dataclass
class TruckInventory:
    id: Optional[int] = None
    truck_id: int = 0
    part_id: int = 0
    quantity: int = 0
    min_quantity: int = 0
    max_quantity: int = 0
    # Joined fields
    part_number: str = field(default="", repr=False)
    part_description: str = field(default="", repr=False)
    unit_cost: float = field(default=0.0, repr=False)
    truck_number: str = field(default="", repr=False)


@dataclass
class TruckTransfer:
    id: Optional[int] = None
    truck_id: int = 0
    part_id: int = 0
    quantity: int = 0
    direction: str = "outbound"
    status: str = "pending"
    created_by: Optional[int] = None
    received_by: Optional[int] = None
    notes: str = ""
    parts_list_id: Optional[int] = None
    job_id: Optional[int] = None
    source_order_id: Optional[int] = None   # v12: PO that supplied this part
    supplier_id: Optional[int] = None       # v12: supplier origin tracking
    created_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    # Joined fields
    part_number: str = field(default="", repr=False)
    part_description: str = field(default="", repr=False)
    truck_number: str = field(default="", repr=False)
    created_by_name: str = field(default="", repr=False)
    received_by_name: str = field(default="", repr=False)
    supplier_name: str = field(default="", repr=False)


@dataclass
class JobAssignment:
    id: Optional[int] = None
    job_id: int = 0
    user_id: int = 0
    role: str = "worker"
    assigned_at: Optional[datetime] = None
    # Joined fields
    user_name: str = field(default="", repr=False)
    job_number: str = field(default="", repr=False)
    job_name: str = field(default="", repr=False)


@dataclass
class Notification:
    id: Optional[int] = None
    user_id: Optional[int] = None
    title: str = ""
    message: str = ""
    severity: str = "info"
    source: str = "system"
    is_read: int = 0
    target_tab: str = ""
    target_data: str = ""
    created_at: Optional[datetime] = None


@dataclass
class ConsumptionLog:
    id: Optional[int] = None
    job_id: int = 0
    truck_id: int = 0
    part_id: int = 0
    quantity: int = 0
    unit_cost_at_use: float = 0.0
    consumed_by: Optional[int] = None
    supplier_id: Optional[int] = None       # v12: supplier origin tracking
    source_order_id: Optional[int] = None   # v12: PO that supplied this part
    notes: str = ""
    consumed_at: Optional[datetime] = None
    # Joined fields
    part_number: str = field(default="", repr=False)
    part_description: str = field(default="", repr=False)
    truck_number: str = field(default="", repr=False)
    job_number: str = field(default="", repr=False)
    consumed_by_name: str = field(default="", repr=False)
    supplier_name: str = field(default="", repr=False)


@dataclass
class LaborEntry:
    id: Optional[int] = None
    user_id: int = 0
    job_id: int = 0
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    hours: float = 0.0
    description: str = ""
    sub_task_category: str = "General"
    photos: str = "[]"
    clock_in_lat: Optional[float] = None
    clock_in_lon: Optional[float] = None
    clock_out_lat: Optional[float] = None
    clock_out_lon: Optional[float] = None
    is_overtime: int = 0
    bill_out_rate: str = ""  # BRO snapshot from job at time of entry
    created_at: Optional[datetime] = None
    # Joined fields
    user_name: str = field(default="", repr=False)
    job_number: str = field(default="", repr=False)
    job_name: str = field(default="", repr=False)

    @property
    def photo_list(self) -> list[str]:
        import json
        try:
            return json.loads(self.photos) if self.photos else []
        except (json.JSONDecodeError, TypeError):
            return []


@dataclass
class JobLocation:
    id: Optional[int] = None
    job_id: int = 0
    latitude: float = 0.0
    longitude: float = 0.0
    geocoded_address: str = ""
    cached_at: Optional[datetime] = None


@dataclass
class JobNotebook:
    id: Optional[int] = None
    job_id: int = 0
    title: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Joined fields
    job_number: str = field(default="", repr=False)


@dataclass
class NotebookSection:
    id: Optional[int] = None
    notebook_id: int = 0
    name: str = ""
    sort_order: int = 0
    created_at: Optional[datetime] = None


@dataclass
class NotebookPage:
    id: Optional[int] = None
    section_id: int = 0
    title: str = "Untitled"
    content: str = ""
    photos: str = "[]"
    part_references: str = "[]"
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Joined fields
    section_name: str = field(default="", repr=False)
    created_by_name: str = field(default="", repr=False)

    @property
    def photo_list(self) -> list[str]:
        import json
        try:
            return json.loads(self.photos) if self.photos else []
        except (json.JSONDecodeError, TypeError):
            return []

    @property
    def part_reference_list(self) -> list[int]:
        import json
        try:
            return json.loads(self.part_references) if self.part_references else []
        except (json.JSONDecodeError, TypeError):
            return []


@dataclass
class Hat:
    id: Optional[int] = None
    name: str = ""
    permissions: str = "[]"  # JSON array of permission keys
    is_system: int = 1       # 1 = built-in hat, 0 = custom
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def permission_list(self) -> list[str]:
        import json
        try:
            return json.loads(self.permissions) if self.permissions else []
        except (json.JSONDecodeError, TypeError):
            return []


@dataclass
class UserHat:
    id: Optional[int] = None
    user_id: int = 0
    hat_id: int = 0
    assigned_at: Optional[datetime] = None
    assigned_by: Optional[int] = None
    # Joined fields
    hat_name: str = field(default="", repr=False)
    user_name: str = field(default="", repr=False)
    assigned_by_name: str = field(default="", repr=False)


@dataclass
class Supplier:
    id: Optional[int] = None
    name: str = ""
    contact_name: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""
    notes: str = ""
    preference_score: int = 50  # 0-100, higher = preferred
    delivery_schedule: str = ""  # JSON or text description
    is_supply_house: int = 0  # 1 = local supply house for pickup orders
    operating_hours: str = ""  # e.g., "Mon-Fri 6am-5pm, Sat 7am-12pm"
    is_active: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Brand:
    id: Optional[int] = None
    name: str = ""
    website: str = ""
    notes: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class PartSupplier:
    """Many-to-many link between parts and suppliers (for specific parts)."""
    id: Optional[int] = None
    part_id: int = 0
    supplier_id: int = 0
    supplier_part_number: str = ""
    notes: str = ""
    # Joined fields
    supplier_name: str = field(default="", repr=False)


@dataclass
class PartVariant:
    """Type/style + color variant for a part."""
    id: Optional[int] = None
    part_id: int = 0
    type_style: str = ""
    color_finish: str = ""
    brand_part_number: str = ""
    image_path: str = ""
    notes: str = ""
    created_at: Optional[datetime] = None


@dataclass
class PartsList:
    id: Optional[int] = None
    name: str = ""
    list_type: str = "general"  # general, specific, fast
    job_id: Optional[int] = None
    notes: str = ""
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Joined fields
    job_number: str = field(default="", repr=False)
    created_by_name: str = field(default="", repr=False)


@dataclass
class PartsListItem:
    id: Optional[int] = None
    list_id: int = 0
    part_id: int = 0
    quantity: int = 1
    notes: str = ""
    # Joined fields
    part_number: str = field(default="", repr=False)
    part_description: str = field(default="", repr=False)
    unit_cost: float = field(default=0.0, repr=False)


@dataclass
class PurchaseOrder:
    id: Optional[int] = None
    order_number: str = ""
    supplier_id: int = 0
    parts_list_id: Optional[int] = None
    status: str = "draft"
    notes: str = ""
    created_by: Optional[int] = None
    submitted_at: Optional[datetime] = None
    expected_delivery: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Joined fields
    supplier_name: str = field(default="", repr=False)
    created_by_name: str = field(default="", repr=False)
    parts_list_name: str = field(default="", repr=False)
    item_count: int = field(default=0, repr=False)
    total_cost: float = field(default=0.0, repr=False)

    @property
    def is_editable(self) -> bool:
        return self.status in ("draft",)

    @property
    def is_receivable(self) -> bool:
        return self.status in ("submitted", "partial")


@dataclass
class PurchaseOrderItem:
    id: Optional[int] = None
    order_id: int = 0
    part_id: int = 0
    quantity_ordered: int = 1
    quantity_received: int = 0
    unit_cost: float = 0.0
    notes: str = ""
    # Joined fields
    part_number: str = field(default="", repr=False)
    part_description: str = field(default="", repr=False)

    @property
    def quantity_remaining(self) -> int:
        return max(0, self.quantity_ordered - self.quantity_received)

    @property
    def is_fully_received(self) -> bool:
        return self.quantity_received >= self.quantity_ordered

    @property
    def line_total(self) -> float:
        return self.quantity_ordered * self.unit_cost


@dataclass
class ReceiveLogEntry:
    id: Optional[int] = None
    order_item_id: int = 0
    quantity_received: int = 0
    allocate_to: str = "warehouse"
    allocate_truck_id: Optional[int] = None
    allocate_job_id: Optional[int] = None
    received_by: Optional[int] = None
    supplier_id: Optional[int] = None       # v12: denormalized supplier reference
    notes: str = ""
    received_at: Optional[datetime] = None
    # Joined fields
    part_number: str = field(default="", repr=False)
    part_description: str = field(default="", repr=False)
    truck_number: str = field(default="", repr=False)
    job_number: str = field(default="", repr=False)
    received_by_name: str = field(default="", repr=False)
    supplier_name: str = field(default="", repr=False)


@dataclass
class ReturnAuthorization:
    id: Optional[int] = None
    ra_number: str = ""
    order_id: Optional[int] = None
    supplier_id: int = 0
    status: str = "initiated"
    reason: str = "wrong_part"
    notes: str = ""
    created_by: Optional[int] = None
    credit_amount: float = 0.0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    picked_up_at: Optional[datetime] = None
    credit_received_at: Optional[datetime] = None
    # Joined fields
    supplier_name: str = field(default="", repr=False)
    order_number: str = field(default="", repr=False)
    created_by_name: str = field(default="", repr=False)
    item_count: int = field(default=0, repr=False)


@dataclass
class ReturnAuthorizationItem:
    id: Optional[int] = None
    ra_id: int = 0
    part_id: int = 0
    quantity: int = 1
    unit_cost: float = 0.0
    reason: str = ""
    # Joined fields
    part_number: str = field(default="", repr=False)
    part_description: str = field(default="", repr=False)

    @property
    def line_total(self) -> float:
        return self.quantity * self.unit_cost


@dataclass
class BillingCycle:
    id: Optional[int] = None
    job_id: Optional[int] = None  # NULL = company default
    cycle_type: str = "monthly"  # weekly, biweekly, monthly, quarterly
    billing_day: int = 1  # Day of week (1=Mon) or month
    next_billing_date: str = ""
    created_at: Optional[datetime] = None
    # Joined fields
    job_number: str = field(default="", repr=False)
    job_name: str = field(default="", repr=False)


@dataclass
class BillingPeriod:
    id: Optional[int] = None
    billing_cycle_id: int = 0
    period_start: str = ""
    period_end: str = ""
    status: str = "open"  # open, closed
    total_parts_cost: float = 0.0
    total_hours: float = 0.0
    created_at: Optional[datetime] = None
    # Joined fields
    cycle_type: str = field(default="", repr=False)
    job_id: Optional[int] = field(default=None, repr=False)
    job_number: str = field(default="", repr=False)


@dataclass
class InventoryAudit:
    id: Optional[int] = None
    audit_type: str = "warehouse"  # warehouse, truck, job
    target_id: Optional[int] = None  # truck_id or job_id (NULL for warehouse)
    part_id: int = 0
    expected_quantity: int = 0
    actual_quantity: int = 0
    status: str = "confirmed"  # confirmed, discrepancy, skipped
    audited_by: Optional[int] = None
    audited_at: Optional[datetime] = None
    # Joined fields
    part_number: str = field(default="", repr=False)
    part_name: str = field(default="", repr=False)
    audited_by_name: str = field(default="", repr=False)


# ── v12 models ──────────────────────────────────────────────────


@dataclass
class ActivityLogEntry:
    """Audit trail entry tracking all major actions in the system."""
    id: Optional[int] = None
    user_id: Optional[int] = None
    action: str = ""            # 'created', 'updated', 'deleted', 'received', etc.
    entity_type: str = ""       # 'job', 'part', 'order', 'labor', 'transfer', etc.
    entity_id: Optional[int] = None
    entity_label: str = ""      # Human-readable, e.g. "Job #4521 - Main St"
    details: str = ""           # JSON or text with additional context
    created_at: Optional[datetime] = None
    # Joined fields
    user_name: str = field(default="", repr=False)


@dataclass
class JobUpdate:
    """Team communication entry for a job."""
    id: Optional[int] = None
    job_id: int = 0
    user_id: int = 0
    message: str = ""
    update_type: str = "comment"    # comment, status_change, assignment, milestone
    is_pinned: int = 0
    photos: str = "[]"
    created_at: Optional[datetime] = None
    # Joined fields
    user_name: str = field(default="", repr=False)
    job_number: str = field(default="", repr=False)
    job_name: str = field(default="", repr=False)

    @property
    def photo_list(self) -> list[str]:
        import json
        try:
            return json.loads(self.photos) if self.photos else []
        except (json.JSONDecodeError, TypeError):
            return []
