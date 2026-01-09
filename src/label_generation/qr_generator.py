"""
QR code generation for part and equipment labels.
"""

import io
from uuid import UUID
import qrcode
from qrcode.image.pil import PilImage
from PIL import Image

from src.config import settings
from src.logger import get_logger

logger = get_logger(__name__)


class QRGenerator:
    """Generates QR codes for parts and equipment."""

    def __init__(self):
        self.base_url = settings.render_service_url or "https://cloud-pms.example.com"

    def generate_part_qr(
        self,
        part_id: UUID,
        part_number: str,
        size: int = 200,
        border: int = 2
    ) -> bytes:
        """
        Generate QR code for a part.

        Args:
            part_id: Part UUID
            part_number: Part number (for display)
            size: QR code size in pixels
            border: Border size in QR modules

        Returns:
            PNG image bytes

        QR code contains URL: https://cloud-pms.example.com/parts/{part_id}
        """
        url = f"{self.base_url}/parts/{part_id}"

        logger.info("Generating part QR code", extra={
            "part_id": str(part_id),
            "part_number": part_number,
            "url": url
        })

        return self._generate_qr_code(url, size, border)

    def generate_equipment_qr(
        self,
        equipment_id: UUID,
        equipment_code: str,
        size: int = 200,
        border: int = 2
    ) -> bytes:
        """
        Generate QR code for equipment.

        Args:
            equipment_id: Equipment UUID
            equipment_code: Equipment code (for display)
            size: QR code size in pixels
            border: Border size in QR modules

        Returns:
            PNG image bytes

        QR code contains URL: https://cloud-pms.example.com/equipment/{equipment_id}
        """
        url = f"{self.base_url}/equipment/{equipment_id}"

        logger.info("Generating equipment QR code", extra={
            "equipment_id": str(equipment_id),
            "equipment_code": equipment_code,
            "url": url
        })

        return self._generate_qr_code(url, size, border)

    def generate_location_qr(
        self,
        location_id: str,
        location_name: str,
        size: int = 200,
        border: int = 2
    ) -> bytes:
        """
        Generate QR code for storage location.

        Args:
            location_id: Location identifier
            location_name: Location name (for display)
            size: QR code size in pixels
            border: Border size in QR modules

        Returns:
            PNG image bytes

        QR code contains URL: https://cloud-pms.example.com/locations/{location_id}
        """
        url = f"{self.base_url}/locations/{location_id}"

        logger.info("Generating location QR code", extra={
            "location_id": location_id,
            "location_name": location_name,
            "url": url
        })

        return self._generate_qr_code(url, size, border)

    def _generate_qr_code(
        self,
        data: str,
        size: int = 200,
        border: int = 2
    ) -> bytes:
        """
        Generate QR code from data string.

        Args:
            data: Data to encode (typically a URL)
            size: QR code size in pixels
            border: Border size in QR modules

        Returns:
            PNG image bytes
        """
        # Create QR code
        qr = qrcode.QRCode(
            version=None,  # Auto-determine version
            error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction (30%)
            box_size=10,  # Size of each box in pixels
            border=border  # Border size in boxes
        )

        qr.add_data(data)
        qr.make(fit=True)

        # Generate image
        img: PilImage = qr.make_image(fill_color="black", back_color="white")

        # Resize to desired size
        img = img.resize((size, size), Image.Resampling.LANCZOS)

        # Convert to bytes
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return buffer.getvalue()

    def generate_batch_qr(
        self,
        items: list[dict],
        item_type: str = "part"
    ) -> dict[str, bytes]:
        """
        Generate QR codes for multiple items.

        Args:
            items: List of item dicts with id and identifier fields
            item_type: Type of items ("part", "equipment", "location")

        Returns:
            Dict mapping item_id to QR code PNG bytes

        Example:
            >>> items = [
            ...     {"id": uuid1, "identifier": "MTU-OF-4568"},
            ...     {"id": uuid2, "identifier": "KOH-AF-9902"}
            ... ]
            >>> qr_codes = generator.generate_batch_qr(items, "part")
            >>> qr_codes[str(uuid1)]  # PNG bytes for first part
        """
        qr_codes = {}

        for item in items:
            item_id = item["id"]
            identifier = item.get("identifier", str(item_id))

            try:
                if item_type == "part":
                    qr_code = self.generate_part_qr(item_id, identifier)
                elif item_type == "equipment":
                    qr_code = self.generate_equipment_qr(item_id, identifier)
                elif item_type == "location":
                    qr_code = self.generate_location_qr(identifier, identifier)
                else:
                    logger.warning(f"Unknown item type: {item_type}")
                    continue

                qr_codes[str(item_id)] = qr_code

            except Exception as e:
                logger.error("Failed to generate QR code", extra={
                    "item_id": str(item_id),
                    "item_type": item_type,
                    "error": str(e)
                })
                continue

        logger.info("Batch QR generation complete", extra={
            "item_type": item_type,
            "total_items": len(items),
            "successful": len(qr_codes),
            "failed": len(items) - len(qr_codes)
        })

        return qr_codes
