"""
PHASE 22: API Endpoint Testing
Test API endpoints with FastAPI TestClient
"""

import asyncio
import sys
import os
from io import BytesIO
from PIL import Image, ImageDraw

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

async def test_health_endpoint():
    """Test health check endpoint"""
    try:
        from fastapi.testclient import TestClient
        from src.api.routes import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/api/v1/documents/health")

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
        assert "ocr_engine" in data
        assert "version" in data

        print(f"✓ Health endpoint returned: {data['status']}")
        print(f"  OCR Engine: {data['ocr_engine']}")
        print(f"  Version: {data['version']}")

        return True
    except Exception as e:
        print(f"✗ Health endpoint test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_upload_endpoint_with_valid_file():
    """Test upload endpoint with valid packing slip image"""
    try:
        from fastapi.testclient import TestClient
        from src.api.routes import router
        from fastapi import FastAPI
        from uuid import uuid4

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Create test image
        img = Image.new('RGB', (800, 300), color='white')
        d = ImageDraw.Draw(img)
        d.text((10, 50), "PACKING SLIP", fill='black')
        d.text((10, 100), "Order: ORD-2024-001", fill='black')

        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)

        # Upload file
        yacht_id = str(uuid4())
        response = client.post(
            "/api/v1/documents/upload",
            params={"yacht_id": yacht_id},
            files={"file": ("test_packing.png", img_bytes, "image/png")}
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        assert "temp_file_id" in data
        assert "ocr_results" in data
        assert "document_classification" in data
        assert "extracted_entities" in data
        assert "matching" in data
        assert "processing_time_total_ms" in data

        print(f"✓ Upload processed successfully")
        print(f"  Temp File ID: {data['temp_file_id']}")
        print(f"  OCR Engine: {data['ocr_results']['engine_used']}")
        print(f"  Processing Time: {data['processing_time_total_ms']}ms")

        return True
    except Exception as e:
        print(f"✗ Upload endpoint test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_upload_endpoint_invalid_yacht_id():
    """Test upload endpoint rejects invalid yacht_id"""
    try:
        from fastapi.testclient import TestClient
        from src.api.routes import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Create test image
        img = Image.new('RGB', (100, 100), color='white')
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)

        # Upload with invalid yacht_id
        response = client.post(
            "/api/v1/documents/upload",
            params={"yacht_id": "invalid-uuid"},
            files={"file": ("test.png", img_bytes, "image/png")}
        )

        assert response.status_code == 400, f"Expected 400, got {response.status_code}"

        data = response.json()
        assert "detail" in data
        assert "yacht_id" in data["detail"].lower()

        print(f"✓ Invalid yacht_id rejected with 400 status")

        return True
    except Exception as e:
        print(f"✗ Invalid yacht_id test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_upload_endpoint_invalid_file_type():
    """Test upload endpoint rejects unsupported file types"""
    try:
        from fastapi.testclient import TestClient
        from src.api.routes import router
        from fastapi import FastAPI
        from uuid import uuid4

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Create text file (unsupported)
        text_content = BytesIO(b"This is a text file")

        yacht_id = str(uuid4())
        response = client.post(
            "/api/v1/documents/upload",
            params={"yacht_id": yacht_id},
            files={"file": ("test.txt", text_content, "text/plain")}
        )

        assert response.status_code == 400, f"Expected 400, got {response.status_code}"

        data = response.json()
        assert "detail" in data
        assert "file type" in data["detail"].lower() or "unsupported" in data["detail"].lower()

        print(f"✓ Invalid file type rejected with 400 status")

        return True
    except Exception as e:
        print(f"✗ Invalid file type test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_upload_endpoint_empty_file():
    """Test upload endpoint rejects empty files"""
    try:
        from fastapi.testclient import TestClient
        from src.api.routes import router
        from fastapi import FastAPI
        from uuid import uuid4

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Create empty file
        empty_file = BytesIO(b"")

        yacht_id = str(uuid4())
        response = client.post(
            "/api/v1/documents/upload",
            params={"yacht_id": yacht_id},
            files={"file": ("test.png", empty_file, "image/png")}
        )

        assert response.status_code == 400, f"Expected 400, got {response.status_code}"

        data = response.json()
        assert "detail" in data
        assert "empty" in data["detail"].lower()

        print(f"✓ Empty file rejected with 400 status")

        return True
    except Exception as e:
        print(f"✗ Empty file test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def run_phase_22():
    """Run all Phase 22 tests"""
    print("\n" + "="*60)
    print("PHASE 22: API Endpoint Testing")
    print("="*60 + "\n")

    results = []

    results.append(("Health endpoint", await test_health_endpoint()))
    results.append(("Upload with valid file", await test_upload_endpoint_with_valid_file()))
    results.append(("Reject invalid yacht_id", await test_upload_endpoint_invalid_yacht_id()))
    results.append(("Reject invalid file type", await test_upload_endpoint_invalid_file_type()))
    results.append(("Reject empty file", await test_upload_endpoint_empty_file()))

    print("\n" + "-"*60)
    print("PHASE 22 RESULTS:")
    print("-"*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ PHASE 22: COMPLETE - API endpoint testing works")
        return True
    else:
        print(f"\n❌ PHASE 22: FAILED - {total - passed} tests broken")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_phase_22())
    sys.exit(0 if success else 1)
