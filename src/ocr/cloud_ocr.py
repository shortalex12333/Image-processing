"""
Cloud OCR services (Google Vision, AWS Textract) as fallback.
Used when Tesseract confidence is low or fails.
"""

from typing import Literal

from src.config import settings
from src.logger import get_logger

logger = get_logger(__name__)


class CloudOCRNotAvailable(Exception):
    """Cloud OCR service not configured."""
    pass


class CloudOCR:
    """Cloud OCR services wrapper (Google Vision or AWS Textract)."""

    def __init__(self, provider: Literal["google_vision", "aws_textract"] = "google_vision"):
        self.provider = provider

        if not settings.enable_cloud_ocr_fallback:
            raise CloudOCRNotAvailable("Cloud OCR fallback is disabled")

    async def extract_text(self, image_bytes: bytes) -> dict:
        """
        Extract text using cloud OCR service.

        Args:
            image_bytes: Image file bytes

        Returns:
            OCR result with text, confidence, and metadata

        Raises:
            CloudOCRNotAvailable: If service not configured
        """
        if self.provider == "google_vision":
            return await self._google_vision_ocr(image_bytes)
        elif self.provider == "aws_textract":
            return await self._aws_textract_ocr(image_bytes)
        else:
            raise ValueError(f"Unknown OCR provider: {self.provider}")

    async def _google_vision_ocr(self, image_bytes: bytes) -> dict:
        """
        Extract text using Google Cloud Vision API.

        Cost: ~$0.0015 per image (first 1000 images/month free)

        Args:
            image_bytes: Image file bytes

        Returns:
            OCR result
        """
        try:
            # Check if credentials configured
            if not settings.google_application_credentials:
                raise CloudOCRNotAvailable("Google Vision credentials not configured")

            # Import Google Vision client
            from google.cloud import vision
            client = vision.ImageAnnotatorClient()

            # Prepare image
            image = vision.Image(content=image_bytes)

            # Perform OCR
            response = client.text_detection(image=image)
            texts = response.text_annotations

            if not texts:
                return {
                    "text": "",
                    "confidence": 0.0,
                    "word_count": 0,
                    "method": "google_vision"
                }

            # First annotation contains full text
            full_text = texts[0].description

            # Calculate average confidence from individual words
            confidences = []
            for text in texts[1:]:  # Skip first (full text)
                if hasattr(text, 'confidence'):
                    confidences.append(text.confidence)

            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.9

            result = {
                "text": full_text,
                "confidence": avg_confidence,
                "word_count": len(full_text.split()),
                "line_count": full_text.count('\n') + 1,
                "method": "google_vision",
                "cost_estimate": 0.0015  # Approximate cost per image
            }

            logger.info("Google Vision OCR complete", extra={
                "confidence": result["confidence"],
                "word_count": result["word_count"]
            })

            return result

        except ImportError:
            logger.error("Google Vision library not installed: pip install google-cloud-vision")
            raise CloudOCRNotAvailable("Google Vision library not available")
        except Exception as e:
            logger.error("Google Vision OCR failed", extra={"error": str(e)}, exc_info=True)
            raise

    async def _aws_textract_ocr(self, image_bytes: bytes) -> dict:
        """
        Extract text using AWS Textract.

        Cost: ~$0.0015 per page

        Args:
            image_bytes: Image file bytes

        Returns:
            OCR result
        """
        try:
            # Check if credentials configured
            if not settings.aws_access_key_id or not settings.aws_secret_access_key:
                raise CloudOCRNotAvailable("AWS credentials not configured")

            # Import boto3
            import boto3
            client = boto3.client(
                'textract',
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_region
            )

            # Call Textract
            response = client.detect_document_text(
                Document={'Bytes': image_bytes}
            )

            # Extract text from blocks
            text_blocks = []
            confidences = []

            for block in response['Blocks']:
                if block['BlockType'] == 'LINE':
                    text_blocks.append(block['Text'])
                    confidences.append(block['Confidence'] / 100.0)

            full_text = "\n".join(text_blocks)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            result = {
                "text": full_text,
                "confidence": avg_confidence,
                "word_count": len(full_text.split()),
                "line_count": len(text_blocks),
                "method": "aws_textract",
                "cost_estimate": 0.0015
            }

            logger.info("AWS Textract OCR complete", extra={
                "confidence": result["confidence"],
                "word_count": result["word_count"]
            })

            return result

        except ImportError:
            logger.error("boto3 library not installed: pip install boto3")
            raise CloudOCRNotAvailable("boto3 library not available")
        except Exception as e:
            logger.error("AWS Textract OCR failed", extra={"error": str(e)}, exc_info=True)
            raise
