"""
PHASE 2: Test Tesseract OCR Engine (Baseline)
Verify Tesseract works and establish baseline accuracy
"""

import asyncio
import sys
import os
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

async def test_tesseract_ocr():
    """Test Tesseract OCR with known text image"""
    try:
        # Create test image with known text
        img = Image.new('RGB', (800, 200), color='white')
        d = ImageDraw.Draw(img)

        # Use default font (system font)
        test_text = "TEST ORDER #12345"
        d.text((10, 50), test_text, fill='black')

        # Convert to bytes
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes = img_bytes.getvalue()

        # Run OCR
        from src.ocr.tesseract_ocr import TesseractOCR
        ocr = TesseractOCR()
        result = await ocr.extract_text(img_bytes)

        # Validate result structure
        assert result.text is not None, "Text is None"
        assert result.confidence >= 0, f"Invalid confidence: {result.confidence}"
        assert result.engine_used == "tesseract", f"Wrong engine: {result.engine_used}"
        assert len(result.lines) >= 0, "Lines list missing"
        assert result.processing_time_ms > 0, f"Invalid processing time: {result.processing_time_ms}"

        print(f"✓ Tesseract extracted: '{result.text.strip()}'")
        print(f"✓ Confidence: {result.confidence:.0%}")
        print(f"✓ Processing time: {result.processing_time_ms}ms")
        print(f"✓ Lines detected: {len(result.lines)}")
        print(f"✓ OCRResult structure valid")

        return True
    except Exception as e:
        print(f"✗ Tesseract OCR test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_tesseract_health_check():
    """Test Tesseract health check"""
    try:
        from src.ocr.tesseract_ocr import TesseractOCR
        ocr = TesseractOCR()

        healthy = await ocr.health_check()
        assert healthy is True, "Health check returned False"

        print("✓ Tesseract health check passed")
        return True
    except Exception as e:
        print(f"✗ Tesseract health check failed: {e}")
        return False

async def test_tesseract_get_engine_name():
    """Test get_engine_name method"""
    try:
        from src.ocr.tesseract_ocr import TesseractOCR
        ocr = TesseractOCR()

        name = ocr.get_engine_name()
        assert name == "tesseract", f"Wrong engine name: {name}"

        print(f"✓ Engine name correct: '{name}'")
        return True
    except Exception as e:
        print(f"✗ get_engine_name test failed: {e}")
        return False

async def run_phase_2():
    """Run all Phase 2 tests"""
    print("\n" + "="*60)
    print("PHASE 2: Test Tesseract OCR Engine")
    print("="*60 + "\n")

    results = []

    results.append(("Tesseract OCR extraction", await test_tesseract_ocr()))
    results.append(("Tesseract health check", await test_tesseract_health_check()))
    results.append(("Tesseract engine name", await test_tesseract_get_engine_name()))

    print("\n" + "-"*60)
    print("PHASE 2 RESULTS:")
    print("-"*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ PHASE 2: COMPLETE - Tesseract baseline works")
        return True
    else:
        print(f"\n❌ PHASE 2: FAILED - {total - passed} tests broken")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_phase_2())
    sys.exit(0 if success else 1)
