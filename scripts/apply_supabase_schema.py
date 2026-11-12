"""Database schema migration executor for Tasks 9 through 16."""

import os
from pathlib import Path
import sys
from dotenv import load_dotenv
import psycopg2

# Load environment configurations from both backend/.env and root .env
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / "backend" / ".env")
load_dotenv(ROOT_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
SUPABASE_DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")


def get_connection():
    """Establish PostgreSQL connection via DATABASE_URL or project credentials."""
    if DATABASE_URL:
        print("[*] Connecting via DATABASE_URL...")
        return psycopg2.connect(DATABASE_URL)

    if SUPABASE_DB_PASSWORD and "supabase.co" in SUPABASE_URL:
        project_ref = (
            SUPABASE_URL.replace("https://", "").replace(".supabase.co", "").strip("/")
        )
        host = f"db.{project_ref}.supabase.co"
        print(f"[*] Connecting to Supabase PostgreSQL at {host}:5432...")
        try:
            return psycopg2.connect(
                dbname="postgres",
                user="postgres",
                password=SUPABASE_DB_PASSWORD,
                host=host,
                port=5432,
                sslmode="require",
                connect_timeout=10,
            )
        except Exception as exc:
            print(f"[*] Direct connection failed ({exc}). Trying session pooler...")
            return psycopg2.connect(
                dbname="postgres",
                user=f"postgres.{project_ref}",
                password=SUPABASE_DB_PASSWORD,
                host="aws-0-ap-south-1.pooler.supabase.com",
                port=5432,
                sslmode="require",
                connect_timeout=10,
            )

    return None


def verify_tables():
    """Verify table creation across Tasks 9 to 16."""
    target_tables = [
        "doctor_registry",
        "drug_schedules",
        "pos_transactions",
        "orders",
        "transfers",
        "credit_accounts",
        "settlements",
        "fleet_vehicles",
        "shipments",
        "demand_signals",
        "production_lines",
        "production_batches",
        "api_inventory",
        "hitl_tasks",
        "audit_ledger",
    ]

    # Add backend directory to sys.path to leverage Supabase client if available
    backend_path = ROOT_DIR / "backend"
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))

    try:
        from app.db.client import get_supabase_client

        client = get_supabase_client()
    except Exception:
        client = None

    print("\n--- Verifying Table Creation (Tasks 9 to 16) ---")
    verified = []
    missing = []

    for tbl in target_tables:
        table_ok = False
        if client:
            try:
                client.table(tbl).select("*").limit(1).execute()
                table_ok = True
            except Exception:
                table_ok = False

        if not table_ok:
            conn = None
            try:
                conn = get_connection()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s);",
                            (tbl,),
                        )
                        table_ok = bool(cur.fetchone()[0])
            except Exception:
                pass
            finally:
                if conn:
                    conn.close()

        if table_ok:
            print(f"  [✓] {tbl}")
            verified.append(tbl)
        else:
            print(f"  [ ] {tbl}")
            missing.append(tbl)

    print(f"\nResult: {len(verified)}/{len(target_tables)} tables verified.")
    return len(missing) == 0


def apply_migrations():
    """Read and execute supabase/migrations/tasks_9_to_16_schema.sql."""
    sql_file = ROOT_DIR / "supabase" / "migrations" / "tasks_9_to_16_schema.sql"
    if not sql_file.exists():
        print(f"[X] Migration file not found: {sql_file}")
        return False

    with open(sql_file, "r", encoding="utf-8") as f:
        sql_content = f.read()

    conn = get_connection()
    if not conn:
        print("[!] DATABASE_URL not set in .env. Please provide PostgreSQL connection string.")
        print("    Format: postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres")
        print("    Alternatively, you can run supabase/migrations/tasks_9_to_16_schema.sql")
        print("    directly in the Supabase Dashboard SQL Editor.")
        return False

    try:
        conn.autocommit = True
        with conn.cursor() as cursor:
            cursor.execute(sql_content)
        print("[✓] Successfully executed migration: tasks_9_to_16_schema.sql")
        conn.close()
        verify_tables()
        return True
    except Exception as e:
        print(f"[X] Migration failed: {e}")
        if conn:
            conn.close()
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        verify_tables()
    else:
        apply_migrations()
