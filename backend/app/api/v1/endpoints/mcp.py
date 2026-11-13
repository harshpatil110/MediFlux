"""Model Context Protocol (MCP) HTTP and JSON-RPC API Endpoints.

Provides REST, JSON-RPC 2.0, and SSE endpoints for external AI agents
and web-based MCP clients to inspect tools, query state, and execute operations.
"""

import json
import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.mcp.server import (
    MCPAuthError,
    MCPExecutionError,
    MCPPermissionError,
    MCPRateLimitError,
    MCPScopeError,
    execute_mcp_tool,
    get_mcp_tools_metadata,
)

logger = logging.getLogger("mediflux.api.mcp")

router = APIRouter(prefix="/mcp", tags=["Model Context Protocol (MCP)"])


# ---------------------------------------------------------------------------
# Request & Response Schemas
# ---------------------------------------------------------------------------

class MCPToolCallRequest(BaseModel):
    name: str | None = Field(default=None, description="Tool name to execute")
    tool: str | None = Field(default=None, description="Alias for tool name")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Arguments to pass to the tool")
    parameters: dict[str, Any] | None = Field(default=None, description="Alias for arguments")


class MCPContentItem(BaseModel):
    type: str = "text"
    text: str


class MCPToolCallResponse(BaseModel):
    content: list[MCPContentItem]
    structured_content: dict[str, Any] | None = None
    is_error: bool = False


class MCPToolsListResponse(BaseModel):
    tools: list[dict[str, Any]]
    count: int
    protocol_version: str = "2024-11-05"


class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: str | int | None = None
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/tools",
    response_model=MCPToolsListResponse,
    summary="List Registered MCP Tools",
    description="List all available MCP tools with their JSON schemas and required API key scopes.",
)
async def list_tools() -> MCPToolsListResponse:
    """Retrieve all available MCP tools."""
    tools = get_mcp_tools_metadata()
    return MCPToolsListResponse(
        tools=tools,
        count=len(tools),
        protocol_version="2024-11-05",
    )


@router.post(
    "/call",
    response_model=MCPToolCallResponse,
    summary="Execute MCP Tool Call",
    description="Execute an MCP tool protected by API key authentication, rate limiting, and scope checks.",
)
async def call_tool(
    body: MCPToolCallRequest,
    request: Request,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    authorization: str | None = Header(None),
) -> MCPToolCallResponse:
    """Execute an MCP tool directly over HTTP."""
    tool_name = body.name or body.tool
    if not tool_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tool name must be specified via 'name' or 'tool'.",
        )

    arguments = body.arguments or body.parameters or {}
    context_key = x_api_key or authorization

    try:
        result = await execute_mcp_tool(
            tool_name=tool_name,
            arguments=arguments,
            context_api_key=context_key,
        )
        return MCPToolCallResponse(
            content=[MCPContentItem(type="text", text=json.dumps(result, indent=2))],
            structured_content=result,
            is_error=False,
        )
    except MCPAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "ApiKey"},
        ) from exc
    except MCPRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": str(getattr(exc, "retry_after", 60))},
        ) from exc
    except (MCPScopeError, MCPPermissionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except MCPExecutionError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error executing MCP tool '%s': %s", tool_name, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error executing tool '{tool_name}': {exc}",
        ) from exc


@router.post(
    "/rpc",
    summary="JSON-RPC 2.0 MCP Protocol Handler",
    description="Handle standard MCP JSON-RPC 2.0 requests such as tools/list and tools/call.",
)
async def handle_json_rpc(
    body: JSONRPCRequest,
    request: Request,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """JSON-RPC 2.0 handler for MCP tools/list and tools/call."""
    rpc_id = body.id
    method = body.method
    params = body.params or {}
    context_key = x_api_key or authorization

    if method == "tools/list":
        tools = get_mcp_tools_metadata()
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {
                "tools": [
                    {
                        "name": t["name"],
                        "description": t["description"],
                        "inputSchema": t.get("input_schema", {}),
                    }
                    for t in tools
                ]
            },
        }

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        if not tool_name:
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {
                    "code": -32602,
                    "message": "Invalid params: missing tool name",
                },
            }

        try:
            result = await execute_mcp_tool(
                tool_name=tool_name,
                arguments=arguments,
                context_api_key=context_key,
            )
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2),
                        }
                    ],
                    "structured_content": result,
                    "isError": False,
                },
            }
        except MCPAuthError as exc:
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {
                    "code": -32001,
                    "message": str(exc),
                    "data": {"status": 401, "code": "unauthorized"},
                },
            }
        except MCPRateLimitError as exc:
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {
                    "code": -32029,
                    "message": str(exc),
                    "data": {"status": 429, "retry_after": getattr(exc, "retry_after", 60)},
                },
            }
        except (MCPScopeError, MCPPermissionError) as exc:
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {
                    "code": -32003,
                    "message": str(exc),
                    "data": {"status": 403, "code": "forbidden"},
                },
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {
                    "code": -32603,
                    "message": str(exc),
                    "data": {"status": 500},
                },
            }

    return {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "error": {
            "code": -32601,
            "message": f"Method '{method}' not found. Supported methods: 'tools/list', 'tools/call'.",
        },
    }


@router.get(
    "/sse",
    summary="MCP Server-Sent Events Transport",
    description="Establish an SSE stream for MCP protocol session initialization.",
)
async def mcp_sse_transport(request: Request) -> EventSourceResponse:
    """Provide MCP SSE transport connection endpoint."""
    async def event_generator():
        # Yield initial endpoint notification per MCP SSE transport specification
        yield {
            "event": "endpoint",
            "data": "/api/v1/mcp/call",
        }
        # Yield server status metadata
        yield {
            "event": "message",
            "data": json.dumps({
                "status": "ready",
                "server": "mediflux-mcp",
                "version": "1.0.0",
                "tools_endpoint": "/api/v1/mcp/tools",
                "call_endpoint": "/api/v1/mcp/call",
                "rpc_endpoint": "/api/v1/mcp/rpc",
            }),
        }

    return EventSourceResponse(event_generator())
