"""
Image preprocessing for improved OCR accuracy.
Includes deskewing, binarization, noise removal, and contrast enhancement.
"""

import cv2
import numpy as np
from PIL import Image
import io

from src.logger import get_logger

logger = get_logger(__name__)


class ImagePreprocessor:
    """Preprocesses images for optimal OCR results."""

    @staticmethod
    def preprocess(image_bytes: bytes) -> bytes:
        """
        Preprocess image for OCR.

        Pipeline:
        1. Convert to grayscale
        2. Deskew (rotate to correct orientation)
        3. Binarize (convert to black & white)
        4. Denoise (remove noise)
        5. Enhance contrast

        Args:
            image_bytes: Input image bytes

        Returns:
            Preprocessed image bytes
        """
        try:
            # Load image
            nparr = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if image is None:
                logger.warning("Failed to decode image for preprocessing")
                return image_bytes  # Return original

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
