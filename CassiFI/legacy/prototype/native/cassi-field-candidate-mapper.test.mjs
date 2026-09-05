import assert from 'node:assert/strict'
import test from 'node:test'
import { rankCandidatesByField } from './cassi-field-candidate-mapper.mjs'

const candidates = [
  { id: 'memory-b', text: 'beta' },
  { id: 'memory-a', text: 'alpha' },
  { id: 'memory-c', text: 'gamma' },
]

const l5dProjection = [
  { x: 0.290322580645161, y: -0.354838709677419, z: 0.67741935483871, q: 0.19971212884439 },
  { x: 0.290322580645161, y: -0.419354838709677, z: 0.67741935483871, q: 0.0941064028914262 },
  { x: 0.290322580645161, y: -0.354838709677419, z: 0.612903225806452, q: 0.0941060578995814 },
  { x: 0.290322580645161, y: -0.419354838709677, z: 0.612903225806452, q: 0.0443439469163787 },
  { x: 0.225806451612903, y: -0.354838709677419, z: 0.67741935483871, q: 0.00554844662012527 },
  { x: 0.354838709677419, y: -0.354838709677419, z: 0.67741935483871, q: 0.00554844662012527 },
  { x: 0.225806451612903, y: -0.419354838709677, z: 0.67741935483871, q: 0.00261457884843892 },
  { x: 0.354838709677419, y: -0.419354838709677, z: 0.67741935483871, q: 0.00261457884843892 },
]

test('disabled mode preserves the exact caller order despite malformed projection', () => {
  const result = rankCandidatesByField(candidates, null)
  assert.equal(result.applied, false)
  assert.deepEqual(result.candidates, candidates)
})

test('valid enabled mapping returns a complete deterministic permutation', () => {
  const first = rankCandidatesByField(candidates, l5dProjection, { enabled: true })
  const second = rankCandidatesByField(candidates, l5dProjection, { enabled: true })
  assert.equal(first.applied, true)
  assert.deepEqual(first, second)
  assert.deepEqual([...first.candidates].sort((a, b) => a.id.localeCompare(b.id)), [...candidates].sort((a, b) => a.id.localeCompare(b.id)))
  assert.equal(first.scores.length, candidates.length)
})

test('score ties preserve the caller order', () => {
  const result = rankCandidatesByField(candidates, [{ x: 0, y: 0, z: 0, q: 0 }], { enabled: true })
  assert.deepEqual(result.candidates, candidates)
})

test('projection rank participates in the field fingerprint', () => {
  const first = rankCandidatesByField(candidates, l5dProjection, { enabled: true })
  const reversed = rankCandidatesByField(candidates, [...l5dProjection].reverse(), { enabled: true })
  assert.notDeepEqual(first.scores, reversed.scores)
})

test('invalid projection and duplicate IDs fail closed to caller order', () => {
  const invalidProjection = rankCandidatesByField(candidates, [{ x: 0, y: 0, z: 0, q: -1 }], { enabled: true })
  assert.equal(invalidProjection.applied, false)
  assert.deepEqual(invalidProjection.candidates, candidates)

  const duplicate = rankCandidatesByField([{ id: 'same' }, { id: 'same' }], l5dProjection, { enabled: true })
  assert.equal(duplicate.applied, false)
  assert.deepEqual(duplicate.candidates, [{ id: 'same' }, { id: 'same' }])
})

test('recorded L5d projection maps without a socket or model dependency', () => {
  const result = rankCandidatesByField(candidates, l5dProjection, { enabled: true })
  assert.equal(result.applied, true)
  assert.ok(result.scores.some((score) => score.score > 0))
})
