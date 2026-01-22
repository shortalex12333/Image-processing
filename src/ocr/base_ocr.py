"""
Base OCR interface - abstract class for all OCR engines.
Allows swapping between Google Vision, Surya, Tesseract without code changes.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class OCRResult:
    """
    Standardized OCR result format (same across all engines).

    Attributes:
        text: Full extracted text
        confidence: Overall confidence score (0.0 to 1.0)
        lines: List of individual text lines with metadata
        processing_time_ms: Processing time in milliseconds
        engine_used: Name of OCR engine used
        metadata: Engine-specific metadata (cost, version, etc.)
    """
    text: str
    confidence: float
    lines: List[Dict[str, Any]]
    processing_time_ms: int
    engine_used: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseOCR(ABC):
    """
    Abstract base class for all OCR engines.

    Implementations:
    - GoogleVisionOCR: Cloud API ($1.50 per 1000 images, 80% accuracy)
    - SuryaOCR: Self-hosted (free, 91% accuracy, requires 4GB RAM)
    - TesseractOCR: Local (free, 20% accuracy, low quality)

    Usage:
        ocr = OCRFactory.get_ocr_engine()  # Auto-selects based on config
        result = await ocr.extract_text(image_bytes)
        print(f"Extracted {len(result.text)} chars with {result.confidence:.1%} confidence")
    """

    @abstractmethod
    async def extract_text(self, image_bytes: bytes) -> OCRResult:
        """
        Extract text from image bytes.

        Args:
            image_bytes: Raw image/PDF bytes (JPEG, PNG, PDF, etc.)

        Returns:
            OCRResult with standardized format

        Raises:
            Exception: If OCR processing fails
        """
        pass

    @abstractmethod
    def get_engine_name(self) -> str:
        """
        Return engine name for logging/metrics.

        Returns:
            Engine name (e.g., "google_vision", "surya", "tesseract")
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if OCR engine is available and healthy.

        Returns:
            True if engine is ready, False otherwise
        """
        pass
