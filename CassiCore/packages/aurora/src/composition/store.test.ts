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
})
