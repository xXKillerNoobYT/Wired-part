"""Data models for the database layer."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Category:
    id: Optional[int] = None
    name: str = ""
    description: str = ""
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
    notes: str = ""
    assigned_at: Optional[datetime] = None
    # Joined fields
    part_number: str = field(default="", repr=False)
    part_description: str = field(default="", repr=False)

    @property
    def total_cost(self) -> float:
        return self.quantity_used * self.unit_cost_at_use
