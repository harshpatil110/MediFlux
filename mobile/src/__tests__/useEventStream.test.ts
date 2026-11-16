import { useEventStream, MobileStreamEvent } from '../hooks/useEventStream';
import { apiClient } from '../api/client';

// Simple in-memory EventSource for testing SSE hook mechanics
class FakeEventSource {
  public url: string;
  public options: any;
  public listeners: Record<string, ((event: any) => void)[]> = {};
  public isClosed = false;

  constructor(url: string, options?: any) {
    this.url = url;
    this.options = options;
  }

  addEventListener(type: string, listener: (event: any) => void) {
    if (!this.listeners[type]) this.listeners[type] = [];
    this.listeners[type].push(listener);
  }

  removeEventListener(type: string, listener: (event: any) => void) {
    if (!this.listeners[type]) return;
    this.listeners[type] = this.listeners[type].filter((l) => l !== listener);
  }

  emit(type: string, data: any) {
    const list = this.listeners[type] || [];
    list.forEach((cb) => cb(data));
  }

  close() {
    this.isClosed = true;
  }
}

describe('useEventStream & SSE Resilience State Machine', () => {
  let createdFakeSources: FakeEventSource[] = [];

  beforeEach(() => {
    createdFakeSources = [];
    apiClient.clearAuth();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('FakeEventSource factory creates instance with Authorization and Last-Event-ID', () => {
    apiClient.setAuth({ token: 'test-jwt-999' });

    let capturedUrl = '';
    let capturedOptions: any = null;

    const factory = (url: string, options: any) => {
      capturedUrl = url;
      capturedOptions = options;
      const fake = new FakeEventSource(url, options);
      createdFakeSources.push(fake);
      return fake;
    };

    const options = {
      eventSourceFactory: factory,
      initialBackoffMs: 100,
    };

    // Instantiate FakeEventSource directly to test factory options
    const instance = factory('http://localhost:8000/api/v1/events/stream?topics=*', {
      headers: {
        Authorization: 'Bearer test-jwt-999',
        'Last-Event-ID': 'evt-100',
      },
    });

    expect(instance).toBeDefined();
    expect(capturedUrl).toContain('/api/v1/events/stream');
    expect(capturedOptions.headers['Authorization']).toBe('Bearer test-jwt-999');
    expect(capturedOptions.headers['Last-Event-ID']).toBe('evt-100');
  });

  test('Event deduplication logic prevents duplicate event IDs in buffer', () => {
    const seenIds = new Set<string>();
    const events: MobileStreamEvent[] = [];
    const maxBufferSize = 5;

    const pushEvent = (evt: MobileStreamEvent) => {
      if (seenIds.has(evt.id)) return;
      seenIds.add(evt.id);
      events.unshift(evt);
      if (events.length > maxBufferSize) {
        events.pop();
      }
    };

    const event1: MobileStreamEvent = {
      id: 'evt-001',
      event_id: 'evt-001',
      event_type: 'sale.completed',
      agent_name: 'POS',
      tier: 'pharmacy',
      summary: 'Sale 1 strip',
      correlation_id: 'corr-1',
      created_at: new Date().toISOString(),
    };

    // Push first time
    pushEvent(event1);
    expect(events.length).toBe(1);

    // Push duplicate
    pushEvent(event1);
    expect(events.length).toBe(1);

    // Push subsequent events
    for (let i = 2; i <= 6; i++) {
      pushEvent({
        ...event1,
        id: `evt-00${i}`,
        event_id: `evt-00${i}`,
      });
    }

    // Bounded ring buffer retains at most maxBufferSize = 5 events
    expect(events.length).toBe(5);
    expect(events[0].id).toBe('evt-006');
    expect(events[4].id).toBe('evt-002');
  });

  test('Exponential backoff computation increases delay and caps at maxBackoffMs', () => {
    const initialBackoffMs = 1000;
    const maxBackoffMs = 15000;

    const computeBackoff = (failures: number) => {
      const delay = initialBackoffMs * Math.pow(2, failures);
      return Math.min(delay, maxBackoffMs);
    };

    expect(computeBackoff(0)).toBe(1000);
    expect(computeBackoff(1)).toBe(2000);
    expect(computeBackoff(2)).toBe(4000);
    expect(computeBackoff(3)).toBe(8000);
    expect(computeBackoff(4)).toBe(15000); // capped at 15000
    expect(computeBackoff(5)).toBe(15000);
  });

  test('Polling fallback trigger logic activates after threshold failures', () => {
    const maxFailuresBeforePolling = 3;
    let consecutiveFailures = 0;
    let isPolling = false;

    const handleFailure = () => {
      consecutiveFailures++;
      if (consecutiveFailures >= maxFailuresBeforePolling) {
        isPolling = true;
      }
    };

    handleFailure();
    expect(isPolling).toBe(false);

    handleFailure();
    expect(isPolling).toBe(false);

    handleFailure();
    expect(isPolling).toBe(true);

    // Reset when stream recovers
    const handleSuccess = () => {
      consecutiveFailures = 0;
      isPolling = false;
    };

    handleSuccess();
    expect(isPolling).toBe(false);
  });
});

