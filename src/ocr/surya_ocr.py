"""
Surya OCR implementation (self-hosted).
Cost: $0 (but requires 4GB RAM server)
Accuracy: ~91% (tested on phone photos)
Speed: ~30s per image (slower but more accurate)

NOTE: This requires Render Standard plan ($25/month) or equivalent.
Will NOT work on Starter plan (512MB RAM).
"""

import time
from io import BytesIO
from typing import Dict, Any, List
from PIL import Image
from src.ocr.base_ocr import BaseOCR, OCRResult
from src.logger import get_logger

logger = get_logger(__name__)


class SuryaOCR(BaseOCR):
    """
    Surya OCR implementation (self-hosted).

    Features:
    - State-of-the-art accuracy (~91%)
    - Open source, no API fees
    - Bounding box detection
    - Multi-language support

    Requirements:
    - 4GB RAM minimum (model is 1.34GB)
    - Python 3.10+
    - GPU optional (faster with GPU)

    Installation:
        pip install surya-ocr pillow

    Pre-load models in Dockerfile:
        RUN python -c "from surya.recognition import FoundationPredictor; FoundationPredictor()"

    Configuration:
        OCR_ENGINE=surya
        SURYA_MODEL_PATH=/app/models/surya  # Optional cache dir
    """

    def __init__(self):
        logger.info("Loading Surya OCR models (this may take 30-60s)...")

        try:
            # Import here to avoid loading if not using Surya
            from surya.recognition import RecognitionPredictor, FoundationPredictor
            from surya.detection import DetectionPredictor

            self.foundation = FoundationPredictor()
            self.detection = DetectionPredictor()
            self.recognition = RecognitionPredictor(self.foundation)

            logger.info("Surya OCR models loaded successfully")

        except ImportError as e:
            logger.error("Surya OCR not installed", extra={
                "error": str(e),
                "install_command": "pip install surya-ocr"
            })
            raise Exception(
                "Surya OCR not installed. Run: pip install surya-ocr"
            )
        except Exception as e:
            logger.error("Failed to load Surya OCR models", extra={
                "error": str(e)
            })
            raise

    async def extract_text(self, image_bytes: bytes) -> OCRResult:
        """
        Extract text using Surya OCR.

        Args:
            image_bytes: Raw image bytes

        Returns:
            OCRResult with extracted text and confidence scores

        Raises:
            Exception: If OCR processing fails
        """
        start_time = time.time()

        try:
            # Convert bytes to PIL Image
            image = Image.open(BytesIO(image_bytes))

            # Convert to RGB if needed (Surya requires RGB)
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Run Surya OCR
            rec_results = self.recognition([image], det_predictor=self.detection)

            if not rec_results or len(rec_results) == 0:
                raise Exception("Surya OCR returned no results")

            result = rec_results[0]

            # Extract text lines
            text_lines = [line.text for line in result.text_lines]
            full_text = "\n".join(text_lines)

            # Calculate average confidence
            confidences = [line.confidence for line in result.text_lines]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            # Extract line-level data with bounding boxes
            lines = [
                {
                    "text": line.text,
                    "confidence": line.confidence,
                    "bbox": line.bbox  # Format: [x1, y1, x2, y2]
                }
                for line in result.text_lines
            ]

            processing_time = int((time.time() - start_time) * 1000)

            logger.info("Surya OCR completed", extra={
                "processing_time_ms": processing_time,
                "avg_confidence": avg_confidence,
                "lines_detected": len(lines),
                "text_length": len(full_text)
            })

            return OCRResult(
                text=full_text,
                confidence=avg_confidence,
                lines=lines,
                processing_time_ms=processing_time,
                engine_used="surya",
                metadata={
                    "model_version": "0.4.0",
                    "cost_usd": 0.0,  # Self-hosted, no API fees
                    "image_mode": image.mode,
                    "image_size": image.size
                }
            )

        except Exception as e:
            logger.error("Surya OCR processing failed", extra={
                "error": str(e)
            }, exc_info=True)
            raise Exception(f"Surya OCR failed: {e}")

    def get_engine_name(self) -> str:
        """Return engine name."""
        return "surya"

    async def health_check(self) -> bool:
        """
        Check if Surya models are loaded and working.

        Returns:
            True if models respond, False otherwise
        """
        try:
            # Test with minimal 1x1 pixel image
            test_image = Image.new('RGB', (1, 1), color='white')
            rec_results = self.recognition([test_image], det_predictor=self.detection)

            if rec_results and len(rec_results) > 0:
                logger.info("Surya OCR health check passed")
                return True
            else:
                logger.warning("Surya OCR health check failed: no results")
                return False

        except Exception as e:
            logger.error("Surya OCR health check error", extra={
                "error": str(e)
            })
            return False
