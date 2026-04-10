export const ENGRAM_TYPES = [
  'fact', 'episode', 'decision', 'pattern',
  'abstraction', 'goal', 'file', 'tool', 'session', 'outcome',
  'source_file', 'changeset', 'artifact', 'concern', 'anomaly'
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
  initialPotentiation?: number
  embedding?: Float32Array | number[] | null
  tags?: string[]
  provenance?: string
  createdAt?: string
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
  filamentCount?: number
  filamentSynapseCount?: number
  filamentEntityCount?: number
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
  filamentExcerpt?: string
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
  filamentAnnotations?: FilamentAnnotation[]
  trace?: KindlingTrace[]
}

export interface KindlingTrace {
  iteration: number
  charges: Record<string, number>
}

export interface EngramPosition {
  id: string
  x: number
  y: number
  t: number
  potentiation: number
  nodeType: EngramType
  clusterId: string | null
}

export interface KindlingOptions {
  complexity?: TaskComplexity
  maxIterations?: number
  convergenceTolerance?: number
  maxSeeds?: number
  maxLuminalSize?: number
  includeText?: boolean
  enableFilaments?: boolean
  maxFilamentSeeds?: number
  maxFilamentExpansions?: number
  chaseSupersessions?: boolean
  filamentPrecisionBoost?: number
  recordTrace?: boolean
  currentAffect?: Affect
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

export const FILAMENT_SYNAPSE_TYPES = [
  'references', 'contradicts', 'elaborates', 'supersedes',
  'derives_from', 'confirms', 'co_activated',
] as const

export type FilamentSynapseType = typeof FILAMENT_SYNAPSE_TYPES[number]

export const FILAMENT_SYNAPSE_PROPAGATION: Record<FilamentSynapseType, number> = {
  supersedes: 0.9,
  references: 0.8,
  elaborates: 0.75,
  contradicts: 0.7,
  derives_from: 0.7,
  confirms: 0.5,
  co_activated: 0.3,
}

export interface Filament {
  id: number
  engramId: string
  spanStart: number
  spanEnd: number
  content: string
  embedding: Float32Array | null
  createdAt: string
}

export interface FilamentCreate {
  engramId: string
  spanStart: number
  spanEnd: number
  content: string
  embedding?: Float32Array | number[] | null
}

export interface FilamentSynapse {
  sourceId: number
  targetId: number
  edgeType: FilamentSynapseType
  weight: number
  confidence: number
  provenance: string
  createdAt: string
  metadata: Record<string, unknown>
}

export interface FilamentSynapseCreate {
  sourceId: number
  targetId: number
  edgeType: FilamentSynapseType
  weight?: number
  confidence?: number
  provenance: string
  metadata?: Record<string, unknown>
}

export interface FilamentEntity {
  filamentId: number
  entity: string
  entityType: string
}

export type FilamentMatchType = 'direct_embedding' | 'direct_text' | 'synapse_expansion' | 'supersession_chase'

export interface FilamentAnnotation {
  filamentId: number
  engramId: string
  content: string
  matchType: FilamentMatchType
  similarity: number
  expansionPath?: {
    sourceFilamentId: number
    edgeType: FilamentSynapseType
    sourceContent: string
  }
}

export interface SegmentationConfig {
  minFilamentLength: number
  maxFilamentLength: number
  minContentLength: number
  skipNodeTypes: EngramType[]
  abbreviations: string[]
  fileExtensions: string[]
}

export const SEGMENTATION_DEFAULTS: SegmentationConfig = {
  minFilamentLength: 20,
  maxFilamentLength: 500,
  minContentLength: 50,
  skipNodeTypes: ['source_file', 'changeset'],
  abbreviations: ['e.g.', 'i.e.', 'etc.', 'vs.', 'approx.', 'cf.', 'al.', 'Dr.', 'Mr.', 'Mrs.', 'Ms.', 'Jr.', 'Sr.', 'No.', 'Vol.'],
  fileExtensions: ['ts', 'js', 'tsx', 'jsx', 'sql', 'md', 'json', 'yaml', 'yml', 'toml', 'py', 'rs', 'go', 'rb', 'html', 'css', 'sh', 'txt', 'log', 'env', 'xml', 'csv'],
} as const

export const FILAMENT_KINDLING_DEFAULTS = {
  precisionBoost: 1.15,
  contextPenalty: 0.9,
  lazyThreshold: 0.75,
  maxFilamentSeeds: 20,
  maxFilamentExpansions: 10,
  maxSupersessionHops: 5,
  coActivationMinSimilarity: 0.6,
  coActivationMaxPerFilament: 20,
  coActivationInitialWeightScale: 0.4,
  coActivationMaxInitialWeight: 0.5,
  coActivationReinforcementStep: 0.05,
  coActivationWeightCap: 0.8,
} as const

export interface FilamentChain {
  filaments: Array<{ id: number; engramId: string; content: string; createdAt: string }>
  edgeTypes: FilamentSynapseType[]
  length: number
}

export type CrystallizationStatus = 'crystallized' | 'contested' | 'isolated'

export interface CrystallizationScore {
  filamentId: number
  content: string
  confirmCount: number
  contradictCount: number
  status: CrystallizationStatus
}

export type ExpertiseLevel = 'deep' | 'moderate' | 'surface'

export interface ExpertiseMetrics {
  nucleusId: string
  label: string
  filamentDensity: number
  synapseDensity: number
  chainDepth: number
  status: ExpertiseLevel
}

export interface DelegationContext {
  renderedText: string
  filamentGraph?: {
    matchedFilaments: FilamentAnnotation[]
    chains: FilamentChain[]
    contradictions: Array<{ claimA: string; claimB: string; engramIds: [string, string] }>
  }
}

export type ZoomLevel = 'full' | 'excerpt' | 'chain'

export interface ZoomEntry {
  engramId: string
  zoom: ZoomLevel
  rendered: string
  tokenEstimate: number
}

export interface RenderOptions {
  tokenBudget: number
  chainBudgetShare?: number
  fullBudgetShare?: number
}

export const RENDER_DEFAULTS = {
  chainBudgetShare: 0.3,
  fullBudgetShare: 0.6,
} as const

export interface Tier3Config {
  maxLlmCallsPerCycle: number
  maxPairsPerCall: number
  cooldownMs: number
  potentiationThreshold: number
}

export const TIER3_DEFAULTS: Tier3Config = {
  maxLlmCallsPerCycle: 5,
  maxPairsPerCall: 15,
  cooldownMs: 600_000,
  potentiationThreshold: 0.8,
} as const

export const CHAIN_EDGE_TYPES = ['derives_from', 'supersedes', 'elaborates'] as const satisfies readonly FilamentSynapseType[]

export interface Affect {
  valence: number   // -1 (negative) to +1 (positive)
  arousal: number   // 0 (calm) to 1 (activated)
}

export interface AffectState extends Affect {
  dominance: number
  label: AffectLabel
  updatedAt: number
}

export type AffectLabel =
  | 'excited' | 'delighted' | 'engaged'
  | 'content' | 'warm' | 'calm'
  | 'frustrated' | 'alarmed' | 'uneasy'
  | 'melancholy' | 'fatigued' | 'neutral'

export interface AffectConfig {
  baselineValence: number
  baselineArousal: number
  decayRate: number             // emotion register: fraction per minute toward baseline
  moodDecayRate: number         // mood register: slower decay for sustained affect
  emotionWeight: number         // blend weight for emotion vs mood (0-1)
  negativeDecayModifier: number // multiplier on decay when valence < 0 (< 1 = slower)
  moodAbsorptionRatio: number   // mood absorbs at this fraction of the emotion rate
  activationAbsorption: number  // lerp rate for activation echoes
  signalAbsorption: number      // lerp rate for system signals
  resonanceFactor: number       // retrieval congruence boost
  dampingFactor: number         // propagation dampening for incongruence
  arousalSparkModulation: number // max spark point shift from arousal
  warmthScale: number           // consolidation potentiation boost
}

export const AFFECT_DEFAULTS: AffectConfig = {
  baselineValence: 0.05,
  baselineArousal: 0.2,
  decayRate: 0.05,
  moodDecayRate: 0.02,
  emotionWeight: 0.6,
  negativeDecayModifier: 0.8,
  moodAbsorptionRatio: 0.3,
  activationAbsorption: 0.15,
  signalAbsorption: 0.08,
  resonanceFactor: 0.2,
  dampingFactor: 0.1,
  arousalSparkModulation: 0.15,
  warmthScale: 0.1,
} as const
