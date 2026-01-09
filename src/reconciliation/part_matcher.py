"""
Part matcher for fuzzy matching draft lines to existing parts.
Uses rapidfuzz for fast, efficient string matching.
"""

from uuid import UUID
from typing import Any

from rapidfuzz import fuzz, process

from src.database import get_supabase_service
from src.logger import get_logger

logger = get_logger(__name__)


class PartMatcher:
    """Matches draft line descriptions to existing parts using fuzzy matching."""

    def __init__(self):
        self.supabase = get_supabase_service()

    async def find_matches(
        self,
        yacht_id: UUID,
        description: str,
        part_number: str | None = None,
        limit: int = 5,
        threshold: int = 70
    ) -> list[dict]:
        """
        Find matching parts for a draft line.

        Args:
            yacht_id: Yacht UUID (for multi-tenant isolation)
            description: Item description from OCR
            part_number: Extracted part number (if available)
            limit: Maximum number of matches to return
            threshold: Minimum similarity score (0-100)

        Returns:
            List of matching parts with confidence scores

        Example:
            >>> matcher = PartMatcher()
            >>> matches = await matcher.find_matches(
            ...     yacht_id=yacht_id,
            ...     description="MTU Oil Filter",
            ...     part_number="MTU-OF-4568"
            ... )
            >>> matches[0]
            {
                "part_id": "uuid",
                "part_number": "MTU-OF-4568",
                "part_name": "MTU Oil Filter Element",
                "confidence": 0.95,
                "match_reason": "exact_part_number",
                "current_stock": 12.0,
                "bin_location": "A-12"
            }
        """
        matches = []

        # Strategy 1: Exact part number match (highest priority)
        if part_number:
            exact_match = await self._exact_part_number_match(yacht_id, part_number)
            if exact_match:
                matches.append(exact_match)
                # If exact part number match, return immediately with high confidence
                return matches[:limit]

        # Strategy 2: Fuzzy part number match
        if part_number:
            fuzzy_part_matches = await self._fuzzy_part_number_match(
                yacht_id, part_number, threshold
            )
            matches.extend(fuzzy_part_matches)

        # Strategy 3: Fuzzy description match
        fuzzy_desc_matches = await self._fuzzy_description_match(
            yacht_id, description, threshold
        )
        matches.extend(fuzzy_desc_matches)

        # Remove duplicates (same part_id)
        seen_ids = set()
        unique_matches = []
        for match in matches:
            if match["part_id"] not in seen_ids:
                seen_ids.add(match["part_id"])
                unique_matches.append(match)

        # Sort by confidence (descending)
        unique_matches.sort(key=lambda m: m["confidence"], reverse=True)

        logger.info("Part matching complete", extra={
            "yacht_id": str(yacht_id),
            "description": description[:50],
            "matches_found": len(unique_matches)
        })

        return unique_matches[:limit]

    async def _exact_part_number_match(self, yacht_id: UUID, part_number: str) -> dict | None:
        """
        Find exact part number match.

        Args:
            yacht_id: Yacht UUID
            part_number: Part number to match

        Returns:
            Match dict or None
        """
        try:
            # Normalize part number for comparison
            normalized = self._normalize_part_number(part_number)

            result = self.supabase.table("pms_parts") \
                .select("part_id, part_number, name, manufacturer, quantity_on_hand, bin_location") \
                .eq("yacht_id", str(yacht_id)) \
                .ilike("part_number", normalized) \
                .limit(1) \
                .execute()

            if result.data:
                part = result.data[0]
                return {
                    "part_id": part["part_id"],
                    "part_number": part["part_number"],
                    "part_name": part["name"],
                    "manufacturer": part.get("manufacturer"),
                    "confidence": 1.0,  # Exact match
                    "match_reason": "exact_part_number",
                    "current_stock": part.get("quantity_on_hand"),
                    "bin_location": part.get("bin_location")
                }

            return None

        except Exception as e:
            logger.error("Exact part number match failed", extra={
                "part_number": part_number,
                "error": str(e)
            })
            return None

    async def _fuzzy_part_number_match(
        self,
        yacht_id: UUID,
        part_number: str,
        threshold: int
    ) -> list[dict]:
        """
        Find fuzzy part number matches.

        Args:
            yacht_id: Yacht UUID
            part_number: Part number to match
            threshold: Minimum similarity score

        Returns:
            List of matches
        """
        try:
            # Get all parts for this yacht
            result = self.supabase.table("pms_parts") \
                .select("part_id, part_number, name, manufacturer, quantity_on_hand, bin_location") \
                .eq("yacht_id", str(yacht_id)) \
                .execute()

            if not result.data:
                return []

            # Normalize input
            normalized_input = self._normalize_part_number(part_number)

            # Build list of part numbers
            parts_dict = {
                self._normalize_part_number(p["part_number"]): p
                for p in result.data
            }

            # Fuzzy match using rapidfuzz
            matches = process.extract(
                normalized_input,
                parts_dict.keys(),
                scorer=fuzz.ratio,
                limit=10
            )

            # Filter by threshold and convert to result format
            results = []
            for match_text, score, _ in matches:
                if score >= threshold:
                    part = parts_dict[match_text]
                    results.append({
                        "part_id": part["part_id"],
                        "part_number": part["part_number"],
                        "part_name": part["name"],
                        "manufacturer": part.get("manufacturer"),
                        "confidence": score / 100.0,  # Normalize to 0-1
                        "match_reason": "fuzzy_part_number",
                        "current_stock": part.get("quantity_on_hand"),
                        "bin_location": part.get("bin_location")
                    })

            return results

        except Exception as e:
            logger.error("Fuzzy part number match failed", extra={
                "part_number": part_number,
                "error": str(e)
            })
            return []

    async def _fuzzy_description_match(
        self,
        yacht_id: UUID,
        description: str,
        threshold: int
    ) -> list[dict]:
        """
        Find fuzzy description matches.

        Args:
            yacht_id: Yacht UUID
            description: Description to match
            threshold: Minimum similarity score

        Returns:
            List of matches
        """
        try:
            # Get all parts for this yacht
            result = self.supabase.table("pms_parts") \
                .select("part_id, part_number, name, manufacturer, quantity_on_hand, bin_location") \
                .eq("yacht_id", str(yacht_id)) \
                .execute()

            if not result.data:
                return []

            # Normalize input
            normalized_input = self._normalize_description(description)

            # Build dict of part names
            parts_dict = {
                self._normalize_description(p["name"]): p
                for p in result.data
            }

            # Fuzzy match using token_sort_ratio (better for word order variations)
            matches = process.extract(
                normalized_input,
                parts_dict.keys(),
                scorer=fuzz.token_sort_ratio,
                limit=10
            )

            # Filter by threshold and convert to result format
            results = []
            for match_text, score, _ in matches:
                if score >= threshold:
                    part = parts_dict[match_text]
                    results.append({
                        "part_id": part["part_id"],
                        "part_number": part["part_number"],
                        "part_name": part["name"],
                        "manufacturer": part.get("manufacturer"),
                        "confidence": score / 100.0,
                        "match_reason": "fuzzy_description",
                        "current_stock": part.get("quantity_on_hand"),
                        "bin_location": part.get("bin_location")
                    })

            return results

        except Exception as e:
            logger.error("Fuzzy description match failed", extra={
                "description": description[:50],
                "error": str(e)
            })
            return []

    @staticmethod
    def _normalize_part_number(part_number: str) -> str:
        """
        Normalize part number for matching.

        Examples:
            MTU-OF-4568 → MTUOF4568
            MTU OF 4568 → MTUOF4568
            MTU_OF_4568 → MTUOF4568
        """
        # Remove spaces, hyphens, underscores
        normalized = part_number.replace(" ", "").replace("-", "").replace("_", "")
        # Uppercase for case-insensitive matching
        return normalized.upper()

    @staticmethod
    def _normalize_description(description: str) -> str:
        """
        Normalize description for matching.

        Examples:
            "MTU Oil Filter Element" → "mtu oil filter element"
            "  Extra   spaces  " → "extra spaces"
        """
        # Lowercase
        normalized = description.lower()
        # Remove extra whitespace
        import re
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized.strip()
