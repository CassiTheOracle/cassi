import type { ILogger } from '@cassicore/foundation'
import type { Cortex } from '../cortex.js'
import type { LightningIndexer } from '../lightning-indexer.js'
import type { LightningRetrievalEvent, IndexerTrainingConfig } from '../types.js'
import { INDEXER_TRAINING_DEFAULTS } from '../types.js'
import type { RetrievalLabelTriple } from '../vendor/core/intelligence/reverie/retrieval-labeler-types.js'
import {
  type IndexerDims,
  type IndexerParams,
  type IndexerGradients,
  type RetrievalRequest,
  computeRetrievalLoss,
} from './retrieval-loss.js'
import { makeMatrixParam, makeVectorParam, zeroGradients, optimizerStep } from './muon.js'
import type { OptParam } from './muon.js'
import { WeightStore } from './weight-store.js'

export interface RunOnceResult {
  skipped: boolean
  reason?: string
  initialLoss?: number
  finalLoss?: number
  epochsRun?: number
  retrievalsTrained?: number
  triplesProcessed?: number
  versionBefore?: number
  versionAfter?: number
  totalGradNorm?: number
  durationMs?: number
}

interface PreparedRetrieval {
  retrievalId: string
  request: RetrievalRequest
  triples: number
}

const DEFAULT_PENDING_LIMIT = 1024

export class IndexerTrainer {
  private readonly weightStore: WeightStore
  private params: OptParam[] | null = null
  private stepCount = 0
  private totalTriplesProcessed = 0

  constructor(
    private readonly cortex: Cortex,
    private readonly indexer: LightningIndexer,
    private readonly logger: ILogger,
    private readonly cfg: IndexerTrainingConfig = INDEXER_TRAINING_DEFAULTS,
  ) {
    this.weightStore = new WeightStore(cortex.getDatabase())
  }

  get steps(): number { return this.stepCount }
  get totalProcessed(): number { return this.totalTriplesProcessed }

  get readyForPromotion(): boolean {
    return this.totalTriplesProcessed >= this.cfg.minTriplesForPromotion
      && this.stepCount >= this.cfg.minStepsForPromotion
  }

  async runOnce(): Promise<RunOnceResult> {
    const start = Date.now()
    const limit = DEFAULT_PENDING_LIMIT
    const triples = this.cortex.getPendingIndexerTrainingRequests(limit)
    if (triples.length === 0) {
      return { skipped: true, reason: 'no pending training requests' }
    }

    const global = this.cortex.getLightningGlobal()
    if (!global) {
      return { skipped: true, reason: 'no lightning_index_global row (indexer not initialized)' }
    }

    const dims: IndexerDims = {
      dEmb: global.dEmb,
      dC: global.dC,
      nH: global.nH,
      dIdx: global.dIdx,
    }

    const prepared = this.prepareRetrievals(triples, dims)
    if (prepared.length === 0) {
      return { skipped: true, reason: 'no valid retrievals (missing query embeddings or keys)' }
    }

    // Initialize optimizer params on first call, synced with current global
    if (!this.params) {
      this.params = [
        makeMatrixParam('wDq', dims.dC, dims.dEmb, global.wDq),
        makeMatrixParam('wIuq', dims.nH * dims.dIdx, dims.dC, global.wIuq),
        makeVectorParam('wI', dims.nH, global.wI),
      ]
    } else {
      // Sync optimizer params with current global in case of external updates
      this.params[0].weight.set(global.wDq)
      this.params[1].weight.set(global.wIuq)
      this.params[2].weight.set(global.wI)
    }

    const indexerParams: IndexerParams = {
      wDq: this.params[0].weight,
      wIuq: this.params[1].weight,
      wI: this.params[2].weight,
    }

    // One epoch: compute loss + gradients in a single pass, then apply optimizer
    zeroGradients(this.params)
    let initialLoss = 0
    let lossSampleCount = 0
    const batchSize = Math.min(this.cfg.batchSize, prepared.length)
    for (let i = 0; i < prepared.length; i += batchSize) {
      const batch = prepared.slice(i, Math.min(i + batchSize, prepared.length))
      const batchLoss = this.accumulateBatchGradients(batch, indexerParams, dims)
      initialLoss += batchLoss
      lossSampleCount += batch.length
    }
    if (lossSampleCount > 0) initialLoss /= lossSampleCount

    // Apply optimizer step
    const optResult = optimizerStep(this.params, {
      muon: {
        learningRate: this.cfg.muonLR,
        beta: this.cfg.muonBeta,
        weightDecay: this.cfg.muonWeightDecay,
        nesterov: true,
        scaleByShape: true,
      },
      adamw: {
        learningRate: this.cfg.adamwLR,
        beta1: this.cfg.adamwBeta1,
        beta2: this.cfg.adamwBeta2,
        eps: this.cfg.adamwEps,
        weightDecay: this.cfg.adamwWeightDecay,
      },
      step: this.stepCount + 1,
    })

    const finalLoss = this.meanLoss(indexerParams, dims, prepared)

    // Persist updated weights
    this.cortex.setLightningGlobal({
      wDq: indexerParams.wDq,
      wIuq: indexerParams.wIuq,
      wI: indexerParams.wI,
      dEmb: dims.dEmb,
      dC: dims.dC,
      nH: dims.nH,
      dIdx: dims.dIdx,
      version: global.version + 1,
    })

    // Update the indexer's in-memory state so subsequent retrievals use new weights
    this.indexer.updateWeights(indexerParams.wDq, indexerParams.wIuq, indexerParams.wI, global.version + 1)

    // Mark triples as processed
    const retrievalIds = [...new Set(prepared.map(p => p.retrievalId))]
    this.cortex.markIndexerTrainingRequestsProcessed(retrievalIds)

    const triplesProcessed = prepared.reduce((s, p) => s + p.triples, 0)
    const durationMs = Date.now() - start

    // Record training step
    this.weightStore.recordTrainingStep({
      version: global.version + 1,
      requestsInBatch: triplesProcessed,
      lossBefore: initialLoss,
      lossAfter: finalLoss,
      learningRate: this.cfg.muonLR,
      muonSteps: optResult.perParam.filter(p => p.kind === 'matrix').length,
      adamwSteps: optResult.perParam.filter(p => p.kind === 'vector').length,
      gradNorm: optResult.totalGradNorm,
      durationMs,
    })

    this.stepCount++
    this.totalTriplesProcessed += triplesProcessed

    this.logger.info('IndexerTrainer.runOnce: trained', {
      retrievals: prepared.length,
      triplesProcessed,
      initialLoss: initialLoss.toFixed(4),
      finalLoss: finalLoss.toFixed(4),
      gradNorm: optResult.totalGradNorm.toFixed(4),
      versionBefore: global.version,
      versionAfter: global.version + 1,
      durationMs,
    })

    return {
      skipped: false,
      initialLoss,
      finalLoss,
      epochsRun: 1,
      retrievalsTrained: prepared.length,
      triplesProcessed,
      versionBefore: global.version,
      versionAfter: global.version + 1,
      totalGradNorm: optResult.totalGradNorm,
      durationMs,
    }
  }

  // ── private helpers ──────────────────────────────────────────────────────  // contributing:ignore

  private prepareRetrievals(triples: RetrievalLabelTriple[], dims: IndexerDims): PreparedRetrieval[] {
    const byRetrieval = new Map<string, RetrievalLabelTriple[]>()
    for (const t of triples) {
      const list = byRetrieval.get(t.retrievalId) ?? []
      list.push(t)
      byRetrieval.set(t.retrievalId, list)
    }

    const allCandidateIds = new Set<string>()
    const events = new Map<string, LightningRetrievalEvent>()

    for (const retrievalId of byRetrieval.keys()) {
      const ev = this.cortex.getLightningRetrievalEvent(retrievalId)
      if (!ev || !ev.queryEmbedding || ev.queryEmbedding.length !== dims.dEmb) continue
      if (ev.candidateIds.length < 2) continue
      events.set(retrievalId, ev)
      for (const id of ev.candidateIds) allCandidateIds.add(id)
    }

    const keys = this.cortex.getLightningKeys([...allCandidateIds])
    const expectedKeyLen = dims.nH * dims.dIdx

    const prepared: PreparedRetrieval[] = []
    for (const [retrievalId, ev] of events) {
      const candidateKeys: Float32Array[] = []
      let allKeysPresent = true
      for (const id of ev.candidateIds) {
        const k = keys.get(id)
        if (!k || k.length !== expectedKeyLen) {
          allKeysPresent = false
          break
        }
        candidateKeys.push(k)
      }
      if (!allKeysPresent) continue

      const labelByCandidate = new Map<string, number>()
      const tripleList = byRetrieval.get(retrievalId)!
      for (const t of tripleList) {
        labelByCandidate.set(t.candidateId, this.labelToFloat(t.label, t.weight))
      }

      const labels = new Float32Array(ev.candidateIds.length)
      let positiveCount = 0
      for (let i = 0; i < ev.candidateIds.length; i++) {
        const v = labelByCandidate.get(ev.candidateIds[i]) ?? 0
        labels[i] = v
        if (v > 0) positiveCount++
      }
      if (positiveCount === 0) continue

      prepared.push({
        retrievalId,
        request: { queryEmb: ev.queryEmbedding!, candidateKeys, labels },
        triples: tripleList.length,
      })
    }

    return prepared
  }

  private labelToFloat(label: RetrievalLabelTriple['label'], weight: number): number {
    switch (label) {
      case 'used': return 1.0 * weight
      case 'should_have_been_retrieved': return 1.0 * weight
      case 'contradicted': return -0.5 * weight
      case 'ignored': return 0
      default: return 0
    }
  }

  private meanLoss(params: IndexerParams, dims: IndexerDims, prepared: PreparedRetrieval[]): number {
    if (prepared.length === 0) return 0
    let sum = 0
    for (const p of prepared) {
      const result = computeRetrievalLoss(params, dims, p.request)
      sum += result.loss
    }
    return sum / prepared.length
  }

  private accumulateBatchGradients(
    batch: PreparedRetrieval[],
    indexerParams: IndexerParams,
    dims: IndexerDims,
  ): number {
    if (!this.params) return 0

    const accumW: IndexerGradients = {
      wDq: new Float32Array(indexerParams.wDq.length),
      wIuq: new Float32Array(indexerParams.wIuq.length),
      wI: new Float32Array(indexerParams.wI.length),
    }

    let lossSum = 0
    let lossCount = 0
    for (const p of batch) {
      try {
        const result = computeRetrievalLoss(indexerParams, dims, p.request)
        lossSum += result.loss
        lossCount++
        for (let i = 0; i < accumW.wDq.length; i++) accumW.wDq[i] += result.gradients.wDq[i]
        for (let i = 0; i < accumW.wIuq.length; i++) accumW.wIuq[i] += result.gradients.wIuq[i]
        for (let i = 0; i < accumW.wI.length; i++) accumW.wI[i] += result.gradients.wI[i]
      } catch {
        // Skip this retrieval if its loss/gradient computation fails
      }
    }

    const scale = 1.0 / batch.length
    if (scale <= 0) return 0

    const dWDq = this.params[0].grad
    const dWIuq = this.params[1].grad
    const dWI = this.params[2].grad
    for (let i = 0; i < accumW.wDq.length; i++) dWDq[i] += accumW.wDq[i] * scale
    for (let i = 0; i < accumW.wIuq.length; i++) dWIuq[i] += accumW.wIuq[i] * scale
    for (let i = 0; i < accumW.wI.length; i++) dWI[i] += accumW.wI[i] * scale

    return lossCount > 0 ? lossSum / lossCount : 0
  }
}
