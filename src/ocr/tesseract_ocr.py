"""
Tesseract OCR for text extraction.
Self-hosted, free, no API costs.
Cost: $0
Accuracy: ~20% (low quality, fallback only)
"""

import io
import time
from typing import Any

import pytesseract
from PIL import Image

from src.config import settings
from src.logger import get_logger
from src.ocr.preprocessor import ImagePreprocessor
from src.ocr.base_ocr import BaseOCR, OCRResult

logger = get_logger(__name__)


class TesseractOCR(BaseOCR):
    """
    Tesseract OCR engine wrapper (fallback engine).

    Use only when Google Vision or Surya are unavailable.
    Accuracy is ~20% on phone photos.
    """

    def __init__(self):
        # Set Tesseract command path - try multiple common locations
        import shutil

        tesseract_path = settings.tesseract_cmd

        # If configured path doesn't exist, try to find tesseract in PATH
        if not self._command_exists(tesseract_path):
            # Try to find tesseract using shutil.which
            found_path = shutil.which('tesseract')
            if found_path:
                tesseract_path = found_path
                logger.info(f"Tesseract found at {tesseract_path}")
            else:
                logger.warning(f"Tesseract not found at {tesseract_path} or in PATH")

        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        logger.info("Tesseract OCR initialized")

    def _command_exists(self, cmd: str) -> bool:
        """Check if a command exists at the given path"""
        import os
        return os.path.isfile(cmd) and os.access(cmd, os.X_OK)

    async def extract_text(self, image_bytes: bytes, preprocess: bool = True) -> OCRResult:
        """
        Extract text from image using Tesseract.

        Args:
            image_bytes: Image file bytes
            preprocess: Whether to preprocess image first

        Returns:
            OCRResult with standardized format
        """
        start_time = time.time()

        try:
            # Optionally preprocess image
            if preprocess:
                preprocessor = ImagePreprocessor()
                image_bytes = preprocessor.preprocess(image_bytes)
                image_bytes = preprocessor.resize_for_ocr(image_bytes)

            # Load image
            image = Image.open(io.BytesIO(image_bytes))

            # Extract text with confidence data
            ocr_data = pytesseract.image_to_data(
                image,
                output_type=pytesseract.Output.DICT,
                config='--psm 6'  # Assume uniform block of text
            )

            # Combine all text
            text = " ".join([
                word for word in ocr_data['text']
                if word.strip()  # Filter empty strings
            ])

            # Calculate average confidence
            confidences = [
                conf for conf in ocr_data['conf']
                if conf != -1  # -1 means no confidence
            ]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            # Get bounding boxes for structure detection
            lines = self._extract_lines_with_bbox(ocr_data)

            confidence = avg_confidence / 100.0  # Normalize to 0-1
            processing_time = int((time.time() - start_time) * 1000)

            logger.info("Tesseract OCR complete", extra={
                "confidence": confidence,
                "word_count": len(text.split()),
                "text_length": len(text),
                "processing_time_ms": processing_time
            })

            return OCRResult(
                text=text,
                confidence=confidence,
                lines=lines,
                processing_time_ms=processing_time,
                engine_used="tesseract",
                metadata={
                    "word_count": len(text.split()),
                    "line_count": text.count('\n') + 1,
                    "cost_usd": 0.0,
                    "preprocessed": preprocess
                }
            )

        except Exception as e:
            logger.error("Tesseract OCR failed", extra={"error": str(e)}, exc_info=True)
            raise

    def _extract_lines_with_bbox(self, ocr_data: dict) -> list[dict]:
        """
        Extract text lines with bounding boxes (standardized format).

        Args:
            ocr_data: Tesseract output data

        Returns:
            List of lines with text, confidence, and bbox
        """
        lines = []
        for i, text in enumerate(ocr_data['text']):
            if not text.strip():
                continue

            line = {
                "text": text,
                "confidence": ocr_data['conf'][i] / 100.0 if ocr_data['conf'][i] != -1 else 0.0,
                "bbox": [
                    ocr_data['left'][i],
                    ocr_data['top'][i],
                    ocr_data['left'][i] + ocr_data['width'][i],
                    ocr_data['top'][i] + ocr_data['height'][i]
                ]
            }
            lines.append(line)

        return lines

    def get_engine_name(self) -> str:
        """Return engine name."""
        return "tesseract"

    async def health_check(self) -> bool:
        """Check if Tesseract is installed and accessible."""
        try:
            version = pytesseract.get_tesseract_version()
            logger.info(f"Tesseract health check passed (version {version})")
            return True
        except Exception as e:
            logger.error("Tesseract health check failed", extra={"error": str(e)})
            return False

    async def extract_from_pdf_page(self, pdf_bytes: bytes, page_number: int = 0) -> dict:
        """
        Extract text from a specific PDF page using OCR.

        Args:
            pdf_bytes: PDF file bytes
            page_number: Page number (0-indexed)

        Returns:
            OCR result for that page
        """
        # TODO: Convert PDF page to image, then OCR
        # For now, delegate to pdf_extractor.py
        raise NotImplementedError("PDF OCR via Tesseract not yet implemented")
