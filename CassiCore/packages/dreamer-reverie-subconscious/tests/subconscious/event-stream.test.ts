/**
 * EventStream — Ring Buffer and Event Ingestion Tests
 *
 * The EventStream is the Subconscious's sensory layer: it connects to the
 * EventBus via onAll() and ingests every event into a fixed-size ring buffer.
 * This provides a sliding window of recent system activity for analysis.
 *
 * Key behaviors tested:
 * - Ring buffer ingestion with chronological ordering preservation
 * - Buffer wrap-around when capacity is exceeded (oldest events dropped)
 * - Per-session indexing for fast session-scoped queries
 * - Binary search for time-based event retrieval (getSince)
 * - Rate tracking and type distribution analysis
 * - Stream summarization for LLM consumption
 */

import { describe, it, expect, vi } from 'vitest';
import { EventStream } from '../../src/subconscious/event-stream.js';
import type { RuntimeEvent } from '@cassicore/foundation';

const mockLogger = () => {
  const l = {
    debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn(),
  };
  return { ...l, child: vi.fn(() => l) };
};

const makeEvent = (type: string, extras: Record<string, unknown> = {}): RuntimeEvent =>
  ({ type, ...extras } as unknown as RuntimeEvent);

const makeBus = () => {
  const listeners: Array<(e: RuntimeEvent) => void> = [];
  return {
    onAll: vi.fn((h: (e: RuntimeEvent) => void) => {
      listeners.push(h);
      return () => listeners.splice(listeners.indexOf(h), 1);
    }),
    emit: (e: RuntimeEvent) => listeners.forEach(h => h(e)),
  };
};

describe('EventStream ring buffer ingestion', () => {
  it('stores events in chronological order (oldest to newest)', () => {
    const stream = new EventStream(mockLogger() as any);
    const bus = makeBus();
    stream.connect(bus as any);

    bus.emit(makeEvent('turn:start', { sessionId: 'a' }));
    bus.emit(makeEvent('turn:end', { sessionId: 'a' }));
    bus.emit(makeEvent('session:ended', { sessionId: 'a' }));

    const all = stream.getAll();
    expect(all.length).toBe(3);
    expect(all[0].event.type).toBe('turn:start');
    expect(all[2].event.type).toBe('session:ended');
  });

  it('tracks cumulative event count across all types', () => {
    const stream = new EventStream(mockLogger() as any);
    const bus = makeBus();
    stream.connect(bus as any);

    for (let i = 0; i < 10; i++) bus.emit(makeEvent('turn:start'));
    expect(stream.totalCount).toBe(10);
  });

  it('wraps around and discards oldest events when buffer capacity is exceeded', () => {
    const stream = new EventStream(mockLogger() as any, { maxBufferSize: 5 });
    const bus = makeBus();
    stream.connect(bus as any);

    for (let i = 0; i < 8; i++) bus.emit(makeEvent('turn:start'));

    const all = stream.getAll();
    expect(all.length).toBe(5);
  });

  it('returns the N most recent events when queried', () => {
    const stream = new EventStream(mockLogger() as any);
    const bus = makeBus();
    stream.connect(bus as any);

    for (let i = 0; i < 20; i++) bus.emit(makeEvent('turn:start'));

    const recent = stream.getRecent(5);
    expect(recent.length).toBe(5);
  });

  it('filters events by type when queried', () => {
    const stream = new EventStream(mockLogger() as any);
    const bus = makeBus();
    stream.connect(bus as any);

    bus.emit(makeEvent('turn:start'));
    bus.emit(makeEvent('session:created'));
    bus.emit(makeEvent('turn:start'));

    const turns = stream.getByType('turn:start' as any);
    expect(turns.length).toBe(2);
  });

  it('stops ingesting events after disconnect() is called', () => {
    const stream = new EventStream(mockLogger() as any);
    const bus = makeBus();
    stream.connect(bus as any);

    bus.emit(makeEvent('turn:start'));
    stream.disconnect();
    bus.emit(makeEvent('turn:end'));

    expect(stream.totalCount).toBe(1);
  });
});

describe('EventStream time-based queries (getSince)', () => {
  it('returns only events received at or after the specified timestamp', async () => {
    const stream = new EventStream(mockLogger() as any);
    const bus = makeBus();
    stream.connect(bus as any);

    bus.emit(makeEvent('session:created'));
    await new Promise(r => setTimeout(r, 10));
    const cutoff = Date.now();
    await new Promise(r => setTimeout(r, 5));
    bus.emit(makeEvent('turn:start'));
    bus.emit(makeEvent('turn:end'));

    const recent = stream.getSince(cutoff);
    expect(recent.length).toBe(2);
    expect(recent.every(e => e.receivedAt >= cutoff)).toBe(true);
  });

  it('returns empty array when cutoff timestamp is in the future', () => {
    const stream = new EventStream(mockLogger() as any);
    const bus = makeBus();
    stream.connect(bus as any);
    bus.emit(makeEvent('turn:start'));

    const result = stream.getSince(Date.now() + 10_000);
    expect(result).toHaveLength(0);
  });
});

describe('EventStream session indexing', () => {
  it('indexes events by sessionId for fast per-session queries', () => {
    const stream = new EventStream(mockLogger() as any);
    const bus = makeBus();
    stream.connect(bus as any);

    bus.emit(makeEvent('turn:start', { sessionId: 'sess-A' }));
    bus.emit(makeEvent('turn:end', { sessionId: 'sess-A' }));
    bus.emit(makeEvent('turn:start', { sessionId: 'sess-B' }));

    expect(stream.getBySession('sess-A').length).toBe(2);
    expect(stream.getBySession('sess-B').length).toBe(1);
    expect(stream.getBySession('sess-C').length).toBe(0);
  });

  it('tracks all sessions that have been seen', () => {
    const stream = new EventStream(mockLogger() as any);
    const bus = makeBus();
    stream.connect(bus as any);

    bus.emit(makeEvent('turn:start', { sessionId: 'x' }));
    bus.emit(makeEvent('turn:start', { sessionId: 'y' }));

    expect(stream.activeSessions).toContain('x');
    expect(stream.activeSessions).toContain('y');
  });

  it('removes session from index when cleanupSession is called', () => {
    const stream = new EventStream(mockLogger() as any);
    const bus = makeBus();
    stream.connect(bus as any);

    bus.emit(makeEvent('turn:start', { sessionId: 'sess-Z' }));
    expect(stream.activeSessions).toContain('sess-Z');

    stream.cleanupSession('sess-Z');
    expect(stream.activeSessions).not.toContain('sess-Z');
  });
});

describe('EventStream rate tracking', () => {
  it('returns zero rate when no events have been ingested', () => {
    const stream = new EventStream(mockLogger() as any);
    expect(stream.getRate(60)).toBe(0);
  });

  it('returns positive rate after events have been ingested', () => {
    const stream = new EventStream(mockLogger() as any);
    const bus = makeBus();
    stream.connect(bus as any);

    for (let i = 0; i < 5; i++) bus.emit(makeEvent('turn:start'));
    expect(stream.getRate(60)).toBeGreaterThan(0);
  });
});

describe('EventStream type distribution', () => {
  it('accumulates cumulative counts per event type', () => {
    const stream = new EventStream(mockLogger() as any);
    const bus = makeBus();
    stream.connect(bus as any);

    bus.emit(makeEvent('turn:start'));
    bus.emit(makeEvent('turn:start'));
    bus.emit(makeEvent('turn:end'));

    const counts = stream.getTypeCounts();
    expect(counts.get('turn:start')).toBe(2);
    expect(counts.get('turn:end')).toBe(1);
  });

  it('returns relative counts for recent event window', () => {
    const stream = new EventStream(mockLogger() as any);
    const bus = makeBus();
    stream.connect(bus as any);

    bus.emit(makeEvent('turn:start'));
    bus.emit(makeEvent('session:created'));

    const dist = stream.getTypeDistribution(10);
    expect(dist['turn:start']).toBe(1);
    expect(dist['session:created']).toBe(1);
  });
});

describe('EventStream summarization', () => {
  it('returns a summary with event count, rate, top types, and active sessions', () => {
    const stream = new EventStream(mockLogger() as any);
    const bus = makeBus();
    stream.connect(bus as any);

    bus.emit(makeEvent('turn:start', { sessionId: 'sess-1' }));
    bus.emit(makeEvent('session:created', { sessionId: 'sess-1' }));

    const summary = stream.summarize(60_000);
    expect(summary).toMatchObject({
      windowMs: expect.any(Number),
      totalEvents: expect.any(Number),
      eventsPerSecond: expect.any(Number),
      topTypes: expect.any(Array),
      recentSequence: expect.any(Array),
      activeSessions: expect.any(Number),
    });
    expect(summary.totalEvents).toBeGreaterThanOrEqual(2);
  });

  it('sorts topTypes by count in descending order', () => {
    const stream = new EventStream(mockLogger() as any);
    const bus = makeBus();
    stream.connect(bus as any);

    for (let i = 0; i < 5; i++) bus.emit(makeEvent('turn:start'));
    bus.emit(makeEvent('turn:end'));

    const summary = stream.summarize(60_000);
    if (summary.topTypes.length >= 2) {
      expect(summary.topTypes[0].count).toBeGreaterThanOrEqual(summary.topTypes[1].count);
    }
  });

  it('collapses consecutive duplicate event types in the sequence', () => {
    const stream = new EventStream(mockLogger() as any);
    const bus = makeBus();
    stream.connect(bus as any);

    bus.emit(makeEvent('turn:start'));
    bus.emit(makeEvent('turn:start'));
    bus.emit(makeEvent('turn:start'));
    bus.emit(makeEvent('turn:end'));

    const summary = stream.summarize(60_000);
    const tsCount = summary.recentSequence.filter((t: string) => t === 'turn:start').length;
    expect(tsCount).toBe(1);
  });
});
