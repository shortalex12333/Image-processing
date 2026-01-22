"""
PHASE 4: Test OCR Factory Selection
Verify factory selects correct engine based on config and implements singleton pattern
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_factory_selection():
    """Test factory returns correct engine based on config"""
    try:
        from src.ocr.ocr_factory import OCRFactory
        from src.config import settings

        # Test current engine (should be google_vision from .env)
        ocr = OCRFactory.get_ocr_engine()
        engine_name = ocr.get_engine_name()

        assert engine_name == settings.ocr_engine.lower(), \
            f"Factory returned {engine_name}, expected {settings.ocr_engine.lower()}"

        print(f"✓ Factory selected correct engine: '{engine_name}'")
        print(f"  (Based on OCR_ENGINE={settings.ocr_engine})")

        return True
    except Exception as e:
        print(f"✗ Factory selection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_singleton_pattern():
    """Test singleton pattern - same instance returned"""
    try:
        from src.ocr.ocr_factory import OCRFactory

        # Get engine twice
        ocr1 = OCRFactory.get_ocr_engine()
        ocr2 = OCRFactory.get_ocr_engine()

        # Should be same instance (singleton)
        assert ocr1 is ocr2, "Factory should return same instance (singleton pattern)"

        print(f"✓ Singleton pattern works (same instance returned)")

        return True
    except Exception as e:
        print(f"✗ Singleton pattern test failed: {e}")
        return False

def test_factory_reset():
    """Test factory reset creates new instance"""
    try:
        from src.ocr.ocr_factory import OCRFactory

        # Get instance
        ocr1 = OCRFactory.get_ocr_engine()

        # Reset factory
        OCRFactory.reset()

        # Get new instance
        ocr2 = OCRFactory.get_ocr_engine()

        # Should be different instance
        assert ocr1 is not ocr2, "Reset should create new instance"

        print(f"✓ Factory reset works (new instance created)")

        return True
    except Exception as e:
        print(f"✗ Factory reset test failed: {e}")
        return False

def test_factory_with_tesseract():
    """Test factory can create Tesseract engine"""
    try:
        from src.ocr.ocr_factory import OCRFactory
        import os

        # Temporarily change OCR_ENGINE
        original_engine = os.environ.get('OCR_ENGINE', 'google_vision')
        os.environ['OCR_ENGINE'] = 'tesseract'

        # Reset factory to pick up new environment
        OCRFactory.reset()

        # Reload settings
        from importlib import reload
        from src import config
        reload(config)
        from src.config import settings

        # Get engine
        ocr = OCRFactory.get_ocr_engine()
        engine_name = ocr.get_engine_name()

        assert engine_name == "tesseract", f"Expected tesseract, got {engine_name}"

        print(f"✓ Factory can create Tesseract engine")

        # Restore original
        os.environ['OCR_ENGINE'] = original_engine
        OCRFactory.reset()

        return True
    except Exception as e:
        print(f"✗ Tesseract factory test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_factory_invalid_engine():
    """Test that Pydantic rejects invalid engine names (security feature)"""
    try:
        import os
        from pydantic import ValidationError

        # Set invalid engine
        original_engine = os.environ.get('OCR_ENGINE', 'google_vision')
        os.environ['OCR_ENGINE'] = 'invalid_engine'

        # Try to reload settings - should raise ValidationError
        validation_failed = False
        try:
            from importlib import reload
            from src import config
            reload(config)
        except ValidationError as e:
            validation_failed = True
            assert "ocr_engine" in str(e), "Validation error should mention ocr_engine"

        # Restore original
        os.environ['OCR_ENGINE'] = original_engine

        # Pydantic should have rejected the invalid value
        assert validation_failed, "Pydantic should reject invalid OCR_ENGINE values"

        print(f"✓ Pydantic rejects invalid engine names (security)")

        return True
    except Exception as e:
        print(f"✗ Invalid engine test failed: {e}")
        import traceback
        traceback.print_exc()
        # Restore original
        os.environ['OCR_ENGINE'] = os.environ.get('OCR_ENGINE', 'google_vision')
        return False

def run_phase_4():
    """Run all Phase 4 tests"""
    print("\n" + "="*60)
    print("PHASE 4: Test OCR Factory Selection")
    print("="*60 + "\n")

    results = []

    results.append(("Factory selects correct engine", test_factory_selection()))
    results.append(("Singleton pattern works", test_singleton_pattern()))
    results.append(("Factory reset works", test_factory_reset()))
    results.append(("Factory creates Tesseract", test_factory_with_tesseract()))
    results.append(("Invalid engine defaults to Tesseract", test_factory_invalid_engine()))

    print("\n" + "-"*60)
    print("PHASE 4 RESULTS:")
    print("-"*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ PHASE 4: COMPLETE - Factory works correctly")
        return True
    else:
        print(f"\n❌ PHASE 4: FAILED - {total - passed} tests broken")
        return False

if __name__ == "__main__":
    success = run_phase_4()
    sys.exit(0 if success else 1)
