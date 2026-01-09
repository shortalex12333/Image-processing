"""
SHA256-based file deduplication to avoid storing duplicate images.
"""

import hashlib
from uuid import UUID

from src.database import get_supabase_service
from src.logger import get_logger

logger = get_logger(__name__)


class Deduplicator:
    """Handles SHA256 hashing and duplicate detection."""

    def __init__(self):
        self.supabase = get_supabase_service()

    @staticmethod
    def calculate_sha256(content: bytes) -> str:
        """
        Calculate SHA256 hash of file content.

        Args:
            content: File bytes

        Returns:
            SHA256 hash as hexadecimal string
        """
        sha256_hash = hashlib.sha256()
        sha256_hash.update(content)
        return sha256_hash.hexdigest()

    async def check_duplicate(self, sha256: str, yacht_id: UUID) -> dict | None:
        """
        Check if file with this SHA256 already exists for this yacht.

        Args:
            sha256: SHA256 hash of file
            yacht_id: Yacht UUID (for multi-tenant isolation)

        Returns:
            Existing image metadata if duplicate found, None otherwise

        Example:
            >>> dedup = Deduplicator()
            >>> existing = await dedup.check_duplicate(sha256_hash, yacht_id)
            >>> if existing:
            ...     print(f"Duplicate of {existing['image_id']}")
        """
        try:
            result = self.supabase.table("pms_image_uploads") \
                .select("image_id, file_name, storage_path, uploaded_at, processing_status") \
                .eq("yacht_id", str(yacht_id)) \
                .eq("sha256", sha256) \
                .limit(1) \
                .execute()

            if result.data:
                existing = result.data[0]
                logger.info("Duplicate image found", extra={
                    "sha256": sha256,
                    "existing_image_id": existing["image_id"],
                    "yacht_id": str(yacht_id)
                })
                return existing

            return None

        except Exception as e:
            logger.error("Duplicate check failed", extra={
                "sha256": sha256,
                "yacht_id": str(yacht_id),
                "error": str(e)
            }, exc_info=True)
            # Don't block upload on dedup failure - return None
            return None

    async def record_upload(
        self,
        yacht_id: UUID,
        user_id: UUID,
        file_name: str,
        mime_type: str,
        file_size_bytes: int,
        sha256: str,
        storage_path: str,
        upload_type: str,
        width: int | None = None,
        height: int | None = None,
        blur_score: float | None = None
    ) -> UUID:
        """
        Record image upload in database.

        Args:
            yacht_id: Yacht UUID
            user_id: Uploader user UUID
            file_name: Original filename
            mime_type: File MIME type
            file_size_bytes: File size
            sha256: SHA256 hash
            storage_path: Path in storage bucket
            upload_type: Type of upload
            width: Image width (if image)
            height: Image height (if image)
            blur_score: Blur detection score (if image)

        Returns:
            UUID of created image record

        Raises:
            Exception: If database insert fails
        """
        try:
            metadata = {
                "upload_type": upload_type,
                "blur_score": blur_score
            }

            if width and height:
                metadata["dimensions"] = {"width": width, "height": height}

            result = self.supabase.table("pms_image_uploads").insert({
                "yacht_id": str(yacht_id),
                "uploaded_by": str(user_id),
                "file_name": file_name,
                "mime_type": mime_type,
                "file_size_bytes": file_size_bytes,
                "sha256": sha256,
                "storage_path": storage_path,
                "processing_status": "queued",
                "metadata": metadata
            }).execute()

            if not result.data:
                raise Exception("Failed to insert image record - no data returned")

            image_id = UUID(result.data[0]["image_id"])

            logger.info("Image upload recorded", extra={
                "image_id": str(image_id),
                "yacht_id": str(yacht_id),
                "file_name": file_name,
                "sha256": sha256[:16]  # Log partial hash
            })

            return image_id

        except Exception as e:
            logger.error("Failed to record upload", extra={
                "yacht_id": str(yacht_id),
                "file_name": file_name,
                "error": str(e)
            }, exc_info=True)
            raise
