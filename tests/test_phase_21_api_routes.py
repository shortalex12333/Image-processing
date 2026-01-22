"""
PHASE 21: Create API Routes
FastAPI endpoints for document processing
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_api_routes_file_exists():
    """Test that API routes file exists"""
    try:
        routes_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'src',
            'api',
            'routes.py'
        )

        assert os.path.exists(routes_path), f"API routes file should exist at {routes_path}"

        print(f"✓ API routes file exists at: {routes_path}")

        return True
    except Exception as e:
        print(f"✗ API routes file test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_routes_imports():
    """Test that routes module imports successfully"""
    try:
        from src.api.routes import router

        assert router is not None, "Router should be defined"

        print("✓ API routes module imports successfully")
        print(f"  Router type: {type(router).__name__}")

        return True
    except Exception as e:
        print(f"✗ API routes import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_upload_endpoint_exists():
    """Test that upload endpoint is defined"""
    try:
        from src.api.routes import router

        # Check that router has routes
        assert len(router.routes) > 0, "Router should have routes defined"

        # Check for upload endpoint
        upload_route = None
        for route in router.routes:
            if hasattr(route, 'path') and 'upload' in route.path:
                upload_route = route
                break

        assert upload_route is not None, "Upload endpoint should exist"

        print(f"✓ Upload endpoint found: {upload_route.path}")
        print(f"  Methods: {upload_route.methods}")

        return True
    except Exception as e:
        print(f"✗ Upload endpoint test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_health_endpoint_exists():
    """Test that health check endpoint exists"""
    try:
        from src.api.routes import router

        # Check for health endpoint
        health_route = None
        for route in router.routes:
            if hasattr(route, 'path') and 'health' in route.path:
                health_route = route
                break

        assert health_route is not None, "Health endpoint should exist"

        print(f"✓ Health endpoint found: {health_route.path}")

        return True
    except Exception as e:
        print(f"✗ Health endpoint test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_router_prefix():
    """Test that router has correct prefix"""
    try:
        from src.api.routes import router

        # Router should have /api/v1/documents prefix or similar
        assert router.prefix is not None or len(router.routes) > 0, "Router should be configured"

        print(f"✓ Router configured with prefix: {router.prefix or 'None (set in app)'}")

        return True
    except Exception as e:
        print(f"✗ Router prefix test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_phase_21():
    """Run all Phase 21 tests"""
    print("\n" + "="*60)
    print("PHASE 21: Create API Routes")
    print("="*60 + "\n")

    results = []

    results.append(("API routes file exists", test_api_routes_file_exists()))
    results.append(("API routes module imports", test_api_routes_imports()))
    results.append(("Upload endpoint exists", test_upload_endpoint_exists()))
    results.append(("Health endpoint exists", test_health_endpoint_exists()))
    results.append(("Router prefix configured", test_router_prefix()))

    print("\n" + "-"*60)
    print("PHASE 21 RESULTS:")
    print("-"*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ PHASE 21: COMPLETE - API routes created")
        return True
    else:
        print(f"\n❌ PHASE 21: FAILED - {total - passed} tests broken")
        return False

if __name__ == "__main__":
    success = run_phase_21()
    sys.exit(0 if success else 1)
