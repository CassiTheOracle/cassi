/**
 * TYPE STUB — LARQL Knowledge Provider (core/intelligence/aurora/larql-provider.ts).
 *
 * Faithful type surface for the symbol mnemic-field consumes: `LarqlKnowledgeProvider`
 * (type-only, used as a provider field in EngramDecomposer). Re-point to the owning
 * package at P5 via the repoint log; the runtime impl (cassi-larql native bindings)
 * is NOT reproduced here.
 */
import type { ILogger } from '@cassicore/foundation'
import type { ModelKnowledgeProvider, CycleIdAware } from './types.js'

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
 */
export declare class LarqlKnowledgeProvider implements ModelKnowledgeProvider, CycleIdAware {
  constructor(logger: ILogger, config?: Partial<LarqlProviderConfig>)
  setCycleId(cycleId: string | null): void
}
