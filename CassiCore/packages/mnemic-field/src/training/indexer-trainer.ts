import type { ILogger } from '../../../../types/interfaces.js'
import type { Cortex } from '../cortex.js'
import type { LightningIndexer } from '../lightning-indexer.js'
import type { LightningRetrievalEvent } from '../types.js'
import type { RetrievalLabelTriple } from '../../reverie/retrieval-labeler-types.js'
import {
  type RetrievalRequest,
  type IndexerDims,
  type IndexerParams,
  type IndexerGradients,
  computeRetrievalLoss,
} from './retrieval-loss.js'

export interface IndexerTrainerOptions {
  lr: number
  batchSize: number
  maxEpochs: number
  tolerance: number
  seed: number
  pendingLimit?: number
}

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
}

interface PreparedRetrieval {
  retrievalId: string
  request: RetrievalRequest
  triples: number
}

const DEFAULT_PENDING_LIMIT = 1024

export class IndexerTrainer {
  constructor(
    private readonly cortex: Cortex,
    private readonly indexer: LightningIndexer,
    private readonly logger: ILogger,
    private readonly opts: IndexerTrainerOptions,
  ) {}

  async runOnce(): Promise<RunOnceResult> {
    const limit = this.opts.pendingLimit ?? DEFAULT_PENDING_LIMIT
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
    if (prepared.length < this.opts.batchSize) {
      return {
        skipped: true,
        reason: `insufficient training data: ${prepared.length} valid retrievals < batchSize ${this.opts.batchSize}`,
      }
    }

    const params: IndexerParams = {
      wDq: new Float32Array(global.wDq),
      wIuq: new Float32Array(global.wIuq),
      wI: new Float32Array(global.wI),
    }

    const initialLoss = this.meanLoss(params, dims, prepared)

    const rng = this.makeRng(this.opts.seed)
    let prevLoss = initialLoss
    let epochsRun = 0
    let finalLoss = initialLoss

    for (let epoch = 0; epoch < this.opts.maxEpochs; epoch++) {
      this.shuffleInPlace(prepared, rng)
      for (let i = 0; i < prepared.length; i += this.opts.batchSize) {
        const batch = prepared.slice(i, Math.min(i + this.opts.batchSize, prepared.length))
        if (batch.length === 0) break
        this.applyBatchStep(params, dims, batch)
      }
      epochsRun++
      const epochLoss = this.meanLoss(params, dims, prepared)
      finalLoss = epochLoss
      if (Math.abs(prevLoss - epochLoss) < this.opts.tolerance) break
      prevLoss = epochLoss
    }

    this.cortex.setLightningGlobal({
      wDq: params.wDq,
      wIuq: params.wIuq,
      wI: params.wI,
      dEmb: dims.dEmb,
      dC: dims.dC,
      nH: dims.nH,
      dIdx: dims.dIdx,
      version: global.version + 1,
    })

    const retrievalIds = prepared.map(p => p.retrievalId)
    this.cortex.markIndexerTrainingRequestsProcessed(retrievalIds)

    const triplesProcessed = prepared.reduce((s, p) => s + p.triples, 0)

    this.logger.info('IndexerTrainer.runOnce: trained', {
      retrievals: prepared.length,
      triplesProcessed,
      initialLoss,
      finalLoss,
      epochsRun,
      versionBefore: global.version,
      versionAfter: global.version + 1,
    })

    return {
      skipped: false,
      initialLoss,
      finalLoss,
      epochsRun,
      retrievalsTrained: prepared.length,
      triplesProcessed,
      versionBefore: global.version,
      versionAfter: global.version + 1,
    }
  }

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

  private applyBatchStep(params: IndexerParams, dims: IndexerDims, batch: PreparedRetrieval[]): void {
    const accum: IndexerGradients = {
      wDq: new Float32Array(params.wDq.length),
      wIuq: new Float32Array(params.wIuq.length),
      wI: new Float32Array(params.wI.length),
    }
    for (const p of batch) {
      const result = computeRetrievalLoss(params, dims, p.request)
      for (let i = 0; i < accum.wDq.length; i++) accum.wDq[i] += result.gradients.wDq[i]
      for (let i = 0; i < accum.wIuq.length; i++) accum.wIuq[i] += result.gradients.wIuq[i]
      for (let i = 0; i < accum.wI.length; i++) accum.wI[i] += result.gradients.wI[i]
    }
    const scale = this.opts.lr / batch.length
    for (let i = 0; i < params.wDq.length; i++) params.wDq[i] -= scale * accum.wDq[i]
    for (let i = 0; i < params.wIuq.length; i++) params.wIuq[i] -= scale * accum.wIuq[i]
    for (let i = 0; i < params.wI.length; i++) params.wI[i] -= scale * accum.wI[i]
  }

  private shuffleInPlace<T>(arr: T[], rng: () => number): void {
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1))
      const tmp = arr[i]
      arr[i] = arr[j]
      arr[j] = tmp
    }
  }

  private makeRng(seed: number): () => number {
    let a = seed >>> 0
    return () => {
      a = (a + 0x6d2b79f5) >>> 0
      let t = a
      t = Math.imul(t ^ (t >>> 15), t | 1)
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296
    }
  }
}
