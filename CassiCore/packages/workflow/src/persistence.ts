/**
 * WorkflowStore — SQLite persistence for workflow runs.
 *
 * Persists workflow runs to survive process restarts. Supports:
 *   - Save/load workflow runs (including suspended runs)
 *   - Query runs by status, workflowId
 *   - Prune old completed/failed runs
 *   - Atomic state updates during execution
 *
 * Schema:
 *   workflow_runs    — one row per run (status, state, trace, input/output)
 *   schema_version   — migration tracking
 */

import Database from 'better-sqlite3'
import * as fs from 'node:fs'
import * as path from 'node:path'
import type { ILogger } from '@cassicore/foundation'
import type { WorkflowRun, WorkflowRunStatus, StepTrace } from '@cassicore/foundation'
import { getDataDir } from '@cassicore/foundation'

// Constants

const SCHEMA_VERSION = 1
const DEFAULT_MAX_AGE_DAYS = 30
const DB_FILENAME = 'system-state.db'

// Row types

interface RunRow {
  run_id: string
  workflow_id: string
  status: string
  state_json: string
  input_json: string
  output_json: string | null
  error: string | null
  current_node_id: string | null
  suspended_at_node_id: string | null
  suspend_reason: string | null
  trace_json: string
  started_at: string
  ended_at: string | null
  duration_ms: number | null
  created_at: string
  updated_at: string
}

// Store

export class WorkflowStore {
  private db: InstanceType<typeof Database>
  private stmts!: ReturnType<WorkflowStore['prepareStatements']>

  private constructor(dbPath: string, private logger: ILogger) {
    this.db = new Database(dbPath)
    this.db.pragma('journal_mode = WAL')
    this.db.pragma('synchronous = NORMAL')
    this.db.pragma('foreign_keys = ON')
    this.db.pragma('busy_timeout = 5000')
    this.migrate()
    this.stmts = this.prepareStatements()
  }

  /** Factory method — creates data directory, opens DB, runs migrations. */
  static open(logger: ILogger, dataDir?: string): WorkflowStore {
    const dir = dataDir ?? getDataDir()
    fs.mkdirSync(dir, { recursive: true })
    const dbPath = path.join(dir, DB_FILENAME)
    const store = new WorkflowStore(dbPath, logger.child('workflow-store'))
    return store
  }

  /** Open with an explicit DB path (useful for testing with in-memory or temp DBs). */
  static openAt(dbPath: string, logger: ILogger): WorkflowStore {
    return new WorkflowStore(dbPath, logger.child('workflow-store'))
  }

  // Public API

  /** Save or update a workflow run. */
  save(run: WorkflowRun): void {
    this.stmts.upsert.run({
      run_id: run.runId,
      workflow_id: run.workflowId,
      status: run.status,
      state_json: JSON.stringify(run.state),
      input_json: JSON.stringify(run.input),
      output_json: run.output !== undefined ? JSON.stringify(run.output) : null,
      error: run.error ?? null,
      current_node_id: run.currentNodeId ?? null,
      suspended_at_node_id: run.suspendedAtNodeId ?? null,
      suspend_reason: run.suspendReason ?? null,
      trace_json: JSON.stringify(run.trace),
      started_at: run.startedAt.toISOString(),
      ended_at: run.endedAt?.toISOString() ?? null,
      duration_ms: run.durationMs ?? null,
    })
  }

  /** Load a workflow run by its id. */
  load(runId: string): WorkflowRun | undefined {
    const row = this.stmts.load.get(runId) as RunRow | undefined
    if (!row) return undefined
    return this.rowToRun(row)
  }

  /** List runs, optionally filtered by status and/or workflowId. */
  list(opts?: {
    status?: WorkflowRunStatus
    workflowId?: string
    limit?: number
  }): WorkflowRun[] {
    const limit = opts?.limit ?? 50
    let rows: RunRow[]

    if (opts?.status && opts?.workflowId) {
      rows = this.stmts.listByStatusAndWorkflow.all(opts.status, opts.workflowId, limit) as RunRow[]
    } else if (opts?.status) {
      rows = this.stmts.listByStatus.all(opts.status, limit) as RunRow[]
    } else if (opts?.workflowId) {
      rows = this.stmts.listByWorkflow.all(opts.workflowId, limit) as RunRow[]
    } else {
      rows = this.stmts.listAll.all(limit) as RunRow[]
    }

    return rows.map((r) => this.rowToRun(r))
  }

  /** Get all suspended runs (for resume after restart). */
  listSuspended(): WorkflowRun[] {
    return this.list({ status: 'suspended' })
  }

  /** Get all running runs (stale after restart — should be marked failed). */
  listRunning(): WorkflowRun[] {
    return this.list({ status: 'running' })
  }

  /** Delete a run by its id. */
  delete(runId: string): boolean {
    const result = this.stmts.delete.run(runId)
    return result.changes > 0
  }

  /** Prune old completed/failed runs older than maxAgeDays. */
  prune(maxAgeDays: number = DEFAULT_MAX_AGE_DAYS): number {
    const cutoff = new Date(Date.now() - maxAgeDays * 24 * 60 * 60 * 1000).toISOString()
    const result = this.stmts.prune.run(cutoff)
    if (result.changes > 0) {
      this.logger.info('Pruned old workflow runs', { pruned: result.changes, maxAgeDays })
    }
    return result.changes
  }

  /** Get aggregate stats. */
  stats(): { total: number; byStatus: Record<string, number> } {
    const rows = this.stmts.statsByStatus.all() as Array<{ status: string; count: number }>
    const byStatus: Record<string, number> = {}
    let total = 0
    for (const row of rows) {
      byStatus[row.status] = row.count
      total += row.count
    }
    return { total, byStatus }
  }

  /** Close the database connection. */
  close(): void {
    this.db.close()
  }

  // Internal

  private rowToRun(row: RunRow): WorkflowRun {
    let state: Record<string, unknown>
    let trace: StepTrace[]
    let input: unknown
    let output: unknown | undefined

    try { state = JSON.parse(row.state_json) } catch { state = {} }
    try { trace = JSON.parse(row.trace_json) } catch { trace = [] }
    try { input = JSON.parse(row.input_json) } catch { input = null }

    if (row.output_json !== null) {
      try { output = JSON.parse(row.output_json) } catch { output = undefined }
    }

    // HOW: Dates come back as ISO strings from SQLite. Trace dates need
    // reconstruction since they were serialized via JSON.stringify.
    const reconstructedTrace = trace.map((t) => ({
      ...t,
      startedAt: typeof t.startedAt === 'string' ? new Date(t.startedAt) : t.startedAt,
      endedAt: t.endedAt ? (typeof t.endedAt === 'string' ? new Date(t.endedAt) : t.endedAt) : undefined,
    }))

    return {
      runId: row.run_id,
      workflowId: row.workflow_id,
      status: row.status as WorkflowRunStatus,
      state,
      input,
      output,
      error: row.error ?? undefined,
      currentNodeId: row.current_node_id ?? undefined,
      suspendedAtNodeId: row.suspended_at_node_id ?? undefined,
      suspendReason: row.suspend_reason ?? undefined,
      trace: reconstructedTrace,
      startedAt: new Date(row.started_at),
      endedAt: row.ended_at ? new Date(row.ended_at) : undefined,
      durationMs: row.duration_ms ?? undefined,
    }
  }

  private migrate(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY
      );
    `)

    const row = this.db.prepare('SELECT version FROM schema_version LIMIT 1').get() as
      | { version: number }
      | undefined
    const current = row?.version ?? 0

    if (current < 1) {
      this.db.exec(`
        CREATE TABLE IF NOT EXISTS workflow_runs (
          run_id                TEXT PRIMARY KEY,
          workflow_id           TEXT NOT NULL,
          status                TEXT NOT NULL DEFAULT 'pending',
          state_json            TEXT NOT NULL DEFAULT '{}',
          input_json            TEXT NOT NULL DEFAULT 'null',
          output_json           TEXT,
          error                 TEXT,
          current_node_id       TEXT,
          suspended_at_node_id  TEXT,
          suspend_reason        TEXT,
          trace_json            TEXT NOT NULL DEFAULT '[]',
          started_at            TEXT NOT NULL,
          ended_at              TEXT,
          duration_ms           INTEGER,
          created_at            TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at            TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_workflow_runs_status
          ON workflow_runs (status);
        CREATE INDEX IF NOT EXISTS idx_workflow_runs_workflow_id
          ON workflow_runs (workflow_id);
        CREATE INDEX IF NOT EXISTS idx_workflow_runs_started_at
          ON workflow_runs (started_at);
      `)

      this.db.prepare('DELETE FROM schema_version').run()
      this.db.prepare('INSERT INTO schema_version (version) VALUES (?)').run(SCHEMA_VERSION)
      this.logger.info('Workflow store schema v1 created')
    }
  }

  private prepareStatements() {
    return {
      upsert: this.db.prepare(`
        INSERT INTO workflow_runs (
          run_id, workflow_id, status, state_json, input_json, output_json,
          error, current_node_id, suspended_at_node_id, suspend_reason,
          trace_json, started_at, ended_at, duration_ms
        ) VALUES (
          @run_id, @workflow_id, @status, @state_json, @input_json, @output_json,
          @error, @current_node_id, @suspended_at_node_id, @suspend_reason,
          @trace_json, @started_at, @ended_at, @duration_ms
        )
        ON CONFLICT (run_id) DO UPDATE SET
          status = @status,
          state_json = @state_json,
          output_json = @output_json,
          error = @error,
          current_node_id = @current_node_id,
          suspended_at_node_id = @suspended_at_node_id,
          suspend_reason = @suspend_reason,
          trace_json = @trace_json,
          ended_at = @ended_at,
          duration_ms = @duration_ms,
          updated_at = datetime('now')
      `),

      load: this.db.prepare(`
        SELECT * FROM workflow_runs WHERE run_id = ?
      `),

      listAll: this.db.prepare(`
        SELECT * FROM workflow_runs ORDER BY started_at DESC LIMIT ?
      `),

      listByStatus: this.db.prepare(`
        SELECT * FROM workflow_runs WHERE status = ? ORDER BY started_at DESC LIMIT ?
      `),

      listByWorkflow: this.db.prepare(`
        SELECT * FROM workflow_runs WHERE workflow_id = ? ORDER BY started_at DESC LIMIT ?
      `),

      listByStatusAndWorkflow: this.db.prepare(`
        SELECT * FROM workflow_runs WHERE status = ? AND workflow_id = ? ORDER BY started_at DESC LIMIT ?
      `),

      delete: this.db.prepare(`
        DELETE FROM workflow_runs WHERE run_id = ?
      `),

      prune: this.db.prepare(`
        DELETE FROM workflow_runs
        WHERE status IN ('completed', 'failed', 'cancelled')
          AND ended_at < ?
      `),

      statsByStatus: this.db.prepare(`
        SELECT status, COUNT(*) as count FROM workflow_runs GROUP BY status
      `),
    }
  }
}
