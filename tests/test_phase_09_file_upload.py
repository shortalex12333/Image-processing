"""
PHASE 9: Add File Upload to Temp Storage Method
DocumentHandler can save uploaded file to temp storage
"""

import asyncio
import sys
import os
from uuid import uuid4

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

async def test_save_to_temp_storage():
    """Test saving file to temp storage"""
    try:
        from src.handlers.document_handler import DocumentHandler

        handler = DocumentHandler()
        yacht_id = uuid4()

        # Create fake file
        file_bytes = b"fake PDF content"
        filename = "test_packing_slip.pdf"

        # Save to temp
        temp_file_id, temp_path = await handler._save_to_temp_storage(
            yacht_id=yacht_id,
            file_bytes=file_bytes,
            filename=filename
        )

        # Verify file ID
        assert temp_file_id is not None, "temp_file_id is None"
        assert len(temp_file_id) == 36, f"temp_file_id should be UUID format: {temp_file_id}"
        print(f"✓ Generated temp file ID: {temp_file_id}")

        # Verify temp path
        assert temp_path is not None, "temp_path is None"
        assert os.path.exists(temp_path), f"File not found at {temp_path}"
        assert temp_path.endswith('.pdf'), f"Path should end with .pdf: {temp_path}"
        print(f"✓ File saved to: {temp_path}")

        # Verify path structure: temp_uploads/{yacht_id}/{uuid}.pdf
        assert str(yacht_id) in temp_path, f"yacht_id not in path: {temp_path}"
        assert temp_file_id in temp_path, f"temp_file_id not in path: {temp_path}"
        print(f"✓ Path structure correct: temp_uploads/{yacht_id}/{temp_file_id}.pdf")

        # Read back and verify content
        with open(temp_path, 'rb') as f:
            content = f.read()
        assert content == file_bytes, "File content doesn't match"
        print(f"✓ File content verified ({len(content)} bytes)")

        # Cleanup
        os.remove(temp_path)
        os.rmdir(os.path.dirname(temp_path))

        return True
    except Exception as e:
        print(f"✗ Save to temp storage test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_save_different_extensions():
    """Test saving files with different extensions"""
    try:
        from src.handlers.document_handler import DocumentHandler

        handler = DocumentHandler()
        yacht_id = uuid4()

        extensions = ['.pdf', '.jpg', '.png', '.heic', '.txt']
        saved_files = []

        for ext in extensions:
            filename = f"test_file{ext}"
            file_bytes = f"test content for {ext}".encode()

            temp_file_id, temp_path = await handler._save_to_temp_storage(
                yacht_id=yacht_id,
                file_bytes=file_bytes,
                filename=filename
            )

            assert temp_path.endswith(ext), f"Extension mismatch: {temp_path}"
            saved_files.append(temp_path)

        print(f"✓ Saved files with {len(extensions)} different extensions")

        # Cleanup
        for temp_path in saved_files:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        yacht_dir = os.path.join("temp_uploads", str(yacht_id))
        if os.path.exists(yacht_dir):
            os.rmdir(yacht_dir)

        return True
    except Exception as e:
        print(f"✗ Different extensions test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_save_no_extension_fails():
    """Test that saving file without extension raises ValueError"""
    try:
        from src.handlers.document_handler import DocumentHandler

        handler = DocumentHandler()
        yacht_id = uuid4()

        # Try to save file without extension
        file_bytes = b"test content"
        filename = "test_file_no_ext"  # No extension

        try:
            temp_file_id, temp_path = await handler._save_to_temp_storage(
                yacht_id=yacht_id,
                file_bytes=file_bytes,
                filename=filename
            )
            print(f"✗ Should have raised ValueError for filename without extension")
            return False
        except ValueError as e:
            assert "extension" in str(e).lower(), f"Error message should mention extension: {e}"
            print(f"✓ Correctly raises ValueError for filename without extension")
            return True

    except Exception as e:
        print(f"✗ No extension test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_save_multiple_files_same_yacht():
    """Test saving multiple files to same yacht directory"""
    try:
        from src.handlers.document_handler import DocumentHandler

        handler = DocumentHandler()
        yacht_id = uuid4()

        # Save 3 files to same yacht
        saved_files = []
        for i in range(3):
            filename = f"document_{i}.pdf"
            file_bytes = f"content for document {i}".encode()

            temp_file_id, temp_path = await handler._save_to_temp_storage(
                yacht_id=yacht_id,
                file_bytes=file_bytes,
                filename=filename
            )
            saved_files.append((temp_file_id, temp_path))

        # Verify all 3 files exist
        for temp_file_id, temp_path in saved_files:
            assert os.path.exists(temp_path), f"File not found: {temp_path}"

        # Verify all have unique UUIDs
        file_ids = [fid for fid, _ in saved_files]
        assert len(file_ids) == len(set(file_ids)), "File IDs should be unique"

        print(f"✓ Saved {len(saved_files)} files to same yacht directory")
        print(f"✓ All file IDs are unique")

        # Cleanup
        for _, temp_path in saved_files:
            os.remove(temp_path)
        yacht_dir = os.path.join("temp_uploads", str(yacht_id))
        os.rmdir(yacht_dir)

        return True
    except Exception as e:
        print(f"✗ Multiple files test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def run_phase_9():
    """Run all Phase 9 tests"""
    print("\n" + "="*60)
    print("PHASE 9: Add File Upload to Temp Storage Method")
    print("="*60 + "\n")

    results = []

    results.append(("Save to temp storage", await test_save_to_temp_storage()))
    results.append(("Different file extensions", await test_save_different_extensions()))
    results.append(("No extension raises ValueError", await test_save_no_extension_fails()))
    results.append(("Multiple files same yacht", await test_save_multiple_files_same_yacht()))

    print("\n" + "-"*60)
    print("PHASE 9 RESULTS:")
    print("-"*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ PHASE 9: COMPLETE - Temp file upload works")
        return True
    else:
        print(f"\n❌ PHASE 9: FAILED - {total - passed} tests broken")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_phase_9())
    sys.exit(0 if success else 1)
