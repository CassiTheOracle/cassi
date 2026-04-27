/**
 * HelixLocus — Session-scoped Spark → Kindle → Radiate for brain-integrated Helix.
 *
 * Mirrors the Constellation Locus pattern (core/intelligence/constellation/locus/)
 * at Helix-session granularity. Each cognitive signal that lands in the
 * session's workspace slice is observed here; the Locus scores it across
 * five axes and decides whether it's bright enough to kindle — i.e. become
 * attention-worthy for other postures.
 *
 * Phase D scope: pure observation + journaling integration. The Conductor
 * feeds signals in, HelixLocus emits kindle events, the Conductor journals
 * them. Luminance boosting (making kindled signals win more GlobalWorkspace
 * slots) is intentionally deferred — the plan calls for it but we don't
 * modify the workspace's ignition math yet. Kindled signals stay visible
 * via the journal + SSE stream, which is enough surface for the Observatory
 * views to render.
 */

import type { ILogger } from '../../../types/interfaces.js'
import type { CognitiveSignal } from '../workspace/index.js'


export type HelixSparkKind =
  | 'finding'
  | 'challenge'
  | 'concession'
  | 'work-unit'
  | 'nudge'
  | 'mentor-flag'
  | 'mentor-nudge'
  | 'investigation-request'
  | 'unknown'


export interface HelixLuminanceScore {
  /** 0-1: How new relative to recent same-kind signals from same posture? */
  novelty: number
  /** 0-1: Time-sensitivity derived from signal type + urgencyHint. */
  urgency: number
  /** 0-1: How many other postures could act on this signal right now? */
  crossRelevance: number
  /** 0-1: Running quality delta along this correlation thread. */
  qualityDelta: number
  /** 0-1: Multi-posture consensus rewarded — the more unique authors, the higher. */
  authorDiversity: number
  /** Weighted composite — actual kindling threshold. */
  composite: number
}


export interface HelixSpark {
  sparkId: string
  sessionId: string
  signalId: string
  postureId: string
  role: string
  kind: HelixSparkKind
  correlation?: string
  recipient?: string
  content: string
  observedAt: string
  score: HelixLuminanceScore
}


export interface HelixKindleEvent {
  eventId: string
  sparkId: string
  signalId: string
  postureId: string
  correlation?: string
  kind: HelixSparkKind
  score: HelixLuminanceScore
  /** Number of live postures this signal was considered relevant to. */
  audience: number
  /** ms this kindled signal remains attention-worthy before radiance decays. */
  ttlMs: number
  timestamp: string
}


export interface HelixRadianceEvent {
  eventId: string
  sparkId: string
  signalId: string
  reason: 'ttl-expired' | 'eclipsed' | 'session-end'
  timestamp: string
}


export interface HelixLocusWeights {
  novelty: number
  urgency: number
  crossRelevance: number
  qualityDelta: number
  authorDiversity: number
}


export const DEFAULT_HELIX_LOCUS_WEIGHTS: HelixLocusWeights = {
  novelty: 0.20,
  urgency: 0.25,
  crossRelevance: 0.20,
  qualityDelta: 0.15,
  authorDiversity: 0.20,
}


const BASE_URGENCY: Record<HelixSparkKind, number> = {
  'challenge': 0.80,
  'mentor-flag': 0.78,
  'mentor-nudge': 0.55,
  'nudge': 0.55,
  'finding': 0.50,
  'concession': 0.45,
  'work-unit': 0.40,
  'investigation-request': 0.60,
  'unknown': 0.35,
}


const BASE_NOVELTY: Record<HelixSparkKind, number> = {
  'finding': 0.70,
  'investigation-request': 0.65,
  'challenge': 0.60,
  'concession': 0.60,
  'mentor-flag': 0.55,
  'mentor-nudge': 0.45,
  'work-unit': 0.35,
  'nudge': 0.35,
  'unknown': 0.40,
}


export interface HelixLocusOpts {
  sessionId: string
  logger: ILogger
  /** Ignition threshold — composite score to kindle. Default 0.45. */
  ignitionThreshold?: number
  /** Score weights. */
  weights?: HelixLocusWeights
  /** ms a kindled signal stays hot. Default 15s. */
  kindleTtlMs?: number
  /** Max tracked postures (for author-diversity denominator). Default 4. */
  maxAudiencePostures?: number
}


export interface HelixLocusStats {
  sparksObserved: number
  kindlesEmitted: number
  radiancesEmitted: number
  uniquePostures: number
  liveKindles: number
}


export type HelixLocusListener =
  | { kind: 'spark'; handler: (spark: HelixSpark) => void }
  | { kind: 'kindle'; handler: (event: HelixKindleEvent) => void }
  | { kind: 'radiance'; handler: (event: HelixRadianceEvent) => void }


export class HelixLocus {
  readonly sessionId: string

  private logger: ILogger
  private threshold: number
  private weights: HelixLocusWeights
  private kindleTtlMs: number
  private maxAudiencePostures: number

  private postureAuthors = new Set<string>()
  private recentByPostureKind = new Map<string, number[]>()
  private correlationHistory = new Map<string, string[]>()
  private liveKindles = new Map<string, { event: HelixKindleEvent; expiresAt: number }>()

  private sparksObserved = 0
  private kindlesEmitted = 0
  private radiancesEmitted = 0

  private listeners: HelixLocusListener[] = []
  private sparkCounter = 0
  private kindleCounter = 0
  private radianceCounter = 0


  constructor(opts: HelixLocusOpts) {
    this.sessionId = opts.sessionId
    this.logger = opts.logger.child
      ? opts.logger.child(`helix-locus:${opts.sessionId.slice(0, 8)}`)
      : opts.logger
    this.threshold = opts.ignitionThreshold ?? 0.45
    this.weights = opts.weights ?? DEFAULT_HELIX_LOCUS_WEIGHTS
    this.kindleTtlMs = opts.kindleTtlMs ?? 15_000
    this.maxAudiencePostures = opts.maxAudiencePostures ?? 4
  }


  /**
   * Register a listener. Returns an unsubscribe function.
   * The Conductor uses this to journal kindle.spark and kindle.radiate.
   */
  on(listener: HelixLocusListener): () => void {
    this.listeners.push(listener)
    return () => {
      const idx = this.listeners.indexOf(listener)
      if (idx >= 0) this.listeners.splice(idx, 1)
    }
  }


  /**
   * Observe a cognitive signal. Returns the resulting HelixSpark along
   * with an optional KindleEvent when the spark crosses the threshold.
   * Signals from other sessions are silently ignored.
   */
  observe(signal: CognitiveSignal): { spark?: HelixSpark; kindle?: HelixKindleEvent } {
    if (signal.sessionId !== this.sessionId && signal.sessionId !== '*') return {}

    const postureId = String(signal.source ?? 'unknown')
    const role = String(signal.metadata?.posture ?? postureId)
    const kind = this.resolveKind(signal)
    const correlation = typeof signal.metadata?.correlation === 'string'
      ? signal.metadata.correlation
      : undefined
    const recipient = typeof signal.metadata?.recipient === 'string'
      ? signal.metadata.recipient
      : undefined

    this.postureAuthors.add(role)

    const score = this.score({ signal, postureId, kind, correlation })
    const spark: HelixSpark = {
      sparkId: `spark-${++this.sparkCounter}-${Date.now().toString(36)}`,
      sessionId: this.sessionId,
      signalId: signal.signalId,
      postureId,
      role,
      kind,
      correlation,
      recipient,
      content: (signal.content ?? '').slice(0, 500),
      observedAt: new Date().toISOString(),
      score,
    }

    this.sparksObserved++
    this.emit({ kind: 'spark', event: spark })
    this.expireStaleKindles()

    if (score.composite < this.threshold) {
      return { spark }
    }

    const audience = this.resolveAudience(recipient)
    const kindleEvent: HelixKindleEvent = {
      eventId: `kindle-${++this.kindleCounter}-${Date.now().toString(36)}`,
      sparkId: spark.sparkId,
      signalId: signal.signalId,
      postureId,
      correlation,
      kind,
      score,
      audience,
      ttlMs: this.kindleTtlMs,
      timestamp: spark.observedAt,
    }

    this.kindlesEmitted++
    this.liveKindles.set(kindleEvent.eventId, {
      event: kindleEvent,
      expiresAt: Date.now() + this.kindleTtlMs,
    })
    this.emit({ kind: 'kindle', event: kindleEvent })
    return { spark, kindle: kindleEvent }
  }


  getStats(): HelixLocusStats {
    this.expireStaleKindles()
    return {
      sparksObserved: this.sparksObserved,
      kindlesEmitted: this.kindlesEmitted,
      radiancesEmitted: this.radiancesEmitted,
      uniquePostures: this.postureAuthors.size,
      liveKindles: this.liveKindles.size,
    }
  }


  /**
   * Force-expire all live kindles; called by the Conductor on session
   * termination. Emits a `session-end` radiance for each.
   */
  drain(): void {
    const now = Date.now()
    for (const [, entry] of this.liveKindles) {
      this.emitRadiance(entry.event, 'session-end', now)
    }
    this.liveKindles.clear()
  }


  private score(input: {
    signal: CognitiveSignal
    postureId: string
    kind: HelixSparkKind
    correlation?: string
  }): HelixLuminanceScore {
    const baseUrgency = BASE_URGENCY[input.kind] ?? 0.35
    const urgencyHint = typeof input.signal.urgencyHint === 'number' ? input.signal.urgencyHint : 0
    const urgency = clamp01(baseUrgency + urgencyHint)

    const noveltyBase = BASE_NOVELTY[input.kind] ?? 0.4
    const key = `${input.postureId}::${input.kind}`
    const recent = this.recentByPostureKind.get(key) ?? []
    const suppression = Math.min(0.6, recent.length * 0.08)
    const novelty = clamp01(noveltyBase - suppression)
    recent.push(Date.now())
    if (recent.length > 8) recent.shift()
    this.recentByPostureKind.set(key, recent)

    const crossRelevance = this.resolveCrossRelevance(input.signal.metadata?.recipient)

    const qualityDelta = input.correlation
      ? this.resolveQualityDelta(input.correlation, input.kind)
      : 0.5

    const authorDiversity = input.correlation
      ? this.updateAuthorDiversity(input.correlation, input.postureId)
      : clamp01(this.postureAuthors.size / Math.max(1, this.maxAudiencePostures))

    const w = this.weights
    const composite =
      w.novelty * novelty +
      w.urgency * urgency +
      w.crossRelevance * crossRelevance +
      w.qualityDelta * qualityDelta +
      w.authorDiversity * authorDiversity

    return { novelty, urgency, crossRelevance, qualityDelta, authorDiversity, composite }
  }


  private resolveCrossRelevance(recipient: unknown): number {
    if (typeof recipient !== 'string' || recipient.length === 0) return 1.0
    return 1 / Math.max(1, this.maxAudiencePostures)
  }


  private resolveQualityDelta(correlation: string, kind: HelixSparkKind): number {
    const history = this.correlationHistory.get(correlation) ?? []
    history.push(kind)
    this.correlationHistory.set(correlation, history)

    // Heuristic: concessions resolve tension — high quality delta. Challenges
    // introduce tension to an established finding — moderate delta.
    if (kind === 'concession' && history.length > 1) return 0.9
    if (kind === 'challenge' && history.includes('finding')) return 0.7
    if (history.length === 1) return 0.5
    return 0.55
  }


  private updateAuthorDiversity(correlation: string, posture: string): number {
    const history = this.correlationHistory.get(correlation) ?? []
    const seen = new Set(history.length > 0 ? history : [posture])
    seen.add(posture)
    return clamp01(seen.size / Math.max(1, this.maxAudiencePostures))
  }


  private resolveAudience(recipient?: string): number {
    if (recipient) return 1
    return Math.max(1, this.postureAuthors.size - 1)
  }


  private resolveKind(signal: CognitiveSignal): HelixSparkKind {
    const raw = signal.metadata?.kind
    if (typeof raw !== 'string') return 'unknown'
    switch (raw) {
      case 'finding':
      case 'challenge':
      case 'concession':
      case 'work-unit':
      case 'nudge':
      case 'mentor-flag':
      case 'mentor-nudge':
      case 'investigation-request':
        return raw
      default:
        return 'unknown'
    }
  }


  private expireStaleKindles(): void {
    const now = Date.now()
    for (const [id, entry] of [...this.liveKindles.entries()]) {
      if (entry.expiresAt <= now) {
        this.emitRadiance(entry.event, 'ttl-expired', now)
        this.liveKindles.delete(id)
      }
    }
  }


  private emitRadiance(event: HelixKindleEvent, reason: HelixRadianceEvent['reason'], now: number): void {
    const radiance: HelixRadianceEvent = {
      eventId: `radiance-${++this.radianceCounter}-${now.toString(36)}`,
      sparkId: event.sparkId,
      signalId: event.signalId,
      reason,
      timestamp: new Date(now).toISOString(),
    }
    this.radiancesEmitted++
    this.emit({ kind: 'radiance', event: radiance })
  }


  private emit(
    input:
      | { kind: 'spark'; event: HelixSpark }
      | { kind: 'kindle'; event: HelixKindleEvent }
      | { kind: 'radiance'; event: HelixRadianceEvent },
  ): void {
    for (const listener of this.listeners) {
      if (listener.kind !== input.kind) continue
      try {
        switch (input.kind) {
          case 'spark':
            (listener as Extract<HelixLocusListener, { kind: 'spark' }>).handler(input.event)
            break
          case 'kindle':
            (listener as Extract<HelixLocusListener, { kind: 'kindle' }>).handler(input.event)
            break
          case 'radiance':
            (listener as Extract<HelixLocusListener, { kind: 'radiance' }>).handler(input.event)
            break
        }
      } catch (err) {
        this.logger.debug('locus listener failed', { error: String(err) })
      }
    }
  }
}


function clamp01(n: number): number {
  if (!Number.isFinite(n)) return 0
  if (n < 0) return 0
  if (n > 1) return 1
  return n
}
