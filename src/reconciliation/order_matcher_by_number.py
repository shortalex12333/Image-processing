"""
OrderMatcherByNumber - Find orders in database by order number.

Matches OCR-extracted order numbers to pms_orders table records,
respecting yacht_id for multi-tenant isolation.
"""

from typing import Optional, Dict, Any
from uuid import UUID

from src.database import get_supabase_service
from src.logger import get_logger

logger = get_logger(__name__)


class OrderMatcherByNumber:
    """
    Matches order numbers to database records.

    Uses exact string matching on order_number field with
    yacht_id filtering for RLS compliance.
    """

    def __init__(self):
        """Initialize order matcher with database connection."""
        self.supabase = get_supabase_service()
        logger.info("OrderMatcherByNumber initialized")

    async def find_order(
        self,
        yacht_id: UUID,
        order_number: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find order by order_number.

        Args:
            yacht_id: Yacht UUID for RLS filtering
            order_number: Order number extracted from OCR (e.g., "ORD-2024-042")

        Returns:
            Order dict if found, None if not found

        Example:
            >>> matcher = OrderMatcherByNumber()
            >>> order = await matcher.find_order(yacht_id, "ORD-2024-042")
            >>> if order:
            >>>     print(f"Found: {order['order_number']}")
        """
        try:
            # Query pms_orders with exact order_number match
            result = self.supabase.table("pms_orders") \
                .select("*") \
                .eq("yacht_id", str(yacht_id)) \
                .eq("order_number", order_number) \
                .limit(1) \
                .execute()

            if result.data and len(result.data) > 0:
                order = result.data[0]

                logger.info(
                    "Order found by order_number",
                    extra={
                        "yacht_id": str(yacht_id),
                        "order_number": order_number,
                        "order_id": order.get("id")
                    }
                )

                return order

            logger.info(
                "Order not found",
                extra={
                    "yacht_id": str(yacht_id),
                    "order_number": order_number
                }
            )

            return None

        except Exception as e:
            logger.error(
                "Order lookup failed",
                extra={
                    "yacht_id": str(yacht_id),
                    "order_number": order_number,
                    "error": str(e)
                },
                exc_info=True
            )
            # Return None on error (order not found)
            return None

    async def find_order_fuzzy(
        self,
        yacht_id: UUID,
        order_number: str,
        threshold: float = 0.8
    ) -> Optional[Dict[str, Any]]:
        """
        Find order using fuzzy matching (for OCR errors).

        Args:
            yacht_id: Yacht UUID
            order_number: Order number (may have OCR errors)
            threshold: Similarity threshold (0.0 to 1.0)

        Returns:
            Best matching order if similarity > threshold, None otherwise

        Note: Fuzzy matching is more expensive - use exact match first
        """
        try:
            # Get all orders for this yacht
            result = self.supabase.table("pms_orders") \
                .select("*") \
                .eq("yacht_id", str(yacht_id)) \
                .execute()

            if not result.data:
                return None

            # Use rapidfuzz for fuzzy matching
            from rapidfuzz import fuzz

            best_match = None
            best_score = 0.0

            for order in result.data:
                db_order_number = order.get("order_number", "")

                # Calculate similarity score
                score = fuzz.ratio(order_number, db_order_number) / 100.0

                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = order

            if best_match:
                logger.info(
                    "Order found via fuzzy matching",
                    extra={
                        "yacht_id": str(yacht_id),
                        "search_term": order_number,
                        "matched_number": best_match.get("order_number"),
                        "similarity_score": best_score
                    }
                )

            return best_match

        except Exception as e:
            logger.error(
                "Fuzzy order lookup failed",
                extra={
                    "yacht_id": str(yacht_id),
                    "order_number": order_number,
                    "error": str(e)
                },
                exc_info=True
            )
            return None

    async def get_shopping_list_items(
        self,
        yacht_id: UUID,
        order_id: str
    ) -> list[Dict[str, Any]]:
        """
        Get shopping list items for an order.

        Args:
            yacht_id: Yacht UUID for RLS filtering
            order_id: Order ID (UUID string)

        Returns:
            List of shopping list item dicts

        Example:
            >>> items = await matcher.get_shopping_list_items(yacht_id, order_id)
            >>> print(f"Found {len(items)} items")
        """
        try:
            result = self.supabase.table("pms_shopping_list_items") \
                .select("*") \
                .eq("yacht_id", str(yacht_id)) \
                .eq("order_id", order_id) \
                .execute()

            items = result.data or []

            logger.info(
                "Retrieved shopping list items",
                extra={
                    "yacht_id": str(yacht_id),
                    "order_id": order_id,
                    "item_count": len(items)
                }
            )

            return items

        except Exception as e:
            logger.error(
                "Failed to get shopping list items",
                extra={
                    "yacht_id": str(yacht_id),
                    "order_id": order_id,
                    "error": str(e)
                },
                exc_info=True
            )
            return []

    async def find_best_shopping_list_match(
        self,
        description: str,
        shopping_list_items: list[Dict[str, Any]],
        threshold: float = 0.7
    ) -> Optional[Dict[str, Any]]:
        """
        Find best matching shopping list item using fuzzy matching.

        Args:
            description: OCR-extracted line item description
            shopping_list_items: List of shopping list items to match against
            threshold: Minimum similarity score (0.0 to 1.0)

        Returns:
            Dict with matched item and match_score, or None if no good match
        """
        from rapidfuzz import fuzz

        if not description or not shopping_list_items:
            return None

        best_match = None
        best_score = 0.0

        for item in shopping_list_items:
            part_name = item.get("part_name", "")
            if not part_name:
                continue

            # Calculate similarity score
            score = fuzz.ratio(description.lower(), part_name.lower()) / 100.0

            if score > best_score:
                best_score = score
                best_match = item

        if best_score >= threshold:
            return {
                "matched_item": best_match,
                "match_score": best_score
            }

        return None

    def detect_discrepancies(
        self,
        expected: int,
        received: int,
        part_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Detect quantity discrepancies between expected and received.

        Args:
            expected: Quantity ordered
            received: Quantity received
            part_name: Part description

        Returns:
            Discrepancy dict if mismatch found, None if quantities match
        """
        if expected == received:
            return None

        shortage = expected - received

        discrepancy = {
            "type": "quantity_mismatch",
            "part_name": part_name,
            "expected_quantity": expected,
            "received_quantity": received,
            "shortage": shortage,  # Positive = short, Negative = overage
            "severity": self._calculate_severity(shortage, expected)
        }

        logger.info(
            "Quantity discrepancy detected",
            extra={
                "part_name": part_name,
                "expected": expected,
                "received": received,
                "shortage": shortage
            }
        )

        return discrepancy

    def _calculate_severity(self, shortage: int, expected: int) -> str:
        """Calculate discrepancy severity."""
        if expected == 0:
            return "high"

        percentage = abs(shortage) / expected

        if percentage >= 0.5:
            return "high"
        elif percentage >= 0.2:
            return "medium"
        else:
            return "low"
