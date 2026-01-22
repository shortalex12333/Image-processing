"""
FastAPI routes for document processing.

Endpoints:
- POST /upload - Upload and process packing slip
- GET /health - Health check
"""

from typing import Dict, Any
from uuid import UUID
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from pydantic import BaseModel

from src.handlers.document_handler import DocumentHandler
from src.intake.rate_limiter import RateLimitExceeded
from src.logger import get_logger

logger = get_logger(__name__)

# Create router with prefix
router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


class UploadResponse(BaseModel):
    """Response model for document upload"""
    temp_file_id: str
    yacht_id: str
    ocr_results: Dict[str, Any]
    document_classification: Dict[str, Any]
    extracted_entities: Dict[str, Any]
    matching: Dict[str, Any]
    processing_time_total_ms: int


class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str
    ocr_engine: str
    version: str


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload and process packing slip",
    description="Upload a packing slip image, extract text via OCR, classify document, extract entities, and match to database"
)
async def upload_packing_slip(
    yacht_id: str,
    file: UploadFile = File(..., description="Packing slip image (PNG, JPG, PDF)")
) -> UploadResponse:
    """
    Process packing slip end-to-end.

    Args:
        yacht_id: Yacht UUID for tenant isolation
        file: Uploaded document file

    Returns:
        Processing results with OCR, classification, entities, and matching

    Raises:
        400: Invalid yacht_id or file format
        429: Rate limit exceeded
        500: Processing error
    """
    try:
        # Validate yacht_id
        try:
            yacht_uuid = UUID(yacht_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid yacht_id format: {yacht_id}"
            )

        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No filename provided"
            )

        # Check file extension
        allowed_extensions = {".png", ".jpg", ".jpeg", ".pdf"}
        import os
        _, ext = os.path.splitext(file.filename)
        if ext.lower() not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {ext}. Allowed: {allowed_extensions}"
            )

        # Read file bytes
        file_bytes = await file.read()

        if len(file_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty file"
            )

        # Process with DocumentHandler
        handler = DocumentHandler()

        try:
            preview = await handler.process_packing_slip_preview(
                yacht_id=yacht_uuid,
                file_bytes=file_bytes,
                filename=file.filename
            )
        except RateLimitExceeded as e:
            logger.warning(
                "Rate limit exceeded",
                extra={"yacht_id": yacht_id, "error": str(e)}
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=str(e)
            )

        logger.info(
            "Document processed via API",
            extra={
                "yacht_id": yacht_id,
                "filename": file.filename,
                "temp_file_id": preview["temp_file_id"],
                "processing_time_ms": preview["processing_time_total_ms"]
            }
        )

        # Return response (exclude temp_file_path from response)
        return UploadResponse(
            temp_file_id=preview["temp_file_id"],
            yacht_id=yacht_id,
            ocr_results=preview["ocr_results"],
            document_classification=preview["document_classification"],
            extracted_entities=preview["extracted_entities"],
            matching=preview["matching"],
            processing_time_total_ms=preview["processing_time_total_ms"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Document processing failed",
            extra={
                "yacht_id": yacht_id,
                "filename": file.filename if file else None,
                "error": str(e)
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document processing failed: {str(e)}"
        )


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Check API health and OCR engine status"
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns:
        Health status with OCR engine info
    """
    try:
        handler = DocumentHandler()

        return HealthResponse(
            status="healthy",
            ocr_engine=handler.ocr_engine.get_engine_name(),
            version="1.0.0"
        )

    except Exception as e:
        logger.error(
            "Health check failed",
            extra={"error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service unhealthy: {str(e)}"
        )
