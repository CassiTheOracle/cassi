import { Buffer } from 'node:buffer'

export const PROTOCOL = 'CassiQwen L15 embedding-to-field lift'
export const VERSION = 1
export const GRID_N = 32
export const VOLUME_SIZE = GRID_N ** 3
export const DIMENSION = 1536
export const MODE_CAPACITY = DIMENSION / 2
export const L16_DIMENSION = 5120
export const L16_MODE_CAPACITY = L16_DIMENSION / 2
export const PHI = 1.618033988749895
export const AMPLITUDE = 1
export const DT = 0.005
export const HORIZONS = Object.freeze([0, 1, 4, 16, 64, 256, 1024, 2048])
export const LAYOUT = 'x + N*(y + N*z)'
export const DTYPE = 'float32-le'
export const VECTOR_SEED = 0x0c4551
export const SHUFFLE_SEED = 0x51f71e1d

export const N = GRID_N
export const V = VOLUME_SIZE
export const D = DIMENSION
export const ALPHA = AMPLITUDE
export const CAPACITY = DIMENSION

const TWO_PI = 2 * Math.PI
const UINT32_SCALE = 0x100000000
const FLOAT32_BYTES = 4

export class CodecError extends Error {
  constructor(message, code = 'ERR_CODEC') {
    super(message)
    this.name = 'CodecError'
    this.code = code
  }
}

function isNumericArray(value) {
  return Array.isArray(value) || (ArrayBuffer.isView(value) && !(value instanceof DataView))
}

function arrayLength(value, label) {
  if (!isNumericArray(value)) throw new TypeError(`${label} must be an array or typed array`)
  return value.length
}

function assertFiniteArray(value, label, expectedLength = undefined) {
  const length = arrayLength(value, label)
  if (expectedLength !== undefined && length !== expectedLength) {
    throw new RangeError(`${label} must contain exactly ${expectedLength} values (received ${length})`)
  }
  for (let i = 0; i < length; i += 1) {
    if (typeof value[i] !== 'number' || !Number.isFinite(value[i])) {
      throw new TypeError(`${label}[${i}] must be finite`)
    }
  }
  return length
}

function asFloat64(value, label, expectedLength = undefined) {
  const length = assertFiniteArray(value, label, expectedLength)
  const result = new Float64Array(length)
  for (let i = 0; i < length; i += 1) result[i] = value[i]
  return result
}

function asFloat32(value, label, expectedLength = undefined) {
  const length = assertFiniteArray(value, label, expectedLength)
  const result = new Float32Array(length)
  for (let i = 0; i < length; i += 1) {
    result[i] = value[i]
    if (!Number.isFinite(result[i])) throw new RangeError(`${label}[${i}] is outside float32 range`)
  }
  return result
}

function assertInteger(value, label) {
  if (!Number.isInteger(value)) throw new TypeError(`${label} must be an integer`)
}

function assertPowerOfTwo(value, label) {
  assertInteger(value, label)
  if (value < 1 || (value & (value - 1)) !== 0) throw new RangeError(`${label} must be a positive power of two`)
}

function inferCubeDimension(length) {
  const n = Math.round(Math.cbrt(length))
  if (n ** 3 !== length) throw new RangeError(`field length ${length} is not a cubic volume`)
  return n
}

function resolveCodecConfig({
  dimension = DIMENSION,
  gridN = GRID_N,
  capacity = dimension,
} = {}) {
  assertInteger(dimension, 'dimension')
  assertInteger(capacity, 'capacity')
  assertPowerOfTwo(gridN, 'gridN')
  if (dimension < 2 || dimension % 2 !== 0) throw new RangeError('dimension must be a positive even integer')
  if (capacity !== dimension) throw new RangeError('capacity must equal the exact codec dimension')
  const modeCount = dimension / 2
  const available = canonicalModes(gridN).length
  if (modeCount > available) {
    throw new RangeError(`dimension ${dimension} needs ${modeCount} modes, grid ${gridN} capacity is ${available * 2}`)
  }
  return Object.freeze({
    dimension,
    capacity,
    gridN,
    volume: gridN ** 3,
    modeCount,
  })
}

/** One unsigned xorshift32 step. */
export function xorshift32(state) {
  let value = state >>> 0
  value ^= value << 13
  value ^= value >>> 17
  value ^= value << 5
  return value >>> 0
}

export function createXorshift32(seed) {
  let state = seed >>> 0
  return () => {
    state = xorshift32(state)
    return state
  }
}

export function xorshiftUnit(nextUint32) {
  if (typeof nextUint32 !== 'function') throw new TypeError('nextUint32 must be a function')
  return nextUint32() / UINT32_SCALE
}

function gaussianFromStream(length, nextUint32) {
  const values = new Float64Array(length)
  let offset = 0
  while (offset < length) {
    let u1 = xorshiftUnit(nextUint32)
    const u2 = xorshiftUnit(nextUint32)
    if (u1 <= 0) u1 = Number.MIN_VALUE
    const radius = Math.sqrt(-2 * Math.log(u1))
    const angle = TWO_PI * u2
    values[offset] = radius * Math.cos(angle)
    offset += 1
    if (offset < length) {
      values[offset] = radius * Math.sin(angle)
      offset += 1
    }
  }
  return values
}

/** Generate standard normals in Box--Muller pairs from an xorshift32 stream. */
export function gaussianStream(length, seed = VECTOR_SEED) {
  assertInteger(length, 'length')
  if (length < 0) throw new RangeError('length must be non-negative')
  return gaussianFromStream(length, createXorshift32(seed))
}

export const boxMuller = gaussianStream

function dotProduct(left, right) {
  let total = 0
  for (let i = 0; i < left.length; i += 1) total += left[i] * right[i]
  return total
}

function normalizeVector(vector, label = 'vector') {
  let sum = 0
  for (let i = 0; i < vector.length; i += 1) {
    const value = vector[i]
    if (!Number.isFinite(value)) throw new TypeError(`${label}[${i}] must be finite`)
    sum += value * value
  }
  const norm = Math.sqrt(sum)
  if (!(norm > 0) || !Number.isFinite(norm)) throw new RangeError(`${label} must have a non-zero finite L2 norm`)
  const result = new Float64Array(vector.length)
  for (let i = 0; i < vector.length; i += 1) result[i] = vector[i] / norm
  return { vector: result, norm }
}

/** Deterministic three-vector Gram--Schmidt board, before fixture float32 rounding. */
export function generateGramSchmidtBasis({ dimension = DIMENSION, seed = VECTOR_SEED } = {}) {
  assertInteger(dimension, 'dimension')
  if (dimension < 3) throw new RangeError('dimension must be at least three')
  const stream = createXorshift32(seed)
  const raw = [
    gaussianFromStream(dimension, stream),
    gaussianFromStream(dimension, stream),
    gaussianFromStream(dimension, stream),
  ]
  const orthonormal = []
  for (let sourceIndex = 0; sourceIndex < raw.length; sourceIndex += 1) {
    const candidate = new Float64Array(raw[sourceIndex])
    for (const previous of orthonormal) {
      const projection = dotProduct(candidate, previous)
      for (let i = 0; i < candidate.length; i += 1) candidate[i] -= projection * previous[i]
    }
    const normalized = normalizeVector(candidate, `Gram-Schmidt vector ${sourceIndex}`)
    orthonormal.push(normalized.vector)
  }
  return Object.freeze({ a: orthonormal[0], u: orthonormal[1], v: orthonormal[2] })
}

/** Build the frozen board; fixture vectors are rounded once to float32. */
export function buildFixtures({ dimension = DIMENSION, seed = VECTOR_SEED } = {}) {
  const { a, u, v } = generateGramSchmidtBasis({ dimension, seed })
  const near64 = new Float64Array(dimension)
  const opposite64 = new Float64Array(dimension)
  const nearWeight = 0.9
  const orthogonalWeight = Math.sqrt(1 - nearWeight ** 2)
  for (let i = 0; i < dimension; i += 1) {
    near64[i] = nearWeight * a[i] + orthogonalWeight * u[i]
    opposite64[i] = -a[i]
  }
  const toFixture = (values) => new Float32Array(values)
  return Object.freeze({
    a: toFixture(a),
    u: toFixture(u),
    v: toFixture(v),
    anchor: toFixture(a),
    near: toFixture(near64),
    orthogonal: toFixture(v),
    opposite: toFixture(opposite64),
  })
}

export function fixtureBoard({ dimension = DIMENSION, seed = VECTOR_SEED } = {}) {
  const fixtures = buildFixtures({ dimension, seed })
  return [
    { id: 'anchor', basis: 'canonical', embedding: fixtures.anchor },
    { id: 'near', basis: 'canonical', embedding: fixtures.near },
    { id: 'orthogonal', basis: 'canonical', embedding: fixtures.orthogonal },
    { id: 'opposite', basis: 'canonical', embedding: fixtures.opposite },
    { id: 'anchor_shuffled', basis: 'shuffled', embedding: fixtures.anchor },
    { id: 'near_shuffled', basis: 'shuffled', embedding: fixtures.near },
    { id: 'zero', basis: 'zero', embedding: null },
  ]
}

export function wrappedWaveNumber(index, gridN = GRID_N) {
  assertInteger(index, 'index')
  assertInteger(gridN, 'gridN')
  if (index < 0 || index >= gridN) throw new RangeError(`index must be in [0, ${gridN})`)
  return index > Math.floor(gridN / 2) ? index - gridN : index
}

export function flatIndex(x, y, z, gridN = GRID_N) {
  assertInteger(gridN, 'gridN')
  if (x < 0 || x >= gridN || y < 0 || y >= gridN || z < 0 || z >= gridN) throw new RangeError('grid coordinate out of range')
  return x + gridN * (y + gridN * z)
}

function negativeCoordinate(index, gridN) {
  return index === 0 ? 0 : gridN - index
}

function modeRecord(x, y, z, gridN) {
  const kx = wrappedWaveNumber(x, gridN)
  const ky = wrappedWaveNumber(y, gridN)
  const kz = wrappedWaveNumber(z, gridN)
  return {
    x,
    y,
    z,
    kx,
    ky,
    kz,
    k2: kx * kx + ky * ky + kz * kz,
    index: flatIndex(x, y, z, gridN),
    negativeIndex: flatIndex(negativeCoordinate(x, gridN), negativeCoordinate(y, gridN), negativeCoordinate(z, gridN), gridN),
  }
}

let canonicalModeCache = null

/** Full canonical one-sided mode list, sorted and conjugate-pair deduplicated. */
export function buildCanonicalModes(gridN = GRID_N) {
  assertPowerOfTwo(gridN, 'gridN')
  const candidates = []
  for (let z = 0; z < gridN; z += 1) {
    for (let y = 0; y < gridN; y += 1) {
      for (let x = 0; x < gridN; x += 1) {
        const mode = modeRecord(x, y, z, gridN)
        if (mode.index === mode.negativeIndex) continue
        candidates.push(mode)
      }
    }
  }
  candidates.sort((left, right) => left.k2 - right.k2 || left.kz - right.kz || left.ky - right.ky || left.kx - right.kx || left.index - right.index)
  const seen = new Uint8Array(gridN ** 3)
  const selected = []
  for (const mode of candidates) {
    if (seen[mode.index] !== 0) continue
    seen[mode.index] = 1
    seen[mode.negativeIndex] = 1
    selected.push(Object.freeze(mode))
  }
  return Object.freeze(selected)
}

function canonicalModes(gridN = GRID_N) {
  if (gridN === GRID_N) {
    if (canonicalModeCache === null) canonicalModeCache = buildCanonicalModes(gridN)
    return canonicalModeCache
  }
  return buildCanonicalModes(gridN)
}

function cloneMode(mode) {
  return { ...mode }
}

export function fisherYatesModes(modes, seed = SHUFFLE_SEED) {
  if (!Array.isArray(modes)) throw new TypeError('modes must be an array')
  const result = modes.map(cloneMode)
  const nextUint32 = createXorshift32(seed)
  for (let i = result.length - 1; i > 0; i -= 1) {
    const j = nextUint32() % (i + 1)
    const swap = result[i]
    result[i] = result[j]
    result[j] = swap
  }
  return result
}

export const shuffleModes = fisherYatesModes

function validateMode(mode, gridN = GRID_N) {
  const coordinates = Array.isArray(mode) ? mode : mode && [mode.x, mode.y, mode.z]
  if (!coordinates || coordinates.length !== 3 || !coordinates.every(Number.isInteger)) throw new TypeError('every mode must have integer x, y, and z coordinates')
  const canonical = modeRecord(coordinates[0], coordinates[1], coordinates[2], gridN)
  if (canonical.index === canonical.negativeIndex) throw new RangeError('self-conjugate modes cannot encode a coefficient pair')
  return canonical
}

export function getModes(basis = 'canonical', count = MODE_CAPACITY, gridN = GRID_N) {
  assertInteger(count, 'count')
  if (count < 1) throw new RangeError('count must be positive')
  const available = canonicalModes(gridN)
  if (count > available.length) throw new RangeError(`requested ${count} modes, capacity is ${available.length}`)
  if (Array.isArray(basis)) {
    if (basis.length !== count) throw new RangeError(`custom basis must contain exactly ${count} modes`)
    const modes = basis.map((mode) => validateMode(mode, gridN))
    const used = new Set()
    for (const mode of modes) {
      if (used.has(mode.index) || used.has(mode.negativeIndex)) throw new RangeError('custom basis contains a repeated conjugate pair')
      used.add(mode.index)
      used.add(mode.negativeIndex)
    }
    return modes
  }
  if (basis !== 'canonical' && basis !== 'shuffled') throw new RangeError(`unsupported basis: ${String(basis)}`)
  const selected = available.slice(0, count).map(cloneMode)
  return basis === 'shuffled' ? fisherYatesModes(selected, SHUFFLE_SEED) : selected
}

export const selectedModes = getModes

export function serializeModes(modes) {
  if (!Array.isArray(modes)) throw new TypeError('modes must be an array')
  return modes.map((mode) => [mode.x, mode.y, mode.z])
}

export function modeBasisManifest({ count = MODE_CAPACITY, gridN = GRID_N } = {}) {
  const canonical = getModes('canonical', count, gridN)
  const shuffled = getModes('shuffled', count, gridN)
  return {
    canonical: {
      capacity: count,
      modes: serializeModes(canonical),
    },
    shuffled: {
      capacity: count,
      seed: `0x${SHUFFLE_SEED.toString(16)}`,
      modes: serializeModes(shuffled),
    },
  }
}

function fft1dInPlace(real, imaginary, inverse = false) {
  const length = real.length
  assertPowerOfTwo(length, 'FFT length')
  if (imaginary.length !== length) throw new RangeError('FFT real and imaginary lengths differ')

  for (let i = 1, j = 0; i < length; i += 1) {
    let bit = length >> 1
    for (; (j & bit) !== 0; bit >>= 1) j ^= bit
    j ^= bit
    if (i < j) {
      const realValue = real[i]
      real[i] = real[j]
      real[j] = realValue
      const imaginaryValue = imaginary[i]
      imaginary[i] = imaginary[j]
      imaginary[j] = imaginaryValue
    }
  }

  for (let block = 2; block <= length; block <<= 1) {
    const angle = (inverse ? TWO_PI : -TWO_PI) / block
    const cosine = Math.cos(angle)
    const sine = Math.sin(angle)
    const half = block >> 1
    for (let start = 0; start < length; start += block) {
      let wr = 1
      let wi = 0
      for (let offset = 0; offset < half; offset += 1) {
        const even = start + offset
        const odd = even + half
        const tr = wr * real[odd] - wi * imaginary[odd]
        const ti = wr * imaginary[odd] + wi * real[odd]
        const er = real[even]
        const ei = imaginary[even]
        real[even] = er + tr
        imaginary[even] = ei + ti
        real[odd] = er - tr
        imaginary[odd] = ei - ti
        const nextWr = wr * cosine - wi * sine
        wi = wr * sine + wi * cosine
        wr = nextWr
      }
    }
  }
  if (inverse) {
    for (let i = 0; i < length; i += 1) {
      real[i] /= length
      imaginary[i] /= length
    }
  }
}

/** Pure 1-D radix-2 transform; returned arrays are always float64. */
export function fft1d(realInput, imaginaryInput = undefined, inverse = false) {
  const real = asFloat64(realInput, 'FFT real input')
  const imaginary = imaginaryInput === undefined ? new Float64Array(real.length) : asFloat64(imaginaryInput, 'FFT imaginary input', real.length)
  fft1dInPlace(real, imaginary, inverse)
  return { real, imaginary, re: real, im: imaginary }
}

function fft3dInPlace(real, imaginary, gridN, inverse) {
  const lineReal = new Float64Array(gridN)
  const lineImaginary = new Float64Array(gridN)
  for (let z = 0; z < gridN; z += 1) {
    for (let y = 0; y < gridN; y += 1) {
      const base = flatIndex(0, y, z, gridN)
      for (let x = 0; x < gridN; x += 1) {
        lineReal[x] = real[base + x]
        lineImaginary[x] = imaginary[base + x]
      }
      fft1dInPlace(lineReal, lineImaginary, inverse)
      for (let x = 0; x < gridN; x += 1) {
        real[base + x] = lineReal[x]
        imaginary[base + x] = lineImaginary[x]
      }
    }
  }
  for (let z = 0; z < gridN; z += 1) {
    for (let x = 0; x < gridN; x += 1) {
      for (let y = 0; y < gridN; y += 1) {
        const index = flatIndex(x, y, z, gridN)
        lineReal[y] = real[index]
        lineImaginary[y] = imaginary[index]
      }
      fft1dInPlace(lineReal, lineImaginary, inverse)
      for (let y = 0; y < gridN; y += 1) {
        const index = flatIndex(x, y, z, gridN)
        real[index] = lineReal[y]
        imaginary[index] = lineImaginary[y]
      }
    }
  }
  for (let y = 0; y < gridN; y += 1) {
    for (let x = 0; x < gridN; x += 1) {
      for (let z = 0; z < gridN; z += 1) {
        const index = flatIndex(x, y, z, gridN)
        lineReal[z] = real[index]
        lineImaginary[z] = imaginary[index]
      }
      fft1dInPlace(lineReal, lineImaginary, inverse)
      for (let z = 0; z < gridN; z += 1) {
        const index = flatIndex(x, y, z, gridN)
        real[index] = lineReal[z]
        imaginary[index] = lineImaginary[z]
      }
    }
  }
}

/** Pure separable 3-D radix-2 transform in x-fastest flat layout. */
export function fft3d(realInput, imaginaryInput = undefined, gridNOrInverse = GRID_N, inverseInput = false) {
  const inverse = typeof gridNOrInverse === 'boolean' ? gridNOrInverse : inverseInput
  const gridN = typeof gridNOrInverse === 'boolean' ? inferCubeDimension(arrayLength(realInput, 'FFT real input')) : gridNOrInverse
  assertPowerOfTwo(gridN, 'gridN')
  const volume = gridN ** 3
  const real = asFloat64(realInput, 'FFT real input', volume)
  const imaginary = imaginaryInput === undefined ? new Float64Array(volume) : asFloat64(imaginaryInput, 'FFT imaginary input', volume)
  fft3dInPlace(real, imaginary, gridN, inverse)
  return { real, imaginary, re: real, im: imaginary, gridN }
}

export const transform3d = fft3d

export function normalizeEmbedding(embedding, { dimension = DIMENSION, capacity = CAPACITY } = {}) {
  assertInteger(dimension, 'dimension')
  assertInteger(capacity, 'capacity')
  const length = arrayLength(embedding, 'embedding')
  if (length > capacity) throw new RangeError(`embedding exceeds codec capacity of ${capacity} values`)
  if (length !== dimension) throw new RangeError(`embedding must contain exactly ${dimension} values (received ${length})`)
  const source = asFloat64(embedding, 'embedding', dimension)
  return normalizeVector(source, 'embedding').vector
}

/** Normalize an exact-dimension vector and retain its finite positive scale. */
export function normalizeEmbeddingWithNorm(embedding, { dimension = DIMENSION, capacity = dimension } = {}) {
  assertInteger(dimension, 'dimension')
  assertInteger(capacity, 'capacity')
  if (capacity !== dimension) throw new RangeError('capacity must equal the exact codec dimension')
  const length = arrayLength(embedding, 'embedding')
  if (length > capacity) throw new RangeError(`embedding exceeds codec capacity of ${capacity} values`)
  if (length !== dimension) throw new RangeError(`embedding must contain exactly ${dimension} values (received ${length})`)
  const source = asFloat64(embedding, 'embedding', dimension)
  return normalizeVector(source, 'embedding')
}

/** Restore a decoded unit-direction vector to a separately carried L2 norm. */
export function restoreEmbeddingNorm(direction, norm, { dimension = DIMENSION } = {}) {
  assertInteger(dimension, 'dimension')
  if (typeof norm !== 'number' || !Number.isFinite(norm) || !(norm > 0)) {
    throw new RangeError('norm must be finite and positive')
  }
  const normalized = asFloat64(direction, 'direction', dimension)
  const restored = new Float64Array(dimension)
  for (let i = 0; i < dimension; i += 1) restored[i] = normalized[i] * norm
  return restored
}

function validatePhi(phi) {
  if (typeof phi !== 'number' || !Number.isFinite(phi) || !(phi > 0)) throw new RangeError('phi must be a finite positive number')
}

function validateAmplitude(amplitude) {
  if (typeof amplitude !== 'number' || !Number.isFinite(amplitude) || amplitude <= 0) throw new RangeError('amplitude must be finite and positive')
}

export function splitSignedField(signal, phi = PHI, { gridN = GRID_N } = {}) {
  validatePhi(phi)
  assertPowerOfTwo(gridN, 'gridN')
  const volume = gridN ** 3
  const source = asFloat32(signal, 'signed field', volume)
  const ey = new Float32Array(volume)
  const ei = new Float32Array(volume)
  for (let i = 0; i < volume; i += 1) {
    const value = source[i]
    if (value > 0) ey[i] = value
    else if (value < 0) ei[i] = -value / phi
  }
  return { ey, ei, EY: ey, EI: ei }
}

export const splitField = splitSignedField

export function joinSignedField(eyInput, eiInput, phi = PHI, { gridN = GRID_N } = {}) {
  validatePhi(phi)
  assertPowerOfTwo(gridN, 'gridN')
  const volume = gridN ** 3
  const ey = asFloat32(eyInput, 'EY field', volume)
  const ei = asFloat32(eiInput, 'EI field', volume)
  const signal = new Float64Array(volume)
  for (let i = 0; i < volume; i += 1) signal[i] = ey[i] - phi * ei[i]
  return signal
}

export const joinField = joinSignedField

function encodeSpectrum(normalized, modes, { gridN, amplitude }) {
  const volume = gridN ** 3
  const real = new Float64Array(volume)
  const imaginary = new Float64Array(volume)
  const scale = amplitude * Math.sqrt(volume / 2)
  for (let pair = 0; pair < modes.length; pair += 1) {
    const a = normalized[2 * pair]
    const b = normalized[2 * pair + 1]
    const positive = modes[pair].index
    const negative = modes[pair].negativeIndex
    real[positive] = scale * a
    imaginary[positive] = -scale * b
    real[negative] = scale * a
    imaginary[negative] = scale * b
  }
  return { real, imaginary, scale }
}

function copyModesForResult(modes) {
  return modes.map(cloneMode)
}

/** Encode an exact real vector into a float32 split field. Defaults retain L15. */
export function encodeEmbedding(embedding, {
  basis = 'canonical',
  phi = PHI,
  amplitude = AMPLITUDE,
  dimension = DIMENSION,
  gridN = GRID_N,
  capacity = dimension,
} = {}) {
  validatePhi(phi)
  validateAmplitude(amplitude)
  const config = resolveCodecConfig({ dimension, gridN, capacity })
  const original = asFloat64(embedding, 'embedding')
  const normalization = normalizeEmbeddingWithNorm(original, config)
  const normalized = normalization.vector
  const modes = getModes(basis, config.modeCount, config.gridN)
  const spectrum = encodeSpectrum(normalized, modes, { gridN: config.gridN, amplitude })
  fft3dInPlace(spectrum.real, spectrum.imaginary, config.gridN, true)
  // The signed-volume boundary is the only float32 rounding in construction.
  const signal = new Float32Array(spectrum.real)
  const split = splitSignedField(signal, phi, { gridN: config.gridN })
  return {
    basis: Array.isArray(basis) ? 'custom' : basis,
    embedding: original,
    normalized,
    input_l2_norm: normalization.norm,
    modes: copyModesForResult(modes),
    grid_n: config.gridN,
    dimension: config.dimension,
    signal,
    signed: signal,
    ey: split.ey,
    ei: split.ei,
    EY: split.ey,
    EI: split.ei,
  }
}

export const encode = encodeEmbedding
export const encodeField = encodeEmbedding

function fieldsFromArguments(first, second, third) {
  if (first && typeof first === 'object' && !isNumericArray(first) && first.ey_b64 !== undefined && first.ei_b64 !== undefined) {
    return { ey_b64: first.ey_b64, ei_b64: first.ei_b64, options: second ?? {} }
  }
  if (typeof first === 'string' && typeof second === 'string') {
    return { ey_b64: first, ei_b64: second, options: third ?? {} }
  }
  if (first && typeof first === 'object' && !isNumericArray(first) && first.ey !== undefined && first.ei !== undefined) {
    return { ey: first.ey, ei: first.ei, options: second ?? {} }
  }
  if (second && typeof second === 'object' && !isNumericArray(second)) return { ey: first, ei: second.ey, options: third ?? {} }
  return { ey: first, ei: second, options: third ?? {} }
}

/** Decode a split field back into the normalized real coefficient vector. */
export function decodeEmbedding(first, second, third) {
  const parsed = fieldsFromArguments(first, second, third)
  const options = typeof parsed.options === 'string' ? { basis: parsed.options } : parsed.options ?? {}
  const phi = options.phi ?? PHI
  const amplitude = options.amplitude ?? AMPLITUDE
  const basis = options.basis ?? 'canonical'
  validatePhi(phi)
  validateAmplitude(amplitude)
  const config = resolveCodecConfig(options)
  const ey = parsed.ey_b64 === undefined ? parsed.ey : base64ToFloat32(parsed.ey_b64, config.volume)
  const ei = parsed.ei_b64 === undefined ? parsed.ei : base64ToFloat32(parsed.ei_b64, config.volume)
  const epsilon = joinSignedField(ey, ei, phi, { gridN: config.gridN })
  const imaginary = new Float64Array(config.volume)
  fft3dInPlace(epsilon, imaginary, config.gridN, false)
  const modes = getModes(basis, config.modeCount, config.gridN)
  const scale = amplitude * Math.sqrt(config.volume / 2)
  const embedding = new Float64Array(config.dimension)
  for (let pair = 0; pair < modes.length; pair += 1) {
    embedding[2 * pair] = epsilon[modes[pair].index] / scale
    embedding[2 * pair + 1] = -imaginary[modes[pair].index] / scale
  }
  return embedding
}

export const decode = decodeEmbedding
export const decodeField = decodeEmbedding

export function decodeSignal(signal, options = {}) {
  const { basis = 'canonical', phi = PHI, amplitude = AMPLITUDE, dimension = DIMENSION, gridN = GRID_N, capacity = dimension } = options
  const split = splitSignedField(signal, phi, { gridN })
  return decodeEmbedding(split, { basis, phi, amplitude, dimension, gridN, capacity })
}

export function encodeEmbeddingBase64(embedding, options = {}) {
  const encoded = encodeEmbedding(embedding, options)
  return {
    ...encoded,
    embedding_b64: float32ToBase64(encoded.embedding),
    signal_b64: float32ToBase64(encoded.signal),
    ey_b64: float32ToBase64(encoded.ey),
    ei_b64: float32ToBase64(encoded.ei),
  }
}

function isCanonicalBase64(value) {
  return typeof value === 'string'
    && value.length % 4 === 0
    && /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value)
}

export function float32ToBase64(values) {
  const length = assertFiniteArray(values, 'float32 values')
  const bytes = new Uint8Array(length * FLOAT32_BYTES)
  const view = new DataView(bytes.buffer)
  for (let i = 0; i < length; i += 1) {
    view.setFloat32(i * FLOAT32_BYTES, values[i], true)
    if (!Number.isFinite(view.getFloat32(i * FLOAT32_BYTES, true))) throw new RangeError(`float32 values[${i}] is outside float32 range`)
  }
  return Buffer.from(bytes).toString('base64')
}

export const encodeFloat32Base64 = float32ToBase64
export const float32ArrayToBase64 = float32ToBase64

export function base64ToFloat32(text, expectedLength = undefined, { allowNonFinite = false } = {}) {
  if (!isCanonicalBase64(text)) throw new TypeError('base64 must be canonical padded base64 text')
  const bytes = Buffer.from(text, 'base64')
  if (bytes.toString('base64') !== text) throw new TypeError('base64 is not canonical')
  if (bytes.byteLength % FLOAT32_BYTES !== 0) throw new RangeError('base64 payload length is not a multiple of four bytes')
  const length = bytes.byteLength / FLOAT32_BYTES
  if (expectedLength !== undefined && length !== expectedLength) throw new RangeError(`decoded float32 length must be ${expectedLength} (received ${length})`)
  const result = new Float32Array(length)
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  for (let i = 0; i < length; i += 1) {
    const value = view.getFloat32(i * FLOAT32_BYTES, true)
    if (!allowNonFinite && !Number.isFinite(value)) throw new TypeError(`decoded float32 value ${i} is non-finite`)
    result[i] = value
  }
  return result
}

export const decodeFloat32Base64 = base64ToFloat32
export const base64ToFloat32Array = base64ToFloat32

export function l2Norm(values) {
  const length = assertFiniteArray(values, 'values')
  let sum = 0
  for (let i = 0; i < length; i += 1) sum += values[i] * values[i]
  return Math.sqrt(sum)
}

export function cosineSimilarity(left, right) {
  const length = assertFiniteArray(left, 'left')
  assertFiniteArray(right, 'right', length)
  let numerator = 0
  let leftSum = 0
  let rightSum = 0
  for (let i = 0; i < length; i += 1) {
    numerator += left[i] * right[i]
    leftSum += left[i] * left[i]
    rightSum += right[i] * right[i]
  }
  const denominator = Math.sqrt(leftSum * rightSum)
  return denominator === 0 ? 0 : numerator / denominator
}

export function relativeL2Error(actual, expected) {
  const length = assertFiniteArray(actual, 'actual')
  assertFiniteArray(expected, 'expected', length)
  let difference = 0
  let reference = 0
  for (let i = 0; i < length; i += 1) {
    const delta = actual[i] - expected[i]
    difference += delta * delta
    reference += expected[i] * expected[i]
  }
  if (reference === 0) return difference === 0 ? 0 : Infinity
  return Math.sqrt(difference / reference)
}

export function pairwiseCosines(vectors) {
  if (!vectors || typeof vectors !== 'object') throw new TypeError('vectors must be an object')
  const names = Object.keys(vectors)
  const result = {}
  for (let i = 0; i < names.length; i += 1) {
    for (let j = i + 1; j < names.length; j += 1) {
      result[`${names[i]}|${names[j]}`] = cosineSimilarity(vectors[names[i]], vectors[names[j]])
    }
  }
  return result
}

export function maxPairwiseCosineError(expectedVectors, decodedVectors) {
  if (!expectedVectors || !decodedVectors) throw new TypeError('expected and decoded vectors are required')
  const names = Object.keys(expectedVectors)
  let maximum = 0
  for (let i = 0; i < names.length; i += 1) {
    for (let j = i + 1; j < names.length; j += 1) {
      const left = names[i]
      const right = names[j]
      const expected = cosineSimilarity(expectedVectors[left], expectedVectors[right])
      const decoded = cosineSimilarity(decodedVectors[left], decodedVectors[right])
      maximum = Math.max(maximum, Math.abs(expected - decoded))
    }
  }
  return maximum
}

/** Fraction of Fourier energy outside the selected conjugate-pair subspace. */
export function subspaceResidualEnergy(fieldOrChannels, basis = 'canonical', {
  phi = PHI,
  dimension = DIMENSION,
  gridN = GRID_N,
  capacity = dimension,
} = {}) {
  const config = resolveCodecConfig({ dimension, gridN, capacity })
  const epsilon = fieldOrChannels && fieldOrChannels.ey !== undefined && fieldOrChannels.ei !== undefined
    ? joinSignedField(fieldOrChannels.ey, fieldOrChannels.ei, phi, { gridN: config.gridN })
    : asFloat64(fieldOrChannels, 'signed field', config.volume)
  const imaginary = new Float64Array(config.volume)
  fft3dInPlace(epsilon, imaginary, config.gridN, false)
  const modes = getModes(basis, config.modeCount, config.gridN)
  const selected = new Uint8Array(config.volume)
  for (const mode of modes) {
    selected[mode.index] = 1
    selected[mode.negativeIndex] = 1
  }
  let total = 0
  let outside = 0
  for (let i = 0; i < config.volume; i += 1) {
    const energy = epsilon[i] * epsilon[i] + imaginary[i] * imaginary[i]
    total += energy
    if (selected[i] === 0) outside += energy
  }
  return total === 0 ? 0 : outside / total
}

export function fieldMetrics(eyInput, eiInput, {
  basis = 'canonical',
  phi = PHI,
  dimension = DIMENSION,
  gridN = GRID_N,
  capacity = dimension,
} = {}) {
  const config = resolveCodecConfig({ dimension, gridN, capacity })
  const ey = asFloat32(eyInput, 'EY field', config.volume)
  const ei = asFloat32(eiInput, 'EI field', config.volume)
  const epsilon = joinSignedField(ey, ei, phi, { gridN: config.gridN })
  let maxAbs = 0
  let eyL2 = 0
  let eiL2 = 0
  let epsilonL2 = 0
  for (let i = 0; i < config.volume; i += 1) {
    const y = ey[i]
    const n = ei[i]
    const e = epsilon[i]
    maxAbs = Math.max(maxAbs, Math.abs(y), Math.abs(n))
    eyL2 += y * y
    eiL2 += n * n
    epsilonL2 += e * e
  }
  return {
    finite: true,
    maxAbs,
    ey_l2: Math.sqrt(eyL2),
    ei_l2: Math.sqrt(eiL2),
    epsilon_l2: Math.sqrt(epsilonL2),
    subspace_residual_energy: subspaceResidualEnergy({ ey, ei }, basis, {
      phi,
      dimension: config.dimension,
      gridN: config.gridN,
      capacity: config.capacity,
    }),
  }
}

export function zeroField({ gridN = GRID_N } = {}) {
  assertPowerOfTwo(gridN, 'gridN')
  const volume = gridN ** 3
  return {
    signal: new Float32Array(volume),
    ey: new Float32Array(volume),
    ei: new Float32Array(volume),
  }
}
