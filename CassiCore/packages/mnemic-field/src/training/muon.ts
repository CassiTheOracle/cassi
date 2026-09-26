import { newtonSchulz } from './newton-schulz.js'

// Muon optimizer (Moonshot/Jordan et al., adopted by DeepSeek V4) plus AdamW fallback.
//
// Muon updates 2D matrix parameters by:
//   1. Aggregating gradient + momentum into M_t (Nesterov by default)
//   2. Mapping M_t through Newton-Schulz to its polar orthogonal factor U_t
//   3. Stepping W_t = W_{t-1} - η · √(max/min) · U_t  - η · weightDecay · W_{t-1}
//
// 1D vector parameters fall back to AdamW because NS is undefined on rank-1 inputs.

export type ParamKind = 'matrix' | 'vector'

export interface MatrixParam {
  kind: 'matrix'
  name: string
  weight: Float32Array  // length rows*cols
  rows: number
  cols: number
  grad: Float32Array
  momentum: Float32Array  // M for Muon
}

export interface VectorParam {
  kind: 'vector'
  name: string
  weight: Float32Array
  grad: Float32Array
  m: Float32Array  // AdamW first moment
  v: Float32Array  // AdamW second moment
}

export type OptParam = MatrixParam | VectorParam

export interface MuonOptions {
  learningRate: number       // base lr (Muon)
  beta: number               // momentum coefficient (typical 0.95)
  weightDecay: number        // typical 0.01
  nesterov: boolean          // default true
  scaleByShape: boolean      // default true; multiply per-param lr by √(max(m,n)/min(m,n))
}

export interface AdamWOptions {
  learningRate: number       // typical 3e-4
  beta1: number              // typical 0.9
  beta2: number              // typical 0.999
  eps: number                // typical 1e-8
  weightDecay: number        // typical 0.01
}

export interface OptimizerOptions {
  muon: MuonOptions
  adamw: AdamWOptions
  step: number               // current step count, used for AdamW bias correction
}

export const DEFAULT_MUON_OPTIONS: MuonOptions = {
  learningRate: 0.02,
  beta: 0.95,
  weightDecay: 0.01,
  nesterov: true,
  scaleByShape: true,
}

export const DEFAULT_ADAMW_OPTIONS: AdamWOptions = {
  learningRate: 3e-4,
  beta1: 0.9,
  beta2: 0.999,
  eps: 1e-8,
  weightDecay: 0.01,
}

export interface ParamUpdateStats {
  name: string
  kind: ParamKind
  gradNorm: number
  stepNorm: number
  weightNorm: number
}

export interface OptimizerStepResult {
  perParam: ParamUpdateStats[]
  totalGradNorm: number
  totalStepNorm: number
}

export function optimizerStep(params: OptParam[], opts: OptimizerOptions): OptimizerStepResult {
  const stats: ParamUpdateStats[] = []
  let totalGradSq = 0
  let totalStepSq = 0

  for (const p of params) {
    const s = p.kind === 'matrix' ? muonUpdate(p, opts.muon) : adamwUpdate(p, opts.adamw, opts.step)
    stats.push(s)
    totalGradSq += s.gradNorm * s.gradNorm
    totalStepSq += s.stepNorm * s.stepNorm
  }

  return {
    perParam: stats,
    totalGradNorm: Math.sqrt(totalGradSq),
    totalStepNorm: Math.sqrt(totalStepSq),
  }
}

function muonUpdate(p: MatrixParam, opts: MuonOptions): ParamUpdateStats {
  const { rows, cols, weight, grad, momentum } = p
  const beta = opts.beta

  for (let i = 0; i < momentum.length; i++) {
    momentum[i] = beta * momentum[i] + grad[i]
  }

  const directionInput = opts.nesterov ? new Float32Array(grad.length) : momentum
  if (opts.nesterov) {
    for (let i = 0; i < grad.length; i++) {
      directionInput[i] = grad[i] + beta * momentum[i]
    }
  }

  const { output: U } = newtonSchulz(directionInput, rows, cols)

  let lr = opts.learningRate
  if (opts.scaleByShape) {
    const maxDim = Math.max(rows, cols)
    const minDim = Math.max(1, Math.min(rows, cols))
    lr *= Math.sqrt(maxDim / minDim)
  }

  let stepSq = 0
  let weightSq = 0
  for (let i = 0; i < weight.length; i++) {
    const decay = opts.weightDecay * weight[i]
    const step = lr * (U[i] + decay)
    weight[i] -= step
    stepSq += step * step
    weightSq += weight[i] * weight[i]
  }

  let gradSq = 0
  for (let i = 0; i < grad.length; i++) gradSq += grad[i] * grad[i]

  return {
    name: p.name,
    kind: 'matrix',
    gradNorm: Math.sqrt(gradSq),
    stepNorm: Math.sqrt(stepSq),
    weightNorm: Math.sqrt(weightSq),
  }
}

function adamwUpdate(p: VectorParam, opts: AdamWOptions, step: number): ParamUpdateStats {
  const { weight, grad, m, v } = p
  const { beta1, beta2, eps, learningRate, weightDecay } = opts

  const t = Math.max(1, step)
  const biasCorr1 = 1 - Math.pow(beta1, t)
  const biasCorr2 = 1 - Math.pow(beta2, t)

  let stepSq = 0
  let weightSq = 0
  for (let i = 0; i < weight.length; i++) {
    m[i] = beta1 * m[i] + (1 - beta1) * grad[i]
    v[i] = beta2 * v[i] + (1 - beta2) * grad[i] * grad[i]
    const mHat = m[i] / biasCorr1
    const vHat = v[i] / biasCorr2
    const decay = weightDecay * weight[i]
    const update = learningRate * (mHat / (Math.sqrt(vHat) + eps) + decay)
    weight[i] -= update
    stepSq += update * update
    weightSq += weight[i] * weight[i]
  }

  let gradSq = 0
  for (let i = 0; i < grad.length; i++) gradSq += grad[i] * grad[i]

  return {
    name: p.name,
    kind: 'vector',
    gradNorm: Math.sqrt(gradSq),
    stepNorm: Math.sqrt(stepSq),
    weightNorm: Math.sqrt(weightSq),
  }
}

export function makeMatrixParam(name: string, rows: number, cols: number, init?: Float32Array): MatrixParam {
  const len = rows * cols
  const weight = init ? Float32Array.from(init) : new Float32Array(len)
  if (init && init.length !== len) {
    throw new Error(`makeMatrixParam(${name}): init length ${init.length} != rows*cols (${len})`)
  }
  return {
    kind: 'matrix',
    name,
    weight,
    rows,
    cols,
    grad: new Float32Array(len),
    momentum: new Float32Array(len),
  }
}

export function makeVectorParam(name: string, length: number, init?: Float32Array): VectorParam {
  const weight = init ? Float32Array.from(init) : new Float32Array(length)
  if (init && init.length !== length) {
    throw new Error(`makeVectorParam(${name}): init length ${init.length} != ${length}`)
  }
  return {
    kind: 'vector',
    name,
    weight,
    grad: new Float32Array(length),
    m: new Float32Array(length),
    v: new Float32Array(length),
  }
}

export function zeroGradients(params: OptParam[]): void {
  for (const p of params) p.grad.fill(0)
}
