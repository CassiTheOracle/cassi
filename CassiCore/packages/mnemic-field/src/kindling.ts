import type { ILogger } from '../../../types/interfaces.js'
import type { Cortex } from './cortex.js'
import { affectSimilarity } from './affect.js'
import type { AttractorManager } from './attractor.js'
import type {
  Engram, MnemicSynapse, ChargedEngram, LuminalSet,
  KindlingOptions, KindlingTrace, TaskComplexity, SpikeOutcome,
  NeuralKindlingConfig, ForwardRecord, ForwardTrace,
} from './types.js'
import {
  SPARK_POINT_DEFAULTS, KINDLING_DEFAULTS, AFFECT_DEFAULTS,
  SYNAPSE_PROPAGATION,
  NEURAL_KINDLING_DEFAULTS,
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
 *
 * When neural kindling is enabled, spreading uses nonlinear activation functions
 * and records forward traces for gradient-based learning during consolidation.
 */
export class KindlingEngine {
  private logger: ILogger
  private currentAffect: { valence: number; arousal: number } | null = null
  private neuralConfig: NeuralKindlingConfig
  private lastTrace: ForwardTrace | null = null
  private attractor: AttractorManager | null = null
  /** Optional: provides the current harmony metric for spark point modulation. */
  private harmonyProvider: (() => number) | null = null
  /** Optional: provides broadcast spark modulation for an engram, keyed by clusterId. */
  private broadcastModProvider: ((clusterId: string | null) => number) | null = null
  /** FeatureIndex for vindex-native seed finding and photon spread (replaces ANN). */
  private featureIndex: {
    lookup: (text: string, opts?: any) => Array<{ engramId: string; sharedFeatureCount: number }>
    findCorrelated: (engramId: string, opts?: any) => Array<{ engramId: string; sharedFeatureCount: number }>
    isReady: () => boolean
  } | null = null

  /** Photon feature-overlap cache: emitterId → correlated engrams (avoids repeat FeatureIndex queries). */
  private photonCache = new Map<string, Array<{ engramId: string; sharedFeatureCount: number }>>()
  private static readonly PHOTON_CACHE_MAX = 5000

  constructor(
    private cortex: Cortex,
    logger: ILogger,
    neuralConfig?: Partial<NeuralKindlingConfig>,
  ) {
    this.logger = logger.child ? logger.child('kindling') : logger
    this.neuralConfig = { ...NEURAL_KINDLING_DEFAULTS, ...neuralConfig }
  }

  /** Wire the attractor for radial attention bias. */
  setAttractor(attractor: AttractorManager | null): void {
    this.attractor = attractor
  }

  /** Set a provider for the harmony metric (Yin/Yang balance, Phase 0-1). */
  setHarmonyProvider(provider: (() => number) | null): void {
    this.harmonyProvider = provider
  }

  /** Wire the FeatureIndex for vindex-native seed finding and photon spread. */
  setFeatureIndex(fi: {
    lookup: (text: string, opts?: any) => Array<{ engramId: string; sharedFeatureCount: number }>
    findCorrelated: (engramId: string, opts?: any) => Array<{ engramId: string; sharedFeatureCount: number }>
    isReady: () => boolean
  } | null): void {
    this.featureIndex = fi
  }

  /** Set a provider for broadcast spark modulation (global workspace priming). */
  setBroadcastModProvider(provider: ((clusterId: string | null) => number) | null): void {
    this.broadcastModProvider = provider
  }

  /** Invalidate the photon feature-overlap cache. */
  invalidatePhotonCache(): void {
    this.photonCache.clear()
  }

  getLastTrace(): ForwardTrace | null {
    return this.lastTrace
  }

  getNeuralConfig(): NeuralKindlingConfig {
    return { ...this.neuralConfig }
  }

  setNeuralConfig(config: Partial<NeuralKindlingConfig>): void {
    this.neuralConfig = { ...this.neuralConfig, ...config }
  }

  /** Check if an engram is a bridge (structural, not content). */
  private isBridge(engram: Engram | null | undefined): boolean {
    return engram?.nodeType === 'bridge'
  }

  /**
   * Run the full kindling process: seed → spread → ignite → return Luminal Set.
   *
   * When neural kindling is enabled, the forward computation graph is recorded
   * as a "trace" for later backpropagation during consolidation.
   */
  kindle(
    embedding: number[] | null,
    textQuery: string | null,
    options: KindlingOptions = {},
  ): LuminalSet {
    const start = Date.now()
    this.lastTrace = null
    this.currentAffect = options.currentAffect ?? null
    const complexity = options.complexity ?? 'normal'
    const maxIter = options.maxIterations ?? KINDLING_DEFAULTS.maxIterations
    const tol = options.convergenceTolerance ?? KINDLING_DEFAULTS.convergenceTolerance
    const maxSeeds = options.maxSeeds ?? KINDLING_DEFAULTS.maxSeeds
    const maxLuminal = options.maxLuminalSize ?? KINDLING_DEFAULTS.maxLuminalSize

    const neural = this.neuralConfig.enabled
    const shouldRecordTrace = neural && this.neuralConfig.traceRecording

    const seeds = this.findSeeds(embedding, textQuery, options)
    this.logger.info('kindling seeds found', { seedCount: seeds.length, hasEmbedding: !!embedding, embeddingDim: embedding?.length ?? 0, hasText: !!textQuery })
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

    // Pre-kindling: attention boost — seeds close to attention get gentle charge.
    // Warms up attended engrams so they're more likely to survive ignition.
    const attentionVector = options.attentionEmbedding
    if (attentionVector) {
      const seedIds = seeds.map(s => s.engramId)
      const seedEmbs = this.cortex.getEngramEmbeddings(seedIds)
      for (const seedId of seedIds) {
        const emb = seedEmbs.get(seedId)
        if (!emb || emb.length !== attentionVector.length) continue
        const dot = dotProductFloat32(emb, attentionVector)
        // cosSim ∈ [-1, 1] — only boost positive alignment
        if (dot > 0.5) {
          const current = chargeMap.get(seedId) ?? 0
          chargeMap.set(seedId, current + 0.05 * dot)
        }
      }
    }

    const trace: KindlingTrace[] = []
    const recording = options.recordTrace === true
    const traceRecords: ForwardRecord[] = shouldRecordTrace ? [] : []

    if (recording) {
      trace.push({ iteration: 0, charges: Object.fromEntries(chargeMap) })
    }

    const seedCharges = shouldRecordTrace ? Object.fromEntries(chargeMap) : undefined

    let iterations = 0
    for (let iter = 0; iter < maxIter; iter++) {
      iterations++
      const delta = neural
        ? this.spreadOnceNeural(chargeMap, iter + 1, attentionVector, shouldRecordTrace ? traceRecords : undefined)
        : this.spreadOnce(chargeMap, attentionVector)
      // Photon spread: first iteration only, wireless discovery of latent connections
      if (iter === 0) {
        this.photonSpread(chargeMap)
      }
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
    this.logger.info('kindling ignition', { luminalSize: luminal.length, sparkPoint: sparkPoint.toFixed(3), chargeMapSize: chargeMap.size })

    if (shouldRecordTrace && seedCharges) {
      const traceId = `trace_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
      this.lastTrace = {
        id: traceId,
        createdAt: Date.now(),
        seedCharges,
        records: traceRecords,
        outputCharges: Object.fromEntries(chargeMap),
        sparkPoint,
        luminalIds: luminal.map(e => e.engram.id),
      }
      try {
        this.cortex.storeForwardTrace(this.lastTrace)
      } catch (err) {
        this.logger.warn('Failed to store forward trace', { error: err })
      }
    }

    // Filter bridge engrams from results — they're structural, not content.
    const contentEngrams = luminal.filter(e => !this.isBridge(e.engram))

    const durationMs = Date.now() - start
    this.logger.debug('Kindling complete', {
      seeds: seeds.length,
      iterations,
      luminalSize: luminal.length,
      contentSize: contentEngrams.length,
      neural,
      traceRecorded: shouldRecordTrace && traceRecords.length > 0,
      durationMs,
    })

    return {
      engrams: contentEngrams,
      totalCharge: contentEngrams.reduce((s, e) => s + e.charge, 0),
      seedCount: seeds.length,
      iterationsUsed: iterations,
      sparkPoint,
      taskComplexity: complexity,
      durationMs,
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

    // Vindex-native path: FeatureIndex lookup replaces ANN cosine scan.
    // The model's gateKnn activation pattern IS the retrieval index —
    // no embedding needed, no dimension mismatch, causal-ready.
    if (textQuery && this.featureIndex?.isReady()) {
      mergeSeeds(seedMap, this.findSeedsByFeatureIndex(textQuery, maxSeeds))
    }

    if (textQuery && includeText) {
      mergeSeeds(seedMap, this.findSeedsByText(textQuery, Math.ceil(maxSeeds / 2)), 0.8)
    }

    // Apply radial attention boost when attractor is wired
    if (this.attractor) {
      const ids = [...seedMap.keys()]
      const engrams = this.cortex.getEngrams(ids)
      for (const engram of engrams) {
        const charge = seedMap.get(engram.id)
        if (charge === undefined) continue
        const r = (engram.metadata as any)?.r as number | undefined
        const theta = (engram.metadata as any)?.theta as number | undefined
        if (r !== undefined && theta !== undefined) {
          const boost = this.attractor.radialBoost(r, theta)
          if (options.shadow) {
            // Shadow mode (Phase 2: Yin/Yang): invert bias.
            // Boost engrams FAR from attractor. boost ∈ [0,1], so 2.0−boost ∈ [1,2].
            seedMap.set(engram.id, charge * (2.0 - boost))
          } else {
            // Normal mode: near engrams get boosted.
            seedMap.set(engram.id, charge * (1.0 + boost))
          }
        }
      }
    }

    return Array.from(seedMap.entries())
      .map(([engramId, charge]) => ({ engramId, charge }))
      .sort((a, b) => b.charge - a.charge)
      .slice(0, maxSeeds)
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
   * Find seeds by vindex feature overlap — direct FeatureIndex lookup.
   *
   * Runs gateKnn on the query text, looks up engrams that share those model
   * features, and ranks by shared feature count. No embedding, no cosine scan,
   * no dimension mismatch. The model's internal activation pattern IS the index.
   *
   * Charge is normalized: sharedFeatureCount / maxSharedFeatureCount.
   */
  private findSeedsByFeatureIndex(
    textQuery: string,
    limit: number,
    options?: { layers?: number[]; featuresPerLayer?: number; minScore?: number },
  ): SeedResult[] {
    if (!this.featureIndex?.isReady()) return []

    const hits = this.featureIndex.lookup(textQuery, {
      layers: options?.layers,
      featuresPerLayer: options?.featuresPerLayer ?? 10,
      minScore: options?.minScore ?? 0.05,
      limit: limit * 2,
    })

    if (hits.length === 0) {
      this.logger.debug('findSeedsByFeatureIndex: no hits', { query: textQuery.slice(0, 60) })
      return []
    }

    const maxOverlap = hits[0].sharedFeatureCount
    if (maxOverlap <= 0) return []

    this.logger.info('findSeedsByFeatureIndex', {
      query: textQuery.slice(0, 80),
      hits: hits.length,
      maxOverlap,
      topId: hits[0]?.engramId?.slice(0, 12),
    })

    return hits
      .map(h => ({
        engramId: h.engramId,
        charge: h.sharedFeatureCount / maxOverlap,
      }))
      .filter(s => s.charge > 0.1)
      .slice(0, limit)
  }

  /**
   * Step 2: One iteration of spreading excitation (original, linear).
   * Returns the total absolute change in charge (for convergence detection).
   *
   * Optimized: batch-fetches all source and neighbor engrams in 2 queries
   * instead of 2 per synapse (was 4N queries, now 2 + 1 per source).
   */
  private spreadOnce(chargeMap: Map<string, number>, attentionVector?: Float32Array): number {
    const updates = new Map<string, number>()

    // Phase 1: batch-fetch all source engrams (1 query)
    const sourceIds = [...chargeMap.keys()].filter(id => (chargeMap.get(id) ?? 0) >= 0.01)
    if (sourceIds.length === 0) return 0
    const sourceEngrams = this.cortex.getEngrams(sourceIds)

    // Phase 2: collect synapses and unique neighbor IDs
    const allSynapses: Array<{
      sourceId: string; neighborId: string; edgeType: string; weight: number
    }> = []
    const neighborIdSet = new Set<string>()

    for (const sourceId of sourceIds) {
      const synapses = this.cortex.getNeighborSynapses(sourceId)
      for (const syn of synapses) {
        const neighborId = syn.sourceId === sourceId ? syn.targetId : syn.sourceId
        neighborIdSet.add(neighborId)
        allSynapses.push({
          sourceId,
          neighborId,
          edgeType: syn.edgeType,
          weight: syn.weight,
        })
      }
    }

    // Phase 3: batch-fetch all neighbor engrams (1 query)
    const neighborEngrams = this.cortex.getEngrams([...neighborIdSet])

    // Phase 4: compute contributions (no DB calls) — linear spreadOnce
    for (const { sourceId, neighborId, edgeType, weight } of allSynapses) {
      const sourceEngram = sourceEngrams.get(sourceId)
      if (!sourceEngram) continue
      const neighborEngram = neighborEngrams.get(neighborId)
      if (!neighborEngram) continue

      const charge = chargeMap.get(sourceId)!
      const propagation = SYNAPSE_PROPAGATION[edgeType] ?? 0.5
      const signedPropagation = edgeType === 'contradicts'
        ? -Math.abs(propagation)
        : propagation
      let xyDist = sphericalOrEuclideanDistance(
        sourceEngram, neighborEngram,
        sourceEngram.embedding, neighborEngram.embedding,
      )
      if (attentionVector && neighborEngram.embedding) {
        xyDist = warpDistanceForAttention(xyDist, neighborEngram.embedding, attentionVector)
      }
      const distDecay = 1 / (1 + KINDLING_DEFAULTS.distanceDecayRate * xyDist)

      const tDist = Math.abs(sourceEngram.t - neighborEngram.t)
      const temporalRelevance = 1 / (1 + KINDLING_DEFAULTS.temporalDecayRate * tDist)

      const potBoost = this.isBridge(neighborEngram)
        ? 1.0
        : 1 + KINDLING_DEFAULTS.potentiationBoostScale * neighborEngram.potentiation

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

      const spread = charge * weight * signedPropagation * distDecay * temporalRelevance * potBoost * emotionalDamping

      const existing = updates.get(neighborId) ?? 0
      updates.set(neighborId, existing + spread)
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

  // Photon layer constants
  private static readonly PHOTON_EMISSION_THRESHOLD = 0.1
  private static readonly PHOTON_DECAY = 8.0
  private static readonly PHOTON_DAMPENING = 0.1
  private static readonly MAX_PHOTON_NEIGHBORS = 20
  private static readonly LUMINOSITY_SCALE = 2.0

  /**
   * Photon spread: wireless activation via vindex feature overlap.
   * Active engrams (charge >= threshold) emit "photons" that gently
   * pre-activate engrams sharing model features, even without synapses.
   *
   * Replaces the ANN embedding-space search with FeatureIndex findCorrelated().
   * The model's internal gate-KNN activation pattern IS the proximity metric —
   * feature overlap replaces cosine distance.
   */
  private photonSpread(chargeMap: Map<string, number>): number {
    if (!this.featureIndex?.isReady()) return 0

    const emitterIds = [...chargeMap.entries()]
      .filter(([_, charge]) => charge >= KindlingEngine.PHOTON_EMISSION_THRESHOLD)
      .map(([id]) => id)

    if (emitterIds.length === 0) return 0

    const emitterEngrams = this.cortex.getEngrams(emitterIds)
    const contributions = new Map<string, number>()

    for (const emitterId of emitterIds) {
      const emitter = emitterEngrams.get(emitterId)
      if (!emitter) continue

      const distinctiveness = (emitter.metadata?.distinctiveness as number) ?? 0.5
      const luminosity = emitter.potentiation * distinctiveness
        * KindlingEngine.LUMINOSITY_SCALE
      const emitterCharge = chargeMap.get(emitterId)!

      // FeatureIndex cache: emitterId → correlated engrams
      const cachedCorrelated = this.photonCache.get(emitterId)
      const correlated = cachedCorrelated ?? this.featureIndex.findCorrelated(
        emitterId,
        { minOverlap: 1, limit: KindlingEngine.MAX_PHOTON_NEIGHBORS },
      )

      if (!cachedCorrelated && this.photonCache.size < KindlingEngine.PHOTON_CACHE_MAX) {
        this.photonCache.set(emitterId, correlated)
      }

      for (const neighbor of correlated) {
        if (neighbor.engramId === emitterId) continue
        if (chargeMap.has(neighbor.engramId)) continue

        // Feature-space distance: 1 − overlap ratio.
        // sharedCount ≥ 1: overlap = sharedCount/(sharedCount+2) ∈ [0.33, 1.0)
        const overlap = neighbor.sharedFeatureCount / (neighbor.sharedFeatureCount + 2)
        const d = 1 - overlap
        const photonicContribution = emitterCharge * luminosity
          / (1 + KindlingEngine.PHOTON_DECAY * d * d)

        if (!isFinite(photonicContribution)) continue

        const existing = contributions.get(neighbor.engramId) ?? 0
        contributions.set(neighbor.engramId, existing + photonicContribution)
      }
    }

    let totalDelta = 0
    let contributedCount = 0
    for (const [id, contrib] of contributions) {
      const dampened = contrib * KindlingEngine.PHOTON_DAMPENING
      const oldCharge = chargeMap.get(id) ?? 0
      chargeMap.set(id, oldCharge + dampened)
      totalDelta += Math.abs(dampened)
      contributedCount++
    }

    if (contributedCount > 0) {
      this.logger.info('Photon spread (FeatureIndex)', {
        emitters: emitterIds.length,
        contributed: contributedCount,
        totalDelta: totalDelta.toFixed(4),
      })
    }

    return totalDelta
  }

  /**
   * Step 2 (Neural): One iteration of spreading with nonlinear activation and bias.
   *
   * Key differences from linear spreadOnce():
   * 1. Incoming contributions are aggregated per target node, then a bias (from potentiation)
   *    is added, and a nonlinear activation function is applied.
   * 2. Optionally records every contribution to a forward trace for backpropagation.
   *
   * Optimized: batch-fetches all source, neighbor, and target engrams in 3 queries
   * instead of 3 per synapse + 1 per target (was 4N+M queries, now 3 + 1 per source).
   */
  private spreadOnceNeural(
    chargeMap: Map<string, number>,
    iteration: number,
    attentionVector?: Float32Array,
    trace?: ForwardRecord[],
  ): number {
    const aggregated = new Map<string, number>()
    const biasScale = this.neuralConfig.biasScale

    // Phase 1: batch-fetch all source engrams (1 query)
    const sourceIds = [...chargeMap.keys()].filter(id => (chargeMap.get(id) ?? 0) >= 0.01)
    if (sourceIds.length === 0) return 0
    const sourceEngrams = this.cortex.getEngrams(sourceIds)

    // Phase 2: collect synapses, neighbor IDs, and per-synapse computation data
    const allSynapses: Array<{
      sourceId: string; neighborId: string; edgeType: string; weight: number; propagation: number
    }> = []
    const neighborIdSet = new Set<string>()

    for (const sourceId of sourceIds) {
      const sourceEngram = sourceEngrams.get(sourceId)
      if (!sourceEngram) continue

      const synapses = this.cortex.getNeighborSynapses(sourceId)
      for (const syn of synapses) {
        const neighborId = syn.sourceId === sourceId ? syn.targetId : syn.sourceId
        neighborIdSet.add(neighborId)
        const propagation = SYNAPSE_PROPAGATION[syn.edgeType] ?? 0.5
        allSynapses.push({
          sourceId,
          neighborId,
          edgeType: syn.edgeType,
          weight: syn.weight,
          propagation,
        })
      }
    }

    // Phase 3: batch-fetch all neighbor engrams (1 query)
    const neighborEngrams = this.cortex.getEngrams([...neighborIdSet])

    // Phase 4: compute raw contributions (no DB calls)
    for (const { sourceId, neighborId, edgeType, weight, propagation } of allSynapses) {
      const sourceEngram = sourceEngrams.get(sourceId)
      if (!sourceEngram) continue
      const neighborEngram = neighborEngrams.get(neighborId)
      if (!neighborEngram) continue

      const charge = chargeMap.get(sourceId)!
      const signedPropagation = edgeType === 'contradicts'
        ? -Math.abs(propagation)
        : propagation
      let xyDist = sphericalOrEuclideanDistance(
        sourceEngram, neighborEngram,
        sourceEngram.embedding, neighborEngram.embedding,
      )
      if (attentionVector && neighborEngram.embedding) {
        xyDist = warpDistanceForAttention(xyDist, neighborEngram.embedding, attentionVector)
      }
      const distDecay = 1 / (1 + KINDLING_DEFAULTS.distanceDecayRate * xyDist)

      const tDist = Math.abs(sourceEngram.t - neighborEngram.t)
      const temporalRelevance = 1 / (1 + KINDLING_DEFAULTS.temporalDecayRate * tDist)

      const potBoost = this.isBridge(neighborEngram)
        ? 1.0
        : 1 + KINDLING_DEFAULTS.potentiationBoostScale * neighborEngram.potentiation

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

      const rawContribution = charge * weight * signedPropagation * distDecay * temporalRelevance * potBoost * emotionalDamping

      const existing = aggregated.get(neighborId) ?? 0
      aggregated.set(neighborId, existing + rawContribution)

      if (trace) {
        trace.push({
          iteration,
          sourceId,
          targetId: neighborId,
          edgeType,
          synapseWeight: weight,
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

    // Phase 5: apply activation — batch-fetch target engrams for bias (1 query)
    const targetIds = [...aggregated.keys()]
    const targetEngrams = this.cortex.getEngrams(targetIds)

    // Build per-target trace index for O(1) lookup instead of O(n²) filter
    let traceByTarget: Map<string, ForwardRecord[]> | undefined
    if (trace) {
      traceByTarget = new Map()
      for (const rec of trace) {
        if (rec.iteration === iteration && rec.activatedOutput === 0) {
          let arr = traceByTarget.get(rec.targetId)
          if (!arr) { arr = []; traceByTarget.set(rec.targetId, arr) }
          arr.push(rec)
        }
      }
    }

    let totalDelta = 0
    for (const [id, rawInput] of aggregated) {
      const engram = targetEngrams.get(id)
      const bias = this.isBridge(engram) ? 0 : (engram?.potentiation ?? 0) * biasScale
      const dampened = rawInput * KINDLING_DEFAULTS.spreadDampening
      const oldCharge = chargeMap.get(id) ?? 0
      const preActivation = oldCharge + dampened + bias
      const activated = this.activate(preActivation)

      chargeMap.set(id, activated)
      totalDelta += Math.abs(activated - oldCharge)

      if (traceByTarget) {
        const records = traceByTarget.get(id)
        if (records) {
          for (const record of records) {
            record.preActivation = preActivation
            record.activatedOutput = activated
          }
        }
      }
    }

    return totalDelta
  }

  /**
   * Apply the configured nonlinear activation function.
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
   * Step 3: Ignite — collect engrams above their effective spark point.
   */
  private ignite(
    chargeMap: Map<string, number>,
    globalSparkPoint: number,
    maxSize: number,
  ): ChargedEngram[] {
    const candidates: ChargedEngram[] = []

    // Batch-fetch all engrams (1 query instead of N)
    const engramIds = [...chargeMap.keys()]
    const engramMap = this.cortex.getEngrams(engramIds)

    for (const [engramId, charge] of chargeMap) {
      const engram = engramMap.get(engramId)
      if (!engram) continue

      let effectiveSparkPoint = globalSparkPoint -
        engram.potentiation * SPARK_POINT_DEFAULTS.potentiationScale

      // Radial bias: engrams near the attractor ignite at lower charge
      if (this.attractor) {
        const r = (engram.metadata as any)?.r as number | undefined
        const theta = (engram.metadata as any)?.theta as number | undefined
        if (r !== undefined && theta !== undefined) {
          const boost = this.attractor.radialBoost(r, theta)
          effectiveSparkPoint *= (1.0 - 0.5 * boost)
        }
      }

      // Broadcast modulation: primed nuclei lower the spark point further
      if (this.broadcastModProvider) {
        effectiveSparkPoint *= this.broadcastModProvider(engram.clusterId)
      }

      if (charge >= Math.max(0.01, effectiveSparkPoint)) {
        candidates.push({ engram, charge })
      }
    }

    return candidates
      .sort((a, b) => b.charge - a.charge)
      .slice(0, maxSize)
  }

  /**
   * Post-task update — record spikes, optionally drift positions.
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

    // Update phasic attractor from luminal set positions
    if (this.attractor) {
      const chargedPositions = luminalSet.engrams
        .map(({ engram, charge }) => ({
          r: (engram.metadata as any)?.r as number | undefined,
          theta: (engram.metadata as any)?.theta as number | undefined,
          charge,
        }))
        .filter(e => e.r !== undefined && e.theta !== undefined) as Array<{ r: number; theta: number; charge: number }>
      this.attractor.updateFromLuminal(chargedPositions)
    }

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
    let sparkPoint = SPARK_POINT_DEFAULTS.baseThreshold * modifier

    // Harmony modulation (Phase 1: Yin/Yang homeostatic balance)
    // When harmony < 0.3 (Yang-dominated): raise spark point, fewer engrams ignite.
    // When harmony > 0.7 (Yin-dominated): lower spark point, more engrams ignite.
    // Target zone 0.3–0.7: no correction. Damping factor 0.3 prevents oscillation.
    if (this.harmonyProvider) {
      const harmony = this.harmonyProvider()
      if (harmony < 0.3) {
        sparkPoint *= 1.0 + (0.3 - harmony) * 0.3  // max 1.09x at harmony=0
      } else if (harmony > 0.7) {
        sparkPoint *= 1.0 - (harmony - 0.7) * 0.3  // min 0.91x at harmony=1
      }
    }

    return sparkPoint
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

/**
 * Distance on the spherical manifold of gate embeddings, falling back
 * to Euclidean XY when embeddings are unavailable.
 *
 * Gate embeddings are L2-normalized 1536-dim vectors on S¹⁵³⁵.
 * Geodesic distance is arccos(dot(a,b)) — the intrinsic metric.
 * This is the model's own representation space metric, replacing
 * the distorted UMAP-projected Cartesian distance.
 *
 * Falls back to Euclidean XY for engrams without gate embeddings
 * (~35% of the field: structural types like bridge, file, etc.).
 */
function sphericalOrEuclideanDistance(
  a: Engram, b: Engram,
  embA?: Float32Array | null, embB?: Float32Array | null,
): number {
  if (embA && embB && embA.length === embB.length && embA.length > 0) {
    const dot = dotProductFloat32(embA, embB)
    return Math.acos(dot)  // geodesic distance in [0, π]
  }
  return Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)
}

// Kept for backward compat — unused, superseded by sphericalOrEuclideanDistance
function euclideanDistance(a: Engram, b: Engram): number {
  return Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)
}

/** Fast dot product for two Float32Array gate embeddings, clamped to [-1, 1]. */
function dotProductFloat32(a: Float32Array, b: Float32Array): number {
  const n = Math.min(a.length, b.length)
  let dot = 0
  for (let i = 0; i < n; i++) dot += a[i] * b[i]
  return Math.max(-1, Math.min(1, dot))
}

/**
 * Warp a geodesic distance by attention proximity.
 * Engrams close to the attention vector get reduced effective distance.
 * Additive only — never increases distance (warp can only amplify signal).
 *
 * @param xyDist - Original geodesic distance from sphericalOrEuclideanDistance
 * @param neighborEmb - Neighbor engram's gate embedding (must be non-null)
 * @param attentionVec - Current attention vector on S¹⁵³⁵
 * @returns Warped distance (≤ xyDist)
 */
function warpDistanceForAttention(xyDist: number, neighborEmb: Float32Array, attentionVec: Float32Array): number {
  const attnDot = dotProductFloat32(neighborEmb, attentionVec)
  const warped = xyDist / (1 + attnDot)  // attnDot ∈ [-1,1] → divisor ∈ [0,2]
  return warped < xyDist ? warped : xyDist
}
