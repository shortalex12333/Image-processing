"""
Receiving event creator for immutable record generation.
Creates pms_receiving_events with auto-numbering.
"""

import hashlib
import json
from uuid import UUID
from datetime import datetime

from src.database import get_supabase_service
from src.logger import get_logger

logger = get_logger(__name__)


class EventCreator:
    """Creates immutable receiving event records."""

    def __init__(self):
        self.supabase = get_supabase_service()

    async def create_receiving_event(
        self,
        session_id: UUID,
        yacht_id: UUID,
        committed_by: UUID,
        commitment_notes: str,
        draft_lines: list[dict],
        total_cost: float | None = None
    ) -> dict:
        """
        Create immutable receiving event.

        Args:
            session_id: Source session UUID
            yacht_id: Yacht UUID
            committed_by: User who committed
            commitment_notes: Commit notes
            draft_lines: Verified draft lines
            total_cost: Total cost of items (if available)

        Returns:
            Created event with event_id and event_number

        Example:
            >>> creator = EventCreator()
            >>> event = await creator.create_receiving_event(
            ...     session_id=session_id,
            ...     yacht_id=yacht_id,
            ...     committed_by=user_id,
            ...     commitment_notes="All items verified",
            ...     draft_lines=[{...}],
            ...     total_cost=1234.56
            ... )
            >>> event
            {
                "event_id": "uuid",
                "event_number": "RCV-EVT-2026-001",
                "session_id": "uuid",
                "lines_committed": 10,
                "total_cost": 1234.56,
                "committed_by": "uuid",
                "committed_at": "2026-01-09T15:30:00Z"
            }
        """
        try:
            # Generate event number
            event_number = await self._generate_event_number(yacht_id)

            # Create signature (SHA256 hash of event data)
            signature = self._generate_signature({
                "session_id": str(session_id),
                "yacht_id": str(yacht_id),
                "committed_by": str(committed_by),
                "lines": [line["draft_line_id"] for line in draft_lines],
                "timestamp": datetime.utcnow().isoformat()
            })

            # Insert event record
            event_data = {
                "yacht_id": str(yacht_id),
                "session_id": str(session_id),
                "event_number": event_number,
                "committed_by": str(committed_by),
                "commitment_notes": commitment_notes,
                "lines_committed": len(draft_lines),
                "total_cost": total_cost,
                "signature": signature,
                "metadata": {
                    "draft_line_ids": [line["draft_line_id"] for line in draft_lines]
                }
            }

            result = self.supabase.table("pms_receiving_events").insert(event_data).execute()

            if not result.data:
                raise Exception("Failed to create receiving event - no data returned")

            event = result.data[0]

            logger.info("Receiving event created", extra={
                "event_id": event["event_id"],
                "event_number": event_number,
                "yacht_id": str(yacht_id),
                "lines_committed": len(draft_lines)
            })

            return {
                "event_id": event["event_id"],
                "event_number": event_number,
                "session_id": str(session_id),
                "lines_committed": len(draft_lines),
                "total_cost": total_cost,
                "committed_by": str(committed_by),
                "committed_at": event["created_at"],
                "signature": signature
            }

        except Exception as e:
            logger.error("Failed to create receiving event", extra={
                "session_id": str(session_id),
                "yacht_id": str(yacht_id),
                "error": str(e)
            }, exc_info=True)
            raise

    async def _generate_event_number(self, yacht_id: UUID) -> str:
        """
        Generate auto-incrementing event number.

        Format: RCV-EVT-{YEAR}-{SEQUENCE}
        Example: RCV-EVT-2026-001

        Args:
            yacht_id: Yacht UUID

        Returns:
            Event number string
        """
        try:
            current_year = datetime.utcnow().year

            # Get count of events for this yacht in current year
            result = self.supabase.table("pms_receiving_events") \
                .select("event_id", count="exact") \
                .eq("yacht_id", str(yacht_id)) \
                .gte("created_at", f"{current_year}-01-01") \
                .execute()

            count = (result.count or 0) + 1
            event_number = f"RCV-EVT-{current_year}-{count:03d}"

            return event_number

        except Exception as e:
            logger.error("Failed to generate event number", extra={
                "yacht_id": str(yacht_id),
                "error": str(e)
            })
            # Fallback to timestamp-based
            timestamp = int(datetime.utcnow().timestamp())
            return f"RCV-EVT-{current_year}-{timestamp}"

    @staticmethod
    def _generate_signature(data: dict) -> str:
        """
        Generate SHA256 signature for event data.

        Args:
            data: Event data to sign

        Returns:
            SHA256 hex digest
        """
        # Convert to JSON string (sorted keys for consistency)
        json_str = json.dumps(data, sort_keys=True)
        # Calculate SHA256
        sha256_hash = hashlib.sha256(json_str.encode()).hexdigest()
        return sha256_hash
