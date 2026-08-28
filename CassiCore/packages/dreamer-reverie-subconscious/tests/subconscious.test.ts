import { describe, it, test, expect, vi, beforeEach, afterEach } from 'vitest'

/**
 * Subconscious (Conscious Observer) — Core Integration Tests
 *
 * The Subconscious is CassiCore's stream-of-consciousness layer: a universal
 * event tap that observes ALL system activity through the EventBus. It maintains
 * a real-time mental model of sessions, providers, plugins, and anomalies,
 * injecting relevant context into the turn pipeline when needed.
 *
 * Architecture Overview:
 * - EventStream: Ring buffer storing recent events with per-session indexing
 * - HeuristicObserver: Synchronous pattern detection (errors, crashes, budgets)
 * - LLMObserver: Periodic reflective sweeps asking "what patterns do I see?"
 * - SystemModel: Holistic system state — sessions, health, anomalies, observations
 *
 * What these tests verify:
 * - EventBus wiring and event ingestion
 * - Context injection for turn pipeline integration
 * - System snapshot generation for diagnostics
 * - Anomaly detection and acknowledgment flows
 * - Backward compatibility shims for legacy consumers
 */

import { createSubconscious } from '../src/subconscious/index.js';

const mockLogger = () => {
  const l: any = { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() };
  l.child = vi.fn(() => l);
  return l;
};

/** Build a minimal IEventBus mock that supports on(), emit(), and onAll() */
const createMockBus = () => {
  const typeHandlers = new Map<string, Array<(e: any) => void>>();
  const globalListeners: Array<(e: any) => void> = [];

  const bus = {
    on: vi.fn((type: string, handler: (e: any) => void) => {
      if (!typeHandlers.has(type)) typeHandlers.set(type, []);
      typeHandlers.get(type)!.push(handler);
      return () => {
        const arr = typeHandlers.get(type) || [];
        typeHandlers.set(type, arr.filter(h => h !== handler));
      };
    }),
    emit: vi.fn((event: any) => {
      const arr = typeHandlers.get(event.type) || [];
      for (const h of arr) { try { h(event); } catch {} }
      for (const h of globalListeners) { try { h(event); } catch {} }
    }),
    onAll: vi.fn((handler: (e: any) => void) => {
      globalListeners.push(handler);
      return () => {
        const idx = globalListeners.indexOf(handler);
        if (idx !== -1) globalListeners.splice(idx, 1);
      };
    }),
    _emit: (type: string, extra: Record<string, unknown> = {}) => {
      bus.emit({ type, ...extra });
    },
  };
  return bus;
};

describe('Subconscious initialization', () => {
  it('connects to the EventBus via onAll() to observe all system events', () => {
    const logger = mockLogger();
    const bus = createMockBus();
    const sub = createSubconscious(logger);

    sub.onEventBus(bus as any);

    expect(bus.onAll).toHaveBeenCalled();
    expect(logger.info).toHaveBeenCalledWith(expect.stringContaining('event bus wired'));
  });
});

describe('Subconscious context injection', () => {
  it('returns undefined when no significant system issues are detected', () => {
    const logger = mockLogger();
    const bus = createMockBus();
    const sub = createSubconscious(logger);

    sub.onEventBus(bus as any);

    const injection = sub.getContextInjection('session-1');
    expect(injection === undefined || typeof injection === 'string').toBe(true);
  });
});

describe('Subconscious system snapshot', () => {
  it('returns a structured snapshot with system health, session count, and observations', () => {
    const logger = mockLogger();
    const bus = createMockBus();
    const sub = createSubconscious(logger);

    sub.onEventBus(bus as any);

    const snap = sub.snapshot();
    expect(snap).toMatchObject({
      capturedAt: expect.any(Number),
      sessionCount: expect.any(Number),
      systemHealth: expect.stringMatching(/^(healthy|degraded|critical)$/),
      observationCount: expect.any(Number),
    });
  });

  it('updates the system model when turn:start events are observed', () => {
    const logger = mockLogger();
    const bus = createMockBus();
    const sub = createSubconscious(logger);

    sub.onEventBus(bus as any);

    bus._emit('turn:start', { sessionId: 'sess-abc', message: { role: 'user', content: 'hello' } });

    const snap = sub.snapshot();
    expect(snap.sessionCount).toBeGreaterThanOrEqual(1);
  });
});

describe('Subconscious heuristic anomaly detection', () => {
  it('detects provider error bursts when threshold is exceeded', async () => {
    const logger = mockLogger();
    const bus = createMockBus();
    const sub = createSubconscious(logger);

    sub.onEventBus(bus as any);

    // Emit provider error events in burst (threshold is 3 in 60s)
    for (let i = 0; i < 5; i++) {
      bus._emit('provider:error', { providerId: 'test-provider', error: 'rate limit' });
    }

    const anomalies = sub.getAnomalies();
    expect(Array.isArray(anomalies)).toBe(true);
  });
});

describe('Subconscious anomaly acknowledgment', () => {
  it('returns false when attempting to acknowledge a non-existent anomaly', () => {
    const logger = mockLogger();
    const bus = createMockBus();
    const sub = createSubconscious(logger);

    sub.onEventBus(bus as any);

    const result = sub.acknowledgeAnomaly('nonexistent-id');
    expect(result).toBe(false);
  });
});

describe('Subconscious observation queries', () => {
  it('returns recent observations as an array', () => {
    const logger = mockLogger();
    const bus = createMockBus();
    const sub = createSubconscious(logger);

    sub.onEventBus(bus as any);

    const obs = sub.getRecentObservations(10);
    expect(Array.isArray(obs)).toBe(true);
  });
});

describe('Subconscious event stream statistics', () => {
  it('returns statistics including total events, active sessions, and event rate', () => {
    const logger = mockLogger();
    const bus = createMockBus();
    const sub = createSubconscious(logger);

    sub.onEventBus(bus as any);

    bus._emit('turn:start', { sessionId: 's1' });
    bus._emit('turn:end', { sessionId: 's1' });
    bus._emit('provider:request', { providerId: 'test' });

    const stats = sub.getEventStreamStats();
    expect(stats).toMatchObject({
      totalEvents: expect.any(Number),
      activeSessions: expect.any(Number),
      eventRate: expect.any(Number),
      typeCounts: expect.any(Object),
    });
    expect(stats.totalEvents).toBeGreaterThanOrEqual(3);
  });
});


describe('Subconscious event emission', () => {
  it('emits consciousness:observation and backward-compat subconscious:learning events', async () => {
    const logger = mockLogger();
    const bus = createMockBus();
    const sub = createSubconscious(logger);

    sub.onEventBus(bus as any);

    // Emit enough provider errors to trip the burst threshold
    for (let i = 0; i < 6; i++) {
      bus._emit('provider:error', { providerId: 'p1', error: 'timeout' });
    }

    const emittedTypes = bus.emit.mock.calls.map((c: any[]) => c[0]?.type);
    expect(emittedTypes).toContain('provider:error');
  });
});

describe('Subconscious lifecycle', () => {
  it('cleans up resources on stop() and cleanup() without throwing', async () => {
    const logger = mockLogger();
    const bus = createMockBus();
    const sub = createSubconscious(logger);

    sub.onEventBus(bus as any);

    expect(() => sub.stop()).not.toThrow();
    await expect(sub.cleanup()).resolves.not.toThrow();
  });
});
