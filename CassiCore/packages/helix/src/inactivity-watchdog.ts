/**
 * InactivityWatchdog — three-stage escalation watchdog for long-running pipelines.
 *
 * Tracks time since the last activity touch and fires callbacks at three thresholds:
 *   - warnMs (default 120s)  — gentle reminder; continue if working, try alternative if stuck
 *   - escalateMs (default 240s) — high-severity nudge; wrap up
 *   - killMs (default 360s)  — hard cancel; stop the pipeline
 *
 * Each callback fires at most once per stuck-period. When activity resumes
 * (silentMs falls below warnMs), the warn/escalate flags reset so future
 * inactivity periods can re-fire.
 *
 * Extracted from helix-pipeline.ts (refactoring #4 from constellation c-27).
 *
 * @example
 *   const wd = new InactivityWatchdog({
 *     warnMs: 120_000,
 *     escalateMs: 240_000,
 *     killMs: 360_000,
 *     onWarn: (silentMs) => sendNudge('inactive 2 min'),
 *     onEscalate: (silentMs) => sendNudge('URGENT inactive 4 min', 'high'),
 *     onKill: (silentMs) => cancelAll(),
 *   })
 *   wd.touch() // every time activity occurs
 *   wd.dispose() // when pipeline ends
 */

export interface InactivityWatchdogOpts {
  /** Time in ms after which onWarn fires. Default 120_000. */
  warnMs?: number
  /** Time in ms after which onEscalate fires. Default 240_000. */
  escalateMs?: number
  /** Time in ms after which onKill fires (hard cancel). Default 360_000. */
  killMs?: number
  /** Polling interval for the inactivity check. Default 15_000. */
  checkIntervalMs?: number
  /** Fired once per stuck-period at warnMs. */
  onWarn?: (silentMs: number) => void
  /** Fired once per stuck-period at escalateMs. */
  onEscalate?: (silentMs: number) => void
  /** Fired at killMs — typically cancels the pipeline. */
  onKill?: (silentMs: number) => void
}

const DEFAULT_WARN_MS = 120_000
const DEFAULT_ESCALATE_MS = 240_000
const DEFAULT_KILL_MS = 360_000
const DEFAULT_CHECK_INTERVAL_MS = 15_000

export class InactivityWatchdog {
  private lastActivity: number = Date.now()
  private warnSent = false
  private escalated = false
  private killed = false
  private interval: ReturnType<typeof setInterval> | undefined
  private disposed = false

  private readonly warnMs: number
  private readonly escalateMs: number
  private readonly killMs: number
  private readonly onWarn?: (silentMs: number) => void
  private readonly onEscalate?: (silentMs: number) => void
  private readonly onKill?: (silentMs: number) => void

  constructor(opts: InactivityWatchdogOpts = {}) {
    this.warnMs = opts.warnMs ?? DEFAULT_WARN_MS
    this.escalateMs = opts.escalateMs ?? DEFAULT_ESCALATE_MS
    this.killMs = opts.killMs ?? DEFAULT_KILL_MS
    this.onWarn = opts.onWarn
    this.onEscalate = opts.onEscalate
    this.onKill = opts.onKill

    const checkIntervalMs = opts.checkIntervalMs ?? DEFAULT_CHECK_INTERVAL_MS
    this.interval = setInterval(() => this.tick(), checkIntervalMs)
  }

  /** Signal that activity occurred — resets the silent timer. */
  touch(): void {
    if (this.disposed) return
    this.lastActivity = Date.now()
  }

  /** Stop the watchdog. Safe to call multiple times. */
  dispose(): void {
    if (this.disposed) return
    this.disposed = true
    if (this.interval) {
      clearInterval(this.interval)
      this.interval = undefined
    }
  }

  /** Get current silent duration in ms (for testing/inspection). */
  get silentMs(): number {
    return Date.now() - this.lastActivity
  }

  private tick(): void {
    if (this.disposed) return
    const silentMs = this.silentMs

    // Stage 3: Hard kill — fire once, then dispose
    if (silentMs > this.killMs && !this.killed) {
      this.killed = true
      try { this.onKill?.(silentMs) } catch { /* swallow */ }
      this.dispose()
      return
    }

    // Stage 2: High-severity escalation
    if (silentMs > this.escalateMs && !this.escalated) {
      this.escalated = true
      try { this.onEscalate?.(silentMs) } catch { /* swallow */ }
      return
    }

    // Stage 1: Gentle warning
    if (silentMs > this.warnMs && !this.warnSent) {
      this.warnSent = true
      try { this.onWarn?.(silentMs) } catch { /* swallow */ }
      return
    }

    // Reset escalation flags when activity resumes
    if (silentMs < this.warnMs) {
      this.warnSent = false
      this.escalated = false
    }
  }
}
