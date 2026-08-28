/**
 * @dep callers: (new utility — will be adopted by centralized.ts, dialectic-voice-base.ts, helix-pipeline.ts, openai-compatible-base.ts, qwen.ts)
 * @dep module: Providers, Intelligence
 * @dep risk: LOW | new utility, no existing callers yet
 */

import { signalPromise } from './abort.js'

export interface ActivityTimeoutOptions {
  /** Time of silence (no touch() calls) before firing. */
  inactivityMs: number
  /** Absolute hard cap from creation. If omitted, only inactivity triggers abort. */
  maxDurationMs?: number
  /** Human-readable label for logging/telemetry. */
  label?: string
  /** External signal to compose with (caller abort, parent timeout). */
  parentSignal?: AbortSignal
}

export type TimeoutReason = 'inactivity' | 'max_duration' | 'parent_signal'

/**
 * Activity-aware timeout that resets on streaming activity.
 *
 * Three abort sources:
 * 1. Inactivity — no touch() within inactivityMs
 * 2. Hard cap — maxDurationMs elapsed since construction
 * 3. Parent signal — external AbortSignal fired
 *
 * Usage:
 *   const at = new ActivityTimeout({ inactivityMs: 60_000, maxDurationMs: 1_200_000 })
 *   for await (const chunk of stream) { at.touch(); yield chunk }
 *   // in finally: at.dispose()
 */
export class ActivityTimeout {
  readonly signal: AbortSignal
  reason: TimeoutReason | null = null

  private controller: AbortController
  private inactivityTimer: ReturnType<typeof setTimeout> | null = null
  private hardCapTimer: ReturnType<typeof setTimeout> | null = null
  private disposed = false
  private lastTouchAt: number
  private readonly inactivityMs: number

  constructor(opts: ActivityTimeoutOptions) {
    this.controller = new AbortController()
    this.signal = this.controller.signal
    this.inactivityMs = opts.inactivityMs
    this.lastTouchAt = Date.now()

    this.startInactivityTimer()

    if (opts.maxDurationMs != null) {
      this.hardCapTimer = setTimeout(() => {
        this.fire('max_duration')
      }, opts.maxDurationMs)
    }

    if (opts.parentSignal) {
      if (opts.parentSignal.aborted) {
        this.fire('parent_signal')
      } else {
        signalPromise(opts.parentSignal)
          .then(() => this.fire('parent_signal'))
          .catch(() => {})
      }
    }
  }

  /** Reset the inactivity timer. Call on every chunk/activity. */
  touch(): void {
    if (this.disposed || this.signal.aborted) return
    this.lastTouchAt = Date.now()
    this.restartInactivityTimer()
  }

  /** Clean up all timers. Idempotent. */
  dispose(): void {
    if (this.disposed) return
    this.disposed = true
    if (this.inactivityTimer) { clearTimeout(this.inactivityTimer); this.inactivityTimer = null }
    if (this.hardCapTimer) { clearTimeout(this.hardCapTimer); this.hardCapTimer = null }
  }

  get fired(): boolean {
    return this.signal.aborted
  }

  /** Milliseconds since the last touch() (or construction if never touched). */
  get silentMs(): number {
    return Date.now() - this.lastTouchAt
  }

  /**
   * Wrap an async iterable, calling touch() after each yielded item.
   * The caller's for-await loop receives items unchanged.
   */
  static async *wrapIterator<T>(
    iter: AsyncIterable<T>,
    timeout: ActivityTimeout,
  ): AsyncIterable<T> {
    for await (const item of iter) {
      timeout.touch()
      yield item
    }
  }

  private fire(reason: TimeoutReason): void {
    if (this.disposed || this.signal.aborted) return
    this.reason = reason
    try { this.controller.abort() } catch {}
    this.dispose()
  }

  private startInactivityTimer(): void {
    this.inactivityTimer = setTimeout(() => {
      this.fire('inactivity')
    }, this.inactivityMs)
  }

  private restartInactivityTimer(): void {
    if (this.inactivityTimer) clearTimeout(this.inactivityTimer)
    this.startInactivityTimer()
  }
}
