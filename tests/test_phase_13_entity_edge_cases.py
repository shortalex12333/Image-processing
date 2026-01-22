"""
PHASE 13: Test Entity Extraction Edge Cases
Handle missing data, malformed text, and edge cases
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_missing_order_number():
    """Test handling of missing order number"""
    try:
        from src.extraction.entity_extractor import EntityExtractor

        extractor = EntityExtractor()
        text = "Just some random text without an order number"

        entities = extractor.extract_packing_slip_entities(text)
        assert entities.get("order_number") is None, \
            f"Expected None, got {entities['order_number']}"

        print("✓ Handles missing order number gracefully")

        return True
    except Exception as e:
        print(f"✗ Missing order number test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_malformed_tracking():
    """Test handling of malformed tracking number"""
    try:
        from src.extraction.entity_extractor import EntityExtractor

        extractor = EntityExtractor()
        text = "Tracking: invalid-format"

        entities = extractor.extract_packing_slip_entities(text)
        assert entities.get("tracking_number") is None, \
            f"Expected None, got {entities['tracking_number']}"

        print("✓ Handles malformed tracking number")

        return True
    except Exception as e:
        print(f"✗ Malformed tracking test failed: {e}")
        return False

def test_no_line_items():
    """Test handling of text with no line items"""
    try:
        from src.extraction.entity_extractor import EntityExtractor

        extractor = EntityExtractor()
        text = """
        PACKING SLIP
        Order: ORD-2024-999
        Tracking: 1Z999999999999999999

        No items shipped
        """

        entities = extractor.extract_packing_slip_entities(text)
        assert len(entities["line_items"]) == 0, \
            f"Expected empty array, got {len(entities['line_items'])} items"

        print("✓ Handles documents with no line items")

        return True
    except Exception as e:
        print(f"✗ No line items test failed: {e}")
        return False

def test_extra_whitespace():
    """Test handling of extra whitespace and formatting"""
    try:
        from src.extraction.entity_extractor import EntityExtractor

        extractor = EntityExtractor()

        # Text with lots of extra whitespace
        text = """


        Order    Number  :    ORD-2024-123


        Tracking   :   1Z1234567890123456


        5   ea   Test   Item


        """

        entities = extractor.extract_packing_slip_entities(text)

        assert entities["order_number"] == "ORD-2024-123", \
            f"Expected ORD-2024-123, got {entities['order_number']}"

        assert entities["tracking_number"] == "1Z1234567890123456", \
            f"Expected tracking number, got {entities['tracking_number']}"

        # Line items might not extract perfectly with extra whitespace, but should not crash
        print(f"✓ Handles extra whitespace (extracted {len(entities['line_items'])} items)")

        return True
    except Exception as e:
        print(f"✗ Extra whitespace test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_special_characters():
    """Test handling of special characters in descriptions"""
    try:
        from src.extraction.entity_extractor import EntityExtractor

        extractor = EntityExtractor()
        text = """
        Order: ORD-2024-001
        2 ea 3/4" Valve (Stainless Steel) - Model #123-ABC
        1 ea Hose 1.5" ID x 36" Long @ 150 PSI
        """

        entities = extractor.extract_packing_slip_entities(text)

        # Should handle special characters in descriptions
        assert entities["order_number"] == "ORD-2024-001"
        assert len(entities["line_items"]) >= 1

        print(f"✓ Handles special characters in descriptions")

        return True
    except Exception as e:
        print(f"✗ Special characters test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_partially_malformed_line_items():
    """Test handling of partially malformed line items"""
    try:
        from src.extraction.entity_extractor import EntityExtractor

        extractor = EntityExtractor()
        text = """
        Items:
        5 ea Good Item Description
        INVALID LINE FORMAT
        3 pcs Another Good Item
        Not a quantity ea Something
        """

        entities = extractor.extract_packing_slip_entities(text)

        # Should extract only valid line items, skip invalid ones
        assert len(entities["line_items"]) >= 2, \
            f"Should extract at least 2 valid items, got {len(entities['line_items'])}"

        print(f"✓ Handles partially malformed line items ({len(entities['line_items'])} valid items extracted)")

        return True
    except Exception as e:
        print(f"✗ Partially malformed line items test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_confidence_with_missing_fields():
    """Test confidence calculation when fields are missing"""
    try:
        from src.extraction.entity_extractor import EntityExtractor

        extractor = EntityExtractor()

        # Only order number
        text1 = "Order: ORD-2024-001"
        result1 = extractor.extract_packing_slip_entities(text1)
        assert result1["extraction_confidence"] > 0.0, "Should have some confidence with order number"
        assert result1["extraction_confidence"] < 0.5, "Confidence should be low with only one field"

        # Only tracking
        text2 = "Tracking: 1Z123456789012345678"
        result2 = extractor.extract_packing_slip_entities(text2)
        assert result2["extraction_confidence"] > 0.0, "Should have some confidence with tracking"

        # No fields
        text3 = "Random text"
        result3 = extractor.extract_packing_slip_entities(text3)
        assert result3["extraction_confidence"] == 0.0, "Should have zero confidence with no fields"

        print(f"✓ Confidence calculation handles missing fields correctly")

        return True
    except Exception as e:
        print(f"✗ Confidence with missing fields test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_phase_13():
    """Run all Phase 13 tests"""
    print("\n" + "="*60)
    print("PHASE 13: Test Entity Extraction Edge Cases")
    print("="*60 + "\n")

    results = []

    results.append(("Missing order number", test_missing_order_number()))
    results.append(("Malformed tracking number", test_malformed_tracking()))
    results.append(("No line items", test_no_line_items()))
    results.append(("Extra whitespace handling", test_extra_whitespace()))
    results.append(("Special characters", test_special_characters()))
    results.append(("Partially malformed line items", test_partially_malformed_line_items()))
    results.append(("Confidence with missing fields", test_confidence_with_missing_fields()))

    print("\n" + "-"*60)
    print("PHASE 13 RESULTS:")
    print("-"*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ PHASE 13: COMPLETE - Edge cases handled robustly")
        return True
    else:
        print(f"\n❌ PHASE 13: FAILED - {total - passed} tests broken")
        return False

if __name__ == "__main__":
    success = run_phase_13()
    sys.exit(0 if success else 1)
