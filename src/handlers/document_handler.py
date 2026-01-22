"""
DocumentHandler - Processes uploaded documents with OCR and database matching.

This handler orchestrates the document processing pipeline:
1. Upload to temp storage
2. OCR text extraction
3. Database matching
4. Approval workflow
"""

from typing import Optional, Dict, Any
from uuid import UUID

from src.ocr.ocr_factory import OCRFactory
from src.intake.rate_limiter import RateLimiter, RateLimitExceeded
from src.logger import get_logger

logger = get_logger(__name__)


class DocumentHandler:
    """
    Handles document upload, OCR, and processing workflow.

    This class manages the entire document processing pipeline from upload
    to approval, including OCR text extraction and database matching.
    """

    def __init__(self):
        """
        Initialize DocumentHandler with OCR engine and rate limiter.

        The OCR engine is selected based on settings.OCR_ENGINE:
        - tesseract: Free, low accuracy (20%), fallback only
        - google_vision: $1.50/1000 images, 80% accuracy (recommended)
        - surya: Free, 91% accuracy, requires 4GB RAM (future upgrade)

        Rate limiter enforces MAX_UPLOADS_PER_HOUR (default: 50/hour)
        """
        # Get OCR engine from factory (based on config)
        self.ocr_engine = OCRFactory.get_ocr_engine()

        # Initialize rate limiter for upload throttling
        self.rate_limiter = RateLimiter()

        logger.info(
            "DocumentHandler initialized",
            extra={"ocr_engine": self.ocr_engine.get_engine_name()}
        )

    async def _save_to_temp_storage(
        self,
        yacht_id: UUID,
        file_bytes: bytes,
        filename: str
    ) -> tuple[str, str]:
        """
        Save uploaded file to temp storage for processing.

        Args:
            yacht_id: Yacht UUID for tenant isolation
            file_bytes: File content as bytes
            filename: Original filename (used to extract extension)

        Returns:
            Tuple of (temp_file_id, temp_file_path)
            - temp_file_id: UUID string for this upload
            - temp_file_path: Full path to saved file

        Raises:
            ValueError: If filename has no extension
            OSError: If file write fails
        """
        import os
        from uuid import uuid4

        # Generate unique file ID
        temp_file_id = str(uuid4())

        # Extract file extension
        _, ext = os.path.splitext(filename)
        if not ext:
            raise ValueError(f"Filename must have extension: {filename}")

        # Build temp file path: temp_uploads/{yacht_id}/{uuid}.ext
        temp_dir = os.path.join("temp_uploads", str(yacht_id))
        os.makedirs(temp_dir, exist_ok=True)

        temp_filename = f"{temp_file_id}{ext}"
        temp_file_path = os.path.join(temp_dir, temp_filename)

        # Write file to temp storage
        try:
            with open(temp_file_path, 'wb') as f:
                f.write(file_bytes)

            logger.info(
                "File saved to temp storage",
                extra={
                    "yacht_id": str(yacht_id),
                    "temp_file_id": temp_file_id,
                    "filename": filename,
                    "size_bytes": len(file_bytes),
                    "temp_path": temp_file_path
                }
            )

            return temp_file_id, temp_file_path

        except OSError as e:
            logger.error(
                "Failed to save file to temp storage",
                extra={
                    "yacht_id": str(yacht_id),
                    "filename": filename,
                    "error": str(e)
                }
            )
            raise

    async def _check_rate_limit(self, yacht_id: UUID) -> None:
        """
        Check if yacht has exceeded upload rate limit.

        Args:
            yacht_id: Yacht UUID for rate limiting

        Raises:
            RateLimitExceeded: If yacht exceeded MAX_UPLOADS_PER_HOUR
        """
        await self.rate_limiter.check_rate_limit(yacht_id)

        logger.debug(
            "Rate limit check passed",
            extra={"yacht_id": str(yacht_id)}
        )

    async def process_packing_slip_preview(
        self,
        yacht_id: UUID,
        file_bytes: bytes,
        filename: str
    ) -> Dict[str, Any]:
        """
        Process packing slip end-to-end and generate preview.

        Args:
            yacht_id: Yacht UUID
            file_bytes: Document image bytes
            filename: Original filename

        Returns:
            Preview dict with OCR, classification, entities, and matching
        """
        import time
        start_time = time.time()

        from src.extraction.document_classifier import DocumentClassifier
        from src.extraction.entity_extractor import EntityExtractor
        from src.reconciliation.order_matcher_by_number import OrderMatcherByNumber

        # Step 1: Save to temp storage
        temp_file_id, temp_path = await self._save_to_temp_storage(
            yacht_id, file_bytes, filename
        )

        # Step 2: Extract text with OCR
        ocr_result = await self.ocr_engine.extract_text(file_bytes)

        # Step 3: Classify document
        classifier = DocumentClassifier()
        classification = classifier.classify(ocr_result.text)

        # Step 4: Extract entities (order #, tracking, line items)
        extractor = EntityExtractor()
        entities = extractor.extract_packing_slip_entities(ocr_result.text)

        # Step 5: Match to database
        matcher = OrderMatcherByNumber()
        order_match = None
        shopping_list = []

        if entities["order_number"]:
            order_match = await matcher.find_order(yacht_id, entities["order_number"])

            if order_match:
                shopping_list = await matcher.get_shopping_list_items(
                    yacht_id, order_match["id"]
                )

        processing_time = (time.time() - start_time) * 1000

        preview = {
            "temp_file_id": temp_file_id,
            "temp_file_path": temp_path,
            "ocr_results": {
                "text": ocr_result.text,
                "confidence": ocr_result.confidence,
                "engine_used": ocr_result.engine_used,
                "processing_time_ms": ocr_result.processing_time_ms
            },
            "document_classification": classification,
            "extracted_entities": entities,
            "matching": {
                "order_found": order_match is not None,
                "order": order_match,
                "shopping_list_items": shopping_list
            },
            "processing_time_total_ms": int(processing_time)
        }

        logger.info(
            "Packing slip preview generated",
            extra={
                "yacht_id": str(yacht_id),
                "temp_file_id": temp_file_id,
                "doc_type": classification["type"],
                "order_found": order_match is not None,
                "processing_time_ms": int(processing_time)
            }
        )

        return preview
