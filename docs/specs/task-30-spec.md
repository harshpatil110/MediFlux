# Task 30 Specification: MediFlux MVP Submission Package & Empirical Verification

## Overview
Task 30 formalizes the definitive submission package for **MediFlux** (also designated in RFP specifications as **NexusChain**). It establishes measured empirical evidence, comprehensive architecture and security documentation, a deterministic 10-step scripted presentation walkthrough, an exported OpenAPI 3.1.0 contract, and release tagging (`v1.0.0-mvp`).

---

## Deliverables & Acceptance Criteria

### 1. Empirical Hardware Fingerprint & Benchmarks (Acceptance Criterion #1)
- **Harness**: `scripts/run_benchmarks.py` executes live ASGI benchmarks against the complete in-process FastAPI application.
- **Hardware Fingerprint**: Dynamically captures host CPU model, logical core count (20 cores), OS platform, and Python runtime version (3.12.6).
- **Benchmark 1A (Single-Event Ingestion)**: Measured concurrency scaling across levels [1, 5, 10, 25, 50], calculating exact p50, p95, p99, mean latencies, and request throughput (req/s).
- **Benchmark 1B (Batch Ingestion)**: Measured bulk POS sales processing across batch sizes [10, 50, 100].
- **Benchmark 2 (4-Tier Demand Cascade Latency)**: End-to-end multi-agent cascade latency measured across 5 runs, computing min, max, mean, and standard deviation.
- **Benchmark 3 (LLM Router & Cache Hit Rate)**: Measures cache hit rate (100.0%) and fallback latency in replay mode.
- **Persisted Artifacts**:
  - `docs/benchmark_results.json` (raw measured JSON metrics)
  - `docs/BENCHMARKS.md` (programmatically generated markdown with zero invented numbers)

### 2. Token Budget & Multi-Tier Cost Modeling (Acceptance Criterion #1)
- **Telemetry Harness**: `scripts/generate_token_report.py` aggregates prompt, completion, and total tokens across all 18 production agents.
- **4-Tier Demand Cascade Budget**: Quantifies exact token consumption per retail dispensing cascade (989 prompt + 358 completion = 1,357 total tokens per cascade).
- **Extrapolation Matrix**: Models monthly operational token volumes and dollar costs across three scaling tiers (Pilot: 50 pharmacies, Regional: 500 pharmacies, National: 10,000 pharmacies) against three provider strategies:
  1. NVIDIA NIM Free Tier ($0.00 / month)
  2. OpenRouter Free Tier ($0.00 / month)
  3. Commercial Reference Tier (GPT-4o @ $2.50/$10.00 per 1M tokens)
- **Persisted Artifacts**:
  - `docs/token_report_results.json`
  - `docs/TOKEN_AND_COST_REPORT.md`

### 3. Comprehensive Technical Documentation (Acceptance Criterion #2)
- **`docs/ARCHITECTURE.md`**: Complete architectural specification including Mermaid diagrams for the 4-tier network topology and event-driven data flow, state machine breakdown of all 6 LangGraph graphs, inventory of 18 domain agents, Dynamic Module Registry architecture, LLM Router fallback cascade, and data store inventory.
- **`docs/POST_MVP.md`**: Post-MVP evolution roadmap covering In-Process EventBus to Redpanda/Kafka migration, Python AST guard to WebAssembly (Wasmtime) sandbox evolution, Redis cluster state management, conceptual production Docker topology, sovereign Llama-3.3-70B on Indian cloud data centers (MeitY empanelled), OpenTelemetry instrumentation, and an honest MVP vs Production disclosure matrix.
- **`docs/SECURITY_AND_COMPLIANCE.md`**: Multi-tenant Row-Level Security (RLS) model, SHA-256 hashed API keys and HMAC-SHA256 webhook signatures, DPDP Act 2023 patient privacy and sovereign sensitive routing (`sensitivity="sensitive"`), and tamper-evident SHA-256 rolling audit ledger hash chain.
- **`docs/DEMO_SCRIPT.md`**: Timed 10-step interactive presentation guide (8–10 minutes) with narrations, curl commands, UI navigation, and expected outputs.
- **`docs/openapi.json`**: Complete OpenAPI 3.1.0 specification generated from FastAPI `app.openapi()`, registering 85 REST routes.
- **`README.md`**: Comprehensive root guide with RFP mapping table, quick start, demo guide, test instructions, and documentation index.
- **`docs/HOW_AI_BUILT_THIS.md`**: Appended Task 30 section detailing Phase 8 submission package implementation.

### 4. 10-Step Interactive Demo Runner & Double Verification (Acceptance Criterion #3)
- **Expanded Demo Runner (`scripts/run_demo.py`)**:
  - Act 1: Single-Unit Retail POS Sale → 4-Tier Automated Demand Cascade
  - Act 2: Self-Evolving Adapter Forge → Legacy Format Ingestion
  - Act 3: Autonomous Regulatory Pipeline → Staging Diff → HITL Hot-Swap
  - Act 4: Sovereign Multimodal Prescription Scanner → Schedule H CDSCO Verification
  - Act 5: Cold-Chain IoT Telemetry → Arrhenius Shelf-Life Auto-Quarantine & Rebalance
  - Act 6: Natural Language Network Copilot & Cryptographic Audit Verification
  - Act 7: Real-Time Canonical Event Ingestion & Server-Sent Events (SSE) Inspection
  - Act 8: Dynamic Business Module Registry & AST Sandbox Isolation
  - Act 9: OpenAPI 3.1.0 Contract Schema & Developer Hub Validation
  - Act 10: Multi-Tier Network Topology & Real-Time Operational KPIs
- **Verification Guarantee**: Verified to execute twice in a row from pristine reset state (`python -m scripts.reset_demo && python -m scripts.run_demo --mode replay`) with exit code 0.

---

## Quality & Verification Standards
- **Zero Invented Numbers**: Every single number in `BENCHMARKS.md` and `TOKEN_AND_COST_REPORT.md` is strictly computed and loaded from measured JSON files.
- **Zero Deferred Tech**: Zero Redis, Docker, WASM, or Kafka introduced into MVP code.
- **Automated Test Suite**: `backend/tests/test_task30_submission_package.py` tests all documentation files, contract validation, secrets cleanliness, and demo replay capability.

