"""Supabase client factory and database connection helper."""

from supabase import Client, create_client

from app.core.config import settings
from app.core.logging import logger

_supabase_client: Client | None = None


def get_supabase_client() -> Client | None:
    """Retrieve or initialize singleton Supabase client."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        logger.warning(
            "Supabase credentials not configured. Running in disconnected local mode."
        )
        return None

    try:
        _supabase_client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY,
        )
        return _supabase_client
    except Exception as exc:
        logger.error("Failed to initialize Supabase client: %s", exc)
        return None
