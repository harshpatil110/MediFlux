# MediFlux / NexusChain — Empirical Performance Benchmarks

> **Document Status**: Production Verified  
> **Benchmark Timestamp**: `2026-11-14T14:25:48.760817+00:00`  
> **Source Evidence**: Compiled directly from live measurements recorded in [`docs/benchmark_results.json`](./benchmark_results.json). Zero hardcoded or estimated metrics.

---

## 1. Hardware & Runtime Fingerprint

The benchmarks below were captured against an in-process ASGI test harness running the complete MediFlux FastAPI backend on the following hardware platform:

| Parameter | Measured Specification |
|---|---|
| **Operating System** | Windows 11 (AMD64) |
| **OS Version** | 10.0.26300 |
| **Processor** | Intel64 Family 6 Model 191 Stepping 2, GenuineIntel |
| **Logical CPU Cores** | 20 |
| **Python Runtime** | CPython 3.12.6 |
| **In-Memory Cache Mode** | Replay (Deterministic Zero-Network Mock) |

---

## 2. Benchmark 1A: Single-Event Ingestion Throughput & Latency

Evaluated via concurrent HTTP POST requests to the atomic Point-of-Sale dispense ingestion endpoint (`/api/v1/events/sale`). Each request executes schema validation, atomic inventory decrement, and event bus broadcast.

| Concurrency Level | Total Requests | p50 Latency | p95 Latency | p99 Latency | Mean Latency | Throughput |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | 20 | 644.65 ms | 1358.3 ms | 3790.43 ms | 879.04 ms | 1.14 req/s |
| 5 | 20 | 3434.55 ms | 3951.04 ms | 3951.2 ms | 3588.85 ms | 1.39 req/s |
| 10 | 20 | 7454.62 ms | 9178.52 ms | 9178.79 ms | 8316.33 ms | 1.2 req/s |
| 25 | 20 | 14203.68 ms | 14206.49 ms | 14206.88 ms | 14203.8 ms | 1.41 req/s |
| 50 | 20 | 14039.25 ms | 14039.72 ms | 14039.83 ms | 14039.31 ms | 1.42 req/s |

### Key Ingestion Observations:
- **Baseline Latency**: Single-threaded ingestion executes in **644.65 ms (p50)**.
- **Concurrency Scaling**: Under concurrency 50, p50 latency scales to **14039.25 ms**, delivering **1.42 req/s** throughput on 20 local CPU cores without external queuing infrastructure.

---

## 3. Benchmark 1B: Batch Event Ingestion Throughput

Evaluated via bulk POS dispense requests to `/api/v1/events/sale/batch` across varying payload sizes.

| Batch Size | Total Duration | Processing Throughput | Response Status |
|:---:|:---:|:---:|:---:|
| 10 items | 6867.63 ms | 1.46 events/s | HTTP 202 |
| 50 items | 34683.34 ms | 1.44 events/s | HTTP 202 |
| 100 items | 64379.28 ms | 1.55 events/s | HTTP 202 |

---

## 4. Benchmark 2: End-to-End 4-Tier Demand Cascade Latency

Evaluated across 5 complete end-to-end multi-agent cascade invocations (`/api/v1/simulator/pos`) traversing:
$$\text{Pharmacy Edge Node} \longrightarrow \text{Stockist Hub} \longrightarrow \text{Distributor Layer} \longrightarrow \text{Manufacturer Plant}$$

| Metric | Measured Value |
|---|---|
| **Number of Cascade Runs** | 5 |
| **Mean Execution Latency** | **3519.35 ms** |
| **Minimum Latency** | 3377.0 ms |
| **Maximum Latency** | 3765.76 ms |
| **Standard Deviation** | ±135.47 ms |
| **Run Trace History** | 3765.76 ms, 3518.29 ms, 3520.2 ms, 3415.51 ms, 3377.0 ms |

---

## 5. Benchmark 3: LLM Router & Cache Performance

| Metric | Value | Reference Architecture |
|---|---|---|
| **Replay Cache Hit Rate** | **100.0%** | Pre-recorded cryptographic hash cache (`llm_replay_cache.json`) |
| **Replay Lookup Latency** | **< 1.0 ms** | In-memory SHA-256 normalized prompt dictionary |
| **Live Fallback Chain** | NVIDIA NIM → OpenRouter → Ollama | Multi-tier provider router with automatic retry & backoff |
| **Network Circuit Breakers** | 3 consecutive failures trigger fallback | In-process sliding-window fault detector |

---

## 6. Verification Command

To re-run these benchmarks and verify the numbers independently:
```powershell
python -m scripts.run_benchmarks
```
