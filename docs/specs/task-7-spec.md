# Task Spec: Task 7 — Agent Framework (Base Agent, Tools, Traces, HITL Primitives)

---

## 1. Objective
Create the foundational agent framework and LangGraph execution primitives for the MediFlux autonomous supply chain network:
1. Base agent class (`BaseAgent`) with bounded decision loops and typed action schemas (`ToolCallAction`, `FinalAnswerAction`, `AgentDecision`).
2. Global, typed tool registry (`@tool`) and scoped tool discovery (`get_agent_tools`).
3. Initial shared tools: `get_inventory`, `get_recent_sales`, `get_node`, `list_nodes_in_cluster`, `run_module`, and `write_audit`.
4. LangGraph graph builders (`build_single_agent_graph`, `build_hitl_workflow_graph`) and persistent SQLite checkpointer (`checkpoints.db`).
5. Human-in-the-Loop (HITL) approval primitives (`request_human_approval`) with `hitl_tasks` persistence and `interrupt()` execution pauses.
6. Execution trace logging into `agent_runs` table and real-time activity broadcasting on the `agent.activity` topic on `InProcessEventBus`.
7. Deterministic test harness (`FakeLLM`).

---

## 2. Inputs & Context
- **Dependencies**: Tasks 1–6, `langgraph`, `langgraph-checkpoint-sqlite`, `aiosqlite`, `pydantic v2`, Supabase database schema.
- **Constraints & Rules**:
  - Bounded iteration loops: agents must respect `max_steps` and halt cleanly without runaway loops.
  - State persistence: graphs paused during execution must survive process restarts using persistent SQLite checkpoints (`checkpoints.db`).
  - Strict privacy: agents inherit sensitivity flags (`normal` vs `sensitive`), routing via Task 5's router to ensure air-gapped local Ollama execution when required.

---

## 3. Architecture & Design Decisions
- **Action & Decision Models (`app/agents/base.py`)**:
  - `ToolCallAction`: `action_type = "tool_call"`, `tool_name`, `tool_args`.
  - `FinalAnswerAction`: `action_type = "final_answer"`, `content`.
  - `AgentDecision`: Discriminated union on `action_type`.
- **Bounded Step Loop & Execution Tracing (`app/agents/base.py`)**:
  - `run(state)` enforces `step < max_steps`.
  - Injects permitted tool schemas into prompt.
  - Executes tool calls via registry and appends results back to conversation.
  - Automatically records full execution trace into `agent_runs` table (`correlation_id`, `graph_name`, `agent_name`, `status`, `input_data`, `output_data`, `tokens_in`, `tokens_out`, `duration_ms`).
  - Publishes `AgentActivityEvent` to `agent.activity` on `InProcessEventBus`.
- **Tool Registry (`app/agents/tools/registry.py`)**:
  - Decorator `@tool` dynamically infers Pydantic JSON schemas from Python type annotations.
  - Scoping helper `get_agent_tools(allowed_tools)` restricts LLM tool visibility per agent role.
- **LangGraph Checkpointing & HITL (`app/agents/graph.py` & `app/agents/hitl.py`)**:
  - Uses `SqliteSaver` (sync) and `AsyncSqliteSaver` (async) backed by `checkpoints.db`.
  - `request_human_approval`:
    1. Creates pending entry in `hitl_tasks`.
    2. Emits event on `hitl` topic on Event Bus.
    3. Triggers LangGraph's native `interrupt()` primitive to freeze execution.
    4. Resumes upon receiving approval payload via `Command(resume=...)`.
- **Deterministic Test Harness (`app/agents/testing.py`)**:
  - `FakeLLM` provides queued, reproducible `AgentDecision` outputs for fast, network-free unit tests.

---

## 4. Outputs & Deliverables
- **Core Modules**:
  - `backend/app/agents/base.py`: `BaseAgent`, `ToolCallAction`, `FinalAnswerAction`, `AgentDecision`, trace recording.
  - `backend/app/agents/state.py`: `AgentGraphState` TypedDict.
  - `backend/app/agents/tools/registry.py`: `@tool` decorator, `execute_tool`, `get_agent_tools`.
  - `backend/app/agents/tools/impl/shared.py`: 6 shared built-in tools.
  - `backend/app/agents/graph.py`: State graph builders and SQLite checkpointers.
  - `backend/app/agents/hitl.py`: `request_human_approval` and HITL task manager.
  - `backend/app/agents/testing.py`: `FakeLLM` deterministic test class.
  - `backend/app/agents/__init__.py`: Public exports.
- **Test Suite**:
  - `backend/tests/test_agent_framework.py`: 6 comprehensive unit and integration tests.

---

## 5. Automated Verification & Results
- **Pytest**:
  ```powershell
  cd backend; .\venv\Scripts\pytest
  # Result: 48 passed in 6.22s (6/6 test_agent_framework.py passed)
  ```
- **Linter**:
  ```powershell
  cd backend; .\venv\Scripts\ruff check .
  # Result: All checks passed! (0 warnings, 0 errors)
  ```
- **Test Coverage**:
  1. `test_tool_calling_agent_execution_and_telemetry`: Tool execution, feedback loop, `agent_runs` persistence, and `agent.activity` bus event.
  2. `test_max_steps_halts_infinite_loop`: Loop limit halts stuck agents at step count.
  3. `test_unauthorized_tool_call_is_rejected`: Calling unlisted tool is rejected and handled gracefully.
  4. `test_tool_metadata_scoping`: Verified `get_agent_tools` schema scoping.
  5. `test_hitl_interrupt_and_resume_across_process_restart`: Verified HITL interrupt, SQLite state persistence across simulated process exit, and clean resumption.
  6. `test_single_agent_graph_compilation`: Compiled and executed single-agent LangGraph workflow.
