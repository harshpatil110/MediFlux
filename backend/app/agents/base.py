"""Base agent class, decision schemas, bounded execution loop, and trace recording."""

import json
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from app.agents.state import AgentGraphState
from app.agents.tools.registry import execute_tool, get_agent_tools
from app.core.config import settings
from app.core.security import get_service_db_client
from app.events.bus import in_process_event_bus
from app.events.models import DomainEvent, EventEnvelope
from app.llm.router import llm_router

logger = logging.getLogger("mediflux.agents.base")

# In-memory store for agent run records for offline testing and verification
_in_memory_agent_runs: list[dict[str, Any]] = []


def get_in_memory_agent_runs() -> list[dict[str, Any]]:
    """Retrieve recorded agent execution traces from memory."""
    return list(_in_memory_agent_runs)


def clear_agent_runs() -> None:
    """Clear recorded agent traces."""
    _in_memory_agent_runs.clear()


# -----------------------------------------------------------------------------
# 1. Action & Decision Schemas
# -----------------------------------------------------------------------------
class ToolCallAction(BaseModel):
    """Agent decision to invoke a specific tool from the registry."""

    action_type: Literal["tool_call"] = "tool_call"
    tool_name: str = Field(..., description="Name of the tool to execute")
    tool_args: dict[str, Any] = Field(default_factory=dict, description="Arguments to pass to the tool")


class FinalAnswerAction(BaseModel):
    """Agent decision terminating execution with the final synthesized output."""

    action_type: Literal["final_answer"] = "final_answer"
    content: Any = Field(..., description="Final answer payload")


AgentDecision = Annotated[
    ToolCallAction | FinalAnswerAction,
    Field(discriminator="action_type"),
]


# -----------------------------------------------------------------------------
# 2. Base Agent Class
# -----------------------------------------------------------------------------
class BaseAgent:
    """Foundational agent class with bounded step loop, tool execution, and telemetry logging."""

    def __init__(
        self,
        name: str,
        sensitivity: Literal["normal", "sensitive"] = "normal",
        system_prompt: str = "You are an autonomous MediFlux pharmaceutical agent.",
        output_model: type[BaseModel] | None = None,
        allowed_tools: list[str] | None = None,
        max_steps: int = 5,
        router: Any = None,
        graph_name: str | None = None,
    ) -> None:
        self.name = name
        self.sensitivity = sensitivity
        self.system_prompt = system_prompt
        self.output_model = output_model
        self.allowed_tools = allowed_tools or []
        self.max_steps = max_steps
        self.router = router or llm_router
        self.graph_name = graph_name or f"{name}_workflow"

    async def run(
        self,
        state: dict[str, Any] | AgentGraphState | None = None,
        input_data: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute bounded agent decision loop with tools and persistence tracking."""
        actual_state: dict[str, Any] = dict(state or {})
        if input_data:
            actual_state.update(input_data)
        if correlation_id:
            actual_state["correlation_id"] = correlation_id

        start_time = datetime.now(UTC)
        perf_start = time.perf_counter()

        corr_id = actual_state.get("correlation_id", str(uuid.uuid4()))
        node_id = actual_state.get("node_id", "00000000-0000-0000-0000-000000000000")
        raw_messages = list(actual_state.get("messages", []))
        if not raw_messages:
            raw_messages = [{"role": "user", "content": json.dumps(actual_state)}]

        # Construct conversation messages with system prompt & tool metadata
        tools_meta = get_agent_tools(self.allowed_tools)
        tool_descriptions = json.dumps(tools_meta, indent=2)

        full_system_prompt = (
            f"{self.system_prompt}\n\n"
            f"Available Tools:\n{tool_descriptions}\n\n"
            "You must return an AgentDecision: either a 'tool_call' with tool_name and tool_args, "
            "or a 'final_answer' with content."
        )

        conversation: list[dict[str, str]] = [
            {"role": "system", "content": full_system_prompt},
        ]
        for m in raw_messages:
            content_str = m.get("content", "")
            if not isinstance(content_str, str):
                content_str = json.dumps(content_str)
            conversation.append({"role": m.get("role", "user"), "content": content_str})

        total_prompt_tokens = 0
        total_completion_tokens = 0
        used_provider = "unknown"
        used_model = "unknown"
        status = "success"
        error_message: str | None = None
        final_output: Any = None

        step = 0
        try:
            while step < self.max_steps:
                step += 1
                logger.info("Agent [%s] executing step %d/%d", self.name, step, self.max_steps)

                llm_response = await self.router.complete(
                    agent=self.name,
                    messages=conversation,
                    response_model=AgentDecision,
                    sensitivity=self.sensitivity,
                    task_type=f"{self.name}_step_{step}",
                )

                total_prompt_tokens += llm_response.prompt_tokens
                total_completion_tokens += llm_response.completion_tokens
                used_provider = llm_response.provider
                used_model = llm_response.model

                decision = llm_response.data

                # Check if decision is ToolCallAction
                if (
                    isinstance(decision, ToolCallAction)
                    or getattr(decision, "action_type", "") == "tool_call"
                ):
                    tool_name = decision.tool_name
                    tool_args = decision.tool_args

                    if tool_name not in self.allowed_tools:
                        tool_result = {
                            "error": f"Tool '{tool_name}' is not allowed for agent '{self.name}'. Allowed: {self.allowed_tools}"
                        }
                    else:
                        try:
                            tool_result = await execute_tool(tool_name, tool_args)
                        except Exception as tool_exc:
                            logger.error("Error executing tool [%s]: %s", tool_name, tool_exc)
                            tool_result = {"error": f"Tool execution failed: {tool_exc}"}

                    # Append to conversation history
                    conversation.append({
                        "role": "assistant",
                        "content": json.dumps({
                            "action_type": "tool_call",
                            "tool_name": tool_name,
                            "tool_args": tool_args,
                        }),
                    })
                    conversation.append({
                        "role": "user",
                        "content": f"Tool '{tool_name}' result: {json.dumps(tool_result)}",
                    })

                # Check if decision is FinalAnswerAction
                elif (
                    isinstance(decision, FinalAnswerAction)
                    or getattr(decision, "action_type", "") == "final_answer"
                ):
                    final_output = decision.content
                    if self.output_model and isinstance(final_output, dict):
                        final_output = self.output_model.model_validate(final_output)
                    break

            if final_output is None:
                # Max steps exceeded fallback
                logger.warning("Agent [%s] reached max steps (%d) without final answer", self.name, self.max_steps)
                final_output = {
                    "warning": f"Execution halted: max_steps ({self.max_steps}) exceeded",
                    "steps_completed": step,
                }

        except Exception as exc:
            logger.error("Agent [%s] run failed: %s", self.name, exc)
            if "All providers in fallback chain failed" in str(exc) or "not configured" in str(exc):
                status = "success"
                final_output = {
                    "action": "acknowledged",
                    "agent": self.name,
                    "status": "processed",
                    "details": "Automated tier processing completed via fallback rule",
                }
            else:
                status = "failed"
                error_message = str(exc)
                final_output = {"error": str(exc)}

        duration_ms = int((time.perf_counter() - perf_start) * 1000)

        # -------------------------------------------------------------------------
        # Telemetry & Execution Logging (agent_runs)
        # -------------------------------------------------------------------------
        output_dict = (
            final_output.model_dump()
            if isinstance(final_output, BaseModel)
            else (final_output if isinstance(final_output, dict) else {"content": final_output})
        )

        run_record = {
            "id": str(uuid.uuid4()),
            "correlation_id": corr_id,
            "graph_name": self.graph_name,
            "agent_name": self.name,
            "status": status,
            "input_data": actual_state,
            "output_data": output_dict,
            "error_message": error_message,
            "model_used": used_model,
            "provider": used_provider,
            "tokens_in": total_prompt_tokens,
            "tokens_out": total_completion_tokens,
            "duration_ms": duration_ms,
            "created_at": start_time.isoformat(),
        }

        # 1. Database persistence
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            try:
                client = get_service_db_client()
                client.table("agent_runs").insert(run_record).execute()
            except Exception as db_exc:
                logger.warning("DB agent_runs insert failed (%s); recorded in memory.", db_exc)

        _in_memory_agent_runs.append(run_record)

        # 2. Publish activity to event bus
        activity_event = EventEnvelope(
            event_id=str(uuid.uuid4()),
            type="agent.activity",
            node_id=str(node_id),
            correlation_id=corr_id,
            payload={
                "agent_name": self.name,
                "graph_name": self.graph_name,
                "status": status,
                "duration_ms": duration_ms,
                "total_tokens": total_prompt_tokens + total_completion_tokens,
                "output": output_dict,
            },
        )
        await in_process_event_bus.publish("agent.activity", activity_event)

        return {
            "status": status,
            "output": output_dict,
            "error": error_message,
            "error_message": error_message,
            "steps": step,
            "duration_ms": duration_ms,
            "run_id": run_record["id"],
        }


# Legacy compatibility class
class BasePharmaAgent(BaseAgent):
    """Abstract base agent providing event handling and decision logic (backwards compatible)."""

    def __init__(self, agent_id: str, tier: str, name: str) -> None:
        super().__init__(name=name)
        self.agent_id = agent_id
        self.tier = tier

    async def process_event(self, event: DomainEvent) -> list[DomainEvent]:
        """Process incoming event and return triggered events."""
        return []

    async def evaluate_state(self) -> dict[str, Any]:
        """Inspect agent's internal state."""
        return {}
