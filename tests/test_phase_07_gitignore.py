"""
PHASE 7: Add temp_uploads/ to .gitignore
Ensure temp files are not committed to git
"""

import sys
import os
import subprocess

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_gitignore_updated():
    """Test that .gitignore contains temp_uploads/ entry"""
    try:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        gitignore_path = os.path.join(project_root, '.gitignore')

        assert os.path.exists(gitignore_path), ".gitignore file not found"

        with open(gitignore_path, 'r') as f:
            content = f.read()

        assert 'temp_uploads/' in content, "temp_uploads/ not found in .gitignore"
        print("✓ .gitignore contains temp_uploads/ entry")

        assert '*.log' in content, "*.log not found in .gitignore"
        print("✓ .gitignore contains *.log entry")

        return True
    except Exception as e:
        print(f"✗ .gitignore update check failed: {e}")
        return False

def test_git_ignores_temp_uploads():
    """Test that git actually ignores temp_uploads/ directory"""
    try:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        temp_dir = os.path.join(project_root, 'temp_uploads')
        test_file = os.path.join(temp_dir, 'test_ignore.txt')

        # Create test file in temp_uploads/
        os.makedirs(temp_dir, exist_ok=True)
        with open(test_file, 'w') as f:
            f.write("This file should be ignored by git")

        # Run git status and check if temp_uploads/ appears
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=project_root,
            capture_output=True,
            text=True
        )

        # Check if temp_uploads/ appears in output
        if 'temp_uploads/' in result.stdout or 'test_ignore.txt' in result.stdout:
            print(f"✗ git status shows temp_uploads/ files (should be ignored)")
            print(f"   Git output: {result.stdout}")
            # Cleanup
            os.remove(test_file)
            return False

        print("✓ git status ignores temp_uploads/ files")

        # Cleanup
        os.remove(test_file)

        return True
    except Exception as e:
        print(f"✗ Git ignore test failed: {e}")
        # Try to cleanup
        try:
            if os.path.exists(test_file):
                os.remove(test_file)
        except:
            pass
        return False

def test_gitignore_format():
    """Test that .gitignore is properly formatted"""
    try:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        gitignore_path = os.path.join(project_root, '.gitignore')

        with open(gitignore_path, 'r') as f:
            lines = f.readlines()

        # Find temp_uploads/ line
        found = False
        for i, line in enumerate(lines):
            if 'temp_uploads/' in line:
                found = True
                # Should not be commented out
                assert not line.strip().startswith('#'), "temp_uploads/ line is commented out"
                # Should end with /
                assert line.strip().endswith('/'), "temp_uploads should end with /"
                break

        assert found, "temp_uploads/ not found in .gitignore"
        print("✓ .gitignore properly formatted")

        return True
    except Exception as e:
        print(f"✗ .gitignore format check failed: {e}")
        return False

def run_phase_7():
    """Run all Phase 7 tests"""
    print("\n" + "="*60)
    print("PHASE 7: Add temp_uploads/ to .gitignore")
    print("="*60 + "\n")

    results = []

    results.append((".gitignore updated", test_gitignore_updated()))
    results.append(("Git ignores temp_uploads/", test_git_ignores_temp_uploads()))
    results.append((".gitignore format correct", test_gitignore_format()))

    print("\n" + "-"*60)
    print("PHASE 7 RESULTS:")
    print("-"*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ PHASE 7: COMPLETE - .gitignore configured")
        return True
    else:
        print(f"\n❌ PHASE 7: FAILED - {total - passed} tests broken")
        return False

if __name__ == "__main__":
    success = run_phase_7()
    sys.exit(0 if success else 1)
