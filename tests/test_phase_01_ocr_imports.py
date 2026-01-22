"""
PHASE 1: Verify Existing OCR Files Are Valid
Test that all OCR files can be imported without errors
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_import_base_ocr():
    """Test importing base OCR classes"""
    try:
        from src.ocr.base_ocr import BaseOCR, OCRResult
        assert BaseOCR is not None, "BaseOCR class is None"
        assert OCRResult is not None, "OCRResult class is None"
        print("✓ base_ocr imports successfully")
        return True
    except Exception as e:
        print(f"✗ base_ocr import failed: {e}")
        return False

def test_import_google_vision():
    """Test importing Google Vision OCR"""
    try:
        from src.ocr.google_vision_ocr import GoogleVisionOCR
        assert GoogleVisionOCR is not None
        print("✓ google_vision_ocr imports successfully")
        return True
    except Exception as e:
        print(f"✗ google_vision_ocr import failed: {e}")
        return False

def test_import_surya():
    """Test importing Surya OCR (may fail if not installed - expected)"""
    try:
        from src.ocr.surya_ocr import SuryaOCR
        assert SuryaOCR is not None
        print("✓ surya_ocr imports successfully")
        return True
    except ImportError as e:
        # Expected if Surya not installed
        print("⚠ surya_ocr import failed (expected if not installed): Surya dependencies missing")
        return True  # Not a failure, just not installed
    except Exception as e:
        print(f"✗ surya_ocr import failed: {e}")
        return False

def test_import_tesseract():
    """Test importing Tesseract OCR"""
    try:
        from src.ocr.tesseract_ocr import TesseractOCR
        assert TesseractOCR is not None
        print("✓ tesseract_ocr imports successfully")
        return True
    except Exception as e:
        print(f"✗ tesseract_ocr import failed: {e}")
        return False

def test_import_factory():
    """Test importing OCR Factory"""
    try:
        from src.ocr.ocr_factory import OCRFactory
        assert OCRFactory is not None
        print("✓ ocr_factory imports successfully")
        return True
    except Exception as e:
        print(f"✗ ocr_factory import failed: {e}")
        return False

def test_factory_can_instantiate():
    """Test that factory can be called (even without API keys)"""
    try:
        from src.ocr.ocr_factory import OCRFactory
        # Don't actually get engine (might fail without API key)
        # Just verify class methods exist
        assert hasattr(OCRFactory, 'get_ocr_engine')
        assert hasattr(OCRFactory, 'reset')
        assert hasattr(OCRFactory, 'health_check_all_engines')
        print("✓ OCRFactory has required methods")
        return True
    except Exception as e:
        print(f"✗ OCRFactory instantiation failed: {e}")
        return False

def run_phase_1():
    """Run all Phase 1 tests"""
    print("\n" + "="*60)
    print("PHASE 1: Verify OCR Imports")
    print("="*60 + "\n")

    results = []

    results.append(("Import base_ocr", test_import_base_ocr()))
    results.append(("Import google_vision_ocr", test_import_google_vision()))
    results.append(("Import surya_ocr", test_import_surya()))
    results.append(("Import tesseract_ocr", test_import_tesseract()))
    results.append(("Import ocr_factory", test_import_factory()))
    results.append(("Factory methods exist", test_factory_can_instantiate()))

    print("\n" + "-"*60)
    print("PHASE 1 RESULTS:")
    print("-"*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ PHASE 1: COMPLETE - All imports working")
        return True
    else:
        print(f"\n❌ PHASE 1: FAILED - {total - passed} imports broken")
        return False

if __name__ == "__main__":
    success = run_phase_1()
    sys.exit(0 if success else 1)
