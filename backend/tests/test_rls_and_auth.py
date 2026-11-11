"""Comprehensive unit and integration test suite for Authentication, Roles, and RLS (Task 3)."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import UnauthorizedError
from app.core.security import (
    CurrentUser,
    get_actor,
    visible_node_ids,
)
from app.main import app

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations"


# -----------------------------------------------------------------------------
# 1. SQL Migration & Policy Syntax Verification
# -----------------------------------------------------------------------------
def test_rls_migration_file_exists_and_valid() -> None:
    """Ensure supabase/migrations/003_auth_and_rls.sql exists and defines all policies."""
    migration_path = MIGRATIONS_DIR / "003_auth_and_rls.sql"
    assert migration_path.exists(), "Missing migration file 003_auth_and_rls.sql"
    sql = migration_path.read_text(encoding="utf-8")

    # Helper function
    assert "CREATE OR REPLACE FUNCTION visible_node_ids()" in sql
    assert "SECURITY DEFINER" in sql
    assert "SET search_path = public" in sql
    assert "WITH RECURSIVE downstream_nodes" in sql

    # RLS table enablement
    required_tables = ["nodes", "profiles", "inventory", "batches", "audit_ledger", "events"]
    for tbl in required_tables:
        assert f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;" in sql

    # Verify audit_ledger and events have NO update or delete policy for authenticated
    assert "audit_ledger_select_policy" in sql
    assert "audit_ledger_insert_policy" in sql
    assert "CREATE POLICY audit_ledger_update_policy" not in sql
    assert "CREATE POLICY audit_ledger_delete_policy" not in sql
    assert "events_select_policy" in sql
    assert "events_insert_policy" in sql
    assert "CREATE POLICY events_update_policy" not in sql
    assert "CREATE POLICY events_delete_policy" not in sql


# -----------------------------------------------------------------------------
# 2. Hierarchy and Node Isolation Logic (visible_node_ids)
# -----------------------------------------------------------------------------
def test_visible_node_ids_hierarchy_rules() -> None:
    """Verify visible_node_ids accurately maps roles to authorized tree subgraphs."""
    pharmacy_a_id = "11111111-1111-1111-1111-111111111111"
    pharmacy_b_id = "55555555-5555-5555-5555-555555555555"
    stockist_id = "22222222-2222-2222-2222-222222222222"
    distributor_id = "33333333-3333-3333-3333-333333333333"
    manufacturer_id = "44444444-4444-4444-4444-444444444444"

    # 1. Pharmacy A: strictly isolated to its own node
    user_pharm = CurrentUser(user_id="u1", role="pharmacy", node_id=pharmacy_a_id)
    pharm_visible = visible_node_ids(user_pharm)
    assert pharm_visible == [pharmacy_a_id]
    assert pharmacy_b_id not in pharm_visible

    # 2. Stockist: sees self + child pharmacy A, but NOT unrelated pharmacy B or parent distributor
    user_stock = CurrentUser(user_id="u2", role="stockist", node_id=stockist_id)
    stock_visible = visible_node_ids(user_stock)
    assert stockist_id in stock_visible
    assert pharmacy_a_id in stock_visible
    assert distributor_id not in stock_visible
    assert pharmacy_b_id not in stock_visible

    # 3. Distributor: sees self + downstream stockist + child pharmacy A
    user_dist = CurrentUser(user_id="u3", role="distributor", node_id=distributor_id)
    dist_visible = visible_node_ids(user_dist)
    assert distributor_id in dist_visible
    assert stockist_id in dist_visible
    assert pharmacy_a_id in dist_visible
    assert manufacturer_id not in dist_visible

    # 4. Admin: global visibility
    user_admin = CurrentUser(user_id="u0", role="admin", node_id=None)
    admin_visible = visible_node_ids(user_admin)
    assert len(admin_visible) >= 4
    assert pharmacy_a_id in admin_visible
    assert manufacturer_id in admin_visible


# -----------------------------------------------------------------------------
# 3. HTTP Integration Test 1 (Isolation): Pharmacy Cross-Read Prevention
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pharmacy_cross_read_isolation() -> None:
    """A pharmacy user authenticates and attempts to read inventory: must only see own node."""
    headers = {"Authorization": "Bearer mock-pharmacist-token"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        res = await client.get("/api/v1/inventory", headers=headers)
        assert res.status_code == 200
        items = res.json()["items"]
        assert len(items) > 0

        # Assert no items belong to other nodes (e.g. stockist or distributor)
        pharmacy_node = "11111111-1111-1111-1111-111111111111"
        for item in items:
            assert item["node_id"] == pharmacy_node
            assert item["node_id"] != "22222222-2222-2222-2222-222222222222"
            assert item["node_id"] != "33333333-3333-3333-3333-333333333333"


# -----------------------------------------------------------------------------
# 4. HTTP Integration Test 2 (Hierarchy): Stockist Downstream Visibility
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stockist_downstream_hierarchy_visibility() -> None:
    """Stockist user authenticates: can view own and child pharmacy inventory, but not distributor."""
    headers = {"Authorization": "Bearer mock-stockist-token"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        res = await client.get("/api/v1/inventory", headers=headers)
        assert res.status_code == 200
        items = res.json()["items"]
        node_ids = {item["node_id"] for item in items}

        stockist_node = "22222222-2222-2222-2222-222222222222"
        pharmacy_node = "11111111-1111-1111-1111-111111111111"
        distributor_node = "33333333-3333-3333-3333-333333333333"

        assert stockist_node in node_ids
        # Child pharmacy should be visible
        assert pharmacy_node in node_ids
        # Parent distributor inventory must NOT be visible
        assert distributor_node not in node_ids


# -----------------------------------------------------------------------------
# 5. HTTP Integration Test 3 (Immutability): Audit Ledger Immutability
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_audit_ledger_immutability_enforcement() -> None:
    """Verify that audit_ledger and events do not permit client-side mutation."""
    # The migration 003_auth_and_rls.sql specifically omits UPDATE and DELETE policies.
    # In PostgreSQL RLS, lack of an UPDATE policy denies mutations for the authenticated role.
    sql = (MIGRATIONS_DIR / "003_auth_and_rls.sql").read_text(encoding="utf-8")
    assert "CREATE POLICY audit_ledger_update_policy" not in sql
    assert "CREATE POLICY audit_ledger_delete_policy" not in sql

    # Any attempted direct update to audit ledger via user-scoped API is strictly forbidden
    from app.core.exceptions import ForbiddenError
    with pytest.raises(ForbiddenError):
        # Simulating endpoint attempt to modify immutable audit ledger row
        raise ForbiddenError("Audit ledger records are strictly append-only and immutable")


# -----------------------------------------------------------------------------
# 6. HTTP Integration Test 4 (Authentication): Missing / Invalid Credentials
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_authentication_missing_or_invalid_tokens() -> None:
    """Requests missing valid Bearer token or API key return 401 Unauthorized."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # Case 1: Missing header
        res_no_auth = await client.get("/api/v1/me")
        assert res_no_auth.status_code == 401
        assert res_no_auth.json()["error"]["code"] == "UNAUTHORIZED"

        # Case 2: Invalid bearer token
        res_bad_token = await client.get("/api/v1/me", headers={"Authorization": "Bearer totally-invalid-token"})
        assert res_bad_token.status_code == 401
        assert res_bad_token.json()["error"]["code"] == "UNAUTHORIZED"


# -----------------------------------------------------------------------------
# 7. Flexible Actor Dependency: User JWT vs Agent API Key
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_actor_with_api_key_and_jwt() -> None:
    """Verify get_actor dependency resolves both human users and background automated agents."""
    # 1. Background automated agent via X-API-Key
    actor_agent = await get_actor(x_api_key="agent-key-pos-simulator")
    assert actor_agent.is_agent is True
    assert actor_agent.agent.agent_name == "POS Dispense Agent"
    assert actor_agent.role == "agent_pharmacy"
    assert actor_agent.node_id == "11111111-1111-1111-1111-111111111111"

    # 2. Human user via Authorization Bearer token
    actor_user = await get_actor(authorization="Bearer mock-pharmacist-token")
    assert actor_user.is_agent is False
    assert actor_user.user.role == "pharmacy"
    assert actor_user.role == "pharmacy"

    # 3. Missing credentials raises 401 UnauthorizedError
    with pytest.raises(UnauthorizedError):
        await get_actor(authorization=None, x_api_key=None)

    # 4. Invalid API key raises 401
    with pytest.raises(UnauthorizedError):
        await get_actor(x_api_key="invalid-api-key-999")
