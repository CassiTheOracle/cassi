// HOST-WIRED: requires CassiCore daemon runtime; excluded from default vitest run.

import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { AuditStore } from '../../core/runtime/audit/index.js'
import { LaminaField } from '../../core/intelligence/lamina/index.js'
import { LaminaStore } from '../../core/intelligence/lamina/lamina-store.js'
import { GlobalWorkspace } from '../../core/intelligence/workspace/global-workspace.js'
import {
  HELIX_GOAL_AUG_CAP,
  HELIX_GOAL_CHAR_LIMIT,
  HELIX_GOAL_LABEL,
  HELIX_GOAL_OWNER,
  appendCoordinationLine,
  appendMentorFlagLine,
  publishHelixGoalSignal,
  rethinkHelixGoalLamina,
  rethinkHelixGoalMidFlight,
  seedHelixGoalLamina,
  trimAugLines,
} from '../../core/intelligence/constellation/helix-goal-lamina.js'

import type { GoalSubTask } from '../../core/intelligence/constellation/corpus-types.js'
import type { ILogger } from '../../types/interfaces.js'

function silentLogger(): ILogger {
  const make = () => () => undefined as unknown as void
  const l: ILogger = {
    debug: make(), info: make(), warn: make(), error: make(),
    child: () => l,
  }
  return l
}

function makeSubTask(overrides: Partial<GoalSubTask> = {}): GoalSubTask {
  return {
    goal: 'Add rate limiting to admin API',
    relevantFiles: ['core/admin-api/index.ts', 'core/admin-api/middleware.ts'],
    budgetSteps: 30,
    priority: 1,
    ...overrides,
  }
}

describe('helix-goal-lamina (PR-1)', () => {
  let tmpDir: string
  let logger: ILogger
  let lamina: LaminaField

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'helix-goal-lamina-test-'))
    const auditDb = path.join(tmpDir, 'audit.db')
    const laminaDb = path.join(tmpDir, 'lamina.db')
    logger = silentLogger()
    new AuditStore(logger, auditDb)
    const store = new LaminaStore(logger, { dbPath: laminaDb })
    lamina = new LaminaField(logger, store)
  })

  afterEach(() => {
    try { fs.rmSync(tmpDir, { recursive: true, force: true }) } catch { /* ignore */ }
  })

  it('seeds a session-scoped lamina with the expected content', () => {
    const helixId = 'helix-test-1'
    const subTask = makeSubTask()

    seedHelixGoalLamina(lamina, helixId, subTask)

    const entry = lamina.read(HELIX_GOAL_LABEL, { kind: 'session', sessionId: helixId })
    expect(entry).not.toBeNull()
    expect(entry?.label).toBe(HELIX_GOAL_LABEL)
    expect(entry?.owner).toBe(HELIX_GOAL_OWNER)
    expect(entry?.charLimit).toBe(HELIX_GOAL_CHAR_LIMIT)
    expect(entry?.scope).toEqual({ kind: 'session', sessionId: helixId })
    expect(entry?.content).toContain('GOAL: Add rate limiting to admin API')
    expect(entry?.content).toContain('Relevant files: core/admin-api/index.ts, core/admin-api/middleware.ts')
    expect(entry?.content).toContain('Budget: 30 steps')
  })

  it('seeds without optional fields when subTask has no relevantFiles or budget', () => {
    const helixId = 'helix-test-minimal'
    const subTask = makeSubTask({ relevantFiles: undefined, budgetSteps: undefined })

    seedHelixGoalLamina(lamina, helixId, subTask)

    const entry = lamina.read(HELIX_GOAL_LABEL, { kind: 'session', sessionId: helixId })
    expect(entry?.content).toContain('GOAL: Add rate limiting to admin API')
    expect(entry?.content).not.toContain('Relevant files:')
    expect(entry?.content).not.toContain('Budget:')
  })

  it('is idempotent — calling seed twice does not error or duplicate', () => {
    const helixId = 'helix-test-idempotent'
    const subTask = makeSubTask()

    seedHelixGoalLamina(lamina, helixId, subTask)
    const first = lamina.read(HELIX_GOAL_LABEL, { kind: 'session', sessionId: helixId })
    expect(first).not.toBeNull()

    expect(() => seedHelixGoalLamina(lamina, helixId, subTask)).not.toThrow()

    const second = lamina.read(HELIX_GOAL_LABEL, { kind: 'session', sessionId: helixId })
    expect(second?.id).toBe(first?.id)
  })

  it('isolates parallel Helixes by sessionId — distinct laminae per Helix', () => {
    const subTaskA = makeSubTask({ goal: 'Task A', relevantFiles: ['a.ts'] })
    const subTaskB = makeSubTask({ goal: 'Task B', relevantFiles: ['b.ts'] })

    seedHelixGoalLamina(lamina, 'helix-a', subTaskA)
    seedHelixGoalLamina(lamina, 'helix-b', subTaskB)

    const a = lamina.read(HELIX_GOAL_LABEL, { kind: 'session', sessionId: 'helix-a' })
    const b = lamina.read(HELIX_GOAL_LABEL, { kind: 'session', sessionId: 'helix-b' })

    expect(a?.content).toContain('GOAL: Task A')
    expect(a?.content).toContain('Relevant files: a.ts')
    expect(b?.content).toContain('GOAL: Task B')
    expect(b?.content).toContain('Relevant files: b.ts')
    expect(a?.id).not.toBe(b?.id)
  })

  it('rethinks on terminal completed status with outcome', () => {
    const helixId = 'helix-terminal-completed'
    const subTask = makeSubTask()

    seedHelixGoalLamina(lamina, helixId, subTask)
    const beforeVersion = lamina.read(HELIX_GOAL_LABEL, { kind: 'session', sessionId: helixId })?.version

    rethinkHelixGoalLamina(lamina, helixId, subTask, 'completed', 'Implemented rate limiter with 60req/min cap')

    const after = lamina.read(HELIX_GOAL_LABEL, { kind: 'session', sessionId: helixId })
    expect(after?.content).toContain('GOAL: Add rate limiting to admin API')
    expect(after?.content).toMatch(/\[completed at \d{4}-\d{2}-\d{2}T/)
    expect(after?.content).toContain('Implemented rate limiter with 60req/min cap')
    expect(after?.version).toBeGreaterThan(beforeVersion ?? 0)
  })

  it('rethinks on terminal failed status without outcome', () => {
    const helixId = 'helix-terminal-failed'
    const subTask = makeSubTask()

    seedHelixGoalLamina(lamina, helixId, subTask)
    rethinkHelixGoalLamina(lamina, helixId, subTask, 'failed')

    const after = lamina.read(HELIX_GOAL_LABEL, { kind: 'session', sessionId: helixId })
    expect(after?.content).toContain('GOAL: Add rate limiting to admin API')
    expect(after?.content).toMatch(/\[failed at \d{4}-\d{2}-\d{2}T/)
  })

  it('seed is a no-op when lamina is undefined', () => {
    expect(() => seedHelixGoalLamina(undefined, 'helix-x', makeSubTask())).not.toThrow()
  })

  it('rethink is a no-op when lamina is undefined', () => {
    expect(() => rethinkHelixGoalLamina(undefined, 'helix-x', makeSubTask(), 'completed')).not.toThrow()
  })
})

describe('helix-goal signal publish (PR-1 territory-awareness)', () => {
  let logger: ILogger
  let workspace: GlobalWorkspace

  beforeEach(() => {
    logger = silentLogger()
    workspace = new GlobalWorkspace(logger)
  })

  it('publishes a goal signal with seed kind, source, sessionId, and metadata', () => {
    const helixId = 'helix-abc123def456'
    const subTask = makeSubTask()

    publishHelixGoalSignal(workspace, 'c-1', helixId, subTask, 'seed')

    const foci = workspace.getCurrentFoci()
    expect(foci.length).toBe(1)
    const sig = foci[0]
    expect(sig.type).toBe('goal')
    expect(sig.source).toBe('helix')
    expect(sig.sessionId).toBe(helixId)
    expect(sig.content).toContain('Working on: Add rate limiting to admin API')
    expect(sig.content).toContain('Files: core/admin-api/index.ts, core/admin-api/middleware.ts')
    expect(sig.metadata).toMatchObject({
      constellationId: 'c-1',
      helixId,
      relevantFiles: subTask.relevantFiles,
      budgetSteps: 30,
      kind: 'seed',
    })
  })

  it('publishes a completed signal with truncated outcome tail', () => {
    const subTask = makeSubTask()
    const longOutcome = 'shipped X with caveats '.repeat(20)

    publishHelixGoalSignal(workspace, 'c-1', 'helix-1', subTask, 'completed', longOutcome)

    const foci = workspace.getCurrentFoci()
    expect(foci.length).toBe(1)
    const sig = foci[0]
    expect(sig.content.startsWith('Completed: Add rate limiting to admin API')).toBe(true)
    expect(sig.content).toContain('shipped X with caveats')
    expect(sig.content.length).toBeLessThanOrEqual(`Completed: ${subTask.goal}: `.length + 200)
    expect(sig.metadata).toMatchObject({ kind: 'completed' })
  })

  it('publishes a failed signal with no outcome tail', () => {
    const subTask = makeSubTask()
    publishHelixGoalSignal(workspace, 'c-1', 'helix-1', subTask, 'failed')

    const foci = workspace.getCurrentFoci()
    expect(foci.length).toBe(1)
    expect(foci[0].content).toBe(`Failed: ${subTask.goal}`)
    expect(foci[0].metadata).toMatchObject({ kind: 'failed' })
  })

  it('is a no-op when workspace is undefined', () => {
    expect(() => publishHelixGoalSignal(undefined, 'c-1', 'helix-1', makeSubTask(), 'seed')).not.toThrow()
  })

  it('preserves relevantFiles and budgetSteps in signal metadata round-trip', () => {
    const subTask = makeSubTask({
      relevantFiles: ['a.ts', 'b.ts', 'c.ts'],
      budgetSteps: 42,
    })
    publishHelixGoalSignal(workspace, 'c-9', 'helix-roundtrip', subTask, 'seed')

    const sig = workspace.getCurrentFoci()[0]
    expect(sig.metadata?.relevantFiles).toEqual(['a.ts', 'b.ts', 'c.ts'])
    expect(sig.metadata?.budgetSteps).toBe(42)
    expect(sig.metadata?.constellationId).toBe('c-9')
    expect(sig.metadata?.helixId).toBe('helix-roundtrip')
  })

  it('handles missing optional fields without emitting Files: line', () => {
    const subTask = makeSubTask({ relevantFiles: undefined, budgetSteps: undefined })
    publishHelixGoalSignal(workspace, 'c-1', 'helix-1', subTask, 'seed')

    const sig = workspace.getCurrentFoci()[0]
    expect(sig.content).toBe('Working on: Add rate limiting to admin API')
    expect(sig.metadata?.relevantFiles).toEqual([])
    expect(sig.metadata?.budgetSteps).toBeUndefined()
  })
})

describe('trimAugLines (PR-2 pure helper)', () => {
  it('appends a line when no aug lines exist', () => {
    const out = trimAugLines('GOAL: x\n\nBudget: 30 steps', 'Coordinating with Helix abcdefgh on a.ts')
    expect(out).toBe('GOAL: x\n\nBudget: 30 steps\nCoordinating with Helix abcdefgh on a.ts')
  })

  it('preserves preamble verbatim above aug lines', () => {
    const seed = 'GOAL: refactor auth\n\nRelevant files: a.ts, b.ts'
    const withOne = trimAugLines(seed, 'Coordinating with Helix peer-001 on a.ts')
    const withTwo = trimAugLines(withOne, 'Mentor noted: drift at step 7')
    expect(withTwo.startsWith(seed)).toBe(true)
    expect(withTwo).toContain('Coordinating with Helix peer-001 on a.ts')
    expect(withTwo).toContain('Mentor noted: drift at step 7')
  })

  it('caps at HELIX_GOAL_AUG_CAP, dropping oldest aug lines FIFO', () => {
    let content = 'GOAL: x'
    for (let i = 0; i < HELIX_GOAL_AUG_CAP; i++) {
      content = trimAugLines(content, `Coordinating with Helix p${i}`)
    }
    expect(content.split('\n').filter(l => l.startsWith('Coordinating with Helix ')).length).toBe(HELIX_GOAL_AUG_CAP)

    content = trimAugLines(content, `Coordinating with Helix p999`)
    const augs = content.split('\n').filter(l => l.startsWith('Coordinating with Helix '))
    expect(augs.length).toBe(HELIX_GOAL_AUG_CAP)
    expect(augs[0]).toBe('Coordinating with Helix p1')
    expect(augs[augs.length - 1]).toBe('Coordinating with Helix p999')
  })

  it('cap is shared across Coordinating + Mentor entries (combined FIFO)', () => {
    let content = 'GOAL: x'
    content = trimAugLines(content, 'Coordinating with Helix p0')
    content = trimAugLines(content, 'Mentor noted: a')
    content = trimAugLines(content, 'Coordinating with Helix p1')
    content = trimAugLines(content, 'Mentor noted: b')
    content = trimAugLines(content, 'Coordinating with Helix p2')
    content = trimAugLines(content, 'Mentor noted: c')

    const augs = content.split('\n').filter(l => /^(Coordinating with Helix |Mentor noted: )/.test(l))
    expect(augs.length).toBe(HELIX_GOAL_AUG_CAP)
    expect(augs[0]).toBe('Mentor noted: a')
  })
})

describe('appendCoordinationLine (PR-2)', () => {
  let tmpDir: string
  let logger: ILogger
  let lamina: LaminaField

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'helix-goal-lamina-pr2-'))
    logger = silentLogger()
    new AuditStore(logger, path.join(tmpDir, 'audit.db'))
    lamina = new LaminaField(logger, new LaminaStore(logger, { dbPath: path.join(tmpDir, 'lamina.db') }))
  })

  afterEach(() => { try { fs.rmSync(tmpDir, { recursive: true, force: true }) } catch {} })

  it('appends a single coordination line on first call', () => {
    seedHelixGoalLamina(lamina, 'helix-1', makeSubTask())
    appendCoordinationLine(lamina, 'helix-1', 'helix-peer-12345', ['a.ts', 'b.ts'])
    const entry = lamina.read(HELIX_GOAL_LABEL, { kind: 'session', sessionId: 'helix-1' })
    expect(entry?.content).toContain('Coordinating with Helix helix-pe on a.ts, b.ts')
  })

  it('preserves the seed body verbatim above the aug line', () => {
    const subTask = makeSubTask({ relevantFiles: ['core/x.ts'] })
    seedHelixGoalLamina(lamina, 'helix-1', subTask)
    const seedContent = lamina.read(HELIX_GOAL_LABEL, { kind: 'session', sessionId: 'helix-1' })?.content ?? ''
    appendCoordinationLine(lamina, 'helix-1', 'peer-1', ['core/x.ts'])
    const after = lamina.read(HELIX_GOAL_LABEL, { kind: 'session', sessionId: 'helix-1' })?.content ?? ''
    expect(after.startsWith(seedContent)).toBe(true)
  })

  it('caps at HELIX_GOAL_AUG_CAP combined entries (FIFO)', () => {
    seedHelixGoalLamina(lamina, 'helix-1', makeSubTask())
    for (let i = 0; i < HELIX_GOAL_AUG_CAP + 3; i++) {
      appendCoordinationLine(lamina, 'helix-1', `peer-${i}`, [`f${i}.ts`])
    }
    const entry = lamina.read(HELIX_GOAL_LABEL, { kind: 'session', sessionId: 'helix-1' })
    const augs = entry!.content.split('\n').filter(l => l.startsWith('Coordinating with Helix '))
    expect(augs.length).toBe(HELIX_GOAL_AUG_CAP)
    expect(augs[augs.length - 1]).toContain('peer-' + (HELIX_GOAL_AUG_CAP + 2))
  })

  it('is a no-op when lamina is undefined', () => {
    expect(() => appendCoordinationLine(undefined, 'helix-x', 'peer', ['a.ts'])).not.toThrow()
  })

  it('is a no-op when lamina has not been seeded yet', () => {
    expect(() => appendCoordinationLine(lamina, 'helix-not-seeded', 'peer', ['a.ts'])).not.toThrow()
    const entry = lamina.read(HELIX_GOAL_LABEL, { kind: 'session', sessionId: 'helix-not-seeded' })
    expect(entry).toBeNull()
  })

  it('isolates per-Helix (parallel)', () => {
    seedHelixGoalLamina(lamina, 'helix-a', makeSubTask())
    seedHelixGoalLamina(lamina, 'helix-b', makeSubTask())
    appendCoordinationLine(lamina, 'helix-a', 'peer-x', ['a.ts'])
    const a = lamina.read(HELIX_GOAL_LABEL, { kind: 'session', sessionId: 'helix-a' })?.content ?? ''
    const b = lamina.read(HELIX_GOAL_LABEL, { kind: 'session', sessionId: 'helix-b' })?.content ?? ''
    expect(a).toContain('Coordinating with Helix peer-x')
    expect(b).not.toContain('Coordinating with Helix')
  })
})

describe('appendMentorFlagLine (PR-2)', () => {
  let tmpDir: string
  let logger: ILogger
  let lamina: LaminaField

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'helix-goal-lamina-pr2-mf-'))
    logger = silentLogger()
    new AuditStore(logger, path.join(tmpDir, 'audit.db'))
    lamina = new LaminaField(logger, new LaminaStore(logger, { dbPath: path.join(tmpDir, 'lamina.db') }))
  })

  afterEach(() => { try { fs.rmSync(tmpDir, { recursive: true, force: true }) } catch {} })

  it('appends a Mentor noted line with issue type + step number', () => {
    seedHelixGoalLamina(lamina, 'helix-m', makeSubTask())
    appendMentorFlagLine(lamina, 'helix-m', 'drift', 7)
    const entry = lamina.read(HELIX_GOAL_LABEL, { kind: 'session', sessionId: 'helix-m' })
    expect(entry?.content).toContain('Mentor noted: drift at step 7')
  })

  it('shares the FIFO cap with coordination entries (oldest of either type drops)', () => {
    seedHelixGoalLamina(lamina, 'helix-mix', makeSubTask())
    appendCoordinationLine(lamina, 'helix-mix', 'p0', ['a.ts'])
    appendMentorFlagLine(lamina, 'helix-mix', 'mp0', 1)
    appendCoordinationLine(lamina, 'helix-mix', 'p1', ['b.ts'])
    appendMentorFlagLine(lamina, 'helix-mix', 'mp1', 2)
    appendCoordinationLine(lamina, 'helix-mix', 'p2', ['c.ts'])
    appendMentorFlagLine(lamina, 'helix-mix', 'mp2', 3)

    const entry = lamina.read(HELIX_GOAL_LABEL, { kind: 'session', sessionId: 'helix-mix' })
    const augs = entry!.content.split('\n').filter(l => /^(Coordinating with Helix |Mentor noted: )/.test(l))
    expect(augs.length).toBe(HELIX_GOAL_AUG_CAP)
    expect(augs[0]).toBe('Mentor noted: mp0 at step 1')
  })
})

describe('rethinkHelixGoalMidFlight (PR-2)', () => {
  let tmpDir: string
  let logger: ILogger
  let lamina: LaminaField

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'helix-goal-lamina-pr2-mf2-'))
    logger = silentLogger()
    new AuditStore(logger, path.join(tmpDir, 'audit.db'))
    lamina = new LaminaField(logger, new LaminaStore(logger, { dbPath: path.join(tmpDir, 'lamina.db') }))
  })

  afterEach(() => { try { fs.rmSync(tmpDir, { recursive: true, force: true }) } catch {} })

  it('writes new content and bumps version on transition', () => {
    seedHelixGoalLamina(lamina, 'helix-1', makeSubTask({ goal: 'old goal' }))
    const before = lamina.read(HELIX_GOAL_LABEL, { kind: 'session', sessionId: 'helix-1' })
    rethinkHelixGoalMidFlight(lamina, 'helix-1', makeSubTask({ goal: 'refined goal' }), 'transition:planned->in-progress')
    const after = lamina.read(HELIX_GOAL_LABEL, { kind: 'session', sessionId: 'helix-1' })
    expect(after?.content).toContain('refined goal')
    expect(after?.content).not.toContain('old goal')
    expect(after?.version).toBeGreaterThan(before?.version ?? 0)
  })

  it('preserves any prior aug lines (Coordinating/Mentor) verbatim', () => {
    seedHelixGoalLamina(lamina, 'helix-1', makeSubTask())
    appendCoordinationLine(lamina, 'helix-1', 'peer-keep', ['k.ts'])
    appendMentorFlagLine(lamina, 'helix-1', 'drift', 4)

    rethinkHelixGoalMidFlight(lamina, 'helix-1', makeSubTask({ goal: 'updated goal' }), 'deviation: foo')

    const after = lamina.read(HELIX_GOAL_LABEL, { kind: 'session', sessionId: 'helix-1' })
    expect(after?.content).toContain('updated goal')
    expect(after?.content).toContain('Coordinating with Helix peer-kee')
    expect(after?.content).toContain('Mentor noted: drift at step 4')
  })

  it('is a no-op when lamina has no prior entry (only triggered on existing helixes)', () => {
    expect(() => rethinkHelixGoalMidFlight(lamina, 'never-seeded', makeSubTask(), 'reason')).not.toThrow()
  })
})
