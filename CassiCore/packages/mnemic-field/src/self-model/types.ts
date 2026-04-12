import type { EngramType, SynapseType, KindlingOptions, MnemicRetrievalHit, TaskComplexity } from '../types.js'

/**
 * Self-Model engram types — semantic understanding of the codebase architecture.
 * These engrams represent knowledge *about* the system, not the source code itself.
 */
export const SELF_MODEL_ENGRAM_TYPES: readonly EngramType[] = [
  'module', 'capability', 'pattern', 'principle', 'weakness', 'evolution', 'portal',
] as const

/**
 * Self-Model synapse types — architectural relationships between components.
 */
export const SELF_MODEL_SYNAPSE_TYPES: readonly SynapseType[] = [
  'depends_on', 'implements', 'uses_pattern', 'governed_by',
  'evolved_from', 'enables', 'constrains', 'mitigates', 'portal_link',
] as const

export interface ModuleMetadata {
  path: string
  domain: string
  maturity: 'experimental' | 'developing' | 'stable' | 'foundational'
  cluster?: string
  dependentCount?: number
  dependencyCount?: number
  complexityScore?: number
  lastSyncedAt?: string
}

export interface CapabilityMetadata {
  implementedBy: string[]
  active: boolean
  userFacing?: string
}

export interface PatternMetadata {
  occurrences: string[]
  category: 'activation' | 'lifecycle' | 'communication' | 'storage' | 'processing' | 'orchestration'
}

export interface WeaknessMetadata {
  severity: 'low' | 'medium' | 'high' | 'critical'
  affectedModules: string[]
  mitigated: boolean
  discoveredVia: 'analysis' | 'incident' | 'review' | 'testing'
}

export interface EvolutionMetadata {
  modulePath: string
  changeType: 'redesign' | 'refactor' | 'extension' | 'bugfix' | 'creation' | 'deprecation'
  commitHash?: string
  authorSessionId?: string
}

export interface PortalMetadata {
  fieldId: 'episodic' | 'self-model'
  linkedPortalId: string
  bridgeConcept: string
  dampening: number
}

/**
 * Default kindling options tuned for self-model retrieval.
 * Uses 'complex' complexity for the lowest spark point modifier (0.7),
 * making architectural knowledge easier to recall.
 */
export const SELF_MODEL_KINDLING_DEFAULTS: Partial<KindlingOptions> = {
  complexity: 'complex' as TaskComplexity,
  maxIterations: 4,
  maxLuminalSize: 20,
  maxSeeds: 15,
  enableFilaments: true,
}

export interface BridgeConfig {
  /** Charge dampening when propagating across fields (0-1). Lower = less bleed-through. */
  crossFieldDampening: number
  /** Maximum number of portal pairs. createPortalPair refuses beyond this. */
  maxPortals: number
  /** How many top hits from one field boost seeds in the other */
  crossPollinationLimit: number
  /** Score multiplier applied to preferred-field hits (1.0 = no preference) */
  fieldPreferenceBoost: number
}

export const BRIDGE_DEFAULTS: BridgeConfig = {
  crossFieldDampening: 0.4,
  maxPortals: 200,
  crossPollinationLimit: 5,
  fieldPreferenceBoost: 1.3,
}

/**
 * Extends MnemicRetrievalHit with cross-field provenance info.
 */
export interface CrossFieldRetrievalHit extends MnemicRetrievalHit {
  sourceField: 'episodic' | 'self-model'
  crossFieldBoosted: boolean
}

export interface CrossFieldResult {
  hits: CrossFieldRetrievalHit[]
  episodicCount: number
  selfModelCount: number
  crossFieldBoosts: number
  durationMs: number
}
