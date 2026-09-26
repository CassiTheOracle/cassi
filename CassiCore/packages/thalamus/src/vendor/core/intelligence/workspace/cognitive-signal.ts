/**
 * VENDORED — faithful type surface of `core/intelligence/workspace/cognitive-signal.ts`.
 * Consumed by @cassicore/thalamus (types.ts, scorer.ts, slots/*) as
 * `SystemLuminanceScore`, `CognitiveSignal`, `SignalType` (type-only).
 * Re-point to `@cassicore/workspace` when that package lands (P5 repoint log).
 */

export type SignalType =
  | 'insight'
  | 'observation'
  | 'warning'
  | 'memory'
  | 'tension'
  | 'convergence'
  | 'suggestion'
  | 'context'
  | 'enrichment'
  | 'goal'
  | 'bridge'

/**
 * System-level luminance score — four dimensions of salience plus
 * resonance and strategic-importance.
 */
export interface SystemLuminanceScore {
  /** 0-1: Is this information new relative to what's already in the workspace? */
  novelty: number
  /** 0-1: How time-sensitive? Warnings score high, background context low. */
  urgency: number
  /** 0-1: How many active sessions / processing contexts benefit? */
  relevance: number
  /** 0-1: Track record of this source producing useful signals. */
  sourceCredibility: number
  /** 0-1: Alignment with current cognitive state. */
  cognitiveResonance: number
  /** 0-1: Enduring significance. */
  strategicImportance: number
  /** Weighted composite — the actual competition score. */
  composite: number
}

/** A cognitive signal submitted by a module to the Global Workspace. */
export interface CognitiveSignal {
  /** Unique identifier for this signal */
  signalId: string
  /** Module that produced this signal */
  source: string
  /** Session this signal applies to (or '*' for global signals) */
  sessionId: string
  /** Functional category */
  type: SignalType
  /** The actual payload — what the module wants to communicate */
  content: string
  /** Luminance score (set by the workspace's luminance scorer) */
  luminance: SystemLuminanceScore
  /** Coalition IDs this signal has joined */
  coalitionIds?: string[]
  /** When this signal was created */
  createdAt: number
  /** Optional urgency hint from the module */
  urgencyHint?: number
  /** Module-specific metadata for downstream tracing */
  metadata?: Record<string, unknown>
}
