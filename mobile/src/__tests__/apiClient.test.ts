import { apiClient } from '../api/client';
import { ApiError } from '../api/generated';

// Save original fetch
const originalFetch = global.fetch;

describe('ApiClient & Request Handling', () => {
  beforeEach(() => {
    apiClient.clearAuth();
    apiClient.setAuthHandlers({});
  });

  afterEach(() => {
    global.fetch = originalFetch;
    jest.clearAllMocks();
  });

  test('attaches Authorization, X-User-Role, X-Node-Id, and X-User-Id headers automatically', async () => {
    apiClient.setAuth({
      token: 'jwt-test-token-123',
      role: 'pharmacy',
      nodeId: 'node-pharmacy-001',
      userId: 'user-pharma-001',
    });

    let capturedHeaders: Record<string, string> = {};

    global.fetch = jest.fn().mockImplementation((_url, init) => {
      capturedHeaders = init?.headers as Record<string, string>;
      return Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ success: true }),
      } as unknown as Response);
    });

    const result = await apiClient.get<{ success: boolean }>('/api/v1/mobile/summary');

    expect(result.success).toBe(true);
    expect(capturedHeaders['Authorization']).toBe('Bearer jwt-test-token-123');
    expect(capturedHeaders['X-User-Role']).toBe('pharmacy');
    expect(capturedHeaders['X-Node-Id']).toBe('node-pharmacy-001');
    expect(capturedHeaders['X-User-Id']).toBe('user-pharma-001');
  });

  test('parses standard backend error format { error: { code, message, details } } into ApiError instance', async () => {
    const errorPayload = {
      error: {
        code: 'BATCH_QUARANTINED',
        message: 'Batch BATCH-2026-COV-01 is quarantined due to temperature excursion.',
        details: { batch_id: 'BATCH-2026-COV-01', temp_c: 12.4 },
      },
    };

    global.fetch = jest.fn().mockImplementation(() => {
      return Promise.resolve({
        ok: false,
        status: 400,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => errorPayload,
      } as unknown as Response);
    });

    try {
      await apiClient.post('/api/v1/events/sale', { barcode: '8901000000018' });
      fail('Expected ApiError to be thrown');
    } catch (err: any) {
      expect(err).toBeInstanceOf(ApiError);
      expect(err.code).toBe('BATCH_QUARANTINED');
      expect(err.message).toContain('quarantined');
      expect(err.status).toBe(400);
      expect(err.details).toEqual({ batch_id: 'BATCH-2026-COV-01', temp_c: 12.4 });
    }
  });

  test('handles 401 Unauthorized by refreshing token once and retrying request', async () => {
    apiClient.setAuth({ token: 'expired-jwt-token' });

    let callCount = 0;
    const refreshMock = jest.fn().mockResolvedValue('fresh-jwt-token-456');
    const forceLogoutMock = jest.fn();

    apiClient.setAuthHandlers({
      onRefresh: refreshMock,
      onForceLogout: forceLogoutMock,
    });

    global.fetch = jest.fn().mockImplementation((_url, init) => {
      callCount++;
      const headers = init?.headers as Record<string, string>;
      if (headers['Authorization'] === 'Bearer expired-jwt-token') {
        return Promise.resolve({
          ok: false,
          status: 401,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({ error: { code: 'UNAUTHORIZED', message: 'Token expired' } }),
        } as unknown as Response);
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ recovered: true }),
      } as unknown as Response);
    });

    const res = await apiClient.get<{ recovered: boolean }>('/api/v1/me');

    expect(callCount).toBe(2);
    expect(refreshMock).toHaveBeenCalledTimes(1);
    expect(forceLogoutMock).not.toHaveBeenCalled();
    expect(res.recovered).toBe(true);
  });

  test('forces logout if 401 refresh returns null or fails', async () => {
    apiClient.setAuth({ token: 'expired-jwt-token' });

    const refreshMock = jest.fn().mockResolvedValue(null);
    const forceLogoutMock = jest.fn();

    apiClient.setAuthHandlers({
      onRefresh: refreshMock,
      onForceLogout: forceLogoutMock,
    });

    global.fetch = jest.fn().mockImplementation(() => {
      return Promise.resolve({
        ok: false,
        status: 401,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ error: { code: 'UNAUTHORIZED', message: 'Token invalid' } }),
      } as unknown as Response);
    });

    try {
      await apiClient.get('/api/v1/me');
    } catch {
      // Expected to fail after unsuccessful refresh
    }

    expect(refreshMock).toHaveBeenCalledTimes(1);
    expect(forceLogoutMock).toHaveBeenCalledWith('Session expired. Please sign in again.');
  });

  test('translates network disconnect into structured NETWORK_ERROR ApiError without crash', async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error('Network request failed'));

    try {
      await apiClient.get('/api/v1/mobile/summary');
      fail('Expected ApiError to be thrown');
    } catch (err: any) {
      expect(err).toBeInstanceOf(ApiError);
      expect(err.code).toBe('NETWORK_ERROR');
      expect(err.message).toBe('Network request failed');
      expect(err.status).toBe(0);
    }
  });

  test('translates request timeout into REQUEST_TIMEOUT ApiError', async () => {
    const abortErr = new Error('The user aborted a request.');
    abortErr.name = 'AbortError';
    global.fetch = jest.fn().mockRejectedValue(abortErr);

    try {
      await apiClient.get('/api/v1/mobile/summary', {}, { timeoutMs: 50 });
      fail('Expected ApiError to be thrown');
    } catch (err: any) {
      expect(err).toBeInstanceOf(ApiError);
      expect(err.code).toBe('REQUEST_TIMEOUT');
      expect(err.status).toBe(408);
    }
  });
});

