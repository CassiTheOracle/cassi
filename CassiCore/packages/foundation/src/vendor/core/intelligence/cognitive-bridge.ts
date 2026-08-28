/**
 * VENDOR TYPE STUB — `core/intelligence/cognitive-bridge.ts`
 *
 * Type-only placeholder for the `ResonancePattern` surface consumed by the P1 live-set
 * (`types/collect-thoughts.ts`). Self-contained; builtin types only; no runtime.
 * Re-pointed to `@cassicore/cortex` (or owning bridge pkg) at P5.
 */

/** Shape of a cognitive signal as referenced by a resonance pattern. */
export interface CognitiveSignalRef {
  kind: string
  text: string
  confidence: number
}

/** A cross-session resonance pattern between two cognitive signals. */
export interface ResonancePattern {
  kind: 'resonance' | 'tension'
  signalA: { sessionId: string; signal: CognitiveSignalRef }
  signalB: { sessionId: string; signal: CognitiveSignalRef }
  similarity: number
  amplifiedConfidence: number
  detectedAt: number
}
