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
    supplier: str = ""
    notes: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Joined fields (not stored directly)
    category_name: str = field(default="", repr=False)

    @property
    def is_low_stock(self) -> bool:
        return self.quantity < self.min_quantity

    @property
    def total_value(self) -> float:
        return self.quantity * self.unit_cost


@dataclass
class Job:
    id: Optional[int] = None
    job_number: str = ""
    name: str = ""
    customer: str = ""
    address: str = ""
    status: str = "active"
    notes: str = ""
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
    notes: str = ""
    assigned_at: Optional[datetime] = None
    # Joined fields
    part_number: str = field(default="", repr=False)
    part_description: str = field(default="", repr=False)

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
    created_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    # Joined fields
    part_number: str = field(default="", repr=False)
    part_description: str = field(default="", repr=False)
    truck_number: str = field(default="", repr=False)
    created_by_name: str = field(default="", repr=False)
    received_by_name: str = field(default="", repr=False)


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
    notes: str = ""
    consumed_at: Optional[datetime] = None
    # Joined fields
    part_number: str = field(default="", repr=False)
    part_description: str = field(default="", repr=False)
    truck_number: str = field(default="", repr=False)
    job_number: str = field(default="", repr=False)
    consumed_by_name: str = field(default="", repr=False)
