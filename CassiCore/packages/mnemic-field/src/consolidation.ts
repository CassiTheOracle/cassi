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
import type { IndexResult } from './feature-index-lmdb.js'
import type { QualityScore } from './engram-quality-scorer.js'

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
  /** Phase 0 merge-on-overlap results (vindex-driven merges during consolidation). */
  mergeOnOverlaps?: number
  mergeOnOverlapReversals?: number
  mergeOnOverlapDurationMs?: number
  /** Phase 1 quality-based pruning results (vindex-driven attention Gini pruning). */
  qualityScores?: number
  qualityPruned?: number
  qualityBoosted?: number
  qualityScoringDurationMs?: number
  /** Phase 2 feature-overlap nuclei results. */
  featureOverlapNuclei?: number
  featureOverlapNucleiDurationMs?: number
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
  /** Skip vindex-driven merge-on-overlap during consolidation. */
  skipMergeOnOverlap?: boolean
  /** Minimum potentiation for engrams to be checked for merge-on-overlap. Default 0.1. */
  mergeOnOverlapMinPotentiation?: number
  /** Skip vindex-driven quality-based pruning during consolidation. */
  skipQualityBasedPruning?: boolean
  /** Minimum attention Gini score to survive quality pruning. Default 0.1 (mapped from Gini 0.5). */
  qualityPruningMinScore?: number
  /** Skip feature-overlap nuclei detection during consolidation. */
  skipFeatureOverlapNuclei?: boolean
  /** Minimum members for a feature-overlap nucleus. Default 3. */
  featureOverlapNucleiMinMembers?: number
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
 * Match old items (nuclei) to new DBSCAN clusters by Jaccard overlap
 * of their member IDs. Old items sorted largest-first get first claim.
 * Returns the mapping from cluster number → old item ID, and the set
 * of old item IDs that survived (found a match above threshold).
 */
function reconcileClusters(
  oldMemberSets: Map<string, Set<string>>,
  clusters: Map<number, Array<{ id: string }>>,
  threshold = 0.3,
): { clusterToOldId: Map<number, string>; survivedOldIds: Set<string> } {
  const sorted = [...oldMemberSets.entries()]
    .sort((a, b) => b[1].size - a[1].size)

  const claimed = new Set<number>()
  const clusterToOldId = new Map<number, string>()

  for (const [oldId, oldIds] of sorted) {
    let bestJaccard = 0
    let bestCluster = -1

    for (const [clusterNum, members] of clusters) {
      if (claimed.has(clusterNum)) continue
      const newIds = new Set(members.map(m => m.id))
      let intersection = 0
      for (const id of oldIds) { if (newIds.has(id)) intersection++ }
      const union = oldIds.size + newIds.size - intersection
      const jaccard = union > 0 ? intersection / union : 0
      if (jaccard > bestJaccard) { bestJaccard = jaccard; bestCluster = clusterNum }
    }

    if (bestJaccard >= threshold && bestCluster >= 0) {
      claimed.add(bestCluster)
      clusterToOldId.set(bestCluster, oldId)
    }
  }

  return {
    clusterToOldId,
    survivedOldIds: new Set(clusterToOldId.values()),
  }
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

  /** Vindex FeatureIndex for merge-on-overlap checks. */
  private featureIndex: {
    checkMergeFor: (engramId: string, opts?: any) => (IndexResult | null)
    findCorrelated?: (engramId: string, opts?: any) => Array<{ engramId: string; sharedFeatureCount: number }>
  } | null = null

  /** Vindex quality scorer for attention-Gini-based pruning. */
  private qualityScorer: { scoreContent: (content: string) => (QualityScore | null); isReady?: () => boolean } | null = null

  setFeatureIndex(fi: typeof this.featureIndex): void {
    this.featureIndex = fi
  }

  setQualityScorer(qs: typeof this.qualityScorer): void {
    this.qualityScorer = qs
  }

  /** Cached tonic (pineal) gate embedding for geodesic distance computation. */
  private _tonicEmbedding: Float32Array | null = null

  /** Compute and cache the tonic reference embedding from pineal facet engrams. */
  private getTonicEmbedding(): Float32Array | null {
    if (this._tonicEmbedding) return this._tonicEmbedding
    const pinealFacets = this.cortex.listEngrams(500).filter(e => e.nodeType === 'pineal_facet')
    if (pinealFacets.length === 0) return null
    const pinealIds = pinealFacets.map(e => e.id)
    const embeddings = this.cortex.getEngramEmbeddings(pinealIds)
    if (embeddings.size === 0) return null

    // Average the pineal facet embeddings (they're L2-normalized, so simple mean works)
    const dim = embeddings.values().next().value!.length
    const avg = new Float32Array(dim)
    let count = 0
    for (const emb of embeddings.values()) {
      for (let i = 0; i < dim; i++) avg[i] += emb[i]
      count++
    }
    for (let i = 0; i < dim; i++) avg[i] /= count
    // Re-normalize to keep on the sphere
    let norm = 0
    for (let i = 0; i < dim; i++) norm += avg[i] * avg[i]
    norm = Math.sqrt(norm)
    if (norm > 0.0001) for (let i = 0; i < dim; i++) avg[i] /= norm
    this._tonicEmbedding = avg
    return avg
  }

  /** Cached global attention — spherical centroid of active session vectors. */
  private _globalAttention: Float32Array | null = null

  /**
   * Set the active session attention embeddings for global attention computation.
   * Called from MnemicField when the Constellation orchestrator pushes session updates.
   * The global attention is computed as the spherical centroid (mean + renormalize)
   * of the provided session embeddings, cached until the next consolidation tick.
   */
  setActiveSessionEmbeddings(sessionEmbeddings: Float32Array[]): void {
    if (sessionEmbeddings.length === 0) {
      this._globalAttention = null
      return
    }
    const dim = sessionEmbeddings[0].length
    // Filter out embeddings with mismatched dimensions (multi-model safety)
    const valid = sessionEmbeddings.filter(e => e.length === dim && e.length > 0)
    if (valid.length === 0) {
      this._globalAttention = null
      return
    }
    const avg = new Float32Array(dim)
    for (const emb of valid) {
      for (let i = 0; i < dim; i++) avg[i] += emb[i]
    }
    for (let i = 0; i < dim; i++) avg[i] /= valid.length
    let norm = 0
    for (let i = 0; i < dim; i++) norm += avg[i] * avg[i]
    norm = Math.sqrt(norm)
    if (norm > 0.0001) for (let i = 0; i < dim; i++) avg[i] /= norm
    this._globalAttention = avg
    if (valid.length < sessionEmbeddings.length) {
      this.logger.warn('Global attention: filtered mismatched embeddings', {
        total: sessionEmbeddings.length, valid: valid.length, expectedDim: dim,
      })
    }
    this.logger.info('Global attention updated', { sessionCount: valid.length })
  }

  /** Compute the global attention consensus — prefer session centroid, fall back to tonic. */
  private getGlobalAttention(): Float32Array | null {
    return this._globalAttention ?? this.getTonicEmbedding()
  }

  /** Invalidate cached global attention after consolidation tick. */
  private invalidateGlobalAttention(): void {
    this._globalAttention = null
  }

  /**
   * Apply attention decay: slerp each session's attention toward the global
   * consensus by a small amount per consolidation tick. This creates gentle
   * convergence without collapsing individuality.
   *
   * Uses the exported slerpEmbedding from the mnemic field index.
   */
  applyAttentionDecay(sessionEmbeddings: Map<string, Float32Array>): Map<string, Float32Array> {
    const global = this.getGlobalAttention()
    if (!global) return sessionEmbeddings

    const decayed = new Map<string, Float32Array>()
    const t = 0.01  // 1% toward global per tick
    for (const [sessionId, emb] of sessionEmbeddings) {
      if (emb.length !== global.length) {
        decayed.set(sessionId, emb)
        continue
      }
      // Inline slerp to avoid circular import of slerpEmbedding
      let dot = 0
      for (let i = 0; i < emb.length; i++) dot += emb[i] * global[i]
      dot = Math.max(-1, Math.min(1, dot))
      const omega = Math.acos(dot)
      if (omega < 0.0001) {
        decayed.set(sessionId, emb)
        continue
      }
      const sinOmega = Math.sin(omega)
      const wA = Math.sin((1 - t) * omega) / sinOmega
      const wB = Math.sin(t * omega) / sinOmega
      const result = new Float32Array(emb.length)
      for (let i = 0; i < emb.length; i++) result[i] = wA * emb[i] + wB * global[i]
      decayed.set(sessionId, result)
    }
    return decayed
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
    // V-field active organization (Phases 0-2)
    let mergeOnOverlaps = 0
    let mergeOnOverlapReversals = 0
    let mergeDuration = 0
    let qualityScores = 0
    let qualityPruned = 0
    let qualityBoosted = 0
    let qualityDuration = 0
    let featureOverlapNucleiCount = 0
    let featureNucleiDuration = 0

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

      // Phase 0: Vindex-driven merge-on-overlap — catch engrams that should
      // have been merged but weren't (stored before their near-duplicate).
      // Uses stored FeatureIndex data — no gateKnn recomputation.
      if (!options.skipMergeOnOverlap && this.featureIndex) {
        const mergeStart = Date.now()
        const mResult = await this.applyMergeOnOverlap({
          minPotentiation: options.mergeOnOverlapMinPotentiation ?? 0.1,
        })
        mergeOnOverlaps = mResult.merges
        mergeOnOverlapReversals = mResult.reversals
        mergeDuration = Date.now() - mergeStart
        await yieldToEventLoop()
      }

      // Phase 1: Vindex-driven quality-based pruning — score engrams via
      // attention Gini and demote/prune low-quality ones.
      if (!options.skipQualityBasedPruning && this.qualityScorer?.isReady?.()) {
        const qualityStart = Date.now()
        const qResult = await this.applyQualityBasedPruning({
          minScore: options.qualityPruningMinScore ?? 0.1,
        })
        qualityScores = qResult.scored
        qualityPruned = qResult.pruned
        qualityBoosted = qResult.boosted
        qualityDuration = Date.now() - qualityStart
        await yieldToEventLoop()
      }

      // Phase 2: Feature-overlap nuclei — cluster engrams by vindex feature
      // overlap instead of spatial XY proximity. Uses the FeatureIndex's
      // stored feature→engram mappings to build a connectivity graph.
      if (!options.skipFeatureOverlapNuclei && this.featureIndex) {
        const nucleiStart = Date.now()
        featureOverlapNucleiCount = await this.detectFeatureOverlapNuclei({
          minMembers: options.featureOverlapNucleiMinMembers ?? 3,
        })
        featureNucleiDuration = Date.now() - nucleiStart
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
        centripetalDrifts,
        angularDrifts,
        contrastiveFeedbackDrifts,
        nucleiDetected,
        abstractionsCreated,
        spikesPruned,
        forwardTracesPruned,
        mergeOnOverlaps,
        mergeOnOverlapReversals,
        mergeDurationMs: mergeDuration,
        qualityScores,
        qualityPruned,
        qualityBoosted,
        qualityDurationMs: qualityDuration,
        featureOverlapNuclei: featureOverlapNucleiCount,
        featureNucleiDurationMs: featureNucleiDuration,
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

      this.invalidateGlobalAttention()

      return buildResult()
    } catch (err) {
      durationMs = Date.now() - start
      this.logger.error('Consolidation cycle failed', {
        error: String(err),
        phaseStatus: {
          radiance:     options.skipRadiance     ? 'skipped' : potentiationUpdates > 0 ? 'updated' : 'ran',
          drift:        options.skipDrift        ? 'skipped' : positionDrifts     > 0 ? 'updated' : 'ran',
          centripetal:  options.skipCentripetalDrift ? 'skipped' : centripetalDrifts > 0 ? 'updated' : 'ran',
          angular:      options.skipAngularDrift ? 'skipped' : angularDrifts    > 0 ? 'updated' : 'ran',
          contrastive:  options.skipContrastiveFeedback ? 'skipped' : contrastiveFeedbackDrifts > 0 ? 'updated' : 'ran',
          nuclei:       options.skipNuclei       ? 'skipped' : nucleiDetected     > 0 ? 'updated' : 'ran',
          abstractions: options.skipAbstractions ? 'skipped' : abstractionsCreated > 0 ? 'updated' : 'ran',
          pruning:      options.skipPruning      ? 'skipped' : spikesPruned       > 0 ? 'updated' : 'ran',
          mergeOverlap: options.skipMergeOnOverlap ? 'skipped' : mergeOnOverlaps > 0 ? 'updated' : 'ran',
          quality:      options.skipQualityBasedPruning ? 'skipped' : qualityScores > 0 ? 'updated' : 'ran',
          featureNuclei: options.skipFeatureOverlapNuclei ? 'skipped' : featureOverlapNucleiCount > 0 ? 'updated' : 'ran',
        },
        durationMs,
      })
      return buildResult()
    }

    function buildResult(): ConsolidationResult {
      return {
        potentiationUpdates, positionDrifts, centripetalDrifts, angularDrifts,
        contrastiveFeedbackDrifts, nucleiDetected, abstractionsCreated, spikesPruned,
        forwardTracesPruned, gradientResult, dreamResult, durationMs,
        mergeOnOverlaps, mergeOnOverlapReversals, mergeOnOverlapDurationMs: mergeDuration,
        qualityScores, qualityPruned, qualityBoosted, qualityScoringDurationMs: qualityDuration,
        featureOverlapNuclei: featureOverlapNucleiCount,
        featureOverlapNucleiDurationMs: featureNucleiDuration,
      }
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

    // Post-drift: update metadata.r to actual geodesic distance from
    // the global attention center (or tonic fallback) using gate embeddings.
    const attentionRef = this.getGlobalAttention()
    if (attentionRef) {
      const driftedIds = updates.map(u => u.id)
      const driftedEmbs = this.cortex.getEngramEmbeddings(driftedIds)
      let corrected = 0
      for (const update of updates) {
        const emb = driftedEmbs.get(update.id)
        if (!emb || emb.length === 0) continue
        let dot = 0
        for (let j = 0; j < emb.length; j++) dot += emb[j] * attentionRef[j]
        dot = Math.max(-1, Math.min(1, dot))
        // Normalize geodesic distance [0,π] to r ∈ [0,1]
        const geodesicR = Math.acos(dot) / Math.PI
        // Merge into existing metadata, preserving affect/r/theta
        const eng = this.cortex.getEngram(update.id)
        if (eng) {
          const meta = { ...(eng.metadata ?? {}), r: geodesicR }
          this.cortex.updateEngram(update.id, { metadata: meta })
          corrected++
        }
      }
      if (corrected > 0) {
        this.logger.debug('Geodesic r correction applied', { corrected, globalAttention: !!this._globalAttention })
      }
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
    const { clusterToOldId, survivedOldIds } = reconcileClusters(oldMemberSets, clusters)

    // Create or update nuclei from each cluster, preserving identity where possible
    let nucleiCount = 0
    let newNucleiCount = 0

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
        const label = `${emotionPrefix}${dominantType}-cluster-${newNucleiCount}`
        newNucleiCount++

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

      // Reconcile super-nuclei via the same generic function
      const { clusterToOldId: superClusterToOldId, survivedOldIds: survivedSuperIds } =
        reconcileClusters(oldSuperMemberSets, superClusters)

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

      // Delete dissolved super-nuclei — null child references first
      for (const oldSn of oldSuperNuclei) {
        if (!survivedSuperIds.has(oldSn.id)) {
          const children = this.cortex.getChildNucleusIds(oldSn.id)
          for (const childId of children) {
            this.cortex.updateNucleus(childId, { parentNucleusId: null })
          }
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

  /**
   * Phase 0: Continuous merge-on-overlap using stored FeatureIndex data.
   *
   * Scans top engrams by potentiation and checks whether they should be
   * merged into another engram via ≥95% feature overlap. This catches
   * duplicates that were stored before their near-duplicate was indexed.
   *
   * When a merge is triggered: the merged engram's potentiation is zeroed
   * (soft retirement) and the anchor's potentiation is boosted. When
   * anchor quality reversal triggers, the old anchor is retired instead
   * and the richer engram remains.
   */
  private async applyMergeOnOverlap(opts: {
    minPotentiation?: number
    batchSize?: number
  }): Promise<{ merges: number; reversals: number }> {
    const minPot = opts.minPotentiation ?? 0.1
    const batchSize = opts.batchSize ?? 200
    let merges = 0
    let reversals = 0

    if (!this.featureIndex) return { merges, reversals }

    const engrams = this.cortex.listEngrams(batchSize * 3)
      .filter(e => e.nodeType && !['bridge', 'file_read', 'file_version', 'message',
        'session', 'thought_command', 'tool', 'tool_invocation'].includes(e.nodeType))
      .filter(e => e.potentiation >= minPot)
      .slice(0, batchSize)

    for (let i = 0; i < engrams.length; i++) {
      const e = engrams[i]
      try {
        // Fetch the merged engram's embedding for slerp-on-merge
        const mergedEmb = this.cortex.getEngramEmbeddings([e.id]).get(e.id)
        const result = this.featureIndex!.checkMergeFor(e.id, {
          minOverlapRatio: 0.95,
          embedding: mergedEmb ?? undefined,
        })
        if (!result) continue

        if (result.action === 'merged' && result.mergedInto) {
          // Boost anchor potentiation
          const anchor = this.cortex.getEngram(result.mergedInto)
          const featureCount = result.featureCount ?? 10
          const boost = 0.02 * Math.min(1.0, featureCount / 40)
          if (anchor) {
            this.cortex.updateEngram(result.mergedInto, {
              potentiation: Math.min(1.0, anchor.potentiation + boost),
            })
          }
          // Soft-retire the merged engram
          this.cortex.updateEngram(e.id, {
            potentiation: 0.001,
            metadata: { mergedInto: result.mergedInto, mergeReason: 'feature-overlap-consolidation' },
          })

          // Slerp the gate embeddings of anchor and merged engram.
          // FeatureIndex returns the slerped embedding when both are available.
          if (result.slerpedEmbedding) {
            this.cortex.bulkUpdateEmbeddings([{ id: result.mergedInto, embedding: result.slerpedEmbedding }])
          }
          merges++
        } else if (result.action === 'indexed') {
          // Anchor quality reversal: the old anchor was removed from index.
          // Retire the old anchor instead. This engram stays.
          // The FeatureIndex already re-indexed the richer engram with union features.
          // We need to find the old anchor — checkMergeFor removed it from the index.
          // The absorbed engram's ID was in `result.mergedInto` — but reversal returns
          // action='indexed' without mergedInto. We'll detect the enriched engram
          // by looking for the one that just absorbed features.
          // For now, log and move on — the FeatureIndex already did the work.
          reversals++
          this.logger.debug?.('Merge-on-overlap reversed', {
            engramId: e.id.slice(0, 12),
            featureCount: result.featureCount,
          })
        }
      } catch (err) {
        this.logger.debug?.('Merge-on-overlap check failed', {
          engramId: e.id.slice(0, 12),
          error: String(err),
        })
      }

      // Yield every 50 engrams
      if ((i + 1) % 50 === 0) await yieldToEventLoop()
    }

    if (merges > 0 || reversals > 0) {
      this.logger.info('Merge-on-overlap complete', { merges, reversals, scanned: engrams.length })
    }

    return { merges, reversals }
  }

  /**
   * Phase 1: Quality-based pruning using attention Gini scoring.
   *
   * Scores low-potentiation engrams via vindexForward + attention Gini.
   * Low-quality engrams (noise, stubs) have their potentiation halved,
   * accelerating natural decay. High-quality engrams with low potentiation
   * get boosted — the model recognizes their value even if they're unused.
   *
   * Each scoring call costs ~1s on GPU (forward pass). Batch size is kept
   * small (20) to keep consolidation responsive.
   */
  private async applyQualityBasedPruning(opts: {
    minScore?: number
    batchSize?: number
  }): Promise<{ scored: number; pruned: number; boosted: number }> {
    const minScore = opts.minScore ?? 0.1
    const batchSize = opts.batchSize ?? 20
    let scored = 0
    let pruned = 0
    let boosted = 0

    if (!this.qualityScorer?.isReady?.()) return { scored, pruned, boosted }

    // Target low-potentiation engrams that are still indexed
    const candidates = this.cortex.listEngrams(batchSize * 5)
      .filter(e => e.nodeType && !['bridge', 'file_read', 'file_version', 'message',
        'session', 'thought_command', 'tool', 'tool_invocation'].includes(e.nodeType))
      .filter(e => e.potentiation > 0.001 && e.potentiation < 0.15)
      .filter(e => e.content && e.content.length > 30)
      .slice(0, batchSize)

    for (const e of candidates) {
      try {
        const result = this.qualityScorer!.scoreContent(e.content)
        if (!result) continue
        scored++

        if (result.score < minScore) {
          // Low quality: halve potentiation → faster decay
          const newPot = Math.max(0.001, e.potentiation * 0.5)
          this.cortex.updateEngram(e.id, { potentiation: newPot })
          pruned++
          this.logger.debug?.('Quality pruning demoted engram', {
            engramId: e.id.slice(0, 12),
            score: result.score.toFixed(3),
            gini: result.attentionGini.toFixed(3),
            oldPot: e.potentiation.toFixed(4),
            newPot: newPot.toFixed(4),
          })
        } else if (result.score > 0.5 && e.potentiation < 0.05) {
          // High quality but low potentiation: boost
          this.cortex.updateEngram(e.id, {
            potentiation: Math.min(0.2, e.potentiation + 0.05),
          })
          boosted++
          this.logger.debug?.('Quality scoring boosted engram', {
            engramId: e.id.slice(0, 12),
            score: result.score.toFixed(3),
            gini: result.attentionGini.toFixed(3),
          })
        }
      } catch (err) {
        this.logger.debug?.('Quality scoring failed', {
          engramId: e.id.slice(0, 12),
          error: String(err),
        })
      }

      // Yield every 5 (each call is ~1s on GPU)
      if ((scored + 1) % 5 === 0) await yieldToEventLoop()
    }

    if (scored > 0) {
      this.logger.info('Quality-based pruning complete', { scored, pruned, boosted })
    }

    return { scored, pruned, boosted }
  }

  /**
   * Phase 2: Feature-overlap nucleus detection.
   *
   * Clusters engrams by vindex feature overlap instead of spatial XY
   * proximity. Uses FeatureIndex.findCorrelated() to build a connectivity
   * graph and Union-Find to detect connected components.
   *
   * Each connected component with ≥minMembers becomes a nucleus. Overlap
   * threshold is set high (min 3 shared features) to keep clusters tight
   * — the model's own concept boundaries define what belongs together.
   */
  private async detectFeatureOverlapNuclei(opts: {
    minMembers?: number
    batchSize?: number
  }): Promise<number> {
    const minMembers = opts.minMembers ?? 3
    const batchSize = opts.batchSize ?? 300

    if (!this.featureIndex?.findCorrelated) return 0

    // Get top engrams by potentiation (exclude structural types)
    const engrams = this.cortex.listEngrams(batchSize)
      .filter(e => e.nodeType && !['bridge', 'file_read', 'file_version', 'message',
        'session', 'thought_command', 'tool', 'tool_invocation'].includes(e.nodeType))
      .filter(e => e.potentiation > 0.05)
      .slice(0, batchSize)

    if (engrams.length < minMembers) return 0

    // Union-Find for connected components
    const parent = new Map<string, string>()
    const find = (x: string): string => {
      const p = parent.get(x)
      if (!p || p === x) return x
      const root = find(p)
      parent.set(x, root) // path compression
      return root
    }
    const union = (a: string, b: string) => {
      const ra = find(a)
      const rb = find(b)
      if (ra !== rb) parent.set(ra, rb)
    }

    // Initialize each engram as its own component
    for (const e of engrams) {
      parent.set(e.id, e.id)
    }
    const engramIds = new Set(engrams.map(e => e.id))

    // Build connectivity graph via FeatureIndex.findCorrelated
    let edges = 0
    for (let i = 0; i < engrams.length; i++) {
      const e = engrams[i]
      try {
        const correlated = this.featureIndex!.findCorrelated!(e.id, {
          minOverlap: 3,
          limit: 10,
        })
        for (const corr of correlated) {
          if (engramIds.has(corr.engramId) && corr.engramId !== e.id) {
            union(e.id, corr.engramId)
            edges++
          }
        }
      } catch {
        // best-effort — skip failed lookups
      }

      // Yield every 50
      if ((i + 1) % 50 === 0) await yieldToEventLoop()
    }

    // Collect connected components
    const components = new Map<string, string[]>()
    for (const e of engrams) {
      const root = find(e.id)
      const comp = components.get(root) ?? []
      comp.push(e.id)
      components.set(root, comp)
    }

    // Create/update nuclei for components with ≥minMembers
    let nucleiCreated = 0
    for (const [_, members] of components) {
      if (members.length < minMembers) continue

      // Compute centroid from engram positions
      let cx = 0, cy = 0, cz = 0, count = 0
      for (const id of members) {
        const eng = this.cortex.getEngram(id)
        if (!eng) continue
        cx += eng.x ?? 0
        cy += eng.y ?? 0
        cz += eng.z ?? 0
        count++
      }
      if (count === 0) continue
      cx /= count; cy /= count; cz /= count

      try {
        const nucleus = this.cortex.createNucleus({
          label: `feature-cluster-${members.length}`,
          centroidX: cx,
          centroidY: cy,
          centroidZ: cz,
          depth: 0,
        })
        this.cortex.updateNucleus(nucleus.id, {
          memberCount: members.length,
          avgPotentiation: members.length > 0 ? 0.1 : 0,
        })
        // Assign members to nucleus
        for (const id of members) {
          this.cortex.updateEngram(id, { clusterId: nucleus.id })
        }
        nucleiCreated++
      } catch (err) {
        this.logger.debug?.('Feature-overlap nucleus creation failed', {
          members: members.length,
          error: String(err),
        })
      }
    }

    if (nucleiCreated > 0) {
      this.logger.info('Feature-overlap nuclei detected', {
        nucleiCreated,
        scanned: engrams.length,
        edges,
        components: components.size,
      })
    }

    return nucleiCreated
  }

}
