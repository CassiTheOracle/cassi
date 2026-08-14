/**
 * VENDORED — temporary type surface of `core/intelligence/pineal/facet.ts`.
 * Consumed by @cassicore/thalamus index.ts as `FacetManager` (type-only).
 *
 * Thalamus calls `reinforceMany` (turn:end reinforcement) and `list` (build the
 * pineal identity-priority context). Re-point to
 * `@cassicore/cortex-pineal-dialectic` when that package lands (P5-A turn 2).
 */

/** A pineal facet — an identity/priority signal (type surface). */
export interface PinealFacet {
  content: string
  conviction: number
}

/** Facet listing filter (type surface). */
export interface FacetFilter {
  active?: boolean
  minConviction?: number
  matchScope?: string | null
  limit?: number
}

/** Pineal facet manager (type surface). */
export declare class FacetManager {
  /** Reinforce facets by id — returns the count reinforced. */
  reinforceMany(facetIds: string[]): number
  /** List facets matching a filter. */
  list(filter?: FacetFilter): PinealFacet[]
}
