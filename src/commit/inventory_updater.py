"""
Inventory updater for stock level management.
Updates pms_inventory_stock and creates pms_inventory_transactions.
"""

from uuid import UUID
from datetime import datetime

from src.database import get_supabase_service
from src.logger import get_logger

logger = get_logger(__name__)


class InventoryUpdater:
    """Updates inventory stock levels."""

    def __init__(self):
        self.supabase = get_supabase_service()

    async def update_inventory(
        self,
        yacht_id: UUID,
        event_id: UUID,
        committed_by: UUID,
        draft_lines: list[dict]
    ) -> dict:
        """
        Update inventory for all committed lines.

        Args:
            yacht_id: Yacht UUID
            event_id: Receiving event UUID
            committed_by: User who committed
            draft_lines: Verified draft lines with part matches

        Returns:
            Inventory update summary

        Example:
            >>> updater = InventoryUpdater()
            >>> summary = await updater.update_inventory(
            ...     yacht_id=yacht_id,
            ...     event_id=event_id,
            ...     committed_by=user_id,
            ...     draft_lines=[{...}]
            ... )
            >>> summary
            {
                "parts_updated": 8,
                "new_parts_created": 2,
                "total_quantity_added": 87.0,
                "transactions_created": 10,
                "low_stock_alerts": [...]
            }
        """
        parts_updated = 0
        new_parts_created = 0
        total_quantity = 0.0
        transactions_created = 0
        low_stock_alerts = []

        for line in draft_lines:
            # Skip lines without part matches
            if not line.get("suggested_part"):
                logger.warning("Draft line has no part match - skipping inventory update", extra={
                    "draft_line_id": line.get("draft_line_id")
                })
                continue

            part_id = UUID(line["suggested_part"]["part_id"])
            quantity = line["quantity"]

            try:
                # Update stock level
                await self._update_stock_level(yacht_id, part_id, quantity)
                parts_updated += 1
                total_quantity += quantity

                # Create transaction record
                await self._create_transaction(
                    yacht_id=yacht_id,
                    part_id=part_id,
                    event_id=event_id,
                    quantity=quantity,
                    transaction_type="receiving",
                    created_by=committed_by,
                    notes=f"Received via {event_id}"
                )
                transactions_created += 1

                # Check for low stock alerts
                alert = await self._check_low_stock(yacht_id, part_id)
                if alert:
                    low_stock_alerts.append(alert)

            except Exception as e:
                logger.error("Failed to update inventory for line", extra={
                    "draft_line_id": line.get("draft_line_id"),
                    "part_id": str(part_id),
                    "error": str(e)
                })
                # Continue with other lines

        logger.info("Inventory update complete", extra={
            "yacht_id": str(yacht_id),
            "event_id": str(event_id),
            "parts_updated": parts_updated,
            "total_quantity": total_quantity
        })

        return {
            "parts_updated": parts_updated,
            "new_parts_created": new_parts_created,
            "total_quantity_added": total_quantity,
            "transactions_created": transactions_created,
            "low_stock_alerts": low_stock_alerts
        }

    async def _update_stock_level(
        self,
        yacht_id: UUID,
        part_id: UUID,
        quantity: float
    ) -> None:
        """
        Update stock level for a part (increment quantity).

        Args:
            yacht_id: Yacht UUID
            part_id: Part UUID
            quantity: Quantity to add
        """
        try:
            # Get current stock level
            result = self.supabase.table("pms_parts") \
                .select("quantity_on_hand") \
                .eq("part_id", str(part_id)) \
                .eq("yacht_id", str(yacht_id)) \
                .single() \
                .execute()

            if not result.data:
                logger.warning("Part not found - cannot update stock", extra={
                    "part_id": str(part_id)
                })
                return

            current_quantity = result.data.get("quantity_on_hand", 0.0) or 0.0
            new_quantity = current_quantity + quantity

            # Update stock level
            self.supabase.table("pms_parts") \
                .update({"quantity_on_hand": new_quantity}) \
                .eq("part_id", str(part_id)) \
                .execute()

            logger.debug("Stock level updated", extra={
                "part_id": str(part_id),
                "old_quantity": current_quantity,
                "new_quantity": new_quantity,
                "added": quantity
            })

        except Exception as e:
            logger.error("Failed to update stock level", extra={
                "part_id": str(part_id),
                "error": str(e)
            })
            raise

    async def _create_transaction(
        self,
        yacht_id: UUID,
        part_id: UUID,
        event_id: UUID,
        quantity: float,
        transaction_type: str,
        created_by: UUID,
        notes: str
    ) -> None:
        """
        Create inventory transaction record.

        Args:
            yacht_id: Yacht UUID
            part_id: Part UUID
            event_id: Related event UUID
            quantity: Quantity (positive for receiving)
            transaction_type: Type of transaction
            created_by: User UUID
            notes: Transaction notes
        """
        try:
            transaction_data = {
                "yacht_id": str(yacht_id),
                "part_id": str(part_id),
                "reference_id": str(event_id),
                "reference_type": "receiving_event",
                "transaction_type": transaction_type,
                "quantity": quantity,
                "notes": notes,
                "created_by": str(created_by)
            }

            self.supabase.table("pms_inventory_transactions").insert(transaction_data).execute()

        except Exception as e:
            logger.error("Failed to create transaction record", extra={
                "part_id": str(part_id),
                "error": str(e)
            })
            # Don't raise - transaction record is audit trail, not critical

    async def _check_low_stock(self, yacht_id: UUID, part_id: UUID) -> dict | None:
        """
        Check if part is below minimum stock level.

        Args:
            yacht_id: Yacht UUID
            part_id: Part UUID

        Returns:
            Alert dict if low stock, None otherwise
        """
        try:
            result = self.supabase.table("pms_parts") \
                .select("part_id, part_number, quantity_on_hand, minimum_quantity") \
                .eq("part_id", str(part_id)) \
                .eq("yacht_id", str(yacht_id)) \
                .single() \
                .execute()

            if not result.data:
                return None

            part = result.data
            current = part.get("quantity_on_hand", 0.0) or 0.0
            minimum = part.get("minimum_quantity", 0.0) or 0.0

            if current < minimum:
                shortage = minimum - current
                return {
                    "part_id": part["part_id"],
                    "part_number": part["part_number"],
                    "current_quantity": current,
                    "minimum_quantity": minimum,
                    "shortage": shortage
                }

            return None

        except Exception as e:
            logger.error("Failed to check low stock", extra={
                "part_id": str(part_id),
                "error": str(e)
            })
            return None
