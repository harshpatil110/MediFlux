# Task Spec: Task 4 — FastAPI Core Skeleton

---

## 1. Objective
Establish the foundational FastAPI application architecture, middleware stack, standardized error format, correlation ID context tracing, shared Pydantic response schemas, cursor pagination, and initial RLS-protected domain endpoints (`/me`, `/nodes`, `/products`, `/inventory`).

---

## 2. Inputs & Context
- **Dependencies**: Tasks 1–3, Supabase database schema, Supabase Auth/JWT settings, and RLS security dependencies.
- **System Constraints**:
  - Strict standardized JSON error schema: `{ "error": { "code", "message", "details" } }`.
  - Correlation ID injection via `X-Correlation-ID` header and context variable in all logs.
  - RLS data scoping on multi-tier inventory and topology nodes.

---

## 3. Architecture & Design Decisions
- **Settings & Config (`app/core/config.py`)**:
  - `pydantic-settings` BaseSettings loading `.env` with fallback defaults.
  - Project metadata, environment, CORS origins (Vite dev + Tauri).
- **Middleware & Tracing (`app/core/middleware.py` & `app/core/logging.py`)**:
  - `CorrelationIdMiddleware` extracts incoming `X-Correlation-ID` or generates a UUID4.
  - Python logging formatter includes `[%(correlation_id)s]`.
  - Outgoing HTTP responses expose `X-Correlation-ID`.
  - Unhandled 500 exceptions caught at ASGI boundary to guarantee standardized error format and avoid leaking stack traces.
- **Exception Handlers (`app/core/exceptions.py` & `app/core/handlers.py`)**:
  - Custom exceptions: `AppException`, `NotFoundError`, `UnauthorizedError`, `ForbiddenError`, `ValidationError`.
  - Standard handlers registered for `AppException`, Starlette/FastAPI `HTTPException`, `RequestValidationError`, and `Exception`.
- **Shared Schemas (`app/schemas/common.py` & `app/schemas/base.py`)**:
  - `PaginationParams`, `PaginatedResponse[T]`, `ErrorResponse`, `UserProfile`, `NodeResponse`, `ProductResponse`, `InventoryItemResponse`.
- **Initial Endpoints (`app/api/v1/endpoints/`)**:
  - `GET /api/v1/me`: Caller profile, role, and node association.
  - `GET /api/v1/nodes`: RLS-filtered supply-chain nodes with cursor pagination.
  - `GET /api/v1/products`: Master SKU catalog with search and cold-chain filters.
  - `GET /api/v1/inventory`: RLS-restricted inventory balances for caller's node and visible downstream nodes.

---

## 4. Outputs & Deliverables
- **Core Modules**:
  - `backend/app/core/config.py`
  - `backend/app/core/logging.py`
  - `backend/app/core/middleware.py`
  - `backend/app/core/exceptions.py`
  - `backend/app/core/handlers.py`
  - `backend/app/core/security.py`
- **Schemas**:
  - `backend/app/schemas/common.py`
  - `backend/app/schemas/base.py`
- **API Endpoints**:
  - `backend/app/api/v1/endpoints/auth.py`
  - `backend/app/api/v1/endpoints/nodes.py`
  - `backend/app/api/v1/endpoints/products.py`
  - `backend/app/api/v1/endpoints/inventory.py`
  - `backend/app/api/v1/router.py`
  - `backend/app/main.py`
- **Test Suite**:
  - `backend/tests/test_api_core.py` (12 comprehensive test cases)
- **Documentation**:
  - `docs/specs/task-4-spec.md`
  - `docs/HOW_AI_BUILT_THIS.md`

---

## 5. Edge Cases & Error Handling
- **Missing or Invalid Auth**: `get_current_user` raises `UnauthorizedError`, returning status 401 with standard `{ "error": { "code": "UNAUTHORIZED", ... } }`.
- **Invalid Query Parameters**: Intercepted by `RequestValidationError` handler, returning 422 with structured field errors.
- **Uncaught Server Errors**: Masked as `{ "error": { "code": "INTERNAL_SERVER_ERROR", "message": "An unexpected internal server error occurred", "details": {} } }` with correlation ID attached.
- **RLS Boundary Breach**: Non-privileged actors only query inventory and nodes where `node_id` matches allowed IDs.

---

## 6. Acceptance Criteria Checklist
- [x] `core/config.py` loads settings using `pydantic-settings`.
- [x] Correlation ID middleware registered and returns `X-Correlation-ID` in headers.
- [x] Error format strictly adheres to `{ "error": { "code": ..., "message": ..., "details": ... } }`.
- [x] GET `/health` returns HTTP 200 with system status and version.
- [x] Endpoints `/api/v1/me`, `/api/v1/nodes`, `/api/v1/products`, and `/api/v1/inventory` implemented with RLS scoping.
- [x] OpenAPI interactive documentation accessible at `/docs` with custom tags.
- [x] Test suite `tests/test_api_core.py` passes with 0 failures (`pytest`).

