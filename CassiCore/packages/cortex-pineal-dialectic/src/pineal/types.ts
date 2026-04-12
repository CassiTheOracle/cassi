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
  pinned: boolean
  scope: string | null  // null = universal, "opencode" | "mcp" | etc. = channel-scoped

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
  pinned?: boolean
  scope?: string | null
  evolvedFrom?: string
}

export interface FacetUpdate {
  content?: string
  conviction?: number
  salience?: number
  tags?: string[]
  active?: boolean
  pinned?: boolean
  scope?: string | null
}

export interface FacetQuery {
  domain?: Domain
  category?: string
  active?: boolean
  pinned?: boolean
  scope?: string | null     // filter: null = only universal, string = only that channel
  matchScope?: string | null  // assembly filter: include universal + matching channel
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

/**
 * Known channel identifiers for scope-aware facet assembly.
 * Session IDs are prefixed with these identifiers (e.g., "oc:abc123").
 * Facets with scope matching a channel are only assembled for that channel's sessions.
 */
export const CHANNEL_PREFIXES: Record<string, string> = {
  'oc:': 'opencode',
  'mcp:': 'mcp',
  'web:': 'web',
  'vscode:': 'vscode',
}

/**
 * Extract the channel identifier from a session ID prefix.
 * Returns null for internal/unknown sessions (universal facets only).
 */
export function channelFromSessionId(sessionId: string | undefined): string | null {
  if (!sessionId) return null
  for (const [prefix, channel] of Object.entries(CHANNEL_PREFIXES)) {
    if (sessionId.startsWith(prefix)) return channel
  }
  return null
}
