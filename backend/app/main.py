"""MediFlux FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context for startup and shutdown events."""
    setup_logging()
    yield


app = FastAPI(
    title="MediFlux Backend",
    description="AI-native hyper-connected pharmaceutical supply chain ecosystem for India",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, Any]:
    """Health check endpoint validating service status."""
    return {
        "status": "ok",
        "app": "MediFlux Backend",
        "version": "0.1.0",
    }


# Include API v1 routes
app.include_router(api_router, prefix="/api/v1")
