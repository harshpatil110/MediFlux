"""Model Context Protocol (MCP) package for MediFlux."""

from app.mcp.server import (
    MCP_TOOLS_METADATA,
    FastMCP,
    MCPAuthError,
    MCPError,
    MCPExecutionError,
    MCPPermissionError,
    MCPRateLimitError,
    MCPScopeError,
    execute_mcp_tool,
    get_mcp_tools_metadata,
    mcp_server,
    run_stdio,
)

__all__ = [
    "FastMCP",
    "MCP_TOOLS_METADATA",
    "MCPAuthError",
    "MCPError",
    "MCPExecutionError",
    "MCPPermissionError",
    "MCPRateLimitError",
    "MCPScopeError",
    "execute_mcp_tool",
    "get_mcp_tools_metadata",
    "mcp_server",
    "run_stdio",
]
