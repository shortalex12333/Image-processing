"""
Tests for extraction layer (OCR, parsing, LLM normalization).
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4

from src.extraction.row_parser import RowParser
from src.extraction.cost_controller import SessionCostTracker, CostController
from src.extraction.table_detector import TableDetector


class TestRowParser:
    """Tests for RowParser."""

    def test_parse_lines_standard_format(self):
        """Test parsing standard packing slip format."""
        parser = RowParser()

        text = """
        PACKING SLIP

        Item  Qty  Unit  Part Number    Description
        1     12   ea    MTU-OF-4568   MTU Oil Filter
        2     8    ea    KOH-AF-9902   Kohler Air Filter
        3     15   ea    MTU-FF-4569   MTU Fuel Filter
        """

        result = parser.parse_lines(text)

        assert result["success"] is True
        assert len(result["lines"]) >= 2  # Should parse at least 2 lines
        assert result["coverage"] > 0.5

    def test_parse_lines_with_decimal_quantities(self):
        """Test parsing lines with decimal quantities."""
        parser = RowParser()

        text = """
        1  12.5  ea  MTU-OF-4568  MTU Oil Filter
        2  8.75  ea  KOH-AF-9902  Kohler Air Filter
        """

        result = parser.parse_lines(text)

        assert result["success"] is True
        lines = result["lines"]
        assert any(line["quantity"] == 12.5 for line in lines)

    def test_parse_lines_no_matches(self):
        """Test parsing with no matches."""
        parser = RowParser()

        text = """
        This is random text with no line items.
        Nothing to parse here.
        """

        result = parser.parse_lines(text)

        assert result["success"] is False
        assert len(result["lines"]) == 0
        assert result["coverage"] == 0.0

    def test_parse_lines_filters_headers(self):
        """Test that parser filters out header rows."""
        parser = RowParser()

        text = """
        Item  Qty  Unit  Part Number    Description
        1     12   ea    MTU-OF-4568   MTU Oil Filter
        Total Items: 1
        """

        result = parser.parse_lines(text)

        # Should not include header or footer
        assert result["success"] is True
        lines = result["lines"]
        assert all("total" not in line["description"].lower() for line in lines)


class TestSessionCostTracker:
    """Tests for SessionCostTracker."""

    def test_initialization(self):
        """Test cost tracker initialization."""
        session_id = uuid4()
        tracker = SessionCostTracker(session_id)

        assert tracker.session_id == session_id
        assert tracker.total_cost == 0.0
        assert tracker.total_tokens == 0
        assert tracker.llm_calls == 0

    def test_record_llm_call(self):
        """Test recording LLM calls."""
        tracker = SessionCostTracker(uuid4())

        tracker.record_llm_call("gpt-4.1-mini", 1000, 500, 0.05)

        assert tracker.total_cost == 0.05
        assert tracker.total_tokens == 1500
        assert tracker.llm_calls == 1

    def test_record_multiple_llm_calls(self):
        """Test recording multiple LLM calls."""
        tracker = SessionCostTracker(uuid4())

        tracker.record_llm_call("gpt-4.1-mini", 1000, 500, 0.05)
        tracker.record_llm_call("gpt-4.1-mini", 800, 400, 0.04)

        assert tracker.total_cost == 0.09
        assert tracker.total_tokens == 2700
        assert tracker.llm_calls == 2

    def test_is_budget_exceeded(self):
        """Test budget exceeded check."""
        tracker = SessionCostTracker(uuid4())

        # Under budget
        tracker.record_llm_call("gpt-4.1-mini", 1000, 500, 0.05)
        assert tracker.is_budget_exceeded() is False

        # Over budget
        tracker.record_llm_call("gpt-4.1", 5000, 2500, 0.50)
        assert tracker.is_budget_exceeded() is True

    def test_can_make_llm_call(self):
        """Test can make LLM call check."""
        tracker = SessionCostTracker(uuid4())

        # Can make calls initially
        assert tracker.can_make_llm_call() is True

        # Make 3 calls
        for _ in range(3):
            tracker.record_llm_call("gpt-4.1-mini", 1000, 500, 0.05)

        # Cannot make more calls (limit is 3)
        assert tracker.can_make_llm_call() is False

    def test_get_summary(self):
        """Test cost summary."""
        tracker = SessionCostTracker(uuid4())

        tracker.record_llm_call("gpt-4.1-mini", 1000, 500, 0.05)
        tracker.record_llm_call("gpt-4.1-mini", 800, 400, 0.04)

        summary = tracker.get_summary()

        assert summary["total_cost"] == 0.09
        assert summary["total_tokens"] == 2700
        assert summary["llm_calls"] == 2
        assert "calls" in summary
        assert len(summary["calls"]) == 2


class TestCostController:
    """Tests for CostController."""

    def test_decide_next_action_skip_llm(self):
        """Test decision to skip LLM when coverage high."""
        tracker = SessionCostTracker(uuid4())
        controller = CostController(tracker)

        decision = controller.decide_next_action(
            coverage=0.85,
            table_confidence=0.9,
            llm_attempts=0
        )

        assert decision == "accept"

    def test_decide_next_action_use_mini(self):
        """Test decision to use gpt-4.1-mini."""
        tracker = SessionCostTracker(uuid4())
        controller = CostController(tracker)

        decision = controller.decide_next_action(
            coverage=0.65,
            table_confidence=0.8,
            llm_attempts=0
        )

        assert decision == "use_mini"

    def test_decide_next_action_escalate(self):
        """Test decision to escalate to gpt-4.1."""
        tracker = SessionCostTracker(uuid4())
        controller = CostController(tracker)

        # First call used mini, coverage still low
        tracker.record_llm_call("gpt-4.1-mini", 1000, 500, 0.05)

        decision = controller.decide_next_action(
            coverage=0.50,
            table_confidence=0.6,
            llm_attempts=1
        )

        assert decision == "escalate"

    def test_decide_next_action_budget_exceeded(self):
        """Test decision when budget exceeded."""
        tracker = SessionCostTracker(uuid4())
        controller = CostController(tracker)

        # Exceed budget
        tracker.record_llm_call("gpt-4.1", 5000, 2500, 0.60)

        decision = controller.decide_next_action(
            coverage=0.50,
            table_confidence=0.6,
            llm_attempts=1
        )

        assert decision == "accept_partial"

    def test_decide_next_action_max_attempts(self):
        """Test decision when max attempts reached."""
        tracker = SessionCostTracker(uuid4())
        controller = CostController(tracker)

        # Make 3 attempts
        for _ in range(3):
            tracker.record_llm_call("gpt-4.1-mini", 1000, 500, 0.05)

        decision = controller.decide_next_action(
            coverage=0.50,
            table_confidence=0.6,
            llm_attempts=3
        )

        assert decision == "accept_partial"


class TestTableDetector:
    """Tests for TableDetector."""

    def test_detect_table_structure_with_table(self):
        """Test table detection with tabular text."""
        detector = TableDetector()

        text = """
        Item  Qty  Unit  Part Number    Description
        1     12   ea    MTU-OF-4568   MTU Oil Filter
        2     8    ea    KOH-AF-9902   Kohler Air Filter
        3     15   ea    MTU-FF-4569   MTU Fuel Filter
        """

        result = detector.detect_table_structure(text)

        assert result["has_table"] is True
        assert result["confidence"] > 0.5
        assert result["row_count"] >= 3

    def test_detect_table_structure_no_table(self):
        """Test table detection with non-tabular text."""
        detector = TableDetector()

        text = """
        This is a paragraph of text.
        It has no table structure.
        Just regular sentences.
        """

        result = detector.detect_table_structure(text)

        assert result["has_table"] is False
        assert result["confidence"] < 0.5

    def test_detect_columns(self):
        """Test column detection."""
        detector = TableDetector()

        text = """
        Item  Qty  Unit  Part Number    Description
        1     12   ea    MTU-OF-4568   MTU Oil Filter
        """

        columns = detector._detect_columns(text)

        assert len(columns) >= 4  # Should detect multiple columns
