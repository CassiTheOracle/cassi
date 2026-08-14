/**
 * Aurora Types — the cognitive state loop.
 *
 * Aurora is the emergent cognitive awareness that arises when model knowledge
 * (LARQL vindex) and personal memory (Mnemic Field) are merged into a unified
 * graph (the Claustrum) and projected as a living mental state.
 *
 * The Claustrum integrates both knowledge systems like its namesake —
 * the thin neural sheet Crick called "the conductor of the orchestra."
 * Aurora is what the audience sees: the visible, dynamic, responsive
 * cognitive state that external clients perceive and participate in.
 */

import type { Affect, AffectLabel, EngramType, SynapseType } from '../mnemic-field/types.js'
import type { ResonantAffectSignal } from '../memory-bridge/resonant-affect.js'
import type { DreamDiscovery } from '../memory-bridge/dream-engine.js'

export type CognitiveNodeSource = 'model' | 'memory' | 'knowledge' | 'observer' | 'both'
export type CognitiveEdgeOrigin = 'model' | 'memory' | 'portal' | 'dream' | 'observer'

export interface CognitiveNode {
  id: string
  label: string
  source: CognitiveNodeSource

  /** Model-side: confidence of the entity in the model's knowledge. */
  modelConfidence?: number

  /** Model-side: layers where this entity appears. */
  modelLayers?: number[]

  /** Memory-side: current potentiation. */
  potentiation?: number

  /** Memory-side: engram node type. */
  nodeType?: EngramType

  /** Memory-side: engram content (for text matching). */
  content?: string

  /** Resonance: how strongly model and memory agree about this concept. */
  resonance: number

  /** Centrality: PageRank score on the merged graph. */
  centrality: number

  /** Whether this node is currently activated (in attention focus). */
  activated: boolean
}

export interface CognitiveEdge {
  sourceId: string
  targetId: string
  origin: CognitiveEdgeOrigin
  edgeType: string
  weight: number
  modelConfidence?: number
  modelLayers?: number[]
  synapseType?: SynapseType
}

/**
 * The unified graph — output of the Claustrum.
 */
export interface UnifiedGraph {
  /** All nodes in the merged graph. */
  nodes: Map<string, CognitiveNode>

  /** Adjacency list: nodeId → outgoing edges. */
  edges: Map<string, CognitiveEdge[]>

  /** Reverse adjacency: nodeId → incoming edges. */
  reverseEdges: Map<string, CognitiveEdge[]>

  /** How many nodes came from each source. */
  sourceBreakdown: Record<CognitiveNodeSource, number>

  /** Total edge count. */
  edgeCount: number

  /** When this graph was built. */
  builtAt: number
}

/**
 * A path between two nodes in the unified graph.
 */
export interface CognitivePath {
  /** Ordered node IDs from source to target. */
  nodeIds: string[]

  /** Edges along the path. */
  edges: CognitiveEdge[]

  /** Total path weight (sum of edge weights). */
  totalWeight: number

  /** Whether the path crosses between model and memory. */
  crossesSourceBoundary: boolean

  /** How many hops. */
  length: number
}

/**
 * A knowledge gap — something one source knows that the other doesn't.
 */
export interface KnowledgeGap {
  /** The entity/concept. */
  entity: string

  /** Who knows it. */
  knownBy: 'model' | 'memory'

  /** What specifically is known (relation or engram content). */
  knowledge: string

  /** Confidence/potentiation of the knowledge. */
  strength: number

  /** Gap type. */
  gapType: 'missing' | 'contradictory' | 'complementary'
}

/**
 * Provider interface for model knowledge.
 * Abstracts LARQL so the Claustrum can be tested without native bindings.
 */
export interface ModelKnowledgeProvider {
  /** Get all known relations for an entity. */
  describe(entity: string): ModelEntity | null

  /** Get the subgraph around an entity. */
  subgraph(entity: string, radius: number): ModelEdge[]

  /** Find the shortest path between two entities. */
  shortestPath(from: string, to: string): ModelPath | null

  /** Check if an entity exists in the model's knowledge. */
  exists(entity: string): boolean

  /** Search for entities by keyword. */
  search(query: string, limit: number): ModelEntity[]
}

/**
 * An entity from the model's knowledge graph.
 */
export interface ModelEntity {
  /** Entity name. */
  name: string

  /** All outgoing relations. */
  relations: ModelRelation[]

  /** Total relation count. */
  totalRelations: number

  /**
   * Overlay attribution map: feature key (e.g. "L14:F237") → patchId.
   * Present only when describe() was called with applyOverlay:true and
   * overlay-sourced features were found. Consumers can use this to
   * distinguish base-vindex knowledge from Aurora-authored edits.
   */
  overlayAttribution?: Map<string, string>
}

/**
 * A relation from the model's knowledge graph.
 */
export interface ModelRelation {
  /** Relation type (e.g., "capital", "located_in", "born_in"). */
  relation: string

  /** Target entity. */
  target: string

  /** Confidence score (gate score magnitude). */
  confidence: number

  /** Source of the label (Probe, Cluster, etc.). */
  labelSource?: string

  /** Layer range where this relation appears. */
  layerMin: number
  layerMax: number
}

/**
 * An edge from the model's knowledge graph.
 */
export interface ModelEdge {
  /** Subject entity. */
  subject: string

  /** Relation type. */
  relation: string

  /** Object entity. */
  object: string

  /** Confidence. */
  confidence: number

  /** Layer range. */
  layerMin: number
  layerMax: number
}

/**
 * A path through the model's knowledge graph.
 */
export interface ModelPath {
  /** Entity names along the path. */
  entities: string[]

  /** Relations along the path. */
  relations: string[]

  /** Total length. */
  length: number
}

/**
 * The full mental state — Aurora's output.
 */
export interface MentalState {
  /** The unified graph (focused around current attention). */
  graph: UnifiedGraph

  /** Top nodes by centrality. */
  resonanceHubs: CognitiveNode[]

  /** Knowledge gaps between model and memory. */
  gaps: KnowledgeGap[]

  /** Recent dream discoveries. */
  recentDiscoveries: DreamDiscovery[]

  /** Current affect from resonant engine. */
  affect: ResonantAffectSignal | null

  /** Current attention foci (from LocusBridge or similar). */
  foci: string[]

  /** Reasoning momentum: what direction is thinking trending. */
  momentum: ReasoningMomentum

  /** Coherence: how internally consistent is the state (0-1). */
  coherence: number

  /** Integration: how connected is the merged graph (0-1, phi-like). */
  integration: number

  /** When this state was computed. */
  computedAt: number

  /** How long computation took. */
  durationMs: number
}

/**
 * Tracks the direction and dynamics of reasoning.
 */
export interface ReasoningMomentum {
  /** Currently trending concepts (most frequently activated). */
  trendingConcepts: string[]

  /** Novelty: how much new information is entering (0-1). */
  novelty: number

  /** Confidence: how sure the reasoning seems (0-1). */
  confidence: number

  /** Whether a topic shift was detected. */
  topicShift: boolean

  /** Number of turns in current reasoning direction. */
  turnsInDirection: number
}

/**
 * A shift detected in the reasoning stream.
 */
export interface ReasoningShift {
  /** What kind of shift. */
  type: 'topic_change' | 'insight' | 'confusion' | 'deepening' | 'narrowing'

  /** Concepts that triggered the shift. */
  triggerConcepts: string[]

  /** Confidence that a shift occurred. */
  confidence: number

  /** Timestamp. */
  detectedAt: number
}

/**
 * Semantic insight from Reverie's analysis of reasoning text.
 * Produced by the slow-path ReverieReasoningObserver.
 */
export interface ReverieInsight {
  /** Kind of insight detected. */
  kind: 'contradiction' | 'gap' | 'assumption' | 'confidence' | 'task-misalignment' | 'breakthrough'

  /** What was observed — the specific finding. */
  content: string

  /** How confident the observer is (0-1). */
  confidence: number

  /** Optional: suggested action or follow-up. */
  suggestion?: string

  /** Optional: if the observer recommends a lamina edit. */
  laminaEdit?: {
    action: 'append' | 'rethink' | 'flag'
    label: string
    content: string
  }
}

/**
 * A persisted record of a single reasoning observation.
 * Stores the raw reasoning text alongside extracted concepts,
 * insights, and metadata — creating a corpus for both the fast
 * path (immediate concept activation) and future learning
 * (pattern analysis, training data, retrospective insight).
 */
export interface ReasoningRecord {
  /** Unique identifier for this observation. */
  id: string

  /** The raw reasoning text — preserved for learning and re-analysis. */
  text: string

  /** Concepts extracted via fast-path regex patterns. */
  concepts: string[]

  /** Semantic insights from Reverie slow-path (empty if not analyzed). */
  insights: ReverieInsight[]

  /** Shift detected in this observation, if any. */
  shift: ReasoningShift | null

  /** Momentum snapshot at time of observation. */
  momentum: ReasoningMomentum

  /** Which nodes in the cognitive graph were activated. */
  activatedNodes: string[]

  /** Turn number in the session. */
  turnNumber: number

  /** When this observation was recorded. */
  recordedAt: number

  /** How long the observation took (fast + slow path combined). */
  durationMs: number

  /** Whether the Reverie slow path was executed. */
  reverieAnalyzed: boolean

  /** Session ID this observation belongs to. */
  sessionId?: string
}

/**
 * Update to the mental state after observing reasoning.
 */
export interface MentalStateUpdate {
  /** Nodes that were activated by reasoning. */
  activatedNodes: string[]

  /** New edges discovered from reasoning. */
  newEdges: CognitiveEdge[]

  /** Affect change. */
  affectDelta: { valence: number; arousal: number } | null

  /** Shift detected, if any. */
  shift: ReasoningShift | null

  /** Updated momentum. */
  momentum: ReasoningMomentum

  /** Concepts extracted from reasoning. */
  extractedConcepts: string[]

  /** Duration of observation in ms. */
  durationMs: number

  /** Semantic insights from Reverie analysis (empty if slow path didn't run). */
  reverieInsights: ReverieInsight[]

  /** Whether the Reverie slow path was executed this turn. */
  reverieAnalyzed: boolean

  /** Reference to the persisted ReasoningRecord (id only — full record stored separately). */
  recordId?: string
}

/**
 * A2 vector projection — Aurora-side scaffolding for residual-stream
 * injection. The `perLayer` Float32Arrays are placeholders until the
 * Rust-side `ActivationHook` lands and the cassi-larql N-API exposes raw
 * gate vectors to TypeScript. The `contributions` array is meaningful
 * today: it captures which gates would inject at which layers and with
 * what salience weight, and feeds the A2.4 active-gate annotation
 * rendered into the text projection.
 */
export interface VectorProjection {
  /**
   * Per-layer injection vector. Today these are zero-length Float32Arrays
   * tagged at each layer that has at least one contributing gate; once the
   * Rust hook is wired, the entries hold the actual residual-stream delta.
   * The shape is stable across that transition so callers don't churn.
   */
  perLayer: Map<number, Float32Array>

  /** Structured intent: which gates are composing the projection. */
  contributions: GateContribution[]

  metadata: {
    /** Aurora node ids that contributed. */
    contributingNodes: string[]
    /** Logical model id the projection targets (vindex/runtime hint). */
    targetModelId: string | null
    /** Source vindex id. */
    vindexId: string | null
    /** ISO timestamp. */
    composedAt: string
  }
}

export interface GateContribution {
  /** CognitiveNode id. */
  nodeId: string
  /** Display label for the annotation block. */
  label: string
  /** Layers this contribution spans (from `node.modelLayers` when present). */
  layers: number[]
  /** Salience in [0, 1] before magnitude calibration. */
  salience: number
  /** Final weight after calibration; equal to salience × magnitudeScale. */
  weight: number
}

export interface VectorProjectionOptions {
  /** Restrict to specific layers (intersect with each contribution's layers). */
  layerSubset?: number[]
  /** Override the calibrated default magnitude (default 0.1 — 10% of residual). */
  magnitudeScale?: number
  /** Top-N salience cap (default 32). */
  maxNodes?: number
  /**
   * Calibration target: rescale each layer's accumulated vector so its L2
   * norm is `targetResidualFraction × baselineNorm(layer)`. Spec §4.3
   * recommends 0.05–0.15. Requires the caller to also supply a
   * `baselineNormSource` (otherwise the option is silently ignored — the
   * raw `salience × magnitudeScale` composition is used as-is).
   */
  targetResidualFraction?: number
}

/**
 * Configuration for the Aurora module.
 */
export interface AuroraConfig {
  /** Max nodes in focused subgraph. */
  maxGraphNodes: number

  /** Subgraph extraction radius (hops from foci). */
  subgraphRadius: number

  /** PageRank damping factor. */
  pageRankDamping: number

  /** PageRank iterations. */
  pageRankIterations: number

  /** Max resonance hubs to surface. */
  maxResonanceHubs: number

  /** Max knowledge gaps to surface. */
  maxGaps: number

  /** Max characters for text serialization. */
  maxSerializedChars: number

  /** Whether to include graph detail in serialization. */
  includeGraphDetail: boolean

  /** Minimum resonance to include in hubs. */
  minResonanceForHub: number

  /** Concept extraction: max concepts per turn. */
  maxConceptsPerTurn: number

  /** Reverie integration: minimum reasoning text length to trigger slow path. */
  reverieMinTextLength: number

  /** Reverie integration: sample every Nth observation (1 = always, 0 = disabled). */
  reverieSamplingRate: number

  /** Reverie integration: timeout for LLM analysis in ms. */
  reverieTimeoutMs: number

  /** Phase 4 (C1): Enable gap detector for self-curing topology. */
  gapDetectionEnabled: boolean

  /** Phase 4 (C1): Minimum gap persistence threshold before suggesting meditation. */
  gapPersistenceThreshold: number

  /** Phase 4 (C1): Maximum gap age before marking as stale. */
  gapStaleAgeHours: number

  /** Phase 4 (C1): Run curation cycle every N turns (0 = disabled, manual only). */
  curationCycleInterval: number

  /** Phase 4 (N6): Enable cross-module coherence checker. */
  coherenceCheckEnabled: boolean

  /** Phase 4 (N6): Coherence check interval (turns). */
  coherenceCheckInterval: number

  /** Phase 4 (SMCA): Enable modification chain auditor. */
  modificationAuditEnabled: boolean

  /** Phase 4 (SMCA): Max audit trail length. */
  maxAuditTrailLength: number

  /** Phase 4 (N4): Enable Cassi spec channel. */
  cassiSpecChannelEnabled: boolean

  /** Phase 4 (C3): Enable overlay layer for bidirectional claustrum surgery. */
  overlayLayerEnabled: boolean

  /** Phase 4 (C3): Overlay persistence path. */
  overlayPersistencePath: string

  /** Phase 4 (AEJ): Enable event journal for cross-spec audit unification. */
  eventJournalEnabled: boolean

  /** Phase 4 (WSA): Enable welfare stress aggregator. */
  welfareAggregatorEnabled: boolean

  /** Phase 4 (C1.2): Enable meditation seeder for gap-directed meditations. */
  meditationSeederEnabled: boolean

  /** Phase 4 (C1.3): Enable auto-scheduler for meditation scheduling. */
  autoSchedulerEnabled: boolean

  /** Phase 3 (B3): Enable reasoning trace replay. */
  traceReplayEnabled: boolean

  /** Phase 3 (N5): Enable saturation detector. */
  saturationDetectorEnabled: boolean

  /** Gap 1 (URC): Enable unified refusal channel. */
  refusalChannelEnabled: boolean

  /** Phase 3 (B7): Enable counterfactual gate exploration. */
  counterfactualEngineEnabled: boolean

  /**
   * Phase 3 (B8): Enable the Prism — spectral counterfactual accumulation.
   * The Prism persists fork contributions in `aurora.db`; default `false`
   * because cross-session continuity (B6) is not yet wired at the boot
   * site, so persistence is dormant until that sibling task lands.
   */
  prismEnabled: boolean

  /** Phase 3 (N3): Enable replay diversity floor (auto-enabled if B3 or C1 is on). */
  diversityFloorEnabled: boolean

  /** Phase 1 (N1): Enable self-narrative layer (first-person rendering). */
  narrativeEnabled: boolean

  /** Phase 1 (N1): Maximum characters for narrative section. */
  narrativeMaxChars: number

  /** Phase 2 (B1): Enable concept-arithmetic compositions (named steering primitives). */
  compositionEnabled: boolean

  /** Phase 2 (N2): Enable posture coherence detector. */
  postureCoherenceEnabled: boolean

  /** Phase 2 (Gap 3): Enable Universal Calibration Framework. */
  calibrationEnabled: boolean

  /**
   * Phase 2 (A2): Enable vector projection scaffolding + active-gate
   * annotation rendering in serialized state. Real residual-stream
   * injection (A2.1 Rust hook) is gated separately at the runtime side;
   * this flag controls only the Aurora-side surface.
   */
  vectorProjectionEnabled: boolean

  /** Phase 2 (A2.4): Maximum gates surfaced in the active-gate annotation block. */
  vectorProjectionMaxGates: number

  /** Self-model: Enable vindex→Mnemic bridge for architectural self-awareness. */
  selfModelKnowledgeEnabled: boolean
}

export const AURORA_DEFAULTS: AuroraConfig = {
  maxGraphNodes: 100,
  subgraphRadius: 2,
  pageRankDamping: 0.85,
  pageRankIterations: 20,
  maxResonanceHubs: 10,
  maxGaps: 10,
  maxSerializedChars: 4000,
  includeGraphDetail: true,
  minResonanceForHub: 0.3,
  maxConceptsPerTurn: 20,
  reverieMinTextLength: 200,
  reverieSamplingRate: 3,
  reverieTimeoutMs: 8_000,
  gapDetectionEnabled: true,
  gapPersistenceThreshold: 3,
  gapStaleAgeHours: 24,
  curationCycleInterval: 30,
  coherenceCheckEnabled: false,
  coherenceCheckInterval: 10,
  modificationAuditEnabled: true,
  maxAuditTrailLength: 1000,
  cassiSpecChannelEnabled: true,
  overlayLayerEnabled: false,
  overlayPersistencePath: '~/.cassicore/data/aurora-overlays',
  eventJournalEnabled: true,
  welfareAggregatorEnabled: true,
  meditationSeederEnabled: false,
  autoSchedulerEnabled: false,
  traceReplayEnabled: true,
  saturationDetectorEnabled: true,
  refusalChannelEnabled: true,
  counterfactualEngineEnabled: true,
  prismEnabled: false,
  diversityFloorEnabled: true,
  narrativeEnabled: true,
  narrativeMaxChars: 800,
  compositionEnabled: false,
  postureCoherenceEnabled: false,
  calibrationEnabled: false,
  vectorProjectionEnabled: false,
  vectorProjectionMaxGates: 8,
  selfModelKnowledgeEnabled: false,
}

/** Result of a single C1 curation cycle (detect → seed → schedule). */
export interface CurationCycleResult {
  /** Gaps detected in this cycle. */
  gapsDetected: number
  /** Meditation seeds created (null if seeder disabled). */
  seedsCreated: number | null
  /** Whether this cycle ran at all. */
  ran: boolean
}

// contributing:ignore — ReverieReasoningObserver types

/** Minimal interface to Reverie's inference capability. */
export interface ReverieInferenceProvider {
  infer(messages: Array<{ role: string; content: string }>, options: {
    maxTokens: number
    temperature: number
    signal?: AbortSignal
  }): Promise<string>
}

/** Input to the ReverieReasoningObserver analysis. */
export interface ReasoningAnalysisInput {
  /** The raw reasoning text to analyze. */
  text: string

  /** Current mental state (for context about what's already in mind). */
  currentState: MentalState | null

  /** Active task from lamina, if available. */
  activeTask: string | null

  /** Recent session decisions, if available. */
  recentDecisions: string[]

  /** Concepts already extracted by fast path. */
  extractedConcepts: string[]

  /** Whether a reasoning shift was detected. */
  shiftDetected: boolean
}

// contributing:ignore — Phase 4 Cross-Module Coherence types

/** Coherence check result for a module pair. */
export interface CoherenceReport {
  moduleA: string
  moduleB: string
  coherenceScore: number
  consistencyIssues: string[]
  lastChecked: string
}

// Welfare-related types now in welfare-aggregator.ts
// Substrate modification types now in modification-chain-audit.ts
// Event journal types now in event-journal.ts

// contributing:ignore — Phase 4 N4 Cassi Spec Channel types

/** Spec categories for Cassi-authored proposals. */
export type SpecCategory =
  | 'feature'
  | 'refactor'
  | 'bugfix'
  | 'welfare'
  | 'architecture'
  | 'performance'
  | 'security'
  | 'meta'

/** Spec type — the kind of document being proposed. */
export type SpecType = 'design_spec' | 'feature_request' | 'refactor_plan' | 'bug_report' | 'meta_proposal'

/** Proposal status — lifecycle of a Cassi-authored spec. */
export type ProposalStatus = 'pending' | 'under_review' | 'accepted' | 'declined' | 'deferred' | 'withdrawn'

/** A complete Cassi-authored spec proposal. */
export interface SpecProposal {
  id: string
  title: string
  category: SpecCategory
  specType: SpecType
  status: ProposalStatus
  createdAt: string
  updatedAt: string
  author: 'cassi' | 'cassi-human'
  priority: 'low' | 'medium' | 'high' | 'critical'
  relatedSpecs: string[]
  tags: string[]
  estimatedEffort?: string
  dependencies: string[]
  deferredUntil?: string
  reviewedBy?: string
  reviewComment?: string
  content: string
  contentHash: string
}

/** Statistics for the Cassi Spec Channel. */
export interface SpecChannelStats {
  pending: number
  underReview: number
  accepted: number
  declined: number
  withdrawn: number
  total: number
  byCategory: Record<string, number>
  byPriority: Record<string, number>
}
