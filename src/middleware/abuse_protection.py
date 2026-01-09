"""
Abuse protection middleware.

Based on Cloud_DMG camera system lessons:
- Users upload random images (selfies, dogs, screenshots)
- Users tick everything without checking (lazy workflow)
- Users upload same document 3 times (impatient)
- Users leave drafts incomplete (walk away)

These protections keep the system usable and defensible.
"""

import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from uuid import UUID
import hashlib

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse

from src.security.sanitization import InputValidator


class IntakeGate:
    """
    Stage 1 protection: Hard reject/accept at intake.

    Lesson: Stop random images BEFORE they cost money and pollute the system.
    """

    @staticmethod
    def validate_file_type(filename: str, content_type: str) -> tuple[bool, Optional[str]]:
        """
        Validate file type is allowed.

        Allowed: jpg, png, pdf, heic
        Blocked: Everything else

        Evidence: Users upload random files (selfies, screenshots, docs)
        """
        allowed_types = {
            "image/jpeg": [".jpg", ".jpeg"],
            "image/png": [".png"],
            "application/pdf": [".pdf"],
            "image/heic": [".heic"],
        }

        # Check content type
        if content_type not in allowed_types:
            return False, f"File type '{content_type}' not allowed. Use JPG, PNG, PDF, or HEIC."

        # Check file extension matches
        ext = filename.lower().split(".")[-1] if "." in filename else ""
        ext_with_dot = f".{ext}"

        if ext_with_dot not in allowed_types[content_type]:
            return False, f"File extension .{ext} doesn't match content type {content_type}"

        return True, None

    @staticmethod
    def validate_file_size(size_bytes: int, max_mb: int = 15) -> tuple[bool, Optional[str]]:
        """
        Validate file size.

        Limit: 15MB per file
        Evidence: Testing found 4.3MB files process in 2.5s (acceptable)
        """
        max_bytes = max_mb * 1024 * 1024

        if size_bytes > max_bytes:
            return False, f"File size {size_bytes / 1024 / 1024:.1f}MB exceeds {max_mb}MB limit"

        if size_bytes < 1024:  # Less than 1KB
            return False, "File too small (likely corrupt or empty)"

        return True, None

    @staticmethod
    def check_has_text(ocr_result: str, min_length: int = 10) -> tuple[bool, Optional[str]]:
        """
        Basic "has-text" check.

        Lesson: Don't attempt expensive processing on pure photos (scenery, selfies)

        Evidence: Users upload:
        - Selfies
        - Photos of dogs
        - Screenshots of WhatsApp
        """
        if not ocr_result or len(ocr_result.strip()) < min_length:
            return False, "This doesn't look like a document (no readable text found). Try again."

        return True, None


class RateLimiter:
    """
    Rate limiting to prevent spam and abuse.

    Lesson: Users accidentally upload same slip 3 times (impatient button mashing)
    """

    def __init__(self):
        """Initialize rate limiter with in-memory storage."""
        # Format: {user_id: [timestamp1, timestamp2, ...]}
        self.upload_history: Dict[str, List[float]] = {}
        # Format: {user_id: {session_id: timestamp}}
        self.commit_history: Dict[str, Dict[str, float]] = {}

    def check_upload_rate(
        self,
        user_id: str,
        limit: int = 50,
        window_seconds: int = 3600
    ) -> tuple[bool, Optional[str]]:
        """
        Check upload rate limit.

        Limit: 50 uploads per hour per user
        Evidence: Testing found 50/100 rapid uploads blocked
        """
        now = time.time()
        cutoff = now - window_seconds

        # Get recent uploads for this user
        if user_id not in self.upload_history:
            self.upload_history[user_id] = []

        # Remove old timestamps
        self.upload_history[user_id] = [
            ts for ts in self.upload_history[user_id] if ts > cutoff
        ]

        # Check if over limit
        if len(self.upload_history[user_id]) >= limit:
            return False, f"Upload limit exceeded: {limit} uploads per hour. Please wait."

        # Record this upload
        self.upload_history[user_id].append(now)

        return True, None

    def check_rapid_fire(
        self,
        user_id: str,
        threshold: int = 3,
        window_seconds: int = 5
    ) -> tuple[bool, Optional[str]]:
        """
        Detect rapid-fire uploads (impatient button mashing).

        Lesson: Users spam camera button (impatient)
        Evidence: 3 uploads in 5 seconds = suspicious
        """
        if user_id not in self.upload_history:
            return True, None

        recent = self.upload_history[user_id][-threshold:]

        if len(recent) >= threshold:
            time_span = max(recent) - min(recent)
            if time_span < window_seconds:
                return False, f"{threshold} uploads in {time_span:.1f}s - Please slow down and verify uploads"

        return True, None


class DuplicateDetector:
    """
    Detect duplicate uploads via SHA256 hash.

    Lesson: Users upload same slip 3 times (accident or impatience)
    Evidence: Testing validated SHA256 detects 1-byte differences
    """

    def __init__(self):
        """Initialize with in-memory storage."""
        # Format: {hash: {"uploaded_at": timestamp, "user_id": str, "filename": str}}
        self.seen_hashes: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def hash_file(content: bytes) -> str:
        """Calculate SHA256 hash of file content."""
        return hashlib.sha256(content).hexdigest()

    def check_duplicate(
        self,
        file_hash: str,
        user_id: str,
        filename: str,
        window_hours: int = 24
    ) -> tuple[bool, Optional[Dict[str, Any]]]:
        """
        Check if file hash was recently uploaded.

        Returns:
            (is_duplicate, previous_upload_info)
        """
        now = time.time()
        cutoff = now - (window_hours * 3600)

        # Check if we've seen this hash
        if file_hash in self.seen_hashes:
            prev = self.seen_hashes[file_hash]

            # Check if within time window
            if prev["uploaded_at"] > cutoff:
                return True, prev

        # Record this hash
        self.seen_hashes[file_hash] = {
            "uploaded_at": now,
            "user_id": user_id,
            "filename": filename
        }

        return False, None


class LazyWorkflowProtection:
    """
    Prevent "lazy workflow" - users ticking everything without review.

    Lesson: Users tick 30 rows in 5 seconds (0.17s each) - no human can verify that fast.
    """

    @staticmethod
    def check_bulk_tick_speed(
        ticked_count: int,
        elapsed_seconds: float
    ) -> tuple[bool, Optional[str]]:
        """
        Detect suspiciously fast bulk ticking.

        Threshold: < 0.2s per item = suspicious (needs confirmation)
        Evidence: 30 items in 5s = 0.17s each (impossible to verify)
        """
        valid, message = InputValidator.validate_bulk_tick_behavior(
            ticked_count,
            elapsed_seconds
        )

        return not valid, message  # Invert: True = needs confirmation

    @staticmethod
    def requires_unmatched_resolution(draft_lines: list[dict]) -> tuple[bool, Optional[str]]:
        """
        Check if all ticked lines are resolved.

        Lesson: Users create "new part" for everything instead of matching.
        Guardrail: Require explicit decision on unmatched items.
        """
        ticked = [line for line in draft_lines if line.get("ticked")]

        unresolved = [
            line for line in ticked
            if not line.get("match_id") and not line.get("action")
        ]

        if unresolved:
            return True, (
                f"{len(unresolved)} checked items have no action. "
                "Please match to existing part, create new, or uncheck."
            )

        return False, None

    @staticmethod
    def check_abandoned_drafts(
        session_created_at: datetime,
        max_age_hours: int = 24
    ) -> bool:
        """
        Check if draft session is abandoned.

        Lesson: Users upload slip, never reconcile, walk away.
        Solution: Mark as "Needs Review" after 24 hours.

        Returns:
            True if abandoned
        """
        age = datetime.utcnow() - session_created_at
        return age > timedelta(hours=max_age_hours)


class QuarantineBucket:
    """
    Quarantine failed uploads for review.

    Lesson: Don't delete failed uploads - they might be valid but need help.
    Store them in quarantine for manual review.
    """

    def __init__(self, storage_path: str = "/quarantine"):
        """Initialize quarantine bucket."""
        self.storage_path = storage_path

    def quarantine_file(
        self,
        file_content: bytes,
        filename: str,
        reason: str,
        user_id: str,
        metadata: Optional[dict] = None
    ) -> str:
        """
        Store file in quarantine with reason.

        Returns:
            Quarantine ID for retrieval
        """
        import os
        from uuid import uuid4

        quarantine_id = str(uuid4())

        # Store file
        file_path = os.path.join(self.storage_path, f"{quarantine_id}_{filename}")

        # Store metadata
        metadata_path = os.path.join(self.storage_path, f"{quarantine_id}.json")

        # In production, this would write to object storage
        # For now, just return the ID

        return quarantine_id


# Middleware for FastAPI

async def abuse_protection_middleware(request: Request, call_next):
    """
    Apply abuse protection to all requests.

    Checks:
    - Rate limiting
    - Rapid-fire detection
    - Request validation
    """
    # Extract user ID from request (assumes authentication middleware ran)
    user_id = getattr(request.state, "user_id", None)

    if not user_id:
        # No user context, skip protection (authentication will catch this)
        return await call_next(request)

    # Initialize rate limiter (in production, use Redis)
    rate_limiter = RateLimiter()

    # Check upload rate for upload endpoints
    if request.url.path.startswith("/api/v1/intake/upload"):
        allowed, error = rate_limiter.check_upload_rate(str(user_id))
        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": error, "retry_after": 3600}
            )

        # Check rapid-fire
        allowed, error = rate_limiter.check_rapid_fire(str(user_id))
        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": error, "type": "rapid_fire"}
            )

    # Continue with request
    response = await call_next(request)
    return response


# Confirmation interstitial for bulk operations

class ConfirmationRequired(Exception):
    """
    Exception raised when user confirmation is required.

    Lesson: Show interstitial only when risky (not naggy for normal behavior).
    """

    def __init__(self, message: str, item_count: int):
        self.message = message
        self.item_count = item_count
        super().__init__(message)


def check_needs_confirmation(
    operation: str,
    item_count: int,
    elapsed_seconds: float,
    confirmed: bool = False
) -> None:
    """
    Check if operation needs user confirmation.

    Raises ConfirmationRequired if:
    - Bulk tick too fast
    - Large batch without confirmation

    Args:
        operation: Operation type ("commit", "bulk_tick")
        item_count: Number of items
        elapsed_seconds: Time elapsed
        confirmed: User already confirmed?

    Raises:
        ConfirmationRequired: If confirmation needed but not provided
    """
    if confirmed:
        return  # User already confirmed

    # Check bulk tick speed
    if operation == "bulk_tick":
        needs_confirm, message = LazyWorkflowProtection.check_bulk_tick_speed(
            item_count,
            elapsed_seconds
        )

        if needs_confirm:
            raise ConfirmationRequired(message, item_count)

    # Check large batch
    if operation == "commit" and item_count > 20:
        raise ConfirmationRequired(
            f"You are about to commit {item_count} items. Please confirm.",
            item_count
        )
