/**
 * VENDORED TYPE STUB — mirrors `core/intelligence/pineal/types.js` surface
 * consumed by lamina's `pineal-bridge` (`Domain`, `Facet`). Re-point to
 * `@cassicore/cortex` at P5-A (§P5b table §B2.2). Type-only — no runtime impl.
 */

export const DOMAINS = ['identity', 'wisdom', 'philosophy', 'praxis'] as const
export type Domain = typeof DOMAINS[number]

export interface Facet {
  id: string
  domain: Domain
  category: string
  content: string
  conviction: number
  salience: number
  provenance: string
  tags: string[]
  pinned: boolean
  scope: string | null
  evolvedFrom: string | null
  version: number
  createdAt: string
  lastReinforced: string
  reinforcements: number
  active: boolean
}

export interface FacetInput {
  domain: Domain
  category: string
  content: string
  conviction?: number
  salience?: number
  provenance?: string
  tags?: string[]
  pinned?: boolean
  scope?: string | null
  evolvedFrom?: string
}
