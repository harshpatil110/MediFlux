# Task Spec: Task 5 — LLM Router (NVIDIA, OpenRouter, Ollama)

---

## 1. Objective
Build an intelligent, multi-provider LLM abstraction and routing engine for MediFlux. The engine provides:
1. Multi-provider failover (`nvidia -> openrouter -> ollama`).
2. Strict privacy isolation for sensitive data (routing only to local Ollama; never leaking to hosted cloud APIs).
3. Pydantic-driven structured outputs with automatic JSON schema injection and a self-healing repair loop.
4. Thread-safe SQLite response caching (`off`, `record`, `replay` modes) for deterministic offline execution and testing.
5. In-flight telemetry tracking (token usage, latency, provider/model attribution, correlation IDs).

---

## 2. Inputs & Context
- **Dependencies**: Tasks 1–4, `httpx`, `pyyaml`, `pydantic v2`.
- **System Constraints**:
  - Deferred technologies: No Redis, Docker, WASM, or Kafka/Redpanda. Caching is handled locally via SQLite (`llm_cache.db`).
  - Strict privacy constraint: Queries flagged with `sensitivity="sensitive"` MUST route exclusively to local Ollama. Failures must raise `SensitiveDataRoutingError` immediately without falling back to hosted cloud providers.
  - Structured output guarantee: All responses return typed, validated Pydantic model instances.

---

## 3. Architecture & Design Decisions
- **Provider Adapters (`app/llm/providers.py`)**:
  - `LLMProvider` abstract base class with async concurrency protection via `asyncio.Semaphore`.
  - `NvidiaProvider`: Hosted NVIDIA NIM API with 5-call concurrency limit, 30s timeout, and Bearer token auth.
  - `OpenRouterProvider`: OpenRouter free-tier endpoint with 5-call concurrency limit, 30s timeout, and custom attribution headers.
  - `OllamaProvider`: Local Ollama instance (`/v1/chat/completions`) with 2-call concurrency limit and 60s timeout.
  - Standardized error handling: maps 429 (rate limits), 5xx (server errors), and timeouts to `LLMProviderError`.
- **Parser & Self-Healing Repair Loop (`app/llm/parser.py`)**:
  - `inject_schema`: Embeds `model_json_schema()` directly into system instructions with strict JSON-only formatting rules without mutating input messages.
  - `extract_json_str` & `parse_and_validate`: Strips markdown fences (` ```json `), extracts innermost JSON objects, and validates via `model_validate_json`.
  - `execute_repair_loop`: On schema failure, retains conversation context, appends model error feedback, and triggers up to 2 repair iterations before raising `LLMStructuredOutputError`.
- **SQLite Response Cache (`app/llm/cache.py`)**:
  - `SQLiteLLMCache`: Thread-safe persistence storing validated JSON payloads and metadata in `llm_cache.db`.
  - Deterministic key generation: SHA-256 hash across `agent + messages + response_model.model_json_schema()`.
  - Modes:
    - `off`: Passthrough execution.
    - `record`: Caches all successful completions.
    - `replay`: Replays cached responses without network access; cache misses raise `LLMCacheMissError`.
- **Telemetry Layer (`app/llm/telemetry.py`)**:
  - `LLMTelemetry`: Records prompt tokens, completion tokens, total tokens, latency in milliseconds, cache hit status, provider, model, and correlation ID.
- **Router Orchestrator (`app/llm/router.py`)**:
  - Loads provider limits, fallback chains, and agent-specific model mappings from `config/agent_models.yaml`.
  - Handles sensitivity routing: enforces local Ollama boundary for `sensitivity="sensitive"`.
  - Handles fallback sequence for `sensitivity="normal"`: NVIDIA NIM $\rightarrow$ OpenRouter $\rightarrow$ Ollama.

---

## 4. Outputs & Deliverables
- **Configuration**:
  - `config/agent_models.yaml`: Central model mapping per agent and provider fallback configuration.
  - `backend/config/agent_models.yaml`: Backend copy for runtime resolution.
- **Core Modules**:
  - `backend/app/llm/schemas.py`: Custom exceptions (`LLMBaseError`, `LLMProviderError`, `SensitiveDataRoutingError`, `LLMStructuredOutputError`, `LLMCacheMissError`), `LLMResponse[T]`, `RawCompletionResult`, and `TokenUsage`.
  - `backend/app/llm/cache.py`: `SQLiteLLMCache` engine.
  - `backend/app/llm/telemetry.py`: `LLMTelemetry` tracker.
  - `backend/app/llm/providers.py`: `NvidiaProvider`, `OpenRouterProvider`, and `OllamaProvider`.
  - `backend/app/llm/parser.py`: Schema injector, JSON extractor, and `execute_repair_loop`.
  - `backend/app/llm/router.py`: `LLMRouter` orchestrator.
  - `backend/app/llm/__init__.py`: Public package exports.
- **Test Suite**:
  - `backend/tests/test_llm_router.py`: 10 comprehensive unit and integration tests.

---

## 5. Automated Verification & Results
- **Pytest**:
  ```powershell
  cd backend; .\venv\Scripts\pytest
  # Result: 35 passed in 4.75s (10/10 test_llm_router.py passed)
  ```
- **Linter**:
  ```powershell
  cd backend; .\venv\Scripts\ruff check .
  # Result: All checks passed! (0 warnings, 0 errors)
  ```
- **Test Matrix Covered**:
  1. Schema injection immutability and markdown-fenced JSON extraction.
  2. Normal query completion returning structured Pydantic model with full telemetry.
  3. Automatic fallback chain execution on HTTP 429 rate limit (NVIDIA $\rightarrow$ OpenRouter).
  4. Privacy isolation: sensitive queries route to Ollama; Ollama failure raises `SensitiveDataRoutingError` with ZERO calls to cloud providers.
  5. Privacy isolation: sensitive queries succeed via Ollama without touching cloud APIs.
  6. SQLite cache replay mode: deterministic hit without network, and `LLMCacheMissError` on unseeded query.
  7. Self-healing repair loop: recovering from malformed JSON via multi-turn feedback.
  8. Repair loop exhaustion raising error when model persistently outputs invalid format.
