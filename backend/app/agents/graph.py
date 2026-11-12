"""LangGraph execution graph constructor and persistent SQLite checkpointer."""

import logging
import sqlite3
from pathlib import Path
from typing import Any

import aiosqlite
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.base import BaseAgent
from app.agents.hitl import request_human_approval
from app.agents.state import AgentGraphState

logger = logging.getLogger("mediflux.agents.graph")


def get_sqlite_checkpointer(db_path: str = "checkpoints.db") -> SqliteSaver:
    """Instantiate a persistent synchronous SQLite checkpointer for LangGraph state persistence."""
    path = Path(db_path)
    if path.parent and str(path.parent) != ".":
        path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver


async def get_async_sqlite_checkpointer(
    db_path: str = "checkpoints.db",
    conn: aiosqlite.Connection | None = None,
) -> AsyncSqliteSaver:
    """Instantiate a persistent asynchronous SQLite checkpointer for LangGraph state persistence."""
    path = Path(db_path)
    if path.parent and str(path.parent) != ".":
        path.parent.mkdir(parents=True, exist_ok=True)

    actual_conn = conn or await aiosqlite.connect(str(path))
    saver = AsyncSqliteSaver(actual_conn)
    await saver.setup()
    return saver


def build_single_agent_graph(
    agent: BaseAgent,
    checkpointer: Any = None,
) -> CompiledStateGraph:
    """Compile an isolated single-agent graph with bounded execution and state persistence."""
    builder = StateGraph(AgentGraphState)

    async def _agent_node(state: AgentGraphState) -> dict[str, Any]:
        result = await agent.run(state)
        # Update messages and data in state
        new_messages = list(state.get("messages", []))
        new_messages.append({
            "role": "assistant",
            "content": result.get("output", {}),
        })
        return {
            "messages": new_messages,
            "data": {**state.get("data", {}), **result.get("output", {})},
            "next_step": "completed",
        }

    builder.add_node("agent_execution", _agent_node)
    builder.add_edge(START, "agent_execution")
    builder.add_edge("agent_execution", END)

    return builder.compile(checkpointer=checkpointer)


def build_hitl_workflow_graph(
    checkpointer: Any = None,
) -> CompiledStateGraph:
    """Build a multi-step graph with Human-in-the-Loop approval interrupt and resumption."""
    builder = StateGraph(AgentGraphState)

    async def _propose_action(state: AgentGraphState) -> dict[str, Any]:
        """Propose an action and pause for human review."""
        proposal = {
            "action": "reorder_restock",
            "medicine_id": state.get("data", {}).get("medicine_id", "MED-001"),
            "quantity": state.get("data", {}).get("requested_quantity", 100),
        }

        # Request human approval (triggers LangGraph interrupt)
        approval_result = await request_human_approval(
            state=state,
            task_type="reorder_approval",
            payload=proposal,
            risk_level="high",
        )

        return {
            "data": {
                **state.get("data", {}),
                "approval_result": approval_result,
                "hitl_pending": False,
            },
            "next_step": "execute_action",
        }

    async def _execute_action(state: AgentGraphState) -> dict[str, Any]:
        """Execute action post-human approval."""
        approval = state.get("data", {}).get("approval_result", {})
        status = "approved_and_executed" if approval.get("approved") else "rejected"
        return {
            "data": {
                **state.get("data", {}),
                "final_execution_status": status,
            },
            "next_step": "done",
        }

    builder.add_node("propose_action", _propose_action)
    builder.add_node("execute_action", _execute_action)

    builder.add_edge(START, "propose_action")
    builder.add_edge("propose_action", "execute_action")
    builder.add_edge("execute_action", END)

    return builder.compile(checkpointer=checkpointer)
