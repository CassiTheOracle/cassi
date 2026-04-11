/**
 * UMAP (Uniform Manifold Approximation and Projection) for reducing
 * high-dimensional embedding vectors to 2D (X, Y) coordinates.
 *
 * Zero external dependencies — implements the full UMAP pipeline:
 * k-NN graph → fuzzy simplicial set → PCA initialization → SGD layout.
 *
 * Preserves local neighborhood structure far better than PCA,
 * producing tighter semantic clusters for kindling seeding.
 *
 * Reference: McInnes, Healy, Melville (2018). "UMAP: Uniform Manifold
 * Approximation and Projection for Dimension Reduction."
 */

export interface ProjectionResult {
  x: number
  y: number
}

/**
 * Cached state for online projection of new engrams into existing topology.
 * Stores pre-normalized reference embeddings and their 2D positions so
 * projectSingle can find nearest neighbors without a full field scan.
 */
export interface ProjectionState {
  referenceEmbeddings: number[][]  // pre-normalized by buildProjectionState
  referencePositions: ProjectionResult[]
  nNeighbors: number
}

export interface UMAPOptions {
  nNeighbors?: number
  minDist?: number
  spread?: number
  nEpochs?: number
  learningRate?: number
  negativeSampleRate?: number
  seed?: number
}

export const UMAP_DEFAULTS = {
  nNeighbors: 15,
  minDist: 0.1,
  spread: 1.0,
  nEpochs: 200,
  learningRate: 1.0,
  negativeSampleRate: 5,
  seed: 42,
} as const

const MAX_REFERENCE_SAMPLES = 5000

/**
 * Normalize positions to fit within [-spread, spread] range.
 * Centers on mean and scales so the max absolute coordinate equals spread.
 */
function normalizeToSpread(positions: ProjectionResult[], spread: number): void {
  if (positions.length === 0) return

  // Center
  let sumX = 0, sumY = 0
  for (const p of positions) {
    sumX += p.x
    sumY += p.y
  }
  const meanX = sumX / positions.length
  const meanY = sumY / positions.length

  for (const p of positions) {
    p.x -= meanX
    p.y -= meanY
  }

  // Scale
  let maxCoord = 1e-8
  for (const p of positions) {
    const ax = Math.abs(p.x), ay = Math.abs(p.y)
    if (ax > maxCoord) maxCoord = ax
    if (ay > maxCoord) maxCoord = ay
  }
  const factor = spread / maxCoord
  if (Math.abs(factor - 1.0) > 0.001) {
    for (const p of positions) {
      p.x *= factor
      p.y *= factor
    }
  }
}

/**
 * Project a set of high-dimensional embedding vectors to 2D using UMAP.
 * Returns one {x, y} per input vector, in the same order.
 *
 * For n < 4, falls back to PCA (UMAP needs a minimum neighborhood size).
 */
export function projectTo2D(vectors: number[][], options?: UMAPOptions): ProjectionResult[] {
  const n = vectors.length
  if (n === 0) return []
  if (n === 1) return [{ x: 0, y: 0 }]
  if (n < 4) return pcaFallback(vectors)

  const opts = resolveOptions(options)
  const k = Math.min(opts.nNeighbors, n - 1)

  const normed = normalizeRows(vectors)
  const { indices, distances } = buildKNNGraph(normed, k)
  const { sigmas, rhos } = smoothKNNDistances(distances, k)
  const edges = buildFuzzySimplicialSet(indices, distances, sigmas, rhos, n)

  const positions = pcaInitialize(vectors, n, opts.seed, opts.spread)
  const { a, b } = findAB(opts.spread, opts.minDist)

  optimizeLayout(positions, edges, n, {
    nEpochs: opts.nEpochs,
    learningRate: opts.learningRate,
    negativeSampleRate: opts.negativeSampleRate,
    a, b,
    seed: opts.seed,
  })

  // Normalize final positions to the spread scale.
  // The SGD optimization can drift — ensure the output fits in [-spread, spread].
  normalizeToSpread(positions, opts.spread)

  return positions
}

/**
 * Project a single new vector into existing topology using cached state.
 * Finds k nearest neighbors among reference embeddings and places the
 * new point at the fuzzy-weighted centroid of their 2D positions.
 *
 * This is intentionally approximate — co-activation drift corrects
 * placement over time, so a good neighborhood estimate is sufficient.
 */
export function projectSingle(vector: number[], state: ProjectionState): ProjectionResult {
  const { referenceEmbeddings, referencePositions, nNeighbors } = state
  if (referenceEmbeddings.length === 0) return { x: 0, y: 0 }
  if (referenceEmbeddings.length === 1) return { ...referencePositions[0] }

  const k = Math.min(nNeighbors, referenceEmbeddings.length)
  const normedVec = normalizeVec(vector)
  const nRef = referenceEmbeddings.length

  const distBuf = new Float64Array(nRef)
  const idxBuf = new Uint32Array(nRef)
  for (let i = 0; i < nRef; i++) {
    distBuf[i] = Math.max(0, 1 - dot(normedVec, referenceEmbeddings[i]))
    idxBuf[i] = i
  }
  partialSelectionSort(distBuf, idxBuf, nRef, k)

  const topKDists = new Array<number>(k)
  const topKIdxs = new Array<number>(k)
  for (let i = 0; i < k; i++) {
    topKDists[i] = distBuf[i]
    topKIdxs[i] = idxBuf[i]
  }

  const rho = topKDists[0]
  const sigma = findSigmaForPoint(topKDists, rho, Math.log2(k))

  let sumX = 0, sumY = 0, sumW = 0
  for (let i = 0; i < k; i++) {
    const adjusted = Math.max(0, topKDists[i] - rho)
    const w = sigma > 1e-10 ? Math.exp(-adjusted / sigma) : 1.0
    const pos = referencePositions[topKIdxs[i]]
    sumX += w * pos.x
    sumY += w * pos.y
    sumW += w
  }

  return sumW > 0 ? { x: sumX / sumW, y: sumY / sumW } : { x: 0, y: 0 }
}

/**
 * Build a ProjectionState from existing embeddings and their 2D positions.
 * Pre-normalizes embeddings so projectSingle only normalizes the query.
 * For large fields, samples uniformly to keep the state under MAX_REFERENCE_SAMPLES.
 */
export function buildProjectionState(
  vectors: number[][],
  positions: ProjectionResult[],
  options?: Pick<UMAPOptions, 'nNeighbors'>,
): ProjectionState {
  const nNeighbors = options?.nNeighbors ?? UMAP_DEFAULTS.nNeighbors

  if (vectors.length <= MAX_REFERENCE_SAMPLES) {
    return { referenceEmbeddings: normalizeRows(vectors), referencePositions: positions, nNeighbors }
  }

  const step = vectors.length / MAX_REFERENCE_SAMPLES
  const sampledEmb: number[][] = []
  const sampledPos: ProjectionResult[] = []
  for (let i = 0; i < MAX_REFERENCE_SAMPLES; i++) {
    const idx = Math.min(Math.floor(i * step), vectors.length - 1)
    sampledEmb.push(normalizeVec(vectors[idx]))
    sampledPos.push(positions[idx])
  }

  return { referenceEmbeddings: sampledEmb, referencePositions: sampledPos, nNeighbors }
}

/**
 * Brute-force k-nearest-neighbor graph using cosine distance on
 * pre-normalized vectors. O(n² × d) — practical up to ~10K vectors
 * for periodic consolidation. NN-Descent is the scaling path for 50K+.
 */
function buildKNNGraph(normed: number[][], k: number): {
  indices: number[][]
  distances: number[][]
} {
  const n = normed.length
  const resultIndices: number[][] = new Array(n)
  const resultDistances: number[][] = new Array(n)

  const distBuf = new Float64Array(n)
  const idxBuf = new Uint32Array(n)

  for (let i = 0; i < n; i++) {
    let count = 0
    for (let j = 0; j < n; j++) {
      if (j === i) continue
      distBuf[count] = Math.max(0, 1 - dot(normed[i], normed[j]))
      idxBuf[count] = j
      count++
    }

    partialSelectionSort(distBuf, idxBuf, count, k)

    resultIndices[i] = Array.from(idxBuf.subarray(0, k))
    resultDistances[i] = Array.from(distBuf.subarray(0, k))
  }

  return { indices: resultIndices, distances: resultDistances }
}

/**
 * For each point, fit σ_i so that the fuzzy neighbor sum equals log₂(k).
 * ρ_i is the distance to the nearest neighbor (the "local connectivity" term).
 */
function smoothKNNDistances(knnDistances: number[][], nNeighbors: number): {
  sigmas: number[]
  rhos: number[]
} {
  const n = knnDistances.length
  const target = Math.log2(nNeighbors)
  const sigmas = new Array<number>(n)
  const rhos = new Array<number>(n)

  for (let i = 0; i < n; i++) {
    rhos[i] = knnDistances[i][0]
    sigmas[i] = findSigmaForPoint(knnDistances[i], rhos[i], target)
  }

  return { sigmas, rhos }
}

function findSigmaForPoint(distances: number[], rho: number, target: number): number {
  let lo = 1e-8, hi = 1000, mid = 1.0

  for (let iter = 0; iter < 64; iter++) {
    mid = (lo + hi) / 2
    let sum = 0
    for (const d of distances) {
      sum += Math.exp(-Math.max(0, d - rho) / mid)
    }
    if (Math.abs(sum - target) < 1e-5) break
    if (sum > target) hi = mid
    else lo = mid
  }

  return mid
}

interface Edge {
  source: number
  target: number
  weight: number
}

/**
 * Build the symmetrized fuzzy simplicial set from the k-NN graph.
 * Directed weights: w(i|j) = exp(-(d(i,j) - ρ_i) / σ_i)
 * Symmetrized: W(i,j) = w(i|j) + w(j|i) - w(i|j)·w(j|i)
 */
function buildFuzzySimplicialSet(
  knnIndices: number[][],
  knnDistances: number[][],
  sigmas: number[],
  rhos: number[],
  n: number,
): Edge[] {
  const directed = new Map<number, number>()

  for (let i = 0; i < n; i++) {
    for (let ki = 0; ki < knnIndices[i].length; ki++) {
      const j = knnIndices[i][ki]
      const d = knnDistances[i][ki]
      const adjusted = Math.max(0, d - rhos[i])
      const w = sigmas[i] > 1e-10 ? Math.exp(-adjusted / sigmas[i]) : 1.0
      directed.set(i * n + j, w)
    }
  }

  const edges: Edge[] = []
  const seen = new Set<number>()

  for (const [key] of directed) {
    const i = Math.floor(key / n)
    const j = key % n
    const lo = Math.min(i, j), hi = Math.max(i, j)
    const canonical = lo * n + hi
    if (seen.has(canonical)) continue
    seen.add(canonical)

    const wij = directed.get(i * n + j) ?? 0
    const wji = directed.get(j * n + i) ?? 0
    const sym = wij + wji - wij * wji
    if (sym > 1e-8) {
      edges.push({ source: lo, target: hi, weight: sym })
    }
  }

  return edges
}

/**
 * Initialize 2D positions via PCA, scaled to a small range (~10/√n).
 * PCA gives a stable global structure for UMAP's SGD to refine.
 */
function pcaInitialize(vectors: number[][], n: number, seed: number, spread = 1.0): ProjectionResult[] {
  const dim = vectors[0].length
  const mean = computeMean(vectors, dim)
  const centered = vectors.map(v => v.map((x, i) => x - mean[i]))

  const pc1 = powerIteration(centered, dim)
  const pc2 = powerIterationDeflated(centered, dim, pc1)

  const positions = centered.map(v => ({
    x: dot(v, pc1),
    y: dot(v, pc2),
  }))

  // Scale PCA output to roughly match the UMAP spread parameter.
  // The old formula (10 / √n) collapsed large datasets — at 124K points
  // it gave a scale of 0.028, crushing everything into a tiny ball.
  // Instead, we normalize to [-spread, spread] so the SGD starts in
  // the right range regardless of dataset size.
  let maxCoord = 1e-8
  for (const p of positions) {
    const ax = Math.abs(p.x), ay = Math.abs(p.y)
    if (ax > maxCoord) maxCoord = ax
    if (ay > maxCoord) maxCoord = ay
  }
  const factor = spread / maxCoord

  const rng = new PRNG(seed + 2000)
  for (const p of positions) {
    p.x = p.x * factor + (rng.next() - 0.5) * 0.001
    p.y = p.y * factor + (rng.next() - 0.5) * 0.001
  }

  return positions
}

/**
 * PCA fallback for n < 4 where UMAP can't form meaningful neighborhoods.
 */
function pcaFallback(vectors: number[][]): ProjectionResult[] {
  const dim = vectors[0].length
  const mean = computeMean(vectors, dim)
  const centered = vectors.map(v => v.map((x, i) => x - mean[i]))
  const pc1 = powerIteration(centered, dim)
  const pc2 = powerIterationDeflated(centered, dim, pc1)

  return centered.map(v => ({ x: dot(v, pc1), y: dot(v, pc2) }))
}

interface LayoutParams {
  nEpochs: number
  learningRate: number
  negativeSampleRate: number
  a: number
  b: number
  seed: number
}

/**
 * Optimize the 2D layout using stochastic gradient descent.
 * Attractive forces pull connected points together (proportional to
 * fuzzy edge weight). Repulsive forces push random unconnected points
 * apart (negative sampling). Mutates positions in place.
 */
function optimizeLayout(
  positions: ProjectionResult[],
  edges: Edge[],
  n: number,
  params: LayoutParams,
): void {
  if (edges.length === 0 || n < 2) return

  const { nEpochs, learningRate, negativeSampleRate, a, b, seed } = params
  const rng = new PRNG(seed + 1000)

  let maxWeight = 0
  for (const e of edges) {
    if (e.weight > maxWeight) maxWeight = e.weight
  }

  const nEdges = edges.length
  const epochsPerSample = new Float64Array(nEdges)
  const nextSample = new Float64Array(nEdges)
  for (let i = 0; i < nEdges; i++) {
    epochsPerSample[i] = edges[i].weight > 0 ? maxWeight / edges[i].weight : nEpochs + 1
    nextSample[i] = epochsPerSample[i]
  }

  const bMinus1 = b - 1

  for (let epoch = 0; epoch < nEpochs; epoch++) {
    const alpha = learningRate * (1 - epoch / nEpochs)

    for (let e = 0; e < nEdges; e++) {
      if (nextSample[e] > epoch) continue
      nextSample[e] += epochsPerSample[e]

      const pi = positions[edges[e].source]
      const pj = positions[edges[e].target]

      const dx = pi.x - pj.x
      const dy = pi.y - pj.y
      const distSq = Math.max(dx * dx + dy * dy, 1e-8)

      const powDistB = Math.pow(distSq, b)
      const gradCoeff = (-2 * a * b * Math.pow(distSq, bMinus1)) / (1 + a * powDistB)

      const gx = clamp(gradCoeff * dx)
      const gy = clamp(gradCoeff * dy)

      pi.x += alpha * gx
      pi.y += alpha * gy
      pj.x -= alpha * gx
      pj.y -= alpha * gy

      const src = edges[e].source
      for (let neg = 0; neg < negativeSampleRate; neg++) {
        const k = rng.nextInt(n)
        if (k === src) continue

        const pk = positions[k]
        const ndx = pi.x - pk.x
        const ndy = pi.y - pk.y
        const nDistSq = Math.max(ndx * ndx + ndy * ndy, 1e-8)

        const nPowDistB = Math.pow(nDistSq, b)
        const nGradCoeff = (2 * b) / ((0.001 + nDistSq) * (1 + a * nPowDistB))

        pi.x += alpha * clamp(nGradCoeff * ndx)
        pi.y += alpha * clamp(nGradCoeff * ndy)
      }
    }
  }
}

/**
 * Find the a, b parameters for UMAP's smooth approximation curve:
 *   φ(d) = 1 / (1 + a·d^(2b))
 *
 * This curve approximates the piecewise target:
 *   ψ(d) = 1 if d ≤ minDist, else exp(-(d - minDist) / spread)
 *
 * Uses a reference-point constraint to derive a from b, then sweeps
 * b to minimize least-squares error against the target curve.
 */
function findAB(spread: number, minDist: number): { a: number; b: number } {
  const refD = minDist + spread
  const refTarget = Math.exp(-1)
  const maxD = 3 * spread + minDist
  const nSamples = 100

  let bestA = 1.929, bestB = 0.7915, bestLoss = Infinity

  for (let bi = 10; bi <= 200; bi++) {
    const b = bi * 0.01
    const denom = Math.pow(refD, 2 * b)
    if (denom < 1e-20) continue
    const a = (1 / refTarget - 1) / denom
    if (a <= 0 || !isFinite(a)) continue

    let loss = 0
    for (let si = 1; si <= nSamples; si++) {
      const d = (si / nSamples) * maxD
      const target = d <= minDist ? 1.0 : Math.exp(-(d - minDist) / spread)
      const pred = 1 / (1 + a * Math.pow(d, 2 * b))
      const err = pred - target
      loss += err * err
    }

    if (loss < bestLoss) {
      bestLoss = loss
      bestA = a
      bestB = b
    }
  }

  return { a: bestA, b: bestB }
}

function dot(a: number[], b: number[]): number {
  let s = 0
  for (let i = 0; i < a.length; i++) s += a[i] * b[i]
  return s
}

function normalizeVec(v: number[]): number[] {
  const n = Math.sqrt(dot(v, v))
  if (n < 1e-10) return v
  return v.map(x => x / n)
}

function normalizeRows(vectors: number[][]): number[][] {
  return vectors.map(normalizeVec)
}

function computeMean(vectors: number[][], dim: number): number[] {
  const mean = new Array<number>(dim).fill(0)
  for (const v of vectors) {
    for (let i = 0; i < dim; i++) mean[i] += v[i]
  }
  const n = vectors.length
  for (let i = 0; i < dim; i++) mean[i] /= n
  return mean
}

/**
 * Power iteration for the dominant eigenvector of X^T X.
 * Finds the first principal component without forming the full covariance matrix.
 */
function powerIteration(centered: number[][], dim: number, maxIter = 100, tol = 1e-8): number[] {
  let v = deterministicUnitVector(dim)

  for (let iter = 0; iter < maxIter; iter++) {
    const proj = centered.map(row => dot(row, v))
    const newV = new Array<number>(dim).fill(0)
    for (let i = 0; i < centered.length; i++) {
      const s = proj[i]
      for (let j = 0; j < dim; j++) newV[j] += centered[i][j] * s
    }

    const normalized = normalizeVec(newV)
    let change = 0
    for (let i = 0; i < dim; i++) change += (normalized[i] - v[i]) ** 2
    change = Math.sqrt(change)

    v = normalized
    if (change < tol) break
  }

  return v
}

function powerIterationDeflated(centered: number[][], dim: number, pc1: number[]): number[] {
  const deflated = centered.map(row => {
    const p = dot(row, pc1)
    return row.map((v, i) => v - p * pc1[i])
  })
  return powerIteration(deflated, dim)
}

function deterministicUnitVector(dim: number): number[] {
  const v = new Array<number>(dim)
  let seed = 42 + dim
  for (let i = 0; i < dim; i++) {
    seed = (seed * 1664525 + 1013904223) & 0x7fffffff
    v[i] = (seed / 0x7fffffff) * 2 - 1
  }
  return normalizeVec(v)
}

function clamp(val: number, limit = 4): number {
  return val < -limit ? -limit : val > limit ? limit : val
}

/**
 * In-place partial sort: after return, the k smallest values
 * occupy positions [0..k) in both buffers (sorted ascending).
 */
function partialSelectionSort(
  dists: Float64Array,
  idxs: Uint32Array | number[],
  count: number,
  k: number,
): void {
  for (let ki = 0; ki < k; ki++) {
    let minPos = ki
    for (let m = ki + 1; m < count; m++) {
      if (dists[m] < dists[minPos]) minPos = m
    }
    if (minPos !== ki) {
      const td = dists[ki]; dists[ki] = dists[minPos]; dists[minPos] = td
      const ti = idxs[ki]; idxs[ki] = idxs[minPos]; idxs[minPos] = ti
    }
  }
}

function resolveOptions(options?: UMAPOptions): Required<UMAPOptions> {
  return {
    nNeighbors: options?.nNeighbors ?? UMAP_DEFAULTS.nNeighbors,
    minDist: options?.minDist ?? UMAP_DEFAULTS.minDist,
    spread: options?.spread ?? UMAP_DEFAULTS.spread,
    nEpochs: options?.nEpochs ?? UMAP_DEFAULTS.nEpochs,
    learningRate: options?.learningRate ?? UMAP_DEFAULTS.learningRate,
    negativeSampleRate: options?.negativeSampleRate ?? UMAP_DEFAULTS.negativeSampleRate,
    seed: options?.seed ?? UMAP_DEFAULTS.seed,
  }
}

/**
 * Deterministic PRNG (linear congruential generator) for reproducible
 * negative sampling and initialization noise.
 */
class PRNG {
  private state: number

  constructor(seed: number) {
    this.state = (seed & 0x7fffffff) || 1
  }

  next(): number {
    this.state = (this.state * 1664525 + 1013904223) & 0x7fffffff
    return this.state / 0x7fffffff
  }

  nextInt(max: number): number {
    return Math.floor(this.next() * max)
  }
}
