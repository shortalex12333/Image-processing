"""
Receiving handler - orchestrates the complete receiving workflow.
Coordinates intake, OCR, extraction, reconciliation, and commit operations.
"""

from uuid import UUID
from typing import Any
from fastapi import UploadFile

from src.intake.validator import FileValidator, ValidationError
from src.intake.deduplicator import Deduplicator
from src.intake.rate_limiter import RateLimiter, RateLimitExceeded
from src.intake.storage_manager import StorageManager, StorageUploadError
from src.ocr.tesseract_ocr import TesseractOCR
from src.ocr.pdf_extractor import PDFExtractor
from src.ocr.cloud_ocr import CloudOCR, CloudOCRNotAvailable
from src.extraction.table_detector import TableDetector
from src.extraction.row_parser import RowParser
from src.extraction.cost_controller import SessionCostTracker, CostController, Decision
from src.extraction.llm_normalizer import LLMNormalizer
from src.reconciliation.part_matcher import PartMatcher
from src.reconciliation.shopping_matcher import ShoppingListMatcher
from src.reconciliation.order_matcher import OrderMatcher
from src.reconciliation.suggestion_ranker import SuggestionRanker
from src.commit.event_creator import EventCreator
from src.commit.inventory_updater import InventoryUpdater
from src.commit.finance_recorder import FinanceRecorder
from src.commit.audit_logger import AuditLogger
from src.database import get_supabase_service
from src.config import settings
from src.logger import get_logger

logger = get_logger(__name__)


class ReceivingHandler:
    """Handles complete receiving workflow from upload to commit."""

    def __init__(self):
        self.supabase = get_supabase_service()

        # Intake components
        self.validator = None  # Created per upload type
        self.deduplicator = Deduplicator()
        self.rate_limiter = RateLimiter()
        self.storage_manager = StorageManager()

        # OCR components
        self.tesseract_ocr = TesseractOCR()
        self.pdf_extractor = PDFExtractor()

        # Extraction components
        self.table_detector = TableDetector()
        self.row_parser = RowParser()

        # Reconciliation components
        self.part_matcher = PartMatcher()
        self.shopping_matcher = ShoppingListMatcher()
        self.order_matcher = OrderMatcher()
        self.suggestion_ranker = SuggestionRanker()

        # Commit components
        self.event_creator = EventCreator()
        self.inventory_updater = InventoryUpdater()
        self.finance_recorder = FinanceRecorder()
        self.audit_logger = AuditLogger()

    async def process_upload(
        self,
        yacht_id: UUID,
        user_id: UUID,
        files: list[UploadFile],
        upload_type: str,
        session_id: UUID | None = None
    ) -> dict:
        """
        Process uploaded image/PDF files.

        Args:
            yacht_id: Yacht UUID
            user_id: Uploader user UUID
            files: List of uploaded files
            upload_type: Type of upload (receiving, shipping_label, etc.)
            session_id: Existing session UUID (optional)

        Returns:
            Upload response with image metadata

        Workflow:
        1. Check rate limit
        2. Validate files (MIME, size, blur)
        3. Check for duplicates (SHA256)
        4. Upload to storage
        5. Record in database
        6. Queue for processing

        Raises:
            RateLimitExceeded: If rate limit exceeded
            ValidationError: If file validation fails
            StorageUploadError: If storage upload fails
        """
        # Step 1: Check rate limit
        await self.rate_limiter.check_rate_limit(yacht_id)

        uploaded_images = []
        self.validator = FileValidator(upload_type)

        for file in files:
            try:
                # Step 2: Validate file
                validation = await self.validator.validate(file)

                # Step 3: Calculate SHA256 and check duplicate
                content = await file.read()
                await file.seek(0)  # Reset for storage upload

                sha256 = self.deduplicator.calculate_sha256(content)
                existing = await self.deduplicator.check_duplicate(sha256, yacht_id)

                if existing:
                    # Duplicate found - return existing image
                    uploaded_images.append({
                        "image_id": existing["image_id"],
                        "file_name": file.filename,
                        "is_duplicate": True,
                        "existing_image_id": existing["image_id"],
                        "processing_status": existing["processing_status"],
                        "storage_path": existing["storage_path"],
                        "message": "Duplicate image - using existing upload"
                    })
                    continue

                # Step 4: Upload to storage
                storage_path = self.storage_manager.generate_storage_path(
                    yacht_id, upload_type, file.filename
                )
                storage_result = await self.storage_manager.upload_file(
                    content, storage_path, upload_type, validation["mime_type"]
                )

                # Step 5: Record in database
                image_id = await self.deduplicator.record_upload(
                    yacht_id=yacht_id,
                    user_id=user_id,
                    file_name=file.filename,
                    mime_type=validation["mime_type"],
                    file_size_bytes=validation["file_size_bytes"],
                    sha256=sha256,
                    storage_path=storage_path,
                    upload_type=upload_type,
                    width=validation.get("width"),
                    height=validation.get("height"),
                    blur_score=validation.get("blur_score")
                )

                uploaded_images.append({
                    "image_id": str(image_id),
                    "file_name": file.filename,
                    "file_size_bytes": validation["file_size_bytes"],
                    "mime_type": validation["mime_type"],
                    "is_duplicate": False,
                    "processing_status": "queued",
                    "storage_path": storage_path,
                    "message": "Upload successful - queued for processing"
                })

                logger.info("File uploaded successfully", extra={
                    "image_id": str(image_id),
                    "file_name": file.filename,
                    "yacht_id": str(yacht_id)
                })

            except ValidationError as e:
                uploaded_images.append({
                    "file_name": file.filename,
                    "is_duplicate": False,
                    "processing_status": "failed",
                    "message": e.message,
                    "error_code": e.error_code
                })
                logger.warning("File validation failed", extra={
                    "file_name": file.filename,
                    "error": e.message
                })

        # Determine status
        success_count = sum(1 for img in uploaded_images if img.get("processing_status") != "failed")
        status = "success" if success_count == len(files) else "partial_success"

        return {
            "status": status,
            "images": uploaded_images,
            "session_id": str(session_id) if session_id else None,
            "processing_eta_seconds": 30 if success_count > 0 else None
        }

    async def process_image_to_draft_lines(
        self,
        image_id: UUID,
        yacht_id: UUID,
        session_id: UUID
    ) -> dict:
        """
        Process image to extract draft lines.

        Args:
            image_id: Image UUID
            yacht_id: Yacht UUID
            session_id: Session UUID

        Returns:
            Processing result with draft lines

        Workflow:
        1. Fetch image from storage
        2. OCR extraction
        3. Table detection
        4. Row parsing (deterministic)
        5. LLM normalization (if needed)
        6. Part reconciliation
        7. Create draft lines
        """
        # Initialize cost tracker for this session
        cost_tracker = SessionCostTracker(session_id)

        try:
            # Step 1: Fetch image metadata
            result = self.supabase.table("pms_image_uploads") \
                .select("storage_path, mime_type, metadata") \
                .eq("image_id", str(image_id)) \
                .single() \
                .execute()

            if not result.data:
                raise Exception(f"Image not found: {image_id}")

            storage_path = result.data["storage_path"]
            mime_type = result.data["mime_type"]
            upload_type = result.data.get("metadata", {}).get("upload_type", "receiving")

            # Download image
            bucket_name = self.storage_manager.supabase.storage.from_(
                settings.storage_bucket_receiving
            ).get_bucket()
            image_bytes = await self.storage_manager.download_file(
                settings.storage_bucket_receiving, storage_path
            )

            # Step 2: OCR extraction
            if mime_type == "application/pdf":
                ocr_result = await self.pdf_extractor.extract_text(image_bytes)
            else:
                ocr_result = await self.tesseract_ocr.extract_text(image_bytes, preprocess=True)

                # Fallback to cloud OCR if confidence too low
                if ocr_result["confidence"] < 0.6 and settings.enable_cloud_ocr_fallback:
                    try:
                        cloud_ocr = CloudOCR(settings.ocr_engine)
                        ocr_result = await cloud_ocr.extract_text(image_bytes)
                    except CloudOCRNotAvailable:
                        logger.info("Cloud OCR not available, using Tesseract result")

            # Step 3: Table detection
            table_result = self.table_detector.detect_table(ocr_result)

            # Step 4: Row parsing
            parse_result = self.row_parser.parse_lines(ocr_result["text"])

            # Step 5: LLM normalization (if needed)
            controller = CostController(cost_tracker)
            decision = controller.decide_next_action(
                coverage=parse_result["coverage"],
                table_confidence=table_result.get("confidence", 0.0),
                llm_attempts=0
            )

            if decision.action == "invoke_llm":
                normalizer = LLMNormalizer(cost_tracker)
                llm_result = await normalizer.normalize(
                    ocr_text=ocr_result["text"],
                    model=decision.model,
                    max_tokens=decision.max_tokens,
                    temperature=decision.temperature
                )
                # Use LLM results
                extracted_lines = llm_result["lines"]
            else:
                # Use deterministic results
                extracted_lines = parse_result["lines"]

            # Step 6: Part reconciliation
            draft_lines = []
            for line in extracted_lines:
                # Find matching parts
                part_matches = await self.part_matcher.find_matches(
                    yacht_id=yacht_id,
                    description=line["description"],
                    part_number=line.get("part_number"),
                    limit=5
                )

                # Check shopping list
                shopping_match = None
                if part_matches:
                    shopping_match = await self.shopping_matcher.check_shopping_list_match(
                        yacht_id=yacht_id,
                        part_id=UUID(part_matches[0]["part_id"]),
                        quantity=line["quantity"]
                    )

                # Check recent orders
                recent_orders = []
                if part_matches:
                    recent_orders = await self.order_matcher.find_recent_orders(
                        yacht_id=yacht_id,
                        part_id=UUID(part_matches[0]["part_id"])
                    )

                # Rank suggestions
                suggested_part = self.suggestion_ranker.rank_suggestions(
                    part_matches=part_matches,
                    shopping_list_match=shopping_match,
                    recent_orders=recent_orders
                )

                # Create alternative suggestions
                alternatives = self.suggestion_ranker.create_alternative_suggestions(
                    part_matches=part_matches,
                    exclude_part_id=UUID(suggested_part["part_id"]) if suggested_part else None
                )

                # Create draft line
                draft_line = {
                    "line_number": line["line_number"],
                    "quantity": line["quantity"],
                    "unit": line["unit"],
                    "description": line["description"],
                    "extracted_part_number": line.get("part_number"),
                    "is_verified": False,
                    "source_image_id": str(image_id),
                    "suggested_part": suggested_part,
                    "alternative_suggestions": alternatives,
                    "shopping_list_match": shopping_match
                }
                draft_lines.append(draft_line)

            # Step 7: Create draft lines in database
            await self._save_draft_lines(session_id, yacht_id, draft_lines)

            logger.info("Image processed to draft lines", extra={
                "image_id": str(image_id),
                "session_id": str(session_id),
                "lines_extracted": len(draft_lines),
                "llm_used": decision.action == "invoke_llm",
                "cost": cost_tracker.total_cost
            })

            return {
                "status": "completed",
                "lines_extracted": len(draft_lines),
                "coverage": parse_result["coverage"],
                "llm_invocations": cost_tracker.llm_calls,
                "total_cost": cost_tracker.total_cost
            }

        except Exception as e:
            logger.error("Image processing failed", extra={
                "image_id": str(image_id),
                "error": str(e)
            }, exc_info=True)
            raise

    async def _save_draft_lines(
        self,
        session_id: UUID,
        yacht_id: UUID,
        draft_lines: list[dict]
    ) -> None:
        """
        Save draft lines to database.

        Args:
            session_id: Session UUID
            yacht_id: Yacht UUID
            draft_lines: List of draft lines to save
        """
        for line in draft_lines:
            line_data = {
                "session_id": str(session_id),
                "yacht_id": str(yacht_id),
                **line
            }
            self.supabase.table("pms_receiving_draft_lines").insert(line_data).execute()

    async def commit_session(
        self,
        session_id: UUID,
        yacht_id: UUID,
        committed_by: UUID,
        commitment_notes: str,
        override_unverified: bool = False
    ) -> dict:
        """
        Commit receiving session (create immutable records).

        Args:
            session_id: Session UUID
            yacht_id: Yacht UUID
            committed_by: User committing (must be HOD)
            commitment_notes: Commit notes
            override_unverified: Allow committing unverified lines

        Returns:
            Commit response

        Workflow:
        1. Validate session ready for commit
        2. Get verified draft lines
        3. Create receiving event
        4. Update inventory
        5. Record finances
        6. Create audit log
        7. Update session status
        """
        # Step 1: Get draft lines
        result = self.supabase.table("pms_receiving_draft_lines") \
            .select("*") \
            .eq("session_id", str(session_id)) \
            .eq("yacht_id", str(yacht_id)) \
            .execute()

        draft_lines = result.data or []

        if not draft_lines:
            raise Exception("No draft lines found for session")

        # Check verification status
        if not override_unverified:
            unverified = [l for l in draft_lines if not l["is_verified"]]
            if unverified:
                raise Exception(f"{len(unverified)} lines not verified")

        # Step 2: Create receiving event
        event = await self.event_creator.create_receiving_event(
            session_id=session_id,
            yacht_id=yacht_id,
            committed_by=committed_by,
            commitment_notes=commitment_notes,
            draft_lines=draft_lines
        )

        # Step 3: Update inventory
        inventory_updates = await self.inventory_updater.update_inventory(
            yacht_id=yacht_id,
            event_id=UUID(event["event_id"]),
            committed_by=committed_by,
            draft_lines=draft_lines
        )

        # Step 4: Record finances
        finance_updates = await self.finance_recorder.record_finance_transactions(
            yacht_id=yacht_id,
            event_id=UUID(event["event_id"]),
            committed_by=committed_by,
            draft_lines=draft_lines
        )

        # Step 5: Create audit log
        audit_id = await self.audit_logger.log_session_commit(
            yacht_id=yacht_id,
            user_id=committed_by,
            session_id=session_id,
            event_id=UUID(event["event_id"]),
            lines_committed=len(draft_lines)
        )

        # Step 6: Update session status
        self.supabase.table("pms_receiving_sessions") \
            .update({
                "status": "committed",
                "committed_by": str(committed_by),
                "committed_at": event["committed_at"],
                "event_id": event["event_id"]
            }) \
            .eq("session_id", str(session_id)) \
            .execute()

        logger.info("Session committed successfully", extra={
            "session_id": str(session_id),
            "event_id": event["event_id"],
            "lines_committed": len(draft_lines)
        })

        return {
            "status": "success",
            "receiving_event": event,
            "inventory_updates": inventory_updates,
            "finance_updates": finance_updates,
            "audit_trail": {
                "audit_log_id": str(audit_id),
                "signature": event["signature"]
            },
            "committed_at": event["committed_at"]
        }
