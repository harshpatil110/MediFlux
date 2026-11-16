"""Device token management endpoints for Mobile Push Notifications (Task M7).

Supports token registration (POST), unregistration (DELETE), and listing (GET)
with Row-Level Security (RLS) enforcement and cryptographic audit logging.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.security import CurrentUser, get_current_user, get_service_db_client
from app.graphs.coldchain import write_audit_entry

logger = logging.getLogger("mediflux.api.devices")

router = APIRouter(prefix="/devices", tags=["Device Notifications"])

# In-memory device token store for offline/test environments: token -> record
_in_memory_device_tokens: dict[str, dict[str, Any]] = {}


def get_in_memory_device_tokens() -> list[dict[str, Any]]:
    """Return all registered device token records from in-memory store."""
    return list(_in_memory_device_tokens.values())


def clear_in_memory_device_tokens() -> None:
    """Clear in-memory device token store."""
    _in_memory_device_tokens.clear()


class DeviceTokenRegisterRequest(BaseModel):
    """Payload schema for registering or updating a client device push token."""

    token: str = Field(..., description="Device push notification token (e.g. ExponentPushToken[...])")
    platform: Literal["android", "ios", "web", "expo"] = Field(
        default="android", description="Client device platform"
    )
    preferences: dict[str, Any] | None = Field(
        default_factory=lambda: {"hitl": True, "coldchain": True},
        description="Notification preference overrides",
    )


class DeviceTokenResponse(BaseModel):
    """Schema for a registered device push token record."""

    id: str
    token: str
    platform: str
    user_id: str
    role: str | None = None
    node_id: str | None = None
    preferences: dict[str, Any]
    created_at: str
    updated_at: str


class DeviceListResponse(BaseModel):
    """Response schema for listing registered devices."""

    devices: list[dict[str, Any]]
    total: int


@router.post(
    "",
    summary="Register Device Push Token",
    description="Register or update an Expo push token for the authenticated user.",
    status_code=status.HTTP_201_CREATED,
    response_model=dict[str, Any],
)
async def register_device_token(
    payload: DeviceTokenRegisterRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JSONResponse:
    """Upsert device token for current user with RLS binding and audit logging."""
    raw_token = payload.token.strip()
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Token cannot be empty.",
        )

    now_iso = datetime.now(UTC).isoformat()
    existing = _in_memory_device_tokens.get(raw_token)
    token_id = existing.get("id") if existing else str(uuid.uuid4())
    created_at = existing.get("created_at") if existing else now_iso

    token_record: dict[str, Any] = {
        "id": token_id,
        "user_id": str(current_user.user_id),
        "role": current_user.role,
        "node_id": str(current_user.node_id) if current_user.node_id else None,
        "token": raw_token,
        "platform": payload.platform,
        "preferences": payload.preferences or {"hitl": True, "coldchain": True},
        "created_at": created_at,
        "updated_at": now_iso,
    }

    # Store in memory
    _in_memory_device_tokens[raw_token] = token_record

    # Persist in Supabase if configured
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                client.table("device_tokens").upsert(token_record, on_conflict="token").execute()
        except Exception as exc:
            logger.warning("Supabase device_tokens upsert failed (%s); using in-memory store", exc)

    # Cryptographic audit log (token masked for security)
    masked_token = f"{raw_token[:12]}...{raw_token[-4:]}" if len(raw_token) > 16 else "***"
    try:
        await write_audit_entry(
            actor=f"user:{current_user.user_id}",
            action="device.token.registered",
            entity_type="device_token",
            entity_id=token_id,
            payload={
                "token_masked": masked_token,
                "platform": payload.platform,
                "role": current_user.role,
                "node_id": str(current_user.node_id) if current_user.node_id else None,
            },
            explanation=f"Registered {payload.platform} push device token for user {current_user.user_id}",
        )
    except Exception as exc:
        logger.debug("Device registration audit log failed: %s", exc)

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "status": "registered",
            **token_record,
        },
    )


@router.delete(
    "/{token:path}",
    summary="Delete Device Push Token",
    description="Remove a registered push token. Enforces that users can only delete their own tokens.",
    status_code=status.HTTP_200_OK,
)
async def delete_device_token(
    token: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JSONResponse:
    """Delete a registered device push token with ownership check and audit logging."""
    target_token = (token or "").strip()
    if not target_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token is required.",
        )

    # Check in-memory store
    record = _in_memory_device_tokens.get(target_token)

    # If not in memory, check Supabase
    if not record and settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                res = client.table("device_tokens").select("*").eq("token", target_token).execute()
                if res.data:
                    record = res.data[0]
        except Exception as exc:
            logger.debug("Supabase lookup for device token failed: %s", exc)

    if record:
        # Ownership enforcement: caller must own the token unless caller is admin
        rec_user_id = str(record.get("user_id"))
        caller_user_id = str(current_user.user_id)
        if rec_user_id != caller_user_id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete another user's device token.",
            )

        # Remove from memory
        _in_memory_device_tokens.pop(target_token, None)

        # Remove from Supabase
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            try:
                client = get_service_db_client()
                if client:
                    client.table("device_tokens").delete().eq("token", target_token).execute()
            except Exception as exc:
                logger.warning("Supabase device_tokens delete failed: %s", exc)

        # Cryptographic audit log
        masked_token = f"{target_token[:12]}...{target_token[-4:]}" if len(target_token) > 16 else "***"
        try:
            await write_audit_entry(
                actor=f"user:{current_user.user_id}",
                action="device.token.removed",
                entity_type="device_token",
                entity_id=record.get("id", str(uuid.uuid4())),
                payload={"token_masked": masked_token},
                explanation=f"Removed device push token for user {current_user.user_id}",
            )
        except Exception as exc:
            logger.debug("Device removal audit log failed: %s", exc)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"removed": True, "token": target_token},
    )


@router.get(
    "",
    summary="List Registered Device Tokens",
    description="Returns registered device tokens for the authenticated user, or all devices if admin.",
    status_code=status.HTTP_200_OK,
)
async def list_device_tokens(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    all_devices: bool = Query(False, alias="all"),
) -> JSONResponse:
    """Retrieve device tokens scoped to caller's identity (or all for admin)."""
    devices: list[dict[str, Any]] = []

    # Supabase lookup if configured
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                query = client.table("device_tokens").select("*")
                if not (current_user.role == "admin" and all_devices):
                    query = query.eq("user_id", str(current_user.user_id))
                res = query.execute()
                if res.data:
                    devices.extend(res.data)
        except Exception as exc:
            logger.debug("Supabase list device_tokens failed: %s", exc)

    # Merge in-memory devices
    existing_tokens = {d.get("token") for d in devices}
    for t_val, rec in _in_memory_device_tokens.items():
        if t_val not in existing_tokens:
            if current_user.role == "admin" and all_devices:
                devices.append(rec)
            elif str(rec.get("user_id")) == str(current_user.user_id):
                devices.append(rec)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "devices": devices,
            "total": len(devices),
        },
    )
