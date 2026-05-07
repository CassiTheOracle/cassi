/**
 * ObserverActivityScheduler — activity-gated firing for LLM observers.
 *
 * Replaces clock-driven `pollIntervalMs` polling with event-driven firing
 * that activates only when the observed channel has produced enough new
 * material. Designed for the GWT-native observer pattern (HelixSynapse,
 * ClusterObserverLayer, CorpusObserverLayer) where the substrate being
 * observed is itself event-driven.
 *
 * Trigger logic:
 *   - cooldownMs is a hard rate cap — observer never fires faster than this.
 *   - materialThreshold + cooldown: when activity counter ≥ threshold AND
 *     cooldown has elapsed, fire.
 *   - maxIdleMs is a staleness ceiling — even on a quiet field, observer
 *     fires at this interval to confirm equanimity.
 *   - warmupEvents: cold-start floor; first fire is suppressed until at
 *     least this many events have arrived.
 *   - fireTerminal(): bypass cooldown for one final fire on scope completion
 *     (e.g. Helix completed) so the observer can summarize the run.
 *
 * Failure isolation: fireFn callback exceptions are swallowed and logged
 * (when a logger is provided), so a misbehaving observer can't break the
 * scheduler's accounting.
 */

export type ObserverFireReason = 'material' | 'idle' | 'terminal'

export interface ObserverActivityConfig {
  /** Min wall time between fires (rate cap). */
  cooldownMs: number
  /** Max wall time without fires (staleness ceiling). Set to Infinity to disable. */
  maxIdleMs: number
  /** Activity counter value at which observer wakes (between cooldowns). */
  materialThreshold: number
  /** Min events that must arrive before the first fire ever happens. */
  warmupEvents: number
}

export type FireFn = (reason: ObserverFireReason) => Promise<void> | void

interface SchedulerLogger {
  debug?: (msg: string, meta?: Record<string, unknown>) => void
  warn?: (msg: string, meta?: Record<string, unknown>) => void
}

export class ObserverActivityScheduler {
  private activityCount = 0
  private lastFireAt: number | null = null
  private warmedUp = false
  private warmedUpAt: number | null = null
  private idleCheckTimer?: ReturnType<typeof setInterval>
  private firing = false
  private stopped = false

  constructor(
    private readonly config: ObserverActivityConfig,
    private readonly fireFn: FireFn,
    private readonly logger?: SchedulerLogger,
  ) {
    if (config.maxIdleMs < config.cooldownMs && Number.isFinite(config.maxIdleMs)) {
      throw new Error(
        `maxIdleMs (${config.maxIdleMs}) must be >= cooldownMs (${config.cooldownMs}) — otherwise the idle floor is unreachable`,
      )
    }
    if (Number.isFinite(config.maxIdleMs)) {
      const tickMs = Math.max(1_000, Math.floor(config.cooldownMs / 4))
      this.idleCheckTimer = setInterval(() => this.checkIdle(), tickMs)
      if (typeof this.idleCheckTimer === 'object' && 'unref' in this.idleCheckTimer) {
        ;(this.idleCheckTimer as { unref?: () => void }).unref?.()
      }
    }
  }

  recordEvent(): void {
    if (this.stopped) return
    this.activityCount++
    if (!this.warmedUp && this.activityCount >= this.config.warmupEvents) {
      this.warmedUp = true
      this.warmedUpAt = Date.now()
    }
    void this.maybeFire()
  }

  fireTerminal(): void {
    if (this.stopped) return
    void this.runFire('terminal')
  }

  stop(): void {
    this.stopped = true
    if (this.idleCheckTimer) {
      clearInterval(this.idleCheckTimer)
      this.idleCheckTimer = undefined
    }
  }

  /** Inspection — used by tests + future telemetry. */
  snapshot(): {
    activityCount: number
    msSinceLastFire: number
    warmedUp: boolean
    stopped: boolean
  } {
    return {
      activityCount: this.activityCount,
      msSinceLastFire: this.lastFireAt === null ? Infinity : Date.now() - this.lastFireAt,
      warmedUp: this.warmedUp,
      stopped: this.stopped,
    }
  }

  private async maybeFire(): Promise<void> {
    if (this.firing || this.stopped) return
    if (!this.warmedUp) return
    const now = Date.now()
    const idleSinceFire = this.lastFireAt === null ? Infinity : now - this.lastFireAt
    if (idleSinceFire < this.config.cooldownMs) return

    if (this.activityCount >= this.config.materialThreshold) {
      await this.runFire('material')
      return
    }

    // Idle gate: measured from last fire if any; otherwise from warmup completion.
    // Fires periodically post-warmup to confirm equanimity even on quiet fields.
    const idleSinceReference = this.lastFireAt !== null
      ? now - this.lastFireAt
      : this.warmedUpAt !== null ? now - this.warmedUpAt : 0
    if (idleSinceReference >= this.config.maxIdleMs) {
      await this.runFire('idle')
    }
  }

  private checkIdle(): void {
    if (this.stopped || this.firing || !this.warmedUp) return
    if (!Number.isFinite(this.config.maxIdleMs)) return
    const now = Date.now()
    const idleSinceFire = this.lastFireAt === null ? Infinity : now - this.lastFireAt
    if (idleSinceFire < this.config.cooldownMs) return
    const idleSinceReference = this.lastFireAt !== null
      ? now - this.lastFireAt
      : this.warmedUpAt !== null ? now - this.warmedUpAt : 0
    if (idleSinceReference >= this.config.maxIdleMs) {
      void this.runFire('idle')
    }
  }

  private async runFire(reason: ObserverFireReason): Promise<void> {
    if (this.firing) return
    this.firing = true
    const activityAtFire = this.activityCount
    this.lastFireAt = Date.now()
    this.activityCount = 0
    this.logger?.debug?.('[scheduler] firing', {
      reason,
      activityAtFire,
      cooldownMs: this.config.cooldownMs,
    })
    try {
      await this.fireFn(reason)
    } catch (err) {
      this.logger?.warn?.('[scheduler] fireFn threw — observer call lost but counter preserved', {
        reason,
        error: String(err),
      })
    } finally {
      this.firing = false
    }
  }
}
