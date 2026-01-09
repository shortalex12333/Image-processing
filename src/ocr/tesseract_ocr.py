"""
Tesseract OCR for text extraction.
Self-hosted, free, no API costs.
"""

import io
from typing import Any

import pytesseract
from PIL import Image

from src.config import settings
from src.logger import get_logger
from src.ocr.preprocessor import ImagePreprocessor

logger = get_logger(__name__)


class TesseractOCR:
    """Tesseract OCR engine wrapper."""

    def __init__(self):
        # Set Tesseract command path
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    async def extract_text(self, image_bytes: bytes, preprocess: bool = True) -> dict:
        """
        Extract text from image using Tesseract.

        Args:
            image_bytes: Image file bytes
            preprocess: Whether to preprocess image first

        Returns:
            OCR result with text, confidence, and metadata

        Example:
            >>> ocr = TesseractOCR()
            >>> result = await ocr.extract_text(image_bytes)
            >>> result
            {
                "text": "Extracted text...",
                "confidence": 0.85,
                "word_count": 123,
                "method": "tesseract"
            }
        """
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
            bounding_boxes = self._extract_bounding_boxes(ocr_data)

            result = {
                "text": text,
                "confidence": avg_confidence / 100.0,  # Normalize to 0-1
                "word_count": len(text.split()),
                "line_count": text.count('\n') + 1,
                "bounding_boxes": bounding_boxes,
                "method": "tesseract"
            }

            logger.info("Tesseract OCR complete", extra={
                "confidence": result["confidence"],
                "word_count": result["word_count"],
                "text_length": len(text)
            })

            return result

        except Exception as e:
            logger.error("Tesseract OCR failed", extra={"error": str(e)}, exc_info=True)
            raise

    def _extract_bounding_boxes(self, ocr_data: dict) -> list[dict]:
        """
        Extract bounding box data for each word.

        Args:
            ocr_data: Tesseract output data

        Returns:
            List of bounding boxes with text and coordinates
        """
        boxes = []
        for i, text in enumerate(ocr_data['text']):
            if not text.strip():
                continue

            box = {
                "text": text,
                "left": ocr_data['left'][i],
                "top": ocr_data['top'][i],
                "width": ocr_data['width'][i],
                "height": ocr_data['height'][i],
                "confidence": ocr_data['conf'][i] / 100.0 if ocr_data['conf'][i] != -1 else 0.0
            }
            boxes.append(box)

        return boxes

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
