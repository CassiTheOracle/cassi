// Newton-Schulz orthogonalization: computes the orthogonal factor U·V^T of the polar
// decomposition of an arbitrary matrix G. Used by Muon to remap a gradient G into an
// "orthogonal step direction" with all singular values driven to 1, which is what makes
// Muon train Lightning Indexer matrices ~5× faster than AdamW per step.
//
// Two-stage iteration: Stage A pulls singular values toward 1 from anywhere in [0, 1],
// Stage B polishes near 1 with quintic-exact correction.

const STAGE_A_ITERATIONS = 8
const STAGE_A_COEFFS = { a: 3.4445, b: -4.7750, c: 2.0315 } as const

const STAGE_B_ITERATIONS = 2
const STAGE_B_COEFFS = { a: 2, b: -1.5, c: 0.5 } as const

export interface NewtonSchulzResult {
  output: Float32Array
  rows: number
  cols: number
  spectralNormPre: number
  rmsPostError: number
}

export function newtonSchulz(input: Float32Array, rows: number, cols: number): NewtonSchulzResult {
  if (input.length !== rows * cols) {
    throw new Error(`newtonSchulz: buffer length ${input.length} != rows*cols (${rows}*${cols}=${rows * cols})`)
  }
  if (rows === 0 || cols === 0) {
    return { output: new Float32Array(0), rows, cols, spectralNormPre: 0, rmsPostError: 0 }
  }

  const transposed = rows > cols
  const m = transposed ? cols : rows
  const n = transposed ? rows : cols

  let X = transposed ? transpose(input, rows, cols) : Float32Array.from(input)

  const fro = frobeniusNorm(X)
  if (fro < 1e-30) {
    return { output: X, rows, cols, spectralNormPre: 0, rmsPostError: 0 }
  }
  scaleInPlace(X, 1 / fro)

  for (let i = 0; i < STAGE_A_ITERATIONS; i++) {
    X = newtonSchulzStep(X, m, n, STAGE_A_COEFFS)
  }
  for (let i = 0; i < STAGE_B_ITERATIONS; i++) {
    X = newtonSchulzStep(X, m, n, STAGE_B_COEFFS)
  }

  const rmsPostError = identityFrobeniusError(X, m, n)
  const result = transposed ? transpose(X, m, n) : X

  return { output: result, rows, cols, spectralNormPre: fro, rmsPostError }
}

function newtonSchulzStep(
  X: Float32Array,
  m: number,
  n: number,
  coeffs: { a: number; b: number; c: number },
): Float32Array {
  const Y = matmulXXT(X, m, n)
  const Y2 = matmulSquare(Y, m)

  const result = new Float32Array(m * n)
  const { a, b, c } = coeffs
  for (let i = 0; i < m; i++) {
    for (let j = 0; j < n; j++) {
      let yx = 0
      let y2x = 0
      for (let k = 0; k < m; k++) {
        const xk = X[k * n + j]
        yx += Y[i * m + k] * xk
        y2x += Y2[i * m + k] * xk
      }
      result[i * n + j] = a * X[i * n + j] + b * yx + c * y2x
    }
  }
  return result
}

function matmulXXT(X: Float32Array, m: number, n: number): Float32Array {
  const Y = new Float32Array(m * m)
  for (let i = 0; i < m; i++) {
    for (let k = i; k < m; k++) {
      let s = 0
      for (let j = 0; j < n; j++) {
        s += X[i * n + j] * X[k * n + j]
      }
      Y[i * m + k] = s
      Y[k * m + i] = s
    }
  }
  return Y
}

function matmulSquare(A: Float32Array, m: number): Float32Array {
  const B = new Float32Array(m * m)
  for (let i = 0; i < m; i++) {
    for (let j = 0; j < m; j++) {
      let s = 0
      for (let k = 0; k < m; k++) {
        s += A[i * m + k] * A[k * m + j]
      }
      B[i * m + j] = s
    }
  }
  return B
}

function transpose(M: Float32Array, rows: number, cols: number): Float32Array {
  const T = new Float32Array(rows * cols)
  for (let i = 0; i < rows; i++) {
    for (let j = 0; j < cols; j++) {
      T[j * rows + i] = M[i * cols + j]
    }
  }
  return T
}

function frobeniusNorm(M: Float32Array): number {
  let s = 0
  for (let i = 0; i < M.length; i++) s += M[i] * M[i]
  return Math.sqrt(s)
}

function scaleInPlace(M: Float32Array, s: number): void {
  for (let i = 0; i < M.length; i++) M[i] *= s
}

function identityFrobeniusError(X: Float32Array, m: number, n: number): number {
  const Y = matmulXXT(X, m, n)
  let s = 0
  for (let i = 0; i < m; i++) {
    for (let j = 0; j < m; j++) {
      const target = i === j ? 1 : 0
      const d = Y[i * m + j] - target
      s += d * d
    }
  }
  return Math.sqrt(s / (m * m))
}
