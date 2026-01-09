"""
Photo handler - handles discrepancy and part photos.
Simple attachment workflow with no processing.
"""

from uuid import UUID
from datetime import datetime

from src.database import get_supabase_service
from src.logger import get_logger

logger = get_logger(__name__)


class PhotoHandler:
    """Handles discrepancy and part photo attachments."""

    def __init__(self):
        self.supabase = get_supabase_service()

    async def attach_discrepancy_photo(
        self,
        image_id: UUID,
        yacht_id: UUID,
        entity_type: str,
        entity_id: UUID,
        notes: str | None = None
    ) -> dict:
        """
        Attach discrepancy photo to an entity.

        Args:
            image_id: Image UUID
            yacht_id: Yacht UUID
            entity_type: Type of entity (fault, work_order, draft_line)
            entity_id: Entity UUID
            notes: Optional notes about discrepancy

        Returns:
            Attachment result

        Entities that can have discrepancy photos:
        - pms_faults (damaged equipment)
        - pms_work_orders (work in progress photos)
        - pms_receiving_draft_lines (damaged goods on arrival)
        """
        try:
            # Create entity-image junction record
            attachment_data = {
                "yacht_id": str(yacht_id),
                "entity_type": entity_type,
                "entity_id": str(entity_id),
                "image_id": str(image_id),
                "attachment_type": "discrepancy_photo",
                "notes": notes,
                "attached_at": datetime.utcnow().isoformat()
            }

            result = self.supabase.table("pms_entity_images") \
                .insert(attachment_data) \
                .execute()

            # Update image status
            self.supabase.table("pms_image_uploads") \
                .update({"processing_status": "completed"}) \
                .eq("image_id", str(image_id)) \
                .execute()

            logger.info("Discrepancy photo attached", extra={
                "image_id": str(image_id),
                "entity_type": entity_type,
                "entity_id": str(entity_id)
            })

            return {
                "status": "attached",
                "image_id": str(image_id),
                "entity_type": entity_type,
                "entity_id": str(entity_id)
            }

        except Exception as e:
            logger.error("Failed to attach discrepancy photo", extra={
                "image_id": str(image_id),
                "entity_type": entity_type,
                "error": str(e)
            }, exc_info=True)
            raise

    async def attach_part_photo(
        self,
        image_id: UUID,
        yacht_id: UUID,
        part_id: UUID,
        photo_type: str = "catalog",
        notes: str | None = None
    ) -> dict:
        """
        Attach part photo to a part.

        Args:
            image_id: Image UUID
            yacht_id: Yacht UUID
            part_id: Part UUID
            photo_type: Type of photo (catalog, installation, location)
            notes: Optional notes

        Returns:
            Attachment result

        Photo types:
        - catalog: Main product photo for catalog
        - installation: Shows how part is installed
        - location: Shows where part is stored
        """
        try:
            # Create entity-image junction record
            attachment_data = {
                "yacht_id": str(yacht_id),
                "entity_type": "part",
                "entity_id": str(part_id),
                "image_id": str(image_id),
                "attachment_type": f"part_photo_{photo_type}",
                "notes": notes,
                "attached_at": datetime.utcnow().isoformat()
            }

            result = self.supabase.table("pms_entity_images") \
                .insert(attachment_data) \
                .execute()

            # Update image status
            self.supabase.table("pms_image_uploads") \
                .update({"processing_status": "completed"}) \
                .eq("image_id", str(image_id)) \
                .execute()

            logger.info("Part photo attached", extra={
                "image_id": str(image_id),
                "part_id": str(part_id),
                "photo_type": photo_type
            })

            return {
                "status": "attached",
                "image_id": str(image_id),
                "part_id": str(part_id),
                "photo_type": photo_type
            }

        except Exception as e:
            logger.error("Failed to attach part photo", extra={
                "image_id": str(image_id),
                "part_id": str(part_id),
                "error": str(e)
            }, exc_info=True)
            raise

    async def get_entity_photos(
        self,
        yacht_id: UUID,
        entity_type: str,
        entity_id: UUID
    ) -> list[dict]:
        """
        Get all photos attached to an entity.

        Args:
            yacht_id: Yacht UUID
            entity_type: Entity type
            entity_id: Entity UUID

        Returns:
            List of attached photos with metadata
        """
        try:
            result = self.supabase.table("pms_entity_images") \
                .select("""
                    image_id,
                    attachment_type,
                    notes,
                    attached_at,
                    pms_image_uploads!inner(
                        file_name,
                        storage_path,
                        file_size_bytes,
                        uploaded_at
                    )
                """) \
                .eq("yacht_id", str(yacht_id)) \
                .eq("entity_type", entity_type) \
                .eq("entity_id", str(entity_id)) \
                .order("attached_at", desc=True) \
                .execute()

            photos = []
            for row in result.data or []:
                image = row["pms_image_uploads"]
                photos.append({
                    "image_id": row["image_id"],
                    "file_name": image["file_name"],
                    "storage_path": image["storage_path"],
                    "attachment_type": row["attachment_type"],
                    "notes": row["notes"],
                    "attached_at": row["attached_at"],
                    "uploaded_at": image["uploaded_at"]
                })

            return photos

        except Exception as e:
            logger.error("Failed to get entity photos", extra={
                "entity_type": entity_type,
                "entity_id": str(entity_id),
                "error": str(e)
            })
            return []
