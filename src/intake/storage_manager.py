"""
Supabase Storage management for file uploads.
"""

import mimetypes
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from src.config import settings
from src.database import get_supabase_service, get_bucket_name
from src.logger import get_logger

logger = get_logger(__name__)


class StorageUploadError(Exception):
    """Failed to upload file to storage."""
    pass


class StorageManager:
    """Manages file uploads to Supabase Storage."""

    def __init__(self):
        self.supabase = get_supabase_service()

    def generate_storage_path(
        self,
        yacht_id: UUID,
        upload_type: str,
        file_name: str,
        image_id: UUID | None = None
    ) -> str:
        """
        Generate storage path for file.

        Path structure: {yacht_id}/{upload_type}/{year}/{month}/{uuid}_{filename}

        Args:
            yacht_id: Yacht UUID
            upload_type: Type of upload
            file_name: Original filename
            image_id: Image UUID (optional, generates new if not provided)

        Returns:
            Storage path

        Example:
            >>> path = manager.generate_storage_path(yacht_id, "receiving", "packing_slip.pdf")
            >>> path
            '85fe1119-b04c-41ac-80f1-829d23322598/receiving/2026/01/550e8400-e29b-41d4-a716-446655440000_packing_slip.pdf'
        """
        now = datetime.utcnow()
        year = now.strftime("%Y")
        month = now.strftime("%m")

        # Sanitize filename
        safe_filename = self._sanitize_filename(file_name)

        # Generate unique ID for file
        unique_id = image_id or uuid4()

        path = f"{yacht_id}/{upload_type}/{year}/{month}/{unique_id}_{safe_filename}"
        return path

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """
        Sanitize filename for storage.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename (safe for URLs)
        """
        # Keep only alphanumeric, hyphens, underscores, and extension
        safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
        return safe_name[:200]  # Limit length

    async def upload_file(
        self,
        content: bytes,
        storage_path: str,
        upload_type: str,
        mime_type: str
    ) -> dict:
        """
        Upload file to Supabase Storage.

        Args:
            content: File bytes
            storage_path: Path within bucket
            upload_type: Type of upload (determines bucket)
            mime_type: File MIME type

        Returns:
            Upload metadata (path, url)

        Raises:
            StorageUploadError: If upload fails
        """
        try:
            bucket_name = get_bucket_name(upload_type)

            # Upload to storage
            result = self.supabase.storage.from_(bucket_name).upload(
                path=storage_path,
                file=content,
                file_options={"content-type": mime_type}
            )

            # Get public URL (with expiry)
            public_url = self.get_signed_url(bucket_name, storage_path, expiry_seconds=3600)

            logger.info("File uploaded to storage", extra={
                "bucket": bucket_name,
                "path": storage_path,
                "size_bytes": len(content)
            })

            return {
                "storage_path": storage_path,
                "bucket": bucket_name,
                "public_url": public_url
            }

        except Exception as e:
            logger.error("Storage upload failed", extra={
                "path": storage_path,
                "upload_type": upload_type,
                "error": str(e)
            }, exc_info=True)
            raise StorageUploadError(f"Failed to upload file: {str(e)}")

    def get_signed_url(self, bucket_name: str, storage_path: str, expiry_seconds: int = 3600) -> str:
        """
        Get signed URL for file access.

        Args:
            bucket_name: Storage bucket name
            storage_path: Path within bucket
            expiry_seconds: URL expiry time (default 1 hour)

        Returns:
            Signed URL
        """
        try:
            result = self.supabase.storage.from_(bucket_name).create_signed_url(
                path=storage_path,
                expires_in=expiry_seconds
            )
            return result.get("signedURL", "")
        except Exception as e:
            logger.warning("Failed to generate signed URL", extra={
                "bucket": bucket_name,
                "path": storage_path,
                "error": str(e)
            })
            return ""

    async def download_file(self, bucket_name: str, storage_path: str) -> bytes:
        """
        Download file from storage.

        Args:
            bucket_name: Storage bucket name
            storage_path: Path within bucket

        Returns:
            File bytes

        Raises:
            StorageUploadError: If download fails
        """
        try:
            result = self.supabase.storage.from_(bucket_name).download(storage_path)
            return result

        except Exception as e:
            logger.error("Storage download failed", extra={
                "bucket": bucket_name,
                "path": storage_path,
                "error": str(e)
            }, exc_info=True)
            raise StorageUploadError(f"Failed to download file: {str(e)}")

    async def delete_file(self, bucket_name: str, storage_path: str) -> None:
        """
        Delete file from storage.

        Args:
            bucket_name: Storage bucket name
            storage_path: Path within bucket
        """
        try:
            self.supabase.storage.from_(bucket_name).remove([storage_path])
            logger.info("File deleted from storage", extra={
                "bucket": bucket_name,
                "path": storage_path
            })
        except Exception as e:
            logger.warning("Storage delete failed", extra={
                "bucket": bucket_name,
                "path": storage_path,
                "error": str(e)
            })
