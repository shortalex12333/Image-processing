"""
PHASE 11: Create DocumentClassifier Class
Classify documents as packing_list, invoice, PO, or WO
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_packing_slip_classification():
    """Test packing slip classification"""
    try:
        from src.extraction.document_classifier import DocumentClassifier

        classifier = DocumentClassifier()

        # Test packing slip
        packing_text = """
        PACKING SLIP
        Order #: ORD-2024-042
        Tracking: 1Z260AT50346207055
        Ship To: Test Yacht
        """

        result = classifier.classify(packing_text)
        assert result["type"] == "packing_list", f"Expected packing_list, got {result['type']}"
        assert result["confidence"] > 0.7, f"Confidence too low: {result['confidence']:.0%}"

        print(f"✓ Packing slip classified with {result['confidence']:.0%} confidence")
        print(f"  Matched patterns: {len(result['matched_patterns'])}")

        return True
    except Exception as e:
        print(f"✗ Packing slip classification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_invoice_classification():
    """Test invoice classification"""
    try:
        from src.extraction.document_classifier import DocumentClassifier

        classifier = DocumentClassifier()

        invoice_text = """
        INVOICE
        Invoice #: INV-2024-123
        Amount Due: $1,234.56
        Due Date: 2024-02-01
        """

        result = classifier.classify(invoice_text)
        assert result["type"] == "invoice", f"Expected invoice, got {result['type']}"
        assert result["confidence"] > 0.7, f"Confidence too low: {result['confidence']:.0%}"

        print(f"✓ Invoice classified with {result['confidence']:.0%} confidence")
        print(f"  Matched patterns: {len(result['matched_patterns'])}")

        return True
    except Exception as e:
        print(f"✗ Invoice classification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_purchase_order_classification():
    """Test purchase order classification"""
    try:
        from src.extraction.document_classifier import DocumentClassifier

        classifier = DocumentClassifier()

        po_text = """
        PURCHASE ORDER
        P.O. #: PO-2024-789
        Vendor Name: Marine Supply Co
        Requested by: Chief Engineer
        Ship via: UPS Ground
        """

        result = classifier.classify(po_text)
        assert result["type"] == "purchase_order", f"Expected purchase_order, got {result['type']}"
        assert result["confidence"] > 0.7, f"Confidence too low: {result['confidence']:.0%}"

        print(f"✓ Purchase Order classified with {result['confidence']:.0%} confidence")
        print(f"  Matched patterns: {len(result['matched_patterns'])}")

        return True
    except Exception as e:
        print(f"✗ Purchase Order classification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_work_order_classification():
    """Test work order classification"""
    try:
        from src.extraction.document_classifier import DocumentClassifier

        classifier = DocumentClassifier()

        wo_text = """
        WORK ORDER
        W.O. #: WO-2024-456
        Task Description: Replace starboard engine oil filter
        Assigned to: Engine Room Crew
        Equipment ID: ENG-001
        Status: In Progress
        """

        result = classifier.classify(wo_text)
        assert result["type"] == "work_order", f"Expected work_order, got {result['type']}"
        assert result["confidence"] > 0.7, f"Confidence too low: {result['confidence']:.0%}"

        print(f"✓ Work Order classified with {result['confidence']:.0%} confidence")
        print(f"  Matched patterns: {len(result['matched_patterns'])}")

        return True
    except Exception as e:
        print(f"✗ Work Order classification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_unknown_classification():
    """Test unknown document classification"""
    try:
        from src.extraction.document_classifier import DocumentClassifier

        classifier = DocumentClassifier()

        unknown_text = """
        This is some random text that doesn't match any document type.
        It has no indicators of being a business document.
        Just generic content with no identifiable patterns.
        Lorem ipsum dolor sit amet consectetur adipiscing elit.
        """

        result = classifier.classify(unknown_text)
        assert result["type"] == "unknown", f"Expected unknown, got {result['type']}"
        assert result["confidence"] == 0.0, f"Confidence should be 0 for unknown: {result['confidence']}"

        print(f"✓ Unknown document classified correctly with {result['confidence']:.0%} confidence")

        return True
    except Exception as e:
        print(f"✗ Unknown classification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_empty_text():
    """Test classification with empty text"""
    try:
        from src.extraction.document_classifier import DocumentClassifier

        classifier = DocumentClassifier()

        result = classifier.classify("")
        assert result["type"] == "unknown"
        assert result["confidence"] == 0.0

        result2 = classifier.classify(None)
        assert result2["type"] == "unknown"

        print(f"✓ Empty text handled correctly")

        return True
    except Exception as e:
        print(f"✗ Empty text test failed: {e}")
        return False

def run_phase_11():
    """Run all Phase 11 tests"""
    print("\n" + "="*60)
    print("PHASE 11: Create DocumentClassifier Class")
    print("="*60 + "\n")

    results = []

    results.append(("Packing slip classification", test_packing_slip_classification()))
    results.append(("Invoice classification", test_invoice_classification()))
    results.append(("Purchase Order classification", test_purchase_order_classification()))
    results.append(("Work Order classification", test_work_order_classification()))
    results.append(("Unknown document classification", test_unknown_classification()))
    results.append(("Empty text handling", test_empty_text()))

    print("\n" + "-"*60)
    print("PHASE 11 RESULTS:")
    print("-"*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ PHASE 11: COMPLETE - Document classification works")
        return True
    else:
        print(f"\n❌ PHASE 11: FAILED - {total - passed} tests broken")
        return False

if __name__ == "__main__":
    success = run_phase_11()
    sys.exit(0 if success else 1)
