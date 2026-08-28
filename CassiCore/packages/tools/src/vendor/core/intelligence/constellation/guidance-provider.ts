/**
 * VENDOR TYPE STUB — `core/intelligence/constellation/guidance-provider.ts`
 * (`ConstellationGuidanceRegistry`).
 *
 * Type-placeholder for the constellation guidance registry surface consumed by
 * collect-thoughts.ts (tools) via
 * `deps.constellationGuidanceRegistry?.get(sessionId)`. The returned provider
 * must match the tools' local `ConstellationGuidanceProvider` interface
 * (`getGuidanceForThought(thought, step, sessionId): string | null`). Owned by
 * the P5 brain package; re-pointed when it lands (Open-6).
 */

/** A guidance provider that yields strategic Corpus guidance for a thought. */
export interface ConstellationGuidanceProvider {
  getGuidanceForThought(thought: string, step: number, sessionId: string): string | null
}

/** Registry that resolves per-constellation guidance providers. */
export interface ConstellationGuidanceRegistry {
  get(sessionId: string): ConstellationGuidanceProvider | undefined
}
