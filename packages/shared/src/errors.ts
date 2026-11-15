/**
 * MediFlux / NexusChain Standard Error Contracts.
 */

export interface StandardErrorDetail {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface StandardErrorPayload {
  error: StandardErrorDetail;
  detail?: string | Array<{ loc?: Array<string | number>; msg: string; type?: string }>;
}

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details?: Record<string, unknown>;

  constructor(code: string, message: string, status: number = 400, details?: Record<string, unknown>) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.details = details;
    Object.setPrototypeOf(this, ApiError.prototype);
  }

  static fromPayload(payload: unknown, status: number = 400): ApiError {
    if (typeof payload === 'object' && payload !== null) {
      const obj = payload as Record<string, any>;
      if (obj.error && typeof obj.error === 'object') {
        return new ApiError(
          obj.error.code || 'API_ERROR',
          obj.error.message || 'An API error occurred',
          status,
          obj.error.details
        );
      }
      if (typeof obj.detail === 'string') {
        return new ApiError('HTTP_ERROR', obj.detail, status);
      }
      if (Array.isArray(obj.detail) && obj.detail.length > 0) {
        const first = obj.detail[0];
        const msg = typeof first === 'object' && first?.msg ? first.msg : JSON.stringify(obj.detail);
        return new ApiError('VALIDATION_ERROR', msg, status, { errors: obj.detail });
      }
      if (obj.message) {
        return new ApiError('ERROR', String(obj.message), status);
      }
    }
    return new ApiError('UNKNOWN_ERROR', 'An unexpected error occurred', status);
  }
}

