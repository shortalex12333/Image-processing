"""
PDF text extraction using pdfplumber.
Extracts embedded text from PDFs (no OCR needed if text is selectable).
"""

import io
from typing import Any

import pdfplumber

from src.logger import get_logger

logger = get_logger(__name__)


class PDFExtractor:
    """Extracts text from PDF files."""

    async def extract_text(self, pdf_bytes: bytes) -> dict:
        """
        Extract text from PDF.

        Args:
            pdf_bytes: PDF file bytes

        Returns:
            Extraction result with text and metadata

        Example:
            >>> extractor = PDFExtractor()
            >>> result = await extractor.extract_text(pdf_bytes)
            >>> result
            {
                "text": "Page 1 text\n\nPage 2 text...",
                "page_count": 2,
                "pages": [
                    {"page_number": 1, "text": "Page 1 text", "has_text": True},
                    {"page_number": 2, "text": "Page 2 text", "has_text": True}
                ],
                "method": "pdfplumber"
            }
        """
        try:
            pdf_file = io.BytesIO(pdf_bytes)
            pages_data = []
            all_text = []

            with pdfplumber.open(pdf_file) as pdf:
                for i, page in enumerate(pdf.pages, start=1):
                    page_text = page.extract_text() or ""
                    has_text = bool(page_text.strip())

                    pages_data.append({
                        "page_number": i,
                        "text": page_text,
                        "has_text": has_text,
                        "char_count": len(page_text)
                    })

                    if has_text:
                        all_text.append(page_text)

            combined_text = "\n\n".join(all_text)

            result = {
                "text": combined_text,
                "page_count": len(pdf.pages),
                "pages": pages_data,
                "word_count": len(combined_text.split()),
                "has_embedded_text": any(p["has_text"] for p in pages_data),
                "method": "pdfplumber"
            }

            logger.info("PDF text extracted", extra={
                "page_count": result["page_count"],
                "word_count": result["word_count"],
                "has_embedded_text": result["has_embedded_text"]
            })

            return result

        except Exception as e:
            logger.error("PDF extraction failed", extra={"error": str(e)}, exc_info=True)
            raise

    async def extract_page(self, pdf_bytes: bytes, page_number: int) -> dict:
        """
        Extract text from a specific PDF page.

        Args:
            pdf_bytes: PDF file bytes
            page_number: Page number (1-indexed)

        Returns:
            Page text extraction result
        """
        try:
            pdf_file = io.BytesIO(pdf_bytes)

            with pdfplumber.open(pdf_file) as pdf:
                if page_number < 1 or page_number > len(pdf.pages):
                    raise ValueError(f"Page {page_number} out of range (1-{len(pdf.pages)})")

                page = pdf.pages[page_number - 1]  # Convert to 0-indexed
                page_text = page.extract_text() or ""

                return {
                    "page_number": page_number,
                    "text": page_text,
                    "has_text": bool(page_text.strip()),
                    "word_count": len(page_text.split()),
                    "method": "pdfplumber"
                }

        except Exception as e:
            logger.error("PDF page extraction failed", extra={
                "page_number": page_number,
                "error": str(e)
            }, exc_info=True)
            raise

    async def extract_tables(self, pdf_bytes: bytes) -> dict:
        """
        Extract tables from PDF.

        Args:
            pdf_bytes: PDF file bytes

        Returns:
            Tables data

        Note:
            This is useful for structured packing slips with clear table layouts.
        """
        try:
            pdf_file = io.BytesIO(pdf_bytes)
            all_tables = []

            with pdfplumber.open(pdf_file) as pdf:
                for i, page in enumerate(pdf.pages, start=1):
                    tables = page.extract_tables()

                    for table_idx, table in enumerate(tables):
                        all_tables.append({
                            "page_number": i,
                            "table_number": table_idx + 1,
                            "rows": table,
                            "row_count": len(table),
                            "column_count": len(table[0]) if table else 0
                        })

            logger.info("PDF tables extracted", extra={
                "table_count": len(all_tables)
            })

            return {
                "tables": all_tables,
                "table_count": len(all_tables),
                "method": "pdfplumber"
            }

        except Exception as e:
            logger.error("PDF table extraction failed", extra={"error": str(e)}, exc_info=True)
            raise
