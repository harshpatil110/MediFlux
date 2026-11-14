# MediFlux / NexusChain — Post-MVP Architectural Evolution Roadmap

> **Document Status**: Production Strategy Specification  
> **Target Release Horizon**: v2.0 Enterprise Production  
> **Compliance & Standards**: MeitY Cloud Guidelines, CDSCO Digital Health, DPDP Act 2023

---

## 1. Architectural Evolution: In-Process EventBus to Redpanda / Apache Kafka

### Current MVP Implementation
The MVP utilizes an in-process, asynchronous Python `EventBus` (`app/events/bus.py`) backed by the Supabase `events` table. This provides zero external dependency overhead and runs on bare metal with zero Docker or message broker setup.

### Production Enterprise Target (v2.0)
In high-throughput national production (> 100,000 events/minute), the in-process bus is migrated to a distributed **Redpanda** or **Apache Kafka** cluster.

#### Topic Partitioning Strategy
- **`mediflux.pos.sales`**: Partitioned by `pharmacy_id` (hash key) to guarantee strict chronological ordering per retail counter while parallelizing across partitions.
- **`mediflux.demand.cascades`**: Partitioned by `pincode_prefix` (first 3 digits of postal code) to align with regional stockist distribution territories.
- **`mediflux.iot.coldchain`**: Partitioned by `vehicle_id` / `shipment_id` for continuous sensor time-series streaming.
- **`mediflux.regulatory.alerts`**: Single-partition broadcast topic replicated across all regional consumer groups.

```mermaid
flowchart LR
    POS["10,000+ Retail POS Terminals"] -->|"Partition by pharmacy_id"| T1[("Topic: mediflux.pos.sales")]
    IoT["5,000+ IoT BLE/GPS Beacons"] -->|"Partition by vehicle_id"| T2[("Topic: mediflux.iot.coldchain")]
    CDSCO["CDSCO Gazette Watcher"] -->|"Broadcast"| T3[("Topic: mediflux.regulatory")]

    T1 --> CG1["Consumer Group: Replenishment Engine"]
    T1 --> CG2["Consumer Group: National Stockpile Telemetry"]
    T2 --> CG3["Consumer Group: Arrhenius Excursion Engine"]
    T3 --> CG4["Consumer Group: Dynamic Hot-Swap Pipeline"]
```

---

## 2. Sandbox Evolution: Python AST Guard to WebAssembly (WASM) / Firecracker

### Current MVP Implementation
The MVP isolates synthesized adapters and business rule patches via `modules_runtime/guard.py` using Python's native `ast` module. The AST inspector validates that incoming code imports zero banned modules (`os`, `sys`, `subprocess`, `socket`, `builtins`), performs zero network/filesystem I/O, and complies with strict interface signatures.

### Production Enterprise Target (v2.0)
To run untrusted third-party ERP adapters in multi-tenant environments without shared memory risks:
1. **Wasmtime / WebAssembly Micro-Sandboxes**: Compile translation adapters to `.wasm` bytecode executed inside isolated WASM runtimes with zero POSIX syscall capabilities. Memory is strictly bounded to 16MB per invocation with a 50ms execution timeout.
2. **Firecracker MicroVMs**: High-compute ETL workflows run inside microVMs spun up in < 5ms with jailer-enforced cgroups and seccomp filters.

---

## 3. Distributed State: In-Memory / Supabase to Redis Cluster

### Current MVP Implementation
To comply with the non-negotiable rule forbidding Redis during the MVP phase, state persistence, caching, and idempotency checks are performed using local memory dictionaries, the deterministic replay cache, and Supabase PostgreSQL tables.

### Production Enterprise Target (v2.0)
In multi-instance cloud deployments (Kubernetes autoscaling pods), a multi-AZ **Redis Cluster** provides:
- **Sliding-Window Rate Limiting**: Distributed token-bucket rate limiters guarding public endpoints (`/api/v1/events/sale`, `/api/v1/copilot/query`).
- **Distributed Locks (Redlock)**: Eliminates race conditions during concurrent stock reservation across multi-stockist allocations.
- **Cross-Pod SSE Pub/Sub**: Redis Pub/Sub backplane syncing Server-Sent Events across heterogeneous backend replicas.

---

## 4. Production Containerization & Cloud Infrastructure (Conceptual)

While Docker is strictly forbidden in MVP code, the following production container topology is designed for cloud staging:

```yaml
# Conceptual Production Reference (Post-MVP v2.0)
version: "3.9"
services:
  mediflux-api:
    image: mediflux/backend:2.0.0
    deploy:
      replicas: 4
    environment:
      - DATABASE_URL=postgresql://mediflux:${DB_PASS}@pgpool:5432/mediflux
      - KAFKA_BROKERS=redpanda:9092
      - REDIS_URL=redis://redis-cluster:6379
      - LLM_ROUTER_MODE=sovereign_first
    depends_on:
      - redpanda
      - redis-cluster

  redpanda:
    image: vectorized/redpanda:v24.1.1
    ports:
      - "9092:9092"

  redis-cluster:
    image: redis:7.2-alpine
    command: redis-server --appendonly yes
```

---

## 5. Sovereign Llama-3.3-70B Deployment on Indian Cloud Infrastructure

### Data Sovereignty Mandate
Under the **Digital Personal Data Protection (DPDP) Act 2023** and **National Health Authority (ABDM)** standards, all sensitive healthcare data—patient identifiers, doctor prescription records, and critical drug stockpiles—must reside within Indian sovereign territory.

### Target Infrastructure Architecture
- **Cloud Providers**: MeitY-empanelled Indian data centers (Yotta NM1 Navi Mumbai, E2E Networks Noida, Netweb Technologies).
- **Inference Runtime**: High-throughput **vLLM** engine with PagedAttention or NVIDIA **TensorRT-LLM** hosted on 4x NVIDIA H100 80GB SXM5 GPUs.
- **Model**: Fine-tuned quantized `meta-llama/Llama-3.3-70B-Instruct-AWQ` trained on:
  - CDSCO Drugs and Cosmetics Act & Schedules (C, G, H, H1, X).
  - Indian Pharmacopoeia (IP) formulation standards.
  - National List of Essential Medicines (NLEM 2022).
  - DPCO ceiling price notifications.

---

## 6. Full-Stack Observability & OpenTelemetry Instrumentation

```mermaid
flowchart TD
    API["FastAPI Endpoints"] -->|OTel Tracing| OTelCollector["OpenTelemetry Collector"]
    Agents["LangGraph Agents"] -->|Span Context| OTelCollector
    EventBus["Event Ingestion"] -->|Latency Metrics| OTelCollector

    OTelCollector --> Prometheus["Prometheus (Time-Series Metrics)"]
    OTelCollector --> Jaeger["Jaeger / Tempo (Distributed Spans)"]
    OTelCollector --> Loki["Loki (Structured JSON Logs)"]

    Prometheus --> Grafana["Unified Grafana Supply Chain NOC Dashboard"]
    Jaeger --> Grafana
    Loki --> Grafana
```

---

## 7. Honest MVP vs. Production Disclosure Matrix

To ensure absolute transparency regarding the MVP implementation scope versus future enterprise integrations:

| Subsystem | MVP Implementation (Verified Today) | Production Target (Post-MVP v2.0) |
|---|---|---|
| **Doctor Registry Verification** | In-process Supabase table (`doctor_registry`) seeded with 10 representative MCI/NMC credentials | Live API integration with the National Medical Commission (NMC) Doctor Verification Portal |
| **IoT Cold-Chain Telemetry** | Mathematical Arrhenius degradation simulation engine (`/api/v1/coldchain/simulate`) | Ingestion of hardware MQTT/CoAP payloads from BLE temperature loggers & GPS truck telematics |
| **B2B Financial Settlement** | Idempotent ledger transactions and simulated credit limit checks (`credit_accounts` table) | Open Banking API / NPCI BBPS / e-RUPI integration for automated instant stockist invoice settlement |
| **CDSCO Gazette Notifications** | Structured JSON ingestion with AST staging mutation (`/api/v1/regulatory/notifications`) | Automated daily web scraper crawling `cdsco.gov.in` and `egazette.gov.in` with OCR PDF parser |
| **LLM Provider Stack** | Hybrid multi-provider (NVIDIA NIM free + OpenRouter free + Local Ollama fallback + Deterministic Replay) | Dedicated self-hosted Llama-3.3-70B cluster inside a MeitY-certified Indian Tier-IV data center |
| **Messaging & Queuing** | Async In-Process EventBus with Supabase event table fallback | Distributed Redpanda / Kafka cluster with multi-partition consumer groups |
| **Dynamic Module Guard** | Python AST static inspection prohibiting banned builtins and system calls | WebAssembly (Wasmtime) sandbox isolation with hardware memory limits |
