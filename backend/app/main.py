"""MediFlux FastAPI application entry point with core middleware, lifecycle, and OpenAPI configuration."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.handlers import register_exception_handlers
from app.core.logging import logger, setup_logging
from app.core.middleware import CorrelationIdMiddleware
from app.db.client import get_supabase_client

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

    yield

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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID"],
)

# 3. Standardized Global Exception Handlers
register_exception_handlers(app)


# 4. Top-level Health Probes
@app.get("/health", tags=["Health"], summary="Liveness & Readiness Health Probe")
async def health_check() -> dict[str, Any]:
    """Return operational status and metadata for system health probes."""
    return {
        "status": "ok",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }


# 5. Core API Domain Routers
app.include_router(api_router, prefix=settings.API_V1_STR)
