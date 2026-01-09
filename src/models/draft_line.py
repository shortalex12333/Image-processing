"""
Pydantic models for draft line items.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class SuggestedPart(BaseModel):
    """Suggested part match for a draft line."""

    part_id: UUID
    part_number: str
    part_name: str
    manufacturer: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    match_reason: Literal[
        "exact_part_number",
        "fuzzy_description",
        "on_shopping_list",
        "recent_order",
        "user_override"
    ]
    current_stock: float | None = None
    bin_location: str | None = None


class AlternativeSuggestion(BaseModel):
    """Alternative part suggestion."""

    part_id: UUID
    part_number: str
    part_name: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    match_reason: str


class ShoppingListMatch(BaseModel):
    """Shopping list item that matches this draft line."""

    item_id: UUID
    quantity_requested: float
    quantity_approved: float | None = None
    status: Literal["candidate", "approved", "ordered", "received", "fulfilled"]


class DiscrepancyPhoto(BaseModel):
    """Photo documenting a discrepancy."""

    image_id: UUID
    file_name: str
    uploaded_at: datetime


class DraftLine(BaseModel):
    """Draft line item extracted from packing slip."""

    draft_line_id: UUID
    line_number: int = Field(..., ge=1)
    quantity: float = Field(..., gt=0)
    unit: Literal["ea", "box", "case", "pcs", "lbs", "kg", "g", "ft", "m", "gal", "L"]
    description: str = Field(..., min_length=1, max_length=500)
    extracted_part_number: str | None = None
    is_verified: bool
    verified_by: UUID | None = None
    verified_at: datetime | None = None
    source_image_id: UUID
    suggested_part: SuggestedPart | None = None
    alternative_suggestions: list[AlternativeSuggestion] = Field(default_factory=list)
    shopping_list_match: ShoppingListMatch | None = None
    has_discrepancy: bool = False
    discrepancy_type: Literal["damaged", "incorrect", "missing", "quantity_mismatch"] | None = None
    discrepancy_notes: str | None = None
    discrepancy_photos: list[DiscrepancyPhoto] = Field(default_factory=list)

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        """Ensure description is not just whitespace."""
        if not v.strip():
            raise ValueError("Description cannot be empty or whitespace only")
        return v.strip()
