/**
 * B1 CompositionStore tests — schema initialization, CRUD, invocation log.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import * as fs from 'fs'

import { CompositionStore } from './store.js'
import type { CompositionAst } from './types.js'

function makeLogger() {
  const log: any = { debug: () => {}, info: () => {}, warn: () => {}, error: () => {} }
  log.child = () => log
  return log
}

describe('CompositionStore', () => {
  let dbPath: string
  let store: CompositionStore

  beforeEach(() => {
    dbPath = `/tmp/aurora-composition-test-${Date.now()}-${Math.random().toString(36).slice(2)}.db`
    store = new CompositionStore(dbPath, makeLogger())
  })

  afterEach(() => {
    store.close()
    try { fs.unlinkSync(dbPath) } catch { /* ignore */ }
    try { fs.unlinkSync(`${dbPath}-wal`) } catch { /* ignore */ }
    try { fs.unlinkSync(`${dbPath}-shm`) } catch { /* ignore */ }
  })

  const sampleAst: CompositionAst = {
    kind: 'sum',
    operands: [
      { kind: 'gate', label: 'calm' },
      { kind: 'gate', label: 'focus' },
      { kind: 'scaled', operand: { kind: 'gate', label: 'reactivity' }, factor: -1 },
    ],
  }

  it('upserts and reads back a composition', () => {
    const rec = store.upsertComposition({
      name: 'calm_focus',
      dsl: 'calm_focus = gate("calm") + gate("focus") - gate("reactivity")',
      ast: sampleAst,
      layerPolicy: 'all',
      affectModulated: false,
      suppressive: false,
      vindexId: 'default',
      description: 'long-horizon strategic posture',
      metadata: { author: 'cassi' },
    })
    expect(rec.createdAt).toBeTruthy()

    const got = store.getComposition('calm_focus')
    expect(got).not.toBeNull()
    expect(got?.dsl).toContain('gate("calm") + gate("focus")')
    expect(got?.ast).toEqual(sampleAst)
    expect(got?.metadata).toEqual({ author: 'cassi' })
  })

  it('updates an existing composition (preserves createdAt, bumps updatedAt)', async () => {
    const first = store.upsertComposition({
      name: 'p',
      dsl: 'p = gate("a")',
      ast: { kind: 'gate', label: 'a' },
      layerPolicy: 'all',
      affectModulated: false,
      suppressive: false,
      vindexId: 'default',
      description: null,
      metadata: {},
    })
    await new Promise(r => setTimeout(r, 5))
    const second = store.upsertComposition({
      name: 'p',
      dsl: 'p = gate("a") + gate("b")',
      ast: { kind: 'sum', operands: [{ kind: 'gate', label: 'a' }, { kind: 'gate', label: 'b' }] },
      layerPolicy: 'all',
      affectModulated: false,
      suppressive: false,
      vindexId: 'default',
      description: null,
      metadata: {},
      createdAt: first.createdAt,
    })
    const got = store.getComposition('p')
    expect(got?.createdAt).toBe(first.createdAt)
    expect(got?.updatedAt).not.toBe(first.createdAt)
    expect(got?.dsl).toContain('+ gate("b")')
    expect(second.updatedAt >= first.updatedAt).toBe(true)
  })

  it('lists compositions alphabetically', () => {
    for (const name of ['zeta', 'alpha', 'mu']) {
      store.upsertComposition({
        name, dsl: `${name} = gate("x")`, ast: { kind: 'gate', label: 'x' },
        layerPolicy: 'all', affectModulated: false, suppressive: false,
        vindexId: 'default', description: null, metadata: {},
      })
    }
    expect(store.listCompositions().map(c => c.name)).toEqual(['alpha', 'mu', 'zeta'])
  })

  it('deletes a composition', () => {
    store.upsertComposition({
      name: 'tmp', dsl: 'tmp = gate("x")', ast: { kind: 'gate', label: 'x' },
      layerPolicy: 'all', affectModulated: false, suppressive: false,
      vindexId: 'default', description: null, metadata: {},
    })
    expect(store.deleteComposition('tmp')).toBe(true)
    expect(store.deleteComposition('tmp')).toBe(false)
    expect(store.getComposition('tmp')).toBeNull()
  })

  it('records invocations and lists them newest-first', () => {
    store.upsertComposition({
      name: 'p', dsl: 'p = gate("x")', ast: { kind: 'gate', label: 'x' },
      layerPolicy: 'all', affectModulated: false, suppressive: false,
      vindexId: 'default', description: null, metadata: {},
    })
    const a = store.recordInvocation({ name: 'p', sessionId: 's1', trigger: 'manual' })
    const b = store.recordInvocation({ name: 'p', sessionId: 's2', trigger: 'manual', resolvedNorm: 0.42 })
    const log = store.listInvocations({ limit: 10 })
    expect(log).toHaveLength(2)
    expect(log[0].id).toBe(b.id)
    expect(log[0].resolvedNorm).toBe(0.42)
    expect(log[1].id).toBe(a.id)
  })

  it('cascades invocation deletion when composition is deleted', () => {
    store.upsertComposition({
      name: 'p', dsl: 'p = gate("x")', ast: { kind: 'gate', label: 'x' },
      layerPolicy: 'all', affectModulated: false, suppressive: false,
      vindexId: 'default', description: null, metadata: {},
    })
    store.recordInvocation({ name: 'p', trigger: 'manual' })
    store.deleteComposition('p')
    expect(store.listInvocations()).toEqual([])
  })

  it('B2.2 — persists and retrieves a retrieval policy', () => {
    store.upsertComposition({
      name: 'careful',
      dsl: 'careful = gate("rigor") with retrieval(consonant, 0.3)',
      ast: sampleAst,
      layerPolicy: 'all',
      affectModulated: false,
      suppressive: false,
      vindexId: 'default',
      description: null,
      metadata: {},
      retrievalPolicy: { mode: 'consonant', strength: 0.3 },
    })
    const got = store.getComposition('careful')!
    expect(got.retrievalPolicy).toEqual({ mode: 'consonant', strength: 0.3 })
  })

  it('B2.2 — null retrievalPolicy roundtrips as null', () => {
    store.upsertComposition({
      name: 'plain',
      dsl: 'plain = gate("a")',
      ast: sampleAst,
      layerPolicy: 'all',
      affectModulated: false,
      suppressive: false,
      vindexId: 'default',
      description: null,
      metadata: {},
      retrievalPolicy: null,
    })
    expect(store.getComposition('plain')!.retrievalPolicy).toBeNull()
  })

  it('B2.2 — upsert replaces retrieval policy on conflict', () => {
    const base = {
      name: 'p',
      dsl: '',
      ast: sampleAst,
      layerPolicy: 'all',
      affectModulated: false,
      suppressive: false,
      vindexId: 'default',
      description: null,
      metadata: {},
    }
    store.upsertComposition({ ...base, retrievalPolicy: { mode: 'consonant', strength: 0.3 } })
    store.upsertComposition({ ...base, retrievalPolicy: { mode: 'complementary', strength: 0.5 } })
    const got = store.getComposition('p')!
    expect(got.retrievalPolicy).toEqual({ mode: 'complementary', strength: 0.5 })
  })

  it('B1.3 — upserts and retrieves an invocation rule', () => {
    const r = store.upsertInvocationRule({
      id: 'feedback_review_mode',
      topicKeywords: ['review', 'feedback', 'critique'],
      composition: 'honest_but_kind',
      ttlTurns: 10,
      magnitudeScale: 0.8,
      description: 'Activate honest_but_kind during reviews',
    })
    expect(r.updatedAt).toBeTruthy()

    const got = store.getInvocationRule('feedback_review_mode')!
    expect(got.topicKeywords).toEqual(['review', 'feedback', 'critique'])
    expect(got.composition).toBe('honest_but_kind')
    expect(got.ttlTurns).toBe(10)
    expect(got.magnitudeScale).toBeCloseTo(0.8, 6)
    expect(got.description).toBe('Activate honest_but_kind during reviews')
  })

  it('B1.3 — getInvocationRule returns null for unknown id', () => {
    expect(store.getInvocationRule('does-not-exist')).toBeNull()
  })

  it('B1.3 — listInvocationRules returns sorted-by-id', () => {
    store.upsertInvocationRule({ id: 'b', topicKeywords: ['x'], composition: 'c1', updatedAt: '2026-01-01T00:00:00Z' })
    store.upsertInvocationRule({ id: 'a', topicKeywords: ['y'], composition: 'c2', updatedAt: '2026-01-01T00:00:00Z' })
    expect(store.listInvocationRules().map(r => r.id)).toEqual(['a', 'b'])
  })

  it('B1.3 — deleteInvocationRule reports success/failure', () => {
    store.upsertInvocationRule({ id: 'r', topicKeywords: ['x'], composition: 'c', updatedAt: '2026-01-01T00:00:00Z' })
    expect(store.deleteInvocationRule('r')).toBe(true)
    expect(store.deleteInvocationRule('r')).toBe(false)
    expect(store.getInvocationRule('r')).toBeNull()
  })

  it('B1.3 — upsert replaces an existing rule on conflict', () => {
    store.upsertInvocationRule({ id: 'r', topicKeywords: ['old'], composition: 'c-old', updatedAt: '2026-01-01T00:00:00Z' })
    store.upsertInvocationRule({ id: 'r', topicKeywords: ['new'], composition: 'c-new', updatedAt: '2026-02-01T00:00:00Z' })
    const got = store.getInvocationRule('r')!
    expect(got.topicKeywords).toEqual(['new'])
    expect(got.composition).toBe('c-new')
  })
})
