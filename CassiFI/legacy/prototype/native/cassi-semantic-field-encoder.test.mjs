import assert from 'node:assert/strict'
import test from 'node:test'
import { encodeActionCandidates, ROLE_COORDINATES } from './cassi-semantic-field-encoder.mjs'

function candidate(id, kind, overrides = {}) {
  return {
    id,
    kind,
    support: 0.6,
    goalAlignment: 0.3,
    urgency: 0.9,
    contradiction: 0.2,
    missingInformation: 0.4,
    risk: 0.1,
    cost: 0.7,
    ...overrides,
  }
}

const board = [
  candidate('answer-id', 'answer'),
  candidate('retrieve-id', 'retrieve'),
  candidate('clarify-id', 'clarify'),
]

test('disabled mode returns no deposits without inspecting malformed input', () => {
  assert.deepEqual(encodeActionCandidates(null), { applied: false, reason: 'semantic field encoding is disabled', deposits: [] })
})

test('valid candidates produce bounded finite deposits with preserved IDs', () => {
  const result = encodeActionCandidates(board, { enabled: true })
  assert.equal(result.applied, true)
  assert.deepEqual(result.deposits.map((deposit) => deposit.id).sort(), ['answer-id', 'clarify-id', 'retrieve-id'])
  for (const deposit of result.deposits) {
    for (const value of [deposit.x, deposit.y, deposit.z, deposit.cy, deposit.ci, deposit.sigma]) assert.ok(Number.isFinite(value))
    assert.ok(deposit.cy >= 0 && deposit.cy <= 1)
    assert.ok(deposit.ci >= 0 && deposit.ci <= 1)
  }
})

test('role coordinates and channel formulae are exact', () => {
  const source = candidate('answer-id', 'answer', {
    support: 0.6, goalAlignment: 0.3, urgency: 0.9,
    contradiction: 0.2, missingInformation: 0.4, risk: 0.1, cost: 0.7,
  })
  const [deposit] = encodeActionCandidates([source], { enabled: true }).deposits
  assert.deepEqual({ x: deposit.x, y: deposit.y, z: deposit.z }, ROLE_COORDINATES.answer)
  assert.equal(deposit.cy, 0.6)
  assert.equal(deposit.ci, 0.35)
  assert.equal(deposit.sigma, 1)
})

test('candidate permutation preserves candidate-to-deposit associations in canonical kind order', () => {
  const first = encodeActionCandidates(board, { enabled: true })
  const second = encodeActionCandidates([...board].reverse(), { enabled: true })
  assert.deepEqual(first, second)
})

test('duplicate roles, duplicate IDs, non-finite, and out-of-range values fail closed', () => {
  for (const malformed of [
    [candidate('a', 'answer'), candidate('b', 'answer')],
    [candidate('same', 'answer'), candidate('same', 'retrieve')],
    [candidate('a', 'answer', { support: Number.NaN })],
    [candidate('a', 'answer', { cost: 1.1 })],
  ]) {
    const result = encodeActionCandidates(malformed, { enabled: true })
    assert.equal(result.applied, false)
    assert.deepEqual(result.deposits, [])
  }
})

test('all-zero features retain geometry with zero channels', () => {
  const result = encodeActionCandidates([candidate('stop-id', 'stop', {
    support: 0, goalAlignment: 0, urgency: 0, contradiction: 0, missingInformation: 0, risk: 0, cost: 0,
  })], { enabled: true })
  assert.equal(result.applied, true)
  assert.deepEqual(result.deposits[0], {
    id: 'stop-id', kind: 'stop', ...ROLE_COORDINATES.stop, cy: 0, ci: 0, sigma: 1,
    features: { support: 0, goalAlignment: 0, urgency: 0, contradiction: 0, missingInformation: 0, risk: 0, cost: 0 },
  })
})
