/**
 * LARQL Knowledge Provider — real model knowledge via cassi-larql.
 *
 * Implements ModelKnowledgeProvider by loading a vindex in browse-only mode
 * (~3GB, no GPU) and using gate KNN across knowledge layers (L14-L27)
 * to query the model's relational knowledge.
 *
 * How describe(entity) works:
 *   1. Tokenize entity name
 *   2. Take the last meaningful token (carries most semantic weight)
 *   3. Run gate KNN at each knowledge layer (L14-L27)
 *   4. Aggregate feature hits by label → relational knowledge
 *   5. Track layer ranges and confidence per relation
 *
 * This is what LARQL's DESCRIBE command does under the hood.
 */

import type { ILogger } from '../../../types/interfaces.js'
import type {
  ModelKnowledgeProvider,
  ModelEntity,
  ModelRelation,
  ModelEdge,
  ModelPath,
} from './types.js'

interface VindexHandle {
  readonly id: number
  readonly path: string
  readonly config: {
    hiddenDim: number
    embeddingDim: number
    numLayers: number
    vocabSize: number
    intermediateSize: number
    phaseTransitionLayers: number[]
  }
}

interface FeatureHit {
  featureIndex: number
  score: number
  label: string | null
}

interface CassiLarqlModule {
  loadVindexOnly(path: string): Promise<VindexHandle>
  unloadVindexOnly(handle: VindexHandle): void
  getVindexConfig(handle: VindexHandle): VindexHandle['config']
  vindexTokenize(handle: VindexHandle, text: string): number[]
  vindexGateKnn(handle: VindexHandle, layer: number, tokenId: number, topK: number): FeatureHit[]
}

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
 */
export class LarqlKnowledgeProvider implements ModelKnowledgeProvider {
  private config: LarqlProviderConfig
  private logger: ILogger
  private handle: VindexHandle | null = null
  private larql: CassiLarqlModule | null = null
  private loaded = false

  // Cache: entity name → describe result
  private cache = new Map<string, ModelEntity | null>()
  private maxCacheSize = 500

  // Feature fingerprints per entity (for similarity search). Capped alongside cache.
  private fingerprints = new Map<string, Map<string, number>>()

  constructor(
    logger: ILogger,
    config?: Partial<LarqlProviderConfig>,
  ) {
    this.logger = logger.child ? logger.child('larql-provider') : logger
    this.config = { ...LARQL_PROVIDER_DEFAULTS, ...config }
  }

  /**
   * Initialize by loading the vindex in browse-only mode.
   * Returns true if loading succeeded.
   */
  async load(vindexPath: string): Promise<boolean> {
    try {
      // @ts-ignore — cassi-larql is a native module without type declarations
      this.larql = await import('cassi-larql') as CassiLarqlModule
    } catch (err) {
      this.logger.warn('cassi-larql bindings not available', { error: String(err) })
      return false
    }

    try {
      this.handle = await this.larql.loadVindexOnly(vindexPath)
      this.loaded = true

      const config = this.larql.getVindexConfig(this.handle)
      this.logger.info('LARQL knowledge provider loaded', {
        path: vindexPath,
        numLayers: config.numLayers,
        hiddenDim: config.hiddenDim,
        vocabSize: config.vocabSize,
        knowledgeLayers: `L${this.config.knowledgeLayers[0]}-L${this.config.knowledgeLayers[this.config.knowledgeLayers.length - 1]}`,
      })

      return true
    } catch (err) {
      this.logger.error('Failed to load vindex', { path: vindexPath, error: String(err) })
      return false
    }
  }

  /**
   * Unload the vindex and free resources.
   */
  unload(): void {
    if (this.handle && this.larql) {
      this.larql.unloadVindexOnly(this.handle)
      this.handle = null
      this.loaded = false
      this.cache.clear()
      this.logger.info('LARQL knowledge provider unloaded')
    }
  }

  /**
   * Whether the provider is loaded and ready.
   */
  isLoaded(): boolean {
    return this.loaded
  }

  /**
   * Describe an entity: what does the model know about it?
   *
   * Tokenizes the entity, runs gate KNN across knowledge layers,
   * and aggregates labeled features into relations.
   */
  describe(entity: string): ModelEntity | null {
    if (!this.loaded || !this.handle || !this.larql) return null

    // Check cache
    if (this.cache.has(entity)) {
      return this.cache.get(entity) ?? null
    }

    const tokens = this.larql.vindexTokenize(this.handle, entity)
    if (tokens.length === 0) {
      this.cacheResult(entity, null)
      return null
    }

    // Use last token (carries most semantic weight in autoregressive models)
    const queryToken = tokens[tokens.length - 1]

    const fingerprint = new Map<string, number>()
    const labeledRelations = new Map<string, { maxScore: number; layerMin: number; layerMax: number; count: number }>()

    for (const layer of this.config.knowledgeLayers) {
      const hits = this.larql.vindexGateKnn(
        this.handle,
        layer,
        queryToken,
        this.config.featuresPerLayer,
      )

      for (const hit of hits) {
        if (hit.score < this.config.minGateScore) continue
        const key = `L${layer}:F${hit.featureIndex}`
        fingerprint.set(key, hit.score)

        if (hit.label) {
          const existing = labeledRelations.get(hit.label)
          if (existing) {
            existing.maxScore = Math.max(existing.maxScore, hit.score)
            existing.layerMin = Math.min(existing.layerMin, layer)
            existing.layerMax = Math.max(existing.layerMax, layer)
            existing.count++
          } else {
            labeledRelations.set(hit.label, {
              maxScore: hit.score,
              layerMin: layer,
              layerMax: layer,
              count: 1,
            })
          }
        }
      }
    }

    if (fingerprint.size === 0) {
      this.cacheResult(entity, null)
      return null
    }

    this.fingerprints.set(entity, fingerprint)

    const modelRelations: ModelRelation[] = []
    for (const [label, data] of labeledRelations) {
      const parts = label.split(':')
      const relation = parts.length > 1 ? parts[0] : 'related_to'
      const target = parts.length > 1 ? parts.slice(1).join(':') : label

      modelRelations.push({
        relation,
        target,
        confidence: data.maxScore,
        layerMin: data.layerMin,
        layerMax: data.layerMax,
      })
    }

    // If no labeled relations, create layer-band summary relations
    if (modelRelations.length === 0) {
      const layerBands = this.summarizeByLayerBand(fingerprint)
      for (const band of layerBands) {
        modelRelations.push({
          relation: band.band,
          target: `${band.featureCount} features (peak L${band.peakLayer})`,
          confidence: band.maxScore,
          layerMin: band.layerMin,
          layerMax: band.layerMax,
        })
      }

      // Add similarity-based relations from cached fingerprints
      const similarEntities = this.findSimilarEntities(entity, fingerprint, 5)
      for (const sim of similarEntities) {
        modelRelations.push({
          relation: 'similar_to',
          target: sim.entity,
          confidence: sim.similarity * 1000,
          layerMin: this.config.knowledgeLayers[0],
          layerMax: this.config.knowledgeLayers[this.config.knowledgeLayers.length - 1],
        })
      }
    }

    // Sort by confidence descending and cap
    modelRelations.sort((a, b) => b.confidence - a.confidence)
    const capped = modelRelations.slice(0, this.config.maxRelationsPerEntity)

    const result: ModelEntity = {
      name: entity,
      relations: capped,
      totalRelations: modelRelations.length,
    }

    this.cacheResult(entity, result)

    this.logger.debug('Entity described', {
      entity,
      relations: capped.length,
      totalFeatures: fingerprint.size,
      topRelation: capped[0]?.relation,
    })

    return result
  }

  /**
   * Get the subgraph around an entity.
   */
  subgraph(entity: string, radius: number = 1): ModelEdge[] {
    const edges: ModelEdge[] = []
    const visited = new Set<string>()
    const queue: Array<{ entity: string; depth: number }> = [{ entity, depth: 0 }]
    const maxDepth = Math.min(radius, this.config.maxSubgraphDepth)

    while (queue.length > 0) {
      const current = queue.shift()!
      if (visited.has(current.entity)) continue
      visited.add(current.entity)

      const described = this.describe(current.entity)
      if (!described) continue

      for (const rel of described.relations) {
        edges.push({
          subject: current.entity,
          relation: rel.relation,
          object: rel.target,
          confidence: rel.confidence,
          layerMin: rel.layerMin,
          layerMax: rel.layerMax,
        })

        if (current.depth < maxDepth && !visited.has(rel.target)) {
          queue.push({ entity: rel.target, depth: current.depth + 1 })
        }
      }

      // Cap total edges for performance
      if (edges.length > 200) break
    }

    return edges
  }

  /**
   * Find shortest path between two entities.
   *
   * Uses BFS through the model's knowledge graph by iteratively
   * describing entities and following relations.
   */
  shortestPath(from: string, to: string): ModelPath | null {
    if (from === to) {
      return { entities: [from], relations: [], length: 0 }
    }

    const visited = new Set<string>()
    const queue: Array<{
      entity: string
      path: string[]
      relations: string[]
    }> = [{ entity: from, path: [from], relations: [] }]

    const maxDepth = 4 // Prevent deep searches
    const targetLower = to.toLowerCase()

    while (queue.length > 0) {
      const current = queue.shift()!
      if (current.path.length > maxDepth) continue
      if (visited.has(current.entity)) continue
      visited.add(current.entity)

      const described = this.describe(current.entity)
      if (!described) continue

      for (const rel of described.relations) {
        if (rel.target.toLowerCase() === targetLower) {
          return {
            entities: [...current.path, rel.target],
            relations: [...current.relations, rel.relation],
            length: current.relations.length + 1,
          }
        }

        if (!visited.has(rel.target)) {
          queue.push({
            entity: rel.target,
            path: [...current.path, rel.target],
            relations: [...current.relations, rel.relation],
          })
        }
      }
    }

    return null
  }

  /**
   * Check if an entity exists in the model's knowledge.
   */
  exists(entity: string): boolean {
    const described = this.describe(entity)
    return described !== null && described.relations.length > 0
  }

  /**
   * Search for entities by keyword.
   *
   * Describes the query to build a fingerprint, then finds cached entities
   * with similar fingerprints. Also returns the query entity itself if
   * it has features.
   */
  search(query: string, limit: number = 5): ModelEntity[] {
    // Describe the query itself to build its fingerprint
    const self = this.describe(query)
    const results: ModelEntity[] = []

    if (self) {
      results.push(self)
    }

    // Find similar entities from cache
    const queryFp = this.fingerprints.get(query)
    if (queryFp) {
      const similar = this.findSimilarEntities(query, queryFp, limit - results.length)
      for (const sim of similar) {
        const described = this.describe(sim.entity)
        if (described) {
          results.push(described)
        }
      }
    }

    return results.slice(0, limit)
  }

  /**
   * Get raw gate KNN features for a token at a layer.
   * Useful for DreamEngine's VindexGateKnnProvider interface.
   */
  gateKnn(layer: number, tokenId: number, topK: number): FeatureHit[] {
    if (!this.loaded || !this.handle || !this.larql) return []
    return this.larql.vindexGateKnn(this.handle, layer, tokenId, topK)
  }

  /**
   * Tokenize text using the vindex's bundled tokenizer.
   */
  tokenize(text: string): number[] {
    if (!this.loaded || !this.handle || !this.larql) return []
    return this.larql.vindexTokenize(this.handle, text)
  }

  /**
   * Create a VindexGateKnnProvider compatible with DreamEngine.
   */
  asDreamProvider(): { tokenize: (text: string) => number[]; gateKnn: (layer: number, tokenId: number, topK: number) => Array<{ featureIndex: number; score: number }> } {
    return {
      tokenize: (text: string) => this.tokenize(text),
      gateKnn: (layer: number, tokenId: number, topK: number) => this.gateKnn(layer, tokenId, topK),
    }
  }

  /**
   * Summarize a fingerprint by layer bands (syntax, knowledge, output).
   */
  private summarizeByLayerBand(fingerprint: Map<string, number>): Array<{
    band: string
    featureCount: number
    maxScore: number
    peakLayer: number
    layerMin: number
    layerMax: number
  }> {
    const bands = [
      { name: 'syntax', min: 0, max: 13 },
      { name: 'knowledge', min: 14, max: 27 },
      { name: 'output', min: 28, max: 33 },
    ]

    return bands.map(band => {
      let featureCount = 0
      let maxScore = 0
      let peakLayer = band.min
      let layerMin = 999
      let layerMax = 0

      for (const [key, score] of fingerprint) {
        const layer = parseInt(key.split(':')[0].slice(1))
        if (layer >= band.min && layer <= band.max) {
          featureCount++
          if (score > maxScore) {
            maxScore = score
            peakLayer = layer
          }
          layerMin = Math.min(layerMin, layer)
          layerMax = Math.max(layerMax, layer)
        }
      }

      return {
        band: band.name,
        featureCount,
        maxScore,
        peakLayer,
        layerMin: layerMin === 999 ? band.min : layerMin,
        layerMax: layerMax === 0 ? band.max : layerMax,
      }
    }).filter(b => b.featureCount > 0)
  }

  /**
   * Find entities with similar feature fingerprints.
   * Uses Jaccard similarity of feature sets (same approach as DreamEngine).
   */
  private findSimilarEntities(
    entity: string,
    fingerprint: Map<string, number>,
    limit: number,
  ): Array<{ entity: string; similarity: number }> {
    const results: Array<{ entity: string; similarity: number }> = []

    for (const [otherEntity, otherFp] of this.fingerprints) {
      if (otherEntity === entity) continue

      let intersection = 0
      for (const key of fingerprint.keys()) {
        if (otherFp.has(key)) intersection++
      }

      const union = fingerprint.size + otherFp.size - intersection
      if (union === 0) continue

      const similarity = intersection / union
      if (similarity > 0.05) {
        results.push({ entity: otherEntity, similarity })
      }
    }

    results.sort((a, b) => b.similarity - a.similarity)
    return results.slice(0, limit)
  }

  private cacheResult(entity: string, result: ModelEntity | null): void {
    if (this.cache.size >= this.maxCacheSize) {
      const firstKey = this.cache.keys().next().value
      if (firstKey !== undefined) {
        this.cache.delete(firstKey)
        this.fingerprints.delete(firstKey)
      }
    }
    this.cache.set(entity, result)
  }

  getCacheStats(): { size: number; maxSize: number; fingerprintCount: number } {
    return {
      size: this.cache.size,
      maxSize: this.maxCacheSize,
      fingerprintCount: this.fingerprints.size,
    }
  }
}
