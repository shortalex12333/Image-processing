"""
Suggestion ranker for scoring and sorting part matches.
Combines multiple signals (fuzzy match, shopping list, recent orders) into final ranking.
"""

from uuid import UUID
from typing import Any

from src.logger import get_logger

logger = get_logger(__name__)


class SuggestionRanker:
    """Ranks and scores part suggestions based on multiple factors."""

    def rank_suggestions(
        self,
        part_matches: list[dict],
        shopping_list_match: dict | None,
        recent_orders: list[dict]
    ) -> dict | None:
        """
        Rank suggestions and return the best match.

        Args:
            part_matches: List of fuzzy-matched parts
            shopping_list_match: Shopping list match (if any)
            recent_orders: Recent purchase orders containing this part

        Returns:
            Best suggestion with boosted confidence, or None

        Example:
            >>> ranker = SuggestionRanker()
            >>> suggestion = ranker.rank_suggestions(
            ...     part_matches=[{...}],
            ...     shopping_list_match={...},
            ...     recent_orders=[{...}]
            ... )
            >>> suggestion
            {
                "part_id": "uuid",
                "part_number": "MTU-OF-4568",
                "part_name": "MTU Oil Filter",
                "confidence": 0.98,  # Boosted from 0.85
                "match_reason": "on_shopping_list",  # Changed from "fuzzy_description"
                "current_stock": 12.0,
                "boost_reasons": ["shopping_list_match", "recent_order"]
            }
        """
        if not part_matches:
            return None

        # Start with top match from part matcher
        best_match = part_matches[0].copy()
        boost_reasons = []

        # Calculate boosts
        shopping_boost = self._calculate_shopping_list_boost(shopping_list_match)
        order_boost = self._calculate_order_boost(recent_orders)

        # Apply boosts to confidence
        base_confidence = best_match["confidence"]
        boosted_confidence = min(
            base_confidence + shopping_boost + order_boost,
            1.0  # Cap at 100%
        )

        # Track boost reasons
        if shopping_boost > 0:
            boost_reasons.append("shopping_list_match")
            # Upgrade match reason if shopping list match
            best_match["match_reason"] = "on_shopping_list"

        if order_boost > 0:
            boost_reasons.append("recent_order")

        # Update confidence
        best_match["confidence"] = boosted_confidence
        best_match["boost_reasons"] = boost_reasons
        best_match["base_confidence"] = base_confidence

        logger.info("Suggestion ranked", extra={
            "part_id": best_match["part_id"],
            "base_confidence": base_confidence,
            "boosted_confidence": boosted_confidence,
            "boost_reasons": boost_reasons
        })

        return best_match

    def rank_all_suggestions(
        self,
        part_matches: list[dict],
        shopping_list_match: dict | None,
        recent_orders: list[dict],
        limit: int = 5
    ) -> list[dict]:
        """
        Rank all suggestions with boosts applied.

        Args:
            part_matches: All fuzzy-matched parts
            shopping_list_match: Shopping list match
            recent_orders: Recent orders
            limit: Maximum suggestions to return

        Returns:
            Ranked list of suggestions
        """
        if not part_matches:
            return []

        # Calculate boosts
        shopping_boost = self._calculate_shopping_list_boost(shopping_list_match)
        order_boost = self._calculate_order_boost(recent_orders)

        # Apply boosts to all matches
        ranked = []
        for match in part_matches:
            boosted = match.copy()
            boost_reasons = []

            # Apply shopping list boost (only to parts that match the shopping list)
            if shopping_list_match and shopping_boost > 0:
                boost_reasons.append("shopping_list_match")

            # Apply recent order boost
            part_in_orders = any(
                str(order.get("order_id")) == str(match["part_id"])
                for order in recent_orders
            )
            if part_in_orders:
                boost_reasons.append("recent_order")
                boosted["confidence"] = min(
                    match["confidence"] + order_boost,
                    1.0
                )

            boosted["boost_reasons"] = boost_reasons
            boosted["base_confidence"] = match["confidence"]
            ranked.append(boosted)

        # Sort by confidence (descending)
        ranked.sort(key=lambda m: m["confidence"], reverse=True)

        return ranked[:limit]

    def _calculate_shopping_list_boost(self, shopping_list_match: dict | None) -> float:
        """
        Calculate confidence boost from shopping list match.

        Args:
            shopping_list_match: Shopping list match or None

        Returns:
            Boost value (0.0 to 0.15)
        """
        if not shopping_list_match:
            return 0.0

        # Higher boost for complete fulfillment
        fulfillment = shopping_list_match.get("fulfillment_percentage", 0.0)

        if fulfillment >= 100.0:
            return 0.15  # +15% for complete fulfillment
        elif fulfillment >= 50.0:
            return 0.10  # +10% for partial fulfillment (>= 50%)
        else:
            return 0.05  # +5% for any shopping list match

    def _calculate_order_boost(self, recent_orders: list[dict]) -> float:
        """
        Calculate confidence boost from recent orders.

        Args:
            recent_orders: List of recent purchase orders

        Returns:
            Boost value (0.0 to 0.10)
        """
        if not recent_orders:
            return 0.0

        # More recent orders = higher boost
        most_recent = recent_orders[0]
        days_since = most_recent.get("days_since_order", 999)

        if days_since <= 7:
            return 0.10  # +10% if ordered within last week
        elif days_since <= 30:
            return 0.05  # +5% if ordered within last month
        else:
            return 0.02  # +2% for any recent order

    def create_alternative_suggestions(
        self,
        part_matches: list[dict],
        exclude_part_id: UUID | None = None,
        limit: int = 3
    ) -> list[dict]:
        """
        Create alternative suggestions (lower confidence matches).

        Args:
            part_matches: All part matches
            exclude_part_id: Part ID to exclude (the primary suggestion)
            limit: Maximum alternatives to return

        Returns:
            List of alternative suggestions
        """
        alternatives = []

        for match in part_matches:
            # Skip the primary suggestion
            if exclude_part_id and match["part_id"] == str(exclude_part_id):
                continue

            # Only include if confidence is reasonable (>= 60%)
            if match["confidence"] < 0.6:
                continue

            alternatives.append({
                "part_id": match["part_id"],
                "part_number": match["part_number"],
                "part_name": match.get("part_name", ""),
                "confidence": match["confidence"],
                "match_reason": match.get("match_reason", "fuzzy_match")
            })

        # Sort by confidence
        alternatives.sort(key=lambda a: a["confidence"], reverse=True)

        return alternatives[:limit]
