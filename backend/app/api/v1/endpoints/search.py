"""FastAPI semantic vector search endpoint with RLS scope enforcement (Task 21)."""

import logging
from typing import Annotated

from fastapi import APIRouter, Header, Query, Request, status
from fastapi.responses import JSONResponse

from app.graphs.copilot import CopilotScope
from app.llm.embeddings import search_vector_index

logger = logging.getLogger("mediflux.api.search")

router = APIRouter(tags=["Semantic Search"])


def _extract_scope(
    request: Request,
    x_user_role: str | None = None,
    x_node_id: str | None = None,
    x_user_region: str | None = None,
    x_user_id: str | None = None,
) -> CopilotScope:
    """Extract authenticated caller operational scope from request headers."""
    role = (x_user_role or getattr(request.state, "user_role", None) or "admin").lower()
    node_id = x_node_id or getattr(request.state, "node_id", None)
    region = x_user_region or getattr(request.state, "user_region", None)
    user_id = x_user_id or getattr(request.state, "user_id", "usr-system")

    return CopilotScope(
        user_id=user_id,
        role=role,
        node_id=node_id,
        tier=role,
        region=region,
    )


@router.get(
    "/search",
    summary="Semantic Vector Search Across Network Knowledge",
    description="Cosine similarity vector search over products, regulatory notices, demand signals, and agent runs.",
    status_code=status.HTTP_200_OK,
)
async def search_endpoint(
    request: Request,
    q: Annotated[str, Query(description="Search query string")],
    types: Annotated[str | None, Query(description="Comma-separated entity types filter")] = None,
    limit: Annotated[int, Query(description="Maximum results", ge=1, le=50)] = 10,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
    x_node_id: Annotated[str | None, Header(alias="X-Node-Id")] = None,
    x_user_region: Annotated[str | None, Header(alias="X-User-Region")] = None,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> JSONResponse:
    """Execute cosine-similarity vector search filtered by caller RLS scope."""
    scope = _extract_scope(
        request=request,
        x_user_role=x_user_role,
        x_node_id=x_node_id,
        x_user_region=x_user_region,
        x_user_id=x_user_id,
    )

    type_list = [t.strip() for t in types.split(",") if t.strip()] if types else None

    results = search_vector_index(
        query=q,
        types=type_list,
        limit=limit,
        scope=scope.model_dump(),
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "query": q,
            "count": len(results),
            "results": results,
        },
    )
