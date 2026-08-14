/**
 * VENDORED — temporary type surface of `core/intelligence/pineal/assembler.ts`.
 * Consumed by @cassicore/thalamus index.ts as `PinealAssembler` (type-only).
 *
 * Thalamus calls `assemble(sessionId)` to get the identity-facet injection text and
 * facet ids. Re-point to `@cassicore/cortex-pineal-dialectic` when that package
 * lands (P5-A turn 2).
 */

/** Assembled identity-facet injection (type surface). */
export interface PinealAssemblerResult {
  text: string
  facetIds: string[]
}

/** Pineal identity-facet assembler (type surface). */
export declare class PinealAssembler {
  /** Assemble the identity-facet context injection for a session. */
  assemble(sessionId: string): PinealAssemblerResult
}
