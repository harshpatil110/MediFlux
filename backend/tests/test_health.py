"""Health check endpoint integration tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    """Validate /health endpoint returns 200 OK and expected structure."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["app"] == settings.PROJECT_NAME
        assert data["version"] == settings.VERSION


@pytest.mark.asyncio
async def test_api_v1_status() -> None:
    """Validate /api/v1/status endpoint returns active network status."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/v1/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["version"] == "v1"
