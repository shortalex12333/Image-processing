"""
Photo attachment routes - Sections C & D: Discrepancy and Part Photos.
Simple attachment workflow with no processing.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from typing import Literal

from src.middleware.auth import get_current_user, UserContext
from src.handlers.photo_handler import PhotoHandler
from src.models.common import ErrorResponse
from src.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# Request/Response Models
class AttachDiscrepancyPhotoRequest(BaseModel):
    """Request to attach discrepancy photo to entity."""
    image_id: UUID = Field(..., description="UUID of uploaded discrepancy photo")
    entity_type: Literal["fault", "work_order", "draft_line"] = Field(
        ...,
        description="Type of entity (fault, work_order, draft_line)"
    )
    entity_id: UUID = Field(..., description="UUID of entity to attach photo to")
    notes: str | None = Field(None, max_length=2000, description="Optional notes about discrepancy")


class AttachPartPhotoRequest(BaseModel):
    """Request to attach part photo."""
    image_id: UUID = Field(..., description="UUID of uploaded part photo")
    part_id: UUID = Field(..., description="UUID of part")
    photo_type: Literal["catalog", "installation", "location"] = Field(
        "catalog",
        description="Type of photo (catalog, installation, location)"
    )
    notes: str | None = Field(None, max_length=2000, description="Optional notes")


class AttachmentResponse(BaseModel):
    """Response from photo attachment."""
    status: str = Field(..., description="Attachment status")
    image_id: UUID = Field(..., description="Image UUID")
    entity_type: str = Field(..., description="Entity type")
    entity_id: UUID = Field(..., description="Entity UUID")


class PhotoMetadata(BaseModel):
    """Photo metadata."""
    image_id: UUID = Field(..., description="Image UUID")
    file_name: str = Field(..., description="Original filename")
    storage_path: str = Field(..., description="Storage path")
    attachment_type: str = Field(..., description="Attachment type")
    notes: str | None = Field(None, description="Notes")
    attached_at: str = Field(..., description="Attachment timestamp")
    uploaded_at: str = Field(..., description="Upload timestamp")


class EntityPhotosResponse(BaseModel):
    """Response containing entity photos."""
    entity_type: str = Field(..., description="Entity type")
    entity_id: UUID = Field(..., description="Entity UUID")
    photos: list[PhotoMetadata] = Field(..., description="List of attached photos")


@router.post(
    "/photos/attach/discrepancy",
    response_model=AttachmentResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Image or entity not found"},
        500: {"model": ErrorResponse, "description": "Attachment failed"}
    },
    summary="Attach discrepancy photo",
    description="""
    Attach a discrepancy photo to an entity (fault, work order, or draft line).

    Section C: Discrepancy Photos
    - Photos of damaged goods on arrival
    - Photos of equipment failures
    - Photos of work in progress
    - Photos documenting issues

    Entities that can have discrepancy photos:
    - pms_faults: Damaged equipment
    - pms_work_orders: Work in progress photos
    - pms_receiving_draft_lines: Damaged goods on arrival

    This is a simple attachment workflow - no processing occurs.
    The photo is linked to the entity via pms_entity_images junction table.
    """
)
async def attach_discrepancy_photo(
    request: AttachDiscrepancyPhotoRequest,
    user: UserContext = Depends(get_current_user)
):
    """
    Attach discrepancy photo to entity.

    Args:
        request: Attachment request
        user: Authenticated user context

    Returns:
        Attachment result

    Raises:
        HTTPException: If attachment fails
    """
    handler = PhotoHandler()

    try:
        logger.info("Attaching discrepancy photo", extra={
            "image_id": str(request.image_id),
            "entity_type": request.entity_type,
            "entity_id": str(request.entity_id),
            "yacht_id": str(user.yacht_id)
        })

        result = await handler.attach_discrepancy_photo(
            image_id=request.image_id,
            yacht_id=user.yacht_id,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            notes=request.notes
        )

        return AttachmentResponse(
            status=result["status"],
            image_id=result["image_id"],
            entity_type=result["entity_type"],
            entity_id=result["entity_id"]
        )

    except ValueError as e:
        logger.warning("Invalid discrepancy photo request", extra={
            "image_id": str(request.image_id),
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_request", "message": str(e)}
        )

    except FileNotFoundError:
        logger.warning("Discrepancy photo or entity not found", extra={
            "image_id": str(request.image_id),
            "entity_id": str(request.entity_id)
        })
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Image or entity not found"}
        )

    except Exception as e:
        logger.error("Discrepancy photo attachment failed", extra={
            "image_id": str(request.image_id),
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "attachment_failed", "message": "Failed to attach discrepancy photo"}
        )


@router.post(
    "/photos/attach/part",
    response_model=AttachmentResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Image or part not found"},
        500: {"model": ErrorResponse, "description": "Attachment failed"}
    },
    summary="Attach part photo",
    description="""
    Attach a part photo to a part in the catalog.

    Section D: Part Photos
    - Catalog photos: Main product photo for part catalog
    - Installation photos: Shows how part is installed
    - Location photos: Shows where part is stored

    Use cases:
    - Visual identification of parts
    - Installation reference for crew
    - Storage location documentation
    - Catalog/ordering reference

    This is a simple attachment workflow - no processing occurs.
    The photo is linked to the part via pms_entity_images junction table.
    """
)
async def attach_part_photo(
    request: AttachPartPhotoRequest,
    user: UserContext = Depends(get_current_user)
):
    """
    Attach part photo.

    Args:
        request: Attachment request
        user: Authenticated user context

    Returns:
        Attachment result

    Raises:
        HTTPException: If attachment fails
    """
    handler = PhotoHandler()

    try:
        logger.info("Attaching part photo", extra={
            "image_id": str(request.image_id),
            "part_id": str(request.part_id),
            "photo_type": request.photo_type,
            "yacht_id": str(user.yacht_id)
        })

        result = await handler.attach_part_photo(
            image_id=request.image_id,
            yacht_id=user.yacht_id,
            part_id=request.part_id,
            photo_type=request.photo_type,
            notes=request.notes
        )

        return AttachmentResponse(
            status=result["status"],
            image_id=result["image_id"],
            entity_type="part",
            entity_id=result["part_id"]
        )

    except ValueError as e:
        logger.warning("Invalid part photo request", extra={
            "image_id": str(request.image_id),
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_request", "message": str(e)}
        )

    except FileNotFoundError:
        logger.warning("Part photo or part not found", extra={
            "image_id": str(request.image_id),
            "part_id": str(request.part_id)
        })
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Image or part not found"}
        )

    except Exception as e:
        logger.error("Part photo attachment failed", extra={
            "image_id": str(request.image_id),
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "attachment_failed", "message": "Failed to attach part photo"}
        )


@router.get(
    "/{entity_type}/{entity_id}/photos",
    response_model=EntityPhotosResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid entity type"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Entity not found"},
        500: {"model": ErrorResponse, "description": "Failed to retrieve photos"}
    },
    summary="Get entity photos",
    description="""
    Retrieve all photos attached to an entity.

    Supported entity types:
    - fault: Fault photos
    - work_order: Work order photos
    - draft_line: Receiving draft line photos
    - part: Part photos (catalog, installation, location)

    Returns photos in reverse chronological order (newest first).
    """
)
async def get_entity_photos(
    entity_type: Literal["fault", "work_order", "draft_line", "part"],
    entity_id: UUID,
    user: UserContext = Depends(get_current_user)
):
    """
    Get all photos for an entity.

    Args:
        entity_type: Type of entity
        entity_id: Entity UUID
        user: Authenticated user context

    Returns:
        List of attached photos

    Raises:
        HTTPException: If retrieval fails
    """
    handler = PhotoHandler()

    try:
        logger.info("Retrieving entity photos", extra={
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "yacht_id": str(user.yacht_id)
        })

        photos = await handler.get_entity_photos(
            yacht_id=user.yacht_id,
            entity_type=entity_type,
            entity_id=entity_id
        )

        # Convert to response format
        photo_metadata = [
            PhotoMetadata(
                image_id=photo["image_id"],
                file_name=photo["file_name"],
                storage_path=photo["storage_path"],
                attachment_type=photo["attachment_type"],
                notes=photo.get("notes"),
                attached_at=photo["attached_at"],
                uploaded_at=photo["uploaded_at"]
            )
            for photo in photos
        ]

        return EntityPhotosResponse(
            entity_type=entity_type,
            entity_id=entity_id,
            photos=photo_metadata
        )

    except ValueError as e:
        logger.warning("Invalid entity type", extra={
            "entity_type": entity_type,
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_entity_type", "message": str(e)}
        )

    except Exception as e:
        logger.error("Failed to retrieve entity photos", extra={
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "retrieval_failed", "message": "Failed to retrieve photos"}
        )


@router.delete(
    "/photos/{image_id}/detach",
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Attachment not found"},
        500: {"model": ErrorResponse, "description": "Failed to detach photo"}
    },
    summary="Detach photo",
    description="""
    Remove photo attachment from entity.

    This removes the link between the photo and the entity.
    The photo file itself is NOT deleted from storage - only the attachment is removed.

    To fully delete the photo, you would need to:
    1. Detach from all entities
    2. Delete the image record from pms_image_uploads
    3. Delete the file from storage
    """
)
async def detach_photo(
    image_id: UUID,
    entity_type: str = Query(..., description="Entity type"),
    entity_id: UUID = Query(..., description="Entity UUID"),
    user: UserContext = Depends(get_current_user)
):
    """
    Detach photo from entity.

    Args:
        image_id: Image UUID
        entity_type: Entity type
        entity_id: Entity UUID
        user: Authenticated user context

    Returns:
        Success confirmation

    Raises:
        HTTPException: If detachment fails
    """
    handler = PhotoHandler()

    try:
        logger.info("Detaching photo", extra={
            "image_id": str(image_id),
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "yacht_id": str(user.yacht_id)
        })

        # Delete attachment record
        result = handler.supabase.table("pms_entity_images") \
            .delete() \
            .eq("image_id", str(image_id)) \
            .eq("entity_type", entity_type) \
            .eq("entity_id", str(entity_id)) \
            .eq("yacht_id", str(user.yacht_id)) \
            .execute()

        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "not_found", "message": "Attachment not found"}
            )

        return {
            "status": "detached",
            "image_id": str(image_id),
            "entity_type": entity_type,
            "entity_id": str(entity_id)
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error("Failed to detach photo", extra={
            "image_id": str(image_id),
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "detachment_failed", "message": "Failed to detach photo"}
        )
