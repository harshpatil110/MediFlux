# MediFlux

> **AI-Native Hyper-Connected Pharmaceutical Supply Chain Ecosystem for India**

MediFlux enables instantaneous single-unit retail demand propagation: when 1 strip of medicine is sold at a retail counter point-of-sale (POS), an automated multi-agent cascade propagates demand up the supply chain across four tiers:

$$\text{Pharmacy Edge Node} \longrightarrow \text{Stockist Hub} \longrightarrow \text{Distributor Layer} \longrightarrow \text{Manufacturer Plant}$$

---

## Architecture Overview

```
                      +---------------------------------------+
                      |       Manufacturer Plant Tier         |
                      +---------------------------------------+
                                          ^
                                          | Reorder Batch
                      +---------------------------------------+
                      |       Distributor Layer Tier          |
                      +---------------------------------------+
                                          ^
                                          | Restock Demand
                      +---------------------------------------+
                      |         Stockist Hub Tier             |
                      +---------------------------------------+
                                          ^
                                          | Aggregated Signal
                      +---------------------------------------+
                      |      Pharmacy Edge Node (POS)         |
                      +---------------------------------------+
                                          ^
                                          | 1 Strip Dispensed
                                   [Patient / Counter]
```

---

## Monorepo Layout

```
mediflux/
  backend/           # FastAPI, LangGraph agents, async event bus, Supabase client
  frontend/          # Vite + React 18 + TypeScript + Tailwind CSS (Warm Editorial Minimalism)
  desktop/           # Tauri desktop packaging (Task 28)
  supabase/          # SQL migrations, seeds, RLS policies
  clients/           # External API integrations & sample clients
  fixtures/          # Synthetic test datasets (CSV/XML/JSON, prescriptions, notices)
  docs/              # System specifications, audit trails, and architecture guides
  scripts/           # Local orchestration and simulation scripts
  AGENTS.md          # AI IDE developer rules, conventions, and deferred constraints
  .env.example       # Template environment variables
```

---

## Quickstart

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm
- (Optional) Ollama for offline LLM support

### 1. Configure Environment
```bash
cp .env.example .env
```

### 2. Launch Stack (Backend + Frontend)
**Windows (PowerShell):**
```powershell
.\scripts\start-all.ps1
```

**Linux / macOS (Bash):**
```bash
chmod +x scripts/start-all.sh
./scripts/start-all.sh
```

- Backend API: `http://localhost:8000` (Docs: `http://localhost:8000/docs`, Health: `http://localhost:8000/health`)
- Frontend App: `http://localhost:5173`

---

## Testing & Quality

```powershell
# Backend Tests & Lint
cd backend
pytest
ruff check .

# Frontend Build
cd frontend
npm run build
```

---

## Spec-Driven Development

Every task is driven by specifications under `docs/specs/` and tracked in the audit trail `docs/HOW_AI_BUILT_THIS.md`. Consult `AGENTS.md` before making code changes.
