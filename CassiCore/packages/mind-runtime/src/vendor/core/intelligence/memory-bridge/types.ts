/**
 * Memory Bridge Types — connects LARQL-style residual stream injection
 * with Mnemic Field kindling for memory-augmented inference.
 *
 * Architecture:
 *   residual[L] = residual[L-1] + attn_delta + ffn_delta + memory_delta
 *
 * Memory delta is injected at phase transition layers (L24-L26),
 * where LARQL research shows the answer crystallizes.
 */

import type { LuminalSet, MnemicRetrievalHit, ChargedEngram } from '@cassicore/mnemic-field'

/**
 * Configuration for memory delta injection.
 */
export interface MemoryInjectionConfig {
  /** Layers to inject memory delta at (phase transition band). */
  injectionLayers: number[]

  /** Maximum contribution in logits (prevent overpowering model). */
  maxContribution: number

  /** Minimum charge threshold for engrams to contribute. */
  chargeThreshold: number

  /** Weight per layer (e.g., L24=0.5, L25=1.0, L26=0.5). */
  layerWeights: Map<number, number>

  /** Whether to use learned projection matrix. */
  useLearnedProjection: boolean

  /** Path to projection matrix file (if learned). */
  projectionMatrixPath?: string

  /** Whether to record memory contributions for consolidation. */
  recordContributions: boolean

  /** Kindling complexity for memory retrieval. */
  kindlingComplexity: 'simple' | 'normal' | 'complex'
}

export const MEMORY_INJECTION_DEFAULTS: MemoryInjectionConfig = {
  injectionLayers: [24, 25, 26],
  maxContribution: 50.0,      // Matches LARQL's FFN contribution scale
  chargeThreshold: 0.3,
  layerWeights: new Map([
    [24, 0.5],   // Attention fires here, memory supports
    [25, 1.0],   // FFN fires here, memory contributes fully
    [26, 0.5],   // Both fire, memory stabilizes
  ]),
  useLearnedProjection: true,
  recordContributions: true,
  kindlingComplexity: 'complex',  // Lower spark point for broader recall
}

/**
 * A single memory contribution to the residual stream.
 */
export interface MemoryContribution {
  /** Engram that contributed. */
  engramId: string

  /** Content excerpt (for trace attribution). */
  content: string

  /** Charge in luminal set (activation strength). */
  charge: number

  /** Match type during kindling. */
  matchType: 'direct_embedding' | 'direct_text' | 'synapse_expansion' | 'supersession_chase'

  /** Contribution weight applied to this engram. */
  weight: number

  /** Layer where this contributed. */
  layer: number

  /** Vector contribution (hidden_size dimensions). */
  vector?: Float32Array
}

/**
 * Memory delta injected into residual stream.
 */
export interface MemoryDelta {
  /** Total vector contribution [hidden_size]. */
  vector: Float32Array

  /** Individual contributions (for trace/consolidation). */
  contributions: MemoryContribution[]

  /** Total magnitude (sum of weighted charges). */
  magnitude: number

  /** Number of engrams that crossed threshold. */
  contributingCount: number

  /** Layer this delta was computed for. */
  layer: number

  /** Whether delta was capped (exceeded maxContribution). */
  wasCapped: boolean
}

/**
 * Boundary residual extracted before phase transition.
 * This is the model's "knowledge so far" at L22.
 */
export interface BoundaryResidual {
  /** Layer where boundary was extracted. */
  layer: number

  /** Residual vector [hidden_size]. */
  vector: Float32Array

  /** Norm of the residual (for diagnostics). */
  norm: number

  /** Top-k predictions at boundary (what model thinks so far). */
  topPredictions: Array<{ token: string; prob: number }>

  /** Timestamp of extraction. */
  extractedAt: number
}

/**
 * Result of memory-augmented kindling for injection.
 */
export interface MemoryKindlingResult {
  /** The luminal set from kindling. */
  luminalSet: LuminalSet

  /** Projected memory deltas per injection layer. */
  deltas: Map<number, MemoryDelta>

  /** Boundary residual used as kindling seed context. */
  boundary: BoundaryResidual

  /** Text query used for kindling. */
  query: string

  /** Total duration in ms. */
  durationMs: number

  /** Whether any memories crossed charge threshold. */
  hadContributions: boolean
}

/**
 * Portal pair connecting LARQL feature to Mnemic Field engram.
 */
export interface FeatureEngramPortal {
  /** Portal ID. */
  id: string

  /** LARQL vindex feature reference. */
  feature: {
    layer: number
    featureIndex: number
    gateScore?: number
    label?: string
  }

  /** Mnemic Field engram reference. */
  engram: {
    id: string
    nodeType: string
    contentPreview: string
  }

  /** Connection type. */
  connectionType: 'semantic' | 'temporal' | 'causal' | 'structural'

  /** Strength of connection (0.0-1.0). */
  strength: number

  /** How this portal was discovered. */
  discoveryMethod: 'auto' | 'manual' | 'correlation'

  /** Correlation score if auto-discovered. */
  correlationScore?: number

  /** Creation timestamp. */
  createdAt: string

  /** Last activation timestamp. */
  lastActivatedAt?: string

  /** Activation count. */
  activationCount: number
}

/**
 * Unified trace node combining LARQL and Mnemic Field traces.
 */
export interface UnifiedTraceNode {
  /** Layer in transformer. */
  layer: number

  /** Position in sequence. */
  position: number

  /** Residual vector at this point [hidden_size]. */
  residual: Float32Array

  /** Attention contribution [hidden_size]. */
  attnDelta: Float32Array

  /** FFN contribution [hidden_size]. */
  ffnDelta: Float32Array

  /** Memory contribution (if at injection layers). */
  memoryDelta?: MemoryDelta

  /** Top answer token at this layer. */
  topAnswer: string

  /** Answer rank at this layer. */
  answerRank: number

  /** Answer probability at this layer. */
  answerProb: number
}

/**
 * Complete unified trace for one inference pass.
 */
export interface UnifiedTrace {
  /** Trace ID. */
  id: string

  /** Query/prompt that generated this trace. */
  query: string

  /** All trace nodes (tokens × layers). */
  nodes: UnifiedTraceNode[]

  /** Memory contributions across all layers. */
  memoryContributions: MemoryContribution[]

  /** Luminal set used for memory injection. */
  luminalSet?: LuminalSet

  /** Total duration in ms. */
  durationMs: number

  /** Created timestamp. */
  createdAt: number
}

/**
 * Projection matrix for mapping embeddings to hidden space.
 * Learned during consolidation from feedback.
 */
export interface ProjectionMatrix {
  /** Matrix dimensions. */
  inputDim: number   // Embedding dimension (e.g., 768)
  outputDim: number  // Hidden dimension (e.g., 2560)

  /** Matrix weights [outputDim, inputDim]. */
  weights: Float32Array

  /** Bias vector [outputDim]. */
  bias: Float32Array

  /** Whether matrix has been trained. */
  isTrained: boolean

  /** Training iteration count. */
  trainingIterations: number

  /** Last update timestamp. */
  updatedAt: string
}

/**
 * Gradient request for projection matrix learning.
 */
export interface ProjectionGradientRequest {
  /** Request ID. */
  id: number

  /** Trace ID this came from. */
  traceId: string

  /** Memory contributions that were helpful. */
  helpfulContributions: string[]  // engram IDs

  /** Memory contributions that were not helpful. */
  unhelpfulContributions: string[]  // engram IDs

  /** Target adjustment (positive = boost, negative = suppress). */
  targetAdjustment: number

  /** Created timestamp. */
  createdAt: number

  /** Whether processed. */
  processed: boolean
}

/**
 * Portal discovery configuration.
 */
export interface PortalDiscoveryConfig {
  correlationThreshold: number
  minActivations: number
  maxPortals: number
  decayRate: number
}

/**
 * Stats for the memory bridge.
 */
export interface MemoryBridgeStats {
  /** Total injections performed. */
  injectionsPerformed: number

  /** Injections with contributions. */
  injectionsWithContributions: number

  /** Average contribution magnitude. */
  avgMagnitude: number

  /** Average contributing count. */
  avgContributingCount: number

  /** Portal pairs count. */
  portalPairsCount: number

  /** Projection matrix status. */
  projectionTrained: boolean

  /** Last injection timestamp. */
  lastInjectionAt?: number
}