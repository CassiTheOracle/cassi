/**
 * HelixQuiescenceDetector — Detects when a brain-integrated Helix session
 * has run out of attention-worthy activity and can terminate cleanly.
 *
 * Classic three-pronged consensus (workStream.isWorkerDone + reviewer
 * readiness + unresolved tensions) lives in helix-posture-runner.ts today
 * and gates the legacy path. Phase F adds this detector as an alternative
 * signal that fires *earlier* when the GlobalWorkspace tells us the
 * session is already quiet — no new ignitions, no live kindles, postures
 * idle — so the Conductor can call the pipeline's cancel hook and spare
 * the LLM a few last wasted iterations.
 *
 * Detection is observational only: this class never forces termination
 * directly. It emits events that the Conductor forwards to its
 * `onQuiescence` callback. The actual termination call (e.g. `cancelAll`)
 * stays in the pipeline for orderly cleanup.
 */

import type { ILogger } from '../../../types/interfaces.js'
import type { HelixJournal, HelixJournalEntry } from './helix-journal.js'
import type { HelixLocus, HelixLocusStats } from './helix-locus.js'


export interface HelixQuiescenceConfig {
  /** Minimum ms of no ignitions before the session is eligible. Default 10s. */
  idleWindowMs?: number
  /** Minimum session age before quiescence can fire. Default 20s. */
  minSessionAgeMs?: number
  /** How often to check. Default 2s. */
  checkIntervalMs?: number
  /** If >0, force termination at this age regardless of activity. Default 0 (disabled). */
  hardCutoffMs?: number
}


export interface HelixQuiescenceReport {
  sessionId: string
  reason: 'idle' | 'hard-cutoff'
  detectedAt: string
  lastEventAt?: string
  sessionAgeMs: number
  idleDurationMs: number
  liveKindles: number
  totalEvents: number
}


export type QuiescenceListener = (report: HelixQuiescenceReport) => void


export interface HelixQuiescenceDetectorOpts {
  sessionId: string
  logger: ILogger
  journal: HelixJournal
  locus?: HelixLocus
  config?: HelixQuiescenceConfig
}


export class HelixQuiescenceDetector {
  readonly sessionId: string

  private logger: ILogger
  private journal: HelixJournal
  private locus?: HelixLocus

  private idleWindowMs: number
  private minSessionAgeMs: number
  private checkIntervalMs: number
  private hardCutoffMs: number

  private startedAt = Date.now()
  private timer?: ReturnType<typeof setInterval>
  private listeners: QuiescenceListener[] = []
  private fired = false


  constructor(opts: HelixQuiescenceDetectorOpts) {
    this.sessionId = opts.sessionId
    this.logger = opts.logger.child
      ? opts.logger.child(`helix-quiescence:${opts.sessionId.slice(0, 8)}`)
      : opts.logger
    this.journal = opts.journal
    this.locus = opts.locus
    this.idleWindowMs = opts.config?.idleWindowMs ?? 10_000
    this.minSessionAgeMs = opts.config?.minSessionAgeMs ?? 20_000
    this.checkIntervalMs = opts.config?.checkIntervalMs ?? 2_000
    this.hardCutoffMs = opts.config?.hardCutoffMs ?? 0
  }


  onQuiescence(listener: QuiescenceListener): () => void {
    this.listeners.push(listener)
    return () => {
      const idx = this.listeners.indexOf(listener)
      if (idx >= 0) this.listeners.splice(idx, 1)
    }
  }


  start(): void {
    if (this.timer) return
    this.startedAt = Date.now()
    this.timer = setInterval(() => {
      try { this.check() } catch (err) {
        this.logger.debug('quiescence check failed', { error: String(err) })
      }
    }, this.checkIntervalMs)
    if (typeof (this.timer as any)?.unref === 'function') {
      (this.timer as any).unref()
    }
  }


  stop(): void {
    if (this.timer) {
      clearInterval(this.timer)
      this.timer = undefined
    }
  }


  /**
   * Force a single check synchronously. Exposed for tests and for
   * Conductor-driven checks at snapshot boundaries.
   */
  check(): HelixQuiescenceReport | null {
    if (this.fired) return null

    const now = Date.now()
    const sessionAgeMs = now - this.startedAt

    if (this.hardCutoffMs > 0 && sessionAgeMs >= this.hardCutoffMs) {
      return this.fire('hard-cutoff', now, sessionAgeMs, Infinity)
    }

    if (sessionAgeMs < this.minSessionAgeMs) return null

    const lastActivityAt = this.lookupLastActivity()
    const idleDurationMs = lastActivityAt
      ? now - Date.parse(lastActivityAt)
      : sessionAgeMs

    if (idleDurationMs < this.idleWindowMs) return null
    if (this.locus && this.locus.getStats().liveKindles > 0) return null

    return this.fire('idle', now, sessionAgeMs, idleDurationMs, lastActivityAt)
  }


  private fire(
    reason: 'idle' | 'hard-cutoff',
    now: number,
    sessionAgeMs: number,
    idleDurationMs: number,
    lastActivityAt?: string,
  ): HelixQuiescenceReport {
    this.fired = true
    const stats: HelixLocusStats | undefined = this.locus?.getStats()
    const report: HelixQuiescenceReport = {
      sessionId: this.sessionId,
      reason,
      detectedAt: new Date(now).toISOString(),
      lastEventAt: lastActivityAt,
      sessionAgeMs,
      idleDurationMs,
      liveKindles: stats?.liveKindles ?? 0,
      totalEvents: this.journal.countSession(this.sessionId),
    }

    this.logger.info('quiescence.detected', {
      sessionId: this.sessionId,
      reason,
      idleDurationMs,
      sessionAgeMs,
    })

    for (const listener of this.listeners) {
      try { listener(report) } catch (err) {
        this.logger.debug('quiescence listener failed', { error: String(err) })
      }
    }

    return report
  }


  private lookupLastActivity(): string | undefined {
    const recent: HelixJournalEntry[] = this.journal.readSession(this.sessionId, {
      sinceSeq: Math.max(0, this.journal.countSession(this.sessionId) - 20),
      limit: 20,
    })
    if (recent.length === 0) return undefined

    // Activity = attention-worthy events. Snapshot ticks and routine
    // lifecycle events don't count as "the session is still thinking".
    const ACTIVITY_EVENTS = new Set([
      'signal.submit',
      'signal.ignite',
      'workspace.broadcast',
      'kindle.spark',
      'aurora.observe',
      'engram.write',
    ])

    for (let i = recent.length - 1; i >= 0; i--) {
      if (ACTIVITY_EVENTS.has(recent[i]!.eventType)) return recent[i]!.timestamp
    }
    return recent[0]!.timestamp
  }
}
