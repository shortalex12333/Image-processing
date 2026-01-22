"""
PHASE 10: Add Rate Limiting Check
Integrate existing RateLimiter into DocumentHandler
"""

import asyncio
import sys
import os
from uuid import uuid4

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

async def test_document_handler_has_rate_limiter():
    """Test that DocumentHandler has RateLimiter"""
    try:
        from src.handlers.document_handler import DocumentHandler

        handler = DocumentHandler()
        assert handler.rate_limiter is not None, "rate_limiter is None"

        print("✓ DocumentHandler has RateLimiter")

        return True
    except Exception as e:
        print(f"✗ RateLimiter check failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_check_rate_limit_method_exists():
    """Test that _check_rate_limit method exists and is callable"""
    try:
        from src.handlers.document_handler import DocumentHandler

        handler = DocumentHandler()
        assert hasattr(handler, '_check_rate_limit'), "_check_rate_limit method missing"
        assert callable(handler._check_rate_limit), "_check_rate_limit not callable"

        print("✓ _check_rate_limit method exists")

        return True
    except Exception as e:
        print(f"✗ Method existence check failed: {e}")
        return False

async def test_rate_limit_imports():
    """Test that RateLimitExceeded can be imported"""
    try:
        from src.handlers.document_handler import RateLimitExceeded
        from src.intake.rate_limiter import RateLimiter

        print("✓ RateLimitExceeded and RateLimiter imported successfully")

        return True
    except Exception as e:
        print(f"✗ Import check failed: {e}")
        return False

async def test_check_rate_limit_no_limit():
    """Test _check_rate_limit with yacht that hasn't hit limit"""
    try:
        from src.handlers.document_handler import DocumentHandler

        handler = DocumentHandler()

        # Use random yacht_id (won't have any uploads in DB)
        yacht_id = uuid4()

        # Should not raise exception (no uploads for this yacht)
        await handler._check_rate_limit(yacht_id)

        print("✓ _check_rate_limit passes for yacht below limit")

        return True
    except Exception as e:
        print(f"✗ Rate limit check failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_rate_limiter_configuration():
    """Test that rate limiter uses correct configuration"""
    try:
        from src.config import settings

        # Verify rate limit settings exist
        assert hasattr(settings, 'max_uploads_per_hour'), "max_uploads_per_hour not in settings"
        assert hasattr(settings, 'upload_rate_limit_window_seconds'), "upload_rate_limit_window_seconds not in settings"

        # Verify default values (from .env.example)
        assert settings.max_uploads_per_hour == 50, f"Expected 50, got {settings.max_uploads_per_hour}"
        assert settings.upload_rate_limit_window_seconds == 3600, f"Expected 3600, got {settings.upload_rate_limit_window_seconds}"

        print(f"✓ Rate limiter configured: {settings.max_uploads_per_hour} uploads per hour")

        return True
    except Exception as e:
        print(f"✗ Configuration check failed: {e}")
        return False

async def test_rate_limit_exception_structure():
    """Test RateLimitExceeded exception structure"""
    try:
        from src.intake.rate_limiter import RateLimitExceeded

        # Create exception
        exc = RateLimitExceeded(
            current_count=51,
            limit=50,
            retry_after_seconds=3600
        )

        # Verify attributes
        assert exc.current_count == 51
        assert exc.limit == 50
        assert exc.retry_after_seconds == 3600
        assert "51/50" in str(exc)

        print("✓ RateLimitExceeded exception has correct structure")

        return True
    except Exception as e:
        print(f"✗ Exception structure check failed: {e}")
        return False

async def run_phase_10():
    """Run all Phase 10 tests"""
    print("\n" + "="*60)
    print("PHASE 10: Add Rate Limiting Check")
    print("="*60 + "\n")

    results = []

    results.append(("DocumentHandler has RateLimiter", await test_document_handler_has_rate_limiter()))
    results.append(("_check_rate_limit method exists", await test_check_rate_limit_method_exists()))
    results.append(("Rate limit imports work", await test_rate_limit_imports()))
    results.append(("Rate limit check passes below limit", await test_check_rate_limit_no_limit()))
    results.append(("Rate limiter configuration", await test_rate_limiter_configuration()))
    results.append(("RateLimitExceeded structure", await test_rate_limit_exception_structure()))

    print("\n" + "-"*60)
    print("PHASE 10 RESULTS:")
    print("-"*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ PHASE 10: COMPLETE - Rate limiting integrated")
        print("\n📊 MILESTONE 2 COMPLETE: Document Upload (Phases 6-10)")
        return True
    else:
        print(f"\n❌ PHASE 10: FAILED - {total - passed} tests broken")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_phase_10())
    sys.exit(0 if success else 1)
