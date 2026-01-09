"""
Tests for reconciliation layer (part matching, suggestions).
"""

import pytest
from unittest.mock import Mock
from uuid import uuid4

from src.reconciliation.part_matcher import PartMatcher
from src.reconciliation.suggestion_ranker import SuggestionRanker


class TestPartMatcher:
    """Tests for PartMatcher."""

    def test_normalize_part_number(self):
        """Test part number normalization."""
        matcher = PartMatcher()

        assert matcher._normalize_part_number("MTU-OF-4568") == "MTUOF4568"
        assert matcher._normalize_part_number("koh af 9902") == "KOHAF9902"
        assert matcher._normalize_part_number("Test-123_ABC") == "TEST123ABC"

    @pytest.mark.asyncio
    async def test_find_matches_exact_part_number(self, yacht_id, sample_part, mock_supabase):
        """Test finding exact part number match."""
        matcher = PartMatcher()
        matcher.supabase = mock_supabase

        # Mock exact match result
        mock_supabase.execute.return_value.data = [sample_part]

        matches = await matcher.find_matches(
            yacht_id=yacht_id,
            description="MTU Oil Filter",
            part_number="MTU-OF-4568"
        )

        assert len(matches) > 0
        assert matches[0]["match_type"] == "exact"
        assert matches[0]["confidence"] == 1.0

    @pytest.mark.asyncio
    async def test_find_matches_no_part_number(self, yacht_id, sample_part, mock_supabase):
        """Test finding matches by description only."""
        matcher = PartMatcher()
        matcher.supabase = mock_supabase

        # Mock parts in database
        mock_supabase.execute.return_value.data = [sample_part]

        matches = await matcher.find_matches(
            yacht_id=yacht_id,
            description="MTU Oil Filter",
            part_number=None
        )

        assert len(matches) > 0
        assert matches[0]["match_type"] in ["fuzzy_description", "fuzzy_part_number"]
        assert 0.0 < matches[0]["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_find_matches_no_results(self, yacht_id, mock_supabase):
        """Test finding matches with no results."""
        matcher = PartMatcher()
        matcher.supabase = mock_supabase

        # Mock no results
        mock_supabase.execute.return_value.data = []

        matches = await matcher.find_matches(
            yacht_id=yacht_id,
            description="Nonexistent Part",
            part_number="XXX-999"
        )

        assert len(matches) == 0

    def test_calculate_fuzzy_score(self):
        """Test fuzzy matching score calculation."""
        matcher = PartMatcher()

        # Identical strings
        score = matcher._calculate_fuzzy_score("MTU Oil Filter", "MTU Oil Filter")
        assert score == 1.0

        # Similar strings
        score = matcher._calculate_fuzzy_score("MTU Oil Filter", "MTU OIL FILTER")
        assert score > 0.9

        # Different strings
        score = matcher._calculate_fuzzy_score("MTU Oil Filter", "Kohler Air Filter")
        assert score < 0.5


class TestSuggestionRanker:
    """Tests for SuggestionRanker."""

    def test_rank_suggestions_by_confidence(self):
        """Test ranking suggestions by confidence."""
        ranker = SuggestionRanker()

        suggestions = [
            {"part_id": uuid4(), "confidence": 0.7, "match_reason": "fuzzy_description"},
            {"part_id": uuid4(), "confidence": 0.95, "match_reason": "exact_part_number"},
            {"part_id": uuid4(), "confidence": 0.85, "match_reason": "fuzzy_part_number"}
        ]

        ranked = ranker.rank_suggestions(suggestions)

        assert ranked[0]["confidence"] == 0.95  # Highest first
        assert ranked[1]["confidence"] == 0.85
        assert ranked[2]["confidence"] == 0.7

    def test_boost_shopping_list_confidence(self):
        """Test confidence boost for shopping list items."""
        ranker = SuggestionRanker()

        suggestion = {
            "part_id": uuid4(),
            "confidence": 0.70,
            "on_shopping_list": True,
            "match_reason": "fuzzy_description"
        }

        boosted = ranker._boost_confidence(suggestion)

        # Should be boosted by 15%
        assert boosted["confidence"] > 0.70
        assert boosted["confidence"] <= 0.85

    def test_boost_recent_order_confidence(self):
        """Test confidence boost for recently ordered items."""
        ranker = SuggestionRanker()

        suggestion = {
            "part_id": uuid4(),
            "confidence": 0.70,
            "recently_ordered": True,
            "match_reason": "fuzzy_description"
        }

        boosted = ranker._boost_confidence(suggestion)

        # Should be boosted by 10%
        assert boosted["confidence"] > 0.70
        assert boosted["confidence"] <= 0.80

    def test_boost_both_shopping_and_recent(self):
        """Test confidence boost for both shopping list and recent order."""
        ranker = SuggestionRanker()

        suggestion = {
            "part_id": uuid4(),
            "confidence": 0.70,
            "on_shopping_list": True,
            "recently_ordered": True,
            "match_reason": "fuzzy_description"
        }

        boosted = ranker._boost_confidence(suggestion)

        # Should be boosted by 25% total (15% + 10%)
        assert boosted["confidence"] > 0.70
        assert boosted["confidence"] <= 0.95  # Cap at 0.95 for non-exact

    def test_confidence_cap(self):
        """Test that confidence doesn't exceed reasonable limits."""
        ranker = SuggestionRanker()

        suggestion = {
            "part_id": uuid4(),
            "confidence": 0.90,
            "on_shopping_list": True,
            "recently_ordered": True,
            "match_reason": "fuzzy_description"
        }

        boosted = ranker._boost_confidence(suggestion)

        # Should be capped at 0.95 for non-exact matches
        assert boosted["confidence"] <= 0.95

    def test_exact_match_not_boosted(self):
        """Test that exact matches don't get boosted."""
        ranker = SuggestionRanker()

        suggestion = {
            "part_id": uuid4(),
            "confidence": 1.0,
            "on_shopping_list": True,
            "match_reason": "exact_part_number"
        }

        boosted = ranker._boost_confidence(suggestion)

        # Exact matches should stay at 1.0
        assert boosted["confidence"] == 1.0

    def test_filter_low_confidence(self):
        """Test filtering out low confidence suggestions."""
        ranker = SuggestionRanker()

        suggestions = [
            {"part_id": uuid4(), "confidence": 0.95, "match_reason": "exact"},
            {"part_id": uuid4(), "confidence": 0.40, "match_reason": "fuzzy"},  # Too low
            {"part_id": uuid4(), "confidence": 0.65, "match_reason": "fuzzy"}
        ]

        filtered = ranker.filter_suggestions(suggestions, min_confidence=0.50)

        assert len(filtered) == 2
        assert all(s["confidence"] >= 0.50 for s in filtered)

    def test_limit_suggestions(self):
        """Test limiting number of suggestions."""
        ranker = SuggestionRanker()

        suggestions = [
            {"part_id": uuid4(), "confidence": 0.95, "match_reason": "exact"},
            {"part_id": uuid4(), "confidence": 0.85, "match_reason": "fuzzy"},
            {"part_id": uuid4(), "confidence": 0.75, "match_reason": "fuzzy"},
            {"part_id": uuid4(), "confidence": 0.65, "match_reason": "fuzzy"}
        ]

        limited = ranker.filter_suggestions(suggestions, max_suggestions=2)

        assert len(limited) == 2
        assert limited[0]["confidence"] == 0.95  # Keep highest confidence
        assert limited[1]["confidence"] == 0.85
