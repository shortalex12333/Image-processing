"""
PHASE 12: Create EntityExtractor Class (Packing Slip Only)
Extract order number, tracking, line items from packing slip
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_extract_packing_slip_entities():
    """Test extracting entities from packing slip"""
    try:
        from src.extraction.entity_extractor import EntityExtractor

        extractor = EntityExtractor()

        text = """
        PACKING SLIP
        Order Number: ORD-2024-042
        Tracking: 1Z260AT50346207055

        Items Shipped:
        5 ea 3/4" O2Y Coil Pack-Sweat
        2 ea 1" O2Y Coil Pack-Sweat
        """

        entities = extractor.extract_packing_slip_entities(text)

        assert entities["order_number"] == "ORD-2024-042", \
            f"Expected ORD-2024-042, got {entities['order_number']}"
        print(f"✓ Order number: {entities['order_number']}")

        assert entities["tracking_number"] == "1Z260AT50346207055", \
            f"Expected 1Z260AT50346207055, got {entities['tracking_number']}"
        print(f"✓ Tracking: {entities['tracking_number']}")

        assert len(entities["line_items"]) >= 2, \
            f"Expected at least 2 line items, got {len(entities['line_items'])}"
        print(f"✓ Extracted {len(entities['line_items'])} line items")

        # Verify line item structure
        for item in entities["line_items"]:
            assert "quantity" in item
            assert "description" in item
            assert item["quantity"] > 0
            print(f"  - {item['quantity']} ea {item['description']}")

        return True
    except Exception as e:
        print(f"✗ Packing slip entity extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_order_number_formats():
    """Test different order number formats"""
    try:
        from src.extraction.entity_extractor import EntityExtractor

        extractor = EntityExtractor()

        test_cases = [
            ("Order #: ORD-2024-042", "ORD-2024-042"),
            ("Order Number ORD-2025-123", "ORD-2025-123"),
            ("ORDER #: PO-123456", "PO-123456"),
        ]

        for text, expected in test_cases:
            entities = extractor.extract_packing_slip_entities(text)
            assert entities["order_number"] == expected, \
                f"Expected {expected}, got {entities['order_number']}"

        print(f"✓ Order number formats recognized: {len(test_cases)}")

        return True
    except Exception as e:
        print(f"✗ Order number format test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_tracking_number_formats():
    """Test different tracking number formats"""
    try:
        from src.extraction.entity_extractor import EntityExtractor

        extractor = EntityExtractor()

        test_cases = [
            ("Tracking: 1Z260AT50346207055", "1Z260AT50346207055"),  # UPS
            ("Tracking Number: 123456789012", "123456789012"),  # Generic numeric
        ]

        for text, expected in test_cases:
            entities = extractor.extract_packing_slip_entities(text)
            assert entities["tracking_number"] == expected, \
                f"Expected {expected}, got {entities['tracking_number']}"

        print(f"✓ Tracking number formats recognized: {len(test_cases)}")

        return True
    except Exception as e:
        print(f"✗ Tracking number format test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_line_item_extraction():
    """Test line item extraction with various formats"""
    try:
        from src.extraction.entity_extractor import EntityExtractor

        extractor = EntityExtractor()

        text = """
        Items Shipped:
        10 ea Stainless Steel Bolts 1/4"
        3 pcs Rubber Gasket 2" ID
        1 unit Emergency Bilge Pump
        """

        entities = extractor.extract_packing_slip_entities(text)

        assert len(entities["line_items"]) == 3, \
            f"Expected 3 line items, got {len(entities['line_items'])}"

        # Check first item
        assert entities["line_items"][0]["quantity"] == 10
        assert "Stainless" in entities["line_items"][0]["description"]

        print(f"✓ Line item extraction working")
        print(f"  Items extracted: {len(entities['line_items'])}")

        return True
    except Exception as e:
        print(f"✗ Line item extraction test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_confidence_calculation():
    """Test extraction confidence scoring"""
    try:
        from src.extraction.entity_extractor import EntityExtractor

        extractor = EntityExtractor()

        # Complete extraction (high confidence)
        complete_text = """
        Order: ORD-2024-001
        Tracking: 1Z123456789012345678
        1 ea Test Item
        """
        result = extractor.extract_packing_slip_entities(complete_text)
        assert result["extraction_confidence"] >= 0.8, \
            f"Complete extraction should have high confidence: {result['extraction_confidence']}"
        print(f"✓ Complete extraction confidence: {result['extraction_confidence']:.0%}")

        # Partial extraction (medium confidence)
        partial_text = "Order: ORD-2024-002"
        result = extractor.extract_packing_slip_entities(partial_text)
        assert 0.2 <= result["extraction_confidence"] <= 0.6, \
            f"Partial extraction should have medium confidence: {result['extraction_confidence']}"
        print(f"✓ Partial extraction confidence: {result['extraction_confidence']:.0%}")

        # No extraction (low confidence)
        empty_text = "This is random text with no entities"
        result = extractor.extract_packing_slip_entities(empty_text)
        assert result["extraction_confidence"] == 0.0, \
            f"No extraction should have zero confidence: {result['extraction_confidence']}"
        print(f"✓ No extraction confidence: {result['extraction_confidence']:.0%}")

        return True
    except Exception as e:
        print(f"✗ Confidence calculation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_empty_text_handling():
    """Test handling of empty or None text"""
    try:
        from src.extraction.entity_extractor import EntityExtractor

        extractor = EntityExtractor()

        # Empty string
        result = extractor.extract_packing_slip_entities("")
        assert result["order_number"] is None
        assert result["tracking_number"] is None
        assert len(result["line_items"]) == 0

        # None
        result = extractor.extract_packing_slip_entities(None)
        assert result["order_number"] is None

        print(f"✓ Empty text handled correctly")

        return True
    except Exception as e:
        print(f"✗ Empty text handling failed: {e}")
        return False

def run_phase_12():
    """Run all Phase 12 tests"""
    print("\n" + "="*60)
    print("PHASE 12: Create EntityExtractor Class (Packing Slip)")
    print("="*60 + "\n")

    results = []

    results.append(("Extract packing slip entities", test_extract_packing_slip_entities()))
    results.append(("Order number formats", test_order_number_formats()))
    results.append(("Tracking number formats", test_tracking_number_formats()))
    results.append(("Line item extraction", test_line_item_extraction()))
    results.append(("Confidence calculation", test_confidence_calculation()))
    results.append(("Empty text handling", test_empty_text_handling()))

    print("\n" + "-"*60)
    print("PHASE 12 RESULTS:")
    print("-"*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ PHASE 12: COMPLETE - Entity extraction works")
        return True
    else:
        print(f"\n❌ PHASE 12: FAILED - {total - passed} tests broken")
        return False

if __name__ == "__main__":
    success = run_phase_12()
    sys.exit(0 if success else 1)
