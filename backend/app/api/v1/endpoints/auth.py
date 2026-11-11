"""Authentication and current user profile endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.schemas.base import UserProfile

router = APIRouter(tags=["Authentication & Profiles"])


@router.get("/me", response_model=UserProfile, summary="Get Current Authenticated Profile")
async def get_my_profile(
    current_user: Annotated[UserProfile, Depends(get_current_user)],
) -> UserProfile:
    """Retrieve the profile, role, and assigned node ID for the active authenticated user."""
    return current_user
