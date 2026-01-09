"""
Finance recorder for cost tracking.
Creates pms_finance_transactions when unit prices are available.
"""

from uuid import UUID
from datetime import datetime

from src.database import get_supabase_service
from src.logger import get_logger

logger = get_logger(__name__)


class FinanceRecorder:
    """Records financial transactions for received items."""

    def __init__(self):
        self.supabase = get_supabase_service()

    async def record_finance_transactions(
        self,
        yacht_id: UUID,
        event_id: UUID,
        committed_by: UUID,
        draft_lines: list[dict]
    ) -> dict | None:
        """
        Record finance transactions for lines with unit prices.

        Args:
            yacht_id: Yacht UUID
            event_id: Receiving event UUID
            committed_by: User who committed
            draft_lines: Draft lines (may include unit_price)

        Returns:
            Finance summary or None if no prices available

        Example:
            >>> recorder = FinanceRecorder()
            >>> summary = await recorder.record_finance_transactions(
            ...     yacht_id=yacht_id,
            ...     event_id=event_id,
            ...     committed_by=user_id,
            ...     draft_lines=[{...}]
            ... )
            >>> summary
            {
                "transactions_created": 8,
                "total_cost": 1234.56,
                "currency": "USD"
            }
        """
        transactions_created = 0
        total_cost = 0.0

        for line in draft_lines:
            # Check if line has unit price
            unit_price = line.get("unit_price")
            if not unit_price or unit_price <= 0:
                continue

            # Calculate line cost
            quantity = line["quantity"]
            line_cost = quantity * unit_price

            try:
                # Create finance transaction
                await self._create_finance_transaction(
                    yacht_id=yacht_id,
                    part_id=UUID(line["suggested_part"]["part_id"]) if line.get("suggested_part") else None,
                    event_id=event_id,
                    quantity=quantity,
                    unit_price=unit_price,
                    total_price=line_cost,
                    created_by=committed_by,
                    description=line["description"]
                )

                transactions_created += 1
                total_cost += line_cost

            except Exception as e:
                logger.error("Failed to record finance transaction", extra={
                    "draft_line_id": line.get("draft_line_id"),
                    "error": str(e)
                })
                # Continue with other lines

        if transactions_created == 0:
            logger.info("No finance transactions recorded (no unit prices)", extra={
                "event_id": str(event_id)
            })
            return None

        logger.info("Finance transactions recorded", extra={
            "yacht_id": str(yacht_id),
            "event_id": str(event_id),
            "transactions": transactions_created,
            "total_cost": total_cost
        })

        return {
            "transactions_created": transactions_created,
            "total_cost": total_cost,
            "currency": "USD"  # TODO: Make configurable
        }

    async def _create_finance_transaction(
        self,
        yacht_id: UUID,
        part_id: UUID | None,
        event_id: UUID,
        quantity: float,
        unit_price: float,
        total_price: float,
        created_by: UUID,
        description: str
    ) -> None:
        """
        Create finance transaction record.

        Args:
            yacht_id: Yacht UUID
            part_id: Part UUID (if matched)
            event_id: Receiving event UUID
            quantity: Quantity received
            unit_price: Unit price
            total_price: Total cost (quantity * unit_price)
            created_by: User UUID
            description: Item description
        """
        try:
            transaction_data = {
                "yacht_id": str(yacht_id),
                "reference_id": str(event_id),
                "reference_type": "receiving_event",
                "transaction_type": "expense",
                "category": "parts_inventory",
                "amount": total_price,
                "currency": "USD",
                "description": f"Receiving: {description} (qty: {quantity} @ ${unit_price:.2f})",
                "metadata": {
                    "part_id": str(part_id) if part_id else None,
                    "quantity": quantity,
                    "unit_price": unit_price
                },
                "created_by": str(created_by)
            }

            self.supabase.table("pms_finance_transactions").insert(transaction_data).execute()

        except Exception as e:
            logger.error("Failed to create finance transaction", extra={
                "event_id": str(event_id),
                "error": str(e)
            })
            raise
