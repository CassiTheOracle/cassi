import type { ILogger } from '../../../types/interfaces.js'
import { cosineSimilarity } from './cortex.js'
import type { Cortex } from './cortex.js'
import { affectSimilarity } from './affect.js'
import type { FilamentCortex } from './filament-cortex.js'
import type {
  Engram, MnemicSynapse, ChargedEngram, LuminalSet,
  KindlingOptions, KindlingTrace, TaskComplexity, SpikeOutcome,
  FilamentAnnotation, FilamentMatchType, FilamentSynapseType,
  NeuralKindlingConfig, ForwardRecord, ForwardTape,
} from './types.js'
import {
  SPARK_POINT_DEFAULTS, KINDLING_DEFAULTS, AFFECT_DEFAULTS,
  SYNAPSE_PROPAGATION, POTENTIATION_DEFAULTS,
  FILAMENT_KINDLING_DEFAULTS, FILAMENT_SYNAPSE_PROPAGATION,
  NEURAL_KINDLING_DEFAULTS,
} from './types.js'

interface SeedResult {
  engramId: string
  charge: number
}

interface MatchedFilamentInfo {
  engramId: string
  content: string
  similarity: number
  matchType: FilamentMatchType
  expansionPath?: FilamentAnnotation['expansionPath']
}

/**
 * The Kindling Engine: spreading activation over the Mnemic Field topology.
 *
 * Query → seed activation → excitation spreads through neighbors
 * → engrams crossing spark point enter Luminal Set → working memory.
 *
 * When neural kindling is enabled, spreading uses nonlinear activation functions
 * and records forward tapes for gradient-based learning during consolidation.
 */
export class KindlingEngine {
  private logger: ILogger
  private matchedFilaments: Map<number, MatchedFilamentInfo> = new Map()
  private currentAffect: { valence: number; arousal: number } | null = null
  private neuralConfig: NeuralKindlingConfig
  private lastTape: ForwardTape | null = null

  constructor(
    private cortex: Cortex,
    logger: ILogger,
    private filamentCortex: FilamentCortex | null = null,
    neuralConfig?: Partial<NeuralKindlingConfig>,
  ) {
    this.logger = logger.child ? logger.child('kindling') : logger
    this.neuralConfig = { ...NEURAL_KINDLING_DEFAULTS, ...neuralConfig }
  }

  getLastTape(): ForwardTape | null {
    return this.lastTape
  }

  getNeuralConfig(): NeuralKindlingConfig {
    return { ...this.neuralConfig }
  }

  setNeuralConfig(config: Partial<NeuralKindlingConfig>): void {
    this.neuralConfig = { ...this.neuralConfig, ...config }
  }

  /**
   * Run the full kindling process: seed → spread → ignite → return Luminal Set.
   *
   * When neural kindling is enabled, the forward computation graph is recorded
   * as a "tape" for later backpropagation during consolidation.
   */
  kindle(
    embedding: number[] | null,
    textQuery: string | null,
    options: KindlingOptions = {},
  ): LuminalSet {
    const start = Date.now()
    this.matchedFilaments = new Map()
    this.lastTape = null
    this.currentAffect = options.currentAffect ?? null
    const complexity = options.complexity ?? 'normal'
    const maxIter = options.maxIterations ?? KINDLING_DEFAULTS.maxIterations
    const tol = options.convergenceTolerance ?? KINDLING_DEFAULTS.convergenceTolerance
    const maxSeeds = options.maxSeeds ?? KINDLING_DEFAULTS.maxSeeds
    const maxLuminal = options.maxLuminalSize ?? KINDLING_DEFAULTS.maxLuminalSize

    const neural = this.neuralConfig.enabled
    const shouldRecordTape = neural && this.neuralConfig.tapeRecording

    const seeds = this.findSeeds(embedding, textQuery, options)
    if (seeds.length === 0) {
      return this.emptyLuminalSet(complexity, Date.now() - start)
    }

    const chargeMap = new Map<string, number>()
    const currentAffect = options.currentAffect
    for (const seed of seeds) {
      let charge = seed.charge
      if (currentAffect) {
        const engram = this.cortex.getEngram(seed.engramId)
        const engramAffect = engram?.metadata?.affect as { valence: number; arousal: number } | undefined
        if (engramAffect) {
          const resonance = affectSimilarity(currentAffect, engramAffect)
          charge *= 1 + AFFECT_DEFAULTS.resonanceFactor * resonance
        }
      }
      chargeMap.set(seed.engramId, charge)
    }

    const trace: KindlingTrace[] = []
    const recording = options.recordTrace === true
    const tapeRecords: ForwardRecord[] = shouldRecordTape ? [] : []

    if (recording) {
      trace.push({ iteration: 0, charges: Object.fromEntries(chargeMap) })
    }

    const seedCharges = shouldRecordTape ? Object.fromEntries(chargeMap) : undefined

    let iterations = 0
    for (let iter = 0; iter < maxIter; iter++) {
      iterations++
      const delta = neural
        ? this.spreadOnceNeural(chargeMap, iter + 1, shouldRecordTape ? tapeRecords : undefined)
        : this.spreadOnce(chargeMap)
      if (recording) {
        trace.push({ iteration: iterations, charges: Object.fromEntries(chargeMap) })
      }
      if (delta < tol) break
    }

    let sparkPoint = this.computeGlobalSparkPoint(complexity)
    if (this.currentAffect) {
      const arousalShift = (this.currentAffect.arousal - AFFECT_DEFAULTS.baselineArousal) * AFFECT_DEFAULTS.arousalSparkModulation
      sparkPoint *= (1 - arousalShift)
    }
    const luminal = this.ignite(chargeMap, sparkPoint, maxLuminal)

    const filamentAnnotations = this.annotateFilaments(luminal)

    if (shouldRecordTape && seedCharges) {
      const tapeId = `tape_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
      this.lastTape = {
        id: tapeId,
        createdAt: Date.now(),
        seedCharges,
        records: tapeRecords,
        outputCharges: Object.fromEntries(chargeMap),
        sparkPoint,
        luminalIds: luminal.map(e => e.engram.id),
      }
      try {
        this.cortex.storeForwardTape(this.lastTape)
      } catch (err) {
        this.logger.warn('Failed to store forward tape', { error: err })
      }
    }

    const durationMs = Date.now() - start
    this.logger.debug('Kindling complete', {
      seeds: seeds.length,
      iterations,
      luminalSize: luminal.length,
      filamentMatches: this.matchedFilaments.size,
      neural,
      tapeRecorded: shouldRecordTape && tapeRecords.length > 0,
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
      filamentAnnotations: filamentAnnotations.length > 0 ? filamentAnnotations : undefined,
      trace: recording ? trace : undefined,
    }
  }

  /**
   * Step 1: Find seed engrams from embedding similarity and/or text search.
   */
  private findSeeds(
    embedding: number[] | null,
    textQuery: string | null,
    options: KindlingOptions = {},
  ): SeedResult[] {
    const maxSeeds = options.maxSeeds ?? KINDLING_DEFAULTS.maxSeeds
    const includeText = options.includeText ?? true
    const seedMap = new Map<string, number>()

    if (embedding && embedding.length > 0) {
      mergeSeeds(seedMap, this.findSeedsByEmbedding(embedding, maxSeeds))
    }

    if (textQuery && includeText) {
      mergeSeeds(seedMap, this.findSeedsByText(textQuery, Math.ceil(maxSeeds / 2)), 0.8)
    }

    if (this.filamentCortex && options.enableFilaments !== false) {
      const bestEngramCharge = Math.max(0, ...Array.from(seedMap.values()))
      const lazyThreshold = FILAMENT_KINDLING_DEFAULTS.lazyThreshold

      if (bestEngramCharge < lazyThreshold) {
        const maxFilSeeds = options.maxFilamentSeeds ?? FILAMENT_KINDLING_DEFAULTS.maxFilamentSeeds
        const boost = options.filamentPrecisionBoost ?? FILAMENT_KINDLING_DEFAULTS.precisionBoost

        if (embedding && embedding.length > 0) {
          mergeSeeds(seedMap, this.findFilamentsByEmbedding(embedding, maxFilSeeds, boost))
        }

        if (textQuery && includeText) {
          mergeSeeds(seedMap, this.findFilamentsByText(textQuery, Math.ceil(maxFilSeeds / 2), boost))
        }

        const maxExpansions = options.maxFilamentExpansions ?? FILAMENT_KINDLING_DEFAULTS.maxFilamentExpansions
        this.expandSeedsThroughFilaments(seedMap, maxExpansions, options.chaseSupersessions ?? true)
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
    const embData = this.cortex.getEmbeddingVectors(50000)

    if (embData.length === 0) return []

    const scored = embData.map(e => ({
      engramId: e.id,
      charge: cosineSimilarity(queryEmb, Array.from(e.embedding)),
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
   * Step 2: One iteration of spreading excitation (original, linear).
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

        let emotionalDamping = 1.0
        if (this.currentAffect) {
          const nAffect = neighborEngram.metadata?.affect as { valence: number; arousal: number } | undefined
          if (nAffect) {
            const congruence = affectSimilarity(this.currentAffect, nAffect)
            if (congruence < 0.5) {
              emotionalDamping = 1 - AFFECT_DEFAULTS.dampingFactor * (1 - congruence)
            }
          }
        }

        const spread = charge * syn.weight * propagation * distDecay * temporalRelevance * potBoost * emotionalDamping

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
   * Step 2 (Neural): One iteration of spreading with nonlinear activation and bias.
   *
   * Key differences from linear spreadOnce():
   * 1. Incoming contributions are aggregated per target node, then a bias (from potentiation)
   *    is added, and a nonlinear activation function is applied.
   * 2. Optionally records every contribution to a forward tape for backpropagation.
   *
   * This turns the Mnemic Field into a genuine message-passing neural network layer.
   */
  private spreadOnceNeural(
    chargeMap: Map<string, number>,
    iteration: number,
    tape?: ForwardRecord[],
  ): number {
    const aggregated = new Map<string, number>()
    const biasScale = this.neuralConfig.biasScale

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

        let emotionalDamping = 1.0
        if (this.currentAffect) {
          const nAffect = neighborEngram.metadata?.affect as { valence: number; arousal: number } | undefined
          if (nAffect) {
            const congruence = affectSimilarity(this.currentAffect, nAffect)
            if (congruence < 0.5) {
              emotionalDamping = 1 - AFFECT_DEFAULTS.dampingFactor * (1 - congruence)
            }
          }
        }

        const rawContribution = charge * syn.weight * propagation * distDecay * temporalRelevance * potBoost * emotionalDamping

        const existing = aggregated.get(neighborId) ?? 0
        aggregated.set(neighborId, existing + rawContribution)

        if (tape) {
          tape.push({
            iteration,
            sourceId: engramId,
            targetId: neighborId,
            edgeType: syn.edgeType,
            synapseWeight: syn.weight,
            sourceCharge: charge,
            propagationFactor: propagation,
            distDecay,
            temporalRelevance,
            potBoost,
            emotionalDamping,
            rawContribution,
            activatedOutput: 0,  // filled in below
            preActivation: 0,    // filled in below
          })
        }
      }
    }

    let totalDelta = 0
    for (const [id, rawInput] of aggregated) {
      const engram = this.cortex.getEngram(id)
      const bias = (engram?.potentiation ?? 0) * biasScale
      const dampened = rawInput * KINDLING_DEFAULTS.spreadDampening
      const oldCharge = chargeMap.get(id) ?? 0
      const preActivation = oldCharge + dampened + bias
      const activated = this.activate(preActivation)

      chargeMap.set(id, activated)
      totalDelta += Math.abs(activated - oldCharge)

      if (tape) {
        const records = tape.filter(r => r.iteration === iteration && r.targetId === id)
        for (const record of records) {
          record.preActivation = preActivation
          record.activatedOutput = activated
        }
      }
    }

    return totalDelta
  }

  /**
   * Apply the configured nonlinear activation function.
   * This is the key addition that makes spreading activation behave like
   * a neural network layer — introducing nonlinearity allows the system
   * to learn non-linear separations in the memory space.
   */
  private activate(x: number): number {
    switch (this.neuralConfig.activationFn) {
      case 'leaky_relu':
        return x > 0 ? x : this.neuralConfig.leakyReluSlope * x
      case 'sigmoid':
        return 1 / (1 + Math.exp(-x))
      case 'tanh':
        return Math.tanh(x)
      case 'linear':
      default:
        return x
    }
  }

  /**
   * Compute the derivative of the activation function at x.
   * Needed for backpropagation during consolidation.
   */
  activationDerivative(x: number): number {
    switch (this.neuralConfig.activationFn) {
      case 'leaky_relu':
        return x > 0 ? 1 : this.neuralConfig.leakyReluSlope
      case 'sigmoid': {
        const s = 1 / (1 + Math.exp(-x))
        return s * (1 - s)
      }
      case 'tanh': {
        const t = Math.tanh(x)
        return 1 - t * t
      }
      case 'linear':
      default:
        return 1
    }
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
    this.recordFilamentCoActivation()

    this.logger.debug('Activation recorded', {
      engramCount: luminalSet.engrams.length,
      taskContext,
      outcome,
    })
  }

  private recordFilamentCoActivation(): void {
    if (!this.filamentCortex || this.matchedFilaments.size < 2) return

    const directMatches = Array.from(this.matchedFilaments.entries())
      .filter(([_, info]) => info.matchType === 'direct_embedding' || info.matchType === 'direct_text')

    const minSim = FILAMENT_KINDLING_DEFAULTS.coActivationMinSimilarity

    for (let i = 0; i < directMatches.length; i++) {
      for (let j = i + 1; j < directMatches.length; j++) {
        const [idA, infoA] = directMatches[i]
        const [idB, infoB] = directMatches[j]

        if (infoA.engramId === infoB.engramId) continue

        const approxSim = Math.min(infoA.similarity, infoB.similarity)
        if (approxSim < minSim) continue

        this.filamentCortex.upsertCoActivationSynapse(idA, idB, approxSim)
      }
    }
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

  private findFilamentsByEmbedding(queryEmb: number[], limit: number, boost: number): SeedResult[] {
    if (!this.filamentCortex) return []

    const embData = this.filamentCortex.getFilamentEmbeddingsWithContent(50000)
    if (embData.length === 0) return []

    const contextPenalty = FILAMENT_KINDLING_DEFAULTS.contextPenalty

    const scored = embData.map(f => ({
      filamentId: f.id,
      engramId: f.engramId,
      content: f.content,
      similarity: cosineSimilarity(queryEmb, Array.from(f.embedding)),
    }))

    const filtered = scored
      .filter(s => s.similarity > 0.1)
      .sort((a, b) => b.similarity - a.similarity)
      .slice(0, limit)

    for (const match of filtered) {
      this.matchedFilaments.set(match.filamentId, {
        engramId: match.engramId,
        content: match.content,
        similarity: match.similarity,
        matchType: 'direct_embedding',
      })
    }

    return filtered.map(f => ({
      engramId: f.engramId,
      charge: f.similarity * boost * contextPenalty,
    }))
  }

  private findFilamentsByText(query: string, limit: number, boost: number): SeedResult[] {
    if (!this.filamentCortex) return []

    const contextPenalty = FILAMENT_KINDLING_DEFAULTS.contextPenalty
    const results = this.filamentCortex.searchFilamentsText(query, limit)

    for (const { filament, score } of results) {
      this.matchedFilaments.set(filament.id, {
        engramId: filament.engramId,
        content: filament.content,
        similarity: score,
        matchType: 'direct_text',
      })
    }

    return results.map(r => ({
      engramId: r.filament.engramId,
      charge: r.score * boost * contextPenalty,
    }))
  }

  private expandSeedsThroughFilaments(
    seedMap: Map<string, number>,
    maxExpansions: number,
    chaseSupersessions: boolean,
  ): void {
    if (!this.filamentCortex) return

    const expansions: Array<{ engramId: string; charge: number }> = []
    const snapshot = [...this.matchedFilaments.entries()]

    for (const [filamentId, info] of snapshot) {
      const synapses = this.filamentCortex.getFilamentSynapsesFrom(filamentId)
      for (const syn of synapses) {
        const propagation = FILAMENT_SYNAPSE_PROPAGATION[syn.edgeType as FilamentSynapseType] ?? 0.3
        const derivedCharge = info.similarity * syn.weight * syn.confidence * propagation

        const targetFilament = this.filamentCortex.getFilament(syn.targetId)
        if (!targetFilament) continue

        if (!this.matchedFilaments.has(syn.targetId)) {
          this.matchedFilaments.set(syn.targetId, {
            engramId: targetFilament.engramId,
            content: targetFilament.content,
            similarity: derivedCharge,
            matchType: 'synapse_expansion',
            expansionPath: {
              sourceFilamentId: filamentId,
              edgeType: syn.edgeType as FilamentSynapseType,
              sourceContent: info.content,
            },
          })
        }

        expansions.push({ engramId: targetFilament.engramId, charge: derivedCharge })

        if (chaseSupersessions && syn.edgeType === 'supersedes') {
          const terminal = this.chaseSupersessionChain(syn.targetId)
          if (terminal && !this.matchedFilaments.has(terminal.id)) {
            this.matchedFilaments.set(terminal.id, {
              engramId: terminal.engramId,
              content: terminal.content,
              similarity: derivedCharge * 1.1,
              matchType: 'supersession_chase',
            })
            expansions.push({ engramId: terminal.engramId, charge: derivedCharge * 1.1 })
          }
        }
      }
    }

    const topExpansions = expansions
      .sort((a, b) => b.charge - a.charge)
      .slice(0, maxExpansions)
    mergeSeeds(seedMap, topExpansions)
  }

  private chaseSupersessionChain(
    filamentId: number,
  ): { id: number; engramId: string; content: string } | null {
    if (!this.filamentCortex) return null

    const maxHops = FILAMENT_KINDLING_DEFAULTS.maxSupersessionHops
    let currentId = filamentId
    let result: { id: number; engramId: string; content: string } | null = null

    for (let hop = 0; hop < maxHops; hop++) {
      const incoming = this.filamentCortex.getFilamentSynapsesTo(currentId)
      const superseder = incoming.find(s => s.edgeType === 'supersedes')
      if (!superseder) break

      const filament = this.filamentCortex.getFilament(superseder.sourceId)
      if (!filament) break

      result = { id: filament.id, engramId: filament.engramId, content: filament.content }
      currentId = superseder.sourceId
    }

    return result
  }

  private annotateFilaments(luminal: ChargedEngram[]): FilamentAnnotation[] {
    const luminalIds = new Set(luminal.map(e => e.engram.id))
    const annotations: FilamentAnnotation[] = []

    for (const [filamentId, info] of this.matchedFilaments) {
      if (!luminalIds.has(info.engramId)) continue

      annotations.push({
        filamentId,
        engramId: info.engramId,
        content: info.content,
        matchType: info.matchType,
        similarity: info.similarity,
        expansionPath: info.expansionPath,
      })
    }

    return annotations
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

function mergeSeeds(
  seedMap: Map<string, number>,
  seeds: Array<{ engramId: string; charge: number }>,
  chargeScale = 1.0,
): void {
  for (const s of seeds) {
    const charge = s.charge * chargeScale
    seedMap.set(s.engramId, Math.max(seedMap.get(s.engramId) ?? 0, charge))
  }
}

function euclideanDistance(a: Engram, b: Engram): number {
  return Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)
}
