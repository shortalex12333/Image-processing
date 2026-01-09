"""
Common Pydantic models shared across the application.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error response model."""

    status: Literal["error"] = "error"
    error_code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict | None = Field(None, description="Additional error context")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: str | None = Field(None, description="Unique request identifier")


class UploadedImage(BaseModel):
    """Metadata for an uploaded image."""

    image_id: UUID
    file_name: str
    file_size_bytes: int | None = None
    mime_type: str | None = None
    is_duplicate: bool
    existing_image_id: UUID | None = None
    processing_status: Literal["queued", "processing", "completed", "failed"]
    storage_path: str | None = None
    message: str | None = None


class NextSteps(BaseModel):
    """Recommended next actions after upload."""

    action: Literal["poll_status", "view_session", "retry_upload"]
    poll_url: str | None = None
    poll_interval_seconds: int | None = None


class UploadResponse(BaseModel):
    """Response schema for image upload endpoint."""

    status: Literal["success", "partial_success"]
    images: list[UploadedImage]
    session_id: UUID | None = None
    processing_eta_seconds: int | None = None
    next_steps: NextSteps | None = None
