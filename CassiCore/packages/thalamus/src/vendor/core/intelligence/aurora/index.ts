/**
 * VENDORED — temporary type surface of `core/intelligence/aurora/index.ts`.
 * Consumed by @cassicore/thalamus index.ts as `Aurora` (type-only).
 *
 * `Aurora` is the explicitly-wired cognitive state module. Thalamus holds it as a
 * class type and calls a small surface (`buildState`, `serialize`, `observeReasoning`,
 * `updateFeatureNarrative`, `setReverieInferenceProvider`). Only those members are
 * declared here. Re-point to `@cassicore/aurora` when that package lands (P5-A turn 2).
 */
import type { ReverieInferenceProvider } from './types.js'

/** A rendered cognitive-state snapshot (opaque to the consumer). */
export type AuroraState = unknown

/** The Aurora cognitive-state module (type surface). */
export declare class Aurora {
  /** Build a mental-state snapshot from current focus signals. */
  buildState(foci: unknown[]): AuroraState
  /** Serialize a mental state for context injection. */
  serialize(state: AuroraState): string
  /** Forward assistant reasoning for cognitive state feedback (fast + Reverie slow path). */
  observeReasoning(text: string): void
  /** Regenerate the feature narrative from recent context. */
  updateFeatureNarrative(contextText: string): Promise<void>
  /** Wire the Reverie inference provider for the reasoning slow path. */
  setReverieInferenceProvider(provider: ReverieInferenceProvider): void
}
