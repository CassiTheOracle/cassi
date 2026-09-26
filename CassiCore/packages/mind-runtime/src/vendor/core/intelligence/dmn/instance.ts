/**
 * DmnInstance — per-attached-main-session DMN state.
 *
 * Activity-Gated Observer Pattern (AGOP), matching the constellation
 * cluster-observer-layer / corpus-observer-layer at
 * core/intelligence/constellation/{cluster,corpus}-observer-layer.ts.
 *
 * Each instance runs its own tick loop on `pollIntervalMs` (default ~8s).
 * On every tick, `discoverActivity()` polls the session substrate via the
 * injected `getActivitySnapshot` callback. When the substrate has changed
 * since the previous tick (new messages, new tool calls, etc.), the
 * scheduler is fed a `recordEvent()`. The scheduler trips on its own
 * thresholds (materialThreshold + cooldown + warmup), invoking `fireOnce`
 * which runs the dialectic over the session window and writes the
 * synthesis to the digest cache.
 *
 * This is autonomous, ambient observation. The session does not push
 * turn-end events at the DMN; the DMN samples the session's state at its
 * own cadence and fires when the substrate has accumulated enough signal.
 *
 * Lifecycle bound to the parent main session: created on session-create,
 * disposed on session-end.
 */

import type { ILogger } from '@cassicore/foundation'

import {
  ObserverActivityScheduler,
  type ObserverActivityConfig,
  type ObserverFireReason,
} from '@cassicore/helix'

import { DigestCache, type DigestSynthesis } from './digest-cache.js'


/**
 * The substrate state the DMN samples each tick. The provider returns a
 * minimal monotonically-non-decreasing snapshot; the instance tracks the
 * delta against the previous tick and feeds that into the scheduler.
 */
export interface SessionActivitySnapshot {
  /** Total messages in the session history. Used as the primary delta signal. */
  historyLength: number
  /** Optional: cumulative tool calls observed in the session. */
  toolCallCount?: number
  /** Optional: cumulative thinking-stream chars observed in the session. */
  thinkingChars?: number
  /** Optional: text of the most recent user message (for richer observer prompts). */
  lastUserMessage?: string
  /** Optional: text of the most recent assistant response (for richer observer prompts). */
  lastAssistantText?: string
}


export type SessionActivitySnapshotProvider = (sessionId: string) => SessionActivitySnapshot | null


export interface DmnInstanceOpts {
  sessionId: string
  logger: ILogger
  schedulerConfig: ObserverActivityConfig
  /** Tick interval for the AGOP poll loop. Default 8s. */
  pollIntervalMs?: number
  /** Substrate sampler. Returns null if the session is gone. */
  getActivitySnapshot: SessionActivitySnapshotProvider
  /**
   * Per-fire handler. Default-no-op until late-bound by the daemon-boot
   * wiring (which calls dialecticSystem.processTurn).
   */
  onFire?: (reason: ObserverFireReason, sessionId: string) => Promise<DigestSynthesis | null>
}


const DEFAULT_POLL_INTERVAL_MS = 8_000


export class DmnInstance {
  readonly sessionId: string
  private logger: ILogger
  private cache = new DigestCache()
  private scheduler?: ObserverActivityScheduler
  private schedulerConfig: ObserverActivityConfig
  private pollIntervalMs: number
  private getActivitySnapshot: SessionActivitySnapshotProvider
  private onFire?: (reason: ObserverFireReason, sessionId: string) => Promise<DigestSynthesis | null>
  private fireCount = 0
  private running = false
  private shutdownRequested = false
  private loopPromise: Promise<void> | null = null
  private cancelSleep?: () => void
  private lastSnapshot: SessionActivitySnapshot = { historyLength: 0, toolCallCount: 0, thinkingChars: 0 }


  constructor(opts: DmnInstanceOpts) {
    this.sessionId = opts.sessionId
    this.logger = opts.logger.child?.(`dmn:${opts.sessionId.slice(0, 8)}`) ?? opts.logger
    this.schedulerConfig = opts.schedulerConfig
    this.pollIntervalMs = opts.pollIntervalMs ?? DEFAULT_POLL_INTERVAL_MS
    this.getActivitySnapshot = opts.getActivitySnapshot
    this.onFire = opts.onFire
  }


  /**
   * Start the AGOP tick loop. Idempotent.
   */
  start(): void {
    if (this.running) return
    this.running = true
    this.shutdownRequested = false
    this.scheduler = new ObserverActivityScheduler(
      this.schedulerConfig,
      (reason) => this.fireOnce(reason),
      this.logger,
    )
    this.loopPromise = this.tickLoop()
    this.logger.debug('DMN instance started (AGOP)', {
      sessionId: this.sessionId,
      pollIntervalMs: this.pollIntervalMs,
      cooldownMs: this.schedulerConfig.cooldownMs,
      materialThreshold: this.schedulerConfig.materialThreshold,
    })
  }


  /**
   * Stop the tick loop and dispose the scheduler. Idempotent.
   */
  async stop(): Promise<void> {
    if (!this.running) return
    this.shutdownRequested = true
    this.cancelSleep?.()
    if (this.loopPromise) {
      try { await this.loopPromise } catch { /* drained */ }
      this.loopPromise = null
    }
    if (this.scheduler) {
      this.scheduler.fireTerminal()
      this.scheduler.stop()
      this.scheduler = undefined
    }
    this.running = false
    this.logger.debug('DMN instance stopped', { sessionId: this.sessionId, fireCount: this.fireCount })
  }


  /**
   * Read the most-recent completed digest, or null if no cycle has
   * completed. Never blocks on an in-flight cycle.
   */
  getDigest(): DigestSynthesis | null {
    return this.cache.read()
  }


  /**
   * Replace the fire handler in-place. Used by late-binding wiring in the
   * daemon boot path so the DMN can be constructed before the dialectic's
   * providers are ready.
   */
  setOnFire(onFire: (reason: ObserverFireReason, sessionId: string) => Promise<DigestSynthesis | null>): void {
    this.onFire = onFire
  }

  /**
   * Replace the activity snapshot provider in-place. Used by Dmn when
   * wrapping the primary provider with external-session fallback after
   * the instance has already been created.
   */
  setActivitySnapshotProvider(provider: SessionActivitySnapshotProvider): void {
    this.getActivitySnapshot = provider
  }


  /**
   * Telemetry surface for tests and observability.
   */
  stats(): { fireCount: number; running: boolean; cache: ReturnType<DigestCache['state']> } {
    return { fireCount: this.fireCount, running: this.running, cache: this.cache.state() }
  }


  /**
   * Record activity from an external source (e.g. the CC proxy requesting
   * a digest). This feeds the scheduler directly without sampling the
   * substrate, so the DMN knows the session is active even when the proxy
   * is its only communication channel.
   */
  recordExternalActivity(): void {
    this.scheduler?.recordEvent()
  }


  /**
   * Sample the substrate once — exposed for tests so the tick cadence can
   * be bypassed. Production code reaches this via the tick loop.
   */
  discoverActivity(): void {
    if (!this.scheduler) return
    let snapshot: SessionActivitySnapshot | null
    try {
      snapshot = this.getActivitySnapshot(this.sessionId)
    } catch (err) {
      this.logger.debug('DMN getActivitySnapshot failed', { error: String(err) })
      return
    }
    if (!snapshot) return

    const historyDelta = Math.max(0, snapshot.historyLength - this.lastSnapshot.historyLength)
    const toolDelta = Math.max(0, (snapshot.toolCallCount ?? 0) - (this.lastSnapshot.toolCallCount ?? 0))
    const thinkingDelta = Math.max(0, (snapshot.thinkingChars ?? 0) - (this.lastSnapshot.thinkingChars ?? 0))

    if (historyDelta > 0 || toolDelta > 0 || thinkingDelta > 0) {
      this.scheduler.recordEvent()
    }

    this.lastSnapshot = {
      historyLength: snapshot.historyLength,
      toolCallCount: snapshot.toolCallCount ?? 0,
      thinkingChars: snapshot.thinkingChars ?? 0,
    }
  }


  /** AGOP tick loop. Runs until shutdownRequested is set. */
  private async tickLoop(): Promise<void> {
    while (!this.shutdownRequested) {
      await this.sleep(this.pollIntervalMs)
      if (this.shutdownRequested) break
      this.discoverActivity()
    }
  }


  /** Cancellable sleep — resolves either on the timer or on `cancelSleep()`. */
  private sleep(ms: number): Promise<void> {
    return new Promise<void>(resolve => {
      const timer = setTimeout(() => {
        this.cancelSleep = undefined
        resolve()
      }, ms)
      this.cancelSleep = () => {
        clearTimeout(timer)
        this.cancelSleep = undefined
        resolve()
      }
    })
  }


  /** Internal: invoked by the scheduler when threshold is crossed. */
  private async fireOnce(reason: ObserverFireReason): Promise<void> {
    if (this.shutdownRequested && reason !== 'terminal') return
    this.fireCount++
    this.cache.markInFlight()

    if (!this.onFire) {
      this.logger.debug('DMN fire (no-op stub)', { reason, fireCount: this.fireCount })
      this.cache.markCompleted({ hasSignal: false })
      return
    }

    try {
      const synthesis = await this.onFire(reason, this.sessionId)
      this.cache.markCompleted(synthesis ?? { hasSignal: false })
    } catch (err) {
      this.logger.warn('DMN fire failed; marking cache empty', { error: String(err) })
      this.cache.markCompleted({ hasSignal: false })
    }
  }
}
