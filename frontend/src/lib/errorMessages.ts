/**
 * Standardized Domain Error Message Normalizer (Task 29).
 * Translates backend domain codes, HTTP statuses, and network exceptions
 * into clear, actionable editorial messages conforming to design.md.
 */

export interface NormalizedError {
  code: string;
  title: string;
  message: string;
  actionableHint?: string;
  isRecoverable: boolean;
  severity: "info" | "warning" | "error" | "critical";
}

const ERROR_CATALOG: Record<string, NormalizedError> = {
  PROVIDER_RATE_LIMITED_429: {
    code: "PROVIDER_RATE_LIMITED_429",
    title: "Free-Tier Providers Rate-Limited",
    message: "Upstream LLM providers (NVIDIA NIM / OpenRouter) hit rate limits. Automatic fallback chain is active.",
    actionableHint: "The router will automatically switch to local Ollama or replay cache in under 100ms.",
    isRecoverable: true,
    severity: "warning",
  },
  LLM_INVALID_JSON_OUTPUT: {
    code: "LLM_INVALID_JSON_OUTPUT",
    title: "Malformed Model Output Repaired",
    message: "The model returned unquoted keys or unbalanced brackets. Resilient AST repair reconstructed valid JSON.",
    actionableHint: "No operator intervention required; schema validation passed after auto-repair.",
    isRecoverable: true,
    severity: "info",
  },
  SOVEREIGN_LOCAL_MODEL_OFFLINE: {
    code: "SOVEREIGN_LOCAL_MODEL_OFFLINE",
    title: "Sovereign Local Model Offline",
    message: "Local Ollama service is unreachable for sensitive prescription analysis. Hosted cloud fallback is strictly prohibited by CDSCO privacy mandate.",
    actionableHint: "Start local Ollama with 'ollama serve' or enable Demo Replay mode to proceed offline.",
    isRecoverable: false,
    severity: "critical",
  },
  HITL_TASK_EXPIRED: {
    code: "HITL_TASK_EXPIRED",
    title: "Approval Task Expired",
    message: "This Human-in-the-Loop task exceeded its statutory timeout window and can no longer be approved.",
    actionableHint: "A new order or regulatory notification must be submitted to trigger a fresh review task.",
    isRecoverable: false,
    severity: "warning",
  },
  PARTIAL_CASCADE_FAILURE: {
    code: "PARTIAL_CASCADE_FAILURE",
    title: "Partial Supply Chain Propagation",
    message: "A downstream tier encountered an issue. Upstream pharmacy inventory was deducted and escalated to HITL.",
    actionableHint: "Review the open task in Approvals Inbox (/approvals) to resolve the stalled tier.",
    isRecoverable: true,
    severity: "warning",
  },
  NETWORK_OFFLINE: {
    code: "NETWORK_OFFLINE",
    title: "Offline Replay Mode Active",
    message: "MediFlux is operating detached from cloud database endpoints. Local in-memory and replay cache active.",
    actionableHint: "All core single-unit cascade, prescription, and cold-chain flows function deterministically.",
    isRecoverable: true,
    severity: "info",
  },
};

export function normalizeErrorMessage(err: unknown): NormalizedError {
  if (!err) {
    return {
      code: "UNKNOWN_ERROR",
      title: "Unexpected Error",
      message: "An unknown system event occurred.",
      isRecoverable: true,
      severity: "error",
    };
  }

  const errObj = err as any;
  const status = errObj.status || errObj.statusCode || errObj.response?.status;
  const rawCode = (
    errObj.code ||
    errObj.error_code ||
    errObj.response?.data?.code ||
    errObj.response?.data?.error?.code ||
    ""
  ).toUpperCase();
  const rawDetail = (
    errObj.detail ||
    errObj.message ||
    errObj.response?.data?.detail ||
    errObj.response?.data?.message ||
    ""
  ).toString();

  // Match exact catalog code
  if (rawCode && ERROR_CATALOG[rawCode]) {
    return ERROR_CATALOG[rawCode];
  }

  // Substring inspections
  if (rawDetail.includes("SovereignLLMOfflineError") || rawDetail.includes("SOVEREIGN_LOCAL_MODEL_OFFLINE") || rawDetail.includes("Ollama provider is not registered")) {
    return ERROR_CATALOG.SOVEREIGN_LOCAL_MODEL_OFFLINE;
  }

  if (status === 429 || rawDetail.includes("rate limit") || rawDetail.includes("429")) {
    return ERROR_CATALOG.PROVIDER_RATE_LIMITED_429;
  }

  if (status === 409 && (rawDetail.includes("expired") || rawDetail.includes("timeout"))) {
    return ERROR_CATALOG.HITL_TASK_EXPIRED;
  }

  if (rawDetail.includes("partial_failure") || rawDetail.includes("partial cascade")) {
    return ERROR_CATALOG.PARTIAL_CASCADE_FAILURE;
  }

  if (rawDetail.includes("Failed to fetch") || rawDetail.includes("NetworkError") || rawDetail.includes("ECONNREFUSED")) {
    return ERROR_CATALOG.NETWORK_OFFLINE;
  }

  if (rawDetail.includes("JSONDecodeError") || rawDetail.includes("LLMStructuredOutputError")) {
    return ERROR_CATALOG.LLM_INVALID_JSON_OUTPUT;
  }

  // Generic fallback
  return {
    code: rawCode || (status ? `HTTP_${status}` : "SYSTEM_ERROR"),
    title: status ? `Service Notice (${status})` : "System Notice",
    message: rawDetail || "The requested operation could not be completed.",
    isRecoverable: status !== 403 && status !== 401,
    severity: status >= 500 ? "error" : "warning",
  };
}

export const normalizeLlmError = normalizeErrorMessage;
