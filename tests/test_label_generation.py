"""
Tests for label generation (QR codes and PDF layout).
"""

import pytest
from uuid import uuid4
from io import BytesIO
from PIL import Image

from src.label_generation.qr_generator import QRGenerator
from src.label_generation.pdf_layout import PDFLabelGenerator


class TestQRGenerator:
    """Tests for QR code generation."""

    def test_generate_part_qr(self):
        """Test QR code generation for parts."""
        generator = QRGenerator()

        part_id = uuid4()
        qr_bytes = generator.generate_part_qr(part_id, "MTU-OF-4568")

        assert isinstance(qr_bytes, bytes)
        assert len(qr_bytes) > 0

        # Verify it's a valid PNG
        img = Image.open(BytesIO(qr_bytes))
        assert img.format == "PNG"
        assert img.size == (200, 200)  # Default size

    def test_generate_equipment_qr(self):
        """Test QR code generation for equipment."""
        generator = QRGenerator()

        equipment_id = uuid4()
        qr_bytes = generator.generate_equipment_qr(equipment_id, "ME-S-001")

        assert isinstance(qr_bytes, bytes)
        assert len(qr_bytes) > 0

        # Verify it's a valid PNG
        img = Image.open(BytesIO(qr_bytes))
        assert img.format == "PNG"

    def test_generate_location_qr(self):
        """Test QR code generation for locations."""
        generator = QRGenerator()

        qr_bytes = generator.generate_location_qr("E-102", "Engine Room")

        assert isinstance(qr_bytes, bytes)
        assert len(qr_bytes) > 0

    def test_qr_code_custom_size(self):
        """Test QR code with custom size."""
        generator = QRGenerator()

        part_id = uuid4()
        qr_bytes = generator.generate_part_qr(part_id, "MTU-OF-4568", size=300)

        img = Image.open(BytesIO(qr_bytes))
        assert img.size == (300, 300)

    def test_qr_code_consistency(self):
        """Test that same input produces same QR code."""
        generator = QRGenerator()

        part_id = uuid4()
        qr_bytes1 = generator.generate_part_qr(part_id, "MTU-OF-4568")
        qr_bytes2 = generator.generate_part_qr(part_id, "MTU-OF-4568")

        # Same input should produce identical output
        assert qr_bytes1 == qr_bytes2

    def test_generate_batch_qr_parts(self):
        """Test batch QR generation for parts."""
        generator = QRGenerator()

        items = [
            {"id": uuid4(), "identifier": "MTU-OF-4568"},
            {"id": uuid4(), "identifier": "KOH-AF-9902"},
            {"id": uuid4(), "identifier": "MTU-FF-4569"}
        ]

        qr_codes = generator.generate_batch_qr(items, "part")

        assert len(qr_codes) == 3
        for item_id, qr_bytes in qr_codes.items():
            assert isinstance(qr_bytes, bytes)
            assert len(qr_bytes) > 0


class TestPDFLabelGenerator:
    """Tests for PDF label generation."""

    def test_generate_part_labels(self):
        """Test PDF generation for part labels."""
        generator = PDFLabelGenerator()

        parts = [
            {
                "part_id": uuid4(),
                "part_number": "MTU-OF-4568",
                "name": "MTU Oil Filter",
                "manufacturer": "MTU",
                "location": "Engine Room",
                "quantity_on_hand": 12.0,
                "unit": "ea"
            }
        ]

        pdf_bytes = generator.generate_part_labels(parts)

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes.startswith(b"%PDF")

    def test_generate_equipment_labels(self):
        """Test PDF generation for equipment labels."""
        generator = PDFLabelGenerator()

        equipment = [
            {
                "equipment_id": uuid4(),
                "code": "ME-S-001",
                "name": "Main Engine Starboard",
                "manufacturer": "MTU",
                "model": "16V4000 M93L",
                "location": "Engine Room"
            }
        ]

        pdf_bytes = generator.generate_equipment_labels(equipment)

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes.startswith(b"%PDF")

    def test_generate_location_labels(self):
        """Test PDF generation for location labels."""
        generator = PDFLabelGenerator()

        locations = [
            {
                "location_id": "E-102",
                "name": "Engine Room",
                "description": "Main engine compartment",
                "zone": "Lower Deck"
            }
        ]

        pdf_bytes = generator.generate_location_labels(locations)

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes.startswith(b"%PDF")

    def test_generate_multiple_part_labels(self):
        """Test PDF generation for multiple parts."""
        generator = PDFLabelGenerator()

        parts = [
            {
                "part_id": uuid4(),
                "part_number": f"PART-{i:04d}",
                "name": f"Test Part {i}",
                "manufacturer": "Test Mfg",
                "location": "Storage",
                "quantity_on_hand": float(i * 10),
                "unit": "ea"
            }
            for i in range(1, 11)  # 10 parts
        ]

        pdf_bytes = generator.generate_part_labels(parts)

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0

    def test_generate_single_part_label(self):
        """Test single part label generation."""
        generator = PDFLabelGenerator()

        part_id = uuid4()
        pdf_bytes = generator.generate_single_part_label(
            part_id=part_id,
            part_number="MTU-OF-4568",
            name="MTU Oil Filter",
            manufacturer="MTU",
            location="Engine Room",
            quantity_on_hand=12.0,
            unit="ea"
        )

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes.startswith(b"%PDF")

    def test_generate_single_equipment_label(self):
        """Test single equipment label generation."""
        generator = PDFLabelGenerator()

        equipment_id = uuid4()
        pdf_bytes = generator.generate_single_equipment_label(
            equipment_id=equipment_id,
            code="ME-S-001",
            name="Main Engine Starboard",
            manufacturer="MTU",
            model="16V4000 M93L",
            location="Engine Room"
        )

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes.startswith(b"%PDF")

    def test_truncate_long_text(self):
        """Test text truncation in labels."""
        generator = PDFLabelGenerator()

        long_text = "A" * 100
        truncated = generator._truncate(long_text, 20)

        assert len(truncated) == 20
        assert truncated.endswith("...")

    def test_truncate_short_text(self):
        """Test that short text is not truncated."""
        generator = PDFLabelGenerator()

        short_text = "Short"
        result = generator._truncate(short_text, 20)

        assert result == short_text

    def test_multiple_pages(self):
        """Test PDF generation spanning multiple pages."""
        generator = PDFLabelGenerator()

        # Generate more than 30 labels (more than one page)
        parts = [
            {
                "part_id": uuid4(),
                "part_number": f"PART-{i:04d}",
                "name": f"Test Part {i}",
                "manufacturer": "Test",
                "quantity_on_hand": 10.0,
                "unit": "ea"
            }
            for i in range(1, 35)  # 34 parts (more than 1 page)
        ]

        pdf_bytes = generator.generate_part_labels(parts)

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        # PDF should be larger for multiple pages
        assert len(pdf_bytes) > 5000
