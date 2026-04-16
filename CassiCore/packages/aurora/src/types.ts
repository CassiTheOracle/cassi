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

/**
 * A node in the unified cognitive graph.
 * Can originate from model knowledge, personal memory, or both.
 */
export interface CognitiveNode {
  /** Unique ID (engram ID for memory nodes, entity name for model nodes). */
  id: string

  /** Human-readable label. */
  label: string

  /** Where this node came from. */
  source: 'model' | 'memory' | 'both'

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

/**
 * An edge in the unified cognitive graph.
 */
export interface CognitiveEdge {
  /** Source node ID. */
  sourceId: string

  /** Target node ID. */
  targetId: string

  /** Origin of this edge. */
  origin: 'model' | 'memory' | 'portal' | 'dream'

  /** Edge type (model relation type or Mnemic Field synapse type). */
  edgeType: string

  /** Edge weight. */
  weight: number

  /** Model-side: confidence. */
  modelConfidence?: number

  /** Model-side: layers where this relation appears. */
  modelLayers?: number[]

  /** Memory-side: synapse type. */
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
  sourceBreakdown: {
    model: number
    memory: number
    both: number
  }

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
}
