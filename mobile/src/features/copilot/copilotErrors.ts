/**
 * Friendly Copilot & LLM error mapping and recovery (Task M8.3).
 */

export interface FormattedCopilotError {
  title: string;
  message: string;
  retryable: boolean;
  code: string;
}

export function formatCopilotError(error: unknown): FormattedCopilotError {
  if (!error) {
    return {
      title: 'Unexpected Error',
      message: 'An unknown error occurred while processing your request. Please try again.',
      retryable: true,
      code: 'UNKNOWN',
    };
  }

  // Check structured backend error payload
  const errObj = error as Record<string, any>;
  const nestedError = errObj.error || errObj.response?.data?.error || errObj.data?.error || {};
  const status = errObj.status || errObj.response?.status || nestedError.status;
  const rawCode = String(nestedError.code || errObj.code || '').toUpperCase();
  const rawMsg = String(nestedError.message || errObj.message || '').toLowerCase();

  // 1. Rate-limiting / Provider busy (429)
  if (
    status === 429 ||
    rawCode.includes('429') ||
    rawCode.includes('RATE_LIMIT') ||
    rawCode.includes('LLM_PROVIDER_BUSY') ||
    rawCode.includes('BUSY') ||
    rawMsg.includes('429') ||
    rawMsg.includes('rate limit') ||
    rawMsg.includes('busy')
  ) {
    return {
      title: 'AI Assistant Busy',
      message: 'The AI model provider is experiencing high demand right now. Tap Retry to run your question again.',
      retryable: true,
      code: 'LLM_PROVIDER_BUSY',
    };
  }

  // 2. Sovereign Local Model Offline (503)
  if (
    status === 503 ||
    rawCode.includes('SOVEREIGN_LOCAL_MODEL_OFFLINE') ||
    rawCode.includes('MODEL_OFFLINE') ||
    rawMsg.includes('sovereign') ||
    rawMsg.includes('model offline')
  ) {
    return {
      title: 'Local Sovereign Model Offline',
      message: 'The local on-premise AI service is unreachable. Sensitive queries remain protected and were not sent to external clouds.',
      retryable: true,
      code: 'SOVEREIGN_LOCAL_MODEL_OFFLINE',
    };
  }

  // 3. Node RLS Scope restriction (403)
  if (
    status === 403 ||
    rawCode.includes('FORBIDDEN') ||
    rawCode.includes('COPILOT_FORBIDDEN_SCOPE') ||
    rawMsg.includes('forbidden') ||
    rawMsg.includes('scope') ||
    rawMsg.includes('restricted by node policy')
  ) {
    return {
      title: 'Restricted by Node Policy',
      message: 'Your role only permits querying records within your assigned supply-chain node.',
      retryable: false,
      code: 'COPILOT_FORBIDDEN_SCOPE',
    };
  }

  // 4. Network offline / timeout
  if (
    rawCode === 'ECONNABORTED' ||
    rawCode === 'ENOTFOUND' ||
    rawMsg.includes('timeout') ||
    rawMsg.includes('network') ||
    rawMsg.includes('failed to fetch') ||
    rawMsg.includes('connection')
  ) {
    return {
      title: 'Connection Interrupted',
      message: 'Could not reach the MediFlux backend. Check your connection and tap Retry.',
      retryable: true,
      code: 'NETWORK_TIMEOUT',
    };
  }

  // Generic fallback
  return {
    title: 'Assistant Temporarily Unavailable',
    message: nestedError.message || errObj.message || 'Unable to complete copilot query. Please tap Retry to try again.',
    retryable: true,
    code: rawCode || 'COPILOT_TEMPORARY_FAILURE',
  };
}
