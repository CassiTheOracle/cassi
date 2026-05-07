/**
 * B1 CompositionStore — SQLite persistence for named compositions and their
 * invocation log. Owns its own DB or shares one (see MeditationSeeder pattern).
 *
 * Tables (Section 4.1 of aurora-concept-arithmetic.md):
 *   aurora_compositions             — named definitions
 *   aurora_composition_invocations  — runtime invocation audit
 */

import * as fs from 'fs'
import * as path from 'path'
import Database from 'better-sqlite3'

import type { ILogger } from '../../../../types/interfaces.js'
import type {
  CompositionAst,
  CompositionRecord,
  InvocationRecord,
  InvocationTrigger,
} from './types.js'

const SCHEMA_V1 = `
  CREATE TABLE IF NOT EXISTS aurora_compositions_schema_version (
    version INTEGER PRIMARY KEY
  );

  CREATE TABLE IF NOT EXISTS aurora_compositions (
    name              TEXT PRIMARY KEY,
    dsl               TEXT NOT NULL,
    ast               TEXT NOT NULL,
    layer_policy      TEXT NOT NULL DEFAULT 'all',
    affect_modulated  INTEGER NOT NULL DEFAULT 0,
    suppressive       INTEGER NOT NULL DEFAULT 0,
    vindex_id         TEXT NOT NULL DEFAULT 'default',
    description       TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    metadata          TEXT NOT NULL DEFAULT '{}'
  );

  CREATE TABLE IF NOT EXISTS aurora_composition_invocations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL REFERENCES aurora_compositions(name) ON DELETE CASCADE,
    invoked_at    TEXT NOT NULL,
    session_id    TEXT,
    trigger       TEXT NOT NULL DEFAULT 'manual',
    resolved_norm REAL,
    metadata      TEXT NOT NULL DEFAULT '{}'
  );

  CREATE INDEX IF NOT EXISTS idx_composition_invocations_name
    ON aurora_composition_invocations(name);
  CREATE INDEX IF NOT EXISTS idx_composition_invocations_invoked_at
    ON aurora_composition_invocations(invoked_at);

  INSERT OR IGNORE INTO aurora_compositions_schema_version (version) VALUES (1);
`

/**
 * B2.2 schema bump — add retrieval_policy_json column to aurora_compositions
 * (NULL = no policy, JSON-serialized RetrievalPolicySpec otherwise).
 */
const SCHEMA_V2_MIGRATION = `
  ALTER TABLE aurora_compositions
    ADD COLUMN retrieval_policy_json TEXT;
`

interface CompositionRow {
  name: string
  dsl: string
  ast: string
  layer_policy: string
  affect_modulated: number
  suppressive: number
  vindex_id: string
  description: string | null
  created_at: string
  updated_at: string
  metadata: string
  retrieval_policy_json: string | null
}

interface InvocationRow {
  id: number
  name: string
  invoked_at: string
  session_id: string | null
  trigger: string
  resolved_norm: number | null
  metadata: string
}

export class CompositionStore {
  private readonly logger: ILogger
  private readonly db: Database.Database
  private readonly ownsDb: boolean

  private stmtUpsertComposition!: Database.Statement
  private stmtGetComposition!: Database.Statement
  private stmtListCompositions!: Database.Statement
  private stmtDeleteComposition!: Database.Statement
  private stmtInsertInvocation!: Database.Statement
  private stmtListInvocations!: Database.Statement

  constructor(dbOrPath: string | Database.Database, logger: ILogger) {
    this.logger = logger.child ? logger.child('aurora:composition-store') : logger

    if (typeof dbOrPath === 'string') {
      const dir = path.dirname(dbOrPath)
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
      this.db = new Database(dbOrPath)
      this.db.pragma('journal_mode = WAL')
      this.db.pragma('busy_timeout = 5000')
      this.db.pragma('synchronous = NORMAL')
      this.ownsDb = true
    } else {
      this.db = dbOrPath
      this.ownsDb = false
    }

    this.initSchema()
    this.prepareStatements()
  }

  private initSchema(): void {
    this.db.exec(SCHEMA_V1)
    const versionRow = this.db
      .prepare(`SELECT MAX(version) AS v FROM aurora_compositions_schema_version`)
      .get() as { v: number | null }
    const current = versionRow.v ?? 1
    if (current < 2) {
      // ALTER TABLE is idempotent-safe via try/catch on the duplicate-column
      // error: when the column already exists (e.g. if the row never made it
      // to the version table after a prior migration attempt), we tolerate
      // it and just bump the version row.
      try {
        this.db.exec(SCHEMA_V2_MIGRATION)
      } catch (err: any) {
        if (!String(err?.message ?? '').includes('duplicate column')) throw err
      }
      this.db.prepare(`INSERT OR IGNORE INTO aurora_compositions_schema_version (version) VALUES (2)`).run()
    }
  }

  private prepareStatements(): void {
    this.stmtUpsertComposition = this.db.prepare(`
      INSERT INTO aurora_compositions
        (name, dsl, ast, layer_policy, affect_modulated, suppressive, vindex_id,
         description, created_at, updated_at, metadata, retrieval_policy_json)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(name) DO UPDATE SET
        dsl                   = excluded.dsl,
        ast                   = excluded.ast,
        layer_policy          = excluded.layer_policy,
        affect_modulated      = excluded.affect_modulated,
        suppressive           = excluded.suppressive,
        vindex_id             = excluded.vindex_id,
        description           = excluded.description,
        updated_at            = excluded.updated_at,
        metadata              = excluded.metadata,
        retrieval_policy_json = excluded.retrieval_policy_json
    `)
    this.stmtGetComposition = this.db.prepare(
      `SELECT * FROM aurora_compositions WHERE name = ?`,
    )
    this.stmtListCompositions = this.db.prepare(
      `SELECT * FROM aurora_compositions ORDER BY name ASC`,
    )
    this.stmtDeleteComposition = this.db.prepare(
      `DELETE FROM aurora_compositions WHERE name = ?`,
    )
    this.stmtInsertInvocation = this.db.prepare(`
      INSERT INTO aurora_composition_invocations
        (name, invoked_at, session_id, trigger, resolved_norm, metadata)
      VALUES (?, ?, ?, ?, ?, ?)
    `)
    this.stmtListInvocations = this.db.prepare(`
      SELECT * FROM aurora_composition_invocations
      WHERE invoked_at >= ?
      ORDER BY invoked_at DESC
      LIMIT ?
    `)
  }

  upsertComposition(rec: Omit<CompositionRecord, 'createdAt' | 'updatedAt'> & { createdAt?: string; updatedAt?: string }): CompositionRecord {
    const now = new Date().toISOString()
    const createdAt = rec.createdAt ?? now
    const updatedAt = rec.updatedAt ?? now
    this.stmtUpsertComposition.run(
      rec.name,
      rec.dsl,
      JSON.stringify(rec.ast),
      rec.layerPolicy,
      rec.affectModulated ? 1 : 0,
      rec.suppressive ? 1 : 0,
      rec.vindexId,
      rec.description,
      createdAt,
      updatedAt,
      JSON.stringify(rec.metadata ?? {}),
      rec.retrievalPolicy === null || rec.retrievalPolicy === undefined
        ? null
        : JSON.stringify(rec.retrievalPolicy),
    )
    return {
      ...rec,
      createdAt,
      updatedAt,
      metadata: rec.metadata ?? {},
      retrievalPolicy: rec.retrievalPolicy ?? null,
    }
  }

  getComposition(name: string): CompositionRecord | null {
    const row = this.stmtGetComposition.get(name) as CompositionRow | undefined
    return row ? this.rowToRecord(row) : null
  }

  listCompositions(): CompositionRecord[] {
    const rows = this.stmtListCompositions.all() as CompositionRow[]
    return rows.map(r => this.rowToRecord(r))
  }

  deleteComposition(name: string): boolean {
    const res = this.stmtDeleteComposition.run(name)
    return res.changes > 0
  }

  recordInvocation(opts: {
    name: string
    sessionId?: string | null
    trigger?: InvocationTrigger
    resolvedNorm?: number | null
    metadata?: Record<string, unknown>
    invokedAt?: string
  }): InvocationRecord {
    const invokedAt = opts.invokedAt ?? new Date().toISOString()
    const trigger = opts.trigger ?? 'manual'
    const result = this.stmtInsertInvocation.run(
      opts.name,
      invokedAt,
      opts.sessionId ?? null,
      trigger,
      opts.resolvedNorm ?? null,
      JSON.stringify(opts.metadata ?? {}),
    )
    return {
      id: Number(result.lastInsertRowid),
      name: opts.name,
      invokedAt,
      sessionId: opts.sessionId ?? null,
      trigger,
      resolvedNorm: opts.resolvedNorm ?? null,
      metadata: opts.metadata ?? {},
    }
  }

  listInvocations(opts: { since?: string; limit?: number } = {}): InvocationRecord[] {
    const since = opts.since ?? '1970-01-01T00:00:00.000Z'
    const limit = opts.limit ?? 100
    const rows = this.stmtListInvocations.all(since, limit) as InvocationRow[]
    return rows.map(r => ({
      id: r.id,
      name: r.name,
      invokedAt: r.invoked_at,
      sessionId: r.session_id,
      trigger: r.trigger as InvocationTrigger,
      resolvedNorm: r.resolved_norm,
      metadata: parseJsonOr(r.metadata, {}),
    }))
  }

  close(): void {
    if (this.ownsDb && this.db.open) this.db.close()
  }

  private rowToRecord(row: CompositionRow): CompositionRecord {
    return {
      name: row.name,
      dsl: row.dsl,
      ast: JSON.parse(row.ast) as CompositionAst,
      layerPolicy: row.layer_policy,
      affectModulated: row.affect_modulated === 1,
      suppressive: row.suppressive === 1,
      vindexId: row.vindex_id,
      description: row.description,
      createdAt: row.created_at,
      updatedAt: row.updated_at,
      metadata: parseJsonOr(row.metadata, {}),
      retrievalPolicy: row.retrieval_policy_json
        ? parseJsonOr<import('./types.js').RetrievalPolicySpec | null>(row.retrieval_policy_json, null)
        : null,
    }
  }
}

function parseJsonOr<T>(text: string, fallback: T): T {
  try { return JSON.parse(text) as T } catch { return fallback }
}
