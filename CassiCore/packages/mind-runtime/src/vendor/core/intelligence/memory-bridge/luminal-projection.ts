/**
 * Luminal Projection — projects Mnemic Field luminal set into transformer hidden space.
 *
 * The key insight from LARQL: FFN contributes ~60% of answer signal at phase transition,
 * with typical FFN deltas of 50-100 logits. Memory contributions should be capped at
 * similar magnitude to not overwhelm model knowledge.
 *
 * Projection approaches:
 * 1. Learned projection matrix W_memory [hidden_size, embedding_dim]
 * 2. Direct embedding addition (if dimensions match)
 * 3. Mean pooling + scaling (simple fallback)
 */

import type { ILogger } from '@cassicore/foundation'
import type { LuminalSet, ChargedEngram, MnemicRetrievalHit } from '@cassicore/mnemic-field'
import type {
  MemoryDelta, MemoryContribution, MemoryInjectionConfig,
  ProjectionMatrix, BoundaryResidual,
} from './types.js'
import { MEMORY_INJECTION_DEFAULTS } from './types.js'
import { cosineSimilarity } from '@cassicore/mnemic-field'

/**
 * LuminalProjectionEngine — converts luminal set to hidden space vectors.
 */
export class LuminalProjectionEngine {
  private logger: ILogger
  private config: MemoryInjectionConfig
  private projectionMatrix: ProjectionMatrix | null = null

  constructor(
    private embeddingDim: number,
    private hiddenDim: number,
    logger: ILogger,
    config?: Partial<MemoryInjectionConfig>,
  ) {
    this.logger = logger.child ? logger.child('luminal-projection') : logger
    this.config = { ...MEMORY_INJECTION_DEFAULTS, ...config }

    if (this.config.useLearnedProjection) {
      this.initializeProjectionMatrix()
    }
  }

  /**
   * Project a luminal set into memory deltas for each injection layer.
   */
  projectLuminal(
    luminal: LuminalSet,
    layerWeights: Map<number, number>,
  ): Map<number, MemoryDelta> {
    const deltas = new Map<number, MemoryDelta>()

    if (luminal.engrams.length === 0) {
      this.logger.debug('Empty luminal set, no deltas to project')
      return deltas
    }

    // Filter by charge threshold
    const contributing = luminal.engrams.filter(e =>
      e.charge >= this.config.chargeThreshold
    )

    if (contributing.length === 0) {
      this.logger.debug('No engrams crossed charge threshold', {
        threshold: this.config.chargeThreshold,
        maxCharge: Math.max(...luminal.engrams.map(e => e.charge)),
      })
      return deltas
    }

    // Compute raw contribution vector (sum of weighted embeddings)
    const rawVector = this.computeRawVector(contributing)

    // Normalize and cap magnitude
    const normalizedVector = this.normalizeAndCap(rawVector)

    // Create deltas for each injection layer
    for (const layer of this.config.injectionLayers) {
      const weight = layerWeights.get(layer) ?? 1.0
      const layerVector = this.scaleVector(normalizedVector, weight)

      const contributions = this.buildContributions(contributing, layer, weight)

      deltas.set(layer, {
        vector: layerVector,
        contributions,
        magnitude: this.computeMagnitude(layerVector),
        contributingCount: contributing.length,
        layer,
        wasCapped: this.computeMagnitude(rawVector) > this.config.maxContribution,
      })
    }

    this.logger.debug('Projected luminal set', {
      engramCount: luminal.engrams.length,
      contributingCount: contributing.length,
      layers: this.config.injectionLayers,
      magnitude: this.computeMagnitude(normalizedVector),
    })

    return deltas
  }

  /**
   * Compute raw contribution vector from weighted embeddings.
   */
  private computeRawVector(engrams: ChargedEngram[]): Float32Array {
    const vector = new Float32Array(this.hiddenDim)

    for (const charged of engrams) {
      // Get embedding from engram
      const embedding = charged.engram.embedding
      if (!embedding) continue

      // Project embedding to hidden space
      const projected = this.projectSingleEmbedding(embedding)

      // Add weighted contribution
      const weight = charged.charge // Use charge as weight
      for (let i = 0; i < this.hiddenDim; i++) {
        vector[i] += projected[i] * weight
      }
    }

    return vector
  }

  /**
   * Project a single embedding to hidden space.
   */
  private projectSingleEmbedding(embedding: Float32Array): Float32Array {
    // If dimensions match, use direct addition
    if (embedding.length === this.hiddenDim) {
      return new Float32Array(embedding)
    }

    // If we have a learned projection matrix, use it
    if (this.projectionMatrix && this.projectionMatrix.isTrained) {
      return this.applyProjectionMatrix(embedding)
    }

    // Fallback: zero-pad or truncate
    const projected = new Float32Array(this.hiddenDim)
    const copyLen = Math.min(embedding.length, this.hiddenDim)
    for (let i = 0; i < copyLen; i++) {
      projected[i] = embedding[i]
    }
    return projected
  }

  /**
   * Apply learned projection matrix to embedding.
   */
  private applyProjectionMatrix(embedding: Float32Array): Float32Array {
    if (!this.projectionMatrix) {
      return new Float32Array(this.hiddenDim)
    }

    const weights = this.projectionMatrix.weights
    const bias = this.projectionMatrix.bias
    const result = new Float32Array(this.hiddenDim)

    // Matrix multiply: W @ embedding + bias
    // W is [hiddenDim, embeddingDim], embedding is [embeddingDim]
    for (let i = 0; i < this.hiddenDim; i++) {
      let sum = bias[i]
      for (let j = 0; j < this.embeddingDim; j++) {
        sum += weights[i * this.embeddingDim + j] * embedding[j]
      }
      result[i] = sum
    }

    return result
  }

  /**
   * Normalize vector and cap magnitude at maxContribution.
   */
  private normalizeAndCap(vector: Float32Array): Float32Array {
    const magnitude = this.computeMagnitude(vector)

    if (magnitude <= 0) {
      return vector
    }

    // Cap at max contribution
    const scale = Math.min(1.0, this.config.maxContribution / magnitude)

    const normalized = new Float32Array(vector.length)
    for (let i = 0; i < vector.length; i++) {
      normalized[i] = vector[i] * scale
    }

    return normalized
  }

  /**
   * Scale a vector by a weight factor.
   */
  private scaleVector(vector: Float32Array, weight: number): Float32Array {
    const scaled = new Float32Array(vector.length)
    for (let i = 0; i < vector.length; i++) {
      scaled[i] = vector[i] * weight
    }
    return scaled
  }

  /**
   * Compute magnitude of a vector.
   */
  private computeMagnitude(vector: Float32Array): number {
    let sum = 0
    for (let i = 0; i < vector.length; i++) {
      sum += vector[i] * vector[i]
    }
    return Math.sqrt(sum)
  }

  /**
   * Build contribution records for a layer.
   */
  private buildContributions(
    engrams: ChargedEngram[],
    layer: number,
    layerWeight: number,
  ): MemoryContribution[] {
    return engrams.map(charged => ({
      engramId: charged.engram.id,
      content: charged.engram.content.slice(0, 100),
      charge: charged.charge,
      matchType: 'direct_embedding' as const,  // contributing:ignore
      weight: charged.charge * layerWeight,
      layer,
    }))
  }

  /**
   * Initialize projection matrix (untrained state).
   */
  private initializeProjectionMatrix(): void {
    // Initialize with random weights (Xavier initialization)
    const weights = new Float32Array(this.hiddenDim * this.embeddingDim)
    const scale = Math.sqrt(2.0 / (this.embeddingDim + this.hiddenDim))

    for (let i = 0; i < weights.length; i++) {
      weights[i] = (Math.random() - 0.5) * 2 * scale
    }

    const bias = new Float32Array(this.hiddenDim)  // Zero bias

    this.projectionMatrix = {
      inputDim: this.embeddingDim,
      outputDim: this.hiddenDim,
      weights,
      bias,
      isTrained: false,
      trainingIterations: 0,
      updatedAt: new Date().toISOString(),
    }

    this.logger.info('Initialized projection matrix', {
      inputDim: this.embeddingDim,
      outputDim: this.hiddenDim,
      trainable: this.config.useLearnedProjection,
    })
  }

  /**
   * Get the projection matrix (for learning/consolidation).
   */
  getProjectionMatrix(): ProjectionMatrix | null {
    return this.projectionMatrix
  }

  /**
   * Update projection matrix (called from consolidation).
   */
  updateProjectionMatrix(
    weights: Float32Array,
    bias: Float32Array,
    iterations: number,
  ): void {
    if (!this.projectionMatrix) {
      this.logger.warn('No projection matrix to update')
      return
    }

    this.projectionMatrix.weights = weights
    this.projectionMatrix.bias = bias
    this.projectionMatrix.trainingIterations += iterations
    this.projectionMatrix.isTrained = this.projectionMatrix.trainingIterations >= 10
    this.projectionMatrix.updatedAt = new Date().toISOString()

    this.logger.info('Updated projection matrix', {
      iterations,
      totalIterations: this.projectionMatrix.trainingIterations,
      isTrained: this.projectionMatrix.isTrained,
    })
  }

  /**
   * Compute similarity between boundary residual and projected memories.
   * Used for portal discovery and correlation.
   */
  computeMemoryBoundaryCorrelation(
    boundary: BoundaryResidual,
    luminal: LuminalSet,
  ): number {
    if (luminal.engrams.length === 0) return 0

    // Get mean luminal embedding
    const meanEmbedding = new Float32Array(this.hiddenDim)
    let count = 0

    for (const charged of luminal.engrams) {
      if (!charged.engram.embedding) continue
      const projected = this.projectSingleEmbedding(charged.engram.embedding)
      for (let i = 0; i < this.hiddenDim; i++) {
        meanEmbedding[i] += projected[i] * charged.charge
      }
      count++
    }

    if (count === 0) return 0

    for (let i = 0; i < this.hiddenDim; i++) {
      meanEmbedding[i] /= count
    }

    return cosineSimilarity(boundary.vector, meanEmbedding)
  }
}