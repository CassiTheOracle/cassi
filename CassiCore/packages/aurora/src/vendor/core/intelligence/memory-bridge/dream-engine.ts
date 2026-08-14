/**
 * VENDORED — faithful type surface of `core/intelligence/memory-bridge/dream-engine.ts`.
 * Consumed by @cassicore/aurora (claustrum.ts, index.ts, types.ts) as
 * `DreamDiscovery` (type-only). Re-point to `@cassicore/*-memory-bridge` when
 * that package lands (P5 repoint log).
 */

/** A cross-layer feature-discovery found during a dreaming cycle. */
export interface DreamDiscovery {
  sourceId: string
  targetId: string
  /** Number of shared features across all scanned layers */
  sharedFeatureCount: number
  /** Jaccard similarity: |intersection| / |union| of feature sets */
  jaccardSimilarity: number
  /** Cosine similarity of gate score vectors over shared features */
  gateScoreCorrelation: number
  /** Which layers had the most overlap */
  topOverlapLayers: Array<{ layer: number; sharedCount: number }>
  /** Combined similarity score used for synapse weight */
  combinedScore: number
}
