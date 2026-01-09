"""
Table detection in OCR text using heuristics and bounding box analysis.
"""

import re
from typing import Any

from src.logger import get_logger

logger = get_logger(__name__)


class TableDetector:
    """Detects tabular structures in OCR text."""

    def detect_table(self, ocr_result: dict) -> dict:
        """
        Detect if OCR text contains a table structure.

        Args:
            ocr_result: OCR result with text and bounding_boxes

        Returns:
            Detection result with confidence and table metadata

        Example:
            >>> detector = TableDetector()
            >>> result = detector.detect_table(ocr_result)
            >>> result
            {
                "has_table": True,
                "confidence": 0.85,
                "column_count": 4,
                "row_count": 12,
                "columns": [
                    {"index": 0, "x_range": [50, 150], "alignment": "left"},
                    {"index": 1, "x_range": [150, 250], "alignment": "center"}
                ]
            }
        """
        text = ocr_result.get("text", "")
        bounding_boxes = ocr_result.get("bounding_boxes", [])

        # Method 1: Detect using bounding boxes (most reliable)
        if bounding_boxes:
            result = self._detect_from_bounding_boxes(bounding_boxes)
            if result["has_table"]:
                return result

        # Method 2: Detect using text patterns (fallback)
        result = self._detect_from_text_patterns(text)

        return result

    def _detect_from_bounding_boxes(self, bounding_boxes: list[dict]) -> dict:
        """
        Detect table using OCR bounding box coordinates.

        Identifies columns by analyzing x-coordinate alignment of words.

        Args:
            bounding_boxes: List of bounding boxes with coordinates

        Returns:
            Detection result
        """
        if len(bounding_boxes) < 10:  # Need enough words to detect pattern
            return {"has_table": False, "confidence": 0.0}

        # Group words by line (similar y-coordinates)
        lines = self._group_into_lines(bounding_boxes)

        if len(lines) < 3:  # Need at least 3 lines to detect table
            return {"has_table": False, "confidence": 0.0}

        # Detect column boundaries by finding vertical alignment
        columns = self._detect_columns(lines)

        if len(columns) < 2:  # Table needs at least 2 columns
            return {"has_table": False, "confidence": 0.0}

        # Calculate confidence based on alignment consistency
        confidence = self._calculate_alignment_confidence(lines, columns)

        return {
            "has_table": confidence > 0.6,
            "confidence": confidence,
            "column_count": len(columns),
            "row_count": len(lines),
            "columns": columns,
            "detection_method": "bounding_boxes"
        }

    def _group_into_lines(self, boxes: list[dict]) -> list[list[dict]]:
        """
        Group words into lines based on y-coordinate proximity.

        Args:
            boxes: Bounding boxes

        Returns:
            List of lines, where each line is a list of boxes
        """
        if not boxes:
            return []

        # Sort by top coordinate
        sorted_boxes = sorted(boxes, key=lambda b: b["top"])

        lines = []
        current_line = [sorted_boxes[0]]
        line_y = sorted_boxes[0]["top"]

        for box in sorted_boxes[1:]:
            # If y-coordinate is close to current line, add to line
            if abs(box["top"] - line_y) < 20:  # Tolerance: 20 pixels
                current_line.append(box)
            else:
                # Start new line
                lines.append(current_line)
                current_line = [box]
                line_y = box["top"]

        # Add last line
        if current_line:
            lines.append(current_line)

        return lines

    def _detect_columns(self, lines: list[list[dict]]) -> list[dict]:
        """
        Detect column boundaries by finding vertical alignment patterns.

        Args:
            lines: Words grouped into lines

        Returns:
            List of column definitions
        """
        # Collect x-coordinates of all words
        x_coords = []
        for line in lines:
            for box in line:
                x_coords.append(box["left"])

        if not x_coords:
            return []

        # Cluster x-coordinates to find column positions
        x_coords.sort()
        columns = []
        current_cluster = [x_coords[0]]
        cluster_threshold = 50  # Pixels tolerance for same column

        for x in x_coords[1:]:
            if x - current_cluster[-1] < cluster_threshold:
                current_cluster.append(x)
            else:
                # New column found
                avg_x = sum(current_cluster) / len(current_cluster)
                columns.append({
                    "index": len(columns),
                    "x_position": int(avg_x),
                    "sample_count": len(current_cluster)
                })
                current_cluster = [x]

        # Add last cluster
        if current_cluster and len(current_cluster) > 2:  # Need multiple instances
            avg_x = sum(current_cluster) / len(current_cluster)
            columns.append({
                "index": len(columns),
                "x_position": int(avg_x),
                "sample_count": len(current_cluster)
            })

        return columns

    def _calculate_alignment_confidence(self, lines: list[list[dict]], columns: list[dict]) -> float:
        """
        Calculate confidence in table detection based on alignment consistency.

        Args:
            lines: Words grouped into lines
            columns: Detected columns

        Returns:
            Confidence score (0.0 to 1.0)
        """
        if not lines or not columns:
            return 0.0

        # Count how many lines have words aligned to columns
        aligned_lines = 0
        for line in lines:
            has_aligned_word = False
            for box in line:
                # Check if this word aligns with any column
                for col in columns:
                    if abs(box["left"] - col["x_position"]) < 50:
                        has_aligned_word = True
                        break
            if has_aligned_word:
                aligned_lines += 1

        alignment_ratio = aligned_lines / len(lines)

        # Boost confidence if multiple columns detected
        column_bonus = min(len(columns) * 0.1, 0.3)

        return min(alignment_ratio + column_bonus, 1.0)

    def _detect_from_text_patterns(self, text: str) -> dict:
        """
        Detect table using text patterns (fallback method).

        Looks for:
        - Multiple consecutive lines with consistent structure
        - Separator characters (|, tabs)
        - Repeated patterns

        Args:
            text: OCR extracted text

        Returns:
            Detection result
        """
        lines = text.split('\n')

        # Remove empty lines
        lines = [l.strip() for l in lines if l.strip()]

        if len(lines) < 3:
            return {"has_table": False, "confidence": 0.0}

        # Check for explicit table separators
        separator_lines = sum(1 for line in lines if '|' in line or '\t' in line)
        if separator_lines / len(lines) > 0.5:
            return {
                "has_table": True,
                "confidence": 0.8,
                "row_count": len(lines),
                "detection_method": "text_separators"
            }

        # Check for consistent patterns (e.g., number at start of each line)
        pattern_confidence = self._detect_line_patterns(lines)

        return {
            "has_table": pattern_confidence > 0.6,
            "confidence": pattern_confidence,
            "row_count": len(lines),
            "detection_method": "text_patterns"
        }

    def _detect_line_patterns(self, lines: list[str]) -> float:
        """
        Detect if lines follow consistent patterns (e.g., all start with numbers).

        Args:
            lines: Text lines

        Returns:
            Pattern confidence (0.0 to 1.0)
        """
        if not lines:
            return 0.0

        # Pattern 1: Lines start with number (line items often do)
        number_start = sum(1 for line in lines if re.match(r'^\d', line))
        number_confidence = number_start / len(lines)

        # Pattern 2: Lines have similar word count (table rows often do)
        word_counts = [len(line.split()) for line in lines]
        avg_words = sum(word_counts) / len(word_counts)
        word_variance = sum(abs(c - avg_words) for c in word_counts) / len(word_counts)
        consistency_confidence = 1.0 - min(word_variance / avg_words, 1.0) if avg_words > 0 else 0.0

        # Combined confidence
        return (number_confidence + consistency_confidence) / 2
