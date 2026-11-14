/**
 * Standardized Domain & LLM Error Message Normalizer (Task 29).
 * Translates backend domain codes, HTTP statuses, and network exceptions
 * into clear, actionable editorial messages conforming to Warm Editorial Minimalism (Design.md).
 */

export interface NormalizedError {
  code: string;
  title: string;
  message: string;
  actionableHint?: string;
  isRecoverable: boolean;
  severity: "info" | "warning" | "error" | "critical";
  suggestedVariant: "warning" | "error" | "sovereign";
}

export const ERROR_CATALOG: Record<string, NormalizedError> = {
  PROVIDER_RATE_LIMITED_429: {
    code: "PROVIDER_RATE_LIMITED_429",
    title: "Upstream Provider Rate Limit",
    message: "Rate limit reached on upstream LLM endpoints. Transparent failover to secondary provider or local cache is active.",
    actionableHint: "The autonomous router will fail over in <100ms or back off. Retry momentarily if needed.",
    isRecoverable: true,
    severity: "warning",
    suggestedVariant: "warning",
  },
  SOVEREIGN_LOCAL_MODEL_OFFLINE: {
    code: "SOVEREIGN_LOCAL_MODEL_OFFLINE",
    title: "Sovereign Local Model Offline",
    message: "Local Ollama service is unreachable for sensitive prescription analysis. External cloud routing is strictly prohibited by CDSCO privacy mandate.",
    actionableHint: "Start local Ollama with 'ollama serve' or enable Demo Replay mode to proceed offline.",
    isRecoverable: false,
    severity: "critical",
    suggestedVariant: "sovereign",
  },
  PROVIDER_OUTAGE_5XX: {
    code: "PROVIDER_OUTAGE_5XX",
    title: "Upstream Provider Service Outage",
    message: "An upstream provider returned a 500, 502, or 503 gateway error. The autonomous fallback router redirected execution.",
    actionableHint: "Verify network status or switch to local Ollama / Demo Replay mode.",
    isRecoverable: true,
    severity: "error",
    suggestedVariant: "error",
  },
  LLM_INVALID_JSON_OUTPUT: {
    code: "LLM_INVALID_JSON_OUTPUT",
    title: "Malformed Model Output Repaired",
    message: "The model returned unquoted keys, unbalanced brackets, or malformed JSON syntax. Resilient AST repair reconstructed valid output.",
    actionableHint: "Autonomous schema correction recovered the data structure. No operator intervention required.",
    isRecoverable: true,
    severity: "info",
    suggestedVariant: "warning",
  },
  NETWORK_DISCONNECTED: {
    code: "NETWORK_DISCONNECTED",
    title: "Network Disconnect Detected",
    message: "Network connection to backend or remote services was lost. MediFlux is operating in detached local mode.",
    actionableHint: "All core single-unit cascade, prescription, and cold-chain flows function deterministically via local cache.",
    isRecoverable: true,
    severity: "warning",
    suggestedVariant: "warning",
  },
  HITL_TASK_EXPIRED: {
    code: "HITL_TASK_EXPIRED",
    title: "Approval Task Expired",
    message: "This Human-in-the-Loop task exceeded its statutory timeout window and can no longer be approved.",
    actionableHint: "A new order or regulatory notification must be submitted to trigger a fresh review task.",
    isRecoverable: false,
    severity: "warning",
    suggestedVariant: "warning",
  },
  PARTIAL_CASCADE_FAILURE: {
    code: "PARTIAL_CASCADE_FAILURE",
    title: "Partial Supply Chain Propagation",
    message: "A downstream tier encountered an issue. Upstream pharmacy inventory was deducted and escalated to HITL.",
    actionableHint: "Review the open task in Approvals Inbox (/approvals) to resolve the stalled tier.",
    isRecoverable: true,
    severity: "warning",
    suggestedVariant: "warning",
  },
};

// Aliases for backwards compatibility
ERROR_CATALOG.NETWORK_OFFLINE = ERROR_CATALOG.NETWORK_DISCONNECTED;

export function normalizeErrorMessage(err: unknown): NormalizedError {
  if (!err) {
    return {
      code: "UNKNOWN_ERROR",
      title: "Unexpected Error",
      message: "An unknown system event occurred.",
      isRecoverable: true,
      severity: "error",
      suggestedVariant: "error",
    };
  }

  const errObj = (typeof err === "object" ? err : {}) as Record<string, any>;
  const status = Number(
    errObj.status ||
    errObj.statusCode ||
    errObj.response?.status ||
    (typeof err === "string" && err.match(/\b(429|500|502|503|504|409)\b/)?.[0]) ||
    0
  );

  const rawCode = (
    errObj.code ||
    errObj.error_code ||
    errObj.response?.data?.code ||
    errObj.response?.data?.error?.code ||
    ""
  ).toString().toUpperCase();

  const rawDetail = (
    errObj.detail ||
    errObj.message ||
    errObj.response?.data?.detail ||
    errObj.response?.data?.message ||
    (typeof err === "string" ? err : "") ||
    ""
  ).toString();

  const rawDetailLower = rawDetail.toLowerCase();

  // 1. Exact catalog code match
  if (rawCode && ERROR_CATALOG[rawCode]) {
    return ERROR_CATALOG[rawCode];
  }

  // 2. Sovereign Local Model Offline (HTTP 503 / SovereignLLMOfflineError)
  // Must precede generic 503 check!
  if (
    rawCode === "SOVEREIGN_LOCAL_MODEL_OFFLINE" ||
    rawDetail.includes("SovereignLLMOfflineError") ||
    rawDetail.includes("SOVEREIGN_LOCAL_MODEL_OFFLINE") ||
    rawDetail.includes("Ollama provider is not registered") ||
    (rawDetailLower.includes("ollama") && (rawDetailLower.includes("offline") || rawDetailLower.includes("unreachable"))) ||
    (status === 503 && (rawDetailLower.includes("sovereign") || rawDetailLower.includes("privacy") || rawDetailLower.includes("ollama")))
  ) {
    return ERROR_CATALOG.SOVEREIGN_LOCAL_MODEL_OFFLINE;
  }

  // 3. Rate Limits (HTTP 429)
  if (
    status === 429 ||
    rawCode.includes("429") ||
    rawDetailLower.includes("rate limit") ||
    rawDetailLower.includes("too many requests") ||
    rawDetail.includes("429")
  ) {
    return ERROR_CATALOG.PROVIDER_RATE_LIMITED_429;
  }

  // 4. HITL Task Expired (HTTP 409)
  if (
    rawCode === "HITL_TASK_EXPIRED" ||
    (status === 409 && (rawDetailLower.includes("expired") || rawDetailLower.includes("timeout")))
  ) {
    return ERROR_CATALOG.HITL_TASK_EXPIRED;
  }

  // 5. Partial Cascade Failure
  if (
    rawCode === "PARTIAL_CASCADE_FAILURE" ||
    rawDetailLower.includes("partial_failure") ||
    rawDetailLower.includes("partial cascade")
  ) {
    return ERROR_CATALOG.PARTIAL_CASCADE_FAILURE;
  }

  // 6. Generic Provider Outages (HTTP 500 / 502 / 503 / 504)
  if (
    rawCode === "PROVIDER_OUTAGE_5XX" ||
    rawCode === "BAD_GATEWAY" ||
    rawCode === "SERVICE_UNAVAILABLE" ||
    status === 502 ||
    status === 503 ||
    status === 504 ||
    (status === 500 && (
      rawDetailLower.includes("provider") ||
      rawDetailLower.includes("upstream") ||
      rawDetailLower.includes("nim") ||
      rawDetailLower.includes("openrouter") ||
      rawDetailLower.includes("bad gateway") ||
      rawDetailLower.includes("gateway")
    ))
  ) {
    return ERROR_CATALOG.PROVIDER_OUTAGE_5XX;
  }

  // 7. Malformed JSON / Parse Failures
  if (
    rawCode === "LLM_INVALID_JSON_OUTPUT" ||
    rawCode === "JSON_PARSE_ERROR" ||
    rawDetail.includes("JSONDecodeError") ||
    rawDetail.includes("LLMStructuredOutputError") ||
    rawDetailLower.includes("malformed json") ||
    rawDetailLower.includes("json parse") ||
    rawDetailLower.includes("unbalanced brackets") ||
    rawDetailLower.includes("unquoted keys") ||
    rawDetail.includes("SyntaxError: Unexpected token")
  ) {
    return ERROR_CATALOG.LLM_INVALID_JSON_OUTPUT;
  }

  // 8. Network / Connection Disconnects
  if (
    rawCode === "NETWORK_OFFLINE" ||
    rawCode === "NETWORK_DISCONNECTED" ||
    rawDetailLower.includes("failed to fetch") ||
    rawDetailLower.includes("networkerror") ||
    rawDetailLower.includes("econnrefused") ||
    rawDetailLower.includes("connect_error") ||
    rawDetailLower.includes("connection refused") ||
    rawDetailLower.includes("network disconnect") ||
    rawDetailLower.includes("network request failed")
  ) {
    return ERROR_CATALOG.NETWORK_DISCONNECTED;
  }

  // 9. Generic Fallback
  const isServer = status >= 500;
  return {
    code: rawCode || (status ? `HTTP_${status}` : "SYSTEM_NOTICE"),
    title: status ? `Service Notice (${status})` : "System Notice",
    message: rawDetail || "The requested operation could not be completed.",
    isRecoverable: status !== 401 && status !== 403,
    severity: isServer ? "error" : "warning",
    suggestedVariant: isServer ? "error" : "warning",
  };
}

export const normalizeLlmError = normalizeErrorMessage;
