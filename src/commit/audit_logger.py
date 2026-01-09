"""
Audit logger for compliance and accountability.
Creates immutable audit trail entries for all commit operations.
"""

import hashlib
import json
from uuid import UUID
from datetime import datetime

from src.database import get_supabase_service
from src.logger import get_logger

logger = get_logger(__name__)


class AuditLogger:
    """Creates audit log entries for receiving operations."""

    def __init__(self):
        self.supabase = get_supabase_service()

    async def log_commit(
        self,
        yacht_id: UUID,
        user_id: UUID,
        action: str,
        entity_type: str,
        entity_id: UUID,
        old_values: dict | None = None,
        new_values: dict | None = None
    ) -> UUID:
        """
        Create audit log entry.

        Args:
            yacht_id: Yacht UUID
            user_id: User who performed action
            action: Action performed (e.g., "commit_session")
            entity_type: Type of entity (e.g., "receiving_session")
            entity_id: Entity UUID
            old_values: State before action (if applicable)
            new_values: State after action

        Returns:
            Audit log entry UUID

        Example:
            >>> audit = AuditLogger()
            >>> log_id = await audit.log_commit(
            ...     yacht_id=yacht_id,
            ...     user_id=user_id,
            ...     action="commit_session",
            ...     entity_type="receiving_session",
            ...     entity_id=session_id,
            ...     old_values={"status": "draft"},
            ...     new_values={"status": "committed", "event_id": "..."}
            ... )
        """
        try:
            # Generate signature (SHA256 of audit data)
            signature = self._generate_signature({
                "yacht_id": str(yacht_id),
                "user_id": str(user_id),
                "action": action,
                "entity_type": entity_type,
                "entity_id": str(entity_id),
                "old_values": old_values,
                "new_values": new_values,
                "timestamp": datetime.utcnow().isoformat()
            })

            # Create audit log entry
            audit_data = {
                "yacht_id": str(yacht_id),
                "user_id": str(user_id),
                "action": action,
                "entity_type": entity_type,
                "entity_id": str(entity_id),
                "old_values": old_values or {},
                "new_values": new_values or {},
                "signature": signature
            }

            result = self.supabase.table("pms_audit_log").insert(audit_data).execute()

            if not result.data:
                raise Exception("Failed to create audit log entry")

            audit_id = UUID(result.data[0]["audit_log_id"])

            logger.info("Audit log entry created", extra={
                "audit_log_id": str(audit_id),
                "action": action,
                "entity_type": entity_type,
                "user_id": str(user_id)
            })

            return audit_id

        except Exception as e:
            logger.error("Failed to create audit log entry", extra={
                "action": action,
                "entity_id": str(entity_id),
                "error": str(e)
            }, exc_info=True)
            raise

    async def log_session_commit(
        self,
        yacht_id: UUID,
        user_id: UUID,
        session_id: UUID,
        event_id: UUID,
        lines_committed: int
    ) -> UUID:
        """
        Log session commit (convenience method).

        Args:
            yacht_id: Yacht UUID
            user_id: User who committed
            session_id: Session UUID
            event_id: Created event UUID
            lines_committed: Number of lines committed

        Returns:
            Audit log entry UUID
        """
        return await self.log_commit(
            yacht_id=yacht_id,
            user_id=user_id,
            action="commit_receiving_session",
            entity_type="receiving_session",
            entity_id=session_id,
            old_values={"status": "draft"},
            new_values={
                "status": "committed",
                "event_id": str(event_id),
                "lines_committed": lines_committed
            }
        )

    @staticmethod
    def _generate_signature(data: dict) -> str:
        """
        Generate SHA256 signature for audit data.

        Args:
            data: Audit data to sign

        Returns:
            SHA256 hex digest
        """
        # Convert to JSON string (sorted keys for consistency)
        json_str = json.dumps(data, sort_keys=True)
        # Calculate SHA256
        sha256_hash = hashlib.sha256(json_str.encode()).hexdigest()
        return sha256_hash
