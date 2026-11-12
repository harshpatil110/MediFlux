"""Unit and security test suite for Task 8: Dynamic Module Runtime and Restricted Execution Guard."""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.agents.bootstrap_agent import bootstrap_agent
from app.core.config import settings
from app.main import app
from app.modules_runtime.guard import (
    ASTGuard,
    GuardViolationError,
    ModuleTimeoutError,
    SubprocessRunner,
)
from app.modules_runtime.registry import module_registry


@pytest.fixture(autouse=True)
def clean_registry_environment() -> None:
    """Ensure module registry is clean and database calls are mocked during tests."""
    module_registry.clear()
    with patch.object(settings, "SUPABASE_URL", ""):
        yield
    module_registry.clear()


# -----------------------------------------------------------------------------
# 1. Malicious Code Rejection Tests (Static AST Guard)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "malicious_code,expected_keyword",
    [
        ("import os\ndef run(input):\n    os.system('ls')", "os"),
        ("import sys\ndef run(input):\n    sys.exit(0)", "sys"),
        ("import subprocess\ndef run(input):\n    return {}", "subprocess"),
        ("import socket\ndef run(input):\n    return {}", "socket"),
        ("def run(input):\n    f = open('/etc/passwd', 'r')\n    return {}", "open"),
        ("def run(input):\n    eval('1 + 1')\n    return {}", "eval"),
        ("def run(input):\n    exec('x = 1')\n    return {}", "exec"),
        (
            "def run(input):\n    subs = ().__class__.__subclasses__()\n    return {}",
            "__class__",
        ),
        (
            "def run(input):\n    return input['__globals__']",
            "__globals__",
        ),
    ],
)
def test_malicious_code_rejected_by_ast_guard(malicious_code: str, expected_keyword: str) -> None:
    """Verify that dangerous imports, built-ins, and dunder attributes are blocked immediately."""
    with pytest.raises(GuardViolationError) as exc_info:
        ASTGuard.validate_code(malicious_code)

    assert "Static AST Guard security policy violated" in str(exc_info.value)
    assert expected_keyword in str(exc_info.value)


# -----------------------------------------------------------------------------
# 2. Infinite Loop Timeout Test
# -----------------------------------------------------------------------------
def test_infinite_loop_timeout_protection() -> None:
    """Verify that a module containing an infinite loop is terminated by the hard timeout."""
    loop_code = """
def run(input: dict) -> dict:
    while True:
        pass
    return {}
"""
    ASTGuard.validate_code(loop_code)

    # Enforce short 0.5s timeout for fast test execution
    with pytest.raises(ModuleTimeoutError) as exc_info:
        SubprocessRunner.execute_module(source_code=loop_code, input_data={}, timeout=0.5)

    assert "timed out" in str(exc_info.value)


# -----------------------------------------------------------------------------
# 3. Atomic Hot-Swap & Version Rollback Test
# -----------------------------------------------------------------------------
def test_atomic_hot_swap_and_rollback() -> None:
    """Verify dynamic modules can be updated and rolled back instantly without server restart."""
    module_name = "test_discount_rule"
    kind = "volume_discount"

    # Version 1: 10% discount
    v1_code = """def run(input: dict) -> dict:
    price = float(input.get('price', 100))
    return {'discounted_price': price * 0.9}
"""
    v1_test = """def test_run():
    res = run({'price': 100})
    assert res['discounted_price'] == 90.0
"""

    # Version 2: 20% discount
    v2_code = """def run(input: dict) -> dict:
    price = float(input.get('price', 100))
    return {'discounted_price': price * 0.8}
"""
    v2_test = """def test_run():
    res = run({'price': 100})
    assert res['discounted_price'] == 80.0
"""

    # 1. Register and activate Version 1
    v1 = module_registry.create_version(module_name, kind, v1_code, v1_test)
    assert v1.version == 1
    module_registry.activate(module_name, 1)

    res_v1 = module_registry.run_module(module_name, {"price": 100})
    assert res_v1["discounted_price"] == 90.0

    # 2. Register and hot-swap to Version 2
    v2 = module_registry.create_version(module_name, kind, v2_code, v2_test)
    assert v2.version == 2
    module_registry.activate(module_name, 2)

    res_v2 = module_registry.run_module(module_name, {"price": 100})
    assert res_v2["discounted_price"] == 80.0  # Instantly hot-swapped!

    # 3. Roll back to Version 1
    rolled_back = module_registry.rollback(module_name)
    assert rolled_back.version == 1

    res_rollback = module_registry.run_module(module_name, {"price": 100})
    assert res_rollback["discounted_price"] == 90.0  # Restored to V1 behavior


# -----------------------------------------------------------------------------
# 4. Bootstrap Agent End-to-End Test
# -----------------------------------------------------------------------------
def test_bootstrap_agent_compiles_and_activates_all_modules() -> None:
    """Verify BootstrapAgent compiles policies into 4 verified active modules."""
    activated = bootstrap_agent.bootstrap_all_modules()

    expected_modules = ["margin_rules", "volume_discount", "credit_check_rules", "price_ceiling"]
    for mod_name in expected_modules:
        assert mod_name in activated
        assert activated[mod_name].status == "active"

    # Verify margin_rules behavior
    margin_res = module_registry.run_module("margin_rules", {"cost_price": 80.0, "selling_price": 100.0})
    assert margin_res["margin_percentage"] == 0.20
    assert margin_res["meets_minimum"] is True
    assert margin_res["flagged"] is False

    # Verify volume_discount behavior
    disc_res = module_registry.run_module("volume_discount", {"quantity": 600, "unit_price": 10.0})
    assert disc_res["discount_percentage"] == 0.05
    assert disc_res["discount_amount"] == 300.0
    assert disc_res["final_total"] == 5700.0

    # Verify credit_check_rules behavior
    credit_res = module_registry.run_module(
        "credit_check_rules",
        {"outstanding_balance": 30000.0, "order_total": 25000.0, "credit_limit": 50000.0},
    )
    assert credit_res["approved"] is False
    assert credit_res["breached_by"] == 5000.0

    # Verify price_ceiling behavior
    ceiling_res = module_registry.run_module(
        "price_ceiling",
        {"medicine_id": "MED-001", "unit_price": 60.0, "neml_ceiling_price": 50.0},
    )
    assert ceiling_res["compliant"] is False
    assert ceiling_res["excess_amount"] == 10.0


# -----------------------------------------------------------------------------
# 5. Admin API Endpoints Test
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_modules_api_endpoints() -> None:
    """Verify admin endpoints list active modules, versions, and handle rollbacks with RBAC."""
    # Seed one module with 2 versions
    bootstrap_agent.bootstrap_all_modules()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # 1. GET /api/v1/modules with valid auth
        res_list = await client.get("/api/v1/modules", headers={"Authorization": "Bearer mock-pharmacist-token"})
        assert res_list.status_code == 200
        modules = res_list.json()
        assert len(modules) >= 4
        names = [m["name"] for m in modules]
        assert "margin_rules" in names

        # 2. GET /api/v1/modules/{name}/versions
        res_ver = await client.get(
            "/api/v1/modules/margin_rules/versions",
            headers={"Authorization": "Bearer mock-pharmacist-token"},
        )
        assert res_ver.status_code == 200
        assert len(res_ver.json()) >= 1

        # 3. POST /api/v1/modules/{name}/rollback without admin role (Pharmacist) -> 403
        res_rb_unauth = await client.post(
            "/api/v1/modules/margin_rules/rollback",
            headers={"Authorization": "Bearer mock-pharmacist-token"},
        )
        assert res_rb_unauth.status_code == 403

        # Add v2 so rollback can succeed
        v2_code = """def run(input: dict) -> dict:\n    return {'margin_percentage': 0.3}\n"""
        v2_test = """def test_run():\n    assert run({})['margin_percentage'] == 0.3\n"""
        module_registry.create_version("margin_rules", "margin_rules", v2_code, v2_test)
        module_registry.activate("margin_rules", 2)

        # 4. POST /api/v1/modules/{name}/rollback with admin token -> 200 OK
        res_rb_admin = await client.post(
            "/api/v1/modules/margin_rules/rollback",
            headers={"Authorization": "Bearer mock-admin-token"},
        )
        assert res_rb_admin.status_code == 200
        assert res_rb_admin.json()["version"] == 1
