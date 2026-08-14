/**
 * VENDORED — temporary type surface of `core/intelligence/aurora/types.ts`.
 * Consumed by @cassicore/thalamus index.ts as `ReverieInferenceProvider`
 * (type-only, for wiring the Reverie slow-path provider into Aurora).
 * Re-point to `@cassicore/aurora` when that package lands (P5-A turn 2).
 */

/** Reverie LLM slow-path inference provider (type surface). */
export interface ReverieInferenceProvider {
  infer(
    messages: Array<{ role: string; content: string }>,
    options: {
      maxTokens: number
      temperature: number
      signal?: AbortSignal
    },
  ): Promise<string>
}
