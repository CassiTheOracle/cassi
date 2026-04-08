import type { ILogger } from '../../../types/interfaces.js'
import type { Cortex } from './cortex.js'
import type {
  Engram, MnemicSynapse, ChargedEngram, LuminalSet,
  KindlingOptions, TaskComplexity, SpikeOutcome,
} from './types.js'
import {
  SPARK_POINT_DEFAULTS, KINDLING_DEFAULTS,
  SYNAPSE_PROPAGATION, POTENTIATION_DEFAULTS,
} from './types.js'

interface SeedResult {
  engramId: string
  charge: number
}

/**
 * The Kindling Engine: spreading activation over the Mnemic Field topology.
 *
 * Query → seed activation → excitation spreads through neighbors
 * → engrams crossing spark point enter Luminal Set → working memory.
 */
export class KindlingEngine {
  private logger: ILogger

  constructor(
    private cortex: Cortex,
    logger: ILogger,
  ) {
    this.logger = logger.child ? logger.child('kindling') : logger
  }

  /**
   * Run the full kindling process: seed → spread → ignite → return Luminal Set.
   */
  kindle(
    embedding: number[] | null,
    textQuery: string | null,
    options: KindlingOptions = {},
  ): LuminalSet {
    const start = Date.now()
    const complexity = options.complexity ?? 'normal'
    const maxIter = options.maxIterations ?? KINDLING_DEFAULTS.maxIterations
    const tol = options.convergenceTolerance ?? KINDLING_DEFAULTS.convergenceTolerance
    const maxSeeds = options.maxSeeds ?? KINDLING_DEFAULTS.maxSeeds
    const maxLuminal = options.maxLuminalSize ?? KINDLING_DEFAULTS.maxLuminalSize

    const seeds = this.findSeeds(embedding, textQuery, maxSeeds, options.includeText ?? true)
    if (seeds.length === 0) {
      return this.emptyLuminalSet(complexity, Date.now() - start)
    }

    const chargeMap = new Map<string, number>()
    for (const seed of seeds) {
      chargeMap.set(seed.engramId, seed.charge)
    }

    let iterations = 0
    for (let iter = 0; iter < maxIter; iter++) {
      iterations++
      const delta = this.spreadOnce(chargeMap)
      if (delta < tol) break
    }

    const sparkPoint = this.computeGlobalSparkPoint(complexity)
    const luminal = this.ignite(chargeMap, sparkPoint, maxLuminal)

    const durationMs = Date.now() - start
    this.logger.debug('Kindling complete', {
      seeds: seeds.length,
      iterations,
      luminalSize: luminal.length,
      durationMs,
    })

    return {
      engrams: luminal,
      totalCharge: luminal.reduce((s, e) => s + e.charge, 0),
      seedCount: seeds.length,
      iterationsUsed: iterations,
      sparkPoint,
      taskComplexity: complexity,
      durationMs,
    }
  }

  /**
   * Step 1: Find seed engrams from embedding similarity and/or text search.
   */
  private findSeeds(
    embedding: number[] | null,
    textQuery: string | null,
    maxSeeds: number,
    includeText: boolean,
  ): SeedResult[] {
    const seedMap = new Map<string, number>()

    if (embedding && embedding.length > 0) {
      const embeddingSeeds = this.findSeedsByEmbedding(embedding, maxSeeds)
      for (const s of embeddingSeeds) {
        seedMap.set(s.engramId, Math.max(seedMap.get(s.engramId) ?? 0, s.charge))
      }
    }

    if (textQuery && includeText) {
      const textSeeds = this.findSeedsByText(textQuery, Math.ceil(maxSeeds / 2))
      for (const s of textSeeds) {
        const existing = seedMap.get(s.engramId) ?? 0
        seedMap.set(s.engramId, Math.max(existing, s.charge * 0.8))
      }
    }

    return Array.from(seedMap.entries())
      .map(([engramId, charge]) => ({ engramId, charge }))
      .sort((a, b) => b.charge - a.charge)
      .slice(0, maxSeeds)
  }

  /**
   * Find seeds by embedding cosine similarity against all engrams with embeddings.
   */
  private findSeedsByEmbedding(queryEmb: number[], limit: number): SeedResult[] {
    const engrams = this.cortex.getAllEngrams()
    const withEmbeddings = engrams.filter(e => e.embedding && e.embedding.length > 0)

    if (withEmbeddings.length === 0) return []

    const scored = withEmbeddings.map(e => ({
      engramId: e.id,
      charge: cosineSimilarity(queryEmb, Array.from(e.embedding!)),
    }))

    return scored
      .filter(s => s.charge > 0.1)
      .sort((a, b) => b.charge - a.charge)
      .slice(0, limit)
  }

  /**
   * Find seeds by FTS5 text search.
   */
  private findSeedsByText(query: string, limit: number): SeedResult[] {
    const results = this.cortex.searchText(query, limit)
    return results.map(r => ({
      engramId: r.engram.id,
      charge: r.score,
    }))
  }

  /**
   * Step 2: One iteration of spreading excitation.
   * Returns the total absolute change in charge (for convergence detection).
   */
  private spreadOnce(chargeMap: Map<string, number>): number {
    const updates = new Map<string, number>()

    for (const [engramId, charge] of chargeMap) {
      if (charge < 0.01) continue

      const synapses = this.cortex.getNeighborSynapses(engramId)
      for (const syn of synapses) {
        const neighborId = syn.sourceId === engramId ? syn.targetId : syn.sourceId
        const neighborEngram = this.cortex.getEngram(neighborId)
        if (!neighborEngram) continue

        const sourceEngram = this.cortex.getEngram(engramId)
        if (!sourceEngram) continue

        const propagation = SYNAPSE_PROPAGATION[syn.edgeType] ?? 0.5
        const xyDist = euclideanDistance(sourceEngram, neighborEngram)
        const distDecay = 1 / (1 + KINDLING_DEFAULTS.distanceDecayRate * xyDist)

        const tDist = Math.abs(sourceEngram.t - neighborEngram.t)
        const temporalRelevance = 1 / (1 + KINDLING_DEFAULTS.temporalDecayRate * tDist)

        const potBoost = 1 + KINDLING_DEFAULTS.potentiationBoostScale * neighborEngram.potentiation

        const spread = charge * syn.weight * propagation * distDecay * temporalRelevance * potBoost

        const existing = updates.get(neighborId) ?? 0
        updates.set(neighborId, existing + spread)
      }
    }

    let totalDelta = 0
    for (const [id, additionalCharge] of updates) {
      const dampened = additionalCharge * KINDLING_DEFAULTS.spreadDampening
      const oldCharge = chargeMap.get(id) ?? 0
      const newCharge = oldCharge + dampened
      chargeMap.set(id, newCharge)
      totalDelta += Math.abs(dampened)
    }

    return totalDelta
  }

  /**
   * Step 4: Ignite — collect engrams above their effective spark point.
   */
  private ignite(
    chargeMap: Map<string, number>,
    globalSparkPoint: number,
    maxSize: number,
  ): ChargedEngram[] {
    const candidates: ChargedEngram[] = []

    for (const [engramId, charge] of chargeMap) {
      const engram = this.cortex.getEngram(engramId)
      if (!engram) continue

      const effectiveSparkPoint = globalSparkPoint -
        engram.potentiation * SPARK_POINT_DEFAULTS.potentiationScale

      if (charge >= Math.max(0.01, effectiveSparkPoint)) {
        candidates.push({ engram, charge })
      }
    }

    return candidates
      .sort((a, b) => b.charge - a.charge)
      .slice(0, maxSize)
  }

  /**
   * Step 6: Post-task update — record spikes, optionally drift positions.
   */
  recordActivation(
    luminalSet: LuminalSet,
    taskContext?: string,
    outcome?: SpikeOutcome,
  ): void {
    if (luminalSet.engrams.length === 0) return

    const maxCharge = Math.max(...luminalSet.engrams.map(e => e.charge))
    const outcomeMultiplier = outcome === 'success' ? 1.5
      : outcome === 'failure' ? 0.5
      : 1.0

    for (const { engram, charge } of luminalSet.engrams) {
      const magnitude = (charge / Math.max(maxCharge, 0.01)) * outcomeMultiplier
      this.cortex.recordSpike({
        engramId: engram.id,
        magnitude,
        taskContext,
        outcome,
      })
    }

    this.driftCoActivated(luminalSet.engrams)

    this.logger.debug('Activation recorded', {
      engramCount: luminalSet.engrams.length,
      taskContext,
      outcome,
    })
  }

  /**
   * XY drift: pull co-activated engrams toward their co-activated neighbors.
   * Only drifts toward directly connected neighbors, not global centroid.
   */
  private driftCoActivated(charged: ChargedEngram[]): void {
    if (charged.length < 2) return

    const learningRate = KINDLING_DEFAULTS.driftLearningRate
    const activeIds = new Set(charged.map(e => e.engram.id))
    const chargeMap = new Map(charged.map(e => [e.engram.id, e.charge]))
    const updates: Array<{ id: string; x: number; y: number }> = []

    for (const { engram, charge } of charged) {
      const synapses = this.cortex.getNeighborSynapses(engram.id)
      let pullX = 0, pullY = 0, pullWeight = 0

      for (const syn of synapses) {
        const neighborId = syn.sourceId === engram.id ? syn.targetId : syn.sourceId
        if (!activeIds.has(neighborId)) continue

        const neighborEngram = this.cortex.getEngram(neighborId)
        if (!neighborEngram) continue

        const neighborCharge = chargeMap.get(neighborId) ?? 0
        const w = syn.weight * Math.min(neighborCharge, 1.0)
        pullX += (neighborEngram.x - engram.x) * w
        pullY += (neighborEngram.y - engram.y) * w
        pullWeight += w
      }

      if (pullWeight > 0) {
        const scale = learningRate * Math.min(charge, 1.0)
        const newX = engram.x + scale * (pullX / pullWeight)
        const newY = engram.y + scale * (pullY / pullWeight)

        if (Math.abs(newX - engram.x) > 0.0001 || Math.abs(newY - engram.y) > 0.0001) {
          updates.push({ id: engram.id, x: newX, y: newY })
        }
      }
    }

    if (updates.length > 0) {
      this.cortex.bulkUpdatePositions(updates)
    }
  }

  private computeGlobalSparkPoint(complexity: TaskComplexity): number {
    const modifier = SPARK_POINT_DEFAULTS.taskModifiers[complexity]
    return SPARK_POINT_DEFAULTS.baseThreshold * modifier
  }

  private emptyLuminalSet(complexity: TaskComplexity, durationMs: number): LuminalSet {
    return {
      engrams: [],
      totalCharge: 0,
      seedCount: 0,
      iterationsUsed: 0,
      sparkPoint: this.computeGlobalSparkPoint(complexity),
      taskComplexity: complexity,
      durationMs,
    }
  }
}

function cosineSimilarity(a: number[], b: number[]): number {
  if (a.length !== b.length || a.length === 0) return 0
  let dot = 0, normA = 0, normB = 0
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i]
    normA += a[i] * a[i]
    normB += b[i] * b[i]
  }
  const denom = Math.sqrt(normA) * Math.sqrt(normB)
  return denom > 0 ? dot / denom : 0
}

function euclideanDistance(a: Engram, b: Engram): number {
  return Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)
}
