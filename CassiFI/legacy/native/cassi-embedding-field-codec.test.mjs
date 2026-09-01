import assert from 'node:assert/strict'
import test from 'node:test'
import {
  DIMENSION,
  GRID_N,
  HORIZONS,
  MODE_CAPACITY,
  PHI,
  SHUFFLE_SEED,
  VOLUME_SIZE,
  buildCanonicalModes,
  buildFixtures,
  cosineSimilarity,
  decodeEmbedding,
  encodeEmbedding,
  fisherYatesModes,
  float32ToBase64,
  base64ToFloat32,
  getModes,
  joinSignedField,
  maxPairwiseCosineError,
  modeBasisManifest,
  pairwiseCosines,
  relativeL2Error,
  splitSignedField,
} from './cassi-embedding-field-codec.mjs'

const fixtures = buildFixtures()
const board = {
  anchor: fixtures.anchor,
  near: fixtures.near,
  orthogonal: fixtures.orthogonal,
  opposite: fixtures.opposite,
}
const expectedGeometry = pairwiseCosines(board)

function expectFiniteVector(values) {
  for (const value of values) assert.ok(Number.isFinite(value))
}

test('fixed constants expose the preregistered 1536-D, N=32 contract', () => {
  assert.equal(DIMENSION, 1536)
  assert.equal(GRID_N, 32)
  assert.equal(VOLUME_SIZE, 32768)
  assert.equal(MODE_CAPACITY, 768)
  assert.deepEqual(HORIZONS, [0, 1, 4, 16, 64, 256, 1024, 2048])
  assert.equal(PHI, 1.618033988749895)
})

test('Gram-Schmidt fixtures have the expected anchor geometry after float32 rounding', () => {
  assert.ok(Math.abs(cosineSimilarity(board.anchor, board.near) - 0.9) <= 2e-7)
  assert.ok(Math.abs(cosineSimilarity(board.anchor, board.orthogonal)) <= 2e-7)
  assert.ok(Math.abs(cosineSimilarity(board.anchor, board.opposite) + 1) <= 2e-7)
  assert.ok(Math.abs(cosineSimilarity(board.near, board.orthogonal)) <= 2e-7)
  assert.ok(Math.abs(cosineSimilarity(board.near, board.opposite) + 0.9) <= 2e-7)
  expectFiniteVector(board.anchor)
  expectFiniteVector(board.near)
  expectFiniteVector(board.orthogonal)
  expectFiniteVector(board.opposite)
})

test('canonical modes are low-|k|, signed-(kz,ky,kx), one per conjugate pair', () => {
  const all = buildCanonicalModes()
  assert.ok(all.length > MODE_CAPACITY)
  assert.equal(all[0].k2, 1)
  assert.deepEqual([all[0].kz, all[0].ky, all[0].kx], [-1, 0, 0])
  assert.notEqual(all[0].index, all[0].negativeIndex)
  const selected = getModes('canonical')
  assert.equal(selected.length, MODE_CAPACITY)
  const seen = new Set()
  for (const mode of selected) {
    assert.ok(!seen.has(mode.index))
    assert.ok(!seen.has(mode.negativeIndex))
    seen.add(mode.index)
    seen.add(mode.negativeIndex)
  }
})

test('Fisher-Yates shuffled mode order is deterministic and uses the frozen seed', () => {
  const canonical = getModes('canonical')
  const first = fisherYatesModes(canonical, SHUFFLE_SEED)
  const second = fisherYatesModes(canonical, SHUFFLE_SEED)
  assert.deepEqual(first, second)
  assert.notDeepEqual(first.map((mode) => mode.index), canonical.map((mode) => mode.index))
  assert.deepEqual(getModes('shuffled'), first)
  assert.deepEqual(modeBasisManifest().shuffled.modes, first.map(({ x, y, z }) => [x, y, z]))
})

test('C1 canonical encoding decodes all nonzero fixtures with cosine and pairwise gates', () => {
  const decoded = {}
  for (const [id, embedding] of Object.entries(board)) {
    const encoded = encodeEmbedding(embedding, { basis: 'canonical' })
    assert.equal(encoded.signal.length, VOLUME_SIZE)
    assert.equal(encoded.ey.length, VOLUME_SIZE)
    assert.equal(encoded.ei.length, VOLUME_SIZE)
    decoded[id] = decodeEmbedding(encoded, { basis: 'canonical' })
    assert.ok(cosineSimilarity(decoded[id], embedding) >= 0.999999)
    assert.ok(relativeL2Error(decoded[id], embedding) <= 2e-6)
  }
  assert.ok(maxPairwiseCosineError(board, decoded) <= 2e-6)
})

test('repeated canonical encoding is byte-identical at every raw artifact', () => {
  for (const embedding of Object.values(board)) {
    const first = encodeEmbedding(embedding)
    const second = encodeEmbedding(embedding)
    assert.equal(float32ToBase64(first.signal), float32ToBase64(second.signal))
    assert.equal(float32ToBase64(first.ey), float32ToBase64(second.ey))
    assert.equal(float32ToBase64(first.ei), float32ToBase64(second.ei))
  }
})

test('canonical and shuffled basis controls both round-trip their own order', () => {
  for (const embedding of [fixtures.anchor, fixtures.near]) {
    const canonical = encodeEmbedding(embedding, { basis: 'canonical' })
    const shuffled = encodeEmbedding(embedding, { basis: 'shuffled' })
    const decodedCanonical = decodeEmbedding(canonical, { basis: 'canonical' })
    const decodedShuffled = decodeEmbedding(shuffled, { basis: 'shuffled' })
    assert.ok(cosineSimilarity(decodedCanonical, embedding) >= 0.999999)
    assert.ok(cosineSimilarity(decodedShuffled, embedding) >= 0.999999)
    assert.ok(relativeL2Error(decodedCanonical, embedding) <= 2e-6)
    assert.ok(relativeL2Error(decodedShuffled, embedding) <= 2e-6)
    assert.notEqual(float32ToBase64(canonical.signal), float32ToBase64(shuffled.signal))
  }
})

test('float32 signed split and join remain within the declared quantization tolerance', () => {
  const signal = encodeEmbedding(fixtures.anchor).signal
  const split = splitSignedField(signal)
  const joined = joinSignedField(split.ey, split.ei)
  let maximum = 0
  let signalScale = 0
  for (let i = 0; i < VOLUME_SIZE; i += 1) {
    maximum = Math.max(maximum, Math.abs(joined[i] - signal[i]))
    signalScale = Math.max(signalScale, Math.abs(signal[i]))
  }
  assert.ok(maximum <= Math.max(2e-7, signalScale * 2e-6))
  assert.equal(split.ey.length, VOLUME_SIZE)
  assert.equal(split.ei.length, VOLUME_SIZE)
})

test('float32 little-endian base64 round-trips bytes exactly', () => {
  const values = new Float32Array([0, -0, 1, -2.5, Math.PI, Number.MIN_VALUE])
  const text = float32ToBase64(values)
  assert.deepEqual(base64ToFloat32(text), values)
  assert.equal(float32ToBase64(base64ToFloat32(text)), text)
})

test('malformed, non-finite, zero, wrong-size, and capacity-exceeding inputs fail closed', () => {
  assert.throws(() => encodeEmbedding(null), /array or typed array/)
  assert.throws(() => encodeEmbedding(new Float32Array(DIMENSION).fill(Number.NaN)), /finite/)
  assert.throws(() => encodeEmbedding(new Float32Array(DIMENSION)), /non-zero finite L2 norm/)
  assert.throws(() => encodeEmbedding(new Float32Array(DIMENSION - 1).fill(1)), /exactly 1536/)
  assert.throws(() => encodeEmbedding(new Float32Array(DIMENSION + 1).fill(1)), /capacity/)
  assert.throws(() => decodeEmbedding(new Float32Array(VOLUME_SIZE - 1), new Float32Array(VOLUME_SIZE)), /exactly 32768/)
  assert.throws(() => decodeEmbedding(new Float32Array(VOLUME_SIZE).fill(Number.POSITIVE_INFINITY), new Float32Array(VOLUME_SIZE)), /finite/)
  assert.throws(() => base64ToFloat32('not-base64'), /canonical padded base64/)
  assert.throws(() => base64ToFloat32('AAAA'), /multiple of four bytes/)
  assert.throws(() => base64ToFloat32(float32ToBase64(new Float32Array([0])), 2), /length must be 2/)
})

test('zero split control is byte-zero and decodes to a zero coefficient vector', () => {
  const zero = new Float32Array(VOLUME_SIZE)
  const split = splitSignedField(zero)
  assert.equal(float32ToBase64(split.ey), float32ToBase64(zero))
  assert.equal(float32ToBase64(split.ei), float32ToBase64(zero))
  const decoded = decodeEmbedding(split)
  assert.equal(relativeL2Error(decoded, new Float64Array(DIMENSION)), 0)
})
