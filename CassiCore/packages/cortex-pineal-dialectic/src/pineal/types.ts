export const DOMAINS = ['identity', 'wisdom', 'philosophy', 'praxis'] as const
export type Domain = typeof DOMAINS[number]

export const PROVENANCES = [
  'soul.md', 'agents.md', 'skill-file',
  'user', 'meditation', 'self',
] as const
export type Provenance = typeof PROVENANCES[number]

export interface Facet {
  id: string
  domain: Domain
  category: string
  content: string
  conviction: number
  salience: number
  provenance: Provenance
  tags: string[]

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
  provenance?: Provenance
  tags?: string[]
  evolvedFrom?: string
}

export interface FacetUpdate {
  content?: string
  conviction?: number
  salience?: number
  tags?: string[]
  active?: boolean
}

export interface FacetQuery {
  domain?: Domain
  category?: string
  active?: boolean
  minConviction?: number
  tags?: string[]
  limit?: number
}

export interface DomainStats {
  domain: Domain
  totalFacets: number
  activeFacets: number
  avgConviction: number
  categories: string[]
}

export interface PinealSnapshot {
  facets: Facet[]
  domains: DomainStats[]
  timestamp: string
}

export interface SkillSummary {
  name: string
  description: string
  facetCount: number
  avgConviction: number
}

/**
 * Initial conviction for new facets per domain.
 * All facets start low and earn strength through use.
 */
export const DOMAIN_INITIAL_CONVICTION: Record<Domain, number> = {
  identity: 0.3,
  wisdom: 0.2,
  philosophy: 0.15,
  praxis: 0.2,
}

/**
 * Reinforcement increment: +REINFORCEMENT_RATE × (1 - conviction)
 * Produces asymptotic growth — rapid early, diminishing near ceiling.
 */
export const REINFORCEMENT_RATE = 0.02
