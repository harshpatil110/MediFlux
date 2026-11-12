"""API v1 master router aggregating all domain sub-routers."""

from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.events import router as events_router
from app.api.v1.endpoints.inventory import router as inventory_router
from app.api.v1.endpoints.modules import router as modules_router
from app.api.v1.endpoints.nodes import router as nodes_router
from app.api.v1.endpoints.products import router as products_router
from app.api.v1.endpoints.stream import router as stream_router

api_router = APIRouter()

# Core Domain Endpoints
api_router.include_router(auth_router)
api_router.include_router(nodes_router)
api_router.include_router(products_router)
api_router.include_router(inventory_router)
api_router.include_router(events_router)
api_router.include_router(stream_router)
api_router.include_router(modules_router)


@api_router.get("/status", tags=["System Status"])
async def get_api_v1_status() -> dict[str, str]:
    """Retrieve API v1 operational status."""
    return {
        "status": "active",
        "version": "v1",
        "ecosystem": "MediFlux Pharma Network",
    }
