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

            # Document Quality Score (DQS) - replaces blur-only detection
            dqs_result = self._calculate_dqs(content)

            if not dqs_result["is_acceptable"]:
                logger.warning("Poor image quality detected", extra={
                    "dqs_score": dqs_result["total_score"],
                    "threshold": settings.dqs_threshold,
                    "blur": dqs_result["details"]["blur"],
                    "glare": dqs_result["details"]["glare"],
                    "contrast": dqs_result["details"]["contrast"],
                    "width": width,
                    "height": height
                })
                raise ValidationError(
                    error_code="IMAGE_QUALITY_TOO_LOW",
                    message=f"Image quality too low (DQS: {dqs_result['total_score']}/100). {dqs_result['feedback']}",
                    details={
                        "dqs_score": dqs_result["total_score"],
                        "threshold": settings.dqs_threshold,
                        "details": dqs_result["details"],
                        "feedback": dqs_result["feedback"]
                    }
                )

            return {
                "is_image": True,
                "width": width,
                "height": height,
                "dqs_score": dqs_result["total_score"],
                "dqs_details": dqs_result["details"],
                "dqs_feedback": dqs_result["feedback"],
                "is_quality_acceptable": True
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

    def _calculate_dqs(self, image_bytes: bytes) -> dict:
        """
        Calculates Document Quality Score (DQS) as weighted average.

        Metrics:
        - Blur (40%): Laplacian variance > 100
        - Glare (30%): < 5% of pixels > 250 brightness
        - Contrast (30%): Michelson ratio > 0.7

        Args:
            image_bytes: Image file bytes

        Returns:
            {
                "total_score": float (0-100),
                "is_acceptable": bool,
                "details": {"blur": float, "glare": float, "contrast": float},
                "feedback": str (user-friendly message)
            }
        """
        try:
            # Decode image
            nparr = np.frombuffer(image_bytes, np.uint8)
            gray = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)

            if gray is None:
                raise ValueError("Failed to decode image for DQS calculation")

            h, w = gray.shape

            # --- METRIC 1: BLUR (Laplacian variance) ---
            blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
            # Normalize to 0-100 scale (threshold = 100)
            blur_normalized = min(100, (blur_score / 150) * 100)

            # --- METRIC 2: GLARE (brightness clustering) ---
            # Count pixels above brightness threshold (250 = near-white)
            _, mask = cv2.threshold(gray, settings.glare_pixel_threshold, 255, cv2.THRESH_BINARY)
            glare_pixels = cv2.countNonZero(mask)
            glare_percent = (glare_pixels / (h * w)) * 100
            # Normalize (penalize glare)
            glare_normalized = max(0, 100 - (glare_percent * 10))

            # --- METRIC 3: CONTRAST (Michelson ratio) ---
            # Formula: (Lmax - Lmin) / (Lmax + Lmin)
            min_val, max_val, _, _ = cv2.minMaxLoc(gray)
            if max_val + min_val == 0:
                contrast_score = 0
            else:
                contrast_score = (max_val - min_val) / (max_val + min_val)
            # Normalize to 0-100 scale
            contrast_normalized = contrast_score * 100

            # --- WEIGHTED TOTAL SCORE ---
            total_score = (
                blur_normalized * settings.dqs_blur_weight +
                glare_normalized * settings.dqs_glare_weight +
                contrast_normalized * settings.dqs_contrast_weight
            )

            # --- USER FEEDBACK ---
            feedback = self._generate_dqs_feedback(blur_normalized, glare_normalized, contrast_normalized)

            return {
                "total_score": round(total_score, 2),
                "is_acceptable": total_score >= settings.dqs_threshold,
                "details": {
                    "blur": round(blur_normalized, 2),
                    "glare": round(glare_normalized, 2),
                    "contrast": round(contrast_normalized, 2)
                },
                "feedback": feedback
            }

        except Exception as e:
            logger.warning("DQS calculation failed, assuming acceptable", extra={"error": str(e)})
            # Return passing score if calculation fails
            return {
                "total_score": 75.0,
                "is_acceptable": True,
                "details": {"blur": 75.0, "glare": 75.0, "contrast": 75.0},
                "feedback": "✅ Image quality is good"
            }

    def _generate_dqs_feedback(self, blur: float, glare: float, contrast: float) -> str:
        """
        Generates user-friendly feedback based on lowest-scoring metric.

        Args:
            blur: Blur score (0-100)
            glare: Glare score (0-100)
            contrast: Contrast score (0-100)

        Returns:
            User-friendly feedback message
        """
        scores = {
            "blur": (blur, "Hold phone steady or move to better lighting"),
            "glare": (glare, "Turn off flash or tilt document away from overhead lights"),
            "contrast": (contrast, "Ensure document is on a dark, flat surface")
        }

        # Find lowest-scoring metric
        lowest = min(scores.items(), key=lambda x: x[1][0])
        metric_name, (score, message) = lowest

        if score < 50:
            return f"⚠️ Image quality issue: {message}"
        elif score < 70:
            return f"⚠️ Image quality could be better: {message}"
        else:
            return "✅ Image quality is good"


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
