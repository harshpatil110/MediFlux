"""Comprehensive integration test suite for FastAPI core skeleton (Task 4)."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.exceptions import ForbiddenError
from app.main import app


@pytest.mark.asyncio
async def test_health_check_endpoint() -> None:
    """Validate /health endpoint returns HTTP 200 with standard status and version info."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["app"] == settings.PROJECT_NAME
        assert data["version"] == settings.VERSION
        assert data["environment"] == settings.ENVIRONMENT


@pytest.mark.asyncio
async def test_correlation_id_middleware_propagation() -> None:
    """Verify X-Correlation-ID is propagated when supplied and generated when omitted."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # Case 1: Client provides correlation ID
        custom_corr_id = "test-corr-uuid-9999"
        res_provided = await client.get("/health", headers={"X-Correlation-ID": custom_corr_id})
        assert res_provided.status_code == 200
        assert res_provided.headers.get("X-Correlation-ID") == custom_corr_id

        # Case 2: Client omits correlation ID (should auto-generate)
        res_generated = await client.get("/health")
        assert res_generated.status_code == 200
        generated_id = res_generated.headers.get("X-Correlation-ID")
        assert generated_id is not None
        assert len(generated_id) > 10


@pytest.mark.asyncio
async def test_unauthorized_request_error_format() -> None:
    """Verify accessing /api/v1/me without authorization header returns standardized 401 JSON."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/api/v1/me")
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "UNAUTHORIZED"
        assert "message" in data["error"]
        assert isinstance(data["error"]["details"], dict)


@pytest.mark.asyncio
async def test_validation_error_format() -> None:
    """Verify input validation errors return standardized 422 JSON schema."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # Pass invalid limit (< 1)
        response = await client.get("/api/v1/products?limit=0")
        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "details" in data["error"]
        assert "errors" in data["error"]["details"]


@pytest.mark.asyncio
async def test_not_found_error_format() -> None:
    """Verify 404 endpoint returns standardized error envelope."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/api/v1/non-existent-endpoint")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_custom_app_exception_and_unhandled_500() -> None:
    """Verify custom AppException and unhandled 500 error return standardized payload formats."""
    # Define temporary test routes on app
    @app.get("/api/v1/test-custom-error")
    async def route_custom_error() -> None:
        raise ForbiddenError("You lack access to this resource", details={"scope": "admin:write"})

    @app.get("/api/v1/test-server-error")
    async def route_server_error() -> None:
        raise RuntimeError("Simulated crash in business logic")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # 1. Custom AppException
        res_custom = await client.get("/api/v1/test-custom-error")
        assert res_custom.status_code == 403
        data_custom = res_custom.json()
        assert data_custom["error"]["code"] == "FORBIDDEN"
        assert data_custom["error"]["message"] == "You lack access to this resource"
        assert data_custom["error"]["details"]["scope"] == "admin:write"

        # 2. Unhandled 500 Internal Error (masks stack trace)
        res_500 = await client.get("/api/v1/test-server-error")
        assert res_500.status_code == 500
        data_500 = res_500.json()
        assert data_500["error"]["code"] == "INTERNAL_SERVER_ERROR"
        assert "internal server error" in data_500["error"]["message"].lower()
        # Stack trace should NOT be leaked in details
        assert "Simulated crash" not in str(data_500)


@pytest.mark.asyncio
async def test_get_current_user_profile() -> None:
    """Verify authenticated request to /api/v1/me returns caller profile, role, and node_id."""
    headers = {"Authorization": "Bearer mock-pharmacist-token"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/api/v1/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["role"] in ("pharmacy", "pharmacist")
        assert data["node_id"] == "11111111-1111-1111-1111-111111111111"
        assert "email" in data


@pytest.mark.asyncio
async def test_rls_inventory_scoping_pharmacist() -> None:
    """Verify pharmacist only sees inventory for their own pharmacy node."""
    headers = {"Authorization": "Bearer mock-pharmacist-token"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/api/v1/inventory", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        items = data["items"]
        assert len(items) > 0
        # Assert every item belongs to the pharmacy node
        pharm_node_id = "11111111-1111-1111-1111-111111111111"
        for item in items:
            assert item["node_id"] == pharm_node_id


@pytest.mark.asyncio
async def test_rls_inventory_scoping_stockist() -> None:
    """Verify stockist can see inventory for both stockist hub and downstream pharmacy."""
    headers = {"Authorization": "Bearer mock-stockist-token"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/api/v1/inventory", headers=headers)
        assert response.status_code == 200
        data = response.json()
        items = data["items"]
        node_ids = {item["node_id"] for item in items}
        assert "22222222-2222-2222-2222-222222222222" in node_ids


@pytest.mark.asyncio
async def test_nodes_list_rls_scoping_and_pagination() -> None:
    """Verify /api/v1/nodes returns visible nodes according to user role and supports pagination."""
    headers = {"Authorization": "Bearer mock-pharmacist-token"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # Pharmacist view
        res = await client.get("/api/v1/nodes", headers=headers)
        assert res.status_code == 200
        nodes = res.json()["items"]
        assert len(nodes) == 1
        assert nodes[0]["tier"] == "pharmacy"

    dist_headers = {"Authorization": "Bearer mock-distributor-token"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # Distributor view (sees multiple tiers)
        res_dist = await client.get("/api/v1/nodes?limit=2", headers=dist_headers)
        assert res_dist.status_code == 200
        dist_data = res_dist.json()
        assert len(dist_data["items"]) <= 2


@pytest.mark.asyncio
async def test_products_catalog_search_and_filters() -> None:
    """Verify /api/v1/products supports filtering by search term and cold chain requirement."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # Search query
        res_search = await client.get("/api/v1/products?search=insulin")
        assert res_search.status_code == 200
        search_items = res_search.json()["items"]
        assert len(search_items) == 1
        assert "Insulin" in search_items[0]["generic_name"]

        # Cold chain filter
        res_cold = await client.get("/api/v1/products?is_cold_chain=true")
        assert res_cold.status_code == 200
        cold_items = res_cold.json()["items"]
        assert all(p["is_cold_chain"] is True for p in cold_items)


@pytest.mark.asyncio
async def test_openapi_documentation_structure() -> None:
    """Verify OpenAPI schema is generated properly with tags and endpoint definitions."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        res = await client.get("/openapi.json")
        assert res.status_code == 200
        schema = res.json()
        assert schema["info"]["title"] == settings.PROJECT_NAME
        assert schema["info"]["version"] == settings.VERSION
        paths = schema["paths"]
        assert "/health" in paths
        assert "/api/v1/me" in paths
        assert "/api/v1/nodes" in paths
        assert "/api/v1/products" in paths
        assert "/api/v1/inventory" in paths
        tags = [t["name"] for t in schema.get("tags", [])]
        assert "Network Nodes" in tags
        assert "Product Catalog" in tags
        assert "Inventory Management" in tags
