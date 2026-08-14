/**
 * VENDOR TYPE STUB — `core/intelligence/thought-observer.ts`
 *
 * Type-only placeholder for the cognitive-signal surface consumed by the P1 live-set
 * (`types/collect-thoughts.ts`, `types/events.ts`). Self-contained; builtin types only;
 * no runtime. Re-pointed to `@cassicore/reflective` (or owning observer pkg) at P5.
 */

/** A cognitive signal extracted from the LLM's thinking stream. */
export interface CognitiveSignal {
  kind: SignalKind
  text: string
  confidence: number
}

/** The kinds of cognitive signals that can be extracted. */
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
