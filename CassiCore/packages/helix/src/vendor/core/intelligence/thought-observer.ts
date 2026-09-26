/**
 * VENDORED TYPE STUB — mirrors `thought-observer.js` `CognitiveSignal` surface
 * (the thinking-stream signal extracted by ThoughtObserver). Helix consumes
 * `CognitiveSignal` via brainstem-types. Self-contained: single file.
 */

export type SignalKind =
  | 'edge_case'
  | 'assumption'
  | 'tension'
  | 'gap'
  | 'convergence'
  | 'insight'
  | 'memory_note'
  | 'search_intent'
  | 'code_intent'
  | 'memory_intent'
  | 'context_intent'

/** A cognitive signal extracted from the LLM's thinking stream. */
export interface CognitiveSignal {
  kind: SignalKind
  text: string
  confidence: number
}
