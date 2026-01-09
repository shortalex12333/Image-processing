"""
Commit routes for finalizing receiving sessions.
Handles POST /api/v1/receiving/sessions/{id}/commit (HOD only)
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.handlers.receiving_handler import ReceivingHandler
from src.middleware.auth import get_auth_context, require_hod, AuthContext
from src.models.commit import CommitRequest, CommitResponse
from src.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("/receiving/sessions/{session_id}/commit", response_model=CommitResponse)
async def commit_session(
    session_id: UUID,
    request: CommitRequest,
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Commit receiving session (create immutable records).

    **Permissions**: HOD only (chief_engineer, captain, manager).

    Workflow:
    1. Validate all lines are verified (or override flag set)
    2. Create immutable receiving_event
    3. Update inventory stock levels
    4. Record financial transactions (if unit prices available)
    5. Create audit log entry
    6. Update session status to "committed"

    **CRITICAL**: This operation cannot be undone. Once committed, the
    receiving event becomes part of the immutable audit trail.

    Args:
        commitment_notes: Notes explaining the commitment (required)
        override_unverified: Allow committing unverified lines (HOD only)
        force_commit: Force commit despite warnings (HOD emergency override)
        financial_approval: Financial approval details (if required)
        delivery_metadata: Additional delivery information
    """
    # Check HOD permissions
    require_hod(auth)

    handler = ReceivingHandler()

    try:
        result = await handler.commit_session(
            session_id=session_id,
            yacht_id=auth.yacht_id,
            committed_by=auth.user_id,
            commitment_notes=request.commitment_notes,
            override_unverified=request.override_unverified
        )

        logger.info("Session committed", extra={
            "session_id": str(session_id),
            "committed_by": str(auth.user_id),
            "event_id": result["receiving_event"]["event_id"]
        })

        return CommitResponse(**result)

    except Exception as e:
        error_msg = str(e)

        # Handle specific error cases
        if "not verified" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "UNVERIFIED_LINES",
                    "message": error_msg,
                    "hint": "Set override_unverified=true to commit anyway (HOD only)"
                }
            )
        elif "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error_code": "SESSION_NOT_FOUND",
                    "message": error_msg
                }
            )
        else:
            logger.error("Commit failed", extra={
                "session_id": str(session_id),
                "committed_by": str(auth.user_id),
                "error": error_msg
            }, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error_code": "COMMIT_FAILED",
                    "message": "Failed to commit session",
                    "details": {"error": error_msg}
                }
            )
