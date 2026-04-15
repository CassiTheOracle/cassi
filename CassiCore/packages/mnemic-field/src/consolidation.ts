import type { ILogger } from '../../../types/interfaces.js'
import { computeSpikeImportance, computeAlpha } from './cortex.js'
import type { Cortex } from './cortex.js'
import type { FilamentConsolidator } from './filament-consolidation.js'
import type { GradientEngine } from './backpropagation.js'
import type { Engram, MnemicSynapse, Nucleus, BackpropResult } from './types.js'
import {
  POTENTIATION_DEFAULTS, SYNAPSE_PROPAGATION, KINDLING_DEFAULTS, AFFECT_DEFAULTS,
} from './types.js'
import { emotionalIntensity, resolveLabel } from './affect.js'
import type { Affect } from './types.js'
import type { DreamEngine, DreamResult } from '../memory-bridge/dream-engine.js'

export interface ConsolidationResult {
  potentiationUpdates: number
  positionDrifts: number
  nucleiDetected: number
  abstractionsCreated: number
  spikesPruned: number
  filamentSynapsesCreated: number
  filamentSynapsesDecayed: number
  gradientResult?: BackpropResult
  dreamResult?: DreamResult
  durationMs: number
}

export interface ConsolidationOptions {
  skipRadiance?: boolean
  skipDrift?: boolean
  skipNuclei?: boolean
  skipAbstractions?: boolean
  skipPruning?: boolean
  skipFilamentConsolidation?: boolean
  skipGradients?: boolean
  skipDreaming?: boolean
  pruneKeepCount?: number
  nucleiMinClusterSize?: number
  nucleiEpsilon?: number
  abstractionMinMembers?: number
  abstractionMinPotentiation?: number
}

/** Yield control back to the event loop so heartbeats and IPC stay responsive. */
function yieldToEventLoop(): Promise<void> {
  return new Promise(resolve => setImmediate(resolve))
}

/**
 * The Consolidation Engine: periodic recomputation of potentiation,
 * XY drift from co-activation, nucleus detection, and spike pruning.
 */
export class ConsolidationEngine {
  private logger: ILogger

  constructor(
    private cortex: Cortex,
    logger: ILogger,
    private filamentConsolidator: FilamentConsolidator | null = null,
    private gradientEngine: GradientEngine | null = null,
    private dreamEngine: DreamEngine | null = null,
  ) {
    this.logger = logger.child ? logger.child('consolidation') : logger
  }

  /**
   * Run a full consolidation cycle.
   *
   * Yields to the event loop between phases and within heavy loops so
   * the daemon can process heartbeats, IPC, and HTTP requests. Without
   * yielding, consolidation over 125K+ engrams blocks the event loop
   * for 50–100 seconds and triggers supervisor restarts.
   */
  async consolidate(options: ConsolidationOptions = {}): Promise<ConsolidationResult> {
    const start = Date.now()
    let potentiationUpdates = 0
    let positionDrifts = 0
    let nucleiDetected = 0
    let abstractionsCreated = 0
    let spikesPruned = 0
    let filamentSynapsesCreated = 0
    let filamentSynapsesDecayed = 0
    let gradientResult: BackpropResult | undefined
    let dreamResult: DreamResult | undefined

    // Load the full dataset once — computeRadiance, applyCoActivationDrift,
    // and pruneSpikeHistories all need engrams (125K+ rows). Loading once
    // instead of three times cuts ~2/3 of the SQLite I/O per consolidation.
    const needsFullDataset = !options.skipRadiance || !options.skipDrift || !options.skipPruning
    const dataset = needsFullDataset ? this.cortex.getAllEngramsWithSynapses() : undefined
    if (needsFullDataset) await yieldToEventLoop()

    if (!options.skipRadiance) {
      potentiationUpdates = await this.computeRadiance(dataset)
      await yieldToEventLoop()
    }

    if (!options.skipDrift) {
      positionDrifts = await this.applyCoActivationDrift(dataset)
      await yieldToEventLoop()
    }

    // Dreaming: discover hidden connections via vindex feature overlap
    if (!options.skipDreaming && this.dreamEngine) {
      dreamResult = await this.dreamEngine.dream()
      await yieldToEventLoop()
    }

    if (!options.skipNuclei) {
      nucleiDetected = this.detectNuclei(
        options.nucleiMinClusterSize ?? 3,
        options.nucleiEpsilon ?? 0.015,
      )
      await yieldToEventLoop()
    }

    if (!options.skipAbstractions) {
      abstractionsCreated = this.generateAbstractions(
        options.abstractionMinMembers ?? 5,
        options.abstractionMinPotentiation ?? 0.3,
      )
      await yieldToEventLoop()
    }

    if (!options.skipPruning) {
      spikesPruned = await this.pruneSpikeHistories(options.pruneKeepCount ?? 100, dataset?.engrams)
      await yieldToEventLoop()
    }

    if (!options.skipFilamentConsolidation && this.filamentConsolidator) {
      const decay = this.filamentConsolidator.decayCoActivation()
      filamentSynapsesDecayed = decay.deleted
      await yieldToEventLoop()
      const tier2 = this.filamentConsolidator.runTier2()
      filamentSynapsesCreated = tier2.synapsesCreated
      await yieldToEventLoop()
    }

    if (!options.skipGradients && this.gradientEngine) {
      gradientResult = await this.gradientEngine.processGradients()
      await yieldToEventLoop()
    }

    const durationMs = Date.now() - start
    this.logger.info('Consolidation complete', {
      potentiationUpdates,
      positionDrifts,
      nucleiDetected,
      abstractionsCreated,
      spikesPruned,
      filamentSynapsesCreated,
      filamentSynapsesDecayed,
      dreamResult: dreamResult ? {
        seeds: dreamResult.seedCount,
        fingerprints: dreamResult.fingerprintsComputed,
        discoveries: dreamResult.discoveries.length,
        synapsesCreated: dreamResult.synapsesCreated,
        durationMs: dreamResult.durationMs,
      } : undefined,
      gradientResult: gradientResult ? {
        synapsesUpdated: gradientResult.synapsesUpdated,
        requestsProcessed: gradientResult.requestsProcessed,
      } : undefined,
      durationMs,
    })

    return { potentiationUpdates, positionDrifts, nucleiDetected, abstractionsCreated, spikesPruned, filamentSynapsesCreated, filamentSynapsesDecayed, gradientResult, dreamResult, durationMs }
  }

  /**
   * Radiance: Recompute potentiation for all engrams using
   * PageRank-style iterative propagation with spike history as teleportation.
   *
   * potentiation_i = α_i × spike_importance_i + (1 - α_i) × Σⱼ(w_ij × propagation(type_ij) × potentiation_j) / norm
   *
   * Where α_i is adaptive per-engram based on spike count.
   */
  async computeRadiance(
    preloaded?: { engrams: Engram[]; synapses: MnemicSynapse[] },
  ): Promise<number> {
    const { engrams, synapses } = preloaded ?? this.cortex.getAllEngramsWithSynapses()
    if (engrams.length === 0) return 0

    await yieldToEventLoop()

    const idToIdx = new Map<string, number>()
    engrams.forEach((e, i) => idToIdx.set(e.id, i))

    const spikeImportances = engrams.map(e => computeSpikeImportance(this.cortex.getSpikes(e.id, 200), POTENTIATION_DEFAULTS.decayRate))
    const alphas = engrams.map(e => computeAlpha(this.cortex.getSpikeCount(e.id), POTENTIATION_DEFAULTS))

    await yieldToEventLoop()

    const baselineTeleportation = 1.0 / engrams.length
    const teleportations = spikeImportances.map(si =>
      si > 0 ? si : baselineTeleportation
    )

    const adjacency = this.buildAdjacency(engrams, synapses, idToIdx)

    await yieldToEventLoop()

    let potentiations = engrams.map(() => 0.0)
    const { pageRankIterations: maxIter, convergenceThreshold: tol } = POTENTIATION_DEFAULTS

    for (let iter = 0; iter < maxIter; iter++) {
      const next = new Array<number>(engrams.length).fill(0)

      for (let i = 0; i < engrams.length; i++) {
        let graphComponent = 0
        let totalWeight = 0

        for (const { neighborIdx, weight } of adjacency[i]) {
          graphComponent += weight * potentiations[neighborIdx]
          totalWeight += weight
        }

        if (totalWeight > 0) {
          graphComponent /= totalWeight
        }

        const alpha = alphas[i]
        next[i] = alpha * teleportations[i] + (1 - alpha) * graphComponent
      }

      let maxDelta = 0
      for (let i = 0; i < engrams.length; i++) {
        maxDelta = Math.max(maxDelta, Math.abs(next[i] - potentiations[i]))
      }
      potentiations = next

      // Yield every iteration so the event loop stays responsive
      await yieldToEventLoop()

      if (maxDelta < tol) {
        this.logger.debug('Radiance converged', { iterations: iter + 1, maxDelta })
        break
      }
    }

    const maxPot = potentiations.reduce((m, p) => p > m ? p : m, 0.001)
    const normalized = potentiations.map((p, i) => {
      let norm = p / maxPot
      const affect = engrams[i].metadata?.affect as Affect | undefined
      if (affect) {
        const intensity = emotionalIntensity(affect)
        norm *= 1 + AFFECT_DEFAULTS.warmthScale * intensity
      }
      return norm
    })

    const updates = engrams
      .map((e, i) => ({ id: e.id, potentiation: normalized[i] }))
      .filter((u, i) => Math.abs(u.potentiation - engrams[i].potentiation) > 0.001)

    if (updates.length > 0) {
      await this.cortex.bulkUpdatePotentiationBatched(updates)
    }

    return updates.length
  }

  /**
   * Build adjacency list from synapses, with weights incorporating
   * synapse weight × edge type propagation factor.
   */
  private buildAdjacency(
    engrams: Engram[],
    synapses: MnemicSynapse[],
    idToIdx: Map<string, number>,
  ): Array<Array<{ neighborIdx: number; weight: number }>> {
    const adj: Array<Array<{ neighborIdx: number; weight: number }>> =
      engrams.map(() => [])

    for (const syn of synapses) {
      const srcIdx = idToIdx.get(syn.sourceId)
      const tgtIdx = idToIdx.get(syn.targetId)
      if (srcIdx === undefined || tgtIdx === undefined) continue

      const propagation = SYNAPSE_PROPAGATION[syn.edgeType] ?? 0.5
      const weight = syn.weight * propagation

      adj[srcIdx].push({ neighborIdx: tgtIdx, weight })
      adj[tgtIdx].push({ neighborIdx: srcIdx, weight })
    }

    return adj
  }

  /**
   * Apply XY drift from recent co-activation patterns.
   * Loads recent spikes to find pairs that were co-activated in the same task,
   * then pulls their positions closer.
   */
  async applyCoActivationDrift(
    preloaded?: { engrams: Engram[]; synapses: MnemicSynapse[] },
  ): Promise<number> {
    const { engrams, synapses } = preloaded ?? this.cortex.getAllEngramsWithSynapses()
    if (engrams.length < 2) return 0

    await yieldToEventLoop()

    const coActivationCounts = this.findCoActivationPairs(engrams)
    if (coActivationCounts.size === 0) return 0

    const engramMap = new Map(engrams.map(e => [e.id, e]))
    const pullVectors = new Map<string, { dx: number; dy: number; totalWeight: number }>()

    for (const [pairKey, count] of coActivationCounts) {
      const [idA, idB] = pairKey.split('|')
      const a = engramMap.get(idA)
      const b = engramMap.get(idB)
      if (!a || !b) continue

      const rate = KINDLING_DEFAULTS.driftLearningRate * Math.min(count * 0.1, 0.5)

      const pullA = pullVectors.get(idA) ?? { dx: 0, dy: 0, totalWeight: 0 }
      pullA.dx += rate * (b.x - a.x)
      pullA.dy += rate * (b.y - a.y)
      pullA.totalWeight += rate
      pullVectors.set(idA, pullA)

      const pullB = pullVectors.get(idB) ?? { dx: 0, dy: 0, totalWeight: 0 }
      pullB.dx += rate * (a.x - b.x)
      pullB.dy += rate * (a.y - b.y)
      pullB.totalWeight += rate
      pullVectors.set(idB, pullB)
    }

    const updates: Array<{ id: string; x: number; y: number }> = []
    for (const [id, pull] of pullVectors) {
      const e = engramMap.get(id)
      if (!e || pull.totalWeight === 0) continue

      const newX = e.x + pull.dx
      const newY = e.y + pull.dy
      if (Math.abs(newX - e.x) > 0.0001 || Math.abs(newY - e.y) > 0.0001) {
        updates.push({ id, x: newX, y: newY })
      }
    }

    if (updates.length > 0) {
      await this.cortex.bulkUpdatePositionsBatched(updates)
    }

    return updates.length
  }

  /**
   * Find pairs of engrams that were co-activated in the same task context recently.
   */
  private findCoActivationPairs(engrams: Engram[]): Map<string, number> {
    const taskEngrams = new Map<string, string[]>()

    for (const engram of engrams) {
      const spikes = this.cortex.getSpikes(engram.id, 20)
      for (const spike of spikes) {
        if (!spike.taskContext) continue
        const existing = taskEngrams.get(spike.taskContext) ?? []
        existing.push(engram.id)
        taskEngrams.set(spike.taskContext, existing)
      }
    }

    const pairCounts = new Map<string, number>()
    for (const [, ids] of taskEngrams) {
      if (ids.length < 2) continue
      const unique = [...new Set(ids)]
      for (let i = 0; i < unique.length && i < 10; i++) {
        for (let j = i + 1; j < unique.length && j < 10; j++) {
          const key = unique[i] < unique[j] ? `${unique[i]}|${unique[j]}` : `${unique[j]}|${unique[i]}`
          pairCounts.set(key, (pairCounts.get(key) ?? 0) + 1)
        }
      }
    }

    return pairCounts
  }

  /**
   * DBSCAN-lite: density-based clustering on XY coordinates.
   * Simpler than full HDBSCAN but effective for detecting spatial clusters.
   * Only considers engrams with non-zero XY (those that have embeddings).
   * Returns the number of nuclei detected.
   */
  detectNuclei(minClusterSize = 3, epsilon = 0.015): number {
    const { engramCount } = this.cortex.stats()
    const engrams = engramCount <= 10000
      ? this.cortex.getAllEngrams()
      : this.cortex.getSpatialEngrams(10000)
    if (engrams.length < minClusterSize) return 0

    const clusters = this.dbscan(engrams, epsilon, minClusterSize)

    for (const existing of this.cortex.listNuclei()) {
      this.cortex.deleteNucleus(existing.id)
    }

    let nucleiCount = 0
    for (const [clusterId, members] of clusters) {
      const centroidX = members.reduce((s, e) => s + e.x, 0) / members.length
      const centroidY = members.reduce((s, e) => s + e.y, 0) / members.length
      const avgPot = members.reduce((s, e) => s + e.potentiation, 0) / members.length

      const dominantType = this.findDominantType(members)
      const dominantEmotion = this.computeClusterAffect(members)
      const emotionPrefix = dominantEmotion ? `${dominantEmotion}-` : ''
      const label = `${emotionPrefix}${dominantType}-cluster-${nucleiCount}`

      const nucleus = this.cortex.createNucleus({
        label,
        centroidX,
        centroidY,
      })

      this.cortex.updateNucleus(nucleus.id, {
        memberCount: members.length,
        avgPotentiation: avgPot,
      })

      for (const member of members) {
        this.cortex.updateEngram(member.id, { clusterId: nucleus.id })
      }

      nucleiCount++
    }

    this.logger.debug('Nucleus detection complete', { nucleiCount, totalEngrams: engrams.length })
    return nucleiCount
  }

  /**
   * DBSCAN clustering algorithm using index-based queue for O(n²) performance.
   * Returns clusters as Map<clusterIndex, Engram[]>.
   */
  private dbscan(engrams: Engram[], epsilon: number, minPts: number): Map<number, Engram[]> {
    const n = engrams.length
    const labels = new Array<number>(n).fill(-1)
    let clusterId = 0
    const epsSq = epsilon * epsilon

    const regionQuery = (idx: number): number[] => {
      const neighbors: number[] = []
      const ex = engrams[idx].x
      const ey = engrams[idx].y
      for (let j = 0; j < n; j++) {
        if (j === idx) continue
        const dx = ex - engrams[j].x
        const dy = ey - engrams[j].y
        if (dx * dx + dy * dy <= epsSq) neighbors.push(j)
      }
      return neighbors
    }

    for (let i = 0; i < n; i++) {
      if (labels[i] !== -1) continue

      const neighbors = regionQuery(i)
      if (neighbors.length < minPts - 1) {
        labels[i] = -2
        continue
      }

      labels[i] = clusterId
      const queue = neighbors.slice()
      let front = 0

      while (front < queue.length) {
        const j = queue[front++]
        if (labels[j] === clusterId) continue

        if (labels[j] === -2) labels[j] = clusterId
        if (labels[j] !== -1 && labels[j] !== clusterId) continue
        labels[j] = clusterId

        const jNeighbors = regionQuery(j)
        if (jNeighbors.length >= minPts - 1) {
          for (const k of jNeighbors) {
            if (labels[k] === -1 || labels[k] === -2) queue.push(k)
          }
        }
      }

      clusterId++
    }

    const clusters = new Map<number, Engram[]>()
    for (let i = 0; i < n; i++) {
      if (labels[i] < 0) continue
      const existing = clusters.get(labels[i]) ?? []
      existing.push(engrams[i])
      clusters.set(labels[i], existing)
    }

    return clusters
  }

  private findDominantType(engrams: Engram[]): string {
    const counts = new Map<string, number>()
    for (const e of engrams) {
      counts.set(e.nodeType, (counts.get(e.nodeType) ?? 0) + 1)
    }
    let best = 'mixed'
    let bestCount = 0
    for (const [type, count] of counts) {
      if (count > bestCount) { best = type; bestCount = count }
    }
    return best
  }

  private computeClusterAffect(engrams: Engram[]): string | null {
    let totalV = 0
    let totalA = 0
    let count = 0
    for (const e of engrams) {
      const affect = e.metadata?.affect as Affect | undefined
      if (!affect) continue
      totalV += affect.valence
      totalA += affect.arousal
      count++
    }
    if (count < 2) return null
    const avg: Affect = { valence: totalV / count, arousal: totalA / count }
    if (emotionalIntensity(avg) < 0.15) return null
    return resolveLabel(avg)
  }

  /**
   * Generate abstraction engrams for qualifying nuclei.
   * Tier 1 (structural extraction): extract common tags, types, entities, temporal range.
   * Creates a summary engram at the nucleus centroid connected to all members.
   */
  generateAbstractions(minMembers = 5, minAvgPotentiation = 0.3): number {
    const nuclei = this.cortex.listNuclei()
    let created = 0

    for (const nucleus of nuclei) {
      if (nucleus.memberCount < minMembers) continue
      if (nucleus.avgPotentiation < minAvgPotentiation) continue
      if (nucleus.abstractionId) continue

      const existingAbstraction = this.findExistingAbstraction(nucleus)
      if (existingAbstraction) {
        this.cortex.updateNucleus(nucleus.id, { abstractionId: existingAbstraction.id })
        continue
      }

      const members = this.cortex.getEngramsByCluster(nucleus.id)

      if (members.length < minMembers) continue

      const abstraction = this.buildAbstractionContent(members, nucleus)

      const engram = this.cortex.createEngram({
        content: abstraction.content,
        nodeType: 'abstraction',
        x: nucleus.centroidX,
        y: nucleus.centroidY,
        tags: abstraction.tags,
        provenance: `nucleus:${nucleus.id}`,
        metadata: {
          nucleusId: nucleus.id,
          memberCount: members.length,
          temporalRange: abstraction.temporalRange,
          typeBreakdown: abstraction.typeBreakdown,
        },
      })

      for (const member of members) {
        this.cortex.createSynapse({
          sourceId: engram.id,
          targetId: member.id,
          edgeType: 'part_of',
          weight: 0.7,
        })
      }

      this.cortex.updateNucleus(nucleus.id, { abstractionId: engram.id })
      created++
    }

    if (created > 0) {
      this.logger.debug('Abstractions generated', { created })
    }

    return created
  }

  /**
   * Check if an abstraction engram already exists near a nucleus centroid.
   */
  private findExistingAbstraction(nucleus: Nucleus): Engram | null {
    const nearby = this.cortex.spatialQuery({
      xMin: nucleus.centroidX - 1.0,
      xMax: nucleus.centroidX + 1.0,
      yMin: nucleus.centroidY - 1.0,
      yMax: nucleus.centroidY + 1.0,
    })
    return nearby.find(e => e.nodeType === 'abstraction') ?? null
  }

  /**
   * Build Tier 1 abstraction content from cluster members.
   */
  private buildAbstractionContent(members: Engram[], nucleus: Nucleus): {
    content: string
    tags: string[]
    temporalRange: { earliest: string; latest: string }
    typeBreakdown: Record<string, number>
  } {
    const allTags = new Map<string, number>()
    for (const m of members) {
      for (const tag of m.tags) {
        allTags.set(tag, (allTags.get(tag) ?? 0) + 1)
      }
    }
    const commonTags = [...allTags.entries()]
      .filter(([, count]) => count >= Math.ceil(members.length * 0.3))
      .sort((a, b) => b[1] - a[1])
      .map(([tag]) => tag)

    const typeBreakdown: Record<string, number> = {}
    for (const m of members) {
      typeBreakdown[m.nodeType] = (typeBreakdown[m.nodeType] ?? 0) + 1
    }

    const timestamps = members
      .map(m => m.createdAt)
      .filter(Boolean)
      .sort()
    const temporalRange = {
      earliest: timestamps[0] ?? '',
      latest: timestamps[timestamps.length - 1] ?? '',
    }

    const dominantType = Object.entries(typeBreakdown)
      .sort(([, a], [, b]) => b - a)[0]?.[0] ?? 'mixed'

    const tagSummary = commonTags.length > 0 ? ` [${commonTags.slice(0, 5).join(', ')}]` : ''
    const content = `Cluster "${nucleus.label}": ${members.length} ${dominantType} engrams${tagSummary}. ` +
      `Types: ${Object.entries(typeBreakdown).map(([t, c]) => `${t}(${c})`).join(', ')}. ` +
      `Avg potentiation: ${nucleus.avgPotentiation.toFixed(3)}.`

    return { content, tags: commonTags, temporalRange, typeBreakdown }
  }

  /**
   * Prune old, low-magnitude spikes to bound storage.
   */
  async pruneSpikeHistories(keepCount = 100, preloadedEngrams?: Engram[]): Promise<number> {
    const engrams = preloadedEngrams ?? this.cortex.getAllEngramsWithSynapses().engrams
    let totalPruned = 0

    for (let i = 0; i < engrams.length; i++) {
      const engram = engrams[i]
      const count = this.cortex.getSpikeCount(engram.id)
      if (count > keepCount) {
        totalPruned += this.cortex.pruneSpikes(engram.id, keepCount)
      }
      // Yield every 5000 engrams to keep the event loop responsive
      if (i > 0 && i % 5000 === 0) await yieldToEventLoop()
    }

    if (totalPruned > 0) {
      this.logger.debug('Spike histories pruned', { totalPruned })
    }

    return totalPruned
  }
}
