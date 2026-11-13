"""Server-Sent Events (SSE) streaming endpoint with node isolation and replay support."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sse_starlette.sse import EventSourceResponse

from app.core.security import CurrentUser, get_actor, get_current_user, visible_node_ids
from app.events.sse import sse_event_stream

logger = logging.getLogger("mediflux.api.stream")

router = APIRouter(tags=["Events & Streaming"])


@router.get(
    "/events/stream",
    summary="Real-Time Server-Sent Events (SSE) Stream Alias",
    include_in_schema=False,
)
@router.get(
    "/stream",
    summary="Real-Time Server-Sent Events (SSE) Stream",
    description="Subscribe to live domain event topics with automatic node-visibility filtering and Last-Event-ID replay.",
)
async def subscribe_event_stream(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    topics: str = Query("pos.sales", description="Comma-separated topics (e.g. pos.sales,agent.activity,*)"),
    last_event_id: str | None = Header(None, alias="Last-Event-ID"),
    last_event_id_query: str | None = Query(None, alias="last_event_id"),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> EventSourceResponse:
    """Stream live events over Server-Sent Events (SSE) with node scoping and reconnection replay."""
    if x_api_key:
        actor = await get_actor(x_api_key=x_api_key)
        scopes = actor.scopes
        if "*" not in scopes and "all" not in scopes and "read:stream" not in scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient API key scope. Required: 'read:stream'",
            )
    topic_list = [t.strip() for t in topics.split(",") if t.strip()]
    if not topic_list:
        topic_list = ["pos.sales"]

    effective_last_id = last_event_id or last_event_id_query

    # Enforce node-level isolation based on caller's role
    if current_user.role == "admin":
        visible_nodes: set[str] | None = None
    else:
        visible_nodes = set(visible_node_ids(current_user))

    logger.info(
        "SSE subscription initiated: user=%s role=%s topics=%s last_id=%s visible_nodes=%s",
        current_user.user_id,
        current_user.role,
        topic_list,
        effective_last_id,
        visible_nodes,
    )

    return EventSourceResponse(
        sse_event_stream(
            topics=topic_list,
            last_event_id=effective_last_id,
            visible_nodes=visible_nodes,
        ),
        ping=15,
    )

