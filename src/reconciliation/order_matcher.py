"""
Order matcher for finding parts in recent purchase orders.
Helps boost confidence when received items match expected deliveries.
"""

from uuid import UUID
from datetime import datetime, timedelta

from src.database import get_supabase_service
from src.logger import get_logger

logger = get_logger(__name__)


class OrderMatcher:
    """Matches draft lines to purchase orders."""

    def __init__(self):
        self.supabase = get_supabase_service()

    async def find_recent_orders(
        self,
        yacht_id: UUID,
        part_id: UUID | None,
        days: int = 90
    ) -> list[dict]:
        """
        Find recent purchase orders containing this part.

        Args:
            yacht_id: Yacht UUID
            part_id: Part ID to search for
            days: Look back this many days

        Returns:
            List of matching orders

        Example:
            >>> matcher = OrderMatcher()
            >>> orders = await matcher.find_recent_orders(
            ...     yacht_id=yacht_id,
            ...     part_id=part_id,
            ...     days=90
            ... )
            >>> orders[0]
            {
                "order_id": "uuid",
                "order_number": "PO-2026-001",
                "supplier": "MTU Parts Direct",
                "order_date": "2026-01-05",
                "quantity_ordered": 12.0,
                "expected_delivery": "2026-01-15",
                "days_since_order": 4
            }
        """
        if not part_id:
            return []

        try:
            cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

            # Query purchase order line items
            result = self.supabase.table("pms_purchase_order_items") \
                .select("""
                    order_id,
                    quantity,
                    pms_purchase_orders!inner(
                        order_number,
                        supplier,
                        order_date,
                        expected_delivery,
                        status
                    )
                """) \
                .eq("part_id", str(part_id)) \
                .gte("pms_purchase_orders.order_date", cutoff_date) \
                .in_("pms_purchase_orders.status", ["ordered", "in_transit", "partially_received"]) \
                .order("pms_purchase_orders.order_date", desc=True) \
                .limit(5) \
                .execute()

            if not result.data:
                return []

            # Format results
            orders = []
            for item in result.data:
                order = item["pms_purchase_orders"]
                order_date = datetime.fromisoformat(order["order_date"].replace('Z', '+00:00'))
                days_since = (datetime.utcnow() - order_date).days

                orders.append({
                    "order_id": item["order_id"],
                    "order_number": order["order_number"],
                    "supplier": order["supplier"],
                    "order_date": order["order_date"],
                    "quantity_ordered": item["quantity"],
                    "expected_delivery": order.get("expected_delivery"),
                    "status": order["status"],
                    "days_since_order": days_since
                })

            logger.info("Recent orders found", extra={
                "yacht_id": str(yacht_id),
                "part_id": str(part_id),
                "order_count": len(orders)
            })

            return orders

        except Exception as e:
            logger.error("Order matching failed", extra={
                "yacht_id": str(yacht_id),
                "part_id": str(part_id) if part_id else None,
                "error": str(e)
            })
            return []

    async def check_expected_delivery(
        self,
        yacht_id: UUID,
        supplier: str | None = None,
        delivery_date: datetime | None = None,
        days_tolerance: int = 7
    ) -> list[dict]:
        """
        Check for purchase orders with expected delivery around this date.

        Useful for matching entire receiving sessions to expected deliveries.

        Args:
            yacht_id: Yacht UUID
            supplier: Supplier name (if detected from packing slip)
            delivery_date: Expected/actual delivery date
            days_tolerance: Match orders within this many days

        Returns:
            List of matching purchase orders
        """
        try:
            query = self.supabase.table("pms_purchase_orders") \
                .select("order_id, order_number, supplier, order_date, expected_delivery, status") \
                .eq("yacht_id", str(yacht_id)) \
                .in_("status", ["ordered", "in_transit"])

            # Filter by supplier if provided
            if supplier:
                query = query.ilike("supplier", f"%{supplier}%")

            # Filter by delivery date if provided
            if delivery_date:
                start_date = (delivery_date - timedelta(days=days_tolerance)).isoformat()
                end_date = (delivery_date + timedelta(days=days_tolerance)).isoformat()
                query = query.gte("expected_delivery", start_date) \
                             .lte("expected_delivery", end_date)

            result = query.order("expected_delivery").limit(10).execute()

            logger.info("Expected delivery check", extra={
                "yacht_id": str(yacht_id),
                "supplier": supplier,
                "matches_found": len(result.data) if result.data else 0
            })

            return result.data or []

        except Exception as e:
            logger.error("Expected delivery check failed", extra={
                "yacht_id": str(yacht_id),
                "error": str(e)
            })
            return []
