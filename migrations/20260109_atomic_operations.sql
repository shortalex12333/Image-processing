-- Migration: Atomic Operations for Race Condition Prevention
-- Date: 2026-01-09
-- Purpose: Fix critical race condition vulnerability found in testing
--
-- Evidence from testing:
-- - 3 concurrent requests for 5 units each (15 total)
-- - Initial stock: 10 units
-- - Check-then-act: 2/3 succeeded (inventory over-deducted)
-- - Solution: Database-level atomic operations

-- ============================================================================
-- Function 1: Atomic Inventory Deduction
-- ============================================================================

CREATE OR REPLACE FUNCTION public.atomic_deduct_inventory(
    p_part_id UUID,
    p_quantity NUMERIC,
    p_user_id UUID,
    p_work_order_id UUID DEFAULT NULL,
    p_equipment_id UUID DEFAULT NULL,
    p_notes TEXT DEFAULT NULL
)
RETURNS TABLE(
    old_quantity NUMERIC,
    new_quantity NUMERIC,
    usage_id UUID
) AS $$
DECLARE
    v_old_quantity NUMERIC;
    v_new_quantity NUMERIC;
    v_usage_id UUID;
    v_yacht_id UUID;
BEGIN
    -- Get current quantity and yacht_id (this locks the row with FOR UPDATE)
    SELECT quantity_on_hand, yacht_id INTO v_old_quantity, v_yacht_id
    FROM pms_parts
    WHERE id = p_part_id
    FOR UPDATE;

    -- Check if part exists
    IF v_old_quantity IS NULL THEN
        RAISE EXCEPTION 'Part % not found', p_part_id;
    END IF;

    -- Check if sufficient stock (CRITICAL: This check and update are atomic)
    IF v_old_quantity < p_quantity THEN
        RAISE EXCEPTION 'Insufficient stock: have %, need %', v_old_quantity, p_quantity;
    END IF;

    -- Perform atomic deduction
    UPDATE pms_parts
    SET
        quantity_on_hand = quantity_on_hand - p_quantity,
        updated_at = NOW()
    WHERE id = p_part_id
    RETURNING quantity_on_hand INTO v_new_quantity;

    -- Create usage record (audit trail)
    INSERT INTO pms_part_usage (
        id,
        yacht_id,
        part_id,
        work_order_id,
        equipment_id,
        quantity,
        usage_reason,
        notes,
        used_by,
        used_at
    ) VALUES (
        gen_random_uuid(),
        v_yacht_id,
        p_part_id,
        p_work_order_id,
        p_equipment_id,
        p_quantity,
        'deduction',
        p_notes,
        p_user_id,
        NOW()
    )
    RETURNING id INTO v_usage_id;

    -- Return results
    RETURN QUERY SELECT v_old_quantity, v_new_quantity, v_usage_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION public.atomic_deduct_inventory TO authenticated;
GRANT EXECUTE ON FUNCTION public.atomic_deduct_inventory TO service_role;

COMMENT ON FUNCTION public.atomic_deduct_inventory IS
'Atomically deduct inventory with stock validation. Prevents race conditions by using row-level locks.';


-- ============================================================================
-- Function 2: Atomic Session Commit (Prevent Double-Commit)
-- ============================================================================

CREATE OR REPLACE FUNCTION public.atomic_commit_session(
    p_session_id UUID,
    p_user_id UUID
)
RETURNS TABLE(
    session_id UUID,
    committed_at TIMESTAMPTZ
) AS $$
DECLARE
    v_session_status TEXT;
    v_committed_at TIMESTAMPTZ;
BEGIN
    -- Check current session status (lock the row)
    SELECT status INTO v_session_status
    FROM receiving_sessions
    WHERE id = p_session_id
    FOR UPDATE;

    -- Check if session exists
    IF v_session_status IS NULL THEN
        RAISE EXCEPTION 'Session % not found', p_session_id;
    END IF;

    -- Check if already committed (CRITICAL: Prevents double-commit attacks)
    IF v_session_status = 'committed' THEN
        RAISE EXCEPTION 'Session % has already been committed', p_session_id;
    END IF;

    -- Atomically commit the session
    UPDATE receiving_sessions
    SET
        status = 'committed',
        committed_by = p_user_id,
        committed_at = NOW()
    WHERE id = p_session_id
    RETURNING receiving_sessions.committed_at INTO v_committed_at;

    -- Return results
    RETURN QUERY SELECT p_session_id, v_committed_at;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION public.atomic_commit_session TO authenticated;
GRANT EXECUTE ON FUNCTION public.atomic_commit_session TO service_role;

COMMENT ON FUNCTION public.atomic_commit_session IS
'Atomically commit a receiving session. Prevents double-commit attacks by checking status with row lock.';


-- ============================================================================
-- Function 3: Get Stock with Lock (for complex multi-step operations)
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_part_stock_with_lock(
    p_part_id UUID
)
RETURNS TABLE(
    part_id UUID,
    quantity_on_hand NUMERIC,
    minimum_quantity NUMERIC,
    unit TEXT
) AS $$
BEGIN
    -- Lock the row and return current stock
    RETURN QUERY
    SELECT
        pms_parts.id,
        pms_parts.quantity_on_hand,
        pms_parts.minimum_quantity,
        pms_parts.unit
    FROM pms_parts
    WHERE id = p_part_id
    FOR UPDATE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION public.get_part_stock_with_lock TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_part_stock_with_lock TO service_role;

COMMENT ON FUNCTION public.get_part_stock_with_lock IS
'Get part stock with row-level lock. Use sparingly - prefer atomic_deduct_inventory for simple operations.';


-- ============================================================================
-- Verification Queries
-- ============================================================================

-- Test that functions exist
SELECT
    proname AS function_name,
    pg_get_function_identity_arguments(oid) AS arguments
FROM pg_proc
WHERE proname IN ('atomic_deduct_inventory', 'atomic_commit_session', 'get_part_stock_with_lock')
    AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public');

-- Expected output:
-- atomic_deduct_inventory    | p_part_id uuid, p_quantity numeric, p_user_id uuid, ...
-- atomic_commit_session      | p_session_id uuid, p_user_id uuid
-- get_part_stock_with_lock   | p_part_id uuid
