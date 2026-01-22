"""
PHASE 18: Fuzzy Matching for Line Items
Match extracted line items to shopping list using fuzzy matching
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

async def test_exact_match():
    """Test exact match returns 100% confidence"""
    try:
        from src.reconciliation.order_matcher_by_number import OrderMatcherByNumber

        matcher = OrderMatcherByNumber()

        shopping_list = [
            {"part_name": "3/4\" O2Y Coil Pack-Sweat", "quantity_ordered": 5},
            {"part_name": "1\" O2Y Coil Pack-Sweat", "quantity_ordered": 3}
        ]

        match = await matcher.find_best_shopping_list_match(
            description="3/4\" O2Y Coil Pack-Sweat",
            shopping_list_items=shopping_list
        )

        assert match is not None, "Should find exact match"
        assert match["match_score"] >= 0.95, f"Exact match should be >95%, got {match['match_score']:.0%}"

        print(f"✓ Exact match: {match['match_score']:.0%} confidence")

        return True
    except Exception as e:
        print(f"✗ Exact match test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_fuzzy_match():
    """Test fuzzy match for OCR errors"""
    try:
        from src.reconciliation.order_matcher_by_number import OrderMatcherByNumber

        matcher = OrderMatcherByNumber()

        shopping_list = [
            {"part_name": "3/4\" O2Y Coil Pack-Sweat", "quantity_ordered": 5}
        ]

        # Missing hyphen (OCR error)
        match = await matcher.find_best_shopping_list_match(
            description="3/4\" O2Y Coil Pack Sweat",
            shopping_list_items=shopping_list
        )

        assert match is not None, "Should find fuzzy match"
        assert match["match_score"] >= 0.85, f"Fuzzy match should be >85%, got {match['match_score']:.0%}"

        print(f"✓ Fuzzy match: {match['match_score']:.0%} confidence")

        return True
    except Exception as e:
        print(f"✗ Fuzzy match test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_no_match_below_threshold():
    """Test that poor matches return None"""
    try:
        from src.reconciliation.order_matcher_by_number import OrderMatcherByNumber

        matcher = OrderMatcherByNumber()

        shopping_list = [
            {"part_name": "3/4\" O2Y Coil Pack-Sweat", "quantity_ordered": 5}
        ]

        match = await matcher.find_best_shopping_list_match(
            description="Completely different item name",
            shopping_list_items=shopping_list,
            threshold=0.7
        )

        assert match is None, "Should return None for poor match"

        print("✓ Returns None for matches below threshold")

        return True
    except Exception as e:
        print(f"✗ No match test failed: {e}")
        return False

async def test_best_match_selection():
    """Test that best match is selected from multiple options"""
    try:
        from src.reconciliation.order_matcher_by_number import OrderMatcherByNumber

        matcher = OrderMatcherByNumber()

        shopping_list = [
            {"part_name": "O2Y Coil Pack 3/4 inch", "quantity_ordered": 5},
            {"part_name": "3/4\" O2Y Coil Pack-Sweat", "quantity_ordered": 3},
            {"part_name": "O2Y Valve 1 inch", "quantity_ordered": 2}
        ]

        match = await matcher.find_best_shopping_list_match(
            description="3/4\" O2Y Coil Pack-Sweat",
            shopping_list_items=shopping_list
        )

        assert match is not None
        assert match["matched_item"]["part_name"] == "3/4\" O2Y Coil Pack-Sweat"

        print(f"✓ Best match selected from {len(shopping_list)} options")

        return True
    except Exception as e:
        print(f"✗ Best match selection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def run_phase_18():
    """Run all Phase 18 tests"""
    print("\n" + "="*60)
    print("PHASE 18: Fuzzy Matching for Line Items")
    print("="*60 + "\n")

    results = []

    results.append(("Exact match (100% confidence)", await test_exact_match()))
    results.append(("Fuzzy match for OCR errors", await test_fuzzy_match()))
    results.append(("No match below threshold", await test_no_match_below_threshold()))
    results.append(("Best match selection", await test_best_match_selection()))

    print("\n" + "-"*60)
    print("PHASE 18 RESULTS:")
    print("-"*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ PHASE 18: COMPLETE - Fuzzy matching works")
        return True
    else:
        print(f"\n❌ PHASE 18: FAILED - {total - passed} tests broken")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_phase_18())
    sys.exit(0 if success else 1)
