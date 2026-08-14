/**
 * TYPE STUB — LARQL Knowledge Provider (core/intelligence/aurora/larql-provider.ts).
 *
 * Faithful type surface for the symbols mnemic-field consumes: `LarqlKnowledgeProvider`
 * (used as a provider field in EngramDecomposer). Re-point to the owning package
 * at P5 via the repoint log; the runtime impl (cassi-larql native bindings) is NOT
 * reproduced here.
 */
import type { ILogger } from '@cassicore/foundation'
import type { ModelKnowledgeProvider, CycleIdAware, ModelEntity, ModelEdge, ModelPath } from './types.js'

export interface LarqlProviderConfig {
  /** Knowledge layers to scan (default: L14-L27 for Gemma 3 4B). */
  knowledgeLayers: number[]
  /** Top-K features per layer per query. */
  featuresPerLayer: number
  /** Minimum gate score to include a relation. */
  minGateScore: number
  /** Maximum relations per entity. */
  maxRelationsPerEntity: number
  /** Maximum depth for subgraph extraction. */
  maxSubgraphDepth: number
}

export const LARQL_PROVIDER_DEFAULTS: LarqlProviderConfig = {
  knowledgeLayers: [14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27],
  featuresPerLayer: 20,
  minGateScore: 0.1,
  maxRelationsPerEntity: 30,
  maxSubgraphDepth: 2,
}

/**
 * LarqlKnowledgeProvider — queries model knowledge via vindex gate KNN.
 * (Type stub only; the runtime impl lives in the P5-owned aurora path.)
 *
 * The surface mirrors the D: original's public methods that mnemic-field
 * consumes (EngramDecomposer calls isLoaded/getConfig/tokenize/
 * traceForwardPerToken; the class also implements ModelKnowledgeProvider).
 */
export declare class LarqlKnowledgeProvider implements ModelKnowledgeProvider, CycleIdAware {
  constructor(logger: ILogger, config?: Partial<LarqlProviderConfig>)

  /** Whether the provider is loaded and ready. */
  isLoaded(): boolean

  /** vindex config (dimensions, layer count, vocab size) — used for version stamping. */
  getConfig(source?: string): { numLayers: number; hiddenDim: number; vocabSize: number } | null

  /** Tokenize text and return token IDs. */
  tokenize(text: string, source?: string): number[]

  /** Multi-token gate KNN — returns per-token feature activations + density metrics. */
  traceForwardPerToken(
    tokens: number[],
    layerStart: number,
    layerEnd: number,
    topK: number,
    source?: string,
  ): {
    tokens: Array<{ tokenIndex: number; tokenId: number; features: Array<{ layer: number; featureIndex: number; score: number; label?: string }>; featureCount: number }>
    totalUniqueFeatures: number
    tokensPerFeature: number
    featuresPerToken: number
    tokensProcessed: number
    layersScanned: number
    durationMs: number
  } | null

  // — ModelKnowledgeProvider surface —
  describe(entity: string, opts?: { applyOverlay?: boolean }): ModelEntity | null
  subgraph(entity: string, radius: number): ModelEdge[]
  shortestPath(from: string, to: string): ModelPath | null
  exists(entity: string): boolean
  search(query: string, limit: number): ModelEntity[]

  setCycleId(cycleId: string | null): void
}
