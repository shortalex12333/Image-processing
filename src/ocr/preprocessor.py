"""
Image preprocessing for improved OCR accuracy.
Includes deskewing, binarization, noise removal, and contrast enhancement.
"""

import cv2
import numpy as np
from PIL import Image
import io
from pillow_heif import register_heif_opener

from src.logger import get_logger

# Register HEIF opener with Pillow (call once at module load)
register_heif_opener()

logger = get_logger(__name__)


class ImagePreprocessor:
    """Preprocesses images for optimal OCR results."""

    @staticmethod
    def _convert_heic_if_needed(image_bytes: bytes) -> bytes:
        """
        Detects HEIC format and converts to PNG (OpenCV-compatible).
        Returns original bytes if already JPEG/PNG.

        Args:
            image_bytes: Input image bytes

        Returns:
            PNG bytes if HEIC, otherwise original bytes
        """
        try:
            # Check if HEIC by attempting to open with Pillow
            img = Image.open(io.BytesIO(image_bytes))

            # Check format (HEIC files report as "HEIF" in Pillow)
            if img.format in ["HEIF", "HEIC"]:
                # Convert to PNG in-memory
                png_buffer = io.BytesIO()
                img.save(png_buffer, format="PNG", optimize=True)
                png_bytes = png_buffer.getvalue()
                logger.info("Converted HEIC to PNG", extra={"original_size": len(image_bytes), "png_size": len(png_bytes)})
                return png_bytes
            else:
                # Already JPEG/PNG, return as-is
                return image_bytes

        except Exception as e:
            # If Pillow can't open it, pass through (cv2.imdecode will handle error)
            logger.debug("HEIC conversion skipped", extra={"error": str(e)})
            return image_bytes

    @staticmethod
    def _apply_exif_orientation(image: np.ndarray, image_bytes: bytes) -> np.ndarray:
        """
        Reads EXIF orientation tag and rotates image accordingly.
        Must be called BEFORE any other preprocessing.

        Args:
            image: OpenCV image array
            image_bytes: Original image bytes (for EXIF reading)

        Returns:
            Rotated image array
        """
        try:
            # Read EXIF data using Pillow
            img_pil = Image.open(io.BytesIO(image_bytes))
            exif = img_pil._getexif()

            if exif is None:
                return image  # No EXIF data, return as-is

            # EXIF tag 274 = Orientation
            orientation = exif.get(274, 1)

            # Apply transformations
            if orientation == 1:
                return image  # No rotation needed
            elif orientation == 2:
                return cv2.flip(image, 1)  # Flip horizontal
            elif orientation == 3:
                return cv2.rotate(image, cv2.ROTATE_180)
            elif orientation == 4:
                return cv2.flip(image, 0)  # Flip vertical
            elif orientation == 5:
                image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
                return cv2.flip(image, 1)
            elif orientation == 6:
                return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
            elif orientation == 7:
                image = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
                return cv2.flip(image, 1)
            elif orientation == 8:
                return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
            else:
                return image  # Unknown orientation, return as-is

        except Exception as e:
            # If EXIF read fails, return original image
            logger.debug("EXIF orientation read failed", extra={"error": str(e)})
            return image

    @staticmethod
    def preprocess(image_bytes: bytes) -> bytes:
        """
        Preprocess image for OCR.

        Pipeline:
        1. HEIC conversion (if needed)
        2. Convert to grayscale
        3. Deskew (rotate to correct orientation)
        4. Binarize (convert to black & white)
        5. Denoise (remove noise)
        6. Enhance contrast

        Args:
            image_bytes: Input image bytes

        Returns:
            Preprocessed image bytes
        """
        try:
            # Convert HEIC to PNG if needed
            image_bytes = ImagePreprocessor._convert_heic_if_needed(image_bytes)

            # Load image
            nparr = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if image is None:
                raise ValueError("Failed to decode image bytes")

            # Apply EXIF orientation FIRST (before any other preprocessing)
            image = ImagePreprocessor._apply_exif_orientation(image, image_bytes)

            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Deskew
            deskewed = ImagePreprocessor._deskew(gray)

            # Binarize
            binary = ImagePreprocessor._binarize(deskewed)

            # Denoise
            denoised = ImagePreprocessor._denoise(binary)

            # Enhance contrast
            enhanced = ImagePreprocessor._enhance_contrast(denoised)

            # Convert back to bytes
            success, encoded = cv2.imencode('.png', enhanced)
            if not success:
                logger.warning("Failed to encode preprocessed image")
                return image_bytes

            return encoded.tobytes()

        except Exception as e:
            logger.warning("Preprocessing failed, using original", extra={"error": str(e)})
            return image_bytes

    @staticmethod
    def _deskew(image: np.ndarray) -> np.ndarray:
        """
        Detect and correct image skew.

        Args:
            image: Grayscale image

        Returns:
            Deskewed image
        """
        try:
            # Calculate skew angle using Hough transform
            coords = np.column_stack(np.where(image > 0))
            angle = cv2.minAreaRect(coords)[-1]

            # Adjust angle
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle

            # Only deskew if angle is significant (> 0.5 degrees)
            if abs(angle) < 0.5:
                return image

            # Rotate image
            (h, w) = image.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(
                image, M, (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE
            )

            logger.debug("Image deskewed", extra={"angle": angle})
            return rotated

        except Exception as e:
            logger.debug("Deskew failed", extra={"error": str(e)})
            return image

    @staticmethod
    def _binarize(image: np.ndarray) -> np.ndarray:
        """
        Convert grayscale image to binary (black & white).

        Uses adaptive thresholding for better results with varying lighting.

        Args:
            image: Grayscale image

        Returns:
            Binary image
        """
        try:
            # Adaptive threshold - better for varying lighting conditions
            binary = cv2.adaptiveThreshold(
                image,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                11,  # Block size
                2    # Constant subtracted from mean
            )
            return binary

        except Exception as e:
            logger.debug("Binarization failed", extra={"error": str(e)})
            return image

    @staticmethod
    def _denoise(image: np.ndarray) -> np.ndarray:
        """
        Remove noise from image.

        Args:
            image: Binary image

        Returns:
            Denoised image
        """
        try:
            # Morphological opening (erosion followed by dilation)
            # Removes small noise spots
            kernel = np.ones((2, 2), np.uint8)
            denoised = cv2.morphologyEx(image, cv2.MORPH_OPEN, kernel)
            return denoised

        except Exception as e:
            logger.debug("Denoising failed", extra={"error": str(e)})
            return image

    @staticmethod
    def _enhance_contrast(image: np.ndarray) -> np.ndarray:
        """
        Enhance image contrast.

        Args:
            image: Grayscale or binary image

        Returns:
            Contrast-enhanced image
        """
        try:
            # CLAHE (Contrast Limited Adaptive Histogram Equalization)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(image)
            return enhanced

        except Exception as e:
            logger.debug("Contrast enhancement failed", extra={"error": str(e)})
            return image

    @staticmethod
    def resize_for_ocr(image_bytes: bytes, max_dimension: int = 3000) -> bytes:
        """
        Resize image if too large (improves OCR speed without losing accuracy).

        Args:
            image_bytes: Input image bytes
            max_dimension: Maximum width or height

        Returns:
            Resized image bytes
        """
        try:
            image = Image.open(io.BytesIO(image_bytes))
            width, height = image.size

            # Only resize if larger than max
            if width > max_dimension or height > max_dimension:
                # Calculate new dimensions (maintain aspect ratio)
                if width > height:
                    new_width = max_dimension
                    new_height = int(height * (max_dimension / width))
                else:
                    new_height = max_dimension
                    new_width = int(width * (max_dimension / height))

                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # Convert back to bytes
                output = io.BytesIO()
                image.save(output, format='PNG')
                return output.getvalue()

            return image_bytes

        except Exception as e:
            logger.warning("Resize failed, using original", extra={"error": str(e)})
            return image_bytes
