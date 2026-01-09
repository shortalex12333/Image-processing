"""
PDF label generation with QR codes.
Creates printable labels for parts and equipment.
"""

import io
from uuid import UUID
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch, mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from src.label_generation.qr_generator import QRGenerator
from src.logger import get_logger

logger = get_logger(__name__)


class PDFLabelGenerator:
    """Generates PDF labels with QR codes."""

    # Label dimensions (Avery 5160 compatible - 3 cols x 10 rows)
    LABEL_WIDTH = 2.625 * inch
    LABEL_HEIGHT = 1.0 * inch
    LABELS_PER_ROW = 3
    LABELS_PER_COL = 10
    LEFT_MARGIN = 0.1875 * inch
    TOP_MARGIN = 0.5 * inch
    HORIZONTAL_GAP = 0.125 * inch
    VERTICAL_GAP = 0.0 * inch

    def __init__(self):
        self.qr_generator = QRGenerator()

    def generate_part_labels(
        self,
        parts: list[dict],
        page_size: tuple = letter
    ) -> bytes:
        """
        Generate PDF with part labels.

        Args:
            parts: List of part dicts with fields:
                - part_id: UUID
                - part_number: str
                - name: str
                - location: str (optional)
                - quantity_on_hand: float (optional)
            page_size: PDF page size (letter or A4)

        Returns:
            PDF bytes

        Label layout:
        +------------------------+
        |  [QR]   MTU-OF-4568   |
        |         Oil Filter     |
        |         MTU            |
        |         Loc: E-102     |
        |         Qty: 12        |
        +------------------------+
        """
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=page_size)

        label_index = 0
        for part in parts:
            # Calculate position
            row = label_index // self.LABELS_PER_ROW
            col = label_index % self.LABELS_PER_ROW

            # Check if we need a new page
            if row >= self.LABELS_PER_COL:
                c.showPage()
                label_index = 0
                row = 0
                col = 0

            x = self.LEFT_MARGIN + col * (self.LABEL_WIDTH + self.HORIZONTAL_GAP)
            y = page_size[1] - self.TOP_MARGIN - (row + 1) * (self.LABEL_HEIGHT + self.VERTICAL_GAP)

            # Draw label
            self._draw_part_label(c, part, x, y)

            label_index += 1

        c.save()
        buffer.seek(0)

        logger.info("Part labels PDF generated", extra={
            "total_parts": len(parts),
            "pages": (label_index // (self.LABELS_PER_ROW * self.LABELS_PER_COL)) + 1
        })

        return buffer.getvalue()

    def generate_equipment_labels(
        self,
        equipment: list[dict],
        page_size: tuple = letter
    ) -> bytes:
        """
        Generate PDF with equipment labels.

        Args:
            equipment: List of equipment dicts with fields:
                - equipment_id: UUID
                - code: str
                - name: str
                - manufacturer: str (optional)
                - model: str (optional)
            page_size: PDF page size (letter or A4)

        Returns:
            PDF bytes

        Label layout:
        +------------------------+
        |  [QR]   ME-S-001      |
        |         Main Engine    |
        |         Starboard      |
        |         MTU 16V4000    |
        +------------------------+
        """
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=page_size)

        label_index = 0
        for equip in equipment:
            # Calculate position
            row = label_index // self.LABELS_PER_ROW
            col = label_index % self.LABELS_PER_ROW

            # Check if we need a new page
            if row >= self.LABELS_PER_COL:
                c.showPage()
                label_index = 0
                row = 0
                col = 0

            x = self.LEFT_MARGIN + col * (self.LABEL_WIDTH + self.HORIZONTAL_GAP)
            y = page_size[1] - self.TOP_MARGIN - (row + 1) * (self.LABEL_HEIGHT + self.VERTICAL_GAP)

            # Draw label
            self._draw_equipment_label(c, equip, x, y)

            label_index += 1

        c.save()
        buffer.seek(0)

        logger.info("Equipment labels PDF generated", extra={
            "total_equipment": len(equipment),
            "pages": (label_index // (self.LABELS_PER_ROW * self.LABELS_PER_COL)) + 1
        })

        return buffer.getvalue()

    def generate_location_labels(
        self,
        locations: list[dict],
        page_size: tuple = letter
    ) -> bytes:
        """
        Generate PDF with location labels.

        Args:
            locations: List of location dicts with fields:
                - location_id: str
                - name: str
                - description: str (optional)
                - zone: str (optional)
            page_size: PDF page size (letter or A4)

        Returns:
            PDF bytes

        Label layout:
        +------------------------+
        |  [QR]   E-102         |
        |         Engine Room    |
        |         Starboard Side |
        |         Lower Deck     |
        +------------------------+
        """
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=page_size)

        label_index = 0
        for location in locations:
            # Calculate position
            row = label_index // self.LABELS_PER_ROW
            col = label_index % self.LABELS_PER_ROW

            # Check if we need a new page
            if row >= self.LABELS_PER_COL:
                c.showPage()
                label_index = 0
                row = 0
                col = 0

            x = self.LEFT_MARGIN + col * (self.LABEL_WIDTH + self.HORIZONTAL_GAP)
            y = page_size[1] - self.TOP_MARGIN - (row + 1) * (self.LABEL_HEIGHT + self.VERTICAL_GAP)

            # Draw label
            self._draw_location_label(c, location, x, y)

            label_index += 1

        c.save()
        buffer.seek(0)

        logger.info("Location labels PDF generated", extra={
            "total_locations": len(locations),
            "pages": (label_index // (self.LABELS_PER_ROW * self.LABELS_PER_COL)) + 1
        })

        return buffer.getvalue()

    def _draw_part_label(self, c: canvas.Canvas, part: dict, x: float, y: float):
        """Draw a single part label."""
        # Generate QR code
        qr_bytes = self.qr_generator.generate_part_qr(
            part["part_id"],
            part["part_number"],
            size=60
        )
        qr_image = ImageReader(io.BytesIO(qr_bytes))

        # Draw QR code (left side)
        qr_size = 0.6 * inch
        c.drawImage(qr_image, x + 0.05 * inch, y + 0.2 * inch, qr_size, qr_size)

        # Text area (right side)
        text_x = x + qr_size + 0.15 * inch
        text_y = y + 0.8 * inch

        # Part number (bold, larger)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(text_x, text_y, self._truncate(part["part_number"], 15))

        # Part name
        c.setFont("Helvetica", 8)
        text_y -= 0.15 * inch
        c.drawString(text_x, text_y, self._truncate(part.get("name", ""), 20))

        # Manufacturer
        if part.get("manufacturer"):
            text_y -= 0.12 * inch
            c.setFont("Helvetica", 7)
            c.drawString(text_x, text_y, self._truncate(part["manufacturer"], 20))

        # Location
        if part.get("location"):
            text_y -= 0.12 * inch
            c.setFont("Helvetica", 7)
            c.drawString(text_x, text_y, f"Loc: {self._truncate(part['location'], 15)}")

        # Quantity
        if part.get("quantity_on_hand") is not None:
            text_y -= 0.12 * inch
            c.setFont("Helvetica", 7)
            qty = part["quantity_on_hand"]
            unit = part.get("unit", "ea")
            c.drawString(text_x, text_y, f"Qty: {qty} {unit}")

        # Border (optional, for debugging)
        # c.rect(x, y, self.LABEL_WIDTH, self.LABEL_HEIGHT)

    def _draw_equipment_label(self, c: canvas.Canvas, equipment: dict, x: float, y: float):
        """Draw a single equipment label."""
        # Generate QR code
        qr_bytes = self.qr_generator.generate_equipment_qr(
            equipment["equipment_id"],
            equipment["code"],
            size=60
        )
        qr_image = ImageReader(io.BytesIO(qr_bytes))

        # Draw QR code (left side)
        qr_size = 0.6 * inch
        c.drawImage(qr_image, x + 0.05 * inch, y + 0.2 * inch, qr_size, qr_size)

        # Text area (right side)
        text_x = x + qr_size + 0.15 * inch
        text_y = y + 0.8 * inch

        # Equipment code (bold, larger)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(text_x, text_y, self._truncate(equipment["code"], 15))

        # Equipment name
        c.setFont("Helvetica", 8)
        text_y -= 0.15 * inch
        c.drawString(text_x, text_y, self._truncate(equipment.get("name", ""), 20))

        # Manufacturer/Model
        if equipment.get("manufacturer") and equipment.get("model"):
            text_y -= 0.12 * inch
            c.setFont("Helvetica", 7)
            mfr_model = f"{equipment['manufacturer']} {equipment['model']}"
            c.drawString(text_x, text_y, self._truncate(mfr_model, 20))
        elif equipment.get("manufacturer"):
            text_y -= 0.12 * inch
            c.setFont("Helvetica", 7)
            c.drawString(text_x, text_y, self._truncate(equipment["manufacturer"], 20))

        # Location
        if equipment.get("location"):
            text_y -= 0.12 * inch
            c.setFont("Helvetica", 7)
            c.drawString(text_x, text_y, self._truncate(equipment["location"], 20))

    def _draw_location_label(self, c: canvas.Canvas, location: dict, x: float, y: float):
        """Draw a single location label."""
        # Generate QR code
        qr_bytes = self.qr_generator.generate_location_qr(
            location["location_id"],
            location["name"],
            size=60
        )
        qr_image = ImageReader(io.BytesIO(qr_bytes))

        # Draw QR code (left side)
        qr_size = 0.6 * inch
        c.drawImage(qr_image, x + 0.05 * inch, y + 0.2 * inch, qr_size, qr_size)

        # Text area (right side)
        text_x = x + qr_size + 0.15 * inch
        text_y = y + 0.8 * inch

        # Location ID (bold, larger)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(text_x, text_y, self._truncate(location["location_id"], 15))

        # Location name
        c.setFont("Helvetica", 8)
        text_y -= 0.15 * inch
        c.drawString(text_x, text_y, self._truncate(location.get("name", ""), 20))

        # Description
        if location.get("description"):
            text_y -= 0.12 * inch
            c.setFont("Helvetica", 7)
            c.drawString(text_x, text_y, self._truncate(location["description"], 20))

        # Zone
        if location.get("zone"):
            text_y -= 0.12 * inch
            c.setFont("Helvetica", 7)
            c.drawString(text_x, text_y, f"Zone: {self._truncate(location['zone'], 15)}")

    def _truncate(self, text: str, max_length: int) -> str:
        """Truncate text to max length."""
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."

    def generate_single_part_label(
        self,
        part_id: UUID,
        part_number: str,
        name: str,
        manufacturer: str | None = None,
        location: str | None = None,
        quantity_on_hand: float | None = None,
        unit: str = "ea"
    ) -> bytes:
        """
        Generate PDF with single part label (for quick printing).

        Args:
            part_id: Part UUID
            part_number: Part number
            name: Part name
            manufacturer: Manufacturer (optional)
            location: Storage location (optional)
            quantity_on_hand: Current stock (optional)
            unit: Unit of measure

        Returns:
            PDF bytes
        """
        part = {
            "part_id": part_id,
            "part_number": part_number,
            "name": name,
            "manufacturer": manufacturer,
            "location": location,
            "quantity_on_hand": quantity_on_hand,
            "unit": unit
        }

        return self.generate_part_labels([part])

    def generate_single_equipment_label(
        self,
        equipment_id: UUID,
        code: str,
        name: str,
        manufacturer: str | None = None,
        model: str | None = None,
        location: str | None = None
    ) -> bytes:
        """
        Generate PDF with single equipment label (for quick printing).

        Args:
            equipment_id: Equipment UUID
            code: Equipment code
            name: Equipment name
            manufacturer: Manufacturer (optional)
            model: Model (optional)
            location: Location (optional)

        Returns:
            PDF bytes
        """
        equipment = {
            "equipment_id": equipment_id,
            "code": code,
            "name": name,
            "manufacturer": manufacturer,
            "model": model,
            "location": location
        }

        return self.generate_equipment_labels([equipment])
