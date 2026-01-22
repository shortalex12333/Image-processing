"""
EntityExtractor - Extract structured data from OCR text.

Extracts specific entities like order numbers, tracking numbers,
and line items from classified documents.
"""

import re
from typing import Dict, List, Optional
from src.logger import get_logger

logger = get_logger(__name__)


class EntityExtractor:
    """
    Extracts structured entities from OCR text.

    Currently supports:
    - Packing slip entities (order #, tracking #, line items)
    """

    def __init__(self):
        """Initialize entity extractor with regex patterns."""

        # Order number patterns (various formats)
        # Allow flexible whitespace between "Order" and "Number"
        self.order_number_patterns = [
            r"(?i)order\s+number\s*:?\s*(ORD-\d{4}-\d{3})",  # ORD-YYYY-### with "Order Number"
            r"(?i)order\s*(?:number|#)?:?\s*(ORD-\d{4}-\d{3})",  # ORD-YYYY-### flexible
            r"(?i)order\s+number\s*:?\s*([A-Z]{2,4}-\d{4,6})",  # Generic with "Order Number"
            r"(?i)order\s*(?:number|#)?:?\s*([A-Z]{2,4}-\d{4,6})",  # Generic flexible
            r"(?i)order\s*(?:number|#)?:?\s*(\d{6,})",  # Numeric only
        ]

        # Tracking number patterns
        self.tracking_patterns = [
            r"(?i)tracking\s*(?:number|#)?:?\s*(1Z[A-Z0-9]{16})",  # UPS
            r"(?i)tracking\s*(?:number|#)?:?\s*(\d{12,22})",  # Generic numeric
            r"(?i)tracking\s*(?:number|#)?:?\s*([A-Z0-9]{10,})",  # Generic alphanumeric
        ]

        # Line item pattern (quantity + description)
        # Matches: "5 ea 3/4" O2Y Coil Pack-Sweat"
        self.line_item_pattern = r"(?i)^[\s]*(\d+)\s+(?:ea|each|pcs?|units?)\s+(.+?)(?:\n|$)"

        logger.info("EntityExtractor initialized with regex patterns")

    def extract_packing_slip_entities(self, text: str) -> Dict[str, any]:
        """
        Extract entities from packing slip text.

        Args:
            text: OCR-extracted text from packing slip

        Returns:
            Dict with:
                - order_number: Order number (or None)
                - tracking_number: Tracking number (or None)
                - line_items: List of dicts with qty and description
                - extraction_confidence: Confidence score (0.0 to 1.0)
        """
        if not text:
            return {
                "order_number": None,
                "tracking_number": None,
                "line_items": [],
                "extraction_confidence": 0.0
            }

        # Extract order number
        order_number = self._extract_order_number(text)

        # Extract tracking number
        tracking_number = self._extract_tracking_number(text)

        # Extract line items
        line_items = self._extract_line_items(text)

        # Calculate confidence based on what was extracted
        confidence = self._calculate_confidence(order_number, tracking_number, line_items)

        result = {
            "order_number": order_number,
            "tracking_number": tracking_number,
            "line_items": line_items,
            "extraction_confidence": confidence
        }

        logger.info(
            "Extracted packing slip entities",
            extra={
                "order_number": order_number,
                "tracking_number": tracking_number,
                "line_item_count": len(line_items),
                "confidence": confidence
            }
        )

        return result

    def _extract_order_number(self, text: str) -> Optional[str]:
        """Extract order number from text."""
        for pattern in self.order_number_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return None

    def _extract_tracking_number(self, text: str) -> Optional[str]:
        """Extract tracking number from text."""
        for pattern in self.tracking_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return None

    def _extract_line_items(self, text: str) -> List[Dict[str, any]]:
        """Extract line items from text."""
        line_items = []

        # Split text into lines and search for line item pattern
        lines = text.split('\n')

        for line in lines:
            match = re.match(self.line_item_pattern, line)
            if match:
                quantity_str = match.group(1)
                description = match.group(2).strip()

                # Convert quantity to int
                try:
                    quantity = int(quantity_str)
                except ValueError:
                    quantity = 0

                # Only add if description is meaningful (not too short)
                if len(description) > 3:
                    line_items.append({
                        "quantity": quantity,
                        "description": description
                    })

        return line_items

    def _calculate_confidence(
        self,
        order_number: Optional[str],
        tracking_number: Optional[str],
        line_items: List[Dict]
    ) -> float:
        """
        Calculate extraction confidence based on what was found.

        High confidence: All fields extracted
        Medium confidence: Most fields extracted
        Low confidence: Few fields extracted
        """
        score = 0.0

        if order_number:
            score += 0.35
        if tracking_number:
            score += 0.35
        if len(line_items) > 0:
            score += 0.20
            # Bonus for multiple line items
            if len(line_items) > 1:
                score += 0.10

        return min(score, 1.0)  # Cap at 1.0
