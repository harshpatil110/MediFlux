"""Bootstrap coding agent to compile plain-English policies into verified active modules."""

import logging
from pathlib import Path

from app.modules_runtime.contract import ModuleVersion
from app.modules_runtime.registry import module_registry

logger = logging.getLogger("mediflux.agents.bootstrap")

# Canonical deterministic implementations for initial policies
BOOTSTRAP_MODULES: dict[str, dict[str, str]] = {
    "margin_rules": {
        "kind": "margin_rules",
        "code": """def run(input: dict) -> dict:
    cost = float(input.get("cost_price", 0.0))
    selling = float(input.get("selling_price", 0.0))
    if selling <= 0:
        return {"margin_percentage": 0.0, "margin_inr": 0.0, "meets_minimum": False, "flagged": True}
    margin_inr = round(selling - cost, 2)
    margin_pct = round(margin_inr / selling, 4)
    return {
        "margin_percentage": margin_pct,
        "margin_inr": margin_inr,
        "meets_minimum": margin_pct >= 0.15,
        "flagged": margin_pct < 0.10,
    }
""",
        "tests_source": """def test_run():
    res1 = run({"cost_price": 80.0, "selling_price": 100.0})
    assert res1["margin_percentage"] == 0.2
    assert res1["meets_minimum"] is True
    assert res1["flagged"] is False

    res2 = run({"cost_price": 95.0, "selling_price": 100.0})
    assert res2["margin_percentage"] == 0.05
    assert res2["meets_minimum"] is False
    assert res2["flagged"] is True
""",
    },
    "volume_discount": {
        "kind": "volume_discount",
        "code": """def run(input: dict) -> dict:
    qty = int(input.get("quantity", 0))
    unit_price = float(input.get("unit_price", 0.0))
    base_total = qty * unit_price

    if qty > 1000:
        rate = 0.08
    elif qty > 500:
        rate = 0.05
    elif qty > 100:
        rate = 0.02
    else:
        rate = 0.0

    discount_amount = round(base_total * rate, 2)
    final_total = round(base_total - discount_amount, 2)
    return {
        "discount_percentage": rate,
        "discount_amount": discount_amount,
        "final_total": final_total,
    }
""",
        "tests_source": """def test_run():
    res1 = run({"quantity": 150, "unit_price": 10.0})
    assert res1["discount_percentage"] == 0.02
    assert res1["final_total"] == 1470.0

    res2 = run({"quantity": 1200, "unit_price": 10.0})
    assert res2["discount_percentage"] == 0.08
    assert res2["final_total"] == 11040.0
""",
    },
    "credit_check_rules": {
        "kind": "credit_check_rules",
        "code": """def run(input: dict) -> dict:
    outstanding = float(input.get("outstanding_balance", 0.0))
    order_total = float(input.get("order_total", 0.0))
    credit_limit = float(input.get("credit_limit", 50000.0))

    total_exposure = round(outstanding + order_total, 2)
    approved = total_exposure <= credit_limit
    breached_by = round(max(0.0, total_exposure - credit_limit), 2)

    return {
        "approved": approved,
        "total_exposure": total_exposure,
        "credit_limit": credit_limit,
        "breached_by": breached_by,
    }
""",
        "tests_source": """def test_run():
    res1 = run({"outstanding_balance": 10000.0, "order_total": 20000.0, "credit_limit": 50000.0})
    assert res1["approved"] is True
    assert res1["breached_by"] == 0.0

    res2 = run({"outstanding_balance": 40000.0, "order_total": 15000.0, "credit_limit": 50000.0})
    assert res2["approved"] is False
    assert res2["breached_by"] == 5000.0
""",
    },
    "price_ceiling": {
        "kind": "price_ceiling",
        "code": """def run(input: dict) -> dict:
    medicine_id = str(input.get("medicine_id", ""))
    unit_price = float(input.get("unit_price", 0.0))
    neml_ceiling = float(input.get("neml_ceiling_price", 0.0))

    compliant = unit_price <= neml_ceiling
    excess = round(max(0.0, unit_price - neml_ceiling), 2)

    return {
        "compliant": compliant,
        "unit_price": unit_price,
        "ceiling_price": neml_ceiling,
        "excess_amount": excess,
    }
""",
        "tests_source": """def test_run():
    res1 = run({"medicine_id": "MED-001", "unit_price": 45.0, "neml_ceiling_price": 50.0})
    assert res1["compliant"] is True
    assert res1["excess_amount"] == 0.0

    res2 = run({"medicine_id": "MED-001", "unit_price": 55.0, "neml_ceiling_price": 50.0})
    assert res2["compliant"] is False
    assert res2["excess_amount"] == 5.0
""",
    },
}


class BootstrapAgent:
    """Agent responsible for bootstrapping plain-English policies into verified active modules."""

    def __init__(self, policy_file_path: str = "config/bootstrap_policies.md") -> None:
        self.policy_file_path = policy_file_path

    def load_policies(self) -> str:
        """Read markdown policy definitions from disk."""
        candidates = [
            Path(self.policy_file_path),
            Path("backend") / self.policy_file_path,
            Path(__file__).parent.parent.parent / self.policy_file_path,
        ]
        for p in candidates:
            if p.is_file():
                return p.read_text(encoding="utf-8")
        return ""

    def bootstrap_all_modules(self) -> dict[str, ModuleVersion]:
        """Compile, test, and activate all initial business rule modules."""
        logger.info("BootstrapAgent: Starting module compilation and activation...")
        activated_modules: dict[str, ModuleVersion] = {}

        for mod_name, mod_info in BOOTSTRAP_MODULES.items():
            kind = mod_info["kind"]
            code = mod_info["code"]
            tests_source = mod_info["tests_source"]

            # 1. Create version (runs static AST guard)
            version = module_registry.create_version(
                name=mod_name,
                kind=kind,
                code=code,
                tests_source=tests_source,
                created_by="bootstrap_agent",
            )

            # 2. Run isolated tests & activate atomically
            active_version = module_registry.activate(mod_name, version.version)
            activated_modules[mod_name] = active_version
            logger.info("BootstrapAgent: Activated module [%s v%d]", mod_name, active_version.version)

        return activated_modules


bootstrap_agent = BootstrapAgent()
