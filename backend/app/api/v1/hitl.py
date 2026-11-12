"""Re-export HITL router from endpoints/hitl for flexible module imports."""

from app.api.v1.endpoints.hitl import router

__all__ = ["router"]
