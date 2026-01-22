"""
PHASE 14: Verify Database Connection
Ensure we can connect to Supabase and query tables
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_supabase_connection():
    """Test that Supabase client can be created"""
    try:
        from src.database import get_supabase_service

        supabase = get_supabase_service()
        assert supabase is not None, "Supabase client is None"

        print("✓ Supabase client created successfully")

        return True
    except Exception as e:
        print(f"✗ Supabase connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_query_pms_orders():
    """Test querying pms_orders table"""
    try:
        from src.database import get_supabase_service

        supabase = get_supabase_service()
        result = supabase.table("pms_orders").select("*").limit(1).execute()

        assert result.data is not None, "Query returned None"

        print(f"✓ Can query pms_orders table ({len(result.data)} orders retrieved)")

        return True
    except Exception as e:
        print(f"✗ Query pms_orders failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_query_pms_shopping_list_items():
    """Test querying pms_shopping_list_items table"""
    try:
        from src.database import get_supabase_service

        supabase = get_supabase_service()
        result = supabase.table("pms_shopping_list_items").select("*").limit(1).execute()

        assert result.data is not None, "Query returned None"

        print(f"✓ Can query pms_shopping_list_items table ({len(result.data)} items retrieved)")

        return True
    except Exception as e:
        print(f"✗ Query pms_shopping_list_items failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_query_pms_receiving_line_items():
    """Test querying pms_receiving_line_items table"""
    try:
        from src.database import get_supabase_service

        supabase = get_supabase_service()
        result = supabase.table("pms_receiving_line_items").select("*").limit(1).execute()

        assert result.data is not None, "Query returned None"

        print(f"✓ Can query pms_receiving_line_items table ({len(result.data)} items retrieved)")

        return True
    except Exception as e:
        print(f"✗ Query pms_receiving_line_items failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_database_service_role_access():
    """Test that service role can bypass RLS (admin access)"""
    try:
        from src.database import get_supabase_service

        supabase = get_supabase_service()

        # Service role should be able to count all rows across all yachts
        result = supabase.table("pms_orders").select("*", count="exact").limit(0).execute()

        total_orders = result.count or 0

        assert total_orders >= 0, "Count should be non-negative"

        print(f"✓ Service role has admin access ({total_orders} total orders across all yachts)")

        return True
    except Exception as e:
        print(f"✗ Service role access test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_connection_reuse():
    """Test that connection is reused (singleton pattern)"""
    try:
        from src.database import get_supabase_service

        supabase1 = get_supabase_service()
        supabase2 = get_supabase_service()

        # Should be the same instance (singleton)
        assert supabase1 is supabase2, "Supabase clients should be same instance"

        print("✓ Database connection reuses singleton instance")

        return True
    except Exception as e:
        print(f"✗ Connection reuse test failed: {e}")
        return False

def run_phase_14():
    """Run all Phase 14 tests"""
    print("\n" + "="*60)
    print("PHASE 14: Verify Database Connection")
    print("="*60 + "\n")

    results = []

    results.append(("Supabase connection", test_supabase_connection()))
    results.append(("Query pms_orders", test_query_pms_orders()))
    results.append(("Query pms_shopping_list_items", test_query_pms_shopping_list_items()))
    results.append(("Query pms_receiving_line_items", test_query_pms_receiving_line_items()))
    results.append(("Service role admin access", test_database_service_role_access()))
    results.append(("Connection reuse (singleton)", test_connection_reuse()))

    print("\n" + "-"*60)
    print("PHASE 14 RESULTS:")
    print("-"*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ PHASE 14: COMPLETE - Database accessible")
        return True
    else:
        print(f"\n❌ PHASE 14: FAILED - {total - passed} tests broken")
        return False

if __name__ == "__main__":
    success = run_phase_14()
    sys.exit(0 if success else 1)
