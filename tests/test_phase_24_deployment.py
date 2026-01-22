"""
PHASE 24: Deployment Verification
Verify system is ready for production deployment
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_environment_variables():
    """Test that required environment variables are configured"""
    try:
        from src.config import settings

        # Check OCR engine
        assert settings.ocr_engine is not None, "ocr_engine should be set"
        assert settings.ocr_engine in ["tesseract", "google_vision", "surya", "aws_textract"], \
            f"ocr_engine should be valid, got {settings.ocr_engine}"

        # Check Supabase configuration (optional for local testing)
        # Note: These can be None in development, so just check they're accessible
        _ = settings.next_public_supabase_url
        _ = settings.supabase_service_role_key

        print(f"✓ Environment variables configured")
        print(f"  OCR Engine: {settings.ocr_engine}")
        if settings.next_public_supabase_url:
            print(f"  Supabase URL: {settings.next_public_supabase_url[:30]}...")

        return True
    except Exception as e:
        print(f"✗ Environment variables test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_required_dependencies():
    """Test that all required Python packages are installed"""
    try:
        # Map package names to their import names
        required_packages = {
            "fastapi": "fastapi",
            "Pillow": "PIL",
            "pytesseract": "pytesseract",
            "supabase": "supabase",
            "pydantic": "pydantic",
            "structlog": "structlog",
            "rapidfuzz": "rapidfuzz"
        }

        missing = []
        for package_name, import_name in required_packages.items():
            try:
                __import__(import_name)
            except ImportError:
                missing.append(package_name)

        assert len(missing) == 0, f"Missing packages: {missing}"

        print(f"✓ All required dependencies installed")
        print(f"  Verified: {', '.join(required_packages.keys())}")

        return True
    except Exception as e:
        print(f"✗ Dependencies test failed: {e}")
        return False

def test_ocr_engine_availability():
    """Test that OCR engine is available and working"""
    try:
        from src.ocr.ocr_factory import OCRFactory

        engine = OCRFactory.get_ocr_engine()
        assert engine is not None, "OCR engine should be initialized"

        engine_name = engine.get_engine_name()
        assert engine_name in ["tesseract", "google_vision", "surya"], \
            f"Invalid engine name: {engine_name}"

        print(f"✓ OCR engine available: {engine_name}")

        # Check Tesseract binary if using Tesseract
        if engine_name == "tesseract":
            import pytesseract
            import shutil
            tesseract_path = shutil.which('tesseract')
            assert tesseract_path is not None, "Tesseract binary not found"
            print(f"  Tesseract path: {tesseract_path}")

        return True
    except Exception as e:
        print(f"✗ OCR engine test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_database_connectivity():
    """Test that database connection works"""
    try:
        from src.database import get_supabase_service

        supabase = get_supabase_service()
        assert supabase is not None, "Supabase client should be initialized"

        # Test simple query
        result = supabase.table("pms_orders").select("id").limit(1).execute()
        assert result is not None, "Database query should return result"

        print(f"✓ Database connectivity works")
        print(f"  Found {len(result.data)} test record(s)")

        return True
    except Exception as e:
        print(f"✗ Database connectivity test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_router_configuration():
    """Test that API routes are properly configured"""
    try:
        from src.api.routes import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        # Check that routes are registered
        assert len(app.routes) > 0, "App should have routes"

        route_paths = [route.path for route in app.routes if hasattr(route, 'path')]
        assert any('/upload' in path for path in route_paths), "Upload route should exist"
        assert any('/health' in path for path in route_paths), "Health route should exist"

        print(f"✓ API router configured correctly")
        print(f"  Total routes: {len(app.routes)}")
        print(f"  Endpoints: {', '.join([p for p in route_paths if '/api/' in p])}")

        return True
    except Exception as e:
        print(f"✗ API router test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_logging_configuration():
    """Test that logging is properly configured"""
    try:
        from src.logger import get_logger

        logger = get_logger(__name__)
        assert logger is not None, "Logger should be initialized"

        # Test logging
        logger.info("Deployment verification test")

        print(f"✓ Logging configured correctly")

        return True
    except Exception as e:
        print(f"✗ Logging test failed: {e}")
        return False

def test_rate_limiter_configuration():
    """Test that rate limiter is configured"""
    try:
        from src.intake.rate_limiter import RateLimiter
        from src.config import settings

        limiter = RateLimiter()
        assert limiter is not None, "Rate limiter should be initialized"

        max_uploads = settings.max_uploads_per_hour
        assert max_uploads > 0, "max_uploads_per_hour should be positive"

        print(f"✓ Rate limiter configured")
        print(f"  Max uploads per hour: {max_uploads}")

        return True
    except Exception as e:
        print(f"✗ Rate limiter test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_temp_storage_directory():
    """Test that temp storage directory can be created"""
    try:
        import os
        from uuid import uuid4

        # Create temp directory
        yacht_id = uuid4()
        temp_dir = os.path.join("temp_uploads", str(yacht_id))
        os.makedirs(temp_dir, exist_ok=True)

        assert os.path.exists(temp_dir), "Temp directory should exist"
        assert os.access(temp_dir, os.W_OK), "Temp directory should be writable"

        # Cleanup
        os.rmdir(temp_dir)

        print(f"✓ Temp storage directory can be created")

        return True
    except Exception as e:
        print(f"✗ Temp storage test failed: {e}")
        return False

def run_phase_24():
    """Run all Phase 24 tests"""
    print("\n" + "="*60)
    print("PHASE 24: Deployment Verification")
    print("="*60 + "\n")

    results = []

    results.append(("Environment variables", test_environment_variables()))
    results.append(("Required dependencies", test_required_dependencies()))
    results.append(("OCR engine availability", test_ocr_engine_availability()))
    results.append(("Database connectivity", test_database_connectivity()))
    results.append(("API router configuration", test_api_router_configuration()))
    results.append(("Logging configuration", test_logging_configuration()))
    results.append(("Rate limiter configuration", test_rate_limiter_configuration()))
    results.append(("Temp storage directory", test_temp_storage_directory()))

    print("\n" + "-"*60)
    print("PHASE 24 RESULTS:")
    print("-"*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ PHASE 24: COMPLETE - System ready for deployment")
        return True
    else:
        print(f"\n❌ PHASE 24: FAILED - {total - passed} tests broken")
        return False

if __name__ == "__main__":
    success = run_phase_24()
    sys.exit(0 if success else 1)
