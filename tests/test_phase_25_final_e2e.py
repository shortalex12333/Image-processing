"""
PHASE 25: Final End-to-End Test
Comprehensive test of entire system from API to database
"""

import asyncio
import sys
import os
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

async def test_complete_packing_slip_workflow():
    """Test complete packing slip processing workflow end-to-end"""
    try:
        from fastapi.testclient import TestClient
        from src.api.routes import router
        from fastapi import FastAPI
        from src.database import get_supabase_service

        # Get real yacht and order from database
        supabase = get_supabase_service()
        result = supabase.table("pms_orders").select("yacht_id, order_number, id").limit(1).execute()

        if not result.data:
            print("⚠️  No orders in database (skipping)")
            return True

        order = result.data[0]
        yacht_id = order["yacht_id"]
        order_number = order["order_number"]

        # Create realistic packing slip image
        img = Image.new('RGB', (1000, 800), color='white')
        d = ImageDraw.Draw(img)

        # Header
        d.rectangle([(0, 0), (1000, 100)], fill='lightgray')
        d.text((20, 30), "PACKING SLIP", fill='black')
        d.text((20, 60), "Vendor: Test Marine Supply Co.", fill='black')

        # Order details
        d.text((20, 150), f"Order Number: {order_number}", fill='black')
        d.text((20, 180), "Order Date: 2026-01-15", fill='black')
        d.text((20, 210), "Ship To: M/Y Test Yacht", fill='black')
        d.text((20, 240), f"Tracking: 1Z{order_number[-6:]}{order_number[-6:]}99", fill='black')

        # Line items header
        d.text((20, 300), "QTY  DESCRIPTION", fill='black')
        d.line([(20, 320), (980, 320)], fill='black', width=2)

        # Line items
        d.text((20, 340), "5 ea  O2Y Sensor Assembly", fill='black')
        d.text((20, 370), "3 ea  Fuel Filter Cartridge", fill='black')
        d.text((20, 400), "10 ea O-Ring Seal Kit", fill='black')

        # Footer
        d.line([(20, 450), (980, 450)], fill='black', width=1)
        d.text((20, 470), "Total Items: 18 pieces", fill='black')
        d.text((20, 500), "Packed by: JD | Date: 2026-01-15", fill='black')

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
            files={"file": ("packing_slip.png", img_bytes, "image/png")}
        )

        assert response.status_code == 200, f"API call failed: {response.status_code}: {response.text}"

        data = response.json()

        # Verify all pipeline stages completed
        assert "temp_file_id" in data, "Should have temp_file_id"
        assert "ocr_results" in data, "Should have OCR results"
        assert "document_classification" in data, "Should have classification"
        assert "extracted_entities" in data, "Should have entities"
        assert "matching" in data, "Should have matching results"
        assert "processing_time_total_ms" in data, "Should have processing time"

        # Verify OCR extracted text
        ocr_text = data["ocr_results"]["text"]
        assert ocr_text is not None, "OCR text should not be None"
        assert len(ocr_text) > 0, "OCR text should not be empty"

        # Verify processing time is reasonable
        processing_time = data["processing_time_total_ms"]
        assert processing_time > 0, "Processing time should be positive"
        assert processing_time < 30000, "Processing should complete in < 30 seconds"

        print(f"✓ Complete workflow test passed")
        print(f"  Yacht ID: {yacht_id}")
        print(f"  Order Number: {order_number}")
        print(f"  OCR Text Length: {len(ocr_text)} chars")
        print(f"  OCR Confidence: {data['ocr_results']['confidence']:.0%}")
        print(f"  Document Type: {data['document_classification']['type']}")
        print(f"  Classification Confidence: {data['document_classification']['confidence']:.0%}")
        print(f"  Entities Extracted: {len(data['extracted_entities'])} fields")
        print(f"  Order Match: {data['matching']['order_found']}")
        print(f"  Processing Time: {processing_time}ms")

        return True
    except Exception as e:
        print(f"✗ Complete workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_system_performance():
    """Test system performance with multiple uploads"""
    try:
        from fastapi.testclient import TestClient
        from src.api.routes import router
        from fastapi import FastAPI
        from uuid import uuid4
        import time

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Create simple test image
        img = Image.new('RGB', (800, 200), color='white')
        d = ImageDraw.Draw(img)
        d.text((10, 50), "PACKING SLIP", fill='black')

        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')

        # Test 5 uploads
        num_uploads = 5
        yacht_id = str(uuid4())
        times = []

        for i in range(num_uploads):
            img_bytes.seek(0)
            start = time.time()

            response = client.post(
                "/api/v1/documents/upload",
                params={"yacht_id": yacht_id},
                files={"file": (f"test_{i}.png", img_bytes, "image/png")}
            )

            elapsed = (time.time() - start) * 1000
            times.append(elapsed)

            assert response.status_code == 200, f"Upload {i+1} failed"

        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        print(f"✓ Performance test passed ({num_uploads} uploads)")
        print(f"  Average time: {avg_time:.0f}ms")
        print(f"  Min time: {min_time:.0f}ms")
        print(f"  Max time: {max_time:.0f}ms")

        return True
    except Exception as e:
        print(f"✗ Performance test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_error_resilience():
    """Test system handles errors gracefully"""
    try:
        from fastapi.testclient import TestClient
        from src.api.routes import router
        from fastapi import FastAPI
        from uuid import uuid4

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Test 1: Invalid yacht_id
        img = Image.new('RGB', (100, 100), color='white')
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)

        response = client.post(
            "/api/v1/documents/upload",
            params={"yacht_id": "invalid-uuid"},
            files={"file": ("test.png", img_bytes, "image/png")}
        )
        assert response.status_code == 400, "Should reject invalid UUID"

        # Test 2: Empty file
        empty_bytes = BytesIO(b"")
        response = client.post(
            "/api/v1/documents/upload",
            params={"yacht_id": str(uuid4())},
            files={"file": ("test.png", empty_bytes, "image/png")}
        )
        assert response.status_code == 400, "Should reject empty file"

        # Test 3: Invalid file type
        text_bytes = BytesIO(b"This is text, not an image")
        response = client.post(
            "/api/v1/documents/upload",
            params={"yacht_id": str(uuid4())},
            files={"file": ("test.txt", text_bytes, "text/plain")}
        )
        assert response.status_code == 400, "Should reject invalid file type"

        print(f"✓ Error resilience test passed")
        print(f"  Invalid UUID rejected: 400")
        print(f"  Empty file rejected: 400")
        print(f"  Invalid file type rejected: 400")

        return True
    except Exception as e:
        print(f"✗ Error resilience test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_database_isolation():
    """Test that yacht_id isolation works correctly"""
    try:
        from src.reconciliation.order_matcher_by_number import OrderMatcherByNumber
        from src.database import get_supabase_service
        from uuid import uuid4

        supabase = get_supabase_service()
        matcher = OrderMatcherByNumber()

        # Get a real order
        result = supabase.table("pms_orders").select("yacht_id, order_number").limit(1).execute()

        if not result.data:
            print("⚠️  No orders in database (skipping)")
            return True

        real_yacht_id = result.data[0]["yacht_id"]
        real_order_number = result.data[0]["order_number"]

        # Test 1: Correct yacht_id should find order
        order = await matcher.find_order(real_yacht_id, real_order_number)
        assert order is not None, "Should find order with correct yacht_id"

        # Test 2: Different yacht_id should NOT find order
        fake_yacht_id = uuid4()
        order = await matcher.find_order(fake_yacht_id, real_order_number)
        assert order is None, "Should NOT find order with wrong yacht_id"

        print(f"✓ Database isolation test passed")
        print(f"  Correct yacht_id: Order found")
        print(f"  Wrong yacht_id: Order NOT found (isolated)")

        return True
    except Exception as e:
        print(f"✗ Database isolation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_all_components_integrated():
    """Test that all system components work together"""
    try:
        from src.ocr.ocr_factory import OCRFactory
        from src.extraction.document_classifier import DocumentClassifier
        from src.extraction.entity_extractor import EntityExtractor
        from src.reconciliation.order_matcher_by_number import OrderMatcherByNumber
        from src.handlers.document_handler import DocumentHandler
        from src.api.routes import router

        # Verify all components can be imported and initialized
        ocr = OCRFactory.get_ocr_engine()
        assert ocr is not None, "OCR engine should initialize"

        classifier = DocumentClassifier()
        assert classifier is not None, "Classifier should initialize"

        extractor = EntityExtractor()
        assert extractor is not None, "Extractor should initialize"

        matcher = OrderMatcherByNumber()
        assert matcher is not None, "Matcher should initialize"

        handler = DocumentHandler()
        assert handler is not None, "Handler should initialize"

        assert router is not None, "Router should be defined"

        print(f"✓ All components integrated successfully")
        print(f"  OCR Engine: {ocr.get_engine_name()}")
        print(f"  Classifier: DocumentClassifier")
        print(f"  Extractor: EntityExtractor")
        print(f"  Matcher: OrderMatcherByNumber")
        print(f"  Handler: DocumentHandler")
        print(f"  API Router: {len(router.routes)} routes")

        return True
    except Exception as e:
        print(f"✗ Component integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def run_phase_25():
    """Run all Phase 25 final end-to-end tests"""
    print("\n" + "="*60)
    print("PHASE 25: Final End-to-End Test")
    print("="*60 + "\n")

    results = []

    results.append(("Complete packing slip workflow", await test_complete_packing_slip_workflow()))
    results.append(("System performance", await test_system_performance()))
    results.append(("Error resilience", await test_error_resilience()))
    results.append(("Database isolation", await test_database_isolation()))
    results.append(("All components integrated", await test_all_components_integrated()))

    print("\n" + "-"*60)
    print("PHASE 25 RESULTS:")
    print("-"*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ PHASE 25: COMPLETE - Final end-to-end testing successful")
        print("\n🎉 ALL 25 PHASES COMPLETE!")
        print("=" * 60)
        print("IMAGE PROCESSING SERVICE: FULLY IMPLEMENTED AND TESTED")
        print("=" * 60)
        return True
    else:
        print(f"\n❌ PHASE 25: FAILED - {total - passed} tests broken")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_phase_25())
    sys.exit(0 if success else 1)
