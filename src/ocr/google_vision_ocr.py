"""
Google Cloud Vision API OCR implementation.
Cost: $1.50 per 1000 images
Accuracy: ~80% (tested on phone photos)
Speed: ~400ms per image
"""

import base64
import time
import requests
from typing import Dict, Any, List
from src.ocr.base_ocr import BaseOCR, OCRResult
from src.config import settings
from src.logger import get_logger

logger = get_logger(__name__)


class GoogleVisionOCR(BaseOCR):
    """
    Google Cloud Vision API implementation.

    Features:
    - DOCUMENT_TEXT_DETECTION mode (optimized for documents)
    - Bounding box detection for each text element
    - Fast processing (~400ms)
    - No local resources needed

    Limitations:
    - Requires API key and billing enabled
    - Online only (no offline mode)
    - $1.50 per 1000 images
    - ~80% accuracy on phone photos (O→0 confusion common)

    Configuration:
        GOOGLE_VISION_API_KEY=your_key_here
    """

    def __init__(self):
        self.api_key = settings.google_vision_api_key
        self.endpoint = (
            f"https://vision.googleapis.com/v1/images:annotate"
            f"?key={self.api_key}"
        )
        logger.info("Google Vision OCR initialized")

    async def extract_text(self, image_bytes: bytes) -> OCRResult:
        """
        Extract text using Google Vision API.

        Args:
            image_bytes: Raw image bytes

        Returns:
            OCRResult with extracted text and metadata

        Raises:
            requests.HTTPError: If API call fails
            Exception: If response parsing fails
        """
        start_time = time.time()

        # Encode image to base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')

        # Build request payload
        payload = {
            "requests": [{
                "image": {"content": image_base64},
                "features": [{
                    "type": "DOCUMENT_TEXT_DETECTION",
                    "maxResults": 1
                }],
                "imageContext": {
                    "languageHints": ["en"]  # English documents
                }
            }]
        }

        # Call Google Vision API
        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                timeout=30,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error("Google Vision API request failed", extra={
                "error": str(e),
                "status_code": getattr(e.response, 'status_code', None)
            })
            raise Exception(f"Google Vision API failed: {e}")

        result = response.json()

        # Parse response
        if 'responses' not in result or not result['responses']:
            raise Exception("No response from Google Vision API")

        annotation = result['responses'][0]

        # Check for API errors
        if 'error' in annotation:
            error_msg = annotation['error'].get('message', 'Unknown error')
            logger.error("Google Vision API error", extra={
                "error": error_msg,
                "code": annotation['error'].get('code')
            })
            raise Exception(f"Google Vision API error: {error_msg}")

        # Extract full text
        full_text = ""
        if 'fullTextAnnotation' in annotation:
            full_text = annotation['fullTextAnnotation'].get('text', '')

        # Extract line-level data with bounding boxes
        lines = []
        if 'textAnnotations' in annotation and len(annotation['textAnnotations']) > 0:
            # First annotation is full text, rest are individual words/blocks
            for text_annotation in annotation['textAnnotations'][1:]:
                lines.append({
                    "text": text_annotation.get('description', ''),
                    "confidence": 1.0,  # Google doesn't provide per-word confidence
                    "bbox": self._extract_bbox(text_annotation.get('boundingPoly', {}))
                })

        processing_time = int((time.time() - start_time) * 1000)

        logger.info("Google Vision OCR completed", extra={
            "processing_time_ms": processing_time,
            "text_length": len(full_text),
            "lines_detected": len(lines)
        })

        return OCRResult(
            text=full_text,
            confidence=0.80,  # Based on testing: 80% field-level accuracy
            lines=lines,
            processing_time_ms=processing_time,
            engine_used="google_vision",
            metadata={
                "api_version": "v1",
                "cost_usd": 0.0015,  # $1.50 per 1000 images
                "features_used": ["DOCUMENT_TEXT_DETECTION"],
                "language_hints": ["en"]
            }
        )

    def _extract_bbox(self, bounding_poly: Dict) -> List[Dict[str, int]]:
        """
        Extract bounding box vertices from Google Vision format.

        Args:
            bounding_poly: Google Vision bounding poly object

        Returns:
            List of vertices with x, y coordinates
        """
        vertices = bounding_poly.get('vertices', [])
        return [
            {"x": v.get('x', 0), "y": v.get('y', 0)}
            for v in vertices
        ]

    def get_engine_name(self) -> str:
        """Return engine name."""
        return "google_vision"

    async def health_check(self) -> bool:
        """
        Check if Google Vision API is accessible.

        Returns:
            True if API responds, False otherwise
        """
        try:
            # Create minimal 1x1 pixel PNG (smallest valid image)
            # PNG header + IHDR chunk for 1x1 transparent image
            test_image_bytes = base64.b64decode(
                b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
            )
            test_image_base64 = base64.b64encode(test_image_bytes).decode()

            payload = {
                "requests": [{
                    "image": {"content": test_image_base64},
                    "features": [{"type": "DOCUMENT_TEXT_DETECTION"}]
                }]
            }

            response = requests.post(
                self.endpoint,
                json=payload,
                timeout=5
            )

            if response.status_code == 200:
                logger.info("Google Vision API health check passed")
                return True
            else:
                logger.warning("Google Vision API health check failed", extra={
                    "status_code": response.status_code
                })
                return False

        except Exception as e:
            logger.error("Google Vision API health check error", extra={
                "error": str(e)
            })
            return False
