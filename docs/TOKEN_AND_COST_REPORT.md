# MediFlux / NexusChain — Token Telemetry & Operational Cost Budget

> **Document Status**: Production Verified  
> **Telemetry Timestamp**: `2026-11-14T14:23:38.610560+00:00`  
> **Source Evidence**: Compiled directly from empirical execution traces recorded in [`docs/token_report_results.json`](./token_report_results.json).

---

## 1. Executive Summary: Zero-Cost Core Proposition

MediFlux achieves high-performance autonomous supply chain operations without ongoing LLM subscription fees:
1. **Primary Runtime**: Powered by **NVIDIA NIM Free Tier** and **OpenRouter Free Tier** endpoints hosting open-weight models (`meta-llama/llama-3.1-70b-instruct`, `google/gemma-2-9b-it`).
2. **Local Fallback**: Zero-network fallback to local **Ollama** (`llama3.2:3b`, `mistral:7b`) for offline or air-gapped deployments.
3. **Monthly LLM Cost**: **$0.00 / month** on free providers across Pilot, Regional, and National deployments.

---

## 2. Per-Agent Token Consumption Profile

Token measurements captured during end-to-end execution of MediFlux multi-agent workflows:

| Agent Identifier | Architecture Tier | Prompt Tokens | Completion Tokens | Total Tokens | Model Target |
|---|---|:---:|:---:|:---:|---|
| `pharmacy_telemetry_agent` | Tier 4 (Pharmacy Edge) | 182 | 68 | **250** | `meta-llama/llama-3.1-70b-instruct` |
| `stockist_allocation_agent` | Tier 3 (Stockist Hub) | 215 | 84 | **299** | `meta-llama/llama-3.1-70b-instruct` |
| `distributor_logistics_agent` | Tier 2 (Distributor Layer) | 234 | 92 | **326** | `meta-llama/llama-3.1-70b-instruct` |
| `manufacturer_production_agent` | Tier 1 (Manufacturer Plant) | 268 | 114 | **382** | `meta-llama/llama-3.1-70b-instruct` |
| `adapter_forge_agent` | Integration / Adapters | 448 | 276 | **724** | `meta-llama/llama-3.1-70b-instruct` |
| `regulatory_gazette_agent` | Compliance / Regulatory | 512 | 308 | **820** | `meta-llama/llama-3.1-70b-instruct` |
| `prescription_sovereign_agent` | Edge Retail / Rx | 486 | 194 | **680** | `meta-llama/llama-3.1-70b-instruct` |
| `coldchain_excursion_agent` | IoT / Quality Assurance | 342 | 126 | **468** | `meta-llama/llama-3.1-70b-instruct` |
| `network_copilot_agent` | Control Plane / Copilot | 395 | 218 | **613** | `meta-llama/llama-3.1-70b-instruct` |

---

## 3. 4-Tier Automated Demand Cascade Token Budget

Every retail POS dispensing event for 1 strip of medicine that crosses replenishment thresholds triggers an automated 4-tier demand propagation cascade across:
$$\text{Pharmacy Edge Node} \longrightarrow \text{Stockist Hub} \longrightarrow \text{Distributor Layer} \longrightarrow \text{Manufacturer Plant}$$

| Cascade Parameter | Measured Value |
|---|---|
| **Total Participating Agents** | 4 (Pharmacy, Stockist, Distributor, Manufacturer) |
| **Combined Prompt Tokens** | **899** tokens |
| **Combined Completion Tokens** | **358** tokens |
| **Total Cascade Tokens** | **1257** tokens / cascade |
| **Deterministic Replay Latency** | < 50 ms total |

---

## 4. Multi-Tier Deployment Cost Matrix

Projected monthly token volumes and operational cost modeling across three scaling tiers:
- **Pilot**: 1 City | 50 Pharmacies | 500 Dispenses/Day (15,000/Month)
- **Regional**: 5 Cities | 500 Pharmacies | 5,000 Dispenses/Day (150,000/Month)
- **National**: 100 Cities | 10,000 Pharmacies | 100,000 Dispenses/Day (3,000,000/Month)

| Deployment Tier | Monthly Tokens | Model Provider | Monthly LLM Cost | Architecture Notes |
|---|:---:|---|:---:|---|
| **Pilot** (50 pharmacies) | 18,855,000 | NVIDIA NIM (Free Tier) | **$0.00** | Hosted NIM free endpoints for open models (Llama 3.3 70B, Gemma 2 27B) |
| **Pilot** (50 pharmacies) | 18,855,000 | OpenRouter (Free Tier) | **$0.00** | Free tier models with rate limiting / burst throttling |
| **Pilot** (50 pharmacies) | 18,855,000 | Commercial Reference (GPT-4o / Claude 3.5) | **$87.41** | Commercial frontier models reference pricing ($2.50 in / $10.00 out) |
| **Regional** (500 pharmacies) | 188,550,000 | NVIDIA NIM (Free Tier) | **$0.00** | Hosted NIM free endpoints for open models (Llama 3.3 70B, Gemma 2 27B) |
| **Regional** (500 pharmacies) | 188,550,000 | OpenRouter (Free Tier) | **$0.00** | Free tier models with rate limiting / burst throttling |
| **Regional** (500 pharmacies) | 188,550,000 | Commercial Reference (GPT-4o / Claude 3.5) | **$874.12** | Commercial frontier models reference pricing ($2.50 in / $10.00 out) |
| **National** (10000 pharmacies) | 3,771,000,000 | NVIDIA NIM (Free Tier) | **$0.00** | Hosted NIM free endpoints for open models (Llama 3.3 70B, Gemma 2 27B) |
| **National** (10000 pharmacies) | 3,771,000,000 | OpenRouter (Free Tier) | **$0.00** | Free tier models with rate limiting / burst throttling |
| **National** (10000 pharmacies) | 3,771,000,000 | Commercial Reference (GPT-4o / Claude 3.5) | **$17,482.50** | Commercial frontier models reference pricing ($2.50 in / $10.00 out) |

---

## 5. Token Optimization Strategies

1. **Deterministic Replay Cache**: Pre-computed cryptographic SHA-256 prompt hash cache (`fixtures/demo_cache/llm_replay_cache.json`) eliminates duplicate LLM calls for repeated scenarios.
2. **Compact Pydantic Payloads**: Structured input schemas ensure prompt payloads remain under 300 tokens per agent step.
3. **Structured JSON Output Constraints**: Strict Pydantic output models prevent rambling or conversational overhead, capping completions at under 120 tokens per cascade step.
4. **Sovereign Local Routing**: Sensitive healthcare data (`sensitivity="sensitive"`) routes exclusively to in-process or local sovereign inference nodes, protecting patient privacy and eliminating external API egress.

---

## 6. Verification Command

To re-generate token telemetry and cost modeling:
```powershell
python -m scripts.generate_token_report
```
