# MediFlux — AI-IDE Rules & Developer Guide (`AGENTS.md`)

This document governs all AI agents and human developers contributing to **MediFlux**.
Every instruction, convention, constraint, and architectural standard here is binding.

---

## 1. Project Summary & Core Value Proposition

**MediFlux** is an AI-native hyper-connected pharmaceutical supply chain ecosystem for India.
The core value proposition is **instantaneous single-unit retail demand propagation**:
When 1 strip of medicine is sold at a retail counter point-of-sale (POS), an automated multi-agent cascade propagates demand up the supply chain across four tiers:

$$\text{Pharmacy Edge Node} \longrightarrow \text{Stockist Hub} \longrightarrow \text{Distributor Layer} \longrightarrow \text{Manufacturer Plant}$$

---

## 2. Technology Stack

- **Backend**: Python 3.11+, FastAPI, Uvicorn, Pydantic v2, Pydantic-Settings, HTTPX, Tenacity
- **Agent Orchestration**: LangGraph, in-process checkpointers
- **Database & Auth**: Supabase (PostgreSQL, pgvector, Row-Level Security, Auth)
- **Frontend**: Vite, React 18, TypeScript, Tailwind CSS, TanStack Query, React Router, Lucide React
- **Desktop**: Tauri wrapper (deferred to Task 28)
- **Free LLM Providers**: NVIDIA-hosted NIM endpoints, OpenRouter free tier, local Ollama fallback

---

## 3. ❌ DEFERRED ITEMS LIST (STRICTLY FORBIDDEN IN MVP CODE)

Under no circumstances should any AI or developer import, configure, or introduce these technologies during the MVP phase:

1. ❌ **Redis**: Strictly forbidden. Use in-process state, in-memory caching, or Supabase tables for state persistence.
2. ❌ **Docker / Containerization**: Strictly forbidden. The MVP runs bare-metal locally with standard virtual environments (`venv`) and Node runtimes.
3. ❌ **WASM Sandbox**: Strictly forbidden. Use static Python AST analysis and runtime inspection via `modules_runtime/guard.py`.
4. ❌ **Apache Kafka / Redpanda**: Strictly forbidden. Use the in-process asynchronous `EventBus` (`events/bus.py`) backed by the Supabase `events` table and Server-Sent Events (SSE).

---

## 4. Coding Conventions & Quality Standards

- **Type Hints**: 100% type coverage across all Python modules (`typing`, `pydantic`). No untyped public functions.
- **Data Models**: Use Pydantic v2 `BaseModel` for all request/response schemas, event payloads, and configuration settings.
- **Async First**: Use `async`/`await` for all I/O-bound operations (database queries, HTTP calls, LLM invocations, event dispatching).
- **Function Design**: Write small, modular, single-responsibility functions (< 50 lines preferred).
- **Error Handling**: Custom structured domain exceptions in `core/errors.py`. Never swallow exceptions without logging.
- **Design System**: Strictly adhere to the **Warm Editorial Minimalism** design system defined in `Design.md`.
  - Background: Warm Ivory (`#E8E4D3`), Deep Ivory (`#DFDBCA`).
  - Accent: Electric Teal (`#00AEBB`).
  - Text: Ink Black (`#031211`), Charcoal (`#5C584E`).
  - Borders: Structural 1px crisp borders (`#D8D3C3`).
  - No dark mode as default, no neon gradients, no glassmorphism, no rounded-full pill buttons.

---

## 5. Definition of Done (DoD)

A task is complete only when:
1. **Working Code**: All specified files, endpoints, and components are created with full functionality (no placeholders or stubs in critical logic).
2. **Automated Verification**:
   - Backend: `pytest` passes with 0 failures.
   - Linter: `ruff check .` passes with 0 warnings/errors.
   - Frontend: `npm run build` or TypeScript check passes cleanly.
3. **Spec & Audit Update**:
   - The task specification under `docs/specs/` is updated or created.
   - An entry is appended to `docs/HOW_AI_BUILT_THIS.md` detailing what was implemented and verified.

---

## 6. Commands Reference

### Backend
```powershell
# Run tests
cd backend; pytest

# Run linter
cd backend; ruff check .

# Start development server
cd backend; uvicorn app.main:app --reload --port 8000
```

### Frontend
```powershell
# Install dependencies
cd frontend; npm install

# Start Vite dev server
cd frontend; npm run dev

# Build check
cd frontend; npm run build
```

### Full Stack
```powershell
# Windows
.\scripts\start-all.ps1

# Linux / macOS
./scripts/start-all.sh
```

