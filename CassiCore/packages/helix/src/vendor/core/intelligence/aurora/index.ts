/**
 * VENDORED TYPE STUB — mirrors `aurora/index.js` `Aurora` type surface (the
 * runtime class lives in the daemon). Helix consumes `Aurora` as a type and
 * calls `observeReasoning(text)` at posture turn boundaries. Supporting
 * mental-state types are declared locally, self-contained.
 */

export type ReasoningShiftType =
  | 'topic_change'
  | 'focus_narrow'
  | 'focus_widen'
  | 'escalation'
  | 'deescalation'
  | 'none'

export interface ReasoningShift {
  type: ReasoningShiftType
  from?: string
  to?: string
  confidence?: number
}

export interface ReasoningMomentum {
  confidence: number
  direction?: string
  magnitude?: number
}

/** Return type of `Aurora.observeReasoning`. */
export interface MentalStateUpdate {
  /** Activated cognitive nodes from the observed text. */
  activatedNodes: unknown[]
  /** Newly created cognitive edges. */
  newEdges: unknown[]
  /** Affect delta observed in the text (null when none). */
  affectDelta: unknown
  /** Reasoning shift detected (null when none). */
  shift: ReasoningShift | null
  /** Momentum of the current reasoning (always present). */
  momentum: ReasoningMomentum
  /** Concepts extracted from the observed text. */
  extractedConcepts: string[]
  /** Duration of the observation pass in ms. */
  durationMs: number
  /** Reverie insights produced (empty when not analyzed). */
  reverieInsights: unknown[]
  /** Whether Reverie analysis ran for this turn. */
  reverieAnalyzed: boolean
  [key: string]: unknown
}

/**
 * Faithful `Aurora` surface — the method Helix consumes (`observeReasoning`)
 * plus an open index signature for the broader daemon class members.
 */
export interface Aurora {
  observeReasoning(text: string): MentalStateUpdate
  [key: string]: unknown
}
