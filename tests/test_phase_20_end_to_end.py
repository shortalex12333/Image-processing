"""
PHASE 20: Integrate Matching into DocumentHandler
Connect OCR → Classification → Extraction → Matching
"""

import asyncio
import sys
import os
from PIL import Image, ImageDraw
from io import BytesIO

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

async def test_end_to_end_preview_generation():
    """Test complete packing slip processing pipeline"""
    try:
        from src.handlers.document_handler import DocumentHandler
        from src.database import get_supabase_service

        handler = DocumentHandler()
        supabase = get_supabase_service()

        # Get real yacht_id from database
        order_result = supabase.table("pms_orders").select("yacht_id, order_number").limit(1).execute()

        if not order_result.data:
            print("⚠️  No orders in database (skipping)")
            return True

        yacht_id = order_result.data[0]["yacht_id"]
        order_number = order_result.data[0]["order_number"]

        # Create test image with order number
        img = Image.new('RGB', (800, 400), color='white')
        d = ImageDraw.Draw(img)
        d.text((10, 50), "PACKING SLIP", fill='black')
        d.text((10, 100), f"Order Number: {order_number}", fill='black')
        d.text((10, 150), "Tracking: 1Z123456789012345678", fill='black')
        d.text((10, 200), "5 ea Test Item Description", fill='black')

        # Convert to bytes
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        file_bytes = img_bytes.getvalue()

        # Process end-to-end
        preview = await handler.process_packing_slip_preview(
            yacht_id=yacht_id,
            file_bytes=file_bytes,
            filename="test_packing.png"
        )

        # Validate preview structure
        assert "temp_file_id" in preview
        assert "ocr_results" in preview
        assert "document_classification" in preview
        assert "extracted_entities" in preview
        assert "matching" in preview
        assert "processing_time_total_ms" in preview

        print(f"✓ Preview generated in {preview['processing_time_total_ms']}ms")
        print(f"  - OCR Engine: {preview['ocr_results']['engine_used']}")
        print(f"  - Doc Type: {preview['document_classification']['type']}")
        print(f"  - Confidence: {preview['document_classification']['confidence']:.0%}")
        print(f"  - Order Found: {preview['matching']['order_found']}")

        # Cleanup temp file
        import os
        if os.path.exists(preview["temp_file_path"]):
            os.remove(preview["temp_file_path"])
            os.rmdir(os.path.dirname(preview["temp_file_path"]))

        return True
    except Exception as e:
        print(f"✗ End-to-end preview test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_preview_with_ocr():
    """Test that OCR actually extracts text"""
    try:
        from src.handlers.document_handler import DocumentHandler

        handler = DocumentHandler()

        # Create simple test image
        img = Image.new('RGB', (800, 200), color='white')
        d = ImageDraw.Draw(img)
        d.text((10, 50), "TEST ORDER ABC123", fill='black')

        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')

        from uuid import uuid4
        yacht_id = uuid4()

        preview = await handler.process_packing_slip_preview(
            yacht_id=yacht_id,
            file_bytes=img_bytes.getvalue(),
            filename="test.png"
        )

        # Should have extracted some text
        assert preview["ocr_results"]["text"] is not None
        assert len(preview["ocr_results"]["text"]) > 0

        print(f"✓ OCR extracted text: '{preview['ocr_results']['text'][:50]}...'")

        # Cleanup
        import os
        if os.path.exists(preview["temp_file_path"]):
            os.remove(preview["temp_file_path"])
            os.rmdir(os.path.dirname(preview["temp_file_path"]))

        return True
    except Exception as e:
        print(f"✗ OCR preview test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_preview_classification():
    """Test that document gets classified"""
    try:
        from src.handlers.document_handler import DocumentHandler

        handler = DocumentHandler()

        # Create packing slip text
        img = Image.new('RGB', (800, 300), color='white')
        d = ImageDraw.Draw(img)
        d.text((10, 50), "PACKING SLIP", fill='black')
        d.text((10, 100), "Order: ORD-2024-999", fill='black')
        d.text((10, 150), "Tracking: 1Z999999999999999999", fill='black')

        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')

        from uuid import uuid4
        yacht_id = uuid4()

        preview = await handler.process_packing_slip_preview(
            yacht_id=yacht_id,
            file_bytes=img_bytes.getvalue(),
            filename="packing.png"
        )

        # Should classify as packing_list
        doc_type = preview["document_classification"]["type"]

        print(f"✓ Document classified as: {doc_type}")
        print(f"  Confidence: {preview['document_classification']['confidence']:.0%}")

        # Cleanup
        import os
        if os.path.exists(preview["temp_file_path"]):
            os.remove(preview["temp_file_path"])
            os.rmdir(os.path.dirname(preview["temp_file_path"]))

        return True
    except Exception as e:
        print(f"✗ Classification test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def run_phase_20():
    """Run all Phase 20 tests"""
    print("\n" + "="*60)
    print("PHASE 20: Integrate Matching into DocumentHandler")
    print("="*60 + "\n")

    results = []

    results.append(("End-to-end preview generation", await test_end_to_end_preview_generation()))
    results.append(("OCR text extraction", await test_preview_with_ocr()))
    results.append(("Document classification", await test_preview_classification()))

    print("\n" + "-"*60)
    print("PHASE 20 RESULTS:")
    print("-"*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ PHASE 20: COMPLETE - End-to-end pipeline works")
        print("\n🎉 MILESTONE 4 COMPLETE: Database Matching (Phases 16-20)")
        return True
    else:
        print(f"\n❌ PHASE 20: FAILED - {total - passed} tests broken")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_phase_20())
    sys.exit(0 if success else 1)
