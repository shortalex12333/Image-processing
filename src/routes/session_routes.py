"""
Session routes for receiving session management.
Handles session viewing and draft line verification.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.middleware.auth import get_auth_context, AuthContext
from src.models.session import SessionResponse
from src.database import get_supabase_service
from src.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/receiving/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: UUID,
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Get receiving session with draft lines.

    Returns complete session details including:
    - Source images
    - Draft lines with suggestions
    - Verification status
    - User permissions

    **Permissions**: Any authenticated user can view sessions for their yacht.
    """
    supabase = get_supabase_service()

    try:
        # Get session
        session_result = supabase.table("pms_receiving_sessions") \
            .select("*") \
            .eq("session_id", str(session_id)) \
            .eq("yacht_id", str(auth.yacht_id)) \
            .single() \
            .execute()

        if not session_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )

        session = session_result.data

        # Get draft lines
        lines_result = supabase.table("pms_receiving_draft_lines") \
            .select("*") \
            .eq("session_id", str(session_id)) \
            .order("line_number") \
            .execute()

        draft_lines = lines_result.data or []

        # Get source images
        images_result = supabase.table("pms_image_uploads") \
            .select("image_id, file_name, uploaded_at, processing_status") \
            .eq("session_id", str(session_id)) \
            .execute()

        source_images = images_result.data or []

        # Calculate verification status
        total_lines = len(draft_lines)
        verified_lines = sum(1 for line in draft_lines if line["is_verified"])
        verification_percentage = (verified_lines / total_lines * 100) if total_lines > 0 else 0.0

        can_commit = (
            verification_percentage == 100.0 and
            session["status"] == "draft" and
            auth.is_hod()
        )

        # Build response
        response = {
            "session": {
                **session,
                "draft_lines": draft_lines,
                "source_images": source_images,
                "processing_summary": {
                    "total_lines_extracted": total_lines,
                    "lines_verified": verified_lines,
                    "lines_with_suggestions": sum(1 for l in draft_lines if l.get("suggested_part")),
                    "lines_requiring_manual_match": sum(1 for l in draft_lines if not l.get("suggested_part")),
                    "llm_invocations": 0,  # TODO: Track this
                    "total_cost_estimate": 0.0,
                    "ocr_method": "tesseract"
                },
                "verification_status": {
                    "can_commit": can_commit,
                    "verification_percentage": verification_percentage,
                    "blockers": [] if can_commit else [{
                        "code": "UNVERIFIED_LINES",
                        "message": f"{total_lines - verified_lines} lines not yet verified"
                    }]
                }
            },
            "permissions": {
                "can_verify": True,  # All users can verify
                "can_commit": auth.is_hod(),
                "can_edit": True,
                "can_cancel": auth.is_hod(),
                "can_override_verification": auth.is_hod()
            }
        }

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get session", extra={
            "session_id": str(session_id),
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session"
        )


@router.patch("/receiving/sessions/{session_id}/lines/{line_id}/verify")
async def verify_draft_line(
    session_id: UUID,
    line_id: UUID,
    auth: AuthContext = Depends(get_auth_context)
):
    """
    Mark a draft line as verified.

    Sets is_verified=true and records who verified and when.

    **Permissions**: Any authenticated user can verify lines.
    """
    supabase = get_supabase_service()

    try:
        # Verify line exists and belongs to this yacht
        result = supabase.table("pms_receiving_draft_lines") \
            .select("draft_line_id, session_id") \
            .eq("draft_line_id", str(line_id)) \
            .eq("session_id", str(session_id)) \
            .eq("yacht_id", str(auth.yacht_id)) \
            .single() \
            .execute()

        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Draft line not found"
            )

        # Update verification status
        from datetime import datetime
        supabase.table("pms_receiving_draft_lines") \
            .update({
                "is_verified": True,
                "verified_by": str(auth.user_id),
                "verified_at": datetime.utcnow().isoformat()
            }) \
            .eq("draft_line_id", str(line_id)) \
            .execute()

        logger.info("Draft line verified", extra={
            "line_id": str(line_id),
            "session_id": str(session_id),
            "verified_by": str(auth.user_id)
        })

        return {"status": "verified", "line_id": str(line_id)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to verify line", extra={
            "line_id": str(line_id),
            "error": str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify line"
        )
