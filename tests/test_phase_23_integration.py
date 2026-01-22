"""
PHASE 23: Integration Testing
Test full pipeline with real database integration
"""

import asyncio
import sys
import os
from io import BytesIO
from PIL import Image, ImageDraw

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

async def test_full_pipeline_with_database():
    """Test complete pipeline from API to database"""
    try:
        from fastapi.testclient import TestClient
        from src.api.routes import router
        from fastapi import FastAPI
        from src.database import get_supabase_service

        # Get real yacht_id from database
        supabase = get_supabase_service()
        result = supabase.table("pms_orders").select("yacht_id, order_number").limit(1).execute()

        if not result.data:
            print("⚠️  No orders in database (skipping)")
            return True

        yacht_id = result.data[0]["yacht_id"]
        order_number = result.data[0]["order_number"]

        # Create test image with order number
        img = Image.new('RGB', (800, 400), color='white')
        d = ImageDraw.Draw(img)
        d.text((10, 50), "PACKING SLIP", fill='black')
        d.text((10, 100), f"Order Number: {order_number}", fill='black')
        d.text((10, 150), "Tracking: 1Z123456789012345678", fill='black')
        d.text((10, 200), "5 ea Test Item", fill='black')

        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)

        # Call API
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post(
            "/api/v1/documents/upload",
            params={"yacht_id": yacht_id},
            files={"file": ("test_packing.png", img_bytes, "image/png")}
        )

        assert response.status_code == 200, f"API call failed: {response.status_code}"

        data = response.json()

        # Verify pipeline components
        assert "ocr_results" in data
        assert "document_classification" in data
        assert "extracted_entities" in data
        assert "matching" in data

        print(f"✓ Full pipeline test completed")
        print(f"  OCR Text Length: {len(data['ocr_results']['text'])} chars")
        print(f"  Document Type: {data['document_classification']['type']}")
        print(f"  Order Match: {data['matching']['order_found']}")
        print(f"  Processing Time: {data['processing_time_total_ms']}ms")

        return True
    except Exception as e:
        print(f"✗ Full pipeline test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_ocr_classification_extraction_flow():
    """Test OCR → Classification → Extraction flow"""
    try:
        from src.ocr.ocr_factory import OCRFactory
        from src.extraction.document_classifier import DocumentClassifier
        from src.extraction.entity_extractor import EntityExtractor

        # Create test document text
        test_text = """
        PACKING SLIP

        Order Number: ORD-2024-042
        Tracking: 1Z9999999999999999

        5 ea Widget A
        3 ea Widget B
        """

        # Step 1: OCR (simulated with test text)
        ocr_engine = OCRFactory.get_ocr_engine()
        assert ocr_engine is not None, "OCR engine should be initialized"

        # Step 2: Classification
        classifier = DocumentClassifier()
        classification = classifier.classify(test_text)

        assert classification["type"] == "packing_list", f"Should classify as packing_list, got {classification['type']}"
        assert classification["confidence"] >= 0.5, "Confidence should be >= 0.5"

        # Step 3: Extraction
        extractor = EntityExtractor()
        entities = extractor.extract_packing_slip_entities(test_text)

        assert entities["order_number"] == "ORD-2024-042", f"Should extract order number, got {entities['order_number']}"
        assert entities["tracking_number"] == "1Z9999999999999999", "Should extract tracking"
        assert len(entities["line_items"]) == 2, f"Should extract 2 line items, got {len(entities['line_items'])}"

        print(f"✓ OCR → Classification → Extraction flow works")
        print(f"  Classified as: {classification['type']} ({classification['confidence']:.0%})")
        print(f"  Extracted order: {entities['order_number']}")
        print(f"  Extracted {len(entities['line_items'])} line items")

        return True
    except Exception as e:
        print(f"✗ OCR flow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_database_matching_flow():
    """Test database order matching and shopping list retrieval"""
    try:
        from src.database import get_supabase_service
        from src.reconciliation.order_matcher_by_number import OrderMatcherByNumber

        # Get real order from database
        supabase = get_supabase_service()
        result = supabase.table("pms_orders").select("yacht_id, order_number, id").limit(1).execute()

        if not result.data:
            print("⚠️  No orders in database (skipping)")
            return True

        order = result.data[0]
        yacht_id = order["yacht_id"]
        order_number = order["order_number"]
        order_id = order["id"]

        # Test order matching
        matcher = OrderMatcherByNumber()
        matched_order = await matcher.find_order(yacht_id, order_number)

        assert matched_order is not None, "Should find order in database"
        assert matched_order["order_number"] == order_number, "Should match order number"

        # Test shopping list retrieval
        shopping_list = await matcher.get_shopping_list_items(yacht_id, order_id)

        # Shopping list may be empty, but should return a list
        assert isinstance(shopping_list, list), "Should return list"

        print(f"✓ Database matching flow works")
        print(f"  Found order: {order_number}")
        print(f"  Shopping list items: {len(shopping_list)}")

        return True
    except Exception as e:
        print(f"✗ Database matching test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_temp_storage_cleanup():
    """Test that temp storage is properly managed"""
    try:
        from src.handlers.document_handler import DocumentHandler
        from uuid import uuid4
        import os

        handler = DocumentHandler()

        # Create test file
        img = Image.new('RGB', (100, 100), color='white')
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')

        yacht_id = uuid4()
        temp_file_id, temp_path = await handler._save_to_temp_storage(
            yacht_id=yacht_id,
            file_bytes=img_bytes.getvalue(),
            filename="test.png"
        )

        # Verify file exists
        assert os.path.exists(temp_path), f"Temp file should exist at {temp_path}"

        # Cleanup
        os.remove(temp_path)
        os.rmdir(os.path.dirname(temp_path))

        print(f"✓ Temp storage management works")
        print(f"  Created temp file: {temp_file_id}")
        print(f"  Path: {temp_path}")

        return True
    except Exception as e:
        print(f"✗ Temp storage test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_error_handling():
    """Test error handling throughout pipeline"""
    try:
        from src.reconciliation.order_matcher_by_number import OrderMatcherByNumber
        from uuid import uuid4

        matcher = OrderMatcherByNumber()

        # Test 1: Non-existent order
        result = await matcher.find_order(
            yacht_id=uuid4(),
            order_number="NONEXISTENT-ORDER-999"
        )

        assert result is None, "Non-existent order should return None"

        # Test 2: Empty shopping list
        shopping_list = await matcher.get_shopping_list_items(
            yacht_id=uuid4(),
            order_id=str(uuid4())
        )

        assert isinstance(shopping_list, list), "Should return empty list for non-existent order"
        assert len(shopping_list) == 0, "Should be empty"

        print(f"✓ Error handling works correctly")
        print(f"  Non-existent order returns None")
        print(f"  Non-existent shopping list returns empty list")

        return True
    except Exception as e:
        print(f"✗ Error handling test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def run_phase_23():
    """Run all Phase 23 tests"""
    print("\n" + "="*60)
    print("PHASE 23: Integration Testing")
    print("="*60 + "\n")

    results = []

    results.append(("Full pipeline with database", await test_full_pipeline_with_database()))
    results.append(("OCR → Classification → Extraction", await test_ocr_classification_extraction_flow()))
    results.append(("Database matching flow", await test_database_matching_flow()))
    results.append(("Temp storage management", await test_temp_storage_cleanup()))
    results.append(("Error handling", await test_error_handling()))

    print("\n" + "-"*60)
    print("PHASE 23 RESULTS:")
    print("-"*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ PHASE 23: COMPLETE - Integration testing works")
        return True
    else:
        print(f"\n❌ PHASE 23: FAILED - {total - passed} tests broken")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_phase_23())
    sys.exit(0 if success else 1)
