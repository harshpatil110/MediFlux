-- =============================================================================
-- MediFlux Schema Migration 04: Authentication, Roles, and Row-Level Security (RLS)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Helper Function: visible_node_ids()
-- Returns set of node UUIDs visible to the current authenticated caller.
-- Admin sees all nodes; others see own node and all descendant nodes recursively.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION visible_node_ids()
RETURNS SETOF UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
STABLE
AS $$
DECLARE
    v_user_id UUID;
    v_node_id UUID;
    v_role TEXT;
BEGIN
    -- Resolve authenticated Supabase user UID
    v_user_id := auth.uid();
    
    IF v_user_id IS NULL THEN
        RETURN;
    END IF;

    -- Lookup user's profile for node association and role
    SELECT node_id, role INTO v_node_id, v_role
    FROM profiles
    WHERE user_id = v_user_id;

    -- Admin has global visibility across all nodes
    IF v_role = 'admin' THEN
        RETURN QUERY SELECT id FROM nodes;
        RETURN;
    END IF;

    -- If no node is assigned, return nothing
    IF v_node_id IS NULL THEN
        RETURN;
    END IF;

    -- Recursive CTE down the hierarchy:
    -- Starting at caller's node, traverse down nodes.parent_id to gather all descendant nodes
    RETURN QUERY
    WITH RECURSIVE downstream_nodes AS (
        -- Base member: caller's own node
        SELECT id, parent_id
        FROM nodes
        WHERE id = v_node_id
        
        UNION ALL
        
        -- Recursive member: child nodes whose parent_id points to a node in downstream_nodes
        SELECT n.id, n.parent_id
        FROM nodes n
        INNER JOIN downstream_nodes dn ON n.parent_id = dn.id
    )
    SELECT id FROM downstream_nodes;
END;
$$;

-- -----------------------------------------------------------------------------
-- 2. Enable Row-Level Security on Node-Scoped Tables
-- -----------------------------------------------------------------------------
ALTER TABLE nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;

-- -----------------------------------------------------------------------------
-- 3. RLS Policies: nodes
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS nodes_select_policy ON nodes;
CREATE POLICY nodes_select_policy ON nodes
    FOR SELECT
    TO authenticated
    USING (id IN (SELECT visible_node_ids()));

DROP POLICY IF EXISTS nodes_insert_policy ON nodes;
CREATE POLICY nodes_insert_policy ON nodes
    FOR INSERT
    TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM profiles 
            WHERE user_id = auth.uid() AND role = 'admin'
        )
    );

DROP POLICY IF EXISTS nodes_update_policy ON nodes;
CREATE POLICY nodes_update_policy ON nodes
    FOR UPDATE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM profiles 
            WHERE user_id = auth.uid() AND role = 'admin'
        )
    );

-- -----------------------------------------------------------------------------
-- 4. RLS Policies: profiles
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS profiles_select_policy ON profiles;
CREATE POLICY profiles_select_policy ON profiles
    FOR SELECT
    TO authenticated
    USING (
        user_id = auth.uid() 
        OR node_id IN (SELECT visible_node_ids())
        OR EXISTS (SELECT 1 FROM profiles p WHERE p.user_id = auth.uid() AND p.role = 'admin')
    );

DROP POLICY IF EXISTS profiles_update_policy ON profiles;
CREATE POLICY profiles_update_policy ON profiles
    FOR UPDATE
    TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- -----------------------------------------------------------------------------
-- 5. RLS Policies: inventory
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS inventory_select_policy ON inventory;
CREATE POLICY inventory_select_policy ON inventory
    FOR SELECT
    TO authenticated
    USING (node_id IN (SELECT visible_node_ids()));

DROP POLICY IF EXISTS inventory_insert_policy ON inventory;
CREATE POLICY inventory_insert_policy ON inventory
    FOR INSERT
    TO authenticated
    WITH CHECK (node_id IN (SELECT visible_node_ids()));

DROP POLICY IF EXISTS inventory_update_policy ON inventory;
CREATE POLICY inventory_update_policy ON inventory
    FOR UPDATE
    TO authenticated
    USING (node_id IN (SELECT visible_node_ids()))
    WITH CHECK (node_id IN (SELECT visible_node_ids()));

DROP POLICY IF EXISTS inventory_delete_policy ON inventory;
CREATE POLICY inventory_delete_policy ON inventory
    FOR DELETE
    TO authenticated
    USING (node_id IN (SELECT visible_node_ids()));

-- -----------------------------------------------------------------------------
-- 6. RLS Policies: batches
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS batches_select_policy ON batches;
CREATE POLICY batches_select_policy ON batches
    FOR SELECT
    TO authenticated
    USING (
        manufacturer_id IN (SELECT visible_node_ids())
        OR id IN (SELECT batch_id FROM inventory WHERE node_id IN (SELECT visible_node_ids()))
    );

DROP POLICY IF EXISTS batches_insert_policy ON batches;
CREATE POLICY batches_insert_policy ON batches
    FOR INSERT
    TO authenticated
    WITH CHECK (manufacturer_id IN (SELECT visible_node_ids()));

DROP POLICY IF EXISTS batches_update_policy ON batches;
CREATE POLICY batches_update_policy ON batches
    FOR UPDATE
    TO authenticated
    USING (manufacturer_id IN (SELECT visible_node_ids()))
    WITH CHECK (manufacturer_id IN (SELECT visible_node_ids()));

-- -----------------------------------------------------------------------------
-- 7. RLS Policies: audit_ledger (Append-Only / Immutable)
-- Strict Immutability: SELECT and INSERT only. NO UPDATE or DELETE policies exist
-- for the authenticated role. Attempts to mutate or drop ledger rows are denied.
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS audit_ledger_select_policy ON audit_ledger;
CREATE POLICY audit_ledger_select_policy ON audit_ledger
    FOR SELECT
    TO authenticated
    USING (node_id IN (SELECT visible_node_ids()));

DROP POLICY IF EXISTS audit_ledger_insert_policy ON audit_ledger;
CREATE POLICY audit_ledger_insert_policy ON audit_ledger
    FOR INSERT
    TO authenticated
    WITH CHECK (node_id IN (SELECT visible_node_ids()));

-- -----------------------------------------------------------------------------
-- 8. RLS Policies: events (Append-Only / Immutable)
-- Strict Immutability: SELECT and INSERT only. NO UPDATE or DELETE policies exist
-- for the authenticated role.
-- -----------------------------------------------------------------------------
DROP POLICY IF EXISTS events_select_policy ON events;
CREATE POLICY events_select_policy ON events
    FOR SELECT
    TO authenticated
    USING (node_id IN (SELECT visible_node_ids()));

DROP POLICY IF EXISTS events_insert_policy ON events;
CREATE POLICY events_insert_policy ON events
    FOR INSERT
    TO authenticated
    WITH CHECK (node_id IN (SELECT visible_node_ids()));

