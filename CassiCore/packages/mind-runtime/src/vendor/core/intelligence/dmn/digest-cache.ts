/**
 * DigestCache — current/previous digest with in-flight fallback.
 *
 * The DMN substrate fires post-turn-end and produces a digest that the
 * NEXT main-session turn injects into its system prompt. If turn N+1 starts
 * before turn N's fire completes, the cache returns the previous digest
 * (last completed) so the system prompt builder never blocks on an
 * in-flight cycle.
 *
 * State machine:
 *   empty → markInFlight → in-flight → markCompleted → completed
 *                                    ↘ markCompleted (next cycle) → completed
 *
 * Reads return the most recent COMPLETED digest. While in-flight, reads
 * return the previous completed (or null if none yet exists).
 */

/** Default half-life for observer confidence decay (5 minutes). */
export const DEFAULT_DMN_HALF_LIFE_MS = 5 * 60 * 1000

/** Confidence below this threshold is considered stale and the
 *  observer block is omitted from the system prompt. */
export const DMN_STALENESS_THRESHOLD = 0.1

export type DigestSynthesis = {
  hasSignal: boolean
  signal?: {
    type: string
    content: string
    /** Confidence at the time of synthesis (0–1). Decays over time. */
    confidence: number
    urgency?: string
  }
  branchesConsidered?: number
  branchesSurfaced?: number
  /** Timestamp (ms) when this synthesis was completed. */
  completedAt?: number
  /** Half-life in ms for exponential confidence decay (default 5 min). */
  halfLifeMs?: number
}

/** Compute the decayed confidence of a synthesis at a given point in time.
 *  Uses exponential decay: confidence * 0.5^(elapsed / halfLife).
 *  When completedAt is unset, treats the synthesis as fresh (no decay). */
export function decayedConfidence(
  synthesis: DigestSynthesis,
  now: number = Date.now(),
): { confidence: number; elapsedMs: number; isStale: boolean } {
  if (!synthesis.hasSignal || !synthesis.signal) {
    return { confidence: 0, elapsedMs: 0, isStale: true }
  }
  const completedAt = synthesis.completedAt
  // No timestamp = assume just-produced (backward compat)
  if (completedAt == null || completedAt <= 0) {
    return {
      confidence: synthesis.signal.confidence,
      elapsedMs: 0,
      isStale: false,
    }
  }
  const elapsedMs = Math.max(0, now - completedAt)
  const halfLifeMs = synthesis.halfLifeMs ?? DEFAULT_DMN_HALF_LIFE_MS

  if (halfLifeMs <= 0 || elapsedMs <= 0) {
    return {
      confidence: synthesis.signal.confidence,
      elapsedMs,
      isStale: false,
    }
  }

  const decayed = synthesis.signal.confidence * Math.pow(0.5, elapsedMs / halfLifeMs)
  return {
    confidence: Math.max(0, decayed),
    elapsedMs,
    isStale: decayed < DMN_STALENESS_THRESHOLD,
  }
}

type Slot =
  | { state: 'empty' }
  | { state: 'in-flight'; startedAt: number }
  | { state: 'completed'; synthesis: DigestSynthesis; completedAt: number }

export class DigestCache {
  private current: Slot = { state: 'empty' }
  private previous: Slot = { state: 'empty' }

  /**
   * Mark the current cycle as in-flight. Demotes the current completed
   * digest to previous so reads during the in-flight window return the
   * last good digest rather than nothing.
   */
  markInFlight(): void {
    if (this.current.state === 'completed') {
      this.previous = this.current
    }
    this.current = { state: 'in-flight', startedAt: Date.now() }
  }

  /**
   * Mark the current cycle as completed with the produced synthesis.
   * Replaces in-flight without touching previous.
   */
  markCompleted(synthesis: DigestSynthesis): void {
    this.current = {
      state: 'completed',
      synthesis: {
        ...synthesis,
        completedAt: synthesis.completedAt ?? Date.now(),
      },
      completedAt: Date.now(),
    }
  }

  /**
   * Read the most recent COMPLETED digest. Returns null if no cycle has
   * ever completed. While the current slot is in-flight, returns the
   * previous completed (or null).
   */
  read(): DigestSynthesis | null {
    if (this.current.state === 'completed') return this.current.synthesis
    if (this.previous.state === 'completed') return this.previous.synthesis
    return null
  }

  /**
   * Inspect current state for telemetry.
   */
  state(): { current: Slot['state']; previous: Slot['state'] } {
    return { current: this.current.state, previous: this.previous.state }
  }
}
