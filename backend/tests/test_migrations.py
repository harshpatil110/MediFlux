"""Validation tests verifying Supabase SQL migration files integrity and syntax."""

from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations"


def test_migration_files_exist() -> None:
    """Ensure all required SQL migration files exist."""
    expected_files = [
        "20260101000001_initial_schema.sql",
        "20260101000002_atomic_functions.sql",
        "20260101000003_indexes.sql",
    ]
    for filename in expected_files:
        migration_file = MIGRATIONS_DIR / filename
        assert migration_file.exists(), f"Missing migration file: {filename}"
        assert migration_file.stat().st_size > 0, f"Empty migration file: {filename}"


def test_initial_schema_completeness() -> None:
    """Verify initial schema defines extensions, enums, tables, and constraints."""
    content = (MIGRATIONS_DIR / "20260101000001_initial_schema.sql").read_text(encoding="utf-8")

    # Extensions
    assert "CREATE EXTENSION IF NOT EXISTS vector;" in content
    assert 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp";' in content

    # Enums
    expected_enums = [
        "node_tier",
        "batch_status",
        "order_status",
        "transfer_status",
        "shipment_status",
        "production_status",
        "module_kind",
        "module_status",
        "hitl_status",
        "schedule_class",
    ]
    for enum_name in expected_enums:
        assert f"CREATE TYPE {enum_name}" in content

    # Tables
    expected_tables = [
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
    for table_name in expected_tables:
        assert f"CREATE TABLE IF NOT EXISTS {table_name}" in content

    # Idempotency constraint on events
    assert "event_id TEXT UNIQUE NOT NULL" in content

    # Vector columns
    assert "embedding vector(1536)" in content


def test_atomic_functions_completeness() -> None:
    """Verify PL/pgSQL atomic functions exist and contain locking logic."""
    content = (MIGRATIONS_DIR / "20260101000002_atomic_functions.sql").read_text(encoding="utf-8")

    # Functions exist
    assert "CREATE OR REPLACE FUNCTION apply_sale" in content
    assert "CREATE OR REPLACE FUNCTION apply_return" in content
    assert "CREATE OR REPLACE FUNCTION apply_expiry" in content

    # Concurrency control keywords
    assert "FOR UPDATE" in content
    assert "oversold" in content
    assert "ON CONFLICT" in content


def test_indexes_completeness() -> None:
    """Verify required B-Tree and HNSW vector search indexes exist."""
    content = (MIGRATIONS_DIR / "20260101000003_indexes.sql").read_text(encoding="utf-8")

    expected_indexes = [
        "idx_events_created_at",
        "idx_events_correlation_id",
        "idx_agent_runs_correlation_id",
        "idx_inventory_node_product",
        "idx_batches_product",
        "idx_demand_signals_embedding",
        "idx_reg_notifications_embedding",
    ]
    for idx in expected_indexes:
        assert idx in content

    # HNSW vector search
    assert "USING hnsw (embedding vector_cosine_ops)" in content
