-- =============================================================================
-- Migration: 004_events_and_inventory_rpc.sql
-- Atomic Ingestion & Inventory Decrement Procedure for MediFlux POS Sales
-- =============================================================================

CREATE OR REPLACE FUNCTION apply_sale(
    p_event_id TEXT,
    p_pharmacy_id UUID,
    p_product_id UUID,
    p_batch_id UUID,
    p_quantity INT,
    p_correlation_id TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_exists BOOLEAN;
    v_prev_hash TEXT;
    v_curr_hash TEXT;
    v_current_qty INT;
BEGIN
    -- 1. Idempotency Check: if event already exists, return duplicate status
    SELECT EXISTS(
        SELECT 1 FROM events WHERE event_id = p_event_id::text
    ) INTO v_exists;

    IF v_exists THEN
        RETURN jsonb_build_object(
            'status', 'duplicate',
            'applied', false,
            'event_id', p_event_id
        );
    END IF;

    -- 2. Insert into events table
    INSERT INTO events (
        event_id,
        type,
        node_id,
        payload,
        correlation_id,
        created_at
    ) VALUES (
        p_event_id::text,
        'pos.sale',
        p_pharmacy_id,
        jsonb_build_object(
            'pharmacy_id', p_pharmacy_id,
            'product_id', p_product_id,
            'batch_id', p_batch_id,
            'quantity', p_quantity,
            'source', 'pos'
        ),
        p_correlation_id,
        now()
    );

    -- 3. Decrement quantity in inventory atomically
    UPDATE inventory
    SET quantity = GREATEST(quantity - p_quantity, 0),
        updated_at = now()
    WHERE node_id = p_pharmacy_id
      AND product_id = p_product_id
      AND batch_id = p_batch_id
    RETURNING quantity INTO v_current_qty;

    -- 4. Append audit ledger entry
    SELECT current_hash INTO v_prev_hash
    FROM audit_ledger
    ORDER BY sequence_id DESC
    LIMIT 1;

    IF v_prev_hash IS NULL THEN
        v_prev_hash := 'GENESIS';
    END IF;

    v_curr_hash := md5(v_prev_hash || p_event_id::text || p_quantity::text);

    INSERT INTO audit_ledger (
        previous_hash,
        current_hash,
        action_type,
        node_id,
        payload,
        timestamp
    ) VALUES (
        v_prev_hash,
        v_curr_hash,
        'INVENTORY_DECREMENT',
        p_pharmacy_id,
        jsonb_build_object(
            'event_id', p_event_id::text,
            'product_id', p_product_id,
            'batch_id', p_batch_id,
            'quantity_deducted', p_quantity,
            'remaining_quantity', v_current_qty,
            'correlation_id', p_correlation_id
        ),
        now()
    );

    RETURN jsonb_build_object(
        'status', 'success',
        'applied', true,
        'event_id', p_event_id,
        'remaining_quantity', v_current_qty
    );
END;
$$;
