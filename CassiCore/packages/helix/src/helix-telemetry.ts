/**
 * HelixTelemetry — Metrics and spans for Helix brain-integrated sessions.
 *
 * Phase A scope: in-process counters + lightweight OpenTelemetry-style spans
 * (start / end / event with attributes). No external OTel dependency yet.
 * Phase D wires this to the SSE stream; a later pass swaps the span store for
 * a real OTel exporter when one is introduced to the codebase.
 *
 * Subscribes to the EventBus for `workspace:ignition` and `workspace:eclipse`
 * events and derives Helix-scoped ignition metrics by filtering on the
 * `helix-` source prefix, avoiding duplicate instrumentation inside PostureModule.
 */

import type { ILogger, IEventBus } from '@cassicore/foundation'
import type { HelixJournal } from './helix-journal.js'


export interface HelixSignalEvent {
  sessionId: string
  posture: string
  signalType: string
  correlation?: string
  recipient?: string
  kind?: string
  ignited: boolean
}


export interface HelixSpanEvent {
  timestamp: string
  name: string
  attrs?: Record<string, unknown>
}


export interface HelixSpan {
  spanId: string
  name: string
  sessionId: string
  parentSpanId?: string
  startedAt: string
  endedAt?: string
  durationMs?: number
  attrs: Record<string, unknown>
  events: HelixSpanEvent[]
  status: 'active' | 'ok' | 'error'
  error?: string
}


export interface HelixMetricsSnapshot {
  sessionsActive: number
  sessionsCompleted: number
  sessionsErrored: number
  signalsSubmitted: Record<string, number>
  signalsIgnited: Record<string, number>
  postureTurnLatencyMsP50: Record<string, number>
  postureTurnLatencyMsP95: Record<string, number>
}


export class HelixTelemetry {
  private logger: ILogger
  private eventBus?: IEventBus
  private journal?: HelixJournal
  private unsubscribers: Array<() => void> = []

  private spans = new Map<string, HelixSpan>()
  private sessionRootSpanIds = new Map<string, string>()

  private sessionsActive = 0
  private sessionsCompleted = 0
  private sessionsErrored = 0

  private counters = {
    submittedByPosture: new Map<string, number>(),
    ignitedByPosture: new Map<string, number>(),
    submittedByType: new Map<string, number>(),
    ignitedByType: new Map<string, number>(),
  }

  private turnLatencies = new Map<string, number[]>()

  private spanCounter = 0


  constructor(logger: ILogger) {
    this.logger = logger.child ? logger.child('helix-telemetry') : logger
  }

  setEventBus(bus: IEventBus): void {
    if (this.eventBus === bus) return
    for (const unsub of this.unsubscribers) {
      try { unsub() } catch { /* best-effort */ }
    }
    this.unsubscribers = []
    this.eventBus = bus

    const unsubIgnite = bus.on('workspace:ignition' as any, (e: any) => {
      const source = String(e?.source ?? '')
      if (!source.startsWith('helix-')) return
      const signalType = String(e?.signalType ?? 'unknown')
      this.bump(this.counters.ignitedByPosture, source)
      this.bump(this.counters.ignitedByType, signalType)
      this.logger.debug('signal.ignite', {
        source,
        signalType,
        luminance: e?.luminance,
      })

      if (this.journal) {
        const sessionId = this.resolveSessionIdFromSource(source)
        if (sessionId) {
          try {
            this.journal.append({
              sessionId,
              eventType: 'signal.ignite',
              postureId: source,
              correlationId: typeof e?.signalId === 'string' ? e.signalId : undefined,
              payload: {
                signalType,
                luminance: e?.luminance,
                coalitionIds: e?.coalitionIds,
              },
            })
          } catch { /* best-effort */ }
        }
      }
    })
    if (unsubIgnite) this.unsubscribers.push(unsubIgnite)
  }

  /**
   * Attach a journal. Subsequent `recordSignalSubmit` calls and
   * `workspace:ignition` events will be journaled in addition to being
   * counted. The journal reference is used best-effort — journal failures
   * do not block metric recording.
   */
  setJournal(journal: HelixJournal): void {
    this.journal = journal
  }

  /**
   * Track which sessionId a posture-id belongs to, so workspace:ignition
   * events (which carry the `source` posture name but not a sessionId) can
   * be journaled to the right session.
   */
  private postureSessionIndex = new Map<string, string>()

  registerPostureSession(postureId: string, sessionId: string): void {
    this.postureSessionIndex.set(postureId, sessionId)
  }

  unregisterPostureSession(postureId: string): void {
    this.postureSessionIndex.delete(postureId)
  }

  private resolveSessionIdFromSource(source: string): string | undefined {
    return this.postureSessionIndex.get(source)
  }


  startSession(sessionId: string, attrs: Record<string, unknown> = {}): HelixSpan {
    const span = this.createSpan('helix.session', sessionId, undefined, attrs)
    this.sessionRootSpanIds.set(sessionId, span.spanId)
    this.sessionsActive++
    this.logger.info('session.start', { sessionId, spanId: span.spanId, ...attrs })
    return span
  }

  endSession(sessionId: string, outcome: 'ok' | 'error', attrs: Record<string, unknown> = {}): void {
    const spanId = this.sessionRootSpanIds.get(sessionId)
    if (!spanId) {
      this.logger.warn('endSession called with no active span', { sessionId })
      return
    }
    this.endSpan(spanId, outcome, attrs)
    this.sessionRootSpanIds.delete(sessionId)
    this.sessionsActive = Math.max(0, this.sessionsActive - 1)
    if (outcome === 'ok') this.sessionsCompleted++
    else this.sessionsErrored++
    this.logger.info('session.end', { sessionId, outcome, ...attrs })
  }

  startPostureTurn(
    sessionId: string,
    postureName: string,
    seq: number,
    attrs: Record<string, unknown> = {},
  ): HelixSpan {
    const parentId = this.sessionRootSpanIds.get(sessionId)
    return this.createSpan('helix.posture.turn', sessionId, parentId, {
      posture: postureName,
      seq,
      ...attrs,
    })
  }

  endPostureTurn(spanId: string, outcome: 'ok' | 'error', attrs: Record<string, unknown> = {}): void {
    const span = this.spans.get(spanId)
    if (!span) return
    this.endSpan(spanId, outcome, attrs)
    const posture = String(span.attrs.posture ?? 'unknown')
    if (span.durationMs !== undefined) {
      const arr = this.turnLatencies.get(posture) ?? []
      arr.push(span.durationMs)
      if (arr.length > 500) arr.shift()
      this.turnLatencies.set(posture, arr)
    }
  }

  /**
   * Record a signal-submit observation from a PostureModule. Separate from
   * workspace:ignition so that sub-threshold signals still appear in counts.
   */
  recordSignalSubmit(event: HelixSignalEvent): void {
    const postureKey = `helix-${event.posture}`
    this.bump(this.counters.submittedByPosture, postureKey)
    this.bump(this.counters.submittedByType, event.signalType)
    if (event.ignited) {
      this.bump(this.counters.ignitedByPosture, postureKey)
      this.bump(this.counters.ignitedByType, event.signalType)
    }
    if (this.journal) {
      try {
        this.journal.append({
          sessionId: event.sessionId,
          eventType: 'signal.submit',
          postureId: postureKey,
          correlationId: event.correlation,
          payload: {
            signalType: event.signalType,
            kind: event.kind,
            recipient: event.recipient,
            ignited: event.ignited,
          },
        })
      } catch { /* best-effort */ }
    }
  }

  recordSpanEvent(spanId: string, name: string, attrs: Record<string, unknown> = {}): void {
    const span = this.spans.get(spanId)
    if (!span) return
    span.events.push({
      timestamp: new Date().toISOString(),
      name,
      attrs,
    })
  }

  getMetricsSnapshot(): HelixMetricsSnapshot {
    return {
      sessionsActive: this.sessionsActive,
      sessionsCompleted: this.sessionsCompleted,
      sessionsErrored: this.sessionsErrored,
      signalsSubmitted: mapToRecord(this.counters.submittedByPosture),
      signalsIgnited: mapToRecord(this.counters.ignitedByPosture),
      postureTurnLatencyMsP50: percentilesByPosture(this.turnLatencies, 0.50),
      postureTurnLatencyMsP95: percentilesByPosture(this.turnLatencies, 0.95),
    }
  }

  getSpan(spanId: string): HelixSpan | undefined {
    return this.spans.get(spanId)
  }

  getSessionSpans(sessionId: string): HelixSpan[] {
    return [...this.spans.values()].filter(s => s.sessionId === sessionId)
  }

  shutdown(): void {
    for (const unsub of this.unsubscribers) {
      try { unsub() } catch { /* best-effort */ }
    }
    this.unsubscribers = []
  }


  private createSpan(
    name: string,
    sessionId: string,
    parentSpanId: string | undefined,
    attrs: Record<string, unknown>,
  ): HelixSpan {
    const spanId = `span-${Date.now()}-${this.spanCounter++}`
    const span: HelixSpan = {
      spanId,
      name,
      sessionId,
      parentSpanId,
      startedAt: new Date().toISOString(),
      attrs: { ...attrs },
      events: [],
      status: 'active',
    }
    this.spans.set(spanId, span)
    return span
  }

  private endSpan(spanId: string, outcome: 'ok' | 'error', attrs: Record<string, unknown>): void {
    const span = this.spans.get(spanId)
    if (!span || span.status !== 'active') return
    span.endedAt = new Date().toISOString()
    span.durationMs = Date.parse(span.endedAt) - Date.parse(span.startedAt)
    span.status = outcome
    Object.assign(span.attrs, attrs)
  }

  private bump(map: Map<string, number>, key: string): void {
    map.set(key, (map.get(key) ?? 0) + 1)
  }
}


function mapToRecord(map: Map<string, number>): Record<string, number> {
  const out: Record<string, number> = {}
  for (const [k, v] of map) out[k] = v
  return out
}


function percentilesByPosture(
  latencies: Map<string, number[]>,
  pct: number,
): Record<string, number> {
  const out: Record<string, number> = {}
  for (const [posture, arr] of latencies) {
    if (arr.length === 0) continue
    const sorted = [...arr].sort((a, b) => a - b)
    const idx = Math.min(sorted.length - 1, Math.max(0, Math.floor(pct * sorted.length)))
    out[posture] = sorted[idx]!
  }
  return out
}
