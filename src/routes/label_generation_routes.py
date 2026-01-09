"""
Label generation routes - Section E: Label PDF Generation.
Handles QR code and PDF label generation for printing.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from pydantic import BaseModel, Field

from src.middleware.auth import get_current_user, UserContext
from src.handlers.label_generation_handler import LabelGenerationHandler
from src.models.common import ErrorResponse
from src.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# Request Models
class GeneratePartLabelsRequest(BaseModel):
    """Request to generate part labels PDF."""
    part_ids: list[UUID] | None = Field(None, description="Specific part UUIDs (if None, all parts)")
    location: str | None = Field(None, max_length=200, description="Filter by location")
    category: str | None = Field(None, max_length=100, description="Filter by category")


class GenerateEquipmentLabelsRequest(BaseModel):
    """Request to generate equipment labels PDF."""
    equipment_ids: list[UUID] | None = Field(None, description="Specific equipment UUIDs (if None, all)")
    location: str | None = Field(None, max_length=200, description="Filter by location")
    category: str | None = Field(None, max_length=100, description="Filter by category")


@router.post(
    "/labels/parts/pdf",
    response_class=Response,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "No parts found"},
        500: {"model": ErrorResponse, "description": "Generation failed"}
    },
    summary="Generate part labels PDF",
    description="""
    Generate printable PDF with part labels.

    Section E: Label PDF Generation
    - QR codes link to part details in Cloud_PMS
    - Compatible with Avery 5160 labels (3 cols x 10 rows)
    - Includes part number, name, manufacturer, location, quantity

    Use cases:
    - Print labels for new parts
    - Re-label existing parts
    - Organize storage locations
    - Inventory management

    Returns PDF file ready for printing on standard label sheets.
    """
)
async def generate_part_labels_pdf(
    request: GeneratePartLabelsRequest,
    user: UserContext = Depends(get_current_user)
):
    """
    Generate part labels PDF.

    Args:
        request: Generation request with filters
        user: Authenticated user context

    Returns:
        PDF file (application/pdf)

    Raises:
        HTTPException: If generation fails
    """
    handler = LabelGenerationHandler()

    try:
        logger.info("Generating part labels PDF", extra={
            "yacht_id": str(user.yacht_id),
            "part_count": len(request.part_ids) if request.part_ids else "all",
            "location": request.location,
            "category": request.category
        })

        pdf_bytes = await handler.generate_part_labels_pdf(
            yacht_id=user.yacht_id,
            part_ids=request.part_ids,
            location=request.location,
            category=request.category
        )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="part_labels_{user.yacht_id}.pdf"'
            }
        )

    except ValueError as e:
        logger.warning("Invalid part labels request", extra={
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "no_parts_found", "message": str(e)}
        )

    except Exception as e:
        logger.error("Part labels PDF generation failed", extra={
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "generation_failed", "message": "Failed to generate labels PDF"}
        )


@router.post(
    "/labels/equipment/pdf",
    response_class=Response,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "No equipment found"},
        500: {"model": ErrorResponse, "description": "Generation failed"}
    },
    summary="Generate equipment labels PDF",
    description="""
    Generate printable PDF with equipment labels.

    Section E: Label PDF Generation
    - QR codes link to equipment details in Cloud_PMS
    - Compatible with Avery 5160 labels (3 cols x 10 rows)
    - Includes equipment code, name, manufacturer, model, location

    Use cases:
    - Label new equipment
    - Re-label existing equipment
    - Organize equipment locations
    - Maintenance tracking

    Returns PDF file ready for printing on standard label sheets.
    """
)
async def generate_equipment_labels_pdf(
    request: GenerateEquipmentLabelsRequest,
    user: UserContext = Depends(get_current_user)
):
    """
    Generate equipment labels PDF.

    Args:
        request: Generation request with filters
        user: Authenticated user context

    Returns:
        PDF file (application/pdf)

    Raises:
        HTTPException: If generation fails
    """
    handler = LabelGenerationHandler()

    try:
        logger.info("Generating equipment labels PDF", extra={
            "yacht_id": str(user.yacht_id),
            "equipment_count": len(request.equipment_ids) if request.equipment_ids else "all",
            "location": request.location,
            "category": request.category
        })

        pdf_bytes = await handler.generate_equipment_labels_pdf(
            yacht_id=user.yacht_id,
            equipment_ids=request.equipment_ids,
            location=request.location,
            category=request.category
        )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="equipment_labels_{user.yacht_id}.pdf"'
            }
        )

    except ValueError as e:
        logger.warning("Invalid equipment labels request", extra={
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "no_equipment_found", "message": str(e)}
        )

    except Exception as e:
        logger.error("Equipment labels PDF generation failed", extra={
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "generation_failed", "message": "Failed to generate labels PDF"}
        )


@router.get(
    "/labels/parts/{part_id}/pdf",
    response_class=Response,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Part not found"},
        500: {"model": ErrorResponse, "description": "Generation failed"}
    },
    summary="Generate single part label PDF",
    description="""
    Generate PDF with single part label (for quick printing).

    Returns PDF with one label for immediate printing.
    Useful for quickly printing a label for a newly received part.
    """
)
async def generate_single_part_label(
    part_id: UUID,
    user: UserContext = Depends(get_current_user)
):
    """
    Generate single part label PDF.

    Args:
        part_id: Part UUID
        user: Authenticated user context

    Returns:
        PDF file (application/pdf)

    Raises:
        HTTPException: If generation fails
    """
    handler = LabelGenerationHandler()

    try:
        pdf_bytes = await handler.generate_single_part_label(
            yacht_id=user.yacht_id,
            part_id=part_id
        )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="part_label_{part_id}.pdf"'
            }
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": str(e)}
        )

    except Exception as e:
        logger.error("Single part label generation failed", extra={
            "part_id": str(part_id),
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "generation_failed", "message": "Failed to generate label"}
        )


@router.get(
    "/labels/equipment/{equipment_id}/pdf",
    response_class=Response,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Equipment not found"},
        500: {"model": ErrorResponse, "description": "Generation failed"}
    },
    summary="Generate single equipment label PDF",
    description="""
    Generate PDF with single equipment label (for quick printing).

    Returns PDF with one label for immediate printing.
    Useful for quickly printing a label for newly installed equipment.
    """
)
async def generate_single_equipment_label(
    equipment_id: UUID,
    user: UserContext = Depends(get_current_user)
):
    """
    Generate single equipment label PDF.

    Args:
        equipment_id: Equipment UUID
        user: Authenticated user context

    Returns:
        PDF file (application/pdf)

    Raises:
        HTTPException: If generation fails
    """
    handler = LabelGenerationHandler()

    try:
        pdf_bytes = await handler.generate_single_equipment_label(
            yacht_id=user.yacht_id,
            equipment_id=equipment_id
        )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="equipment_label_{equipment_id}.pdf"'
            }
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": str(e)}
        )

    except Exception as e:
        logger.error("Single equipment label generation failed", extra={
            "equipment_id": str(equipment_id),
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "generation_failed", "message": "Failed to generate label"}
        )


@router.get(
    "/labels/parts/{part_id}/qr",
    response_class=Response,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        500: {"model": ErrorResponse, "description": "Generation failed"}
    },
    summary="Generate part QR code",
    description="""
    Generate QR code image (PNG) for a part.

    Returns PNG image that can be displayed in UI or printed separately.
    QR code links to part details in Cloud_PMS.
    """
)
async def generate_part_qr(
    part_id: UUID,
    part_number: str = Query(..., description="Part number"),
    user: UserContext = Depends(get_current_user)
):
    """
    Generate part QR code PNG.

    Args:
        part_id: Part UUID
        part_number: Part number
        user: Authenticated user context

    Returns:
        PNG image (image/png)
    """
    handler = LabelGenerationHandler()

    try:
        qr_bytes = await handler.generate_part_qr_only(part_id, part_number)

        return Response(
            content=qr_bytes,
            media_type="image/png",
            headers={
                "Content-Disposition": f'inline; filename="part_{part_id}_qr.png"'
            }
        )

    except Exception as e:
        logger.error("Part QR generation failed", extra={
            "part_id": str(part_id),
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "generation_failed", "message": "Failed to generate QR code"}
        )


@router.get(
    "/labels/equipment/{equipment_id}/qr",
    response_class=Response,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        500: {"model": ErrorResponse, "description": "Generation failed"}
    },
    summary="Generate equipment QR code",
    description="""
    Generate QR code image (PNG) for equipment.

    Returns PNG image that can be displayed in UI or printed separately.
    QR code links to equipment details in Cloud_PMS.
    """
)
async def generate_equipment_qr(
    equipment_id: UUID,
    equipment_code: str = Query(..., description="Equipment code"),
    user: UserContext = Depends(get_current_user)
):
    """
    Generate equipment QR code PNG.

    Args:
        equipment_id: Equipment UUID
        equipment_code: Equipment code
        user: Authenticated user context

    Returns:
        PNG image (image/png)
    """
    handler = LabelGenerationHandler()

    try:
        qr_bytes = await handler.generate_equipment_qr_only(equipment_id, equipment_code)

        return Response(
            content=qr_bytes,
            media_type="image/png",
            headers={
                "Content-Disposition": f'inline; filename="equipment_{equipment_id}_qr.png"'
            }
        )

    except Exception as e:
        logger.error("Equipment QR generation failed", extra={
            "equipment_id": str(equipment_id),
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "generation_failed", "message": "Failed to generate QR code"}
        )
