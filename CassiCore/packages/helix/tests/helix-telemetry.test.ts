/**
 * HelixTelemetry tests — Phase A scaffold.
 *
 * Verifies session + posture-turn span lifecycle, signal counters, EventBus
 * ingestion of workspace:ignition events, and latency percentile computation.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { HelixTelemetry } from '../src/helix-telemetry.js'
import type { ILogger, IEventBus } from '@cassicore/foundation'


function createMockLogger(): ILogger {
  const make = () => vi.fn()
  const logger: ILogger = {
    debug: make(),
    info: make(),
    warn: make(),
    error: make(),
    child: () => logger,
  } as any
  return logger
}


function createMockBus() {
  const handlers = new Map<string, Array<(e: any) => void>>()
  const bus: IEventBus = {
    emit: vi.fn(async (e: any) => {
      const key = String(e?.type)
      for (const h of handlers.get(key) ?? []) h(e)
    }),
    on: (type: any, handler: (e: any) => void) => {
      const key = String(type)
      const arr = handlers.get(key) ?? []
      arr.push(handler)
      handlers.set(key, arr)
      return () => {
        const idx = arr.indexOf(handler)
        if (idx >= 0) arr.splice(idx, 1)
      }
    },
  } as any
  return bus
}


describe('HelixTelemetry', () => {
  let logger: ILogger

  beforeEach(() => {
    logger = createMockLogger()
  })

  it('tracks session lifecycle in spans + metrics', () => {
    const tel = new HelixTelemetry(logger)
    const span = tel.startSession('sess-1', { goal: 'test' })
    expect(span.name).toBe('helix.session')
    expect(span.sessionId).toBe('sess-1')
    expect(span.status).toBe('active')
    expect(tel.getMetricsSnapshot().sessionsActive).toBe(1)

    tel.endSession('sess-1', 'ok', { durationMs: 500 })
    const snap = tel.getMetricsSnapshot()
    expect(snap.sessionsActive).toBe(0)
    expect(snap.sessionsCompleted).toBe(1)
    expect(snap.sessionsErrored).toBe(0)

    const closed = tel.getSpan(span.spanId)
    expect(closed?.status).toBe('ok')
    expect(closed?.durationMs).toBeGreaterThanOrEqual(0)
    expect(closed?.attrs.durationMs).toBe(500)
  })

  it('records posture-turn spans as children of the session span', () => {
    const tel = new HelixTelemetry(logger)
    const sessionSpan = tel.startSession('sess-2')
    const turnSpan = tel.startPostureTurn('sess-2', 'unity', 3, { goal: 'tick' })

    expect(turnSpan.name).toBe('helix.posture.turn')
    expect(turnSpan.parentSpanId).toBe(sessionSpan.spanId)
    expect(turnSpan.attrs).toMatchObject({ posture: 'unity', seq: 3 })

    tel.endPostureTurn(turnSpan.spanId, 'ok')
    const closed = tel.getSpan(turnSpan.spanId)
    expect(closed?.status).toBe('ok')
    expect(closed?.durationMs).toBeGreaterThanOrEqual(0)
  })

  it('records signal-submit counters by posture and type', () => {
    const tel = new HelixTelemetry(logger)
    tel.recordSignalSubmit({
      sessionId: 's',
      posture: 'unity',
      signalType: 'observation',
      ignited: true,
    })
    tel.recordSignalSubmit({
      sessionId: 's',
      posture: 'unity',
      signalType: 'observation',
      ignited: false,
    })
    tel.recordSignalSubmit({
      sessionId: 's',
      posture: 'yang',
      signalType: 'tension',
      ignited: true,
    })

    const snap = tel.getMetricsSnapshot()
    expect(snap.signalsSubmitted['helix-unity']).toBe(2)
    expect(snap.signalsSubmitted['helix-yang']).toBe(1)
    expect(snap.signalsIgnited['helix-unity']).toBe(1)
    expect(snap.signalsIgnited['helix-yang']).toBe(1)
  })

  it('computes p50 and p95 posture-turn latencies', () => {
    const tel = new HelixTelemetry(logger)
    tel.startSession('s')

    for (let i = 0; i < 10; i++) {
      const turn = tel.startPostureTurn('s', 'unity', i)
      const fixedStart = Date.parse('2026-01-01T00:00:00.000Z')
      ;(turn as any).startedAt = new Date(fixedStart).toISOString()
      ;(turn as any).endedAt = new Date(fixedStart + (i + 1) * 10).toISOString()
      ;(turn as any).durationMs = (i + 1) * 10
      ;(turn as any).status = 'ok'
      tel.endPostureTurn(turn.spanId, 'ok')
    }

    const snap = tel.getMetricsSnapshot()
    expect(snap.postureTurnLatencyMsP50['unity']).toBeGreaterThan(0)
    expect(snap.postureTurnLatencyMsP95['unity']).toBeGreaterThanOrEqual(
      snap.postureTurnLatencyMsP50['unity']!,
    )
  })

  it('ingests workspace:ignition events from the EventBus (helix-prefixed sources only)', () => {
    const tel = new HelixTelemetry(logger)
    const bus = createMockBus()
    tel.setEventBus(bus)

    // Helix ignition — should be counted
    bus.emit({
      type: 'workspace:ignition',
      source: 'helix-unity-a',
      signalType: 'observation',
      luminance: 0.5,
      timestamp: Date.now(),
    } as any)

    // Non-Helix ignition — should be ignored
    bus.emit({
      type: 'workspace:ignition',
      source: 'thinker',
      signalType: 'insight',
      luminance: 0.7,
      timestamp: Date.now(),
    } as any)

    const snap = tel.getMetricsSnapshot()
    expect(snap.signalsIgnited['helix-unity-a']).toBe(1)
    expect(snap.signalsIgnited['thinker']).toBeUndefined()
  })

  it('getSessionSpans returns only spans for the given session', () => {
    const tel = new HelixTelemetry(logger)
    tel.startSession('s1')
    tel.startSession('s2')
    tel.startPostureTurn('s1', 'unity', 0)
    tel.startPostureTurn('s2', 'yang', 0)

    const s1Spans = tel.getSessionSpans('s1')
    const s2Spans = tel.getSessionSpans('s2')
    expect(s1Spans.length).toBe(2)
    expect(s2Spans.length).toBe(2)
    expect(s1Spans.every(s => s.sessionId === 's1')).toBe(true)
  })

  it('shutdown unsubscribes from the EventBus', () => {
    const tel = new HelixTelemetry(logger)
    const bus = createMockBus()
    tel.setEventBus(bus)
    tel.shutdown()

    bus.emit({
      type: 'workspace:ignition',
      source: 'helix-unity-a',
      signalType: 'observation',
      luminance: 0.5,
      timestamp: Date.now(),
    } as any)

    const snap = tel.getMetricsSnapshot()
    expect(snap.signalsIgnited['helix-unity-a']).toBeUndefined()
  })
})
