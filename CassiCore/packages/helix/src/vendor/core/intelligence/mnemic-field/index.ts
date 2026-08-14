/**
 * VENDORED TYPE STUB — mirrors `mnemic-field/index.js` `MnemicField` type
 * surface (the class lives in the daemon; only the method surface consumed by
 * Helix is declared here, structurally faithful to the D: original). Helix
 * calls `store`, `connect`, and `classifyPhrase`. Self-contained: all
 * supporting engram/synapse types are inlined locally.
 */

/** Engram node type — union over the ENGRAM_TYPES array. */
export type EngramType =
  | 'fact' | 'episode' | 'decision' | 'pattern'
  | 'abstraction' | 'goal' | 'file' | 'tool' | 'session' | 'outcome'
  | 'source_file' | 'changeset' | 'artifact' | 'concern' | 'anomaly'
  | 'module' | 'capability' | 'principle' | 'weakness' | 'evolution' | 'portal'
  | 'bridge' | 'synthesized_invariant' | 'intent_span' | 'thought_command'
  | 'replay_segment' | 'expert_summary' | 'file_version' | 'file_read'
  | 'tool_invocation' | 'message' | 'pineal_facet' | 'error_report'
  | 'search_finding' | 'code_change' | 'test_result' | 'build_output'
  | 'spatial_feature' | 'attractor' | 'generation' | 'visual_memory'

/** Synapse edge type — union over the SYNAPSE_TYPES array. */
export type SynapseType =
  | 'similar_to' | 'contradicts' | 'supports'
  | 'caused_by' | 'led_to' | 'used_in_task' | 'part_of'
  | 'temporal_neighbor' | 'supersedes' | 'about_file' | 'spawned_from'
  | 'imports' | 'modified_by' | 'co_changed' | 'contains_symbol'
  | 'depends_on' | 'implements' | 'uses_pattern' | 'governed_by'
  | 'evolved_from' | 'enables' | 'constrains' | 'mitigates' | 'portal_link'
  | 'responds_to' | 'triggered_by' | 'commands' | 'expert_summary'
  | 'injected_for' | 'contains' | 'created_in' | 'produces'
  | 'operated_on' | 'vindex_correlation' | 'cross_modal'
  | 'activated_by' | 'visual_similar'

export interface Engram {
  id: string
  content: string
  nodeType: EngramType
  x: number
  y: number
  z: number
  t: number
  potentiation: number
  clusterId: string | null
  embedding: Float32Array | null
  tags: string[]
  provenance: string
  createdAt: string
  accessedAt: string | null
  metadata: Record<string, unknown>
}

export interface EngramCreate {
  id?: string
  content: string
  nodeType: EngramType
  x?: number
  y?: number
  z?: number
  r?: number
  theta?: number
  t?: number
  initialPotentiation?: number
  embedding?: Float32Array | number[] | null
  tags?: string[]
  provenance?: string
  createdAt?: string
  metadata?: Record<string, unknown>
}

export interface MnemicSynapse {
  sourceId: string
  targetId: string
  edgeType: SynapseType
  weight: number
  createdAt: string
  metadata: Record<string, unknown>
}

export interface SynapseCreate {
  sourceId: string
  targetId: string
  edgeType: SynapseType
  weight?: number
  metadata?: Record<string, unknown>
}

export interface EngramSearchResult {
  engram: Engram
  score: number
}

export interface MnemicRetrievalHit {
  id: string
  content: string
  nodeType: EngramType
  score: number
  charge: number
  potentiation: number
  provenance: string
  tags: string[]
  metadata: Record<string, unknown>
}

export interface FieldStats {
  engramCount: number
  synapseCount: number
  spikeCount: number
  nucleusCount: number
  avgPotentiation: number
  topEngramsByPotentiation: Array<{ id: string; content: string; potentiation: number }>
}

/** A labeled prototype set for phrase classification (edge-relators). */
export interface PhrasePrototypeSet {
  labels: string[]
  [key: string]: unknown
}

export interface ClassificationResult {
  label: string | null
  score: number
}

/**
 * Faithful `MnemicField` surface — the methods Helix consumes (`store`,
 * `connect`, `classifyPhrase`) plus the core retrieval members Mira the D:
 * original class exposes.
 */
export interface MnemicField {
  store(input: EngramCreate): Engram
  update(id: string, update: { [key: string]: unknown }): Engram | null
  connect(input: SynapseCreate): MnemicSynapse
  retrieve(query: string, options?: Record<string, unknown>): Promise<MnemicRetrievalHit[]>
  searchText(query: string, limit?: number): EngramSearchResult[]
  classifyPhrase(text: string, prototypeSet: PhrasePrototypeSet, threshold?: number): Promise<ClassificationResult>
  list(limit?: number): Engram[]
  get(id: string): Engram | null
  stats(): FieldStats
  close(): void
  [key: string]: unknown
}
