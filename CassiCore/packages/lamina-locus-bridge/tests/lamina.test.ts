import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { AuditStore, withStep } from '../src/vendor/core/runtime/audit/index.js'
import { LaminaField } from '../src/lamina/index.js'
import { LaminaCasConflict, LaminaOverflow, LaminaAuthorityError } from '../src/lamina/types.js'
import { LaminaStore } from '../src/lamina/lamina-store.js'

import type { ILogger } from '@cassicore/foundation'

function silentLogger(): ILogger {
  const make = () => () => undefined as unknown as void
  const l: ILogger = {
    debug: make(), info: make(), warn: make(), error: make(),
    child: () => l,
  }
  return l
}

describe('Lamina foundation (PR-1.1)', () => {
  let tmpDir: string
  let auditDb: string
  let laminaDb: string
  let logger: ILogger

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'lamina-test-'))
    auditDb = path.join(tmpDir, 'audit.db')
    laminaDb = path.join(tmpDir, 'lamina.db')
    logger = silentLogger()
  })

  afterEach(() => {
    try { fs.rmSync(tmpDir, { recursive: true, force: true }) } catch { /* ignore */ }
  })

  it('records runs and steps with monotonic numbering', () => {
    const audit = new AuditStore(logger, auditDb)
    const run = audit.startRun({ kind: 'turn', agentId: 'primary', sessionId: 's1' })
    const s1 = audit.startStep({ runId: run.id, slot: 'primary', model: 'm', reason: 'first' })
    const s2 = audit.startStep({ runId: run.id, slot: 'primary' })
    expect(s1.stepNumber).toBe(1)
    expect(s2.stepNumber).toBe(2)
    audit.finishStep(s1.id, { status: 'completed' })
    audit.finishStep(s2.id, { status: 'completed', toolCallCount: 3 })
    audit.finishRun(run.id, 'completed')
    const all = audit.listSteps(run.id)
    expect(all.length).toBe(2)
    expect(all[1].toolCallCount).toBe(3)
    expect(audit.metrics().runs).toBe(1)
    expect(audit.metrics().steps).toBe(2)
    audit.close()
  })

  it('attaches step provenance to lamina writes via AsyncLocalStorage', () => {
    const audit = new AuditStore(logger, auditDb)
    const store = new LaminaStore(logger, { dbPath: laminaDb })
    const field = new LaminaField(logger, store)

    const run = audit.startRun({ kind: 'turn', agentId: 'primary' })
    const step = audit.startStep({ runId: run.id, slot: 'primary' })

    let lamina = withStep({ runId: run.id, stepId: step.id, agentId: 'primary' }, () => {
      return field.create({ label: 'task', content: 'first', owner: 'primary' }, 'primary')
    })
    expect(lamina.lastWriteProvenance?.runId).toBe(run.id)
    expect(lamina.lastWriteProvenance?.stepId).toBe(step.id)

    // Append in a new step
    const step2 = audit.startStep({ runId: run.id, slot: 'primary' })
    lamina = withStep({ runId: run.id, stepId: step2.id, agentId: 'primary' }, () => {
      return field.append('task', { content: 'second' }, 'primary')
    })
    expect(lamina.content).toBe('first\nsecond')
    expect(lamina.lastWriteProvenance?.stepId).toBe(step2.id)
    expect(lamina.version).toBe(2)

    store.close()
    audit.close()
  })

  it('enforces CAS via contentHash on replace', () => {
    const store = new LaminaStore(logger, { dbPath: laminaDb })
    const field = new LaminaField(logger, store)
    const created = field.create({ label: 'task', content: 'A', owner: 'primary' }, 'primary')
    expect(() =>
      field.replace('task', { expectedHash: 'wrong-hash', content: 'B' }, 'primary'),
    ).toThrowError(LaminaCasConflict)

    const updated = field.replace('task', { expectedHash: created.contentHash, content: 'B' }, 'primary')
    expect(updated.content).toBe('B')
    expect(updated.version).toBe(2)
    store.close()
  })

  it('rejects writes that overflow charLimit', () => {
    const store = new LaminaStore(logger, { dbPath: laminaDb })
    const field = new LaminaField(logger, store)
    field.create({ label: 'small', owner: 'primary', charLimit: 10, content: '' }, 'primary')
    expect(() =>
      field.append('small', { content: 'this is way too long for the limit' }, 'primary'),
    ).toThrowError(LaminaOverflow)
    store.close()
  })

  it('owner-exclusive laminae block rethink from non-owners but allow append', () => {
    const store = new LaminaStore(logger, { dbPath: laminaDb })
    const field = new LaminaField(logger, store)
    field.create({ label: 'user-model', owner: 'reverie', ownerExclusive: true, content: 'initial' }, 'reverie')

    // Primary can append (owner-exclusive only blocks rethink)
    const appended = field.append('user-model', { content: 'observation' }, 'primary')
    expect(appended.content).toContain('observation')

    // Primary cannot rethink
    expect(() =>
      field.rethink('user-model', { content: 'new model', reason: 'test' }, 'primary'),
    ).toThrowError(LaminaAuthorityError)

    // Reverie can rethink
    const re = field.rethink('user-model', { content: 'new model', reason: 'consolidation' }, 'reverie')
    expect(re.content).toBe('new model')
    store.close()
  })

  it('read-only laminae block all writes from non-owners', () => {
    const store = new LaminaStore(logger, { dbPath: laminaDb })
    const field = new LaminaField(logger, store)
    field.mirrorReadOnly({ label: 'identity', content: 'I am Cassi.', owner: 'pineal' })
    expect(() =>
      field.append('identity', { content: 'tamper' }, 'primary'),
    ).toThrowError(LaminaAuthorityError)

    // Mirror update by the owner is allowed (idempotent re-mirror)
    const re = field.mirrorReadOnly({ label: 'identity', content: 'I am Cassi. Updated.', owner: 'pineal' })
    expect(re.content).toContain('Updated')
    store.close()
  })

  it('seedDefaults is idempotent', () => {
    const store = new LaminaStore(logger, { dbPath: laminaDb })
    const field = new LaminaField(logger, store)
    const first = field.seedDefaults()
    const second = field.seedDefaults()
    expect(first).toBeGreaterThan(0)
    expect(second).toBe(0)
    store.close()
  })

  it('scopes laminae per session and merges with globals via matchScope', () => {
    const store = new LaminaStore(logger, { dbPath: laminaDb })
    const field = new LaminaField(logger, store)
    field.create({ label: 'goal', owner: 'primary', content: 'global', scope: { kind: 'global' } }, 'primary')
    field.create({ label: 'goal', owner: 'primary', content: 'session-A', scope: { kind: 'session', sessionId: 'A' } }, 'primary')
    field.create({ label: 'goal', owner: 'primary', content: 'session-B', scope: { kind: 'session', sessionId: 'B' } }, 'primary')

    const results = field.list({ matchScope: { kind: 'session', sessionId: 'A' } })
    const labels = results.map(l => `${l.scope.kind}:${l.content}`).sort()
    expect(labels).toContain('global:global')
    expect(labels).toContain('session:session-A')
    expect(labels).not.toContain('session:session-B')
    store.close()
  })
})
