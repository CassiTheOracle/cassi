import type { ILogger } from '../../../types/interfaces.js'
import { computeSpikeImportance, computeAlpha } from './cortex.js'
import type { Cortex } from './cortex.js'
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
  centripetalDrifts: number
  angularDrifts: number
  nucleiDetected: number
  abstractionsCreated: number
  spikesPruned: number
  forwardTracesPruned: number
  contrastiveFeedbackDrifts: number
  gradientResult?: BackpropResult
  dreamResult?: DreamResult
  durationMs: number
  /** Phase 2 contrastive extraction results (set by MnemicField.consolidate, not the engine). */
  distinctivenessEngramsScored?: number
  distinctivenessGroupsProcessed?: number
  distinctivenessDurationMs?: number
}

export interface ConsolidationOptions {
  skipRadiance?: boolean
  skipDrift?: boolean
  skipCentripetalDrift?: boolean
  skipAngularDrift?: boolean
  skipNuclei?: boolean
  skipAbstractions?: boolean
  skipPruning?: boolean
  skipForwardTracePrune?: boolean
  skipGradients?: boolean
  skipDreaming?: boolean
  skipContrastiveFeedback?: boolean
  /** Phase 2: contrastive extraction — cancels shared sentences to surface what's unique. */
  skipDistinctiveness?: boolean
  /** Skip nearest-neighbor orphan assignment after DBSCAN clustering. */
  skipOrphanAssignment?: boolean
  pruneKeepCount?: number
  /** Matches NeuralKindlingConfig.maxTraceAge default (1 hour). Traces older than this are garbage — their gradient feedback will never arrive. */
  forwardTracePruneAgeMs?: number
  nucleiMinClusterSize?: number
  nucleiEpsilon?: number
  abstractionMinMembers?: number
  abstractionMinPotentiation?: number
}

const DEFAULT_FORWARD_TRACE_MAX_AGE_MS = 3_600_000

/**
 * Lerp between two angles (in radians), handling wrap-around at 2π.
 * Both input and output are normalized to [0, 2π).
 * Exported so Phase 7 (radial/polar topology) can reuse it.
 */
export function lerpAngle(a: number, b: number, t: number): number {
  let diff = b - a
  while (diff > Math.PI) diff -= 2 * Math.PI
  while (diff < -Math.PI) diff += 2 * Math.PI
  let result = a + t * diff
  if (result < 0) result += 2 * Math.PI
  if (result >= 2 * Math.PI) result -= 2 * Math.PI
  return result
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

  /**
   * Type-specific potentiation multipliers for semantic classification labels.
   * Decisions and insights retain near-full strength; concerns and anomalies
   * decay faster so retrieval naturally favors durable facts.
   */
  private static TYPE_POTENTIATION: Record<string, number> = {
    decision: 1.0,      // full retention — decisions define the project
    insight: 0.85,       // high retention — understanding persists
    resolution: 0.8,     // high — resolved questions are valuable context
    revelation: 0.8,     // high — revelations shift the mental model
    confirmation: 0.75,  // moderate-high — validates working hypotheses
    reversal: 0.85,      // high — corrections are crucial for accuracy
    concern: 0.5,        // moderate — risks fade if not revisited
    anomaly: 0.35,       // low — one-off surprises don't need long life
    // tool-result types (matched via nodeType when semanticType absent)
    error_report: 0.35,    // one-off, fast decay (same tier as anomaly)
    search_finding: 0.3,   // search result caches — transient but reusable
    code_change: 0.65,     // structural, moderate retention
    test_result: 0.6,      // diagnostic, useful for patterns
    build_output: 0.45,    // voluminous, lower retention
    // Structural/administrative types — high volume, low recall value
    tool: 0.05,            // raw tool input JSON — never useful for recall
    tool_invocation: 0.05, // tool call records — administrative scaffolding
    file: 0.05,            // file tracking metadata — structural
    file_read: 0.05,       // read events — high volume, low signal
    file_version: 0.05,    // file version diffs — technical artifact
    message: 0.05,         // raw conversation fragments — ephemeral
    bridge: 0.05,          // structural connector — already capped at 0.3 by override below
    session: 0.05,         // session boundary markers
    changeset: 0.05,       // code change tracking — structural
    thought_command: 0.05, // internal cognitive signals — ephemeral
    replay_segment: 0.05,  // internal processing artifacts
    expert_summary: 0.4,   // expert summaries — keep some signal
  }

  constructor(
    private cortex: Cortex,
    logger: ILogger,
    private gradientEngine: GradientEngine | null = null,
    private dreamEngine: DreamEngine | null = null,
  ) {
    this.logger = logger.child ? logger.child('consolidation') : logger
  }

  /** Optional: provides the current harmony metric for drift modulation. */
  private harmonyProvider: (() => number) | null = null

  setHarmonyProvider(provider: (() => number) | null): void {
    this.harmonyProvider = provider
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
    let centripetalDrifts = 0
    let angularDrifts = 0
    let contrastiveFeedbackDrifts = 0
    let nucleiDetected = 0
    let abstractionsCreated = 0
    let spikesPruned = 0
    let gradientResult: BackpropResult | undefined
    let dreamResult: DreamResult | undefined
    let forwardTracesPruned = 0
    let durationMs = 0

    try {
      // Load the full dataset once — computeRadiance, applyCoActivationDrift,
      // applyCentripetalDrift, applyAngularDrift, applyContrastiveFeedback,
      // and pruneSpikeHistories all need engrams (125K+ rows). Loading once
      // instead of six times cuts ~5/6 of the SQLite I/O per consolidation.
      const needsFullDataset = !options.skipRadiance || !options.skipDrift
        || !options.skipCentripetalDrift || !options.skipAngularDrift
        || !options.skipContrastiveFeedback || !options.skipPruning
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

      if (!options.skipCentripetalDrift) {
        centripetalDrifts = await this.applyCentripetalDrift(dataset)
        await yieldToEventLoop()
      }

      if (!options.skipAngularDrift) {
        angularDrifts = await this.applyAngularDrift(dataset)
        await yieldToEventLoop()
      }

      // Contrastive retrieval feedback: self-supervised position learning
      // from spike outcomes. Engrams that produce useful offspring drift
      // inward; engrams retrieved but never used drift outward.
      if (!options.skipContrastiveFeedback) {
        contrastiveFeedbackDrifts = await this.applyContrastiveFeedback(dataset)
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

      if (!options.skipGradients && this.gradientEngine) {
        gradientResult = await this.gradientEngine.processGradients()
        await yieldToEventLoop()
      }

      if (!options.skipForwardTracePrune) {
        const maxAgeMs = options.forwardTracePruneAgeMs ?? DEFAULT_FORWARD_TRACE_MAX_AGE_MS
        forwardTracesPruned = this.cortex.pruneOldTraces(maxAgeMs)
        await yieldToEventLoop()
      }

      durationMs = Date.now() - start
      this.logger.info('Consolidation complete', {
        potentiationUpdates,
        positionDrifts,
        nucleiDetected,
        abstractionsCreated,
        spikesPruned,
        forwardTracesPruned,
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

      return buildResult()
    } catch (err) {
      durationMs = Date.now() - start
      this.logger.error('Consolidation cycle failed', {
        error: String(err),
        phaseStatus: {
          radiance:     options.skipRadiance     ? 'skipped' : potentiationUpdates > 0 ? 'updated' : 'ran',
          drift:        options.skipDrift        ? 'skipped' : positionDrifts     > 0 ? 'updated' : 'ran',
          nuclei:       options.skipNuclei       ? 'skipped' : nucleiDetected     > 0 ? 'updated' : 'ran',
          abstractions: options.skipAbstractions ? 'skipped' : abstractionsCreated > 0 ? 'updated' : 'ran',
          pruning:      options.skipPruning      ? 'skipped' : spikesPruned       > 0 ? 'updated' : 'ran',
        },
        durationMs,
      })
      return buildResult()
    }

    function buildResult(): ConsolidationResult {
      return { potentiationUpdates, positionDrifts, centripetalDrifts, angularDrifts, contrastiveFeedbackDrifts, nucleiDetected, abstractionsCreated, spikesPruned, forwardTracesPruned, gradientResult, dreamResult, durationMs }
    }
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

    // Batch-fetch spikes and spike counts for all engrams in single queries
    const engramIds = engrams.map(e => e.id)
    const allSpikes = this.cortex.getAllSpikesForEngrams(engramIds, 200)
    const allSpikeCounts = this.cortex.getAllSpikeCountsForEngrams(engramIds)
    const spikeImportances = engrams.map(e => computeSpikeImportance(allSpikes.get(e.id) ?? [], POTENTIATION_DEFAULTS.decayRate))
    const alphas = engrams.map(e => computeAlpha(allSpikeCounts.get(e.id) ?? 0, POTENTIATION_DEFAULTS))

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
      // Type-specific decay: durable facts (decision, insight) retain
      // more potentiation; ephemeral signals (anomaly, concern) decay faster.
      // Falls back to nodeType when semanticType isn't set (tool engrams).
      const semanticType = engrams[i].metadata?.semanticType as string | undefined
      const typeKey = semanticType ?? engrams[i].nodeType
      if (typeKey) {
        const multiplier = ConsolidationEngine.TYPE_POTENTIATION[typeKey] ?? 0.7
        norm *= multiplier
      }
      return norm
    })

    // Override bridge engram potentiation from their synapse links (capped at 0.3)
    for (let i = 0; i < engrams.length; i++) {
      if (engrams[i].nodeType === 'bridge') {
        const bridgeSynapses = synapses.filter(
          s => s.sourceId === engrams[i].id || s.targetId === engrams[i].id,
        )
        if (bridgeSynapses.length > 0) {
          const avgWeight = bridgeSynapses.reduce((sum, s) => sum + s.weight, 0) / bridgeSynapses.length
          normalized[i] = Math.min(avgWeight, 0.3)
        } else {
          normalized[i] = 0
        }
      }
    }

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
    const pullVectors = new Map<string, { dx: number; dy: number; dz: number; totalWeight: number }>()

    for (const [pairKey, count] of coActivationCounts) {
      const [idA, idB] = pairKey.split('|')
      const a = engramMap.get(idA)
      const b = engramMap.get(idB)
      if (!a || !b) continue

      const rate = KINDLING_DEFAULTS.driftLearningRate * Math.min(count * 0.1, 0.5)

      // Type affinity: engrams of the same semantic type attract each other
      // an additional 25%, pulling decision clusters together spatially.
      const aType = (a.metadata?.semanticType as string) ?? null
      const bType = (b.metadata?.semanticType as string) ?? null
      const affinity = (aType && aType === bType) ? 1.25 : 1.0

      const pullA = pullVectors.get(idA) ?? { dx: 0, dy: 0, dz: 0, totalWeight: 0 }
      pullA.dx += rate * affinity * (b.x - a.x)
      pullA.dy += rate * affinity * (b.y - a.y)
      pullA.dz += rate * affinity * (b.z - a.z)
      pullA.totalWeight += rate * affinity
      pullVectors.set(idA, pullA)

      const pullB = pullVectors.get(idB) ?? { dx: 0, dy: 0, dz: 0, totalWeight: 0 }
      pullB.dx += rate * affinity * (a.x - b.x)
      pullB.dy += rate * affinity * (a.y - b.y)
      pullB.dz += rate * affinity * (a.z - b.z)
      pullB.totalWeight += rate * affinity
      pullVectors.set(idB, pullB)
    }

    const updates: Array<{ id: string; x: number; y: number; z: number }> = []
    for (const [id, pull] of pullVectors) {
      const e = engramMap.get(id)
      if (!e || pull.totalWeight === 0) continue

      const newX = e.x + pull.dx
      const newY = e.y + pull.dy
      const newZ = e.z + pull.dz
      if (Math.abs(newX - e.x) > 0.0001 || Math.abs(newY - e.y) > 0.0001 || Math.abs(newZ - e.z) > 0.0001) {
        updates.push({ id, x: newX, y: newY, z: newZ })
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

    // Batch-fetch spikes for all engrams in a single query
    const engramIds = engrams.map(e => e.id)
    const allSpikes = this.cortex.getAllSpikesForEngrams(engramIds, 20)
    for (const engram of engrams) {
      const spikes = allSpikes.get(engram.id) ?? []
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
   * Centripetal Drift: radial attractor force that pulls engrams inward
   * based on their Pineal synapse connectivity. Engrams strongly connected
   * to pineal_facet engrams drift toward the origin (lower r); disconnected
   * engrams drift outward due to a small constant pressure.
   *
   * This self-organizes the field so core semantic knowledge (pineal facets)
   * anchors the center and less-relevant engrams migrate to the periphery.
   */
  async applyCentripetalDrift(
    preloaded?: { engrams: Engram[]; synapses: MnemicSynapse[] },
  ): Promise<number> {
    const { engrams, synapses } = preloaded ?? this.cortex.getAllEngramsWithSynapses()
    if (engrams.length === 0) return 0

    await yieldToEventLoop()

    // Build a set of pineal_facet engram IDs
    const pinealIds = new Set<string>()
    for (const e of engrams) {
      if (e.nodeType === 'pineal_facet') pinealIds.add(e.id)
    }
    if (pinealIds.size === 0) return 0

    // Compute pineal synapse weight for each non-pineal engram.
    // A synapse is "pineal-connected" if either endpoint is a pineal_facet.
    const pinealWeights = new Map<string, number>()
    for (const syn of synapses) {
      const srcPineal = pinealIds.has(syn.sourceId)
      const tgtPineal = pinealIds.has(syn.targetId)
      if (srcPineal && !tgtPineal) {
        pinealWeights.set(syn.targetId, (pinealWeights.get(syn.targetId) ?? 0) + syn.weight)
      } else if (!srcPineal && tgtPineal) {
        pinealWeights.set(syn.sourceId, (pinealWeights.get(syn.sourceId) ?? 0) + syn.weight)
      }
    }

    await yieldToEventLoop()

    const updates: Array<{ id: string; x: number; y: number; z: number }> = []

    for (const engram of engrams) {
      // Do not drift pineal_facet engrams — they are the anchors
      if (engram.nodeType === 'pineal_facet') continue

      // Read current radial distance from metadata, or compute from x,y
      let r = (engram.metadata?.r as number | undefined) ?? Math.sqrt(engram.x * engram.x + engram.y * engram.y)
      if (isNaN(r) || r <= 0) r = 0.5

      // Read current angle from metadata, or compute from x,y
      const theta = (engram.metadata?.theta as number | undefined) ?? Math.atan2(engram.y, engram.x)

      const pinealWeight = pinealWeights.get(engram.id) ?? 0
      let inwardForce = pinealWeight * 0.01
      const outwardPressure = 0.002

      // Harmony modulation (Phase 3: Yin/Yang homeostatic topology)
      // harmony < 0.5 (Yang-dominated, too clustered): weaken centripetal pull
      // harmony > 0.5 (Yin-dominated, too dispersed): strengthen centripetal pull
      if (this.harmonyProvider) {
        const harmony = this.harmonyProvider()
        const harmonyFactor = 1.0 + (0.5 - harmony) * 1.0  // range 0.5–1.5
        inwardForce *= Math.max(0.5, Math.min(1.5, harmonyFactor))
      }

      let newR = r - inwardForce + outwardPressure
      newR = Math.max(0.01, Math.min(1.0, newR))

      const newX = newR * Math.cos(theta)
      const newY = newR * Math.sin(theta)
      // Scale z proportionally to radial drift: engrams pulled inward
      // also move closer to the semantic plane (z → 0).
      const zScale = r > 0.001 ? newR / r : 1.0
      const newZ = engram.z * zScale

      if (Math.abs(newX - engram.x) > 0.0001 || Math.abs(newY - engram.y) > 0.0001 || Math.abs(newZ - engram.z) > 0.0001) {
        updates.push({ id: engram.id, x: newX, y: newY, z: newZ })
      }
    }

    if (updates.length > 0) {
      await this.cortex.bulkUpdatePositionsBatched(updates)
    }

    this.logger.debug('Centripetal drift applied', { drifted: updates.length })
    return updates.length
  }

  /**
   * Angular Drift: engrams align their angle (theta) toward the weighted
   * average angle of their connected neighbors. Over time this pulls
   * topically-related engrams into the same angular sectors.
   */
  async applyAngularDrift(
    preloaded?: { engrams: Engram[]; synapses: MnemicSynapse[] },
  ): Promise<number> {
    const { engrams, synapses } = preloaded ?? this.cortex.getAllEngramsWithSynapses()
    if (engrams.length === 0) return 0

    await yieldToEventLoop()

    // Build bidirectional adjacency from synapses
    const adjacency = new Map<string, Array<{ neighborId: string; weight: number }>>()
    for (const syn of synapses) {
      if (!adjacency.has(syn.sourceId)) adjacency.set(syn.sourceId, [])
      if (!adjacency.has(syn.targetId)) adjacency.set(syn.targetId, [])
      adjacency.get(syn.sourceId)!.push({ neighborId: syn.targetId, weight: syn.weight })
      adjacency.get(syn.targetId)!.push({ neighborId: syn.sourceId, weight: syn.weight })
    }

    const engramMap = new Map(engrams.map(e => [e.id, e]))

    await yieldToEventLoop()

    const updates: Array<{ id: string; x: number; y: number; z: number }> = []

    for (const engram of engrams) {
      // Do not drift pineal_facet engrams — they anchor their sectors
      if (engram.nodeType === 'pineal_facet') continue

      const neighbors = adjacency.get(engram.id)
      if (!neighbors || neighbors.length === 0) continue

      // Weighted circular mean of neighbor angles
      let sumSin = 0
      let sumCos = 0
      let totalWeight = 0

      for (const { neighborId, weight } of neighbors) {
        const neighbor = engramMap.get(neighborId)
        if (!neighbor) continue
        const nTheta = (neighbor.metadata?.theta as number | undefined) ?? Math.atan2(neighbor.y, neighbor.x)
        sumSin += Math.sin(nTheta) * weight
        sumCos += Math.cos(nTheta) * weight
        totalWeight += weight
      }

      if (totalWeight === 0) continue

      const avgTheta = Math.atan2(sumSin, sumCos)
      const normalizedAvg = avgTheta < 0 ? avgTheta + 2 * Math.PI : avgTheta
      const currentTheta = (engram.metadata?.theta as number | undefined) ?? Math.atan2(engram.y, engram.x)
      let lerpRate = 0.05

      // Harmony modulation (Phase 3: Yin/Yang homeostatic topology)
      // harmony < 0.5 (Yang-dominated): strengthen angular drift to spread engrams
      // harmony > 0.5 (Yin-dominated): weaken angular drift to let clusters stay
      if (this.harmonyProvider) {
        const harmony = this.harmonyProvider()
        const angularFactor = 1.0 - (0.5 - harmony) * 1.0  // range 0.5–1.5
        lerpRate *= Math.max(0.5, Math.min(1.5, angularFactor))
      }

      const newTheta = lerpAngle(currentTheta, normalizedAvg, lerpRate)

      // Preserve radial distance
      const r = (engram.metadata?.r as number | undefined) ?? Math.sqrt(engram.x * engram.x + engram.y * engram.y)

      const newX = r * Math.cos(newTheta)
      const newY = r * Math.sin(newTheta)

      // Lerp z toward weighted average neighbor z
      let sumZ = 0
      let totalZW = 0
      for (const { neighborId, weight } of neighbors) {
        const neighbor = engramMap.get(neighborId)
        if (!neighbor) continue
        sumZ += neighbor.z * weight
        totalZW += weight
      }
      const newZ = totalZW > 0
        ? engram.z + lerpRate * (sumZ / totalZW - engram.z)
        : engram.z

      if (Math.abs(newX - engram.x) > 0.0001 || Math.abs(newY - engram.y) > 0.0001 || Math.abs(newZ - engram.z) > 0.0001) {
        updates.push({ id: engram.id, x: newX, y: newY, z: newZ })
      }
    }

    if (updates.length > 0) {
      await this.cortex.bulkUpdatePositionsBatched(updates)
    }

    this.logger.debug('Angular drift applied', { drifted: updates.length })
    return updates.length
  }

  /**
   * Contrastive Retrieval Feedback: self-supervised radial position learning
   * from spike outcomes. Engrams that produce consistently useful offspring
   * (high success-to-failure ratio) drift inward toward the origin; engrams
   * that are retrieved but never used drift outward toward the periphery.
   *
   * Reads spike outcomes (success/failure/unknown) from the cortex,
   * computes a utility score per engram, and applies a small radial drift
   * proportional to that utility. Pineal facet engrams are skipped — they
   * are semantic anchors and must not drift.
   */
  async applyContrastiveFeedback(
    preloaded?: { engrams: Engram[]; synapses: MnemicSynapse[] },
  ): Promise<number> {
    const { engrams } = preloaded ?? this.cortex.getAllEngramsWithSynapses()
    if (engrams.length === 0) return 0

    await yieldToEventLoop()

    // Batch-fetch spike outcome distributions for all engrams in 2 queries
    const engramIds = engrams.map(e => e.id)
    const spikeOutcomes = this.cortex.getAllSpikeOutcomesForEngrams(engramIds)
    const spikeCounts = this.cortex.getAllSpikeCountsForEngrams(engramIds)

    await yieldToEventLoop()

    const updates: Array<{ id: string; x: number; y: number }> = []
    const MIN_SPIKES = 5
    const DRIFT_FACTOR = 0.005

    for (const engram of engrams) {
      // Pineal facet engrams are semantic anchors — never drift them
      if (engram.nodeType === 'pineal_facet') continue

      const outcomes = spikeOutcomes.get(engram.id)
      const totalSpikes = spikeCounts.get(engram.id) ?? 0

      // Only apply when sufficient evidence exists
      if (totalSpikes < MIN_SPIKES) continue

      // Compute utility: (success - failure) / (success + failure + 1)
      // Positive utility → engram produces useful offspring → drift inward
      // Negative utility → engram retrieved but unused → drift outward
      let utility = 0
      if (outcomes) {
        const successCount = outcomes.success
        const failureCount = outcomes.failure
        const total = successCount + failureCount
        if (total > 0) {
          utility = (successCount - failureCount) / (total + 1)
        }
      }

      // Read current radial distance from metadata, or compute from Cartesian
      let r = (engram.metadata?.r as number | undefined)
        ?? Math.sqrt(engram.x * engram.x + engram.y * engram.y)
      if (isNaN(r) || r <= 0) r = 0.5

      // Apply drift: positive utility pulls inward, negative pushes outward
      const newR = Math.max(0.01, Math.min(1.0, r - utility * DRIFT_FACTOR))

      // Preserve current angular position
      const theta = (engram.metadata?.theta as number | undefined)
        ?? Math.atan2(engram.y, engram.x)

      const newX = newR * Math.cos(theta)
      const newY = newR * Math.sin(theta)

      if (Math.abs(newX - engram.x) > 0.0001 || Math.abs(newY - engram.y) > 0.0001) {
        updates.push({ id: engram.id, x: newX, y: newY })
      }
    }

    if (updates.length > 0) {
      await this.cortex.bulkUpdatePositionsBatched(updates)
    }

    this.logger.debug('Contrastive feedback drift applied', { drifted: updates.length })
    return updates.length
  }

  /**
   * Multi-level DBSCAN: density-based clustering at multiple epsilon scales.
   * Level 0 (ε=0.015): nuclei from engrams (depth 0).
   * Level 2 (ε=0.05):  super-nuclei from nucleus centroids, parent-linked to depth-0 nuclei.
   * Level 1 (sub-nuclei, ε=0.005) deferred until 3D topology is available.
   *
   * Returns { nucleiDetected, superNucleiDetected, fractalDimension }.
   */
  detectNuclei(minClusterSize = 3, epsilon = 0.015): number {
    const { engramCount } = this.cortex.stats()
    const engrams = engramCount <= 10000
      ? this.cortex.getAllEngrams()
      : this.cortex.getSpatialEngrams(10000)
    if (engrams.length < minClusterSize) return 0

    // Snapshot old nuclei with their member IDs for Jaccard reconciliation
    const oldNuclei = this.cortex.listNuclei().filter(n => n.depth === 0)
    const oldMemberSets = new Map<string, Set<string>>()
    for (const n of oldNuclei) {
      const ids = this.cortex.getEngramIdsByCluster(n.id)
      if (ids.length > 0) oldMemberSets.set(n.id, new Set(ids))
    }
    // Also snapshot old super-nuclei (depth 2)
    const oldSuperNuclei = this.cortex.listNuclei().filter(n => n.depth === 2)
    const oldSuperMemberSets = new Map<string, Set<string>>()
    for (const sn of oldSuperNuclei) {
      const childIds = this.cortex.getChildNucleusIds(sn.id)
      if (childIds.length > 0) oldSuperMemberSets.set(sn.id, new Set(childIds))
    }

    // DBSCAN clustering: engrams → depth-0 nuclei
    // Level 0: nuclei from engrams (depth 0)
    const clusters = this.dbscan(engrams, epsilon, minClusterSize)

    // Reconcile: match old nuclei → new clusters by Jaccard overlap.
    // Sort old nuclei largest-first so bigger clusters get first claim.
    const sortedOld = oldNuclei
      .filter(n => oldMemberSets.has(n.id))
      .sort((a, b) => (oldMemberSets.get(b.id)?.size ?? 0) - (oldMemberSets.get(a.id)?.size ?? 0))

    const claimedClusters = new Set<number>()
    const clusterToOldId = new Map<number, string>()  // clusterNum → old nucleus ID

    for (const old of sortedOld) {
      const oldIds = oldMemberSets.get(old.id)!
      let bestJaccard = 0
      let bestCluster = -1

      for (const [clusterNum, members] of clusters) {
        if (claimedClusters.has(clusterNum)) continue
        const newIds = new Set(members.map(e => e.id))
        let intersection = 0
        for (const id of oldIds) { if (newIds.has(id)) intersection++ }
        const union = oldIds.size + newIds.size - intersection
        const jaccard = union > 0 ? intersection / union : 0
        if (jaccard > bestJaccard) { bestJaccard = jaccard; bestCluster = clusterNum }
      }

      if (bestJaccard >= 0.5 && bestCluster >= 0) {
        claimedClusters.add(bestCluster)
        clusterToOldId.set(bestCluster, old.id)
      }
    }

    // Create or update nuclei from each cluster, preserving identity where possible
    let nucleiCount = 0
    const survivedOldIds = new Set(clusterToOldId.values())

    for (const [clusterNum, members] of clusters) {
      const centroidX = members.reduce((s, e) => s + e.x, 0) / members.length
      const centroidY = members.reduce((s, e) => s + e.y, 0) / members.length
      const centroidZ = members.reduce((s, e) => s + (e.z ?? 0), 0) / members.length
      const avgPot = members.reduce((s, e) => s + e.potentiation, 0) / members.length

      const oldId = clusterToOldId.get(clusterNum)
      if (oldId) {
        // Surviving nucleus — update centroid + member count, keep label
        this.cortex.updateNucleus(oldId, {
          centroidX, centroidY, centroidZ,
          memberCount: members.length,
          avgPotentiation: avgPot,
        })
        for (const member of members) {
          this.cortex.updateEngram(member.id, { clusterId: oldId })
        }
      } else {
        // New nucleus — create with auto-label
        const dominantType = this.findDominantType(members)
        const dominantEmotion = this.computeClusterAffect(members)
        const emotionPrefix = dominantEmotion ? `${dominantEmotion}-` : ''
        const label = `${emotionPrefix}${dominantType}-cluster-${nucleiCount}`

        const nucleus = this.cortex.createNucleus({
          label, centroidX, centroidY, centroidZ, depth: 0,
        })
        this.cortex.updateNucleus(nucleus.id, {
          memberCount: members.length,
          avgPotentiation: avgPot,
        })
        for (const member of members) {
          this.cortex.updateEngram(member.id, { clusterId: nucleus.id })
        }
      }
      nucleiCount++
    }

    // Delete old nuclei that dissolved (no matching cluster above Jaccard threshold)
    for (const old of oldNuclei) {
      if (!survivedOldIds.has(old.id)) {
        this.cortex.deleteNucleus(old.id)
      }
    }

    // Level 2: super-nuclei from depth-0 nucleus centroids (with reconciliation)
    const SUPER_EPSILON = 0.05
    const SUPER_MIN_PTS = 2
    let superNucleiCount = 0
    const depth0Nuclei = this.cortex.listNuclei().filter(n => n.depth === 0)

    if (depth0Nuclei.length >= SUPER_MIN_PTS) {
      const pseudoEngrams: Engram[] = depth0Nuclei.map(n => ({
        id: n.id,
        content: n.label,
        nodeType: 'abstraction',
        x: n.centroidX, y: n.centroidY, z: n.centroidZ ?? 0,
        t: 0, potentiation: n.avgPotentiation, clusterId: null,
        embedding: null, tags: [], provenance: 'super-nucleus-seed',
        createdAt: n.createdAt, accessedAt: null, metadata: {},
      }))

      const superClusters = this.dbscan(pseudoEngrams, SUPER_EPSILON, SUPER_MIN_PTS)

      // Reconcile super-nuclei the same way
      const sortedOldSuper = oldSuperNuclei
        .filter(sn => oldSuperMemberSets.has(sn.id))
        .sort((a, b) => (oldSuperMemberSets.get(b.id)?.size ?? 0) - (oldSuperMemberSets.get(a.id)?.size ?? 0))

      const claimedSuper = new Set<number>()
      const superClusterToOldId = new Map<number, string>()

      for (const oldSn of sortedOldSuper) {
        const oldChildIds = oldSuperMemberSets.get(oldSn.id)!
        let bestJaccard = 0
        let bestCluster = -1

        for (const [clusterNum, members] of superClusters) {
          if (claimedSuper.has(clusterNum)) continue
          const newChildIds = new Set(members.map(m => m.id))
          let intersection = 0
          for (const id of oldChildIds) { if (newChildIds.has(id)) intersection++ }
          const union = oldChildIds.size + newChildIds.size - intersection
          const jaccard = union > 0 ? intersection / union : 0
          if (jaccard > bestJaccard) { bestJaccard = jaccard; bestCluster = clusterNum }
        }

        if (bestJaccard >= 0.5 && bestCluster >= 0) {
          claimedSuper.add(bestCluster)
          superClusterToOldId.set(bestCluster, oldSn.id)
        }
      }

      const survivedSuperIds = new Set(superClusterToOldId.values())

      for (const [clusterNum, members] of superClusters) {
        const superCentroidX = members.reduce((s, e) => s + e.x, 0) / members.length
        const superCentroidY = members.reduce((s, e) => s + e.y, 0) / members.length
        const superCentroidZ = members.reduce((s, e) => s + (e.z ?? 0), 0) / members.length
        const superAvgPot = members.reduce((s, e) => s + e.potentiation, 0) / members.length

        const oldSnId = superClusterToOldId.get(clusterNum)
        if (oldSnId) {
          this.cortex.updateNucleus(oldSnId, {
            centroidX: superCentroidX, centroidY: superCentroidY, centroidZ: superCentroidZ,
            memberCount: members.length, avgPotentiation: superAvgPot,
          })
          for (const member of members) {
            this.cortex.updateNucleus(member.id, { parentNucleusId: oldSnId })
          }
        } else {
          const superNucleus = this.cortex.createNucleus({
            label: `super-cluster-${superNucleiCount}`,
            centroidX: superCentroidX, centroidY: superCentroidY, centroidZ: superCentroidZ,
            depth: 2,
          })
          this.cortex.updateNucleus(superNucleus.id, {
            memberCount: members.length, avgPotentiation: superAvgPot,
          })
          for (const member of members) {
            this.cortex.updateNucleus(member.id, { parentNucleusId: superNucleus.id })
          }
        }
        superNucleiCount++
      }

      // Delete dissolved super-nuclei
      for (const oldSn of oldSuperNuclei) {
        if (!survivedSuperIds.has(oldSn.id)) {
          this.cortex.deleteNucleus(oldSn.id)
        }
      }
    }

    this.logger.info('Multi-level nucleus detection complete', {
      depth0Nuclei: nucleiCount,
      depth2SuperNuclei: superNucleiCount,
      totalEngrams: engrams.length,
      survivedDepth0: survivedOldIds.size,
      dissolvedDepth0: oldNuclei.length - survivedOldIds.size,
      newDepth0: nucleiCount - survivedOldIds.size,
    })

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
      const ez = engrams[idx].z ?? 0
      for (let j = 0; j < n; j++) {
        if (j === idx) continue
        const dx = ex - engrams[j].x
        const dy = ey - engrams[j].y
        const dz = ez - (engrams[j].z ?? 0)
        if (dx * dx + dy * dy + dz * dz <= epsSq) neighbors.push(j)
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
   * Receive promotion candidates from the legacy detector and act on each.
   *
   * For every candidate whose source engram exists in the field, create a
   * pattern engram representing the promoted class and link the source as
   * superseded. The action side is fail-open per candidate so a single bad
   * key does not abort the batch.
   *
   * @param candidates Promotion proposals from the legacy ConsolidationEngine
   * @returns Number of pattern engrams created
   */
  consolidatePromotionCandidates(
    candidates: ReadonlyArray<{ key: string; from: string; to: string }>,
  ): number {
    if (candidates.length === 0) return 0

    let created = 0
    for (const candidate of candidates) {
      try {
        const sourceId = `memory:${candidate.key}`
        const source = this.cortex.getEngram(sourceId)
        if (!source) continue

        const patternId = `pattern:${candidate.key}:${candidate.to}`
        if (this.cortex.getEngram(patternId)) continue

        const content = `Consolidated ${candidate.from} → ${candidate.to}: ${source.content}`
        this.cortex.createEngram({
          id: patternId,
          content,
          nodeType: 'pattern',
          x: source.x,
          y: source.y,
          tags: ['consolidation', `from:${candidate.from}`, `to:${candidate.to}`],
          provenance: 'consolidation:promotion',
        })

        this.cortex.createSynapse({
          sourceId: patternId,
          targetId: sourceId,
          edgeType: 'supersedes',
          weight: 0.8,
        })
        created++
      } catch (err) {
        this.logger.debug('Promotion candidate consolidation failed (non-fatal)', {
          key: candidate.key,
          error: String(err),
        })
      }
    }

    if (created > 0) {
      this.logger.info('Promotion candidates consolidated', { count: created })
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
