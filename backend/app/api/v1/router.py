"""API v1 master router."""

from fastapi import APIRouter

api_router = APIRouter()


@api_router.get("/status", tags=["Status"])
async def get_api_v1_status() -> dict[str, str]:
    """Retrieve API v1 operational status."""
    return {
        "status": "active",
        "version": "v1",
        "ecosystem": "MediFlux Pharma Network",
    }
