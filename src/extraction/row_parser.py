"""
Row parser for extracting structured data from OCR text using regex patterns.
Deterministic approach - $0 cost.
"""

import re
from typing import Any

from src.logger import get_logger

logger = get_logger(__name__)


class RowParser:
    """Parses rows from packing slip OCR text using regex patterns."""

    # Common unit abbreviations
    UNITS = ["ea", "box", "case", "pcs", "lbs", "kg", "g", "ft", "m", "gal", "L", "each"]

    # Regex patterns for different packing slip formats
    PATTERNS = [
        # Format 1: Qty | Unit | Description | Part#
        # Example: "12 ea MTU Oil Filter MTU-OF-4568"
        {
            "name": "qty_unit_desc_part",
            "regex": r'(\d+\.?\d*)\s+(ea|box|case|pcs|lbs|kg|g|ft|m|gal|L|each)\s+([A-Za-z0-9\s,\.\/\-\(\)]+?)\s+([A-Z0-9\-]{3,20})\s*$',
            "groups": {"quantity": 1, "unit": 2, "description": 3, "part_number": 4}
        },

        # Format 2: Part# - Description (Qty Unit)
        # Example: "MTU-OF-4568 - MTU Oil Filter (12 ea)"
        {
            "name": "part_desc_qty",
            "regex": r'([A-Z0-9\-]{3,20})\s*-\s*([A-Za-z0-9\s,\.\/\-\(\)]+?)\s*\((\d+\.?\d*)\s+(ea|box|case|pcs|lbs|kg|g|ft|m|gal|L|each)\)',
            "groups": {"part_number": 1, "description": 2, "quantity": 3, "unit": 4}
        },

        # Format 3: Qty Description Part# (unit implied)
        # Example: "12 MTU Oil Filter MTU-OF-4568"
        {
            "name": "qty_desc_part",
            "regex": r'(\d+\.?\d*)\s+([A-Za-z0-9\s,\.\/\-\(\)]+?)\s+([A-Z0-9\-]{3,20})\s*$',
            "groups": {"quantity": 1, "description": 2, "part_number": 3, "unit": None}
        },

        # Format 4: Description only with quantity embedded
        # Example: "MTU Oil Filter - 12 pieces"
        {
            "name": "desc_with_qty",
            "regex": r'([A-Za-z0-9\s,\.\/\-\(\)]+?)\s*[-:]\s*(\d+\.?\d*)\s+(ea|box|case|pcs|pieces|lbs|kg|g|ft|m|gal|L|each)',
            "groups": {"description": 1, "quantity": 2, "unit": 3, "part_number": None}
        },

        # Format 5: Simple tabular (tab-separated or multi-space)
        # Example: "12    ea    MTU Oil Filter    MTU-OF-4568"
        {
            "name": "tabular",
            "regex": r'(\d+\.?\d*)\s{2,}(ea|box|case|pcs|lbs|kg|g|ft|m|gal|L|each)\s{2,}([A-Za-z0-9\s,\.\/\-\(\)]+?)\s{2,}([A-Z0-9\-]{3,})',
            "groups": {"quantity": 1, "unit": 2, "description": 3, "part_number": 4}
        },

        # Format 6: Minimal - just quantity and description
        # Example: "12 MTU Oil Filter"
        {
            "name": "qty_desc_only",
            "regex": r'^(\d+\.?\d*)\s+([A-Za-z0-9\s,\.\/\-\(\)]{10,})\s*$',
            "groups": {"quantity": 1, "description": 2, "unit": None, "part_number": None}
        }
    ]

    def parse_lines(self, ocr_text: str) -> dict:
        """
        Parse OCR text to extract line items.

        Args:
            ocr_text: OCR extracted text

        Returns:
            Parsing result with extracted lines and coverage metrics

        Example:
            >>> parser = RowParser()
            >>> result = parser.parse_lines(ocr_text)
            >>> result
            {
                "lines": [
                    {
                        "line_number": 1,
                        "quantity": 12.0,
                        "unit": "ea",
                        "description": "MTU Oil Filter",
                        "part_number": "MTU-OF-4568",
                        "confidence": "high",
                        "pattern_matched": "qty_unit_desc_part"
                    }
                ],
                "coverage": 0.85,
                "total_text_lines": 20,
                "lines_extracted": 17,
                "method": "regex"
            }
        """
        text_lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]

        if not text_lines:
            return {
                "lines": [],
                "coverage": 0.0,
                "total_text_lines": 0,
                "lines_extracted": 0,
                "method": "regex"
            }

        extracted_lines = []
        line_number = 1

        for text_line in text_lines:
            # Skip header/footer lines
            if self._is_header_or_footer(text_line):
                continue

            # Try each pattern
            parsed = None
            for pattern in self.PATTERNS:
                parsed = self._try_pattern(text_line, pattern)
                if parsed:
                    parsed["line_number"] = line_number
                    parsed["pattern_matched"] = pattern["name"]
                    extracted_lines.append(parsed)
                    line_number += 1
                    break

        # Calculate coverage
        coverage = len(extracted_lines) / len(text_lines) if text_lines else 0.0

        result = {
            "lines": extracted_lines,
            "coverage": coverage,
            "total_text_lines": len(text_lines),
            "lines_extracted": len(extracted_lines),
            "method": "regex"
        }

        logger.info("Row parsing complete", extra={
            "lines_extracted": len(extracted_lines),
            "coverage": coverage,
            "total_lines": len(text_lines)
        })

        return result

    def _try_pattern(self, line: str, pattern: dict) -> dict | None:
        """
        Try to match a line against a pattern.

        Args:
            line: Text line
            pattern: Pattern definition

        Returns:
            Parsed data if match, None otherwise
        """
        match = re.match(pattern["regex"], line, re.IGNORECASE)
        if not match:
            return None

        # Extract groups
        groups = pattern["groups"]
        parsed = {
            "quantity": None,
            "unit": None,
            "description": None,
            "part_number": None,
            "raw_text": line
        }

        for field, group_idx in groups.items():
            if group_idx is not None:
                value = match.group(group_idx)
                if value:
                    parsed[field] = value.strip()

        # Validate extraction
        if not self._validate_extraction(parsed):
            return None

        # Normalize data
        parsed = self._normalize(parsed)

        # Assign confidence
        parsed["confidence"] = self._calculate_confidence(parsed)

        return parsed

    def _validate_extraction(self, parsed: dict) -> bool:
        """
        Validate extracted data has required fields.

        Args:
            parsed: Parsed data

        Returns:
            True if valid, False otherwise
        """
        # Must have quantity and description at minimum
        if not parsed.get("quantity") or not parsed.get("description"):
            return False

        # Description must be reasonable length
        desc = parsed.get("description", "")
        if len(desc) < 5 or len(desc) > 500:
            return False

        return True

    def _normalize(self, parsed: dict) -> dict:
        """
        Normalize parsed data.

        Args:
            parsed: Parsed data

        Returns:
            Normalized data
        """
        # Convert quantity to float
        if parsed.get("quantity"):
            try:
                parsed["quantity"] = float(parsed["quantity"])
            except ValueError:
                parsed["quantity"] = None

        # Normalize unit
        if parsed.get("unit"):
            unit = parsed["unit"].lower()
            # Map common variations
            unit_map = {
                "each": "ea",
                "pieces": "pcs",
                "pc": "pcs"
            }
            parsed["unit"] = unit_map.get(unit, unit)

        # If no unit, default to "ea"
        if not parsed.get("unit"):
            parsed["unit"] = "ea"

        # Clean description
        if parsed.get("description"):
            parsed["description"] = self._clean_description(parsed["description"])

        # Clean part number
        if parsed.get("part_number"):
            parsed["part_number"] = parsed["part_number"].strip().upper()

        return parsed

    def _clean_description(self, description: str) -> str:
        """
        Clean and normalize description text.

        Args:
            description: Raw description

        Returns:
            Cleaned description
        """
        # Remove extra whitespace
        description = re.sub(r'\s+', ' ', description)

        # Remove trailing punctuation
        description = description.rstrip('.,;:-')

        # Capitalize appropriately (simple title case)
        # Preserve all-caps acronyms
        words = description.split()
        cleaned_words = []
        for word in words:
            if word.isupper() and len(word) > 1:
                cleaned_words.append(word)  # Keep acronyms
            else:
                cleaned_words.append(word.capitalize())

        return ' '.join(cleaned_words)

    def _calculate_confidence(self, parsed: dict) -> str:
        """
        Calculate confidence in parsed data.

        Args:
            parsed: Parsed data

        Returns:
            Confidence level: "high", "medium", "low"
        """
        score = 0

        # Has quantity
        if parsed.get("quantity") and parsed["quantity"] > 0:
            score += 1

        # Has unit
        if parsed.get("unit"):
            score += 1

        # Has description (good length)
        desc = parsed.get("description", "")
        if 10 <= len(desc) <= 200:
            score += 1

        # Has part number
        if parsed.get("part_number"):
            score += 2  # Part number is very valuable

        # Map score to confidence
        if score >= 4:
            return "high"
        elif score >= 2:
            return "medium"
        else:
            return "low"

    def _is_header_or_footer(self, line: str) -> bool:
        """
        Check if line is a header/footer (should be skipped).

        Args:
            line: Text line

        Returns:
            True if header/footer, False otherwise
        """
        line_lower = line.lower()

        # Common header keywords
        header_keywords = [
            "packing slip", "packing list", "invoice", "order", "date",
            "item", "quantity", "description", "part number", "unit price",
            "ship to", "bill to", "customer", "po number", "page"
        ]

        for keyword in header_keywords:
            if keyword in line_lower:
                return True

        # Footer patterns (page numbers, totals)
        if re.match(r'^\s*(page|total|subtotal)\s+\d+', line_lower):
            return True

        return False
