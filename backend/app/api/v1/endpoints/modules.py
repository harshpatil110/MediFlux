"""FastAPI endpoints for dynamic module registry inspection and version rollback."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.security import CurrentUser, get_current_user
from app.modules_runtime.contract import ModuleVersion
from app.modules_runtime.registry import module_registry

logger = logging.getLogger("mediflux.api.modules")

router = APIRouter(prefix="/modules", tags=["Dynamic Business Modules"])


@router.get(
    "",
    summary="List Active Modules",
    description="Retrieve all currently active dynamic business rules and adapter modules.",
    response_model=list[ModuleVersion],
)
async def list_active_modules(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[ModuleVersion]:
    """List all currently active business rule modules."""
    return module_registry.list_active_modules()


@router.get(
    "/{name}/versions",
    summary="List Module Version History",
    description="Retrieve full version history for a specified module including staging and retired versions.",
    response_model=list[ModuleVersion],
)
async def list_module_versions(
    name: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[ModuleVersion]:
    """List all versions for a given module name."""
    versions = module_registry.list_versions(name)
    if not versions:
        raise NotFoundError(f"No versions found for module '{name}'")
    return versions


@router.post(
    "/{name}/rollback",
    summary="Rollback Module Version",
    description="Admin-only endpoint to atomically retire the current active module and reactivate the prior version.",
    response_model=ModuleVersion,
)
async def rollback_module(
    name: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ModuleVersion:
    """Roll back module to previous stable version (admin only)."""
    if current_user.role != "admin":
        raise ForbiddenError("Administrator privileges required to execute module rollback")

    try:
        rolled_back = module_registry.rollback(name)
        return rolled_back
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rollback failed: {exc}",
        ) from exc
