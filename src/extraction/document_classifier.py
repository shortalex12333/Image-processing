"""
DocumentClassifier - Classify documents by type using regex patterns.

Supported document types:
- packing_list: Packing slips with order and tracking info
- invoice: Invoices with amounts and due dates
- purchase_order: Purchase orders
- work_order: Work orders
- unknown: Cannot classify
"""

import re
from typing import Dict, List
from src.logger import get_logger

logger = get_logger(__name__)


class DocumentClassifier:
    """
    Classifies documents based on keyword patterns.

    Uses regex patterns to identify document type and calculate
    confidence score based on number of matching indicators.
    """

    def __init__(self):
        """Initialize classifier with regex patterns for each document type."""

        # Packing slip patterns
        self.packing_list_patterns = [
            r"(?i)packing\s+slip",
            r"(?i)packing\s+list",
            r"(?i)shipment\s+#",
            r"(?i)tracking\s*(?:number|#)?:?\s*1Z[A-Z0-9]{16}",  # UPS tracking
            r"(?i)tracking\s*(?:number|#)?:?\s*\d{12,}",  # Generic tracking
            r"(?i)ship\s+to",
            r"(?i)shipped\s+(?:on|date)",
            r"(?i)carrier:",
            r"(?i)items\s+shipped",
        ]

        # Invoice patterns
        self.invoice_patterns = [
            r"(?i)invoice(?:\s+#)?",
            r"(?i)invoice\s+number",
            r"(?i)amount\s+due",
            r"(?i)due\s+date",
            r"(?i)bill\s+to",
            r"(?i)payment\s+terms",
            r"(?i)total\s+amount",
            r"(?i)subtotal",
            r"(?i)tax\s+amount",
            r"\$\d+,?\d*\.\d{2}",  # Dollar amounts
        ]

        # Purchase Order patterns
        self.purchase_order_patterns = [
            r"(?i)purchase\s+order",
            r"(?i)P\.?O\.?\s*#",
            r"(?i)vendor\s+(?:name|#)",
            r"(?i)requested\s+by",
            r"(?i)ship\s+via",
            r"(?i)required\s+date",
            r"(?i)deliver\s+to",
        ]

        # Work Order patterns
        self.work_order_patterns = [
            r"(?i)work\s+order",
            r"(?i)W\.?O\.?\s*#",
            r"(?i)task\s+description",
            r"(?i)assigned\s+to",
            r"(?i)equipment\s+(?:id|#)",
            r"(?i)priority\s*:",
            r"(?i)status\s*:",
            r"(?i)completed\s+by",
        ]

        logger.info("DocumentClassifier initialized with pattern matching")

    def classify(self, text: str) -> Dict[str, any]:
        """
        Classify document based on text content.

        Args:
            text: OCR-extracted text from document

        Returns:
            Dict with:
                - type: Document type (packing_list, invoice, purchase_order, work_order, unknown)
                - confidence: Confidence score (0.0 to 1.0)
                - matched_patterns: List of patterns that matched
        """
        if not text or len(text.strip()) < 10:
            return {
                "type": "unknown",
                "confidence": 0.0,
                "matched_patterns": []
            }

        # Count pattern matches for each type
        scores = {
            "packing_list": self._count_matches(text, self.packing_list_patterns),
            "invoice": self._count_matches(text, self.invoice_patterns),
            "purchase_order": self._count_matches(text, self.purchase_order_patterns),
            "work_order": self._count_matches(text, self.work_order_patterns),
        }

        # Get matched patterns for winning type
        matched_patterns = []
        if max(scores.values()) > 0:
            winning_type = max(scores, key=scores.get)
            matched_patterns = self._get_matched_patterns(text, winning_type)

        # Determine winner
        max_score = max(scores.values())

        if max_score == 0:
            doc_type = "unknown"
            confidence = 0.0
        else:
            doc_type = max(scores, key=scores.get)

            # Calculate confidence based on pattern matches
            # Require at least 2 matches for high confidence
            if max_score >= 3:
                confidence = 0.9  # Very confident
            elif max_score == 2:
                confidence = 0.75  # Fairly confident
            elif max_score == 1:
                confidence = 0.5  # Low confidence
            else:
                confidence = 0.0

        logger.info(
            "Document classified",
            extra={
                "type": doc_type,
                "confidence": confidence,
                "scores": scores,
                "text_length": len(text)
            }
        )

        return {
            "type": doc_type,
            "confidence": confidence,
            "matched_patterns": matched_patterns
        }

    def _count_matches(self, text: str, patterns: List[str]) -> int:
        """Count how many patterns match in the text."""
        count = 0
        for pattern in patterns:
            if re.search(pattern, text):
                count += 1
        return count

    def _get_matched_patterns(self, text: str, doc_type: str) -> List[str]:
        """Get list of patterns that matched for a document type."""
        patterns_map = {
            "packing_list": self.packing_list_patterns,
            "invoice": self.invoice_patterns,
            "purchase_order": self.purchase_order_patterns,
            "work_order": self.work_order_patterns,
        }

        patterns = patterns_map.get(doc_type, [])
        matched = []

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                matched.append(match.group(0))

        return matched
