"""
Shopping list matcher for identifying items that fulfill shopping list requests.
"""

from uuid import UUID
from datetime import datetime, timedelta

from src.database import get_supabase_service
from src.logger import get_logger

logger = get_logger(__name__)


class ShoppingListMatcher:
    """Matches draft lines to shopping list items."""

    def __init__(self):
        self.supabase = get_supabase_service()

    async def check_shopping_list_match(
        self,
        yacht_id: UUID,
        part_id: UUID | None,
        quantity: float
    ) -> dict | None:
        """
        Check if this part fulfills a shopping list item.

        Args:
            yacht_id: Yacht UUID
            part_id: Matched part ID (if available)
            quantity: Quantity being received

        Returns:
            Shopping list match or None

        Example:
            >>> matcher = ShoppingListMatcher()
            >>> match = await matcher.check_shopping_list_match(
            ...     yacht_id=yacht_id,
            ...     part_id=part_id,
            ...     quantity=12.0
            ... )
            >>> match
            {
                "item_id": "uuid",
                "quantity_requested": 12.0,
                "quantity_approved": 12.0,
                "status": "approved",
                "fulfillment_percentage": 100.0
            }
        """
        if not part_id:
            return None

        try:
            # Query shopping list for this part
            # Status should be "approved" or "ordered" (not yet received)
            result = self.supabase.table("pms_shopping_list") \
                .select("item_id, quantity_requested, quantity_approved, status, requested_by, requested_at") \
                .eq("yacht_id", str(yacht_id)) \
                .eq("part_id", str(part_id)) \
                .in_("status", ["approved", "ordered"]) \
                .order("requested_at", desc=True) \
                .limit(1) \
                .execute()

            if not result.data:
                return None

            item = result.data[0]

            # Calculate fulfillment percentage
            requested = item["quantity_approved"] or item["quantity_requested"]
            fulfillment = min((quantity / requested) * 100, 100.0) if requested > 0 else 0.0

            match = {
                "item_id": item["item_id"],
                "quantity_requested": item["quantity_requested"],
                "quantity_approved": item["quantity_approved"],
                "status": item["status"],
                "fulfillment_percentage": fulfillment,
                "is_complete_fulfillment": fulfillment >= 100.0,
                "is_partial_fulfillment": 0 < fulfillment < 100.0
            }

            logger.info("Shopping list match found", extra={
                "yacht_id": str(yacht_id),
                "part_id": str(part_id),
                "item_id": item["item_id"],
                "fulfillment": f"{fulfillment:.1f}%"
            })

            return match

        except Exception as e:
            logger.error("Shopping list match failed", extra={
                "yacht_id": str(yacht_id),
                "part_id": str(part_id) if part_id else None,
                "error": str(e)
            })
            return None

    async def get_recent_shopping_items(
        self,
        yacht_id: UUID,
        days: int = 90,
        limit: int = 100
    ) -> list[dict]:
        """
        Get recent shopping list items for context.

        Useful for suggesting parts that are on the shopping list
        even if exact match isn't found.

        Args:
            yacht_id: Yacht UUID
            days: Look back this many days
            limit: Maximum items to return

        Returns:
            List of shopping list items
        """
        try:
            cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

            result = self.supabase.table("pms_shopping_list") \
                .select("item_id, part_id, quantity_requested, quantity_approved, status") \
                .eq("yacht_id", str(yacht_id)) \
                .gte("requested_at", cutoff_date) \
                .order("requested_at", desc=True) \
                .limit(limit) \
                .execute()

            return result.data or []

        except Exception as e:
            logger.error("Failed to fetch shopping list items", extra={
                "yacht_id": str(yacht_id),
                "error": str(e)
            })
            return []
