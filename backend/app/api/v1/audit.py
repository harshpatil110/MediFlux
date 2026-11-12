"""Re-export audit router from endpoints/audit for flexible imports."""

from app.api.v1.endpoints.audit import router

__all__ = ["router"]
