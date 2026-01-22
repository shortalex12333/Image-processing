"""
Rate limiting for upload endpoints.
Prevents abuse by limiting uploads per hour per yacht.
"""

from datetime import datetime, timedelta
from uuid import UUID

from src.config import settings
from src.database import get_supabase_service
from src.logger import get_logger

logger = get_logger(__name__)


class RateLimitExceeded(Exception):
    """Rate limit exceeded for this yacht."""

    def __init__(self, current_count: int, limit: int, retry_after_seconds: int):
        self.current_count = current_count
        self.limit = limit
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Rate limit exceeded: {current_count}/{limit} uploads in last hour")


class RateLimiter:
    """Enforces upload rate limits per yacht."""

    def __init__(self):
        self.supabase = get_supabase_service()

    async def check_rate_limit(self, yacht_id: UUID) -> None:
        """
        Check if yacht has exceeded upload rate limit.

        Args:
            yacht_id: Yacht UUID

        Raises:
            RateLimitExceeded: If rate limit exceeded
        """
        window_start = datetime.utcnow() - timedelta(seconds=settings.upload_rate_limit_window_seconds)

        try:
            # Count uploads in the time window
            result = self.supabase.table("pms_image_uploads") \
                .select("id", count="exact") \
                .eq("yacht_id", str(yacht_id)) \
                .gte("uploaded_at", window_start.isoformat()) \
                .execute()

            upload_count = result.count or 0

            if upload_count >= settings.max_uploads_per_hour:
                retry_after = settings.upload_rate_limit_window_seconds
                logger.warning("Rate limit exceeded", extra={
                    "yacht_id": str(yacht_id),
                    "upload_count": upload_count,
                    "limit": settings.max_uploads_per_hour
                })
                raise RateLimitExceeded(
                    current_count=upload_count,
                    limit=settings.max_uploads_per_hour,
                    retry_after_seconds=retry_after
                )

            logger.debug("Rate limit check passed", extra={
                "yacht_id": str(yacht_id),
                "upload_count": upload_count,
                "limit": settings.max_uploads_per_hour
            })

        except RateLimitExceeded:
            raise
        except Exception as e:
            logger.error("Rate limit check failed", extra={
                "yacht_id": str(yacht_id),
                "error": str(e)
            }, exc_info=True)
            # Don't block on rate limit check failure - allow upload
            pass

    async def record_upload_attempt(self, yacht_id: UUID, success: bool) -> None:
        """
        Record upload attempt for monitoring (optional).

        Args:
            yacht_id: Yacht UUID
            success: Whether upload succeeded
        """
        # Future: Store in separate rate_limit_log table for analytics
        pass
