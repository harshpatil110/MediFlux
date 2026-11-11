# Task Spec: Task [Number] — [Task Title]

---

## 1. Objective
A concise statement of what this task accomplishes and its place in the MediFlux 4-tier supply chain.

---

## 2. Inputs & Context
- **Dependencies**: Prerequisites, completed tasks, and database state required.
- **Payloads / Data**: Relevant schemas, incoming event payloads, or external API contracts.
- **Reference Docs**: Links to `Design.md`, `tasks.md`, or relevant regulatory/architectural docs.

---

## 3. Architecture & Design Decisions
- **Component Placement**: Files, modules, and submodules impacted.
- **Data Flow**: Sequence diagrams or ASCII flow of data between nodes.
- **Constraints Enforced**:
  - No Redis, Docker, WASM, or Kafka/Redpanda.
  - Strict typing and Pydantic models.
  - In-process event bus and Supabase persistence.

---

## 4. Outputs & Deliverables
- **Code Artifacts**: New/modified files, endpoints, classes, or components.
- **Database Changes**: Migrations, tables, indexes, or RLS policies.
- **Automated Tests**: Unit and integration test files.

---

## 5. Edge Cases & Error Handling
- **Failure Modes**: Network timeouts, schema validation errors, concurrency collisions.
- **Recovery Strategies**: Retry mechanisms (Tenacity), fallback providers, circuit breaking.
- **Logging & Monitoring**: Events emitted and log structures.

---

## 6. Acceptance Criteria Checklist
- [ ] Functional requirement 1 implemented and verified.
- [ ] Functional requirement 2 implemented and verified.
- [ ] Unit and integration tests written and passing cleanly (`pytest`).
- [ ] Linter passing with zero warnings or errors (`ruff check .`).
- [ ] Audit entry recorded in `docs/HOW_AI_BUILT_THIS.md`.

