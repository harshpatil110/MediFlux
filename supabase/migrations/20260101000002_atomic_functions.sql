-- =============================================================================
-- MediFlux Schema Migration 02: Atomic Stored Functions
-- Concurrency-safe PL/pgSQL inventory mutation routines
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Function: apply_sale
-- Atomically decrements quantity in inventory for given node, product, and batch.
-- Uses explicit row-level locking (FOR UPDATE) to prevent race conditions.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION apply_sale(
    p_node_id UUID,
    p_product_id UUID,
    p_batch_id UUID,
    p_qty INT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_current_qty INT;
    v_new_qty INT;
BEGIN
    IF p_qty <= 0 THEN
        RETURN jsonb_build_object(
            'success', false,
            'new_quantity', 0,
            'oversold', false,
            'error', 'Quantity must be positive'
        );
    END IF;

    -- Row-level locking to prevent concurrent read-modify-write collisions
    SELECT quantity INTO v_current_qty
    FROM inventory
    WHERE node_id = p_node_id
      AND product_id = p_product_id
      AND batch_id = p_batch_id
    FOR UPDATE;

    -- If record does not exist
    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'success', false,
            'new_quantity', 0,
            'oversold', true,
            'error', 'Inventory record not found'
        );
    END IF;

    -- Check if sufficient stock is available
    IF v_current_qty < p_qty THEN
        RETURN jsonb_build_object(
            'success', false,
            'new_quantity', v_current_qty,
            'oversold', true
        );
    END IF;

    -- Execute decrement
    UPDATE inventory
    SET quantity = quantity - p_qty,
        updated_at = now()
    WHERE node_id = p_node_id
      AND product_id = p_product_id
      AND batch_id = p_batch_id
    RETURNING quantity INTO v_new_qty;

    RETURN jsonb_build_object(
        'success', true,
        'new_quantity', v_new_qty,
        'oversold', false
    );
END;
$$;

-- -----------------------------------------------------------------------------
-- Function: apply_return
-- Atomically increments quantity in inventory (with upsert on conflict).
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION apply_return(
    p_node_id UUID,
    p_product_id UUID,
    p_batch_id UUID,
    p_qty INT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_new_qty INT;
BEGIN
    IF p_qty <= 0 THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'Quantity must be positive'
        );
    END IF;

    -- Upsert inventory record atomically
    INSERT INTO inventory (node_id, product_id, batch_id, quantity, updated_at)
    VALUES (p_node_id, p_product_id, p_batch_id, p_qty, now())
    ON CONFLICT (node_id, product_id, batch_id)
    DO UPDATE SET
        quantity = inventory.quantity + EXCLUDED.quantity,
        updated_at = now()
    RETURNING quantity INTO v_new_qty;

    RETURN jsonb_build_object(
        'success', true,
        'new_quantity', v_new_qty
    );
END;
$$;

-- -----------------------------------------------------------------------------
-- Function: apply_expiry
-- Decrements active quantity for an expired batch and updates batch status
-- to 'expired' or 'quarantined' if total remaining stock is depleted.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION apply_expiry(
    p_node_id UUID,
    p_product_id UUID,
    p_batch_id UUID,
    p_qty INT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_current_qty INT;
    v_deduct_qty INT;
    v_new_qty INT;
    v_total_batch_qty INT;
    v_batch_status TEXT;
BEGIN
    IF p_qty <= 0 THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'Quantity must be positive'
        );
    END IF;

    -- Lock inventory row
    SELECT quantity INTO v_current_qty
    FROM inventory
    WHERE node_id = p_node_id
      AND product_id = p_product_id
      AND batch_id = p_batch_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN jsonb_build_object(
            'success', false,
            'remaining_quantity', 0,
            'batch_status', 'not_found'
        );
    END IF;

    -- Deduct up to the available quantity
    v_deduct_qty := LEAST(v_current_qty, p_qty);

    UPDATE inventory
    SET quantity = quantity - v_deduct_qty,
        updated_at = now()
    WHERE node_id = p_node_id
      AND product_id = p_product_id
      AND batch_id = p_batch_id
    RETURNING quantity INTO v_new_qty;

    -- Check remaining batch quantity across the entire network
    SELECT COALESCE(SUM(quantity), 0) INTO v_total_batch_qty
    FROM inventory
    WHERE batch_id = p_batch_id;

    IF v_total_batch_qty = 0 THEN
        UPDATE batches
        SET status = 'expired'
        WHERE id = p_batch_id;
        v_batch_status := 'expired';
    ELSE
        SELECT status::text INTO v_batch_status
        FROM batches
        WHERE id = p_batch_id;
    END IF;

    RETURN jsonb_build_object(
        'success', true,
        'remaining_quantity', v_new_qty,
        'batch_status', v_batch_status
    );
END;
$$;

