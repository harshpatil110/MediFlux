# Task 19 Specification: Prescription and Schedule H Compliance Graph

## 1. Overview & Objective

Task 19 implements the **Sovereign Prescription and Schedule H Compliance Graph** for MediFlux (RFP Phase 4). The system enforces sovereign local-only processing (`sensitivity="sensitive"`), ensuring that protected health information (PHI) and prescription scans never egress to external hosted cloud providers.

The pipeline:
1. Parses clinical prescription scans using local sovereign multimodal and OCR extraction pipelines.
2. Redacts patient names to privacy-compliant initials (e.g. `R.K.`, `H.P.`) before persistence.
3. Classifies prescribed medications against CDSCO schedules (OTC, Schedule H, H1, X) using deterministic reference registries without hallucinating or guessing.
4. Verifies prescribing physician credentials and active registration against the national doctor registry.
5. Evaluates regulatory compliance:
   - Missing doctor registration number $\rightarrow$ `rejected` / `flagged`.
   - Unregistered or unknown doctor $\rightarrow$ `flagged` with Human-in-the-Loop task (`prescription_doctor_verification`).
   - Unlisted or experimental medication $\rightarrow$ `flagged` with Human-in-the-Loop task (`prescription_unknown_drug`).
   - Valid verified doctor and classified drugs $\rightarrow$ `approved` (`approve_dispense`).
6. Persists records to `public.prescriptions`, generates itemized compliance logs in `public.compliance_logs`, and appends immutable cryptographic records to `public.audit_ledger`.
7. Seamlessly integrates with Task 11 Pharmacy Agent's `check_prescription_link` to unlock retail dispensing and replenishment for verified Schedule H prescriptions while enforcing strict compliance holds on unverified sales.

---

## 2. Core Architecture & Workflow

```
[Prescription Scan: Multipart Upload / Image Bytes / JSON]
                           │
                           ▼
             ┌───────────────────────────┐
             │ prescription_parser_node  │ Local Sovereign multimodal / OCR
             └─────────────┬─────────────┘ sensitivity="sensitive" (Zero Cloud)
                           │ Extracts: doctor_name, doctor_reg_no,
                           │           patient_initials (redacted), drugs
                           ▼
             ┌───────────────────────────┐
             │  schedule_compliance_node │ Evaluates each drug against CDSCO schedules
             └─────────────┬─────────────┘ Tool: lookup_schedule(drug_name)
                           │ (NEVER guesses: unlisted returns "unknown")
                           ▼
             ┌───────────────────────────┐
             │ doctor_verification_node  │ Checks license against doctor_registry
             └─────────────┬─────────────┘ Tool: verify_doctor(reg_no, doc_name)
                           │ Returns: verified (bool) + structured reason
                           ▼
             ┌───────────────────────────┐
             │       decision_node       │ Evaluates compliance outcome
             └─────────────┬─────────────┘
                           │
        ┌──────────────────┼──────────────────┐
  [Missing Reg No]  [Unknown Doctor]    [Unlisted Drug]   [All Verified & Classified]
        │                  │                  │                         │
        ▼                  ▼                  ▼                         ▼
   ┌──────────┐     ┌──────────────┐   ┌──────────────┐         ┌───────────────┐
   │  REJECT  │     │ FLAG -> HITL │   │ FLAG -> HITL │         │    APPROVE    │
   │ (reject) │     │ (doc_verify) │   │(unknown_drug)│         │(approve_disp) │
   └────┬─────┘     └──────┬───────┘   └──────┬───────┘         └───────┬───────┘
        │                  │                  │                         │
        └──────────────────┴─────────┬────────┴─────────────────────────┘
                                     │
                                     ▼
                      ┌─────────────────────────────┐
                      │    1. public.prescriptions  │
                      │    2. public.compliance_logs│
                      │    3. public.audit_ledger   │
                      └─────────────────────────────┘
                                     │
                                     ▼
                      ┌─────────────────────────────┐
                      │ Task 11 Pharmacy Integration│
                      │   (check_prescription_link) │
                      └─────────────────────────────┘
```

---

## 3. Reference Data & Fixtures

### 3.1 Synthetic Prescription Scan Fixtures (`fixtures/prescriptions/`)
Generated using Pillow with high-contrast clinical layouts and embedded PNG `tEXt` chunks for deterministic testing:
1. `valid_prescription.png`: Dr. A. K. Sharma (`MCI-2019-88412`), patient `R.K.`, Paracetamol 500mg (OTC) $\rightarrow$ `status="approved"`.
2. `missing_reg_no.png`: Dr. Ramesh Gupta (`Reg No: NONE`), patient `S.M.`, Amoxicillin 500mg $\rightarrow$ `status="rejected"`.
3. `unknown_doctor.png`: Dr. Vikram Ghost (`FAKE-9999-00000`), patient `A.P.`, Azithromycin 500mg $\rightarrow$ `status="flagged"` (`prescription_doctor_verification`).
4. `schedule_h_prescription.png`: Dr. A. K. Sharma (`MCI-2019-88412`), patient `H.P.`, Amoxicillin 500mg (Schedule H) $\rightarrow$ `status="approved"`.
5. `unlisted_drug.png`: Dr. A. K. Sharma (`MCI-2019-88412`), patient `N.D.`, Xenorab-ZX 999mg $\rightarrow$ `status="flagged"` (`prescription_unknown_drug`).

---

## 4. API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/prescriptions` | Ingests prescription scan via multipart form or JSON body. Executes Sovereign Prescription Graph and returns structured decision, parsed drugs, doctor verification status, and audit identifiers. |
| `GET` | `/api/v1/prescriptions/{id}` | Retrieves full prescription record, schedule classifications, and decision by ID. Returns 404 if not found. |
| `GET` | `/api/v1/compliance/logs` | Retrieves filtered compliance log entries (supports filtering by `prescription_id`, `action`, `node_id`, `limit`). |

---

## 5. Security & Sovereign Privacy Guardrails

- **Zero Cloud Leakage**: `sensitivity="sensitive"` is strictly enforced across all LLM requests in the prescription graph. The LLM router blocks external cloud providers (`openai`, `anthropic`, `gemini`, `groq`), raising `SensitiveDataRoutingError` on attempts to bypass local routing.
- **Patient Privacy Redaction**: Full patient names are automatically parsed and redacted to privacy initials (e.g. `R.K.`, `H.P.`) before database insertion.
- **Cryptographic Audit Ledger**: Every evaluated prescription writes a SHA-256 hash-chained entry to `public.audit_ledger`.
- **Architectural Rules (AGENTS.md)**: Zero Redis, Zero Docker, Zero WASM, Zero Kafka. Uses Supabase relational tables (`prescriptions`, `compliance_logs`, `doctor_registry`, `drug_schedules`, `hitl_tasks`, `audit_ledger`) with in-memory fallbacks for offline test isolation.
