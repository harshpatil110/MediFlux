"""Database persistence package via Supabase (PostgreSQL, pgvector, RLS)."""

from app.db.client import get_supabase_client

__all__ = ["get_supabase_client"]
