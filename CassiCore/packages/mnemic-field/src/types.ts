/**
 * RerankerMode now lives in the shared embeddings/types.ts so both
 * MnemicField retrieval and Thalamus's ToolResultDistiller reference the
 * same identity. Re-exported here for backward compat with existing
 * imports (`from '../mnemic-field/types.js'`).
 */
export type { RerankerMode } from '../embeddings/types.js'

export const ENGRAM_TYPES = [
  'fact', 'episode', 'decision', 'pattern',
  'abstraction', 'goal', 'file', 'tool', 'session', 'outcome',
  'source_file', 'changeset', 'artifact', 'concern', 'anomaly',
  'module', 'capability', 'principle', 'weakness', 'evolution', 'portal',
  'bridge',
  'synthesized_invariant',
  'intent_span',
  'thought_command',
  'replay_segment',
  'expert_summary',
  'file_version',
  'file_read',
  'tool_invocation',
  'message',
  'pineal_facet',
  'error_report',
  'search_finding',
  'code_change',
  'test_result',
  'build_output',
] as const

export type EngramType = typeof ENGRAM_TYPES[number]

export const SYNAPSE_TYPES = [
  'similar_to', 'contradicts', 'supports',
  'caused_by', 'led_to', 'used_in_task', 'part_of',
  'temporal_neighbor', 'supersedes', 'about_file', 'spawned_from',
  'imports', 'modified_by', 'co_changed', 'contains_symbol',
  'depends_on', 'implements', 'uses_pattern', 'governed_by',
  'evolved_from', 'enables', 'constrains', 'mitigates', 'portal_link',
  'responds_to',
  'triggered_by',
  'commands',
  'expert_summary',
  'injected_for',
  'contains',
  'created_in',
  'produces',
  'operated_on',
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
  /** Radial distance from origin (0-1). Computes x/y if both r and theta provided. */
  r?: number
  /** Angular position in radians (0-2π). Computes x/y if both r and theta provided. */
  theta?: number
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
  r?: number
  theta?: number
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

export const REPLAY_ID_PREFIXES = {
  session: 'session:',
  run: 'run:',
  step: 'step:',
  turn: 'turn:',
  toolCall: 'tc:',
  toolResult: 'tr:',
  sessionResult: 'session_result:',
  sessionSummary: 'session_summary:',
  error: 'err:',
  artifact: 'artifact:',
} as const

export type ReplayNodeKind = keyof typeof REPLAY_ID_PREFIXES

export interface ReplayNode {
  engram: Engram
  parentIds: string[]
  childIds: string[]
  previousIds: string[]
  nextIds: string[]
}

export interface ReplayTraversalOptions {
  includeRecursive?: boolean
  limit?: number
}

export interface ReplayTraversal {
  rootId: string
  nodes: ReplayNode[]
  synapses: MnemicSynapse[]
}

export type ReplayEventKind =
  | 'session'
  | 'run'
  | 'step'
  | 'turn'
  | 'tool_call'
  | 'tool_result'
  | 'session_result'
  | 'session_summary'
  | 'error'
  | 'artifact'
  | 'unknown'

export interface ReplayEvent {
  id: string
  kind: ReplayEventKind
  nodeType: EngramType
  timestamp: string
  content: string
  metadata: Record<string, unknown>
  parentIds: string[]
  childIds: string[]
  previousIds: string[]
  nextIds: string[]
}

export interface SessionReplaySummary {
  sessionId: string
  exists: boolean
  eventCount: number
  turnCount: number
  runCount: number
  stepCount: number
  toolCallCount: number
  toolResultCount: number
  anomalyCount: number
  artifactCount: number
  startedAt: string | null
  lastEventAt: string | null
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
  depends_on: 0.85,
  implements: 0.9,
  uses_pattern: 0.7,
  governed_by: 0.6,
  evolved_from: 0.8,
  enables: 0.85,
  constrains: 0.5,
  mitigates: 0.7,
  portal_link: 0.6,
  responds_to: 0.5,
  triggered_by: 0.4,
  commands: 0.3,
  expert_summary: 0.9,
  injected_for: 0.7,
  contains: 0.7,
  created_in: 0.5,
  produces: 0.85,
  operated_on: 0.8,
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
    simple: 0.9,      // more permissive for simple lookups
    normal: 1.0,      // baseline
    complex: 1.2,     // stricter — complex tasks need precision, not noise
    delegation: 1.5,  // tightest — delegated agents get clean, focused context
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
  recordTrace?: boolean
  currentAffect?: Affect
  /** Shadow mode (Phase 2: Yin/Yang): invert radial seed bias to surface
   *  engrams in neglected sectors far from the attractor. */
  shadow?: boolean
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

/**
 * Metadata for a `file` engram — the anchor engram for a tracked filesystem path.
 * Replaces SourceFileMetadata for new file tracking; `source_file` engrams
 * retain SourceFileMetadata for backward compatibility.
 */
export interface FileMetadata {
  filePath: string
  language: string
  currentChecksum: string
  sizeBytes: number
  versionCount: number
  readCount: number
  lastReadAt: string | null
  lastModifiedAt: string | null
}

/**
 * Metadata for a `file_version` engram — one snapshot of a file's content.
 * v1 stores full content; v2+ store a diff from v1's full content so any
 * version can be reconstructed by applying one diff (no chained diffs).
 */
export interface FileVersionMetadata {
  filePath: string
  checksum: string
  sizeBytes: number
  versionIndex: number
  toolInvocationId: string | null    // tool_invocation engram that produced this version
  supersedesId: string | null         // engram ID of the previous file_version
  diffFromBaseVersionId: string | null // engram ID of v1 (diff base)
  isDiff: boolean                     // true if content is a diff from v1
}

/**
 * Metadata for a `file_read` engram — records that a session read a file.
 */
export interface FileReadMetadata {
  filePath: string
  sessionId: string
  timestamp: string
  readCount: number
  toolInvocationId: string | null
}

/**
 * Metadata for a `tool_invocation` engram — full tool call + result.
 */
export interface ToolInvocationMetadata {
  toolName: string
  toolClass: string
  input: Record<string, unknown>
  durationMs: number
  outputBytes: number
  isError: boolean
  sessionId: string
  messageIndex: number
  filePath: string | null   // for fs tools that operate on a file
  searchTarget: string | null  // for search/grep tools
}

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


export type ActivationFunction = 'linear' | 'leaky_relu' | 'sigmoid' | 'tanh'

export interface NeuralKindlingConfig {
  enabled: boolean
  activationFn: ActivationFunction
  biasScale: number             // how much potentiation contributes as a bias term
  traceRecording: boolean       // whether to record forward traces for later backprop
  maxTraceAge: number           // ms before traces are garbage-collected
  leakyReluSlope: number        // negative slope for leaky ReLU (default 0.01)
}

export const NEURAL_KINDLING_DEFAULTS: NeuralKindlingConfig = {
  enabled: true,
  activationFn: 'leaky_relu',
  biasScale: 0.3,
  traceRecording: true,
  maxTraceAge: 3_600_000,        // 1 hour
  leakyReluSlope: 0.01,
} as const

/**
 * A single recorded contribution during spreading activation.
 * These records form the "trace" used for backpropagation during consolidation.
 */
export interface ForwardRecord {
  iteration: number
  sourceId: string
  targetId: string
  edgeType: SynapseType
  synapseWeight: number
  sourceCharge: number
  propagationFactor: number     // edgeType-based propagation constant
  distDecay: number
  temporalRelevance: number
  potBoost: number
  emotionalDamping: number
  rawContribution: number       // the spread value before activation
  activatedOutput: number       // the charge after activation function
  preActivation: number         // the aggregated input before activation (needed for σ')
}

/**
 * A complete forward trace for one kindling operation.
 * Contains everything needed to compute gradients during consolidation.
 */
export interface ForwardTrace {
  id: string                    // unique trace identifier
  createdAt: number             // timestamp
  seedCharges: Record<string, number>  // initial seed → charge mapping
  records: ForwardRecord[]      // ordered by iteration, then by contribution
  outputCharges: Record<string, number>  // final chargeMap snapshot after spreading
  sparkPoint: number            // the threshold used for ignition
  luminalIds: string[]          // engram IDs that made it into the LuminalSet
}

/**
 * Feedback for a completed kindling — maps engram IDs to helpfulness.
 * Used to compute loss during consolidation backprop.
 */
export interface GradientRequest {
  id: number
  traceId: string
  feedback: Record<string, boolean>  // engramId → was this helpful?
  createdAt: number
  processed: boolean
}


/**
 * Per-synapse Adam optimizer state, persisted in synapse_optimizer_state.
 */
export interface SynapseOptimizerState {
  sourceId: string
  targetId: string
  edgeType: SynapseType
  m: number          // first moment estimate (mean of gradients)
  v: number          // second moment estimate (mean of squared gradients)
  step: number       // number of updates applied
}

/**
 * Configuration for the backpropagation / gradient engine.
 */
export interface BackpropConfig {
  learningRate: number           // Adam step size (α)
  beta1: number                  // exponential decay for first moment
  beta2: number                  // exponential decay for second moment
  epsilon: number                // numerical stability constant
  maxGradNorm: number            // gradient clipping threshold
  weightMin: number              // minimum synapse weight after update
  weightMax: number              // maximum synapse weight after update
  batchSize: number              // max gradient requests to process per consolidation
  minTraceRecords: number        // skip traces with fewer records than this
}

export const BACKPROP_DEFAULTS: BackpropConfig = {
  learningRate: 0.001,
  beta1: 0.9,
  beta2: 0.999,
  epsilon: 1e-8,
  maxGradNorm: 1.0,
  weightMin: 0.01,
  weightMax: 5.0,
  batchSize: 50,
  minTraceRecords: 2,
} as const

/**
 * Result of a single backpropagation pass over one forward trace.
 */
export interface TraceGradientResult {
  traceId: string
  synapseGradients: Map<string, number>  // "source|target|edgeType" → accumulated gradient
  feedbackCount: number
  positiveCount: number
  negativeCount: number
}

/**
 * Aggregate result from processing a batch of gradient requests.
 */
export interface BackpropResult {
  requestsProcessed: number
  tracesProcessed: number
  synapsesUpdated: number
  avgGradientMagnitude: number
  maxGradientMagnitude: number
  skippedStaleTraces: number
  durationMs: number
}

export const LIGHTNING_INDEXER_VERSION = 1

export interface LightningIndexerConfig {
  dEmb: number
  dC: number
  nH: number
  dIdx: number
  seed: number
  /** Whether to PolarQuant-compress lightning keys before storing.
   *  Saves ~17× disk space (1024 bytes → 58 bytes per 256-dim key)
   *  at the cost of decode overhead on load. Default: false. */
  compressKeys: boolean
}

export const LIGHTNING_INDEXER_DEFAULTS: LightningIndexerConfig = {
  dEmb: 1024,
  dC: 128,
  nH: 8,
  dIdx: 32,
  seed: 0xC0FFEE,
  compressKeys: false,
}

export interface LightningIndexerGlobal {
  wDq: Float32Array
  wIuq: Float32Array
  wI: Float32Array
  dEmb: number
  dC: number
  nH: number
  dIdx: number
  version: number
  updatedAt: string
}

export interface LightningCandidate {
  engramId: string
  embedding: Float32Array
}

export interface LightningRanked {
  engramId: string
  score: number
}

export type LightningRetrievalMode =
  | 'shadow'        // Indexer scores logged alongside reranker output, reranker drives ordering
  | 'live'          // Indexer drives ordering (post-Phase 2)
  | 'fallback'      // Indexer scored but reranker overrode based on disagreement
  | 'kindle-only'   // No reranker, kindling charges drove ordering
  | 'fts-fallback'  // Empty kindling, FTS searchText() fallback

export interface LightningRetrievalEvent {
  retrievalId: string
  sessionId?: string
  queryText: string
  queryEmbedding?: Float32Array
  candidateIds: string[]
  indexerScores?: Float32Array
  rerankerScores?: Float32Array
  indexerVersion?: number
  mode: LightningRetrievalMode
  createdAt: string
}

export interface LightningRetrievalEventQuery {
  sessionId?: string
  since?: string
  mode?: LightningRetrievalMode
  limit?: number
}

export type ExpertKind =
  | 'topic'
  | 'principle'
  | 'skill'
  | 'self_model'
  | 'relationship'
  | 'meta_cognitive'
  | 'identity'
  | 'factual'
  | 'aesthetic'
  | 'heuristic'

export type ExpertDomain = 'identity' | 'wisdom' | 'philosophy' | 'praxis'

export type ExpertProvenance = 'soul.md' | 'agents.md' | 'skill-file' | 'user' | 'meditation' | 'self'

export interface ExpertMetadata {
  expertId: string
  expertKind: ExpertKind
  expertDomain: ExpertDomain
  expertConviction: number
  expertSalience: number
  expertPinned: boolean
  expertScope: string | null
  expertEvolvedFrom: string | null
  expertVersion: number
  expertProvenance: ExpertProvenance
  expertLastReinforced: string
  expertReinforcements: number
  expertNewSinceSummary: number
  expertCentroid: number[]
  expertSourceIds: string[]
}

export type ExpertLifecycleState = 'active' | 'dormant' | 'archived' | 'hot'

export interface ExpertQuery {
  expertKind?: ExpertKind
  expertDomain?: ExpertDomain
  expertPinned?: boolean
  expertScope?: string | null
  minConviction?: number
  lifecycleState?: ExpertLifecycleState
  limit?: number
}

export interface TraceOptions {
  sessionIds?: string[]
  expertId?: string
  from?: string
  to?: string
  limit?: number
}

export interface TraceEvent {
  sessionId: string
  timestamp: string
  engram: Engram
  edges: MnemicSynapse[]
  expertInjections?: string[]
}

/** Primed nucleus — temporary spark point reduction from a global workspace broadcast. */
export interface PrimedNucleus {
  nucleusId: string
  /** Resonance score at time of priming (0-1). Higher = stronger prime. */
  resonance: number
  /** When this prime expires (epoch ms). After this, spark modulation returns to 1.0. */
  expiresAt: number
}

/** Result of a global workspace broadcast. */
export interface BroadcastResult {
  /** Number of nuclei that received priming (resonance >= threshold). */
  nucleiPrimed: number
  /** Number of nuclei that were below the resonance threshold (shadow accumulated). */
  nucleiIgnored: number
  /** The broadcast centroid position (mean of luminal engram positions). */
  broadcastX: number
  broadcastY: number
  /** Duration of the broadcast computation in ms. */
  durationMs: number
}

/**
 * Per-engram result of contrastive extraction (Phase 2).
 * Stored on engram.metadata.distinctiveness.
 */
export interface DistinctivenessResult {
  /** Fraction of content that is unique within its group (0-1). */
  score: number
  /** Unique sentences not shared with other engrams in the same nucleus/sector. */
  distinctiveContent: string
  /** Total sentences in the engram. */
  totalSentences: number
  /** Number of unique sentences. */
  uniqueSentences: number
  /** Grouping key used (nucleus ID or sector index). */
  groupKey: string
}
