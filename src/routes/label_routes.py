"""
Shipping label routes - Section B: Shipping Label Support.
Handles metadata extraction from shipping labels.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.middleware.auth import get_current_user, UserContext
from src.handlers.label_handler import LabelHandler
from src.models.common import ErrorResponse
from src.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# Request/Response Models
class ProcessLabelRequest(BaseModel):
    """Request to process shipping label."""
    image_id: UUID = Field(..., description="UUID of uploaded shipping label image")


class ShippingLabelMetadata(BaseModel):
    """Extracted shipping label metadata."""
    carrier: str | None = Field(None, description="Carrier name (FedEx, UPS, DHL, etc.)")
    tracking_number: str | None = Field(None, description="Tracking number")
    recipient_name: str | None = Field(None, description="Recipient name")
    recipient_address: str | None = Field(None, description="Full recipient address")
    ship_date: str | None = Field(None, description="Shipping date (YYYY-MM-DD)")
    delivery_date: str | None = Field(None, description="Expected delivery date (YYYY-MM-DD)")
    service_type: str | None = Field(None, description="Service type (Ground, Express, etc.)")
    supplier: str | None = Field(None, description="Supplier name (if identified)")


class MatchedOrder(BaseModel):
    """Purchase order matched to shipping label."""
    order_id: UUID = Field(..., description="Purchase order UUID")
    order_number: str = Field(..., description="Purchase order number")
    supplier: str = Field(..., description="Supplier name")
    expected_delivery: str | None = Field(None, description="Expected delivery date")
    match_confidence: float = Field(..., ge=0.0, le=1.0, description="Match confidence score")


class ProcessLabelResponse(BaseModel):
    """Response from shipping label processing."""
    status: str = Field(..., description="Processing status")
    image_id: UUID = Field(..., description="Image UUID")
    metadata: ShippingLabelMetadata = Field(..., description="Extracted metadata")
    matched_orders: list[MatchedOrder] = Field(default_factory=list, description="Matched purchase orders")
    cost: float = Field(..., ge=0, description="Processing cost in USD")


class LabelMetadataResponse(BaseModel):
    """Response containing label metadata."""
    image_id: UUID = Field(..., description="Image UUID")
    metadata: ShippingLabelMetadata = Field(..., description="Extracted metadata")
    matched_orders: list[MatchedOrder] = Field(default_factory=list, description="Matched purchase orders")
    processed_at: str = Field(..., description="Processing timestamp")


@router.post(
    "/shipping-labels/process",
    response_model=ProcessLabelResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Image not found"},
        500: {"model": ErrorResponse, "description": "Processing failed"}
    },
    summary="Process shipping label",
    description="""
    Extract metadata from a shipping label image using gpt-4.1-nano.

    Workflow:
    1. Fetch image from storage
    2. Generate signed URL for LLM access
    3. Call gpt-4.1-nano to extract metadata
    4. Match to expected purchase orders
    5. Return metadata and matched orders

    Cost: ~$0.0005 per label (100x cheaper than full OCR pipeline)

    Extracted fields:
    - carrier: FedEx, UPS, DHL, USPS, etc.
    - tracking_number: Full tracking number
    - recipient_name: Delivery recipient
    - recipient_address: Full address
    - ship_date: Shipping date
    - delivery_date: Expected delivery date
    - service_type: Ground, Express, Priority, etc.
    """
)
async def process_shipping_label(
    request: ProcessLabelRequest,
    user: UserContext = Depends(get_current_user)
):
    """
    Process shipping label and extract metadata.

    Args:
        request: Processing request with image_id
        user: Authenticated user context

    Returns:
        Extracted metadata and matched orders

    Raises:
        HTTPException: If image not found or processing fails
    """
    handler = LabelHandler()

    try:
        logger.info("Processing shipping label", extra={
            "image_id": str(request.image_id),
            "yacht_id": str(user.yacht_id),
            "user_id": str(user.user_id)
        })

        result = await handler.process_shipping_label(
            image_id=request.image_id,
            yacht_id=user.yacht_id,
            user_id=user.user_id
        )

        # Convert to response format
        metadata = ShippingLabelMetadata(**result["metadata"])
        matched_orders = [
            MatchedOrder(
                order_id=order["order_id"],
                order_number=order["order_number"],
                supplier=order["supplier"],
                expected_delivery=order.get("expected_delivery"),
                match_confidence=order.get("match_confidence", 0.0)
            )
            for order in result.get("matched_orders", [])
        ]

        return ProcessLabelResponse(
            status=result["status"],
            image_id=request.image_id,
            metadata=metadata,
            matched_orders=matched_orders,
            cost=result["cost"]
        )

    except ValueError as e:
        logger.warning("Invalid shipping label request", extra={
            "image_id": str(request.image_id),
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_request", "message": str(e)}
        )

    except FileNotFoundError:
        logger.warning("Shipping label image not found", extra={
            "image_id": str(request.image_id)
        })
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "image_not_found", "message": "Shipping label image not found"}
        )

    except Exception as e:
        logger.error("Shipping label processing failed", extra={
            "image_id": str(request.image_id),
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "processing_failed", "message": "Failed to process shipping label"}
        )


@router.get(
    "/shipping-labels/{image_id}/metadata",
    response_model=LabelMetadataResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Metadata not found"},
        500: {"model": ErrorResponse, "description": "Failed to retrieve metadata"}
    },
    summary="Get shipping label metadata",
    description="""
    Retrieve previously extracted metadata for a shipping label.

    Returns the metadata stored in the database from prior processing.
    If the label hasn't been processed yet, returns 404.
    """
)
async def get_shipping_label_metadata(
    image_id: UUID,
    user: UserContext = Depends(get_current_user)
):
    """
    Get shipping label metadata.

    Args:
        image_id: Image UUID
        user: Authenticated user context

    Returns:
        Extracted metadata

    Raises:
        HTTPException: If metadata not found
    """
    handler = LabelHandler()

    try:
        # Fetch image metadata from database
        result = handler.supabase.table("pms_image_uploads") \
            .select("metadata, processing_status, created_at") \
            .eq("image_id", str(image_id)) \
            .eq("yacht_id", str(user.yacht_id)) \
            .eq("upload_type", "shipping_label") \
            .single() \
            .execute()

        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "not_found", "message": "Shipping label not found"}
            )

        if result.data["processing_status"] != "completed":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "not_processed",
                    "message": "Shipping label has not been processed yet",
                    "status": result.data["processing_status"]
                }
            )

        metadata_dict = result.data.get("metadata", {})
        matched_order_ids = metadata_dict.pop("matched_orders", [])

        # Fetch matched order details
        matched_orders = []
        if matched_order_ids:
            orders_result = handler.supabase.table("pms_purchase_orders") \
                .select("order_id, order_number, supplier, expected_delivery") \
                .in_("order_id", matched_order_ids) \
                .execute()

            matched_orders = [
                MatchedOrder(
                    order_id=order["order_id"],
                    order_number=order["order_number"],
                    supplier=order["supplier"],
                    expected_delivery=order.get("expected_delivery"),
                    match_confidence=0.85  # Default confidence
                )
                for order in orders_result.data or []
            ]

        return LabelMetadataResponse(
            image_id=image_id,
            metadata=ShippingLabelMetadata(**metadata_dict),
            matched_orders=matched_orders,
            processed_at=result.data["created_at"]
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error("Failed to retrieve shipping label metadata", extra={
            "image_id": str(image_id),
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "retrieval_failed", "message": "Failed to retrieve metadata"}
        )
