/**
 * Listwise softmax cross-entropy loss for the Lightning Indexer.
 *
 * Trainable parameters: wDq (D_c × D_emb), wIuq ((nH·D_idx) × D_c), wI (nH).
 * Frozen during training: per-engram keys K_e (deterministic from embeddings).
 *
 * Forward pass (mirrors LightningIndexer.projectToIndex + scoreCandidate):
 *   q_c_pre = wDq · q_emb                                  // (D_c,)
 *   q_c    = relu(q_c_pre)                                 // (D_c,)   ← hidden ReLU
 *   q_h    = wIuq · q_c, reshaped to (nH × D_idx)          // (nH × D_idx)
 *   pre_i,h = sum_d q_h[h,d] · K_e[i, h, d]                // (N × nH)
 *   act_i,h = relu(pre_i,h)                                // (N × nH) ← per-head ReLU
 *   score_i = sum_h wI[h] · act_i,h                        // (N,)
 *
 * Loss:
 *   target_i  = (label_i + ε) / (sum_j label_j + N·ε)      // label smoothing
 *   softmax_i = exp(score_i - max_score) / Z               // stable softmax
 *   L         = -sum_i target_i · log(softmax_i)
 *
 * Backward pass derived in the source — checked numerically in tests.
 */

export interface IndexerDims {
  dEmb: number
  dC: number
  nH: number
  dIdx: number
}

export interface IndexerParams {
  wDq: Float32Array
  wIuq: Float32Array
  wI: Float32Array
}

export interface RetrievalRequest {
  queryEmb: Float32Array
  candidateKeys: Float32Array[]
  labels: Float32Array
}

export interface IndexerGradients {
  wDq: Float32Array
  wIuq: Float32Array
  wI: Float32Array
}

export interface LossResult {
  loss: number
  gradients: IndexerGradients
  predictions: Float32Array
  scores: Float32Array
}

export interface LossOptions {
  labelSmoothingEps?: number
  logProbClipMin?: number
}

const DEFAULT_EPS = 1e-3
const DEFAULT_LOG_CLIP = -50

export function computeIndexerScores(
  params: IndexerParams,
  dims: IndexerDims,
  queryEmb: Float32Array,
  candidateKeys: Float32Array[],
): Float32Array {
  const { dEmb, dC, nH, dIdx } = dims
  if (queryEmb.length !== dEmb) {
    throw new Error(`queryEmb length ${queryEmb.length} ≠ dEmb ${dEmb}`)
  }
  const { wDq, wIuq, wI } = params

  const qC = new Float32Array(dC)
  for (let j = 0; j < dC; j++) {
    let acc = 0
    for (let k = 0; k < dEmb; k++) acc += wDq[j * dEmb + k] * queryEmb[k]
    qC[j] = acc > 0 ? acc : 0
  }

  const qH = new Float32Array(nH * dIdx)
  for (let h = 0; h < nH; h++) {
    for (let d = 0; d < dIdx; d++) {
      let acc = 0
      for (let j = 0; j < dC; j++) {
        acc += wIuq[(h * dIdx + d) * dC + j] * qC[j]
      }
      qH[h * dIdx + d] = acc
    }
  }

  const N = candidateKeys.length
  const scores = new Float32Array(N)
  for (let i = 0; i < N; i++) {
    const Ke = candidateKeys[i]
    if (Ke.length !== nH * dIdx) {
      throw new Error(`candidateKeys[${i}] length ${Ke.length} ≠ nH·dIdx ${nH * dIdx}`)
    }
    let scoreI = 0
    for (let h = 0; h < nH; h++) {
      let pre = 0
      for (let d = 0; d < dIdx; d++) pre += qH[h * dIdx + d] * Ke[h * dIdx + d]
      if (pre > 0) scoreI += wI[h] * pre
    }
    scores[i] = scoreI
  }
  return scores
}

export function computeRetrievalLoss(
  params: IndexerParams,
  dims: IndexerDims,
  request: RetrievalRequest,
  options: LossOptions = {},
): LossResult {
  const { dEmb, dC, nH, dIdx } = dims
  const eps = options.labelSmoothingEps ?? DEFAULT_EPS
  const logClip = options.logProbClipMin ?? DEFAULT_LOG_CLIP
  const { wDq, wIuq, wI } = params
  const { queryEmb, candidateKeys, labels } = request
  const N = candidateKeys.length

  if (labels.length !== N) {
    throw new Error(`labels length ${labels.length} ≠ candidates ${N}`)
  }
  if (queryEmb.length !== dEmb) {
    throw new Error(`queryEmb length ${queryEmb.length} ≠ dEmb ${dEmb}`)
  }
  if (wDq.length !== dC * dEmb) {
    throw new Error(`wDq length ${wDq.length} ≠ dC·dEmb ${dC * dEmb}`)
  }
  if (wIuq.length !== nH * dIdx * dC) {
    throw new Error(`wIuq length ${wIuq.length} ≠ nH·dIdx·dC ${nH * dIdx * dC}`)
  }
  if (wI.length !== nH) {
    throw new Error(`wI length ${wI.length} ≠ nH ${nH}`)
  }

  const qCpre = new Float32Array(dC)
  const qC = new Float32Array(dC)
  for (let j = 0; j < dC; j++) {
    let acc = 0
    for (let k = 0; k < dEmb; k++) acc += wDq[j * dEmb + k] * queryEmb[k]
    qCpre[j] = acc
    qC[j] = acc > 0 ? acc : 0
  }

  const qH = new Float32Array(nH * dIdx)
  for (let h = 0; h < nH; h++) {
    for (let d = 0; d < dIdx; d++) {
      let acc = 0
      for (let j = 0; j < dC; j++) {
        acc += wIuq[(h * dIdx + d) * dC + j] * qC[j]
      }
      qH[h * dIdx + d] = acc
    }
  }

  const preRelu = new Float32Array(N * nH)
  const scores = new Float32Array(N)
  for (let i = 0; i < N; i++) {
    const Ke = candidateKeys[i]
    if (Ke.length !== nH * dIdx) {
      throw new Error(`candidateKeys[${i}] length ${Ke.length} ≠ nH·dIdx`)
    }
    let scoreI = 0
    for (let h = 0; h < nH; h++) {
      let pre = 0
      for (let d = 0; d < dIdx; d++) pre += qH[h * dIdx + d] * Ke[h * dIdx + d]
      preRelu[i * nH + h] = pre
      if (pre > 0) scoreI += wI[h] * pre
    }
    scores[i] = scoreI
  }

  let labelSum = 0
  for (let i = 0; i < N; i++) labelSum += labels[i]
  const targetDenom = labelSum + N * eps
  const targets = new Float32Array(N)
  for (let i = 0; i < N; i++) targets[i] = (labels[i] + eps) / targetDenom

  let maxScore = -Infinity
  for (let i = 0; i < N; i++) if (scores[i] > maxScore) maxScore = scores[i]
  let z = 0
  const expScores = new Float32Array(N)
  for (let i = 0; i < N; i++) {
    const e = Math.exp(scores[i] - maxScore)
    expScores[i] = e
    z += e
  }
  const predictions = new Float32Array(N)
  for (let i = 0; i < N; i++) predictions[i] = expScores[i] / z

  let loss = 0
  for (let i = 0; i < N; i++) {
    let logP = Math.log(predictions[i])
    if (!Number.isFinite(logP) || logP < logClip) logP = logClip
    loss += -targets[i] * logP
  }

  const dScores = new Float32Array(N)
  for (let i = 0; i < N; i++) dScores[i] = predictions[i] - targets[i]

  const gWi = new Float32Array(nH)
  const dQh = new Float32Array(nH * dIdx)
  for (let i = 0; i < N; i++) {
    const Ke = candidateKeys[i]
    const dsI = dScores[i]
    for (let h = 0; h < nH; h++) {
      const pre = preRelu[i * nH + h]
      if (pre <= 0) continue
      gWi[h] += dsI * pre
      const dActIH = dsI * wI[h]
      for (let d = 0; d < dIdx; d++) {
        dQh[h * dIdx + d] += dActIH * Ke[h * dIdx + d]
      }
    }
  }

  const gWiuq = new Float32Array(nH * dIdx * dC)
  const dQc = new Float32Array(dC)
  for (let h = 0; h < nH; h++) {
    for (let d = 0; d < dIdx; d++) {
      const dQhHd = dQh[h * dIdx + d]
      if (dQhHd === 0) continue
      const rowOffset = (h * dIdx + d) * dC
      for (let j = 0; j < dC; j++) {
        gWiuq[rowOffset + j] += dQhHd * qC[j]
        dQc[j] += dQhHd * wIuq[rowOffset + j]
      }
    }
  }

  const gWdq = new Float32Array(dC * dEmb)
  for (let j = 0; j < dC; j++) {
    if (qCpre[j] <= 0) continue
    const dQcJ = dQc[j]
    if (dQcJ === 0) continue
    const rowOffset = j * dEmb
    for (let k = 0; k < dEmb; k++) {
      gWdq[rowOffset + k] = dQcJ * queryEmb[k]
    }
  }

  return {
    loss,
    gradients: { wDq: gWdq, wIuq: gWiuq, wI: gWi },
    predictions,
    scores,
  }
}

export function copyParams(p: IndexerParams): IndexerParams {
  return {
    wDq: new Float32Array(p.wDq),
    wIuq: new Float32Array(p.wIuq),
    wI: new Float32Array(p.wI),
  }
}
