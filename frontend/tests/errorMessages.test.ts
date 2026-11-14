/**
 * Comprehensive verification of error message normalizer (Task 29 / Milestone 4).
 * Tests all required error classifications and returned metadata.
 */

import assert from "node:assert";
import { normalizeErrorMessage, normalizeLlmError, ERROR_CATALOG } from "../src/lib/errorMessages.ts";

function runTests() {
  console.log("Running errorMessages.ts test suite...");

  // 1. Rate Limit 429
  {
    const res1 = normalizeErrorMessage({ status: 429, message: "Rate limit exceeded" });
    assert.strictEqual(res1.code, "PROVIDER_RATE_LIMITED_429");
    assert.strictEqual(res1.suggestedVariant, "warning");
    assert.strictEqual(res1.isRecoverable, true);

    const res2 = normalizeErrorMessage("Error 429: Too Many Requests from NVIDIA NIM");
    assert.strictEqual(res2.code, "PROVIDER_RATE_LIMITED_429");
  }

  // 2. Sovereign Local Model Offline (HTTP 503 / SovereignLLMOfflineError)
  {
    const res1 = normalizeErrorMessage({
      status: 503,
      code: "SOVEREIGN_LOCAL_MODEL_OFFLINE",
      detail: "SovereignLLMOfflineError: Local Ollama is offline for sensitive analysis",
    });
    assert.strictEqual(res1.code, "SOVEREIGN_LOCAL_MODEL_OFFLINE");
    assert.strictEqual(res1.suggestedVariant, "sovereign");
    assert.strictEqual(res1.isRecoverable, false);
    assert.ok(res1.message.includes("Ollama"));
    assert.ok(res1.message.includes("CDSCO privacy"));

    const res2 = normalizeErrorMessage("SovereignLLMOfflineError: Local Ollama offline");
    assert.strictEqual(res2.code, "SOVEREIGN_LOCAL_MODEL_OFFLINE");

    const res3 = normalizeErrorMessage({ detail: "Ollama provider is not registered" });
    assert.strictEqual(res3.code, "SOVEREIGN_LOCAL_MODEL_OFFLINE");
  }

  // 3. Generic Provider Outages (500 / 502 / 503 non-sovereign)
  {
    const res502 = normalizeErrorMessage({ status: 502, message: "Bad Gateway" });
    assert.strictEqual(res502.code, "PROVIDER_OUTAGE_5XX");
    assert.strictEqual(res502.suggestedVariant, "error");

    const res503 = normalizeErrorMessage({ status: 503, message: "Service Unavailable" });
    assert.strictEqual(res503.code, "PROVIDER_OUTAGE_5XX");

    const res500 = normalizeErrorMessage({ status: 500, message: "Upstream provider NIM returned 500 Internal Error" });
    assert.strictEqual(res500.code, "PROVIDER_OUTAGE_5XX");
  }

  // 4. Malformed JSON / Parse Failures
  {
    const res1 = normalizeErrorMessage({ message: "JSONDecodeError: Expecting property name enclosed in double quotes" });
    assert.strictEqual(res1.code, "LLM_INVALID_JSON_OUTPUT");
    assert.strictEqual(res1.severity, "info");
    assert.strictEqual(res1.isRecoverable, true);

    const res2 = normalizeErrorMessage({ detail: "LLMStructuredOutputError: Malformed JSON with unbalanced brackets" });
    assert.strictEqual(res2.code, "LLM_INVALID_JSON_OUTPUT");
  }

  // 5. Network / Disconnects
  {
    const res1 = normalizeErrorMessage({ message: "Failed to fetch" });
    assert.strictEqual(res1.code, "NETWORK_DISCONNECTED");
    assert.strictEqual(res1.isRecoverable, true);

    const res2 = normalizeErrorMessage(new Error("connect ECONNREFUSED 127.0.0.1:8000"));
    assert.strictEqual(res2.code, "NETWORK_DISCONNECTED");
  }

  // 6. HITL Task Expired (HTTP 409)
  {
    const res = normalizeErrorMessage({ status: 409, message: "HITL task has expired past statutory deadline" });
    assert.strictEqual(res.code, "HITL_TASK_EXPIRED");
    assert.strictEqual(res.isRecoverable, false);
  }

  // 7. Partial Cascade Failure
  {
    const res = normalizeErrorMessage({ message: "Cascade execution ended with status partial_failure" });
    assert.strictEqual(res.code, "PARTIAL_CASCADE_FAILURE");
    assert.strictEqual(res.isRecoverable, true);
  }

  // 8. Alias normalizeLlmError
  {
    const res = normalizeLlmError({ status: 429 });
    assert.strictEqual(res.code, "PROVIDER_RATE_LIMITED_429");
  }

  console.log("All 8 error normalizer test scenarios passed successfully!");
}

runTests();
