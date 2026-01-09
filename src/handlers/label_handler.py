"""
Shipping label handler - extracts metadata from shipping labels.
Uses gpt-4.1-nano for cheap, fast metadata extraction.
"""

from uuid import UUID
from fastapi import UploadFile

from src.intake.validator import FileValidator
from src.intake.storage_manager import StorageManager
from src.extraction.llm_normalizer import LLMNormalizer
from src.extraction.cost_controller import SessionCostTracker
from src.database import get_supabase_service
from src.config import settings
from src.logger import get_logger

logger = get_logger(__name__)


class LabelHandler:
    """Handles shipping label metadata extraction."""

    def __init__(self):
        self.supabase = get_supabase_service()
        self.validator = FileValidator("shipping_label")
        self.storage_manager = StorageManager()

    async def process_shipping_label(
        self,
        image_id: UUID,
        yacht_id: UUID,
        user_id: UUID
    ) -> dict:
        """
        Extract metadata from shipping label.

        Args:
            image_id: Image UUID
            yacht_id: Yacht UUID
            user_id: User UUID

        Returns:
            Extracted metadata

        Workflow:
        1. Fetch image from storage
        2. Get signed URL for image
        3. Call gpt-4.1-nano with image
        4. Extract carrier, tracking, address, dates
        5. Save metadata to database
        6. Try to match to expected purchase orders

        Example Result:
        {
            "carrier": "FedEx",
            "tracking_number": "1234567890",
            "recipient_name": "MY Excellence",
            "ship_date": "2026-01-08",
            "delivery_date": "2026-01-10",
            "service_type": "Express"
        }
        """
        try:
            # Step 1: Fetch image metadata
            result = self.supabase.table("pms_image_uploads") \
                .select("storage_path, mime_type") \
                .eq("image_id", str(image_id)) \
                .single() \
                .execute()

            if not result.data:
                raise Exception(f"Image not found: {image_id}")

            storage_path = result.data["storage_path"]

            # Step 2: Get signed URL (for LLM to access)
            signed_url = self.storage_manager.get_signed_url(
                settings.storage_bucket_receiving,
                storage_path,
                expiry_seconds=3600
            )

            # Step 3: Extract metadata with LLM
            cost_tracker = SessionCostTracker(image_id)  # Use image_id as session
            normalizer = LLMNormalizer(cost_tracker)

            metadata = await normalizer.extract_shipping_label_metadata(signed_url)

            # Step 4: Try to match to purchase orders
            matched_orders = []
            if metadata.get("supplier"):
                from src.reconciliation.order_matcher import OrderMatcher
                from datetime import datetime

                matcher = OrderMatcher()
                delivery_date = None
                if metadata.get("delivery_date"):
                    try:
                        delivery_date = datetime.fromisoformat(metadata["delivery_date"])
                    except:
                        pass

                matched_orders = await matcher.check_expected_delivery(
                    yacht_id=yacht_id,
                    supplier=metadata.get("supplier"),
                    delivery_date=delivery_date
                )

            # Step 5: Save metadata
            self.supabase.table("pms_image_uploads") \
                .update({
                    "processing_status": "completed",
                    "metadata": {
                        **metadata,
                        "matched_orders": [str(o["order_id"]) for o in matched_orders]
                    }
                }) \
                .eq("image_id", str(image_id)) \
                .execute()

            logger.info("Shipping label processed", extra={
                "image_id": str(image_id),
                "carrier": metadata.get("carrier"),
                "tracking": metadata.get("tracking_number"),
                "matched_orders": len(matched_orders)
            })

            return {
                "status": "completed",
                "metadata": metadata,
                "matched_orders": matched_orders,
                "cost": cost_tracker.total_cost
            }

        except Exception as e:
            logger.error("Shipping label processing failed", extra={
                "image_id": str(image_id),
                "error": str(e)
            }, exc_info=True)
            raise
