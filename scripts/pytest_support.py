"""Keep automated checks independent of local cloud credentials and push services."""

import os
from collections.abc import Iterator

import pytest

# Set these before collection imports the application or seeds its module registry.
# Database-specific tests explicitly supply their own clients and settings.
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = ""
os.environ["PUSH_ENABLED"] = "false"
os.environ["EMBEDDING_PROVIDER"] = "local_semantic"
os.environ["NVIDIA_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""
os.environ["DEMO_MODE"] = "false"
os.environ["LLM_CACHE_MODE"] = "off"


@pytest.fixture(autouse=True)
def restore_runtime_settings() -> Iterator[None]:
    """Prevent demo and fault-injection tests from changing later tests' settings."""
    from app.core.config import settings

    original = settings.model_dump()
    yield
    for name, value in original.items():
        setattr(settings, name, value)
