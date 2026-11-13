"""Application configuration management using Pydantic Settings."""

from typing import Literal

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
    PROJECT_NAME: str = "Pharma Supply Chain API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # CORS origins (Vite dev servers, Tauri & Electron desktop origins)
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "tauri://localhost",
        "http://tauri.localhost",
        "https://tauri.localhost",
        "app://.",
        "app://localhost",
        "file://",
        "null",
    ]

    # Supabase credentials & JWT secret
    SUPABASE_URL: str = Field(default="", description="Supabase project URL")
    SUPABASE_ANON_KEY: str = Field(default="", description="Supabase public anon key")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(
        default="", description="Supabase service role secret key"
    )
    SUPABASE_JWT_SECRET: str = Field(
        default="mediflux-super-secret-jwt-key-2026",
        description="Supabase JWT secret for token verification",
    )

    # LLM Provider credentials
    NVIDIA_API_KEY: str | None = Field(default=None, description="NVIDIA NIM API key")
    OPENROUTER_API_KEY: str | None = Field(default=None, description="OpenRouter API key")
    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434/v1", description="Local Ollama endpoint"
    )

    # Embeddings & Vector Search (Task 21)
    EMBEDDING_PROVIDER: str = Field(
        default="ollama", description="Embedding provider: ollama, gemini, openai, local_semantic"
    )
    EMBEDDING_MODEL: str = Field(
        default="nomic-embed-text", description="Embedding model name"
    )
    EMBEDDING_DIM: int = Field(
        default=768, description="Vector dimension size for pgvector"
    )

    # Application Modes
    LLM_CACHE_MODE: str = Field(
        default="record", description="Cache mode: off, record, replay"
    )
    LLM_CACHE_DB_PATH: str = Field(
        default="llm_cache.db", description="Path to SQLite cache database"
    )
    AGENT_MODELS_CONFIG_PATH: str = Field(
        default="config/agent_models.yaml", description="Path to agent models yaml"
    )
    DEMO_MODE: bool = Field(default=False, description="Enable deterministic synthetic demo mode")
    CASCADE_MODE: Literal["per_event", "micro_batch"] = Field(
        default="per_event", description="Cascade mode: per_event or micro_batch"
    )
    CASCADE_MICRO_BATCH_WINDOW_SECONDS: int = Field(
        default=5, description="Time window in seconds to aggregate events in micro_batch mode"
    )
    CASCADE_MAX_CONCURRENCY: int = Field(
        default=2, description="Maximum concurrent cascade executions permitted"
    )
    REG_AUTO_DEPLOY: bool = Field(
        default=False, description="Automatically deploy regulatory code updates"
    )

    # MCP Server (Task 23)
    MCP_ALLOW_DECIDE_APPROVAL: bool = Field(
        default=True, description="Allow decide_approval tool calls via MCP if API key has required scope"
    )


settings = Settings()
