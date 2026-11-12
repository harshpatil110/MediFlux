"""Centralized deterministic tool registry for MediFlux autonomous agents."""

import asyncio
import functools
import inspect
import logging
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, create_model

logger = logging.getLogger("mediflux.agents.tools")


class ToolDefinition(BaseModel):
    """Encapsulates a registered tool's metadata, invocation target, and JSON schema."""

    name: str
    description: str
    func: Any
    schema_def: dict[str, Any]

    model_config = {"arbitrary_types_allowed": True}


_TOOL_REGISTRY: dict[str, ToolDefinition] = {}


def tool(name: str | None = None, description: str | None = None) -> Callable[..., Any]:
    """Decorator to register functions into the global MediFlux Agent Tool Registry."""

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        tool_name = name or fn.__name__
        tool_desc = description or fn.__doc__ or f"Execute {tool_name}"

        # Generate Pydantic schema from function signature
        sig = inspect.signature(fn)
        fields: dict[str, Any] = {}

        for param_name, param in sig.parameters.items():
            param_type = param.annotation if param.annotation != inspect.Parameter.empty else Any
            param_default = param.default if param.default != inspect.Parameter.empty else ...
            fields[param_name] = (param_type, param_default)

        # Create dynamic model to generate JSON schema
        arg_model = create_model(f"{tool_name}_args", **fields)
        schema_def = arg_model.model_json_schema()

        tool_def = ToolDefinition(
            name=tool_name,
            description=tool_desc.strip(),
            func=fn,
            schema_def=schema_def,
        )

        _TOOL_REGISTRY[tool_name] = tool_def
        logger.debug("Registered agent tool: %s", tool_name)

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def get_tool(name: str) -> ToolDefinition | None:
    """Retrieve a tool definition by name."""
    return _TOOL_REGISTRY.get(name)


def list_tools() -> list[str]:
    """List all registered tool names."""
    return list(_TOOL_REGISTRY.keys())


def get_agent_tools(allowed_tools: list[str]) -> list[dict[str, Any]]:
    """Return JSON schemas for tools permitted for a specific agent."""
    tools_meta = []
    for tool_name in allowed_tools:
        t = _TOOL_REGISTRY.get(tool_name)
        if t:
            tools_meta.append({
                "name": t.name,
                "description": t.description,
                "parameters": t.schema_def,
            })
    return tools_meta


async def execute_tool(name: str, args: dict[str, Any]) -> Any:
    """Execute a registered tool by name with arguments (supporting both sync and async)."""
    t = _TOOL_REGISTRY.get(name)
    if not t:
        raise ValueError(f"Tool '{name}' is not registered in Tool Registry")

    logger.info("Executing tool [%s] with args: %s", name, args)

    if asyncio.iscoroutinefunction(t.func):
        return await t.func(**args)
    return t.func(**args)


def clear_registry() -> None:
    """Clear registered tools (testing helper)."""
    _TOOL_REGISTRY.clear()
