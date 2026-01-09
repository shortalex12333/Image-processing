"""
Upload routes for image/PDF file uploads.
Handles POST /api/v1/images/upload
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, status

from src.handlers.receiving_handler import ReceivingHandler
from src.middleware.auth import get_auth_context, AuthContext
from src.models.common import UploadResponse, ErrorResponse
from src.intake.validator import ValidationError
from src.intake.rate_limiter import RateLimitExceeded
from src.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("/images/upload", response_model=UploadResponse)
async def upload_images(
    files: Annotated[list[UploadFile], File(description="Images or PDFs to upload")],
    upload_type: Annotated[
        Literal["receiving", "shipping_label", "discrepancy", "part_photo", "finance"],
        Form(description="Type of upload")
    ],
    session_id: Annotated[UUID | None, Form(description="Existing session UUID (optional)")] = None,
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Upload images or PDFs for processing.

    - **files**: One or more image/PDF files (max 10)
    - **upload_type**: Type of upload (determines processing pipeline)
    - **session_id**: Optional existing session UUID (for adding to existing session)

    Returns upload status with processing metadata.

    **Rate Limit**: 50 uploads per hour per yacht.
    **File Size**: Maximum 15MB per file.
    **Allowed Types**: JPEG, PNG, HEIC, PDF (varies by upload_type).
    """
    # Validate file count
    if len(files) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 files per upload"
        )

    handler = ReceivingHandler()

    try:
        result = await handler.process_upload(
            yacht_id=auth.yacht_id,
            user_id=auth.user_id,
            files=files,
            upload_type=upload_type,
            session_id=session_id
        )

        return UploadResponse(**result)

    except RateLimitExceeded as e:
        logger.warning("Rate limit exceeded", extra={
            "yacht_id": str(auth.yacht_id),
            "user_id": str(auth.user_id),
            "current_count": e.current_count,
            "limit": e.limit
        })
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error_code": "RATE_LIMIT_EXCEEDED",
                "message": f"Upload rate limit exceeded: {e.current_count}/{e.limit} uploads in last hour",
                "retry_after_seconds": e.retry_after_seconds
            }
        )

    except ValidationError as e:
        logger.warning("File validation failed", extra={
            "yacht_id": str(auth.yacht_id),
            "error_code": e.error_code,
            "message": e.message
        })
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": e.error_code,
                "message": e.message,
                "details": e.details
            }
        )

    except Exception as e:
        logger.error("Upload failed", extra={
            "yacht_id": str(auth.yacht_id),
            "upload_type": upload_type,
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "UPLOAD_FAILED",
                "message": "Failed to process upload",
                "details": {"error": str(e)}
            }
        )


@router.get("/images/{image_id}/status")
async def get_image_status(
    image_id: UUID,
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Get processing status for an uploaded image.

    Returns current processing status and any extracted data.
    """
    from src.database import get_supabase_for_user

    supabase = get_supabase_for_user(f"Bearer {auth.user_id}")  # TODO: Use actual JWT

    try:
        result = supabase.table("pms_image_uploads") \
            .select("image_id, file_name, processing_status, uploaded_at, metadata") \
            .eq("image_id", str(image_id)) \
            .eq("yacht_id", str(auth.yacht_id)) \
            .single() \
            .execute()

        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image not found"
            )

        return result.data

    except Exception as e:
        logger.error("Failed to get image status", extra={
            "image_id": str(image_id),
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve image status"
        )
