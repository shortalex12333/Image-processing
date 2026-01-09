"""
Pydantic models for receiving sessions.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field

from src.models.draft_line import DraftLine


class SourceImage(BaseModel):
    """Image that was processed for this session."""

    image_id: UUID
    file_name: str
    uploaded_at: datetime
    processing_status: Literal["queued", "processing", "completed", "failed"]
    ocr_confidence: float | None = Field(None, ge=0.0, le=1.0)
    lines_extracted: int = Field(..., ge=0)


class ProcessingSummary(BaseModel):
    """Summary of processing metrics for a session."""

    total_lines_extracted: int = Field(..., ge=0)
    lines_verified: int = Field(..., ge=0)
    lines_with_suggestions: int = Field(..., ge=0)
    lines_requiring_manual_match: int = Field(..., ge=0)
    llm_invocations: int = Field(..., ge=0)
    total_cost_estimate: float = Field(..., ge=0.0)
    ocr_method: Literal["tesseract", "google_vision", "aws_textract", "mixed"]


class VerificationBlocker(BaseModel):
    """Issue blocking session commit."""

    code: Literal[
        "UNVERIFIED_LINES",
        "PROCESSING_INCOMPLETE",
        "DUPLICATE_SESSION",
        "MISSING_REQUIRED_DATA"
    ]
    message: str
    affected_line_ids: list[UUID] = Field(default_factory=list)


class VerificationStatus(BaseModel):
    """Progress toward commit readiness."""

    can_commit: bool
    verification_percentage: float = Field(..., ge=0.0, le=100.0)
    blockers: list[VerificationBlocker] = Field(default_factory=list)


class SessionMetadata(BaseModel):
    """Additional session metadata."""

    supplier: str | None = None
    order_reference: str | None = None
    delivery_date: datetime | None = None
    notes: str | None = None


class Session(BaseModel):
    """Receiving session with draft lines."""

    session_id: UUID
    session_number: str = Field(..., pattern=r"^RCV-\d{4}-\d{3,}$")
    yacht_id: UUID
    status: Literal["draft", "committed", "cancelled"]
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    committed_at: datetime | None = None
    committed_by: UUID | None = None
    draft_lines: list[DraftLine] = Field(default_factory=list)
    source_images: list[SourceImage] = Field(default_factory=list)
    processing_summary: ProcessingSummary
    verification_status: VerificationStatus
    metadata: SessionMetadata = Field(default_factory=SessionMetadata)


class SessionPermissions(BaseModel):
    """User's permissions for a session."""

    can_verify: bool
    can_commit: bool
    can_edit: bool
    can_cancel: bool
    can_override_verification: bool


class ShoppingListItem(BaseModel):
    """Shopping list item potentially fulfilled by session."""

    item_id: UUID
    part_id: UUID
    part_number: str
    quantity_requested: float
    quantity_approved: float | None = None
    status: Literal["candidate", "approved", "ordered", "received", "fulfilled"]


class PurchaseOrder(BaseModel):
    """Purchase order potentially related to delivery."""

    order_id: UUID
    order_number: str
    supplier: str
    order_date: datetime
    expected_delivery: datetime | None = None
    status: str


class RelatedEntities(BaseModel):
    """Related entities for context."""

    shopping_list_items: list[ShoppingListItem] = Field(default_factory=list)
    purchase_orders: list[PurchaseOrder] = Field(default_factory=list)


class SessionResponse(BaseModel):
    """Response schema for GET /api/v1/receiving/sessions/{id}"""

    session: Session
    permissions: SessionPermissions
    related_entities: RelatedEntities | None = None
