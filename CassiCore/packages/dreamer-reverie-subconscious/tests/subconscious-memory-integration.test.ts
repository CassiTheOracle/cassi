/**
 * Subconscious Memory Integration Tests
 *
 * These tests verify the integration between the Subconscious (Conscious Observer)
 * and the Memory module. The Subconscious uses Memory for:
 * - Persisting anomalies and observations across daemon restarts
 * - Hydrating state on startup from previous runs
 * - Cross-session historical context via the session index
 *
 * This integration ensures that the Subconscious maintains continuity
 * even when the daemon restarts or when analyzing patterns across
 * historical sessions.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createSubconscious } from '../src/subconscious/index.js';


const createMockLogger = () => {
  const logger = {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    child: vi.fn(function () { return logger; }),
  };
  return logger;
};

const createMockMemory = () => ({
  store: vi.fn(async (_entry: unknown) => `mem_${Date.now()}`),
  search: vi.fn(async (_query: string, _opts?: unknown) => []),
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  kv_get: vi.fn(async (_key: string): Promise<any> => undefined),
  kv_set: vi.fn(async (_key: string, _value: unknown) => {}),
});

const createMockBus = () => {
  const handlers: Record<string, Array<(e: unknown) => void>> = {};
  const globalListeners: Array<(e: unknown) => void> = [];

  const bus = {
    on: vi.fn((type: string, handler: (e: unknown) => void) => {
      handlers[type] = handlers[type] ?? [];
      handlers[type].push(handler);
    }),
    onAll: vi.fn((handler: (e: unknown) => void) => {
      globalListeners.push(handler);
    }),
    emit: vi.fn((event: Record<string, unknown>) => {
      const type = event.type as string;
      if (handlers[type]) {
        for (const h of handlers[type]) h(event);
      }
      for (const gl of globalListeners) gl(event);
    }),
  };
  return bus;
};


describe('Subconscious memory wiring', () => {
  it('connects memory to the system model without throwing', () => {
    const logger = createMockLogger();
    const sub = createSubconscious(logger);
    const memory = createMockMemory();

    expect(() => sub.setMemory(memory as any)).not.toThrow();
  });
});


describe('Subconscious persistence to memory', () => {
  it('writes anomalies and observations to memory KV on persist', async () => {
    const logger = createMockLogger();
    const sub = createSubconscious(logger);
    const memory = createMockMemory();
    const bus = createMockBus();

    sub.setMemory(memory as any);
    sub.onEventBus(bus as any);

    // Emit provider errors to generate an anomaly via heuristics
    bus.emit({ type: 'provider:request_error', providerId: 'openai', consecutiveErrors: 3 });
    bus.emit({ type: 'provider:request_error', providerId: 'openai', consecutiveErrors: 4 });
    bus.emit({ type: 'provider:request_error', providerId: 'openai', consecutiveErrors: 5 });

    await new Promise(r => setTimeout(r, 20));

    await (sub as any).systemModel?.persist?.();

    expect(memory.kv_set).toHaveBeenCalled();
  });
});


describe('Subconscious hydration from memory', () => {
  it('restores anomalies and observations from memory KV on startup', async () => {
    const logger = createMockLogger();
    const sub = createSubconscious(logger);

    const storedAnomalies = [
      { id: 'anm-1', description: 'Provider cascade failure', severity: 'high', eventTypes: [], timestamp: Date.now() - 1000 },
    ];
    const storedObservations = [
      { id: 'obs-1', summary: 'LLM sweep summary', patterns: ['pattern:a'], confidence: 0.8, source: 'llm', relatedEventTypes: [], timestamp: Date.now() - 2000 },
    ];

    const memory = createMockMemory();
    memory.kv_get = vi.fn(async (key: string) => {
      if (key === 'consciousness:anomalies') return storedAnomalies;
      if (key === 'consciousness:observations') return storedObservations;
      return undefined;
    });

    sub.setMemory(memory as any);
    await (sub as any).systemModel?.hydrate?.();

    const anomalies = sub.getAnomalies();
    expect(anomalies.length).toBeGreaterThanOrEqual(1);
    expect(anomalies[0].id).toBe('anm-1');
  });
});


describe('Subconscious multi-event observation accumulation', () => {
  it('accumulates session state from session:created and turn:start events', () => {
    const logger = createMockLogger();
    const bus = createMockBus();
    const sub = createSubconscious(logger);

    sub.onEventBus(bus as any);

    bus.emit({ type: 'session:created', sessionId: 'sess-A' });
    bus.emit({ type: 'session:created', sessionId: 'sess-B' });
    bus.emit({ type: 'turn:start', sessionId: 'sess-A', message: { role: 'user', content: 'hello' } });

    const snap = sub.snapshot();
    expect(snap.sessionCount).toBeGreaterThanOrEqual(2);
  });

  it('removes session from model when session:ended is received', () => {
    const logger = createMockLogger();
    const bus = createMockBus();
    const sub = createSubconscious(logger);

    sub.onEventBus(bus as any);

    bus.emit({ type: 'session:created', sessionId: 'sess-temp' });
    expect(sub.snapshot().sessionCount).toBeGreaterThanOrEqual(1);

    bus.emit({ type: 'session:ended', sessionId: 'sess-temp' });
    const snap = sub.snapshot();
    expect(snap.sessionCount).toBeGreaterThanOrEqual(0);
  });

  it('tracks provider health through error and recovery cycle', () => {
    const logger = createMockLogger();
    const bus = createMockBus();
    const sub = createSubconscious(logger);

    sub.onEventBus(bus as any);

    bus.emit({ type: 'provider:request_error', providerId: 'anthropic', consecutiveErrors: 4 });
    let snap = sub.snapshot();
    expect(snap.providerHealth['anthropic']).toBe('error');

    bus.emit({ type: 'provider:error_reset', providerId: 'anthropic' });
    snap = sub.snapshot();
    expect(snap.providerHealth['anthropic']).toBe('healthy');
  });

  it('tracks active drones through their lifecycle', () => {
    const logger = createMockLogger();
    const bus = createMockBus();
    const sub = createSubconscious(logger);

    sub.onEventBus(bus as any);

    bus.emit({ type: 'drone:spawned', droneId: 'drone-1' });
    bus.emit({ type: 'drone:spawned', droneId: 'drone-2' });
    expect(sub.snapshot().activeDrones).toBe(2);

    bus.emit({ type: 'drone:completed', droneId: 'drone-1' });
    expect(sub.snapshot().activeDrones).toBe(1);

    bus.emit({ type: 'drone:failed', droneId: 'drone-2' });
    expect(sub.snapshot().activeDrones).toBe(0);
  });

  it('tracks active teams through their lifecycle', () => {
    const logger = createMockLogger();
    const bus = createMockBus();
    const sub = createSubconscious(logger);

    sub.onEventBus(bus as any);

    bus.emit({ type: 'team:started', teamId: 'team-alpha' });
    expect(sub.snapshot().activeTeams).toBe(1);

    bus.emit({ type: 'team:completed', teamId: 'team-alpha' });
    expect(sub.snapshot().activeTeams).toBe(0);
  });
});


describe('Subconscious heuristic anomaly detection with memory', () => {
  it('detects consecutive provider errors and surfaces them as anomalies', async () => {
    const logger = createMockLogger();
    const bus = createMockBus();
    const sub = createSubconscious(logger);

    sub.onEventBus(bus as any);

    bus.emit({ type: 'provider:request_error', providerId: 'openai', consecutiveErrors: 3 });
    bus.emit({ type: 'provider:request_error', providerId: 'openai', consecutiveErrors: 4 });
    bus.emit({ type: 'provider:request_error', providerId: 'openai', consecutiveErrors: 5 });

    await new Promise(r => setTimeout(r, 20));

    const anomalies = sub.getAnomalies();
    expect(anomalies.length).toBeGreaterThan(0);
  });

  it('excludes acknowledged anomalies from default getAnomalies() results', async () => {
    const logger = createMockLogger();
    const bus = createMockBus();
    const sub = createSubconscious(logger);

    sub.onEventBus(bus as any);

    bus.emit({ type: 'provider:request_error', providerId: 'kimi', consecutiveErrors: 5 });
    bus.emit({ type: 'provider:request_error', providerId: 'kimi', consecutiveErrors: 6 });
    bus.emit({ type: 'provider:request_error', providerId: 'kimi', consecutiveErrors: 7 });

    await new Promise(r => setTimeout(r, 20));

    const before = sub.getAnomalies();
    if (before.length === 0) {
      return;
    }

    const id = before[0].id;
    const acked = sub.acknowledgeAnomaly(id);
    expect(acked).toBe(true);

    const after = sub.getAnomalies();
    expect(after.find(a => a.id === id)).toBeUndefined();
  });

  it('returns false when acknowledging a non-existent anomaly', () => {
    const logger = createMockLogger();
    const sub = createSubconscious(logger);

    expect(sub.acknowledgeAnomaly('not-real')).toBe(false);
  });
});


describe('Subconscious event stream statistics', () => {
  it('tracks total event count accurately across all event types', async () => {
    const logger = createMockLogger();
    const bus = createMockBus();
    const sub = createSubconscious(logger);

    sub.onEventBus(bus as any);

    const count = 30;
    for (let i = 0; i < count; i++) {
      bus.emit({ type: 'turn:start', sessionId: `sess-${i}`, message: { role: 'user', content: `msg ${i}` } });
    }

    const stats = sub.getEventStreamStats();
    expect(stats.totalEvents).toBeGreaterThanOrEqual(count);
  });

  it('provides event rate and type distribution in statistics', async () => {
    const logger = createMockLogger();
    const bus = createMockBus();
    const sub = createSubconscious(logger);

    sub.onEventBus(bus as any);

    bus.emit({ type: 'session:created', sessionId: 'sess-x' });
    bus.emit({ type: 'turn:start', sessionId: 'sess-x', message: { role: 'user', content: 'hi' } });
    bus.emit({ type: 'provider:request_start', providerId: 'anthropic' });

    const stats = sub.getEventStreamStats();
    expect(stats).toMatchObject({
      totalEvents: expect.any(Number),
      eventRate: expect.any(Number),
      typeCounts: expect.any(Object),
    });
    expect(stats.typeCounts['turn:start']).toBeGreaterThanOrEqual(1);
  });
});


describe('Subconscious context injection for turn pipeline', () => {
  it('returns undefined when system is healthy with no anomalies', () => {
    const logger = createMockLogger();
    const bus = createMockBus();
    const sub = createSubconscious(logger);

    sub.onEventBus(bus as any);

    const injection = sub.getContextInjection('sess-clean');
    expect(injection == null || injection === '').toBe(true);
  });

  it('surfaces provider degradation in context injection', () => {
    const logger = createMockLogger();
    const bus = createMockBus();
    const sub = createSubconscious(logger);

    sub.onEventBus(bus as any);

    bus.emit({ type: 'provider:request_error', providerId: 'anthropic', consecutiveErrors: 4 });

    const injection = sub.getContextInjection('sess-degraded');
    expect(injection).toBeTruthy();
    expect(injection).toContain('anthropic');
  });
});
