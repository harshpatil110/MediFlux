"""Verification script for MediFlux Supabase schema and functions."""

import sys
from pathlib import Path

# Ensure backend/ directory is on sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.core.config import settings
from app.db.client import get_supabase_client


def main() -> None:
    client = get_supabase_client()
    if not client:
        print("❌ Could not initialize Supabase client. Check credentials in .env")
        sys.exit(1)

    print(f"Connecting to Supabase at: {settings.SUPABASE_URL}")

    tables = [
        "nodes",
        "profiles",
        "products",
        "batches",
        "inventory",
        "api_inventory",
        "events",
        "orders",
        "transfers",
        "fleet_vehicles",
        "shipments",
        "credit_accounts",
        "settlements",
        "production_lines",
        "production_batches",
        "demand_signals",
        "drug_schedules",
        "doctor_registry_mock",
        "prescriptions",
        "compliance_logs",
        "sensor_readings",
        "quarantine_actions",
        "agent_runs",
        "modules",
        "adapters",
        "reg_notifications",
        "hitl_tasks",
        "audit_ledger",
        "api_keys",
        "webhook_subscriptions",
        "webhook_deliveries",
    ]

    success_count = 0
    missing_tables = []

    print("\n--- Verifying Tables ---")
    for tbl in tables:
        try:
            client.table(tbl).select("*").limit(1).execute()
            print(f"  ✅ {tbl}")
            success_count += 1
        except Exception as exc:
            err_msg = str(exc)
            if "PGRST205" in err_msg or "Could not find the table" in err_msg:
                print(f"  ❌ {tbl} (Table not yet created)")
            else:
                print(f"  ❌ {tbl}: {err_msg[:60]}")
            missing_tables.append(tbl)

    print(f"\nResult: {success_count}/{len(tables)} tables verified.")

    if missing_tables:
        print(f"\n⚠️ {len(missing_tables)} tables are pending migration in Supabase.")
        print("Please follow Option A to paste and run the 3 SQL files in the Supabase Dashboard SQL Editor.")
        sys.exit(1)
    else:
        print("\n🎉 All MediFlux tables verified successfully on Supabase!")
        sys.exit(0)


if __name__ == "__main__":
    main()
