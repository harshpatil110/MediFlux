"""Direct PostgreSQL migration runner for Supabase."""

import os
from pathlib import Path
import sys
from dotenv import load_dotenv

# Load .env
load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import psycopg2

SQL_FILE = Path(__file__).resolve().parent.parent / "supabase" / "all_migrations_combined.sql"


def main() -> None:
    db_url = os.getenv("DATABASE_URL")
    db_pass = os.getenv("SUPABASE_DB_PASSWORD")
    project_url = os.getenv("SUPABASE_URL", "")

    conn = None

    if db_url:
        print(f"Connecting to database via DATABASE_URL...")
        conn = psycopg2.connect(db_url)
    elif db_pass and "supabase.co" in project_url:
        project_ref = project_url.replace("https://", "").replace(".supabase.co", "").strip("/")
        # Try direct host
        host = f"db.{project_ref}.supabase.co"
        print(f"Connecting to Postgres at {host}:5432...")
        try:
            conn = psycopg2.connect(
                dbname="postgres",
                user="postgres",
                password=db_pass,
                host=host,
                port=5432,
                sslmode="require",
                connect_timeout=10,
            )
        except Exception as exc:
            print(f"Direct connection failed ({exc}). Trying session pooler...")
            # Try default AWS pooler
            conn = psycopg2.connect(
                dbname="postgres",
                user=f"postgres.{project_ref}",
                password=db_pass,
                host="aws-0-ap-south-1.pooler.supabase.com",
                port=5432,
                sslmode="require",
                connect_timeout=10,
            )
    else:
        print("❌ Neither DATABASE_URL nor SUPABASE_DB_PASSWORD is configured in .env.")
        print("To apply migrations automatically, add SUPABASE_DB_PASSWORD=<your_db_password> to .env")
        print("Or paste supabase/all_migrations_combined.sql into Supabase Dashboard SQL Editor.")
        sys.exit(1)

    print(f"Reading migration file: {SQL_FILE.name}...")
    sql_content = SQL_FILE.read_text(encoding="utf-8")

    print("Executing all migrations on Supabase PostgreSQL...")
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(sql_content)

    conn.close()
    print("✅ All migrations applied successfully via PostgreSQL direct connection!")


if __name__ == "__main__":
    main()
