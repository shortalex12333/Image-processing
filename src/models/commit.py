"""
Pydantic models for session commit operations.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field


class FinancialApproval(BaseModel):
    """Financial approval details."""

    approved_by: UUID
    approval_reference: str
    approved_at: datetime | None = None


class DeliveryMetadata(BaseModel):
    """Additional delivery metadata."""

    carrier: str | None = None
    tracking_number: str | None = None
    delivery_date: datetime | None = None
    received_by: str | None = None
    delivery_location: str | None = None


class CommitRequest(BaseModel):
    """Request schema for committing a receiving session."""

    commitment_notes: str = Field(..., min_length=1, max_length=2000)
    override_unverified: bool = False
    force_commit: bool = False
    financial_approval: FinancialApproval | None = None
    delivery_metadata: DeliveryMetadata | None = None


class ReceivingEvent(BaseModel):
    """Immutable receiving event record."""

    event_id: UUID
    event_number: str = Field(..., pattern=r"^RCV-EVT-\d{4}-\d{3,}$")
    session_id: UUID
    session_number: str | None = None
    lines_committed: int = Field(..., ge=1)
    total_cost: float | None = Field(None, ge=0.0)
    committed_by: UUID
    commitment_notes: str


class LowStockAlert(BaseModel):
    """Part that triggered low stock alert."""

    part_id: UUID
    part_number: str
    current_quantity: float
    minimum_quantity: float
    shortage: float


class InventoryUpdates(BaseModel):
    """Summary of inventory changes."""

    parts_updated: int = Field(..., ge=0)
    new_parts_created: int = Field(..., ge=0)
    total_quantity_added: float = Field(..., ge=0.0)
    transactions_created: int = Field(..., ge=0)
    low_stock_alerts: list[LowStockAlert] = Field(default_factory=list)


class BudgetImpact(BaseModel):
    """Impact on yacht budgets."""

    budget_id: UUID
    remaining_budget: float
    percentage_used: float = Field(..., ge=0.0, le=100.0)


class FinanceUpdates(BaseModel):
    """Financial transaction summary."""

    transactions_created: int = Field(..., ge=0)
    total_cost: float = Field(..., ge=0.0)
    currency: str = "USD"
    budget_impact: BudgetImpact | None = None


class ShoppingListUpdates(BaseModel):
    """Shopping list fulfillment summary."""

    items_fulfilled: int = Field(..., ge=0)
    items_partially_fulfilled: int = Field(..., ge=0)
    fulfilled_item_ids: list[UUID] = Field(default_factory=list)


class AuditTrail(BaseModel):
    """Audit log references."""

    audit_log_id: UUID
    signature: str
    old_state_hash: str | None = None
    new_state_hash: str | None = None


class CommitWarning(BaseModel):
    """Non-blocking warning generated during commit."""

    code: Literal[
        "UNVERIFIED_LINES",
        "MISSING_PART_NUMBERS",
        "MISSING_UNIT_PRICES",
        "OVERSTOCKING_WARNING",
        "DUPLICATE_PART_DELIVERY"
    ]
    message: str
    affected_line_ids: list[UUID] = Field(default_factory=list)


class NextStepsAfterCommit(BaseModel):
    """Recommended next actions after commit."""

    generate_labels: bool = False
    label_generation_url: str | None = None
    update_shopping_list: bool = False
    review_low_stock: bool = False


class CommitResponse(BaseModel):
    """Response schema for successful session commit."""

    status: Literal["success"] = "success"
    receiving_event: ReceivingEvent
    inventory_updates: InventoryUpdates
    finance_updates: FinanceUpdates | None = None
    shopping_list_updates: ShoppingListUpdates | None = None
    audit_trail: AuditTrail
    committed_at: datetime
    warnings: list[CommitWarning] = Field(default_factory=list)
    next_steps: NextStepsAfterCommit = Field(default_factory=NextStepsAfterCommit)
