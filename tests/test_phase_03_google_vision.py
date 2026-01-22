"""
PHASE 3: Test Google Vision OCR Engine
Verify Google Vision API integration works and beats Tesseract baseline
"""

import asyncio
import sys
import os
from PIL import Image, ImageDraw
from io import BytesIO

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

async def test_google_vision_health():
    """Test Google Vision API health check"""
    try:
        from src.ocr.google_vision_ocr import GoogleVisionOCR

        ocr = GoogleVisionOCR()
        health = await ocr.health_check()

        assert health == True, "Google Vision health check failed - check API key"

        print("✓ Google Vision API accessible")
        return True
    except Exception as e:
        print(f"✗ Google Vision health check failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_google_vision_ocr():
    """Test Google Vision OCR extraction"""
    try:
        # Create same test image as Phase 2
        img = Image.new('RGB', (800, 200), color='white')
        d = ImageDraw.Draw(img)
        test_text = "TEST ORDER #12345"
        d.text((10, 50), test_text, fill='black')

        # Convert to bytes
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes = img_bytes.getvalue()

        # Run OCR
        from src.ocr.google_vision_ocr import GoogleVisionOCR
        ocr = GoogleVisionOCR()
        result = await ocr.extract_text(img_bytes)

        # Validate result structure
        assert result.text is not None, "Text is None"
        assert "12345" in result.text or "ORDER" in result.text, f"Expected text not found in: {result.text}"
        assert result.confidence >= 0.7, f"Confidence too low: {result.confidence:.0%} (expected >70%)"
        assert result.engine_used == "google_vision", f"Wrong engine: {result.engine_used}"
        assert "cost_usd" in result.metadata, "Cost metadata missing"
        assert result.metadata["cost_usd"] == 0.0015, f"Wrong cost: {result.metadata['cost_usd']}"
        assert result.processing_time_ms > 0, f"Invalid processing time: {result.processing_time_ms}"

        print(f"✓ Google Vision extracted: '{result.text.strip()}'")
        print(f"✓ Confidence: {result.confidence:.0%}")
        print(f"✓ Cost: ${result.metadata['cost_usd']}")
        print(f"✓ Processing time: {result.processing_time_ms}ms")
        print(f"✓ Lines detected: {len(result.lines)}")

        return True
    except Exception as e:
        print(f"✗ Google Vision OCR test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_google_vision_get_engine_name():
    """Test get_engine_name method"""
    try:
        from src.ocr.google_vision_ocr import GoogleVisionOCR
        ocr = GoogleVisionOCR()

        name = ocr.get_engine_name()
        assert name == "google_vision", f"Wrong engine name: {name}"

        print(f"✓ Engine name correct: '{name}'")
        return True
    except Exception as e:
        print(f"✗ get_engine_name test failed: {e}")
        return False

async def test_google_vision_vs_tesseract():
    """Compare Google Vision vs Tesseract accuracy"""
    try:
        # Create test image
        img = Image.new('RGB', (800, 200), color='white')
        d = ImageDraw.Draw(img)
        test_text = "TEST ORDER #12345"
        d.text((10, 50), test_text, fill='black')

        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes = img_bytes.getvalue()

        # Test both engines
        from src.ocr.google_vision_ocr import GoogleVisionOCR
        from src.ocr.tesseract_ocr import TesseractOCR

        google_ocr = GoogleVisionOCR()
        tesseract_ocr = TesseractOCR()

        google_result = await google_ocr.extract_text(img_bytes)
        tesseract_result = await tesseract_ocr.extract_text(img_bytes)

        print(f"\n📊 Accuracy Comparison:")
        print(f"   Tesseract: {tesseract_result.confidence:.0%} - '{tesseract_result.text.strip()}'")
        print(f"   Google Vision: {google_result.confidence:.0%} - '{google_result.text.strip()}'")

        # Google Vision should be better
        assert google_result.confidence >= tesseract_result.confidence, \
            f"Google Vision ({google_result.confidence:.0%}) should be >= Tesseract ({tesseract_result.confidence:.0%})"

        print(f"✓ Google Vision accuracy >= Tesseract baseline")

        return True
    except Exception as e:
        print(f"✗ Accuracy comparison failed: {e}")
        return False

async def run_phase_3():
    """Run all Phase 3 tests"""
    print("\n" + "="*60)
    print("PHASE 3: Test Google Vision OCR Engine")
    print("="*60 + "\n")

    results = []

    results.append(("Google Vision health check", await test_google_vision_health()))
    results.append(("Google Vision OCR extraction", await test_google_vision_ocr()))
    results.append(("Google Vision engine name", await test_google_vision_get_engine_name()))
    results.append(("Google Vision vs Tesseract comparison", await test_google_vision_vs_tesseract()))

    print("\n" + "-"*60)
    print("PHASE 3 RESULTS:")
    print("-"*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ PHASE 3: COMPLETE - Google Vision works, better than Tesseract")
        return True
    else:
        print(f"\n❌ PHASE 3: FAILED - {total - passed} tests broken")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_phase_3())
    sys.exit(0 if success else 1)
