import type {
  EngramType,
  SynapseType,
  KindlingOptions,
  MnemicRetrievalHit,
  TaskComplexity,
} from '../types.js'

/**
 * Knowledge engram types — external research and technique knowledge.
 * These map to existing EngramType values:
 *   paper → 'fact' (research fact)
 *   technique → 'pattern' (implementation pattern)
 *   finding → 'fact' (empirical result)
 *   survey → 'abstraction' (literature overview)
 *   algorithm → 'pattern' (algorithmic pattern)
 *   benchmark → 'outcome' (evaluation result)
 *   dataset → 'file' (data artifact)
 *   model → 'tool' (model as a tool)
 *
 * We store the semantic type in metadata.nodeType for filtering.
 */
export const KNOWLEDGE_SEMANTIC_TYPES = [
  'paper', 'technique', 'finding', 'survey',
  'algorithm', 'benchmark', 'dataset', 'model',
] as const

export type KnowledgeSemanticType = typeof KNOWLEDGE_SEMANTIC_TYPES[number]

/** Map semantic type to EngramType */
export function semanticToEngramType(semantic: KnowledgeSemanticType): EngramType {
  switch (semantic) {
    case 'paper': return 'fact'
    case 'technique': return 'pattern'
    case 'finding': return 'fact'
    case 'survey': return 'abstraction'
    case 'algorithm': return 'pattern'
    case 'benchmark': return 'outcome'
    case 'dataset': return 'file'
    case 'model': return 'tool'
  }
}

/**
 * Knowledge synapse types — relationships between research artifacts.
 * These map to existing SynapseType values:
 *   introduces → 'led_to'
 *   uses_algorithm → 'uses_pattern'
 *   evaluated_on → 'used_in_task'
 *   confirms → 'supports'
 *   contradicts → 'contradicts'
 *   extends → 'evolved_from'
 *   cites → 'depends_on'
 *   supersedes → 'supersedes'
 *   related_to → 'similar_to'
 *   implements → 'implements'
 *   improves_upon → 'enables'
 *   inspired_by → 'spawned_from'
 */
export const KNOWLEDGE_SEMANTIC_SYMAPSES = [
  'introduces', 'uses_algorithm', 'evaluated_on',
  'confirms', 'contradicts', 'extends',
  'cites', 'supersedes', 'related_to',
  'implements', 'improves_upon', 'inspired_by',
] as const

export type KnowledgeSemanticSynapse = typeof KNOWLEDGE_SEMANTIC_SYMAPSES[number]

/** Map semantic synapse to SynapseType */
export function semanticToSynapseType(semantic: KnowledgeSemanticSynapse): SynapseType {
  switch (semantic) {
    case 'introduces': return 'led_to'
    case 'uses_algorithm': return 'uses_pattern'
    case 'evaluated_on': return 'used_in_task'
    case 'confirms': return 'supports'
    case 'contradicts': return 'contradicts'
    case 'extends': return 'evolved_from'
    case 'cites': return 'depends_on'
    case 'supersedes': return 'supersedes'
    case 'related_to': return 'similar_to'
    case 'implements': return 'implements'
    case 'improves_upon': return 'enables'
    case 'inspired_by': return 'spawned_from'
  }
}

export interface PaperMetadata {
  authors: string[]
  year: number
  venue: string
  doi?: string
  url?: string
  citationCount?: number
  techniqueIds?: string[]
  /** Internal semantic type for filtering */
  knowledgeType: 'paper'
}

export interface TechniqueMetadata {
  domain: string
  hyperparameters?: Record<string, unknown>
  failureModes?: string[]
  implementationNotes?: string
  sourcePaperId?: string
  prerequisites?: string[]
  benchmarks?: Array<{
    dataset: string
    score: number
    baseline?: number
    metric: string
  }>
  knowledgeType: 'technique'
}

export interface FindingMetadata {
  confidence: 'low' | 'medium' | 'high'
  evidenceType: 'empirical' | 'theoretical' | 'anecdotal'
  sourcePaperId?: string
  replicationStatus?: 'replicated' | 'unreplicated' | 'disputed'
  knowledgeType: 'finding'
}

export interface SurveyMetadata {
  coverage: string[]
  paperCount: number
  conclusion: string
  knowledgeType: 'survey'
}

export interface AlgorithmMetadata {
  timeComplexity?: string
  spaceComplexity?: string
  category: string
  pseudocode?: string
  knowledgeType: 'algorithm'
}

export interface BenchmarkMetadata {
  dataset: string
  metric: string
  stateOfTheArt: number
  baseline: number
  year: number
  knowledgeType: 'benchmark'
}

/**
 * Default kindling options tuned for knowledge retrieval.
 * Uses 'simple' complexity for higher spark point = precision over breadth.
 * Research queries want the exact technique, not a broad neighborhood.
 */
export const KNOWLEDGE_KINDLING_DEFAULTS: Partial<KindlingOptions> = {
  complexity: 'simple' as TaskComplexity,
  maxIterations: 3,
  maxLuminalSize: 15,
  maxSeeds: 10,
  enableFilaments: true,
} as const

/**
 * Synapse propagation weights for knowledge relationships.
 * Causal/derivation chains are strongest; statistical relations weakest.
 */
export const KNOWLEDGE_SYNAPSE_PROPAGATION: Record<SynapseType, number> = {
  // Mapped from knowledge semantics
  led_to: 0.9,           // introduces
  supersedes: 0.9,       // supersedes
  evolved_from: 0.85,    // extends
  enables: 0.85,         // improves_upon
  uses_pattern: 0.8,     // uses_algorithm
  implements: 0.8,       // implements
  supports: 0.75,        // confirms
  contradicts: 0.75,     // contradicts
  used_in_task: 0.6,     // evaluated_on
  depends_on: 0.5,       // cites
  spawned_from: 0.5,     // inspired_by
  similar_to: 0.3,       // related_to
  // Existing types (defaults)
  caused_by: 0.9,
  part_of: 0.6,
  temporal_neighbor: 0.3,
  about_file: 0.5,
  modified_by: 0.3,
  co_changed: 0.6,
  contains_symbol: 0.4,
  governed_by: 0.6,
  constrains: 0.5,
  mitigates: 0.7,
  portal_link: 0.6,
  imports: 0.7,
  responds_to: 0.5,
  triggered_by: 0.4,
  commands: 0.3,
  expert_summary: 0.9,
  injected_for: 0.7,
  // Remaining SynapseType keys (non-knowledge defaults, mirror SYNAPSE_PROPAGATION)
  contains: 0.7,
  created_in: 0.5,
  produces: 0.85,
  operated_on: 0.8,
  vindex_correlation: 0.4,
  cross_modal: 0.45,
  activated_by: 0.7,
  visual_similar: 0.55,
} as const

/**
 * Paper/technique ingestion result.
 */
export interface KnowledgeIngestResult {
  papersCreated: number
  techniquesCreated: number
  findingsCreated: number
  algorithmsCreated: number
  benchmarksCreated: number
  synapsesCreated: number
  durationMs: number
}

/**
 * Ingestion options.
 */
export interface KnowledgeIngestOptions {
  /** Skip already-existing engrams matched by title/name */
  skipExisting?: boolean
  /** Minimum paper year to include */
  minYear?: number
  /** Create synapses between papers and techniques */
  createSynapses?: boolean
  /** Embedding provider for generating vectors */
  embeddingProvider?: (text: string) => Promise<number[] | null>
}

/**
 * Comparison result for knowledge_compare tool.
 */
export interface TechniqueComparison {
  techniqueA: { id: string; name: string; content: string; metadata: TechniqueMetadata }
  techniqueB: { id: string; name: string; content: string; metadata: TechniqueMetadata }
  sharedDomains: string[]
  contradictions: Array<{ claimA: string; claimB: string }>
  benchmarkDelta: Array<{
    dataset: string
    metric: string
    scoreA: number
    scoreB: number
    delta: number
  }>
}
