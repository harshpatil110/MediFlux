import { getBackendUrl } from '../lib/config';
import { storage } from '../lib/storage';
import { ApiError } from './generated';

export interface RequestOptions {
  headers?: Record<string, string>;
  timeoutMs?: number;
  skipAuth?: boolean;
  _retried401?: boolean;
}

export interface AuthContext {
  token?: string | null;
  role?: string | null;
  nodeId?: string | null;
  userId?: string | null;
}

export type RefreshHandler = () => Promise<string | null>;
export type ForceLogoutHandler = (reason?: string) => Promise<void> | void;

class ApiClient {
  private authContext: AuthContext = {};
  private defaultTimeoutMs: number = 15000;
  private onRefresh: RefreshHandler | null = null;
  private onForceLogout: ForceLogoutHandler | null = null;
  private isRefreshing: boolean = false;
  private refreshSubscribers: Array<(token: string | null) => void> = [];

  constructor() {
    this.restoreSession();
  }

  public setAuthHandlers(handlers: {
    onRefresh?: RefreshHandler;
    onForceLogout?: ForceLogoutHandler;
  }): void {
    if (handlers.onRefresh) this.onRefresh = handlers.onRefresh;
    if (handlers.onForceLogout) this.onForceLogout = handlers.onForceLogout;
  }

  public async restoreSession(): Promise<AuthContext> {
    try {
      const token = await storage.getItem('mediflux_auth_token');
      const role = await storage.getItem('mediflux_auth_role');
      const nodeId = await storage.getItem('mediflux_auth_node_id');
      const userId = await storage.getItem('mediflux_auth_user_id');

      this.authContext = {
        token,
        role,
        nodeId,
        userId,
      };
      return this.authContext;
    } catch {
      return this.authContext;
    }
  }

  public setAuth(context: Partial<AuthContext>): void {
    this.authContext = { ...this.authContext, ...context };
    if (context.token !== undefined) {
      if (context.token) storage.setItem('mediflux_auth_token', context.token);
      else storage.removeItem('mediflux_auth_token');
    }
    if (context.role !== undefined) {
      if (context.role) storage.setItem('mediflux_auth_role', context.role);
      else storage.removeItem('mediflux_auth_role');
    }
    if (context.nodeId !== undefined) {
      if (context.nodeId) storage.setItem('mediflux_auth_node_id', context.nodeId);
      else storage.removeItem('mediflux_auth_node_id');
    }
    if (context.userId !== undefined) {
      if (context.userId) storage.setItem('mediflux_auth_user_id', context.userId);
      else storage.removeItem('mediflux_auth_user_id');
    }
  }

  public clearAuth(): void {
    this.authContext = {};
    storage.removeItem('mediflux_auth_token');
    storage.removeItem('mediflux_auth_role');
    storage.removeItem('mediflux_auth_node_id');
    storage.removeItem('mediflux_auth_user_id');
  }

  public getAuth(): AuthContext {
    return { ...this.authContext };
  }

  private buildHeaders(options?: RequestOptions): Record<string, string> {
    const headers: Record<string, string> = {
      Accept: 'application/json',
      ...(options?.headers || {}),
    };

    if (!options?.skipAuth && this.authContext.token) {
      headers['Authorization'] = `Bearer ${this.authContext.token}`;
    }

    if (this.authContext.role) {
      headers['X-User-Role'] = this.authContext.role;
    }
    if (this.authContext.nodeId) {
      headers['X-Node-Id'] = this.authContext.nodeId;
    }
    if (this.authContext.userId) {
      headers['X-User-Id'] = this.authContext.userId;
    }

    return headers;
  }

  private buildUrl(path: string, params?: Record<string, any>): string {
    const baseUrl = getBackendUrl().replace(/\/+$/, '');
    const cleanPath = path.startsWith('/') ? path : `/${path}`;
    const url = new URL(`${baseUrl}${cleanPath}`);

    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, String(value));
        }
      });
    }

    return url.toString();
  }

  private async handleTokenRefresh(): Promise<string | null> {
    if (this.isRefreshing) {
      return new Promise<string | null>((resolve) => {
        this.refreshSubscribers.push(resolve);
      });
    }

    this.isRefreshing = true;
    try {
      if (!this.onRefresh) {
        return null;
      }
      const newToken = await this.onRefresh();
      if (newToken) {
        this.authContext.token = newToken;
        storage.setItem('mediflux_auth_token', newToken);
      }
      this.refreshSubscribers.forEach((cb) => cb(newToken));
      return newToken;
    } catch {
      this.refreshSubscribers.forEach((cb) => cb(null));
      return null;
    } finally {
      this.isRefreshing = false;
      this.refreshSubscribers = [];
    }
  }

  private async execute<T>(
    method: string,
    path: string,
    body?: any,
    params?: Record<string, any>,
    options?: RequestOptions
  ): Promise<T> {
    const fullUrl = this.buildUrl(path, params);
    const headers = this.buildHeaders(options);

    if (body && !(body instanceof FormData) && typeof body === 'object') {
      headers['Content-Type'] = 'application/json';
    }

    const timeout = options?.timeoutMs || this.defaultTimeoutMs;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);

    try {
      const response = await fetch(fullUrl, {
        method,
        headers,
        body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      clearTimeout(timer);

      // Handle 401 Unauthorized with single retry
      const isAuthRoute = path.includes('/auth/login') || path.includes('/auth/refresh');
      if (response.status === 401 && !options?._retried401 && !isAuthRoute && this.onRefresh) {
        const refreshedToken = await this.handleTokenRefresh();
        if (refreshedToken) {
          const retryOptions: RequestOptions = {
            ...options,
            _retried401: true,
          };
          return this.execute<T>(method, path, body, params, retryOptions);
        } else if (this.onForceLogout) {
          this.onForceLogout('Session expired. Please sign in again.');
        }
      }

      // Handle 204 No Content
      if (response.status === 204) {
        return undefined as unknown as T;
      }

      let data: any = null;
      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        data = await response.json();
      } else {
        data = await response.text();
      }

      if (!response.ok) {
        throw ApiError.fromPayload(data, response.status);
      }

      return data as T;
    } catch (err: unknown) {
      clearTimeout(timer);
      if (err instanceof ApiError) {
        throw err;
      }
      if (err instanceof Error && err.name === 'AbortError') {
        throw new ApiError('REQUEST_TIMEOUT', `Request timed out after ${timeout}ms`, 408);
      }
      throw new ApiError(
        'NETWORK_ERROR',
        err instanceof Error ? err.message : 'Network request failed',
        0
      );
    }
  }

  public async get<T>(
    path: string,
    params?: Record<string, any>,
    options?: RequestOptions
  ): Promise<T> {
    return this.execute<T>('GET', path, undefined, params, options);
  }

  public async post<T>(path: string, body?: any, options?: RequestOptions): Promise<T> {
    return this.execute<T>('POST', path, body, undefined, options);
  }

  public async put<T>(path: string, body?: any, options?: RequestOptions): Promise<T> {
    return this.execute<T>('PUT', path, body, undefined, options);
  }

  public async delete<T>(
    path: string,
    params?: Record<string, any>,
    options?: RequestOptions
  ): Promise<T> {
    return this.execute<T>('DELETE', path, undefined, params, options);
  }

  public async uploadMultipart<T>(
    path: string,
    formData: FormData,
    options?: RequestOptions
  ): Promise<T> {
    const customOptions: RequestOptions = {
      ...options,
      headers: { ...(options?.headers || {}) },
    };
    return this.execute<T>('POST', path, formData, undefined, customOptions);
  }
}

export const apiClient = new ApiClient();
