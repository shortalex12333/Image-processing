"""
PHASE 6: Create Temp Storage Directory Structure
Set up temp_uploads/ directory with yacht-based folders
"""

import sys
import os
from uuid import uuid4

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_temp_storage_setup():
    """Test creating temp storage directory structure"""
    try:
        temp_dir = "temp_uploads"
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        temp_path = os.path.join(project_root, temp_dir)

        # Create main directory
        os.makedirs(temp_path, exist_ok=True)
        assert os.path.exists(temp_path), f"Failed to create {temp_path}"
        print(f"✓ Created {temp_dir}/ directory")

        # Create yacht subdirectory
        test_yacht_id = str(uuid4())
        yacht_dir = os.path.join(temp_path, test_yacht_id)
        os.makedirs(yacht_dir, exist_ok=True)
        assert os.path.exists(yacht_dir), f"Failed to create yacht subdirectory"
        print(f"✓ Created yacht subdirectory: {test_yacht_id[:8]}...")

        # Test write access
        test_file = os.path.join(yacht_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test content")
        assert os.path.exists(test_file), "Failed to write test file"
        print(f"✓ Can write files to temp directory")

        # Test read access
        with open(test_file, 'r') as f:
            content = f.read()
        assert content == "test content", "File content doesn't match"
        print(f"✓ Can read files from temp directory")

        # Cleanup
        os.remove(test_file)
        os.rmdir(yacht_dir)
        print(f"✓ Cleanup successful (removed test files)")

        return True
    except Exception as e:
        print(f"✗ Temp storage setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_temp_storage_permissions():
    """Test that temp directory has correct permissions"""
    try:
        temp_dir = "temp_uploads"
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        temp_path = os.path.join(project_root, temp_dir)

        # Check directory is readable
        assert os.access(temp_path, os.R_OK), "temp_uploads/ not readable"
        print(f"✓ Directory is readable")

        # Check directory is writable
        assert os.access(temp_path, os.W_OK), "temp_uploads/ not writable"
        print(f"✓ Directory is writable")

        # Check directory is executable (can list contents)
        assert os.access(temp_path, os.X_OK), "temp_uploads/ not executable"
        print(f"✓ Directory is executable")

        return True
    except Exception as e:
        print(f"✗ Permission check failed: {e}")
        return False

def test_multiple_yacht_directories():
    """Test creating multiple yacht directories simultaneously"""
    try:
        temp_dir = "temp_uploads"
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        temp_path = os.path.join(project_root, temp_dir)

        # Create multiple yacht directories
        yacht_ids = [str(uuid4()) for _ in range(3)]
        yacht_dirs = []

        for yacht_id in yacht_ids:
            yacht_dir = os.path.join(temp_path, yacht_id)
            os.makedirs(yacht_dir, exist_ok=True)
            yacht_dirs.append(yacht_dir)
            assert os.path.exists(yacht_dir), f"Failed to create {yacht_id}"

        print(f"✓ Created {len(yacht_ids)} yacht directories")

        # Write a file to each
        for yacht_dir in yacht_dirs:
            test_file = os.path.join(yacht_dir, "test.txt")
            with open(test_file, 'w') as f:
                f.write(f"yacht data for {os.path.basename(yacht_dir)}")
            assert os.path.exists(test_file)

        print(f"✓ Can write files to all yacht directories")

        # Verify isolation (files are in separate directories)
        file_count = 0
        for yacht_dir in yacht_dirs:
            files = os.listdir(yacht_dir)
            assert len(files) == 1, f"Expected 1 file, found {len(files)}"
            file_count += len(files)

        assert file_count == 3, "Files should be isolated per yacht"
        print(f"✓ Files are properly isolated per yacht")

        # Cleanup
        for yacht_dir in yacht_dirs:
            test_file = os.path.join(yacht_dir, "test.txt")
            os.remove(test_file)
            os.rmdir(yacht_dir)

        print(f"✓ Cleanup successful")

        return True
    except Exception as e:
        print(f"✗ Multiple yacht directories test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_phase_6():
    """Run all Phase 6 tests"""
    print("\n" + "="*60)
    print("PHASE 6: Create Temp Storage Directory Structure")
    print("="*60 + "\n")

    results = []

    results.append(("Temp storage setup", test_temp_storage_setup()))
    results.append(("Temp storage permissions", test_temp_storage_permissions()))
    results.append(("Multiple yacht directories", test_multiple_yacht_directories()))

    print("\n" + "-"*60)
    print("PHASE 6 RESULTS:")
    print("-"*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ PHASE 6: COMPLETE - Temp storage ready")
        return True
    else:
        print(f"\n❌ PHASE 6: FAILED - {total - passed} tests broken")
        return False

if __name__ == "__main__":
    success = run_phase_6()
    sys.exit(0 if success else 1)
