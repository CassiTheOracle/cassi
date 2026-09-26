/**
 * Worker thread that runs the full UMAP projection pipeline off the main
 * thread. Receives high-dimensional vectors via SharedArrayBuffer, runs
 * NN-Descent → fuzzy set → PCA init → SGD layout, and returns 2D positions.
 *
 * Plain JavaScript (CJS) for maximum worker_threads compatibility.
 * All algorithms are self-contained — no imports from the main codebase.
 */
'use strict'

const { parentPort, workerData } = require('worker_threads')

const {
  vectorsBuffer,   // SharedArrayBuffer: all vectors packed as Float32Array
  n,               // number of vectors
  dim,             // vector dimensionality
  nNeighbors,      // k for KNN
  minDist,
  spread,
  nEpochs,
  learningRate,
  negativeSampleRate,
  seed,
  nnDescentThreshold, // convergence threshold (fraction of n*k)
  nnDescentMaxIter,   // max NN-Descent iterations
} = workerData

const vectors = new Float32Array(vectorsBuffer)

// ─── Utility ─────────────────────────────────────────────────────────────

class PRNG {
  constructor(seed) { this.state = (seed & 0x7fffffff) || 1 }
  next() {
    this.state = (this.state * 1664525 + 1013904223) & 0x7fffffff
    return this.state / 0x7fffffff
  }
  nextInt(max) { return Math.floor(this.next() * max) }
}

function dot(aOff, bOff) {
  let s = 0
  for (let d = 0; d < dim; d++) s += vectors[aOff + d] * vectors[bOff + d]
  return s
}

function dotVec(a, b) {
  let s = 0
  for (let i = 0; i < a.length; i++) s += a[i] * b[i]
  return s
}

function cosineDistFlat(i, j) {
  return Math.max(0, 1 - dot(i * dim, j * dim))
}

function clamp(val, limit) {
  limit = limit || 4
  return val < -limit ? -limit : val > limit ? limit : val
}

function sampleArray(arr, count, rng) {
  if (arr.length <= count) return arr.slice()
  // Fisher-Yates partial shuffle — O(count), no Set allocation
  for (let i = 0; i < count; i++) {
    const j = i + rng.nextInt(arr.length - i)
    const tmp = arr[i]; arr[i] = arr[j]; arr[j] = tmp
  }
  arr.length = count
  return arr
}

// ─── Normalize vectors ──────────────────────────────────────────────────

const normedBuf = new Float32Array(n * dim)
for (let i = 0; i < n; i++) {
  let norm = 0
  const off = i * dim
  for (let d = 0; d < dim; d++) norm += vectors[off + d] * vectors[off + d]
  norm = Math.sqrt(norm)
  if (norm < 1e-10) norm = 1
  for (let d = 0; d < dim; d++) normedBuf[off + d] = vectors[off + d] / norm
}

function normedDot(i, j) {
  let s = 0
  const iOff = i * dim, jOff = j * dim
  for (let d = 0; d < dim; d++) s += normedBuf[iOff + d] * normedBuf[jOff + d]
  return s
}

function normedCosineDist(i, j) {
  let s = 0
  const iOff = i * dim, jOff = j * dim
  // Unroll by 4 for V8 JIT vectorization
  const end4 = dim - (dim % 4)
  let s0 = 0, s1 = 0, s2 = 0, s3 = 0
  for (let d = 0; d < end4; d += 4) {
    s0 += normedBuf[iOff + d] * normedBuf[jOff + d]
    s1 += normedBuf[iOff + d + 1] * normedBuf[jOff + d + 1]
    s2 += normedBuf[iOff + d + 2] * normedBuf[jOff + d + 2]
    s3 += normedBuf[iOff + d + 3] * normedBuf[jOff + d + 3]
  }
  s = s0 + s1 + s2 + s3
  for (let d = end4; d < dim; d++) {
    s += normedBuf[iOff + d] * normedBuf[jOff + d]
  }
  return Math.max(0, 1 - s)
}

// ─── KNN: brute force (for small n) ─────────────────────────────────────

function buildKNNBrute(k) {
  const indices = new Int32Array(n * k)
  const distances = new Float64Array(n * k)
  const distBuf = new Float64Array(n)
  const idxBuf = new Uint32Array(n)

  for (let i = 0; i < n; i++) {
    let count = 0
    for (let j = 0; j < n; j++) {
      if (j === i) continue
      distBuf[count] = normedCosineDist(i, j)
      idxBuf[count] = j
      count++
    }
    partialSelectionSort(distBuf, idxBuf, count, k)
    for (let m = 0; m < k; m++) {
      indices[i * k + m] = idxBuf[m]
      distances[i * k + m] = distBuf[m]
    }

    // Progress reporting every 1000 rows
    if (i % 1000 === 0 && i > 0) {
      parentPort.postMessage({ type: 'progress', phase: 'knn-brute', progress: i / n })
    }
  }

  return { indices, distances }
}

// ─── KNN: NN-Descent (for large n) ──────────────────────────────────────

function buildKNNNNDescent(k) {
  const rng = new PRNG(seed + 3000)

  // Flat storage: neighbors[i*k + m] and dists[i*k + m]
  const neighbors = new Int32Array(n * k)
  const dists = new Float64Array(n * k)
  const isNew = new Uint8Array(n * k)

  // Initialize with random neighbors
  parentPort.postMessage({ type: 'progress', phase: 'nn-descent-init', progress: 0 })

  for (let i = 0; i < n; i++) {
    const used = new Set()
    used.add(i)
    for (let m = 0; m < k; m++) {
      let j
      do { j = rng.nextInt(n) } while (used.has(j))
      used.add(j)
      neighbors[i * k + m] = j
      dists[i * k + m] = normedCosineDist(i, j)
      isNew[i * k + m] = 1
    }
  }

  parentPort.postMessage({ type: 'progress', phase: 'nn-descent-init', progress: 1 })

  const maxIter = nnDescentMaxIter || 15
  const threshold = Math.max(1, Math.floor((nnDescentThreshold || 0.001) * n * k))
  let totalDistComps = 0

  for (let iter = 0; iter < maxIter; iter++) {
    let updates = 0

    // Build forward new/old lists
    const newFwd = new Array(n)
    const oldFwd = new Array(n)
    for (let i = 0; i < n; i++) {
      newFwd[i] = []
      oldFwd[i] = []
      for (let m = 0; m < k; m++) {
        if (isNew[i * k + m] === 1) {
          newFwd[i].push(neighbors[i * k + m])
        } else {
          oldFwd[i].push(neighbors[i * k + m])
        }
      }
    }

    // Build reverse lists
    const newRev = new Array(n)
    const oldRev = new Array(n)
    for (let i = 0; i < n; i++) { newRev[i] = []; oldRev[i] = [] }
    for (let i = 0; i < n; i++) {
      for (const j of newFwd[i]) newRev[j].push(i)
      for (const j of oldFwd[i]) oldRev[j].push(i)
    }

    // Sample reverse lists to keep sizes manageable (rho=0.5 matches reference UMAP)
    const maxRev = Math.max(1, Math.floor(k * 0.5))
    for (let i = 0; i < n; i++) {
      if (newRev[i].length > maxRev) newRev[i] = sampleArray(newRev[i], maxRev, rng)
      if (oldRev[i].length > maxRev) oldRev[i] = sampleArray(oldRev[i], maxRev, rng)
    }

    // Mark all current "new" as "old" for next iteration
    isNew.fill(0)

    // Local join: for each point p, check all pairs from
    // (new) × (new ∪ old) without allocating intermediate arrays.
    // Pairs are processed per-point without global dedup to avoid Set size limits.
    for (let p = 0; p < n; p++) {
      const pNewFwd = newFwd[p]
      const pNewRev = newRev[p]
      if (pNewFwd.length === 0 && pNewRev.length === 0) continue

      const pOldFwd = oldFwd[p]
      const pOldRev = oldRev[p]

      // new × new pairs: within pNewFwd
      for (let a = 0; a < pNewFwd.length; a++) {
        const u = pNewFwd[a]
        for (let b = a + 1; b < pNewFwd.length; b++) {
          const v = pNewFwd[b]
          const d = normedCosineDist(u, v)
          totalDistComps++
          updates += tryInsert(neighbors, dists, isNew, u, v, d, k)
          updates += tryInsert(neighbors, dists, isNew, v, u, d, k)
        }
        // cross: pNewFwd × pNewRev
        for (let b = 0; b < pNewRev.length; b++) {
          const v = pNewRev[b]
          if (v === u) continue
          const d = normedCosineDist(u, v)
          totalDistComps++
          updates += tryInsert(neighbors, dists, isNew, u, v, d, k)
          updates += tryInsert(neighbors, dists, isNew, v, u, d, k)
        }
      }
      // new × new pairs: within pNewRev
      for (let a = 0; a < pNewRev.length; a++) {
        const u = pNewRev[a]
        for (let b = a + 1; b < pNewRev.length; b++) {
          const v = pNewRev[b]
          const d = normedCosineDist(u, v)
          totalDistComps++
          updates += tryInsert(neighbors, dists, isNew, u, v, d, k)
          updates += tryInsert(neighbors, dists, isNew, v, u, d, k)
        }
      }

      // new × old pairs: all new × all old
      for (let ni = 0; ni < pNewFwd.length; ni++) {
        const u = pNewFwd[ni]
        for (let oi = 0; oi < pOldFwd.length; oi++) {
          const v = pOldFwd[oi]
          if (u === v) continue
          const d = normedCosineDist(u, v)
          totalDistComps++
          updates += tryInsert(neighbors, dists, isNew, u, v, d, k)
          updates += tryInsert(neighbors, dists, isNew, v, u, d, k)
        }
        for (let oi = 0; oi < pOldRev.length; oi++) {
          const v = pOldRev[oi]
          if (u === v) continue
          const d = normedCosineDist(u, v)
          totalDistComps++
          updates += tryInsert(neighbors, dists, isNew, u, v, d, k)
          updates += tryInsert(neighbors, dists, isNew, v, u, d, k)
        }
      }
      for (let ni = 0; ni < pNewRev.length; ni++) {
        const u = pNewRev[ni]
        for (let oi = 0; oi < pOldFwd.length; oi++) {
          const v = pOldFwd[oi]
          if (u === v) continue
          const d = normedCosineDist(u, v)
          totalDistComps++
          updates += tryInsert(neighbors, dists, isNew, u, v, d, k)
          updates += tryInsert(neighbors, dists, isNew, v, u, d, k)
        }
        for (let oi = 0; oi < pOldRev.length; oi++) {
          const v = pOldRev[oi]
          if (u === v) continue
          const d = normedCosineDist(u, v)
          totalDistComps++
          updates += tryInsert(neighbors, dists, isNew, u, v, d, k)
          updates += tryInsert(neighbors, dists, isNew, v, u, d, k)
        }
      }
    }

    parentPort.postMessage({
      type: 'progress',
      phase: 'nn-descent',
      progress: (iter + 1) / maxIter,
      updates,
      totalDistComps,
      iter: iter + 1,
      maxIter,
    })

    if (updates < threshold) {
      parentPort.postMessage({
        type: 'progress',
        phase: 'nn-descent-converged',
        iter: iter + 1,
        updates,
        totalDistComps,
      })
      break
    }
  }

  return { indices: neighbors, distances: dists }
}

function tryInsert(neighbors, dists, isNewFlags, u, v, d, k) {
  // Try to insert v as neighbor of u with distance d
  // First check if v is already a neighbor of u
  const base = u * k
  for (let m = 0; m < k; m++) {
    if (neighbors[base + m] === v) return 0
  }

  // Find worst (most distant) current neighbor
  let worstPos = 0
  let worstDist = dists[base]
  for (let m = 1; m < k; m++) {
    if (dists[base + m] > worstDist) {
      worstDist = dists[base + m]
      worstPos = m
    }
  }

  if (d >= worstDist) return 0

  // Replace worst with v
  neighbors[base + worstPos] = v
  dists[base + worstPos] = d
  isNewFlags[base + worstPos] = 1
  return 1
}

// ─── Build KNN graph (auto-select strategy) ─────────────────────────────

const NN_DESCENT_THRESHOLD = 5000  // use NN-Descent when n > this

function buildKNN(k) {
  if (n <= NN_DESCENT_THRESHOLD) {
    return buildKNNBrute(k)
  }
  return buildKNNNNDescent(k)
}

// ─── Smooth KNN distances ───────────────────────────────────────────────

function smoothKNNDistances(knnDistances, nNeighbors, nPoints, k) {
  const target = Math.log2(nNeighbors)
  const sigmas = new Float64Array(nPoints)
  const rhos = new Float64Array(nPoints)

  for (let i = 0; i < nPoints; i++) {
    rhos[i] = knnDistances[i * k]  // nearest neighbor distance
    sigmas[i] = findSigma(knnDistances, i, k, rhos[i], target)
  }

  return { sigmas, rhos }
}

function findSigma(distances, point, k, rho, target) {
  let lo = 1e-8, hi = 1000, mid = 1.0
  const base = point * k

  for (let iter = 0; iter < 64; iter++) {
    mid = (lo + hi) / 2
    let sum = 0
    for (let m = 0; m < k; m++) {
      sum += Math.exp(-Math.max(0, distances[base + m] - rho) / mid)
    }
    if (Math.abs(sum - target) < 1e-5) break
    if (sum > target) hi = mid
    else lo = mid
  }

  return mid
}

// ─── Build fuzzy simplicial set ─────────────────────────────────────────

function buildFuzzySimplicialSet(knnIndices, knnDistances, sigmas, rhos, nPoints, k) {
  const directed = new Map()

  for (let i = 0; i < nPoints; i++) {
    for (let m = 0; m < k; m++) {
      const j = knnIndices[i * k + m]
      const d = knnDistances[i * k + m]
      const adjusted = Math.max(0, d - rhos[i])
      const w = sigmas[i] > 1e-10 ? Math.exp(-adjusted / sigmas[i]) : 1.0
      directed.set(i * nPoints + j, w)
    }
  }

  const edges = []
  const seen = new Set()

  for (const [key] of directed) {
    const i = Math.floor(key / nPoints)
    const j = key % nPoints
    const lo = Math.min(i, j), hi = Math.max(i, j)
    const canonical = lo * nPoints + hi
    if (seen.has(canonical)) continue
    seen.add(canonical)

    const wij = directed.get(i * nPoints + j) || 0
    const wji = directed.get(j * nPoints + i) || 0
    const sym = wij + wji - wij * wji
    if (sym > 1e-8) {
      edges.push({ source: lo, target: hi, weight: sym })
    }
  }

  return edges
}

// ─── PCA initialization ─────────────────────────────────────────────────

function pcaInitialize(nPoints, pcaSeed, pcaSpread) {
  // Compute mean
  const mean = new Float64Array(dim)
  for (let i = 0; i < nPoints; i++) {
    const off = i * dim
    for (let d = 0; d < dim; d++) mean[d] += vectors[off + d]
  }
  for (let d = 0; d < dim; d++) mean[d] /= nPoints

  // Power iteration for PC1
  const pc1 = powerIteration(mean, nPoints)
  // Deflate and get PC2
  const pc2 = powerIterationDeflated(mean, nPoints, pc1)

  // Project onto PC1 and PC2
  const positions = new Float64Array(nPoints * 2)
  for (let i = 0; i < nPoints; i++) {
    let dotPC1 = 0, dotPC2 = 0
    const off = i * dim
    for (let d = 0; d < dim; d++) {
      const centered = vectors[off + d] - mean[d]
      dotPC1 += centered * pc1[d]
      dotPC2 += centered * pc2[d]
    }
    positions[i * 2] = dotPC1
    positions[i * 2 + 1] = dotPC2
  }

  // Normalize to [-spread, spread]
  let maxCoord = 1e-8
  for (let i = 0; i < nPoints * 2; i++) {
    const ax = Math.abs(positions[i])
    if (ax > maxCoord) maxCoord = ax
  }
  const factor = pcaSpread / maxCoord

  const rng = new PRNG(pcaSeed + 2000)
  for (let i = 0; i < nPoints; i++) {
    positions[i * 2] = positions[i * 2] * factor + (rng.next() - 0.5) * 0.001
    positions[i * 2 + 1] = positions[i * 2 + 1] * factor + (rng.next() - 0.5) * 0.001
  }

  return positions
}

function powerIteration(mean, nPoints, maxIter, tol) {
  maxIter = maxIter || 100
  tol = tol || 1e-8

  // Deterministic starting vector
  let v = new Float64Array(dim)
  let piSeed = 42 + dim
  for (let d = 0; d < dim; d++) {
    piSeed = (piSeed * 1664525 + 1013904223) & 0x7fffffff
    v[d] = (piSeed / 0x7fffffff) * 2 - 1
  }
  normalizeInPlace(v)

  for (let iter = 0; iter < maxIter; iter++) {
    // newV = X^T * X * v (without forming covariance matrix)
    const proj = new Float64Array(nPoints)
    for (let i = 0; i < nPoints; i++) {
      let s = 0
      const off = i * dim
      for (let d = 0; d < dim; d++) s += (vectors[off + d] - mean[d]) * v[d]
      proj[i] = s
    }

    const newV = new Float64Array(dim)
    for (let i = 0; i < nPoints; i++) {
      const s = proj[i]
      const off = i * dim
      for (let d = 0; d < dim; d++) newV[d] += (vectors[off + d] - mean[d]) * s
    }

    normalizeInPlace(newV)

    let change = 0
    for (let d = 0; d < dim; d++) change += (newV[d] - v[d]) ** 2
    change = Math.sqrt(change)

    v = newV
    if (change < tol) break
  }

  return v
}

function powerIterationDeflated(mean, nPoints, pc1) {
  // Deflate: subtract projection onto pc1 from each row
  // We don't actually modify vectors — just compute deflated projections inline
  const deflatedVectors = new Float64Array(n * dim)
  for (let i = 0; i < nPoints; i++) {
    const off = i * dim
    let proj = 0
    for (let d = 0; d < dim; d++) proj += (vectors[off + d] - mean[d]) * pc1[d]
    for (let d = 0; d < dim; d++) {
      deflatedVectors[off + d] = vectors[off + d] - mean[d] - proj * pc1[d]
    }
  }

  // Power iteration on deflated data
  let v = new Float64Array(dim)
  let piSeed = 42 + dim
  for (let d = 0; d < dim; d++) {
    piSeed = (piSeed * 1664525 + 1013904223) & 0x7fffffff
    v[d] = (piSeed / 0x7fffffff) * 2 - 1
  }
  normalizeInPlace(v)

  for (let iter = 0; iter < 100; iter++) {
    const proj = new Float64Array(nPoints)
    for (let i = 0; i < nPoints; i++) {
      let s = 0
      const off = i * dim
      for (let d = 0; d < dim; d++) s += deflatedVectors[off + d] * v[d]
      proj[i] = s
    }

    const newV = new Float64Array(dim)
    for (let i = 0; i < nPoints; i++) {
      const s = proj[i]
      const off = i * dim
      for (let d = 0; d < dim; d++) newV[d] += deflatedVectors[off + d] * s
    }

    normalizeInPlace(newV)

    let change = 0
    for (let d = 0; d < dim; d++) change += (newV[d] - v[d]) ** 2
    change = Math.sqrt(change)

    v = newV
    if (change < 1e-8) break
  }

  return v
}

function normalizeInPlace(v) {
  let norm = 0
  for (let d = 0; d < dim; d++) norm += v[d] * v[d]
  norm = Math.sqrt(norm)
  if (norm < 1e-10) return
  for (let d = 0; d < dim; d++) v[d] /= norm
}

// ─── SGD layout optimization ────────────────────────────────────────────

function optimizeLayout(positions, edges, nPoints, params) {
  const { epochs, lr, negRate, a, b, sgdSeed } = params
  if (edges.length === 0 || nPoints < 2) return

  const rng = new PRNG(sgdSeed + 1000)

  let maxWeight = 0
  for (const e of edges) {
    if (e.weight > maxWeight) maxWeight = e.weight
  }

  const nEdges = edges.length
  const epochsPerSample = new Float64Array(nEdges)
  const nextSample = new Float64Array(nEdges)
  for (let i = 0; i < nEdges; i++) {
    epochsPerSample[i] = edges[i].weight > 0 ? maxWeight / edges[i].weight : epochs + 1
    nextSample[i] = epochsPerSample[i]
  }

  const bMinus1 = b - 1

  for (let epoch = 0; epoch < epochs; epoch++) {
    const alpha = lr * (1 - epoch / epochs)

    for (let e = 0; e < nEdges; e++) {
      if (nextSample[e] > epoch) continue
      nextSample[e] += epochsPerSample[e]

      const si = edges[e].source
      const ti = edges[e].target
      const px = positions[si * 2], py = positions[si * 2 + 1]
      const qx = positions[ti * 2], qy = positions[ti * 2 + 1]

      const dx = px - qx
      const dy = py - qy
      const distSq = Math.max(dx * dx + dy * dy, 1e-8)

      const powDistB = Math.pow(distSq, b)
      const gradCoeff = (-2 * a * b * Math.pow(distSq, bMinus1)) / (1 + a * powDistB)

      const gx = clamp(gradCoeff * dx)
      const gy = clamp(gradCoeff * dy)

      positions[si * 2] += alpha * gx
      positions[si * 2 + 1] += alpha * gy
      positions[ti * 2] -= alpha * gx
      positions[ti * 2 + 1] -= alpha * gy

      // Negative sampling
      for (let neg = 0; neg < negRate; neg++) {
        const kk = rng.nextInt(nPoints)
        if (kk === si) continue

        const nkx = positions[kk * 2], nky = positions[kk * 2 + 1]
        const ndx = px - nkx
        const ndy = py - nky
        const nDistSq = Math.max(ndx * ndx + ndy * ndy, 1e-8)

        const nPowDistB = Math.pow(nDistSq, b)
        const nGradCoeff = (2 * b) / ((0.001 + nDistSq) * (1 + a * nPowDistB))

        positions[si * 2] += alpha * clamp(nGradCoeff * ndx)
        positions[si * 2 + 1] += alpha * clamp(nGradCoeff * ndy)
      }
    }

    // Progress every 10 epochs
    if (epoch % 10 === 0) {
      parentPort.postMessage({ type: 'progress', phase: 'sgd', progress: epoch / epochs })
    }
  }
}

// ─── Find a, b parameters ───────────────────────────────────────────────

function findAB(abSpread, abMinDist) {
  const refD = abMinDist + abSpread
  const refTarget = Math.exp(-1)
  const maxD = 3 * abSpread + abMinDist
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
      const target = d <= abMinDist ? 1.0 : Math.exp(-(d - abMinDist) / abSpread)
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

// ─── Partial selection sort ─────────────────────────────────────────────

function partialSelectionSort(dBuf, iBuf, count, k) {
  for (let ki = 0; ki < k; ki++) {
    let minPos = ki
    for (let m = ki + 1; m < count; m++) {
      if (dBuf[m] < dBuf[minPos]) minPos = m
    }
    if (minPos !== ki) {
      const td = dBuf[ki]; dBuf[ki] = dBuf[minPos]; dBuf[minPos] = td
      const ti = iBuf[ki]; iBuf[ki] = iBuf[minPos]; iBuf[minPos] = ti
    }
  }
}

// ─── Main pipeline ──────────────────────────────────────────────────────

function run() {
  const startTime = Date.now()
  const k = Math.min(nNeighbors, n - 1)

  parentPort.postMessage({ type: 'progress', phase: 'start', n, dim, k })

  // Step 1: Build KNN graph
  const knnStart = Date.now()
  const { indices, distances } = buildKNN(k)
  const knnMs = Date.now() - knnStart
  parentPort.postMessage({ type: 'progress', phase: 'knn-done', durationMs: knnMs })

  // Step 2: Smooth KNN distances
  const { sigmas, rhos } = smoothKNNDistances(distances, nNeighbors, n, k)
  parentPort.postMessage({ type: 'progress', phase: 'smooth-done' })

  // Step 3: Build fuzzy simplicial set
  const edges = buildFuzzySimplicialSet(indices, distances, sigmas, rhos, n, k)
  parentPort.postMessage({ type: 'progress', phase: 'edges-done', edgeCount: edges.length })

  // Step 4: PCA initialization
  const positions = pcaInitialize(n, seed, spread)
  parentPort.postMessage({ type: 'progress', phase: 'pca-done' })

  // Step 5: Find a, b parameters
  const { a, b } = findAB(spread, minDist)

  // Step 6: SGD optimization
  const sgdStart = Date.now()
  optimizeLayout(positions, edges, n, {
    epochs: nEpochs,
    lr: learningRate,
    negRate: negativeSampleRate,
    a, b,
    sgdSeed: seed,
  })
  const sgdMs = Date.now() - sgdStart
  parentPort.postMessage({ type: 'progress', phase: 'sgd-done', durationMs: sgdMs })

  // Step 7: Normalize positions to [-spread, spread]
  let sumX = 0, sumY = 0
  for (let i = 0; i < n; i++) {
    sumX += positions[i * 2]
    sumY += positions[i * 2 + 1]
  }
  const meanX = sumX / n, meanY = sumY / n
  for (let i = 0; i < n; i++) {
    positions[i * 2] -= meanX
    positions[i * 2 + 1] -= meanY
  }
  let maxCoord = 1e-8
  for (let i = 0; i < n * 2; i++) {
    const ax = Math.abs(positions[i])
    if (ax > maxCoord) maxCoord = ax
  }
  const factor = spread / maxCoord
  if (Math.abs(factor - 1.0) > 0.001) {
    for (let i = 0; i < n * 2; i++) positions[i] *= factor
  }

  const totalMs = Date.now() - startTime

  // Return results as a plain array (positions is Float64Array)
  const result = new Array(n)
  for (let i = 0; i < n; i++) {
    result[i] = { x: positions[i * 2], y: positions[i * 2 + 1] }
  }

  parentPort.postMessage({
    type: 'result',
    positions: result,
    stats: { totalMs, knnMs, sgdMs, edges: edges.length },
  })
}

try {
  run()
} catch (err) {
  parentPort.postMessage({ type: 'error', message: String(err), stack: err.stack })
}
