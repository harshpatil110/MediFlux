import { apiClient } from '../api/client';
import { ApiError } from '../api/generated';

function generateClientEventId(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

class SaleSubmissionController {
  public pendingEventId: string;
  public isDispensing: boolean = false;
  public lastError: string | null = null;
  public lastTrace: any = null;

  constructor() {
    this.pendingEventId = generateClientEventId();
  }

  public async submitSale(saleData: {
    productId: string;
    batchNumber: string;
    quantity: number;
    nodeId: string;
  }): Promise<any> {
    if (this.isDispensing) {
      // Guard against double-tap while already in flight
      return null;
    }

    this.isDispensing = true;
    this.lastError = null;

    const eventIdToSend = this.pendingEventId;

    try {
      const response = await apiClient.post('/api/v1/events/sale', {
        event_id: eventIdToSend,
        product_id: saleData.productId,
        batch_number: saleData.batchNumber,
        quantity: saleData.quantity,
        node_id: saleData.nodeId,
        channel: 'mobile_pos',
      });

      this.lastTrace = response;
      // On success: generate new UUID for next transaction
      this.pendingEventId = generateClientEventId();
      return response;
    } catch (err: any) {
      this.lastError = err.message || 'Dispense failed';
      // ON ERROR / RETRY: Do NOT generate new UUID, preserve current pendingEventId
      throw err;
    } finally {
      this.isDispensing = false;
    }
  }

  public resetForNextSale() {
    this.lastError = null;
    this.lastTrace = null;
    this.pendingEventId = generateClientEventId();
  }
}

describe('POS Sale Idempotency & Mid-Flow Drop Recovery', () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    jest.clearAllMocks();
  });

  test('generates valid RFC4122 v4 UUID client-side before submission', () => {
    const uuid = generateClientEventId();
    expect(uuid).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
    );
  });

  test('re-uses identical event_id when retrying after network drop', async () => {
    const controller = new SaleSubmissionController();
    const initialEventId = controller.pendingEventId;
    expect(initialEventId).toBeTruthy();

    const salePayload = {
      productId: 'prod-paracetamol-650',
      batchNumber: 'BATCH-2026-PAR-01',
      quantity: 1,
      nodeId: 'node-pharmacy-001',
    };

    const sentEventIds: string[] = [];

    // 1. First attempt: simulate mid-flow network drop
    global.fetch = jest.fn().mockImplementation((_url, init) => {
      const body = JSON.parse(init?.body as string);
      sentEventIds.push(body.event_id);
      return Promise.reject(new Error('Network request failed'));
    });

    try {
      await controller.submitSale(salePayload);
      fail('Expected network error');
    } catch (err: any) {
      expect(err).toBeInstanceOf(ApiError);
      expect(err.code).toBe('NETWORK_ERROR');
    }

    // Verify controller preserved identical event ID on failure
    expect(controller.pendingEventId).toBe(initialEventId);
    expect(sentEventIds).toEqual([initialEventId]);

    // 2. Second attempt (retry): connection restored, backend returns idempotent response
    global.fetch = jest.fn().mockImplementation((_url, init) => {
      const body = JSON.parse(init?.body as string);
      sentEventIds.push(body.event_id);
      return Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({
          status: 'success',
          idempotent_replay: true,
          correlation_id: 'corr-idempotent-sale-123',
          cascade_trace: {
            correlation_id: 'corr-idempotent-sale-123',
            status: 'completed',
          },
        }),
      } as unknown as Response);
    });

    const successResult = await controller.submitSale(salePayload);

    // Assert that the exact same event_id was sent on retry
    expect(sentEventIds[0]).toBe(sentEventIds[1]);
    expect(successResult.idempotent_replay).toBe(true);
    expect(successResult.correlation_id).toBe('corr-idempotent-sale-123');

    // Assert that upon success, a new unique event_id is generated for the next sale
    expect(controller.pendingEventId).not.toBe(initialEventId);
  });

  test('double-tap guard blocks secondary submission while in flight', async () => {
    const controller = new SaleSubmissionController();
    let callCount = 0;

    global.fetch = jest.fn().mockImplementation(async () => {
      callCount++;
      await new Promise((r) => setTimeout(r, 50));
      return {
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ status: 'success' }),
      } as unknown as Response;
    });

    const salePayload = {
      productId: 'prod-001',
      batchNumber: 'BATCH-001',
      quantity: 1,
      nodeId: 'node-001',
    };

    // First tap starts flight
    const p1 = controller.submitSale(salePayload);
    // Second rapid tap while isDispensing is true
    const p2 = controller.submitSale(salePayload);

    const [res1, res2] = await Promise.all([p1, p2]);

    expect(callCount).toBe(1);
    expect(res1).toEqual({ status: 'success' });
    expect(res2).toBeNull();
  });
});

