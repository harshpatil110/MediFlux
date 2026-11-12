# Task 8 Specification: Generated Module Registry and Restricted Execution Guard

## 1. Overview & Objective
Task 8 establishes the "zero-code base" foundation for MediFlux: dynamic business rules (margin calculations, volume discounts, credit checks, price ceilings, and adapters) live as versioned, auditable Python source code in the database rather than hardcoded server logic.
The runtime guarantees safety via:
1. **Static AST Analysis** (`ASTGuard`): Strict whitelisting of safe modules and blocking of hazardous built-ins/attributes.
2. **Subprocess Isolation** (`SubprocessRunner`): Execution inside isolated, non-persistent subprocesses with cleaned environments, standard I/O pipes, and a hard 2.0-second timeout.
3. **Atomic Hot-Swapping and Rollback** (`ModuleRegistry`): Activation of new versions and rolling back without restarting the server.
4. **Agent Integration & Bootstrap Policies**: Ingestion and validation of bootstrap rules (`margin_rules`, `volume_discount`, `credit_check_rules`, `price_ceiling`) and seamless execution via `run_module` agent tool.

---

## 2. Key Components

### 2.1 Module Contract (`app/modules_runtime/contract.py`)
- Standardized execution signature: `def run(input: dict) -> dict`.
- Standardized test signature: `def test_run()`.
- Valid module kinds: `margin_rules`, `volume_discount`, `credit_check_rules`, `price_ceiling`, `traceability_rules`, `adapter`.
- Status lifecycle: `draft` -> `tested` -> `active` -> `retired` / `failed`.

### 2.2 Restricted Execution Guard (`app/modules_runtime/guard.py`)
- **ASTGuard**:
  - Whitelist: `json`, `math`, `datetime`, `decimal`, `re`, `typing`, `statistics`.
  - Blocklist: `os`, `sys`, `subprocess`, `socket`, `shutil`, `importlib`, `pathlib`, `builtins`, `http`, `urllib`, `requests`.
  - Blocked built-ins: `open`, `eval`, `exec`, `compile`, `__import__`, `globals`, `locals`, `getattr`, `setattr`, `delattr`, `input`.
  - Blocked dunders: `__subclasses__`, `__class__`, `__globals__`, `__bases__`, `__mro__`, `__builtins__`, `__code__`, `__import__`.
- **SubprocessRunner**:
  - Isolated execution via `sys.executable -c <payload>`.
  - Stripped environment (no API keys, no Supabase credentials leaked).
  - Cross-platform 2.0s execution timeout (avoiding platform-specific `resource.setrlimit`).
  - Max 1 MB output cap.

### 2.3 Module Registry (`app/modules_runtime/registry.py`)
- `create_version(name, kind, code_source, tests_source, created_by)`: Calculates SHA-256 hash, runs static AST verification, stores version in database or in-memory fallback.
- `run_tests(version_id)`: Runs `test_run()` in an isolated subprocess runner.
- `activate(version_id)`: Ensures tests pass, atomicity transitions active versions to retired, marks target as active, updates in-memory cache.
- `rollback(name)`: Reverts active module to its most recent previously active version without downtime.
- `run_module(name, input_data)`: Runs currently active module in isolated subprocess.

### 2.4 Bootstrap Policies & Agent (`app/agents/bootstrap_agent.py`)
- Configured from `config/bootstrap_policies.md`:
  - `margin_rules`: Base 12%, volume discount, generic boost, credit rating adjustments, max 30%.
  - `volume_discount`: Slab tiers (100 -> 3%, 500 -> 5%, 1000 -> 8%, 5000 -> 12%).
  - `credit_check_rules`: Approved/blocked thresholds based on credit score, overdue balance, and credit limit.
  - `price_ceiling`: DPCO compliance checks, ensuring price <= ceiling price.

### 2.5 Admin API Endpoints (`app/api/v1/endpoints/modules.py`)
- `GET /api/v1/modules`: List active versions for all modules.
- `GET /api/v1/modules/{name}/versions`: List version history for a module.
- `POST /api/v1/modules/{name}/rollback`: Roll back active module to previous active version.

---

## 3. Verification & Test Coverage
- **AST Security Tests**: Verifies rejection of `os`, `sys`, `subprocess`, `socket`, `open()`, `eval()`, `exec()`, `__class__.__subclasses__()`, and dunder string indices `input['__globals__']`.
- **Subprocess Timeout Protection**: Verifies that infinite loops (`while True: pass`) trigger `ModuleTimeoutError` within 2 seconds without hanging the worker.
- **Atomic Hot-Swap & Rollback**: Verifies version creation, test running, activation, and instantaneous rollback.
- **Bootstrap Verification**: Ingests, tests, and activates all 4 core business rule modules.
- **API Endpoint Tests**: Verifies listing, version inspection, and rollback over HTTP.
