"""Application configuration management using Pydantic Settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for MediFlux backend services."""

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Project metadata
    PROJECT_NAME: str = "MediFlux Backend"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"

    # CORS origins
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Supabase credentials
    SUPABASE_URL: str = Field(default="", description="Supabase project URL")
    SUPABASE_ANON_KEY: str = Field(default="", description="Supabase public anon key")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(
        default="", description="Supabase service role secret key"
    )

    # LLM Provider credentials
    NVIDIA_API_KEY: str = Field(default="", description="NVIDIA NIM API key")
    OPENROUTER_API_KEY: str = Field(default="", description="OpenRouter API key")
    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434/v1", description="Local Ollama endpoint"
    )

    # Application Modes
    LLM_CACHE_MODE: str = Field(
        default="record", description="Cache mode: off, read, record, or offline"
    )
    DEMO_MODE: bool = Field(default=False, description="Enable deterministic synthetic demo mode")
    CASCADE_MODE: str = Field(
        default="per_event", description="Cascade mode: per_event or batched"
    )
    REG_AUTO_DEPLOY: bool = Field(
        default=False, description="Automatically deploy regulatory code updates"
    )


settings = Settings()

