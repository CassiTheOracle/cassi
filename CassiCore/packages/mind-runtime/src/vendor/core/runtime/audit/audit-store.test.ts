import { describe, expect, it } from 'vitest'
import path from 'node:path'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'

import { MnemicField } from '@cassicore/mnemic-field'
import { AuditStore } from './audit-store.js'
import type { ILogger } from '@cassicore/foundation'

function logger(): ILogger {
  return {
    debug: () => {},
    info: () => {},
    warn: () => {},
    error: () => {},
    child: () => logger(),
  }
}

describe('AuditStore replay bridge', () => {
  it('writes run and step replay engrams with membership and temporal links', () => {
    const dir = mkdtempSync(path.join(tmpdir(), 'cassicore-audit-replay-'))
    const audit = new AuditStore(logger(), path.join(dir, 'audit.db'))
    const field = new MnemicField(logger(), ':memory:')
    audit.setMnemicField(field)

    const run = audit.startRun({ kind: 'turn', sessionId: 's1', agentId: 'primary', goal: 'answer user' })
    const step1 = audit.startStep({ runId: run.id, slot: 'primary', model: 'm1', reason: 'first' })
    const step2 = audit.startStep({ runId: run.id, slot: 'primary', model: 'm1', reason: 'second' })
    audit.finishStep(step1.id, { status: 'completed', toolCallCount: 2 })
    audit.finishStep(step2.id, { status: 'failed' })
    audit.finishRun(run.id, 'failed')

    const runId = `run:${run.id}`
    const stepOneId = `step:${run.id}:1`
    const stepTwoId = `step:${run.id}:2`

    expect(field.get('session:s1')?.nodeType).toBe('session')
    expect(field.get(runId)?.nodeType).toBe('goal')
    expect(field.get(stepOneId)?.metadata).toMatchObject({ auditStepId: step1.id, toolCallCount: 2 })
    expect(field.replayRun(run.id).map(e => e.id)).toEqual([runId, stepOneId, stepTwoId])

    const graph = field.getReplaySubgraph('session:s1')
    expect(graph.synapses.map(s => `${s.sourceId}->${s.targetId}:${s.edgeType}`)).toContain(`${runId}->session:s1:part_of`)
    expect(graph.synapses.map(s => `${s.sourceId}->${s.targetId}:${s.edgeType}`)).toContain(`${stepOneId}->${stepTwoId}:temporal_neighbor`)

    audit.close()
    field.close()
    rmSync(dir, { recursive: true, force: true })
  })

  it('keeps audit writes working when replay bridge fails', () => {
    const dir = mkdtempSync(path.join(tmpdir(), 'cassicore-audit-replay-fail-'))
    const audit = new AuditStore(logger(), path.join(dir, 'audit.db'))
    const failingField = {
      get: () => null,
      store: () => { throw new Error('mnemic unavailable') },
    } as unknown as MnemicField
    audit.setMnemicField(failingField)

    const run = audit.startRun({ kind: 'turn', sessionId: 's2', agentId: 'primary' })
    const step = audit.startStep({ runId: run.id, slot: 'primary' })
    audit.finishStep(step.id)
    audit.finishRun(run.id)

    expect(audit.getRun(run.id)?.status).toBe('completed')
    expect(audit.getStep(step.id)?.status).toBe('completed')

    audit.close()
    rmSync(dir, { recursive: true, force: true })
  })
})
