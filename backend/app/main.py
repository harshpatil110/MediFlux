"""MediFlux FastAPI application entry point with core middleware, lifecycle, and OpenAPI configuration."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import SovereignLLMOfflineError
from app.core.handlers import register_exception_handlers
from app.core.logging import logger, setup_logging
from app.core.middleware import CorrelationIdMiddleware
from app.db.client import get_supabase_client
from app.mcp.server import mcp_server

# OpenAPI Tags Metadata Documentation
OPENAPI_TAGS: list[dict[str, Any]] = [
    {
        "name": "Health",
        "description": "Liveness and readiness probes for infrastructure monitoring.",
    },
    {
        "name": "Authentication & Profiles",
        "description": "Caller identity, assigned roles, and node associations.",
    },
    {
        "name": "Network Nodes",
        "description": "Pharma supply chain topological nodes with RLS-scoping.",
    },
    {
        "name": "Product Catalog",
        "description": "Pharmaceutical master SKU catalog, storage bounds, and CDSCO schedules.",
    },
    {
        "name": "Inventory Management",
        "description": "Real-time stock balance records, safety levels, and batch reservations.",
    },
    {
        "name": "System Status",
        "description": "API versioning and network health telemetry.",
    },
    {
        "name": "HITL",
        "description": "Human-in-the-Loop approval workflows, tasks, and operator decision checkpoints.",
    },
    {
        "name": "Audit Ledger",
        "description": "Cryptographically verified, tamper-evident hash-chained audit trails.",
    },
    {
        "name": "Adapter Forge & Marketplace",
        "description": "Self-evolving API translators, code synthesis, testing, and marketplace rollback.",
    },
    {
        "name": "Live Legacy Ingestion",
        "description": "Restricted-guard translation and real-time ingestion of legacy format payloads.",
    },
    {
        "name": "Regulatory Pipeline",
        "description": "Autonomous regulatory change detection, code mutation, staging testing, and zero-downtime hot-swap.",
    },
    {
        "name": "Prescriptions",
        "description": "Sovereign multimodal prescription scanning, clinical information extraction, and verification.",
    },
    {
        "name": "Compliance",
        "description": "CDSCO Schedule H/H1/X compliance logging, audit trails, and physician registry validation.",
    },
    {
        "name": "Cold Chain Telemetry",
        "description": "IoT environmental sensor monitoring, Arrhenius shelf-life degradation, and autonomous batch quarantine.",
    },
    {
        "name": "Network Copilot",
        "description": "RLS-scoped conversational AI agent with grounded supply chain citations and SSE streaming.",
    },
    {
        "name": "Semantic Search",
        "description": "Cosine-similarity vector search across regulatory notices, demand forecasts, products, and agent activity.",
    },
    {
        "name": "Developer Platform & API Keys",
        "description": "Scoped SHA-256 API key management, in-memory token-bucket rate limiting, and developer scopes.",
    },
    {
        "name": "Webhooks Engine",
        "description": "Outbound HMAC-SHA256 signed event delivery, exponential backoff retries, and failure auto-disable.",
    },
    {
        "name": "Model Context Protocol (MCP)",
        "description": "Model Context Protocol (MCP) server endpoints exposing 7 scoped AI supply chain tools to external agents.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager handling application startup and graceful shutdown."""
    setup_logging()
    logger.info("Initializing %s v%s in [%s] mode", settings.PROJECT_NAME, settings.VERSION, settings.ENVIRONMENT)

    # Database connectivity verification
    db_client = get_supabase_client()
    if db_client:
        logger.info("Supabase client initialized successfully at: %s", settings.SUPABASE_URL)
    else:
        logger.warning("Supabase client running in offline/unconfigured local fallback mode")

    # Start background cascade & HITL expiry workers
    from app.workers.cascade_worker import cascade_worker
    from app.workers.hitl_expiry_worker import hitl_expiry_worker

    await cascade_worker.start()
    await hitl_expiry_worker.start()

    yield

    # Shutdown background workers
    await hitl_expiry_worker.stop()
    await cascade_worker.stop()

    logger.info("Shutting down %s services gracefully", settings.PROJECT_NAME)


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "MediFlux: AI-native hyper-connected pharmaceutical supply chain ecosystem for India.\n\n"
        "Instantaneous single-unit retail demand propagation across 4 tiers: "
        "Pharmacy Edge Node -> Stockist Hub -> Distributor Layer -> Manufacturer Plant."
    ),
    version=settings.VERSION,
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# 1. Custom Correlation ID Middleware
app.add_middleware(CorrelationIdMiddleware)

# 2. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"^(tauri://.*|https?://(localhost|127\.0\.0\.1)(:\d+)?|app://.*|file://.*)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Correlation-ID",
        "Last-Event-ID",
        "Retry-After",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
    ],
)

# 3. Standardized Global Exception Handlers
register_exception_handlers(app)


@app.exception_handler(SovereignLLMOfflineError)
async def sovereign_llm_offline_exception_handler(_: Request, exc: SovereignLLMOfflineError) -> JSONResponse:
    """Handle SovereignLLMOfflineError returning HTTP 503 with JSON detail."""
    return JSONResponse(
        status_code=503,
        content={
            "detail": exc.message,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        },
    )


# 4. Top-level Health Probes
@app.get("/health", tags=["Health"], summary="Liveness & Readiness Health Probe")
async def health_check() -> dict[str, Any]:
    """Return operational status and metadata for system health probes."""
    return {
        "status": "ok",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "desktop_cors_enabled": True,
    }


# 5. Core API Domain Routers
app.include_router(api_router, prefix=settings.API_V1_STR)

# 6. Official MCP Server Transport App (SSE)
app.mount(f"{settings.API_V1_STR}/mcp/transport", mcp_server.sse_app())


def custom_openapi() -> dict[str, Any]:
    """Generate OpenAPI schema enriched with JWT Bearer and API Key security schemes."""
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
    )
    if "components" not in schema:
        schema["components"] = {}

    schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT Bearer token for user / node operator authentication.",
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "Scoped SHA-256 API key for third-party developer integration.",
        },
    }
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi
