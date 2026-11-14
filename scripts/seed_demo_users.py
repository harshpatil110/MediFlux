"""Seed script for MediFlux demo users across all 5 supply chain roles.

Creates demo users in Supabase Auth and populates corresponding profiles table entries.
Idempotent: Safely skips or updates existing users.
"""

import sys
from pathlib import Path

# Ensure backend/ is in sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.core.config import settings
from app.db.client import get_supabase_client

DEMO_NODES = [
    {
        "id": "44444444-4444-4444-4444-444444444444",
        "tier": "manufacturer",
        "name": "Sun Pharma Formulation Plant - Baddi",
        "region": "HP-Baddi",
        "parent_id": None,
        "address": "Industrial Area, Baddi, Himachal Pradesh 173205",
        "is_active": True,
    },
    {
        "id": "33333333-3333-3333-3333-333333333333",
        "tier": "distributor",
        "name": "Northern India Regional Depot",
        "region": "HR-Gurugram",
        "parent_id": "44444444-4444-4444-4444-444444444444",
        "address": "Udyog Vihar Phase 4, Gurugram 122016",
        "is_active": True,
    },
    {
        "id": "22222222-2222-2222-2222-222222222222",
        "tier": "stockist",
        "name": "North Delhi Stockist Hub",
        "region": "DL-Delhi-North",
        "parent_id": "33333333-3333-3333-3333-333333333333",
        "address": "Okhla Phase III, New Delhi 110020",
        "is_active": True,
    },
    {
        "id": "11111111-1111-1111-1111-111111111111",
        "tier": "pharmacy",
        "name": "Apollo Pharmacy - Connaught Place",
        "region": "DL-Delhi-Central",
        "parent_id": "22222222-2222-2222-2222-222222222222",
        "address": "Block B, Connaught Place, New Delhi 110001",
        "is_active": True,
    },
]

DEMO_USERS = [
    {
        "email": "admin@mediflux.in",
        "password": "AdminPassword123!",
        "role": "admin",
        "node_id": None,
    },
    {
        "email": "manufacturer@mediflux.in",
        "password": "MfgPassword123!",
        "role": "manufacturer",
        "node_id": "44444444-4444-4444-4444-444444444444",
    },
    {
        "email": "distributor@mediflux.in",
        "password": "DistPassword123!",
        "role": "distributor",
        "node_id": "33333333-3333-3333-3333-333333333333",
    },
    {
        "email": "stockist@mediflux.in",
        "password": "StockPassword123!",
        "role": "stockist",
        "node_id": "22222222-2222-2222-2222-222222222222",
    },
    {
        "email": "pharmacy@mediflux.in",
        "password": "PharmPassword123!",
        "role": "pharmacy",
        "node_id": "11111111-1111-1111-1111-111111111111",
    },
]


def seed_nodes(client) -> None:
    """Ensure baseline hierarchy nodes exist in nodes table."""
    print("\n--- Seeding Base Supply Chain Nodes ---")
    for node in DEMO_NODES:
        try:
            client.table("nodes").upsert(node, on_conflict="id").execute()
            print(f"  ✅ Node: {node['name']} ({node['tier']})")
        except Exception as exc:
            print(f"  ⚠️ Node {node['name']} upsert note: {exc}")


def seed_users(client) -> None:
    """Create Auth users and corresponding profiles."""
    print("\n--- Seeding 5 Role-Based Demo Users ---")

    # Fetch existing users to ensure idempotency
    existing_users: dict[str, str] = {}
    try:
        users_resp = client.auth.admin.list_users()
        user_list = users_resp if isinstance(users_resp, list) else getattr(users_resp, "users", [])
        for u in user_list:
            if hasattr(u, "email") and hasattr(u, "id"):
                existing_users[u.email] = u.id
    except Exception as list_exc:
        print(f"  ⚠️ Could not pre-fetch existing users: {list_exc}")

    for user_info in DEMO_USERS:
        email = user_info["email"]
        password = user_info["password"]
        role = user_info["role"]
        node_id = user_info["node_id"]

        user_id = existing_users.get(email)

        # 1. Create in Supabase Auth if not already existing
        if not user_id:
            try:
                auth_res = client.auth.admin.create_user(
                    {
                        "email": email,
                        "password": password,
                        "email_confirm": True,
                        "user_metadata": {"role": role, "node_id": node_id},
                    }
                )
                if auth_res and hasattr(auth_res, "user") and auth_res.user:
                    user_id = auth_res.user.id
                    print(f"  ✅ Created Auth User: {email} (ID: {user_id})")
            except Exception as exc:
                print(f"  ⚠️ Auth creation note for {email}: {exc}")
        else:
            print(f"  ℹ️ Found Existing Auth User: {email} (ID: {user_id})")

        # 2. Upsert profile record
        if user_id:
            profile_data = {
                "user_id": user_id,
                "role": role,
                "node_id": node_id,
                "email": email,
            }
            try:
                client.table("profiles").upsert(profile_data, on_conflict="user_id").execute()
                print(f"  ✅ Linked Profile: {email} -> role={role}, node={node_id}")
            except Exception as prof_exc:
                print(f"  ⚠️ Profile upsert note for {email}: {prof_exc}")
        else:
            print(f"  ❌ Skipping profile for {email} (could not resolve Auth user ID)")


def main() -> None:
    client = get_supabase_client()
    if not client:
        print("❌ Cannot connect to Supabase. Check SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env")
        sys.exit(1)

    print(f"Connected to Supabase: {settings.SUPABASE_URL}")
    seed_nodes(client)
    seed_users(client)
    print("\n🎉 Demo users seeding script completed.")


if __name__ == "__main__":
    main()
