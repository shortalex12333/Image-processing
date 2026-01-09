"""
File validation for image uploads.
Validates MIME type, file size, dimensions, and blur detection.
"""

import io
from typing import Literal

import cv2
import numpy as np
from PIL import Image
from fastapi import UploadFile

from src.config import settings
from src.logger import get_logger

logger = get_logger(__name__)


class ValidationError(Exception):
    """File validation failed."""

    def __init__(self, error_code: str, message: str, details: dict | None = None):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class FileValidator:
    """Validates uploaded files against requirements."""

    # Allowed MIME types by upload type
    ALLOWED_MIME_TYPES = {
        "receiving": ["image/jpeg", "image/png", "image/heic", "application/pdf"],
        "shipping_label": ["image/jpeg", "image/png", "image/heic", "application/pdf"],
        "discrepancy": ["image/jpeg", "image/png", "image/heic"],
        "part_photo": ["image/jpeg", "image/png"],
        "finance": ["application/pdf", "image/jpeg", "image/png"]
    }

    def __init__(self, upload_type: Literal["receiving", "shipping_label", "discrepancy", "part_photo", "finance"]):
        self.upload_type = upload_type
        self.allowed_types = self.ALLOWED_MIME_TYPES[upload_type]

    async def validate(self, file: UploadFile) -> dict:
        """
        Validate uploaded file.

        Args:
            file: FastAPI UploadFile object

        Returns:
            Validation result with metadata

        Raises:
            ValidationError: If validation fails
        """
        # Read file content
        content = await file.read()
        await file.seek(0)  # Reset for re-reading

        # Validate file size
        self._validate_size(len(content))

        # Validate MIME type
        mime_type = file.content_type or "application/octet-stream"
        self._validate_mime_type(mime_type)

        # For images, perform additional checks
        if mime_type.startswith("image/"):
            image_validation = await self._validate_image(content, mime_type)
            return {
                "mime_type": mime_type,
                "file_size_bytes": len(content),
                **image_validation
            }

        # For PDFs, basic validation only
        return {
            "mime_type": mime_type,
            "file_size_bytes": len(content),
            "is_image": False
        }

    def _validate_size(self, size_bytes: int) -> None:
        """Validate file size is within limits."""
        if size_bytes > settings.max_file_size_bytes:
            size_mb = size_bytes / (1024 * 1024)
            raise ValidationError(
                error_code="FILE_TOO_LARGE",
                message=f"File size {size_mb:.2f}MB exceeds maximum {settings.max_file_size_mb}MB",
                details={"size_bytes": size_bytes, "max_bytes": settings.max_file_size_bytes}
            )

    def _validate_mime_type(self, mime_type: str) -> None:
        """Validate MIME type is allowed for this upload type."""
        if mime_type not in self.allowed_types:
            raise ValidationError(
                error_code="INVALID_FILE_TYPE",
                message=f"File type {mime_type} not allowed for {self.upload_type}",
                details={"mime_type": mime_type, "allowed_types": self.allowed_types}
            )

    async def _validate_image(self, content: bytes, mime_type: str) -> dict:
        """
        Validate image dimensions and quality.

        Args:
            content: Image file bytes
            mime_type: Image MIME type

        Returns:
            Image metadata (width, height, blur_score)

        Raises:
            ValidationError: If image validation fails
        """
        try:
            # Load image with PIL
            image = Image.open(io.BytesIO(content))
            width, height = image.size

            # Validate dimensions
            if width < settings.min_image_width or height < settings.min_image_height:
                raise ValidationError(
                    error_code="IMAGE_TOO_SMALL",
                    message=f"Image {width}x{height} below minimum {settings.min_image_width}x{settings.min_image_height}",
                    details={"width": width, "height": height}
                )

            # Blur detection
            blur_score = self._detect_blur(content)
            is_blurry = blur_score < settings.blur_threshold

            if is_blurry:
                logger.warning("Blurry image detected", extra={
                    "blur_score": blur_score,
                    "threshold": settings.blur_threshold,
                    "width": width,
                    "height": height
                })
                raise ValidationError(
                    error_code="IMAGE_BLURRY",
                    message=f"Image appears blurry (score: {blur_score:.2f}, threshold: {settings.blur_threshold})",
                    details={"blur_score": blur_score, "threshold": settings.blur_threshold}
                )

            return {
                "is_image": True,
                "width": width,
                "height": height,
                "blur_score": blur_score,
                "is_blurry": False
            }

        except ValidationError:
            raise
        except Exception as e:
            logger.error("Image validation failed", extra={"error": str(e)}, exc_info=True)
            raise ValidationError(
                error_code="INVALID_IMAGE",
                message=f"Failed to validate image: {str(e)}",
                details={"error": str(e)}
            )

    def _detect_blur(self, image_bytes: bytes) -> float:
        """
        Detect image blur using Laplacian variance.

        Args:
            image_bytes: Image file bytes

        Returns:
            Blur score (higher = sharper, lower = blurrier)
            Typical values: > 100 = sharp, 50-100 = ok, < 50 = blurry
        """
        try:
            # Convert bytes to numpy array
            nparr = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)

            if image is None:
                logger.warning("Failed to decode image for blur detection")
                return 100.0  # Assume not blurry if we can't check

            # Calculate Laplacian variance
            laplacian = cv2.Laplacian(image, cv2.CV_64F)
            variance = laplacian.var()

            return float(variance)

        except Exception as e:
            logger.warning("Blur detection failed, assuming sharp", extra={"error": str(e)})
            return 100.0  # Assume not blurry if detection fails


async def validate_file(
    file: UploadFile,
    upload_type: Literal["receiving", "shipping_label", "discrepancy", "part_photo", "finance"]
) -> dict:
    """
    Validate uploaded file (convenience function).

    Args:
        file: FastAPI UploadFile
        upload_type: Type of upload

    Returns:
        Validation metadata

    Raises:
        ValidationError: If validation fails
    """
    validator = FileValidator(upload_type)
    return await validator.validate(file)
