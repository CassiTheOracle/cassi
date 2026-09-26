/**
 * AuditStore — faithful self-contained RUNTIME copy of
 * `core/runtime/audit/audit-store.ts` (SQLite run/step ledger).
 *
 * Kept host-dep-light per the P5b Group B Open Flag 4 default: `ILogger` and
 * `getDataDir` come from `@cassicore/foundation`; `prefixedId` is a vendored
 * runtime copy; the mnemic-field replay seam is carried as minimal local
 * structural types (the replay path is inert here — nothing calls
 * `setMnemicField` in this package or its tests). Re-point to
 * `@cassicore/events` at P6.
 */

import fs from 'node:fs'
import path from 'node:path'

import Database from 'better-sqlite3'

import { getDataDir } from '@cassicore/foundation'
import type { ILogger } from '@cassicore/foundation'
import { prefixedId } from '../../intelligence/utils/prefixed-id.js'
import type { Run, Step, RunCreate, StepCreate } from './types.js'

const DB_NAME = 'system-state.db'

/** Minimal structural EngramCreate surface used by the (inert) replay seam. */
interface EngramCreateLike {
  id?: string
  content: string
  nodeType: string
  t?: number
  createdAt?: string
  tags?: string[]
  provenance?: string
  metadata?: Record<string, unknown>
  [key: string]: unknown
}

/** Minimal structural MnemicField surface used by the (inert) replay seam. */
interface MnemicFieldLike {
  get(id: string): unknown
  store(input: EngramCreateLike): unknown
  update(id: string, updates: { content?: string; nodeType?: string; t?: number; tags?: string[]; metadata?: Record<string, unknown> }): unknown
  connect(opts: { sourceId: string; targetId: string; edgeType: string }): unknown
}

const SCHEMA_SQL = `
  CREATE TABLE IF NOT EXISTS audit_runs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    session_id TEXT,
    agent_id TEXT NOT NULL,
    parent_run_id TEXT,
    goal TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    FOREIGN KEY (parent_run_id) REFERENCES audit_runs(id)
  );

  CREATE INDEX IF NOT EXISTS idx_audit_runs_session ON audit_runs(session_id, started_at DESC);
  CREATE INDEX IF NOT EXISTS idx_audit_runs_agent ON audit_runs(agent_id, started_at DESC);
  CREATE INDEX IF NOT EXISTS idx_audit_runs_status ON audit_runs(status);

  CREATE TABLE IF NOT EXISTS audit_steps (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    step_number INTEGER NOT NULL,
    request_id TEXT,
    slot TEXT NOT NULL,
    model TEXT,
    reason TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    duration_ms INTEGER,
    status TEXT NOT NULL DEFAULT 'open',
    tool_call_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (run_id) REFERENCES audit_runs(id) ON DELETE CASCADE
  );

  CREATE INDEX IF NOT EXISTS idx_audit_steps_run ON audit_steps(run_id, step_number);
  CREATE INDEX IF NOT EXISTS idx_audit_steps_request ON audit_steps(request_id);
  CREATE UNIQUE INDEX IF NOT EXISTS uniq_audit_steps_run_num ON audit_steps(run_id, step_number);
`

function rowToRun(row: Record<string, unknown>): Run {
  return {
    id: row.id as string,
    kind: row.kind as Run['kind'],
    sessionId: (row.session_id as string | null) ?? null,
    agentId: row.agent_id as string,
    parentRunId: (row.parent_run_id as string | null) ?? null,
    goal: (row.goal as string | null) ?? null,
    startedAt: row.started_at as string,
    finishedAt: (row.finished_at as string | null) ?? null,
    status: row.status as Run['status'],
  }
}

function rowToStep(row: Record<string, unknown>): Step {
  return {
    id: row.id as string,
    runId: row.run_id as string,
    stepNumber: row.step_number as number,
    requestId: (row.request_id as string | null) ?? null,
    slot: row.slot as string,
    model: (row.model as string | null) ?? null,
    reason: (row.reason as string | null) ?? null,
    startedAt: row.started_at as string,
    finishedAt: (row.finished_at as string | null) ?? null,
    durationMs: (row.duration_ms as number | null) ?? null,
    status: row.status as Step['status'],
    toolCallCount: (row.tool_call_count as number | null) ?? 0,
  }
}

type MetricsSnapshot = { runs: number; openRuns: number; steps: number; avgStepMs: number | null }

export class AuditStore {
  private db: Database.Database
  private logger: ILogger
  private mnemicField?: MnemicFieldLike

  private insertRunStmt: Database.Statement
  private finishRunStmt: Database.Statement
  private selectRunStmt: Database.Statement
  private maxStepStmt: Database.Statement
  private insertStepStmt: Database.Statement
  private selectStepStartStmt: Database.Statement
  private finishStepStmt: Database.Statement
  private selectStepStmt: Database.Statement
  private listStepsStmt: Database.Statement
  private countRunsStmt: Database.Statement
  private countOpenRunsStmt: Database.Statement
  private countStepsStmt: Database.Statement
  private avgDurationStmt: Database.Statement

  // Metrics are called frequently by the admin dashboard but the underlying
  // counters only change on startRun/startStep/finishRun/finishStep. Cache the
  // full snapshot and bust on any mutation.
  private metricsCache: MetricsSnapshot | null = null

  constructor(logger: ILogger, dbPath?: string) {
    this.logger = logger.child?.('audit-store') ?? logger

    const finalPath = dbPath ?? path.join(getDataDir(), DB_NAME)
    fs.mkdirSync(path.dirname(finalPath), { recursive: true })

    this.db = new Database(finalPath)
    this.db.pragma('journal_mode = WAL')
    this.db.pragma('foreign_keys = ON')
    this.db.exec(SCHEMA_SQL)

    this.insertRunStmt = this.db.prepare(`
      INSERT INTO audit_runs (id, kind, session_id, agent_id, parent_run_id, goal, started_at, status)
      VALUES (?, ?, ?, ?, ?, ?, ?, 'open')
    `)
    this.finishRunStmt = this.db.prepare(`UPDATE audit_runs SET finished_at = ?, status = ? WHERE id = ?`)
    this.selectRunStmt = this.db.prepare(`SELECT * FROM audit_runs WHERE id = ?`)
    this.maxStepStmt = this.db.prepare(`SELECT COALESCE(MAX(step_number), 0) AS n FROM audit_steps WHERE run_id = ?`)
    this.insertStepStmt = this.db.prepare(`
      INSERT INTO audit_steps (id, run_id, step_number, request_id, slot, model, reason, started_at, status, tool_call_count)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', 0)
    `)
    this.selectStepStartStmt = this.db.prepare(`SELECT started_at FROM audit_steps WHERE id = ?`)
    this.finishStepStmt = this.db.prepare(
      `UPDATE audit_steps SET finished_at = ?, status = ?, duration_ms = ?, tool_call_count = COALESCE(?, tool_call_count) WHERE id = ?`
    )
    this.selectStepStmt = this.db.prepare(`SELECT * FROM audit_steps WHERE id = ?`)
    this.listStepsStmt = this.db.prepare(`SELECT * FROM audit_steps WHERE run_id = ? ORDER BY step_number ASC`)
    this.countRunsStmt = this.db.prepare(`SELECT COUNT(*) AS n FROM audit_runs`)
    this.countOpenRunsStmt = this.db.prepare(`SELECT COUNT(*) AS n FROM audit_runs WHERE status = 'open'`)
    this.countStepsStmt = this.db.prepare(`SELECT COUNT(*) AS n FROM audit_steps`)
    this.avgDurationStmt = this.db.prepare(`SELECT AVG(duration_ms) AS a FROM audit_steps WHERE duration_ms IS NOT NULL`)
  }

  private bustMetrics(): void {
    this.metricsCache = null
  }

  setMnemicField(field: MnemicFieldLike): void {
    this.mnemicField = field
  }

  close(): void {
    try { this.db.close() } catch { /* ignore */ }
  }

  // Runs

  startRun(input: RunCreate): Run {
    const id = prefixedId('r')
    const now = new Date().toISOString()
    this.insertRunStmt.run(
      id,
      input.kind,
      input.sessionId ?? null,
      input.agentId,
      input.parentRunId ?? null,
      input.goal ?? null,
      now,
    )
    this.bustMetrics()

    const run: Run = {
      id,
      kind: input.kind,
      sessionId: input.sessionId ?? null,
      agentId: input.agentId,
      parentRunId: input.parentRunId ?? null,
      goal: input.goal ?? null,
      startedAt: now,
      finishedAt: null,
      status: 'open',
    }
    this.writeRunReplay(run)
    return run
  }

  finishRun(id: string, status: 'completed' | 'failed' | 'aborted' = 'completed'): void {
    const now = new Date().toISOString()
    this.finishRunStmt.run(now, status, id)
    this.bustMetrics()
    const run = this.getRun(id)
    if (run) this.writeRunReplay(run)
  }

  getRun(id: string): Run | null {
    const row = this.selectRunStmt.get(id) as Record<string, unknown> | undefined
    return row ? rowToRun(row) : null
  }

  listRuns(opts: { sessionId?: string; agentId?: string; status?: Run['status']; limit?: number } = {}): Run[] {
    const where: string[] = []
    const args: unknown[] = []
    if (opts.sessionId) { where.push('session_id = ?'); args.push(opts.sessionId) }
    if (opts.agentId) { where.push('agent_id = ?'); args.push(opts.agentId) }
    if (opts.status) { where.push('status = ?'); args.push(opts.status) }
    const whereSql = where.length ? `WHERE ${where.join(' AND ')}` : ''
    const limit = Math.max(1, Math.min(opts.limit ?? 50, 500))
    const rows = this.db
      .prepare(`SELECT * FROM audit_runs ${whereSql} ORDER BY started_at DESC LIMIT ?`)
      .all(...args, limit) as Record<string, unknown>[]
    return rows.map(rowToRun)
  }

  // Steps

  startStep(input: StepCreate): Step {
    const id = prefixedId('s')
    const now = new Date().toISOString()

    const row = this.maxStepStmt.get(input.runId) as { n: number }
    const stepNumber = (row?.n ?? 0) + 1

    this.insertStepStmt.run(
      id, input.runId, stepNumber, input.requestId ?? null, input.slot,
      input.model ?? null, input.reason ?? null, now,
    )
    this.bustMetrics()

    const step: Step = {
      id,
      runId: input.runId,
      stepNumber,
      requestId: input.requestId ?? null,
      slot: input.slot,
      model: input.model ?? null,
      reason: input.reason ?? null,
      startedAt: now,
      finishedAt: null,
      durationMs: null,
      status: 'open',
      toolCallCount: 0,
    }
    this.writeStepReplay(step)
    return step
  }

  finishStep(id: string, opts: { status?: 'completed' | 'failed'; toolCallCount?: number } = {}): void {
    const now = new Date()
    const row = this.selectStepStartStmt.get(id) as { started_at: string } | undefined
    if (!row) return
    const durationMs = now.getTime() - new Date(row.started_at).getTime()
    this.finishStepStmt.run(
      now.toISOString(), opts.status ?? 'completed', durationMs,
      opts.toolCallCount ?? null, id,
    )
    this.bustMetrics()
    const step = this.getStep(id)
    if (step) this.writeStepReplay(step)
  }

  getStep(id: string): Step | null {
    const row = this.selectStepStmt.get(id) as Record<string, unknown> | undefined
    return row ? rowToStep(row) : null
  }

  listSteps(runId: string): Step[] {
    const rows = this.listStepsStmt.all(runId) as Record<string, unknown>[]
    return rows.map(rowToStep)
  }

  /** Aggregate metrics for observability — snapshot-cached between mutations. */
  metrics(): MetricsSnapshot {
    if (this.metricsCache) return this.metricsCache
    const runs = (this.countRunsStmt.get() as { n: number }).n
    const openRuns = (this.countOpenRunsStmt.get() as { n: number }).n
    const steps = (this.countStepsStmt.get() as { n: number }).n
    const avgRow = this.avgDurationStmt.get() as { a: number | null }
    this.metricsCache = { runs, openRuns, steps, avgStepMs: avgRow?.a ?? null }
    return this.metricsCache
  }

  private writeRunReplay(run: Run): void {
    if (!this.mnemicField) return
    try {
      const runId = this.replayRunId(run.id)
      if (run.sessionId) this.ensureReplaySession(run.sessionId, run.startedAt)
      this.upsertReplayEngram({
        id: runId,
        content: JSON.stringify(run),
        nodeType: 'goal',
        t: new Date(run.startedAt).getTime(),
        createdAt: run.startedAt,
        tags: ['session-replay', 'audit-run', run.kind, run.agentId],
        provenance: 'audit-store',
        metadata: {
          auditRunId: run.id,
          sessionId: run.sessionId,
          agentId: run.agentId,
          kind: run.kind,
          status: run.status,
        },
      })
      if (run.sessionId) {
        this.mnemicField.connect({ sourceId: runId, targetId: `session:${run.sessionId}`, edgeType: 'part_of' })
      }
      if (run.parentRunId && this.mnemicField.get(this.replayRunId(run.parentRunId))) {
        this.mnemicField.connect({ sourceId: runId, targetId: this.replayRunId(run.parentRunId), edgeType: 'spawned_from' })
      }
    } catch (err) {
      this.logger.warn('AuditStore replay run write failed', { runId: run.id, error: String(err) })
    }
  }

  private writeStepReplay(step: Step): void {
    if (!this.mnemicField) return
    try {
      const stepId = this.replayStepId(step.runId, step.stepNumber)
      this.upsertReplayEngram({
        id: stepId,
        content: JSON.stringify(step),
        nodeType: 'decision',
        t: new Date(step.startedAt).getTime(),
        createdAt: step.startedAt,
        tags: ['session-replay', 'audit-step', step.slot],
        provenance: 'audit-store',
        metadata: {
          auditStepId: step.id,
          auditRunId: step.runId,
          requestId: step.requestId,
          stepNumber: step.stepNumber,
          slot: step.slot,
          model: step.model,
          status: step.status,
          toolCallCount: step.toolCallCount,
        },
      })
      if (this.mnemicField.get(this.replayRunId(step.runId))) {
        this.mnemicField.connect({ sourceId: stepId, targetId: this.replayRunId(step.runId), edgeType: 'part_of' })
      }
      if (step.stepNumber > 1 && this.mnemicField.get(this.replayStepId(step.runId, step.stepNumber - 1))) {
        this.mnemicField.connect({
          sourceId: this.replayStepId(step.runId, step.stepNumber - 1),
          targetId: stepId,
          edgeType: 'temporal_neighbor',
        })
      }
    } catch (err) {
      this.logger.warn('AuditStore replay step write failed', { stepId: step.id, error: String(err) })
    }
  }

  private ensureReplaySession(sessionId: string, startedAt: string): void {
    if (!this.mnemicField || this.mnemicField.get(`session:${sessionId}`)) return
    this.upsertReplayEngram({
      id: `session:${sessionId}`,
      content: JSON.stringify({ sessionId, source: 'audit-store' }),
      nodeType: 'session',
      t: new Date(startedAt).getTime(),
      createdAt: startedAt,
      tags: ['session-replay', 'audit-session-stub'],
      provenance: 'audit-store',
      metadata: { sessionId, source: 'audit-store' },
    })
  }

  private upsertReplayEngram(input: EngramCreateLike): void {
    if (!this.mnemicField || !input.id) return
    const existing = this.mnemicField.get(input.id)
    if (existing) {
      this.mnemicField.update(input.id, {
        content: input.content,
        nodeType: input.nodeType,
        t: input.t,
        tags: input.tags,
        metadata: input.metadata,
      })
      return
    }
    this.mnemicField.store(input)
  }

  private replayRunId(runId: string): string {
    return `run:${runId}`
  }

  private replayStepId(runId: string, stepNumber: number): string {
    return `step:${runId}:${stepNumber}`
  }
}
