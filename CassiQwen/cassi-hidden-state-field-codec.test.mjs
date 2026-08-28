import assert from 'node:assert/strict'
import test from 'node:test'

import {
  GRID_N,
  L16_DIMENSION,
  L16_MODE_CAPACITY,
  cosineSimilarity,
  decodeEmbedding,
  encodeEmbedding,
  getModes,
  l2Norm,
  normalizeEmbeddingWithNorm,
  relativeL2Error,
  restoreEmbeddingNorm,
  subspaceResidualEnergy,
} from './cassi-embedding-field-codec.mjs'

const OPTIONS = Object.freeze({
  dimension: L16_DIMENSION,
  capacity: L16_DIMENSION,
  gridN: GRID_N,
})

function hiddenFixture() {
  const values = new Float32Array(L16_DIMENSION)
  for (let index = 0; index < values.length; index += 1) {
    values[index] = Math.sin(index * 0.017) + 0.25 * Math.cos(index * 0.071)
  }
  return values
}

test('L16 capacity holds the complete 5120-D hidden state', () => {
  assert.equal(L16_MODE_CAPACITY, 2560)
  assert.equal(getModes('canonical', L16_MODE_CAPACITY, GRID_N).length, L16_MODE_CAPACITY)
})

test('L16 canonical field preserves hidden direction and separately carried norm', () => {
  const hidden = hiddenFixture()
  const normalized = normalizeEmbeddingWithNorm(hidden, OPTIONS)
  const encoded = encodeEmbedding(hidden, { ...OPTIONS, basis: 'canonical' })
  const decoded = decodeEmbedding(encoded, { ...OPTIONS, basis: 'canonical' })
  const restored = restoreEmbeddingNorm(decoded, normalized.norm, OPTIONS)

  assert.ok(Math.abs(l2Norm(encoded.signal) - 1) <= 2e-6)
  assert.ok(cosineSimilarity(decoded, normalized.vector) >= 0.999999)
  assert.ok(relativeL2Error(restored, hidden) <= 2e-6)
  assert.ok(subspaceResidualEnergy({ ey: encoded.ey, ei: encoded.ei }, 'canonical', OPTIONS) <= 2e-12)
})

test('L16 shuffled field has a deterministic independent mode allocation', () => {
  const hidden = hiddenFixture()
  const first = encodeEmbedding(hidden, { ...OPTIONS, basis: 'shuffled' })
  const second = encodeEmbedding(hidden, { ...OPTIONS, basis: 'shuffled' })
  const decoded = decodeEmbedding(first, { ...OPTIONS, basis: 'shuffled' })
  const normalized = normalizeEmbeddingWithNorm(hidden, OPTIONS)

  assert.deepEqual([...first.signal], [...second.signal])
  assert.deepEqual(first.modes.map(({ x, y, z }) => [x, y, z]), second.modes.map(({ x, y, z }) => [x, y, z]))
  assert.ok(cosineSimilarity(decoded, normalized.vector) >= 0.999999)
})

test('L16 rejects wrong-sized, non-finite, zero, and over-capacity hidden states', () => {
  assert.throws(() => encodeEmbedding(new Float32Array(L16_DIMENSION - 1), OPTIONS), /exactly 5120/)
  assert.throws(() => encodeEmbedding(new Float32Array(L16_DIMENSION + 1), OPTIONS), /capacity/)
  const nonFinite = hiddenFixture()
  nonFinite[17] = Number.NaN
  assert.throws(() => encodeEmbedding(nonFinite, OPTIONS), /finite/)
  assert.throws(() => encodeEmbedding(new Float32Array(L16_DIMENSION), OPTIONS), /non-zero finite L2 norm/)
  assert.throws(() => restoreEmbeddingNorm(new Float64Array(L16_DIMENSION), 0, OPTIONS), /positive/)
})
