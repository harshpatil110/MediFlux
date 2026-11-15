import { useState, useEffect, useCallback } from 'react';
import { apiClient } from './client';
import { ApiError } from '@mediflux/shared';

export interface QueryState<T> {
  data: T | null;
  loading: boolean;
  error: ApiError | null;
  refetch: () => Promise<void>;
}

export function useApiQuery<T>(
  path: string,
  params?: Record<string, any>,
  enabled: boolean = true
): QueryState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(enabled);
  const [error, setError] = useState<ApiError | null>(null);

  const fetcher = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const result = await apiClient.get<T>(path, params);
      setData(result);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err);
      } else {
        setError(new ApiError('QUERY_ERROR', (err as Error)?.message || 'Query failed', 0));
      }
    } finally {
      setLoading(false);
    }
  }, [path, JSON.stringify(params), enabled]);

  useEffect(() => {
    fetcher();
  }, [fetcher]);

  return { data, loading, error, refetch: fetcher };
}

export function useApiMutation<TReq, TResp>(
  mutationFn: (variables: TReq) => Promise<TResp>
) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const mutate = async (variables: TReq): Promise<TResp> => {
    setLoading(true);
    setError(null);
    try {
      return await mutationFn(variables);
    } catch (err: unknown) {
      const apiErr =
        err instanceof ApiError
          ? err
          : new ApiError('MUTATION_ERROR', (err as Error)?.message || 'Action failed', 0);
      setError(apiErr);
      throw apiErr;
    } finally {
      setLoading(false);
    }
  };

  return { mutate, loading, error };
}

// Domain-specific query hooks
export function useNodes() {
  return useApiQuery<Array<{ id: string; name: string; tier: string; city: string; state: string }>>(
    '/api/v1/nodes'
  );
}

export function useProducts() {
  return useApiQuery<Array<{ id: string; name: string; sku: string; schedule: string }>>(
    '/api/v1/products'
  );
}

export function useInventory(nodeId?: string) {
  return useApiQuery<Array<any>>(
    nodeId ? `/api/v1/inventory/node/${nodeId}` : '/api/v1/inventory',
    undefined,
    Boolean(nodeId)
  );
}

export function usePendingHitlTasks() {
  return useApiQuery<Array<any>>('/api/v1/hitl?status=pending');
}

export function useColdChainBatches() {
  return useApiQuery<Array<any>>('/api/v1/coldchain/batches');
}
