"""FastAPI endpoints for Network Copilot conversational query and SSE streaming (Task 21)."""

import logging
import uuid
from typing import Annotated, Any

import jwt
from fastapi import APIRouter, Header, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.core.security import DEMO_USERS
from app.graphs.copilot import (
    CopilotScope,
    run_copilot,
    stream_copilot_events,
)

logger = logging.getLogger("mediflux.api.copilot")

router = APIRouter(prefix="/copilot", tags=["Network Copilot"])


class CopilotQueryRequest(BaseModel):
    """Payload for conversational copilot query."""

    question: str = Field(description="Operational question to ask the Copilot")
    stream: bool = Field(default=False, description="Enable Server-Sent Events progressive streaming")
    region: str | None = Field(default=None, description="Optional region filter")
    node_id: str | None = Field(default=None, description="Optional target node ID")


def _resolve_caller_scope(
    request: Request,
    body_node_id: str | None = None,
    body_region: str | None = None,
    x_user_role: str | None = None,
    x_node_id: str | None = None,
    x_user_region: str | None = None,
    x_user_id: str | None = None,
) -> CopilotScope:
    """Resolve caller identity and enforce strict node-isolation rules."""
    role = x_user_role or getattr(request.state, "user_role", None)
    header_node_id = x_node_id or getattr(request.state, "node_id", None)
    region = x_user_region or getattr(request.state, "user_region", None)
    user_id = x_user_id or getattr(request.state, "user_id", "usr-anonymous")

    # Inspect Bearer token if headers not explicitly passed
    auth_header = request.headers.get("Authorization")
    if auth_header and not role:
        try:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token = parts[1]
                if token in DEMO_USERS:
                    u_data = DEMO_USERS[token]
                    role = u_data.get("role")
                    header_node_id = u_data.get("node_id")
                    user_id = u_data.get("user_id", user_id)
                elif settings.SUPABASE_JWT_SECRET:
                    payload = jwt.decode(
                        token,
                        settings.SUPABASE_JWT_SECRET,
                        algorithms=["HS256"],
                        options={"verify_aud": False},
                    )
                    user_id = payload.get("sub", user_id)
                    role = payload.get("role", "authenticated")
                    user_meta = payload.get("user_metadata", {})
                    header_node_id = user_meta.get("node_id", header_node_id)
                    region = user_meta.get("region", region)
        except Exception:
            pass

    final_role = (role or "admin").lower()

    # RLS rule: Pharmacy caller cannot override their authenticated node_id with body_node_id
    if final_role == "pharmacy":
        effective_node_id = header_node_id or "11111111-1111-1111-1111-111111111111"
    else:
        effective_node_id = body_node_id or header_node_id

    effective_region = body_region or region

    return CopilotScope(
        user_id=user_id,
        role=final_role,
        node_id=effective_node_id,
        tier=final_role,
        region=effective_region,
    )


@router.post(
    "/query",
    summary="Query Network Copilot",
    description="Ask natural-language operational questions; receives grounded answers with references or SSE stream.",
    status_code=status.HTTP_200_OK,
)
async def query_copilot(
    payload: CopilotQueryRequest,
    request: Request,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
    x_node_id: Annotated[str | None, Header(alias="X-Node-Id")] = None,
    x_user_region: Annotated[str | None, Header(alias="X-User-Region")] = None,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_correlation_id: Annotated[str | None, Header(alias="X-Correlation-ID")] = None,
) -> Any:
    """Execute Copilot query with RLS scoping, returning JSON or SSE stream."""
    correlation_id = x_correlation_id or getattr(request.state, "correlation_id", str(uuid.uuid4()))

    scope = _resolve_caller_scope(
        request=request,
        body_node_id=payload.node_id,
        body_region=payload.region,
        x_user_role=x_user_role,
        x_node_id=x_node_id,
        x_user_region=x_user_region,
        x_user_id=x_user_id,
    )

    # 1. SSE Streaming Response
    accept_header = request.headers.get("Accept", "")
    if payload.stream or "text/event-stream" in accept_header:
        async def event_generator():
            async for ev in stream_copilot_events(
                question=payload.question,
                scope=scope,
                correlation_id=correlation_id,
            ):
                yield {
                    "event": ev.get("event", "message"),
                    "data": ev.get("data", ""),
                }

        return EventSourceResponse(event_generator())

    # 2. Standard JSON Response
    result = await run_copilot(
        question=payload.question,
        scope=scope,
        correlation_id=correlation_id,
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=result,
    )
