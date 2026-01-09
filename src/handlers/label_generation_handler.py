"""
Label generation handler - Section E: Label PDF Generation.
Handles QR code and PDF label generation for parts and equipment.
"""

from uuid import UUID

from src.label_generation import QRGenerator, PDFLabelGenerator
from src.database import get_supabase_service
from src.logger import get_logger

logger = get_logger(__name__)


class LabelGenerationHandler:
    """Handles label generation requests."""

    def __init__(self):
        self.supabase = get_supabase_service()
        self.qr_generator = QRGenerator()
        self.pdf_generator = PDFLabelGenerator()

    async def generate_part_labels_pdf(
        self,
        yacht_id: UUID,
        part_ids: list[UUID] | None = None,
        location: str | None = None,
        category: str | None = None
    ) -> bytes:
        """
        Generate PDF with part labels.

        Args:
            yacht_id: Yacht UUID
            part_ids: Specific part UUIDs (if None, generate for all parts)
            location: Filter by location
            category: Filter by category

        Returns:
            PDF bytes

        Example:
            # Generate labels for specific parts
            pdf = await handler.generate_part_labels_pdf(
                yacht_id, part_ids=[uuid1, uuid2]
            )

            # Generate labels for all parts in location
            pdf = await handler.generate_part_labels_pdf(
                yacht_id, location="Engine Room"
            )
        """
        # Build query
        query = self.supabase.table("pms_parts") \
            .select("part_id, part_number, name, manufacturer, location, quantity_on_hand, unit") \
            .eq("yacht_id", str(yacht_id))

        if part_ids:
            query = query.in_("part_id", [str(pid) for pid in part_ids])

        if location:
            query = query.eq("location", location)

        if category:
            query = query.eq("category", category)

        # Execute query
        result = query.execute()

        if not result.data:
            raise ValueError("No parts found matching criteria")

        logger.info("Generating part labels PDF", extra={
            "yacht_id": str(yacht_id),
            "part_count": len(result.data),
            "location": location,
            "category": category
        })

        # Generate PDF
        pdf_bytes = self.pdf_generator.generate_part_labels(result.data)

        return pdf_bytes

    async def generate_equipment_labels_pdf(
        self,
        yacht_id: UUID,
        equipment_ids: list[UUID] | None = None,
        location: str | None = None,
        category: str | None = None
    ) -> bytes:
        """
        Generate PDF with equipment labels.

        Args:
            yacht_id: Yacht UUID
            equipment_ids: Specific equipment UUIDs (if None, generate for all)
            location: Filter by location
            category: Filter by category

        Returns:
            PDF bytes
        """
        # Build query
        query = self.supabase.table("pms_equipment") \
            .select("equipment_id, code, name, manufacturer, model, location") \
            .eq("yacht_id", str(yacht_id))

        if equipment_ids:
            query = query.in_("equipment_id", [str(eid) for eid in equipment_ids])

        if location:
            query = query.eq("location", location)

        if category:
            query = query.eq("category", category)

        # Execute query
        result = query.execute()

        if not result.data:
            raise ValueError("No equipment found matching criteria")

        logger.info("Generating equipment labels PDF", extra={
            "yacht_id": str(yacht_id),
            "equipment_count": len(result.data),
            "location": location,
            "category": category
        })

        # Generate PDF
        pdf_bytes = self.pdf_generator.generate_equipment_labels(result.data)

        return pdf_bytes

    async def generate_single_part_label(
        self,
        yacht_id: UUID,
        part_id: UUID
    ) -> bytes:
        """
        Generate PDF with single part label (for quick printing).

        Args:
            yacht_id: Yacht UUID
            part_id: Part UUID

        Returns:
            PDF bytes
        """
        # Fetch part
        result = self.supabase.table("pms_parts") \
            .select("part_id, part_number, name, manufacturer, location, quantity_on_hand, unit") \
            .eq("yacht_id", str(yacht_id)) \
            .eq("part_id", str(part_id)) \
            .single() \
            .execute()

        if not result.data:
            raise ValueError(f"Part not found: {part_id}")

        logger.info("Generating single part label", extra={
            "yacht_id": str(yacht_id),
            "part_id": str(part_id),
            "part_number": result.data["part_number"]
        })

        # Generate PDF
        pdf_bytes = self.pdf_generator.generate_single_part_label(
            part_id=result.data["part_id"],
            part_number=result.data["part_number"],
            name=result.data["name"],
            manufacturer=result.data.get("manufacturer"),
            location=result.data.get("location"),
            quantity_on_hand=result.data.get("quantity_on_hand"),
            unit=result.data.get("unit", "ea")
        )

        return pdf_bytes

    async def generate_single_equipment_label(
        self,
        yacht_id: UUID,
        equipment_id: UUID
    ) -> bytes:
        """
        Generate PDF with single equipment label (for quick printing).

        Args:
            yacht_id: Yacht UUID
            equipment_id: Equipment UUID

        Returns:
            PDF bytes
        """
        # Fetch equipment
        result = self.supabase.table("pms_equipment") \
            .select("equipment_id, code, name, manufacturer, model, location") \
            .eq("yacht_id", str(yacht_id)) \
            .eq("equipment_id", str(equipment_id)) \
            .single() \
            .execute()

        if not result.data:
            raise ValueError(f"Equipment not found: {equipment_id}")

        logger.info("Generating single equipment label", extra={
            "yacht_id": str(yacht_id),
            "equipment_id": str(equipment_id),
            "code": result.data["code"]
        })

        # Generate PDF
        pdf_bytes = self.pdf_generator.generate_single_equipment_label(
            equipment_id=result.data["equipment_id"],
            code=result.data["code"],
            name=result.data["name"],
            manufacturer=result.data.get("manufacturer"),
            model=result.data.get("model"),
            location=result.data.get("location")
        )

        return pdf_bytes

    async def generate_part_qr_only(
        self,
        part_id: UUID,
        part_number: str
    ) -> bytes:
        """
        Generate QR code only (PNG) for a part.

        Args:
            part_id: Part UUID
            part_number: Part number

        Returns:
            PNG bytes
        """
        logger.info("Generating part QR code", extra={
            "part_id": str(part_id),
            "part_number": part_number
        })

        return self.qr_generator.generate_part_qr(part_id, part_number)

    async def generate_equipment_qr_only(
        self,
        equipment_id: UUID,
        equipment_code: str
    ) -> bytes:
        """
        Generate QR code only (PNG) for equipment.

        Args:
            equipment_id: Equipment UUID
            equipment_code: Equipment code

        Returns:
            PNG bytes
        """
        logger.info("Generating equipment QR code", extra={
            "equipment_id": str(equipment_id),
            "equipment_code": equipment_code
        })

        return self.qr_generator.generate_equipment_qr(equipment_id, equipment_code)
