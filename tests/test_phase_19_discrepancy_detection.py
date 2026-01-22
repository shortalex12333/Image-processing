"""
PHASE 19: Detect Quantity Discrepancies
Compare expected vs received quantities
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_shortage_detection():
    """Test detecting shortages (received < ordered)"""
    try:
        from src.reconciliation.order_matcher_by_number import OrderMatcherByNumber

        matcher = OrderMatcherByNumber()

        disc = matcher.detect_discrepancies(
            expected=5,
            received=3,
            part_name="O2Y Coil Pack"
        )

        assert disc is not None, "Should detect shortage"
        assert disc["type"] == "quantity_mismatch"
        assert disc["shortage"] == 2, f"Expected shortage of 2, got {disc['shortage']}"
        assert disc["expected_quantity"] == 5
        assert disc["received_quantity"] == 3

        print(f"✓ Shortage detected: {disc['shortage']} units short")
        print(f"  Severity: {disc['severity']}")

        return True
    except Exception as e:
        print(f"✗ Shortage detection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_overage_detection():
    """Test detecting overages (received > ordered)"""
    try:
        from src.reconciliation.order_matcher_by_number import OrderMatcherByNumber

        matcher = OrderMatcherByNumber()

        disc = matcher.detect_discrepancies(
            expected=5,
            received=7,
            part_name="O2Y Coil Pack"
        )

        assert disc is not None, "Should detect overage"
        assert disc["shortage"] == -2, f"Expected -2 (overage), got {disc['shortage']}"

        print(f"✓ Overage detected: {abs(disc['shortage'])} extra units")

        return True
    except Exception as e:
        print(f"✗ Overage detection test failed: {e}")
        return False

def test_exact_match_no_discrepancy():
    """Test that exact matches return None"""
    try:
        from src.reconciliation.order_matcher_by_number import OrderMatcherByNumber

        matcher = OrderMatcherByNumber()

        disc = matcher.detect_discrepancies(
            expected=5,
            received=5,
            part_name="O2Y Coil Pack"
        )

        assert disc is None, "Exact match should return None"

        print("✓ No discrepancy for exact match")

        return True
    except Exception as e:
        print(f"✗ Exact match test failed: {e}")
        return False

def test_severity_calculation():
    """Test discrepancy severity levels"""
    try:
        from src.reconciliation.order_matcher_by_number import OrderMatcherByNumber

        matcher = OrderMatcherByNumber()

        # High severity (>50% difference)
        disc_high = matcher.detect_discrepancies(
            expected=10,
            received=4,
            part_name="Item A"
        )
        assert disc_high["severity"] == "high", f"Expected high severity, got {disc_high['severity']}"

        # Medium severity (20-50% difference)
        disc_medium = matcher.detect_discrepancies(
            expected=10,
            received=7,
            part_name="Item B"
        )
        assert disc_medium["severity"] == "medium", f"Expected medium severity, got {disc_medium['severity']}"

        # Low severity (<20% difference)
        disc_low = matcher.detect_discrepancies(
            expected=10,
            received=9,
            part_name="Item C"
        )
        assert disc_low["severity"] == "low", f"Expected low severity, got {disc_low['severity']}"

        print("✓ Severity levels: high (>50%), medium (20-50%), low (<20%)")

        return True
    except Exception as e:
        print(f"✗ Severity calculation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_phase_19():
    """Run all Phase 19 tests"""
    print("\n" + "="*60)
    print("PHASE 19: Detect Quantity Discrepancies")
    print("="*60 + "\n")

    results = []

    results.append(("Shortage detection", test_shortage_detection()))
    results.append(("Overage detection", test_overage_detection()))
    results.append(("Exact match (no discrepancy)", test_exact_match_no_discrepancy()))
    results.append(("Severity calculation", test_severity_calculation()))

    print("\n" + "-"*60)
    print("PHASE 19 RESULTS:")
    print("-"*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ PHASE 19: COMPLETE - Discrepancy detection works")
        return True
    else:
        print(f"\n❌ PHASE 19: FAILED - {total - passed} tests broken")
        return False

if __name__ == "__main__":
    success = run_phase_19()
    sys.exit(0 if success else 1)
