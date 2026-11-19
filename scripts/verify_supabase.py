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
        print("[FAIL] Could not initialize Supabase client. Check credentials in .env")
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
        "doctor_registry",
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
            print(f"  [OK] {tbl}")
            success_count += 1
        except Exception as exc:
            err_msg = str(exc)
            if "PGRST205" in err_msg or "Could not find the table" in err_msg:
                print(f"  [FAIL] {tbl} (Table not yet created)")
            else:
                print(f"  [FAIL] {tbl}: {err_msg[:60]}")
            missing_tables.append(tbl)

    print(f"\nResult: {success_count}/{len(tables)} tables verified.")

    if missing_tables:
        print(f"\n[FAIL] {len(missing_tables)} tables could not be verified in Supabase.")
        print("Review the errors above and the migrations in supabase/migrations.")
        sys.exit(1)
    else:
        print("\n[OK] All MediFlux tables verified successfully on Supabase!")
        sys.exit(0)


if __name__ == "__main__":
    main()
