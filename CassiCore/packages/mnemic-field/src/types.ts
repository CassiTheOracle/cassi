export const ENGRAM_TYPES = [
  'fact', 'episode', 'decision', 'pattern',
  'abstraction', 'goal', 'file', 'tool', 'session', 'outcome',
  'source_file', 'changeset', 'artifact'
] as const

export type EngramType = typeof ENGRAM_TYPES[number]

export const SYNAPSE_TYPES = [
  'similar_to', 'contradicts', 'supports',
  'caused_by', 'led_to', 'used_in_task', 'part_of',
  'temporal_neighbor', 'supersedes', 'about_file', 'spawned_from',
  'imports', 'modified_by', 'co_changed', 'contains_symbol'
] as const

export type SynapseType = typeof SYNAPSE_TYPES[number]

export type SpikeOutcome = 'success' | 'failure' | 'unknown'

export interface Engram {
  id: string
  content: string
  nodeType: EngramType
  x: number
  y: number
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
  t?: number
  embedding?: Float32Array | number[] | null
  tags?: string[]
  provenance?: string
  metadata?: Record<string, unknown>
}

export interface EngramUpdate {
  content?: string
  nodeType?: EngramType
  x?: number
  y?: number
  t?: number
  potentiation?: number
  clusterId?: string | null
  embedding?: Float32Array | number[] | null
  tags?: string[]
  accessedAt?: string
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

export interface ActivationSpike {
  id: number
  engramId: string
  timestamp: number
  magnitude: number
  taskContext: string | null
  outcome: SpikeOutcome | null
}

export interface SpikeCreate {
  engramId: string
  magnitude: number
  taskContext?: string
  outcome?: SpikeOutcome
}

export interface Nucleus {
  id: string
  label: string
  centroidX: number
  centroidY: number
  memberCount: number
  avgPotentiation: number
  abstractionId: string | null
  createdAt: string
  updatedAt: string
}

export interface NucleusCreate {
  id?: string
  label: string
  centroidX: number
  centroidY: number
  abstractionId?: string
}

export interface SpatialQuery {
  xMin?: number
  xMax?: number
  yMin?: number
  yMax?: number
  tMin?: number
  tMax?: number
  potentiationMin?: number
  potentiationMax?: number
  limit?: number
}

export interface EngramSearchResult {
  engram: Engram
  score: number
}

export interface TensionPair {
  engramA: Engram
  engramB: Engram
  synapse: MnemicSynapse
  tension: number
}

export interface TensionReport {
  pairs: TensionPair[]
  totalTension: number
  highestTension: number
  recommendation: string
}

export interface FieldStats {
  engramCount: number
  synapseCount: number
  spikeCount: number
  nucleusCount: number
  avgPotentiation: number
  topEngramsByPotentiation: Array<{ id: string; content: string; potentiation: number }>
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

export const SYNAPSE_PROPAGATION: Record<SynapseType, number> = {
  caused_by: 0.9,
  led_to: 0.9,
  used_in_task: 0.85,
  supports: 0.8,
  contradicts: 0.8,
  part_of: 0.6,
  similar_to: 0.5,
  temporal_neighbor: 0.3,
  supersedes: 0.4,
  about_file: 0.5,
  spawned_from: 0.6,
  imports: 0.7,
  modified_by: 0.3,
  co_changed: 0.6,
  contains_symbol: 0.4,
}

export const POTENTIATION_DEFAULTS = {
  alphaMin: 0.1,
  alphaMax: 0.5,
  alphaTau: 10,
  decayRate: 0.5,
  pageRankDamping: 0.85,
  pageRankIterations: 20,
  convergenceThreshold: 0.001,
} as const

export const SPARK_POINT_DEFAULTS = {
  baseThreshold: 0.5,
  potentiationScale: 0.3,
  taskModifiers: {
    simple: 1.2,
    normal: 1.0,
    complex: 0.7,
    delegation: 0.5,
  },
} as const

export type TaskComplexity = keyof typeof SPARK_POINT_DEFAULTS.taskModifiers

export interface ChargedEngram {
  engram: Engram
  charge: number
}

export interface LuminalSet {
  engrams: ChargedEngram[]
  totalCharge: number
  seedCount: number
  iterationsUsed: number
  sparkPoint: number
  taskComplexity: TaskComplexity
  durationMs: number
}

export interface KindlingOptions {
  complexity?: TaskComplexity
  maxIterations?: number
  convergenceTolerance?: number
  maxSeeds?: number
  maxLuminalSize?: number
  includeText?: boolean
}

export const KINDLING_DEFAULTS = {
  maxIterations: 5,
  convergenceTolerance: 0.01,
  maxSeeds: 20,
  maxLuminalSize: 50,
  spreadDampening: 0.5,
  distanceDecayRate: 0.5,
  temporalDecayRate: 0.0001,
  potentiationBoostScale: 0.5,
  driftLearningRate: 0.02,
} as const

export type ChangesetStatus = 'pending' | 'committed' | 'verified' | 'failed'
export type ChangesetFileOperation = 'create' | 'modify' | 'delete'

export interface Changeset {
  id: string
  description: string
  authorSessionId: string | null
  authorAgentId: string | null
  parentChangesetId: string | null
  status: ChangesetStatus
  buildVerified: boolean
  fileCount: number
  createdAt: string
  committedAt: string | null
  metadata: Record<string, unknown>
}

export interface ChangesetCreate {
  id?: string
  description: string
  authorSessionId?: string
  authorAgentId?: string
  parentChangesetId?: string
  metadata?: Record<string, unknown>
}

export interface ChangesetFile {
  changesetId: string
  engramId: string
  previousChecksum: string | null
  previousContent: string | null
  operation: ChangesetFileOperation
}

export interface SourceFileMetadata {
  filePath: string
  language: string
  checksum: string
  sizeBytes: number
  changesetId: string | null
  buildable: boolean
}
