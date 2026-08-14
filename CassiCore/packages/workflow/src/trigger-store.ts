/**
 * WorkflowTriggerStore — SQLite persistence for workflow triggers and their runtime state.
 *
 * Persists trigger configurations and runtime state (fire counts, last/next fire times,
 * status) so triggers survive process restarts. On restart, the scheduler reloads
 * all triggers and their state, then reactivates enabled ones.
 *
 * Schema:
 *   workflow_triggers       — one row per trigger (config: kind, workflowId, etc.)
 *   workflow_trigger_states — one row per trigger (runtime: fireCount, lastFiredAt, status)
 *   trigger_schema_version  — migration tracking
 *
 * Uses the same database as WorkflowStore/WorkflowDefinitionStore (workflows.db) to
 * keep all workflow data colocated. Separate migration tracking avoids conflicts.
 *
 * EventTrigger.eventFilter is a function and cannot be serialized. Only the
 * eventPattern string is persisted. Triggers with custom filter predicates
 * must re-attach the filter after loading.
 */

import Database from 'better-sqlite3'
import * as fs from 'node:fs'
import * as path from 'node:path'
import type { ILogger } from '../../types/interfaces.js'
import type {
  WorkflowTrigger,
  TriggerKind,
  TriggerState,
  IWorkflowTriggerStore,
} from '../../types/workflow.js'
import { getDataDir } from '../utils/paths.js'

const TRIGGER_SCHEMA_VERSION = 1
const DB_FILENAME = 'system-state.db'

interface TriggerRow {
  id: string
  kind: string
  workflow_id: string
  description: string | null
  enabled: number
  max_fires: number | null
  input_json: string | null
  interval_ms: number | null
  cron_expression: string | null
  event_pattern: string | null
  fire_at: string | null
  created_at: string
  updated_at: string
}

interface TriggerStateRow {
  trigger_id: string
  fire_count: number
  last_fired_at: string | null
  next_fire_at: string | null
  status: string
  last_error: string | null
}

export class WorkflowTriggerStore implements IWorkflowTriggerStore {
  private db: InstanceType<typeof Database>
  private stmts!: ReturnType<WorkflowTriggerStore['prepareStatements']>

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
  static open(logger: ILogger, dataDir?: string): WorkflowTriggerStore {
    const dir = dataDir ?? getDataDir()
    fs.mkdirSync(dir, { recursive: true })
    const dbPath = path.join(dir, DB_FILENAME)
    return new WorkflowTriggerStore(dbPath, logger.child('workflow-trigger-store'))
  }

  /** Open with an explicit DB path (useful for testing). */
  static openAt(dbPath: string, logger: ILogger): WorkflowTriggerStore {
    return new WorkflowTriggerStore(dbPath, logger.child('workflow-trigger-store'))
  }

  /** Save or update a trigger. */
  saveTrigger(trigger: WorkflowTrigger): void {
    this.stmts.upsertTrigger.run({
      id: trigger.id,
      kind: trigger.kind,
      workflow_id: trigger.workflowId,
      description: trigger.description ?? null,
      enabled: trigger.enabled ? 1 : 0,
      max_fires: trigger.maxFires ?? null,
      input_json: trigger.input !== undefined ? JSON.stringify(trigger.input) : null,
      interval_ms: trigger.kind === 'interval' ? trigger.intervalMs : null,
      cron_expression: trigger.kind === 'cron' ? trigger.cronExpression : null,
      event_pattern: trigger.kind === 'event' ? trigger.eventPattern : null,
      fire_at: trigger.kind === 'once' ? trigger.fireAt : null,
    })
  }

  /** Load a trigger by id. */
  loadTrigger(id: string): WorkflowTrigger | undefined {
    const row = this.stmts.loadTrigger.get(id) as TriggerRow | undefined
    if (!row) return undefined
    return this.rowToTrigger(row)
  }

  /** List triggers, optionally filtered. */
  listTriggers(opts?: {
    workflowId?: string
    kind?: TriggerKind
    enabled?: boolean
    limit?: number
  }): WorkflowTrigger[] {
    const limit = opts?.limit ?? 50
    let rows: TriggerRow[]

    if (opts?.workflowId && opts?.kind) {
      rows = this.stmts.listByWorkflowAndKind.all(opts.workflowId, opts.kind, limit) as TriggerRow[]
    } else if (opts?.workflowId) {
      rows = this.stmts.listByWorkflow.all(opts.workflowId, limit) as TriggerRow[]
    } else if (opts?.kind) {
      rows = this.stmts.listByKind.all(opts.kind, limit) as TriggerRow[]
    } else if (opts?.enabled !== undefined) {
      rows = this.stmts.listByEnabled.all(opts.enabled ? 1 : 0, limit) as TriggerRow[]
    } else {
      rows = this.stmts.listAll.all(limit) as TriggerRow[]
    }

    return rows.map((r) => this.rowToTrigger(r))
  }

  /** Delete a trigger and its state. */
  deleteTrigger(id: string): boolean {
    const txn = this.db.transaction(() => {
      this.stmts.deleteState.run(id)
      return this.stmts.deleteTrigger.run(id).changes > 0
    })
    return txn()
  }

  /** Save or update trigger runtime state. */
  saveState(state: TriggerState): void {
    this.stmts.upsertState.run({
      trigger_id: state.triggerId,
      fire_count: state.fireCount,
      last_fired_at: state.lastFiredAt ?? null,
      next_fire_at: state.nextFireAt ?? null,
      status: state.status,
      last_error: state.lastError ?? null,
    })
  }

  /** Load trigger runtime state. */
  loadState(triggerId: string): TriggerState | undefined {
    const row = this.stmts.loadState.get(triggerId) as TriggerStateRow | undefined
    if (!row) return undefined
    return this.rowToState(row)
  }

  /** Get aggregate stats. */
  stats(): {
    total: number
    enabled: number
    disabled: number
    byKind: Record<string, number>
  } {
    const kindRows = this.stmts.statsByKind.all() as Array<{ kind: string; count: number }>
    const byKind: Record<string, number> = {}
    let total = 0
    for (const row of kindRows) {
      byKind[row.kind] = row.count
      total += row.count
    }

    const enabledRow = this.stmts.countEnabled.get() as { count: number }

    return {
      total,
      enabled: enabledRow.count,
      disabled: total - enabledRow.count,
      byKind,
    }
  }

  /** Close the database connection. */
  close(): void {
    this.db.close()
  }

  private rowToTrigger(row: TriggerRow): WorkflowTrigger {
    const base = {
      id: row.id,
      workflowId: row.workflow_id,
      description: row.description ?? undefined,
      enabled: row.enabled === 1,
      maxFires: row.max_fires ?? undefined,
      input: row.input_json !== null ? JSON.parse(row.input_json) : undefined,
      createdAt: row.created_at,
      updatedAt: row.updated_at,
    }

    switch (row.kind as TriggerKind) {
      case 'interval':
        return { ...base, kind: 'interval' as const, intervalMs: row.interval_ms! }
      case 'cron':
        return { ...base, kind: 'cron' as const, cronExpression: row.cron_expression! }
      case 'event':
        return { ...base, kind: 'event' as const, eventPattern: row.event_pattern! }
      case 'once':
        return { ...base, kind: 'once' as const, fireAt: row.fire_at! }
      default:
        // HOW: Fallback for unknown kinds — treat as interval with safe defaults.
        // This shouldn't happen in practice, but prevents a crash if the DB
        // contains data from a future version with new trigger kinds.
        return { ...base, kind: 'interval' as const, intervalMs: 60_000 }
    }
  }

  private rowToState(row: TriggerStateRow): TriggerState {
    return {
      triggerId: row.trigger_id,
      fireCount: row.fire_count,
      lastFiredAt: row.last_fired_at ?? undefined,
      nextFireAt: row.next_fire_at ?? undefined,
      status: row.status as TriggerState['status'],
      lastError: row.last_error ?? undefined,
    }
  }

  private migrate(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS trigger_schema_version (
        version INTEGER PRIMARY KEY
      );
    `)

    const row = this.db.prepare('SELECT version FROM trigger_schema_version LIMIT 1').get() as
      | { version: number }
      | undefined
    const current = row?.version ?? 0

    if (current < 1) {
      this.db.exec(`
        CREATE TABLE IF NOT EXISTS workflow_triggers (
          id                TEXT PRIMARY KEY,
          kind              TEXT NOT NULL,
          workflow_id       TEXT NOT NULL,
          description       TEXT,
          enabled           INTEGER NOT NULL DEFAULT 1,
          max_fires         INTEGER,
          input_json        TEXT,
          interval_ms       INTEGER,
          cron_expression   TEXT,
          event_pattern     TEXT,
          fire_at           TEXT,
          created_at        TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS workflow_trigger_states (
          trigger_id        TEXT PRIMARY KEY,
          fire_count        INTEGER NOT NULL DEFAULT 0,
          last_fired_at     TEXT,
          next_fire_at      TEXT,
          status            TEXT NOT NULL DEFAULT 'active',
          last_error        TEXT,
          FOREIGN KEY (trigger_id) REFERENCES workflow_triggers(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_workflow_triggers_kind
          ON workflow_triggers (kind);
        CREATE INDEX IF NOT EXISTS idx_workflow_triggers_workflow_id
          ON workflow_triggers (workflow_id);
        CREATE INDEX IF NOT EXISTS idx_workflow_triggers_enabled
          ON workflow_triggers (enabled);
      `)

      this.db.prepare('DELETE FROM trigger_schema_version').run()
      this.db.prepare('INSERT INTO trigger_schema_version (version) VALUES (?)').run(TRIGGER_SCHEMA_VERSION)
      this.logger.info('Workflow trigger store schema v1 created')
    }
  }

  private prepareStatements() {
    return {
      upsertTrigger: this.db.prepare(`
        INSERT INTO workflow_triggers (
          id, kind, workflow_id, description, enabled, max_fires,
          input_json, interval_ms, cron_expression, event_pattern, fire_at
        ) VALUES (
          @id, @kind, @workflow_id, @description, @enabled, @max_fires,
          @input_json, @interval_ms, @cron_expression, @event_pattern, @fire_at
        )
        ON CONFLICT (id) DO UPDATE SET
          kind = @kind,
          workflow_id = @workflow_id,
          description = @description,
          enabled = @enabled,
          max_fires = @max_fires,
          input_json = @input_json,
          interval_ms = @interval_ms,
          cron_expression = @cron_expression,
          event_pattern = @event_pattern,
          fire_at = @fire_at,
          updated_at = datetime('now')
      `),

      loadTrigger: this.db.prepare(`
        SELECT * FROM workflow_triggers WHERE id = ?
      `),

      listAll: this.db.prepare(`
        SELECT * FROM workflow_triggers ORDER BY updated_at DESC LIMIT ?
      `),

      listByWorkflow: this.db.prepare(`
        SELECT * FROM workflow_triggers WHERE workflow_id = ?
        ORDER BY updated_at DESC LIMIT ?
      `),

      listByKind: this.db.prepare(`
        SELECT * FROM workflow_triggers WHERE kind = ?
        ORDER BY updated_at DESC LIMIT ?
      `),

      listByEnabled: this.db.prepare(`
        SELECT * FROM workflow_triggers WHERE enabled = ?
        ORDER BY updated_at DESC LIMIT ?
      `),

      listByWorkflowAndKind: this.db.prepare(`
        SELECT * FROM workflow_triggers WHERE workflow_id = ? AND kind = ?
        ORDER BY updated_at DESC LIMIT ?
      `),

      deleteTrigger: this.db.prepare(`
        DELETE FROM workflow_triggers WHERE id = ?
      `),

      upsertState: this.db.prepare(`
        INSERT INTO workflow_trigger_states (
          trigger_id, fire_count, last_fired_at, next_fire_at, status, last_error
        ) VALUES (
          @trigger_id, @fire_count, @last_fired_at, @next_fire_at, @status, @last_error
        )
        ON CONFLICT (trigger_id) DO UPDATE SET
          fire_count = @fire_count,
          last_fired_at = @last_fired_at,
          next_fire_at = @next_fire_at,
          status = @status,
          last_error = @last_error
      `),

      loadState: this.db.prepare(`
        SELECT * FROM workflow_trigger_states WHERE trigger_id = ?
      `),

      deleteState: this.db.prepare(`
        DELETE FROM workflow_trigger_states WHERE trigger_id = ?
      `),

      statsByKind: this.db.prepare(`
        SELECT kind, COUNT(*) as count FROM workflow_triggers GROUP BY kind
      `),

      countEnabled: this.db.prepare(`
        SELECT COUNT(*) as count FROM workflow_triggers WHERE enabled = 1
      `),
    }
  }
}
