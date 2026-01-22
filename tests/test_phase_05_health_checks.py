"""
PHASE 5: Test Health Check for All Engines
Verify health check endpoint works for all available OCR engines
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

async def test_all_engine_health():
    """Test health_check_all_engines() returns correct status for each engine"""
    try:
        from src.ocr.ocr_factory import OCRFactory

        health = await OCRFactory.health_check_all_engines()

        print("Engine Health Status:")
        for engine, status in health.items():
            status_icon = "✓" if status else "✗"
            status_text = "HEALTHY" if status else "UNAVAILABLE"
            print(f"  {status_icon} {engine}: {status_text}")

        # Verify expected statuses
        assert "google_vision" in health, "google_vision should be in health check results"
        assert "tesseract" in health, "tesseract should be in health check results"
        assert "surya" in health, "surya should be in health check results"

        # Google Vision should be healthy (API key set)
        assert health["google_vision"] == True, "Google Vision should be healthy (API key is set)"

        # Tesseract should be available
        assert health["tesseract"] == True, "Tesseract should be available"

        # Surya should be unavailable (not installed)
        assert health["surya"] == False, "Surya should be unavailable (dependencies not installed)"

        print(f"\n✓ All health checks returned expected results")

        return True
    except Exception as e:
        print(f"✗ Health check test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_individual_health_checks():
    """Test each engine's individual health check"""
    try:
        from src.ocr.google_vision_ocr import GoogleVisionOCR
        from src.ocr.tesseract_ocr import TesseractOCR

        results = []

        # Test Google Vision
        google_ocr = GoogleVisionOCR()
        google_health = await google_ocr.health_check()
        results.append(("Google Vision individual check", google_health))
        print(f"  {'✓' if google_health else '✗'} Google Vision: {'HEALTHY' if google_health else 'UNAVAILABLE'}")

        # Test Tesseract
        tesseract_ocr = TesseractOCR()
        tesseract_health = await tesseract_ocr.health_check()
        results.append(("Tesseract individual check", tesseract_health))
        print(f"  {'✓' if tesseract_health else '✗'} Tesseract: {'HEALTHY' if tesseract_health else 'UNAVAILABLE'}")

        # All available engines should be healthy
        for name, health in results:
            assert health == True, f"{name} should be healthy"

        print(f"\n✓ Individual health checks passed")

        return True
    except Exception as e:
        print(f"✗ Individual health check test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_health_check_performance():
    """Test that health checks are reasonably fast"""
    try:
        import time
        from src.ocr.ocr_factory import OCRFactory

        start_time = time.time()
        health = await OCRFactory.health_check_all_engines()
        elapsed_ms = (time.time() - start_time) * 1000

        # Health checks should complete in reasonable time (< 5 seconds)
        assert elapsed_ms < 5000, f"Health checks took too long: {elapsed_ms:.0f}ms"

        print(f"✓ Health checks completed in {elapsed_ms:.0f}ms")

        return True
    except Exception as e:
        print(f"✗ Health check performance test failed: {e}")
        return False

async def run_phase_5():
    """Run all Phase 5 tests"""
    print("\n" + "="*60)
    print("PHASE 5: Test Health Check for All Engines")
    print("="*60 + "\n")

    results = []

    results.append(("All engines health check", await test_all_engine_health()))
    print()
    results.append(("Individual health checks", await test_individual_health_checks()))
    print()
    results.append(("Health check performance", await test_health_check_performance()))

    print("\n" + "-"*60)
    print("PHASE 5 RESULTS:")
    print("-"*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ PHASE 5: COMPLETE - Health checks working")
        return True
    else:
        print(f"\n❌ PHASE 5: FAILED - {total - passed} tests broken")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_phase_5())
    sys.exit(0 if success else 1)
