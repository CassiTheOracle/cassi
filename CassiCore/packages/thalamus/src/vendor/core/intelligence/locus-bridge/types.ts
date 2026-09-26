/**
 * VENDORED — faithful type surface of `core/intelligence/locus-bridge/types.ts`.
 * Consumed by @cassicore/thalamus types.ts as `BridgeFocus` (type-only).
 * Re-point to `@cassicore/lamina` when that package lands (P5 repoint log).
 */

/** Bridge spark types — session events rather than branch digests. */
export type BridgeSparkType =
  | 'user-intent'
  | 'tool-discovery'
  | 'memory-recall'
  | 'code-reference'
  | 'constellation-radiance'
  | 'compaction-recovery'
  | 'reasoning_block'

/** Bridge luminance scoring — adapted for session context. */
export interface BridgeLuminanceScore {
  novelty: number
  urgency: number
  relevance: number
  sourceCredibility: number
  composite: number
}

/** A BridgeSpark is a proposal from a session event competing for focus. */
export interface BridgeSpark {
  sparkId: string
  /** Session that produced this spark */
  sourceSessionId: string
  /** The content being proposed for attentional focus */
  content: string
  /** What kind of content this is */
  type: BridgeSparkType
  /** Composite salience score determining competition outcome */
  luminance: BridgeLuminanceScore
  /** When this spark was generated */
  sparkedAt: number
  /** Current task/intent at spark time */
  sourceGoal: string
  /** Files relevant to this spark */
  relevantFiles: string[]
}

/** A focus slot in the attentional workspace. */
export interface BridgeFocus {
  slotIndex: number
  spark: BridgeSpark | null
  occupiedSince: number | null
  occupancyTicks: number
  eclipsedSparkId?: string
}
