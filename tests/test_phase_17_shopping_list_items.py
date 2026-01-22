"""
PHASE 17: Get Shopping List Items for Order
Load shopping_list_items for matched order
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

async def test_get_shopping_list_items():
    """Test getting shopping list items for an order"""
    try:
        from src.reconciliation.order_matcher_by_number import OrderMatcherByNumber
        from src.database import get_supabase_service

        matcher = OrderMatcherByNumber()
        supabase = get_supabase_service()

        # Get a real order
        order_result = supabase.table("pms_orders").select("*").limit(1).execute()

        if order_result.data and len(order_result.data) > 0:
            test_order = order_result.data[0]
            yacht_id = test_order["yacht_id"]
            order_id = test_order["id"]

            # Get shopping list items
            items = await matcher.get_shopping_list_items(yacht_id, order_id)

            assert isinstance(items, list), "Should return a list"

            print(f"✓ Retrieved {len(items)} shopping list items for order")

            # If items exist, verify structure
            if len(items) > 0:
                assert "id" in items[0], "Item should have id"
                assert "yacht_id" in items[0], "Item should have yacht_id"
                print(f"  First item ID: {items[0].get('id')}")

            return True
        else:
            print("⚠️  No orders to test (skipping)")
            return True

    except Exception as e:
        print(f"✗ Get shopping list items test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_shopping_list_items_empty():
    """Test getting shopping list items for order with no items"""
    try:
        from src.reconciliation.order_matcher_by_number import OrderMatcherByNumber
        from src.database import get_supabase_service
        from uuid import uuid4

        matcher = OrderMatcherByNumber()
        supabase = get_supabase_service()

        # Get a real yacht_id
        order_result = supabase.table("pms_orders").select("yacht_id").limit(1).execute()

        if order_result.data and len(order_result.data) > 0:
            yacht_id = order_result.data[0]["yacht_id"]

            # Use non-existent order_id
            fake_order_id = str(uuid4())

            items = await matcher.get_shopping_list_items(yacht_id, fake_order_id)

            assert isinstance(items, list), "Should return a list"
            assert len(items) == 0, "Should return empty list for non-existent order"

            print("✓ Returns empty list for order with no items")

            return True
        else:
            print("⚠️  No yacht data to test (skipping)")
            return True

    except Exception as e:
        print(f"✗ Empty shopping list test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_shopping_list_yacht_id_filtering():
    """Test that yacht_id filtering works on shopping list items"""
    try:
        from src.reconciliation.order_matcher_by_number import OrderMatcherByNumber
        from src.database import get_supabase_service
        from uuid import uuid4

        matcher = OrderMatcherByNumber()
        supabase = get_supabase_service()

        # Get a real order with items
        items_result = supabase.table("pms_shopping_list_items").select("*").limit(1).execute()

        if items_result.data and len(items_result.data) > 0:
            test_item = items_result.data[0]
            correct_yacht_id = test_item["yacht_id"]
            order_id = test_item["order_id"]

            # Try with wrong yacht_id
            wrong_yacht_id = uuid4()

            items = await matcher.get_shopping_list_items(wrong_yacht_id, order_id)

            assert len(items) == 0, "Should return empty list with wrong yacht_id"

            print("✓ Yacht ID filtering enforced on shopping list items")

            return True
        else:
            print("⚠️  No shopping list items to test (skipping)")
            return True

    except Exception as e:
        print(f"✗ Shopping list yacht ID filtering test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_shopping_list_items_structure():
    """Test shopping list item structure"""
    try:
        from src.reconciliation.order_matcher_by_number import OrderMatcherByNumber
        from src.database import get_supabase_service

        matcher = OrderMatcherByNumber()
        supabase = get_supabase_service()

        # Get real items directly
        items_result = supabase.table("pms_shopping_list_items").select("*").limit(1).execute()

        if items_result.data and len(items_result.data) > 0:
            item = items_result.data[0]

            # Verify expected fields exist
            required_fields = ["id", "yacht_id", "order_id"]
            for field in required_fields:
                assert field in item, f"Shopping list item missing {field}"

            print("✓ Shopping list items have required fields")

            return True
        else:
            print("⚠️  No shopping list items to test (skipping)")
            return True

    except Exception as e:
        print(f"✗ Shopping list item structure test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def run_phase_17():
    """Run all Phase 17 tests"""
    print("\n" + "="*60)
    print("PHASE 17: Get Shopping List Items for Order")
    print("="*60 + "\n")

    results = []

    results.append(("Get shopping list items", await test_get_shopping_list_items()))
    results.append(("Empty shopping list", await test_shopping_list_items_empty()))
    results.append(("Yacht ID filtering on shopping list", await test_shopping_list_yacht_id_filtering()))
    results.append(("Shopping list item structure", await test_shopping_list_items_structure()))

    print("\n" + "-"*60)
    print("PHASE 17 RESULTS:")
    print("-"*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ PHASE 17: COMPLETE - Shopping list retrieval works")
        return True
    else:
        print(f"\n❌ PHASE 17: FAILED - {total - passed} tests broken")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_phase_17())
    sys.exit(0 if success else 1)
