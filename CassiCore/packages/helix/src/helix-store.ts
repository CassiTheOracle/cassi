/**
 * HelixStore — SQLite-backed persistence for Helix agent sessions.
 *
 * Lives at ~/.cassicore/data/helix.db (separate from dyad.db and lumen.db)
 * Persists Helix session state, work stream messages, role conversations,
 * tool calls, and events.
 *
 * Design:
 *   - Sessions table: one row per Helix project invocation (status, result, metrics)
 *   - Work stream table: full WorkStream message log (work units, nudges, etc.)
 *   - Role conversations table: full message arrays per role (unity/yang/yin)
 *   - Tool calls table: individual tool executions per role
 *   - Events table: append-only audit log per session
 *
 * Pattern follows DyadStore (core/intelligence/dyad/dyad-store.ts) —
 * WAL mode, JSON blobs for nested state, minimal schema normalization.
 */

import fs from 'node:fs'
import path from 'node:path'

import Database from 'better-sqlite3'

import type { ILogger } from '../../../types/interfaces.js'
import type { BlackboardState, Report } from '../../../types/flux-team.js'
import { getDataDir } from '../../utils/paths.js'


const SCHEMA_VERSION = 1
const DEFAULT_MAX_AGE_DAYS = 7

export type HelixRole = 'unity' | 'yang' | 'yin' | 'mentor'


const SCHEMA_SQL = `
  CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);

  CREATE TABLE IF NOT EXISTS helix_sessions (
    id                    TEXT PRIMARY KEY,
    goal                  TEXT NOT NULL,
    context               TEXT,
    status                TEXT NOT NULL DEFAULT 'running',
    unity_summary         TEXT,
    yang_summary          TEXT,
    yin_summary           TEXT,
    unity_conclusion      TEXT,
    yang_conclusion       TEXT,
    yin_conclusion        TEXT,
    convergence_points    TEXT DEFAULT '[]',
    unresolved_tensions   TEXT DEFAULT '[]',
    dialectic_stats       TEXT DEFAULT '{}',
    quality_score         REAL,
    remaining_issues      TEXT DEFAULT '[]',
    work_units_produced   INTEGER DEFAULT 0,
    nudges_sent           INTEGER DEFAULT 0,
    nudges_acknowledged   INTEGER DEFAULT 0,
    tokens_unity          INTEGER DEFAULT 0,
    tokens_yang           INTEGER DEFAULT 0,
    tokens_yin            INTEGER DEFAULT 0,
    iterations_unity      INTEGER DEFAULT 0,
    iterations_yang       INTEGER DEFAULT 0,
    iterations_yin        INTEGER DEFAULT 0,
    tool_calls_unity      INTEGER DEFAULT 0,
    tool_calls_yang       INTEGER DEFAULT 0,
    tool_calls_yin        INTEGER DEFAULT 0,
    files_modified        TEXT DEFAULT '[]',
    report_json           TEXT,
    blackboard_snapshot   TEXT,
    duration_ms           INTEGER,
    error                 TEXT,
    model                 TEXT,
    provider              TEXT,
    created_at            INTEGER NOT NULL,
    completed_at          INTEGER
  );

  CREATE TABLE IF NOT EXISTS helix_work_stream (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    msg_type        TEXT NOT NULL,
    from_role       TEXT,
    content         TEXT NOT NULL,
    timestamp       INTEGER NOT NULL,
    FOREIGN KEY (session_id) REFERENCES helix_sessions(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS helix_conversations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    role            TEXT NOT NULL,
    turn_index      INTEGER NOT NULL,
    msg_role        TEXT NOT NULL,
    content_json    TEXT NOT NULL,
    tokens_used     INTEGER DEFAULT 0,
    timestamp       INTEGER NOT NULL,
    FOREIGN KEY (session_id) REFERENCES helix_sessions(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS helix_tool_calls (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    role            TEXT NOT NULL,
    tool_name       TEXT NOT NULL,
    tool_call_id    TEXT,
    is_meta_tool    BOOLEAN DEFAULT 0,
    input_json      TEXT NOT NULL,
    result          TEXT,
    is_error        BOOLEAN DEFAULT 0,
    duration_ms     INTEGER DEFAULT 0,
    turn_index      INTEGER,
    timestamp       INTEGER NOT NULL,
    FOREIGN KEY (session_id) REFERENCES helix_sessions(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS helix_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    type            TEXT NOT NULL,
    entity          TEXT,
    message         TEXT NOT NULL,
    data_json       TEXT,
    timestamp       INTEGER NOT NULL,
    FOREIGN KEY (session_id) REFERENCES helix_sessions(id) ON DELETE CASCADE
  );

  CREATE INDEX IF NOT EXISTS idx_helix_ws_session ON helix_work_stream(session_id, timestamp);
  CREATE INDEX IF NOT EXISTS idx_helix_conv_session ON helix_conversations(session_id, role, turn_index);
  CREATE INDEX IF NOT EXISTS idx_helix_tc_session ON helix_tool_calls(session_id, role);
  CREATE INDEX IF NOT EXISTS idx_helix_events_session ON helix_events(session_id, timestamp);
  CREATE INDEX IF NOT EXISTS idx_helix_sessions_status ON helix_sessions(status);
  CREATE INDEX IF NOT EXISTS idx_helix_sessions_created ON helix_sessions(created_at);
`


export class HelixStore {
  private db: InstanceType<typeof Database>
  private logger: ILogger

  private _stmts?: {
    insertSession: Database.Statement
    updateSession: Database.Statement
    failSession: Database.Statement
    insertWorkStreamMessage: Database.Statement
    insertConversation: Database.Statement
    insertToolCall: Database.Statement
    insertEvent: Database.Statement
    selectSession: Database.Statement
    selectSessions: Database.Statement
    selectWorkStreamMessages: Database.Statement
    selectConversations: Database.Statement
    selectToolCalls: Database.Statement
    selectEvents: Database.Statement
    pruneOld: Database.Statement
  }

  private constructor(dbPath: string, logger: ILogger) {
    this.logger = logger.child('helix-store')
    this.db = new Database(dbPath)
    this.db.pragma('journal_mode = WAL')
    this.db.pragma('synchronous = NORMAL')
    this.db.pragma('foreign_keys = ON')
    this.db.pragma('busy_timeout = 5000')
    this.migrate()
  }


  static open(logger: ILogger, dataDir?: string, maxAgeDays = DEFAULT_MAX_AGE_DAYS): HelixStore {
    const dir = dataDir ?? getDataDir()
    fs.mkdirSync(dir, { recursive: true })
    const dbPath = path.join(dir, 'helix.db')
    const store = new HelixStore(dbPath, logger)
    const pruned = store.prune(maxAgeDays)
    if (pruned > 0) store.logger.info(`Pruned ${pruned} stale helix session(s) (>${maxAgeDays}d old)`)
    store.logger.info(`HelixStore open — ${dbPath}`)
    return store
  }


  private migrate(): void {
    const row = this.db.prepare(
      `SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'`
    ).get() as { name: string } | undefined

    if (!row) {
      this.db.exec(SCHEMA_SQL)
      this.db.prepare('INSERT INTO schema_version (version) VALUES (?)').run(SCHEMA_VERSION)
      return
    }

    const versionRow = this.db.prepare('SELECT version FROM schema_version LIMIT 1').get() as { version: number } | undefined
    const current = versionRow?.version ?? 0

    if (current < SCHEMA_VERSION) {
      // Future migrations go here
      this.db.prepare('UPDATE schema_version SET version = ?').run(SCHEMA_VERSION)
    }
  }


  private get stmts() {
    if (!this._stmts) {
      this._stmts = {
        insertSession: this.db.prepare(`
          INSERT INTO helix_sessions (id, goal, context, status, model, provider, created_at)
          VALUES (@id, @goal, @context, @status, @model, @provider, @created_at)
        `),
        updateSession: this.db.prepare(`
          UPDATE helix_sessions SET
            status = @status,
            unity_summary = @unity_summary,
            yang_summary = @yang_summary,
            yin_summary = @yin_summary,
            unity_conclusion = @unity_conclusion,
            yang_conclusion = @yang_conclusion,
            yin_conclusion = @yin_conclusion,
            convergence_points = @convergence_points,
            unresolved_tensions = @unresolved_tensions,
            dialectic_stats = @dialectic_stats,
            quality_score = @quality_score,
            remaining_issues = @remaining_issues,
            work_units_produced = @work_units_produced,
            nudges_sent = @nudges_sent,
            nudges_acknowledged = @nudges_acknowledged,
            tokens_unity = @tokens_unity,
            tokens_yang = @tokens_yang,
            tokens_yin = @tokens_yin,
            iterations_unity = @iterations_unity,
            iterations_yang = @iterations_yang,
            iterations_yin = @iterations_yin,
            tool_calls_unity = @tool_calls_unity,
            tool_calls_yang = @tool_calls_yang,
            tool_calls_yin = @tool_calls_yin,
            files_modified = @files_modified,
            report_json = @report_json,
            blackboard_snapshot = @blackboard_snapshot,
            duration_ms = @duration_ms,
            error = @error,
            completed_at = @completed_at
          WHERE id = @id
        `),
        failSession: this.db.prepare(`
          UPDATE helix_sessions SET status = @status, error = @error, completed_at = @completed_at WHERE id = @id
        `),
        insertWorkStreamMessage: this.db.prepare(`
          INSERT INTO helix_work_stream (session_id, msg_type, from_role, content, timestamp)
          VALUES (@session_id, @msg_type, @from_role, @content, @timestamp)
        `),
        insertConversation: this.db.prepare(`
          INSERT INTO helix_conversations (session_id, role, turn_index, msg_role, content_json, tokens_used, timestamp)
          VALUES (@session_id, @role, @turn_index, @msg_role, @content_json, @tokens_used, @timestamp)
        `),
        insertToolCall: this.db.prepare(`
          INSERT INTO helix_tool_calls (session_id, role, tool_name, tool_call_id, is_meta_tool, input_json, result, is_error, duration_ms, turn_index, timestamp)
          VALUES (@session_id, @role, @tool_name, @tool_call_id, @is_meta_tool, @input_json, @result, @is_error, @duration_ms, @turn_index, @timestamp)
        `),
        insertEvent: this.db.prepare(`
          INSERT INTO helix_events (session_id, type, entity, message, data_json, timestamp)
          VALUES (@session_id, @type, @entity, @message, @data_json, @timestamp)
        `),
        selectSession: this.db.prepare('SELECT * FROM helix_sessions WHERE id = ?'),
        selectSessions: this.db.prepare(`
          SELECT * FROM helix_sessions WHERE (@status IS NULL OR status = @status) ORDER BY created_at DESC LIMIT @limit
        `),
        selectWorkStreamMessages: this.db.prepare(
          'SELECT * FROM helix_work_stream WHERE session_id = ? ORDER BY timestamp ASC'
        ),
        selectConversations: this.db.prepare(
          'SELECT * FROM helix_conversations WHERE session_id = @session_id AND (@role IS NULL OR role = @role) ORDER BY turn_index ASC'
        ),
        selectToolCalls: this.db.prepare(
          'SELECT * FROM helix_tool_calls WHERE session_id = @session_id AND (@role IS NULL OR role = @role) ORDER BY timestamp ASC'
        ),
        selectEvents: this.db.prepare('SELECT * FROM helix_events WHERE session_id = ? ORDER BY timestamp ASC'),
        pruneOld: this.db.prepare(`
          DELETE FROM helix_sessions WHERE status IN ('completed', 'failed', 'timeout', 'cancelled') AND created_at < ?
        `),
      }
    }
    return this._stmts
  }


  createSession(id: string, goal: string, context?: string, meta?: { model?: string; provider?: string }): void {
    this.stmts.insertSession.run({
      id, goal, context: context ?? null, status: 'running',
      model: meta?.model ?? null, provider: meta?.provider ?? null, created_at: Date.now(),
    })
    this.logger.debug(`Created Helix session ${id}`, { goal })
  }

  completeSession(id: string, result: HelixResultLike): void {
    this.stmts.updateSession.run({
      id, status: 'completed',
      unity_summary: result.unitySummary ?? result.unityConclusion ?? null,
      yang_summary: result.yangSummary ?? result.yangConclusion ?? null,
      yin_summary: result.yinSummary ?? result.yinConclusion ?? null,
      unity_conclusion: result.unityConclusion ?? null,
      yang_conclusion: result.yangConclusion ?? null,
      yin_conclusion: result.yinConclusion ?? null,
      convergence_points: JSON.stringify(result.convergencePoints ?? []),
      unresolved_tensions: JSON.stringify(result.unresolvedTensions ?? []),
      dialectic_stats: JSON.stringify(result.dialecticStats ?? {}),
      quality_score: result.qualityScore ?? null,
      remaining_issues: JSON.stringify(result.remainingIssues ?? []),
      work_units_produced: result.pipelineStats?.workUnitsProduced ?? 0,
      nudges_sent: result.pipelineStats?.nudgesSent ?? 0,
      nudges_acknowledged: result.pipelineStats?.nudgesAcknowledged ?? 0,
      tokens_unity: result.tokensUsed?.unity ?? 0,
      tokens_yang: result.tokensUsed?.yang ?? 0,
      tokens_yin: result.tokensUsed?.yin ?? 0,
      iterations_unity: result.iterationCounts?.unity ?? 0,
      iterations_yang: result.iterationCounts?.yang ?? 0,
      iterations_yin: result.iterationCounts?.yin ?? 0,
      tool_calls_unity: result.toolCallCounts?.unity ?? 0,
      tool_calls_yang: result.toolCallCounts?.yang ?? 0,
      tool_calls_yin: result.toolCallCounts?.yin ?? 0,
      files_modified: JSON.stringify(result.filesModified ?? []),
      report_json: JSON.stringify(result.report ?? null),
      blackboard_snapshot: JSON.stringify(result.blackboard ?? null),
      duration_ms: result.durationMs ?? null,
      error: result.error ?? null,
      completed_at: Date.now(),
    })
    this.logger.debug(`Completed Helix session ${id}`)
  }

  failSession(id: string, error: string): void {
    this.stmts.failSession.run({ id, status: 'failed', error, completed_at: Date.now() })
    this.logger.error(`Helix session ${id} failed`, { error })
  }


  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  saveWorkStreamMessages(sessionId: string, messages: any[]): void {
    if (!messages || messages.length === 0) return
    const txn = this.db.transaction(() => {
      for (const msg of messages) {
        this.stmts.insertWorkStreamMessage.run({
          session_id: sessionId,
          msg_type: String(msg.type ?? 'unknown'),
          from_role: this.extractFromRole(msg),
          content: JSON.stringify(msg),
          timestamp: msg.timestamp ?? Date.now(),
        })
      }
    })
    txn()
    this.logger.debug(`Saved ${messages.length} work stream message(s) for helix session ${sessionId}`)
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private extractFromRole(msg: any): string | null {
    switch (msg?.type) {
      case 'work_unit': return 'unity'
      case 'refinement': return 'unity'
      case 'nudge': return (msg as Record<string, unknown>).from === 'yang' ? 'yang' : 'yin'
      case 'nudge_ack': return 'unity'
      case 'research': return 'yang'
      case 'guidance': return 'yin'
      default: return null
    }
  }


  saveConversation(sessionId: string, role: HelixRole, turnIndex: number, msgRole: string, content: string | object, tokensUsed?: number): void {
    this.stmts.insertConversation.run({
      session_id: sessionId, role, turn_index: turnIndex, msg_role: msgRole,
      content_json: typeof content === 'string' ? content : JSON.stringify(content),
      tokens_used: tokensUsed ?? 0, timestamp: Date.now(),
    })
  }


  saveToolCall(sessionId: string, role: HelixRole, toolName: string, toolCallId: string, isMetaTool: boolean, input: unknown, result?: string, isError?: boolean, durationMs?: number, turnIndex?: number): void {
    this.stmts.insertToolCall.run({
      session_id: sessionId, role, tool_name: toolName, tool_call_id: toolCallId,
      is_meta_tool: isMetaTool ? 1 : 0, input_json: JSON.stringify(input),
      result: result ?? null, is_error: isError ? 1 : 0, duration_ms: durationMs ?? 0,
      turn_index: turnIndex ?? null, timestamp: Date.now(),
    })
  }


  appendEvent(sessionId: string, type: string, entity: string, message: string, data?: unknown): void {
    this.stmts.insertEvent.run({
      session_id: sessionId, type, entity, message,
      data_json: data ? JSON.stringify(data) : null, timestamp: Date.now(),
    })
  }


  getSession(id: string): HelixSessionRow | undefined {
    const row = this.stmts.selectSession.get(id) as RawHelixSessionRow | undefined
    if (!row) return undefined
    return this.rowToSession(row)
  }

  listSessions(limit = 100, status?: string): HelixSessionRow[] {
    const rows = this.stmts.selectSessions.all({ limit, status: status ?? null }) as RawHelixSessionRow[]
    return rows.map(r => this.rowToSession(r))
  }

  getWorkStreamMessages(sessionId: string): WorkStreamMessageRow[] {
    const rows = this.stmts.selectWorkStreamMessages.all(sessionId) as RawWorkStreamMessageRow[]
    return rows.map(r => ({
      id: r.id, sessionId: r.session_id, msgType: r.msg_type,
      fromRole: r.from_role as HelixRole | null, content: r.content, timestamp: r.timestamp,
    }))
  }

  getConversations(sessionId: string, role?: HelixRole): ConversationRow[] {
    const rows = this.stmts.selectConversations.all({ session_id: sessionId, role: role ?? null }) as RawConversationRow[]
    return rows.map(r => ({
      id: r.id, sessionId: r.session_id, role: r.role as HelixRole, turnIndex: r.turn_index,
      msgRole: r.msg_role, contentJson: r.content_json, tokensUsed: r.tokens_used, timestamp: r.timestamp,
    }))
  }

  getToolCalls(sessionId: string, role?: HelixRole): ToolCallRow[] {
    const rows = this.stmts.selectToolCalls.all({ session_id: sessionId, role: role ?? null }) as RawToolCallRow[]
    return rows.map(r => ({
      id: r.id, sessionId: r.session_id, role: r.role as HelixRole, toolName: r.tool_name,
      toolCallId: r.tool_call_id ?? undefined, isMetaTool: r.is_meta_tool === 1,
      inputJson: r.input_json, result: r.result ?? undefined, isError: r.is_error === 1,
      durationMs: r.duration_ms, turnIndex: r.turn_index ?? undefined, timestamp: r.timestamp,
    }))
  }

  getEvents(sessionId: string, limit?: number): EventRow[] {
    const rows = this.stmts.selectEvents.all(sessionId) as RawEventRow[]
    const result = rows.map(r => ({
      id: r.id, sessionId: r.session_id, type: r.type, entity: r.entity ?? undefined,
      message: r.message, dataJson: r.data_json ?? undefined, timestamp: r.timestamp,
    }))
    return limit ? result.slice(-limit) : result
  }


  prune(maxAgeDays = DEFAULT_MAX_AGE_DAYS): number {
    const cutoff = Date.now() - maxAgeDays * 86_400_000
    return this.stmts.pruneOld.run(cutoff).changes
  }

  close(): void {
    this.db.close()
    this.logger.info('HelixStore closed')
  }


  private rowToSession(row: RawHelixSessionRow): HelixSessionRow {
    return {
      id: row.id, goal: row.goal, context: row.context ?? undefined, status: row.status,
      unitySummary: row.unity_summary ?? undefined, yangSummary: row.yang_summary ?? undefined,
      yinSummary: row.yin_summary ?? undefined,
      unityConclusion: row.unity_conclusion ?? undefined, yangConclusion: row.yang_conclusion ?? undefined,
      yinConclusion: row.yin_conclusion ?? undefined,
      convergencePoints: JSON.parse(row.convergence_points),
      unresolvedTensions: JSON.parse(row.unresolved_tensions),
      dialecticStats: JSON.parse(row.dialectic_stats),
      qualityScore: row.quality_score ?? undefined, remainingIssues: JSON.parse(row.remaining_issues),
      workUnitsProduced: row.work_units_produced,
      nudgesSent: row.nudges_sent, nudgesAcknowledged: row.nudges_acknowledged,
      tokensUnity: row.tokens_unity, tokensYang: row.tokens_yang, tokensYin: row.tokens_yin,
      iterationsUnity: row.iterations_unity, iterationsYang: row.iterations_yang, iterationsYin: row.iterations_yin,
      toolCallsUnity: row.tool_calls_unity, toolCallsYang: row.tool_calls_yang, toolCallsYin: row.tool_calls_yin,
      filesModified: JSON.parse(row.files_modified),
      report: row.report_json ? JSON.parse(row.report_json) as Report : undefined,
      blackboard: row.blackboard_snapshot ? JSON.parse(row.blackboard_snapshot) as BlackboardState : undefined,
      durationMs: row.duration_ms ?? undefined, error: row.error ?? undefined,
      model: row.model ?? undefined, provider: row.provider ?? undefined,
      createdAt: row.created_at, completedAt: row.completed_at ?? undefined,
    }
  }
}


// ── Result-like interface for completeSession() ──────────────────────────────

/** Subset of HelixResult accepted by completeSession(). */
export interface HelixResultLike {
  unitySummary?: string
  yangSummary?: string
  yinSummary?: string
  unityConclusion?: string
  yangConclusion?: string
  yinConclusion?: string
  convergencePoints?: unknown[]
  unresolvedTensions?: unknown[]
  dialecticStats?: Record<string, unknown>
  qualityScore?: number
  remainingIssues?: string[]
  filesModified?: unknown[]
  tokensUsed?: { unity: number; yang: number; yin: number }
  iterationCounts?: { unity: number; yang: number; yin: number }
  toolCallCounts?: { unity: number; yang: number; yin: number }
  pipelineStats?: { workUnitsProduced: number; nudgesSent: number; nudgesAcknowledged: number }
  durationMs?: number
  error?: string
  report?: Report
  blackboard?: BlackboardState
}


// ── Row types ────────────────────────────────────────────────────────────────

export interface HelixSessionRow {
  id: string; goal: string; context?: string; status: string
  unitySummary?: string; yangSummary?: string; yinSummary?: string
  unityConclusion?: string; yangConclusion?: string; yinConclusion?: string
  convergencePoints: unknown[]; unresolvedTensions: unknown[]
  dialecticStats: Record<string, unknown>
  qualityScore?: number; remainingIssues: string[]
  workUnitsProduced: number
  nudgesSent: number; nudgesAcknowledged: number
  tokensUnity: number; tokensYang: number; tokensYin: number
  iterationsUnity: number; iterationsYang: number; iterationsYin: number
  toolCallsUnity: number; toolCallsYang: number; toolCallsYin: number
  report?: Report; blackboard?: BlackboardState
  filesModified: unknown[]; durationMs?: number; error?: string
  model?: string; provider?: string; createdAt: number; completedAt?: number
}

export interface WorkStreamMessageRow {
  id: number; sessionId: string; msgType: string; fromRole: HelixRole | null
  content: string; timestamp: number
}

export interface ConversationRow {
  id: number; sessionId: string; role: HelixRole; turnIndex: number
  msgRole: string; contentJson: string; tokensUsed: number; timestamp: number
}

export interface ToolCallRow {
  id: number; sessionId: string; role: HelixRole; toolName: string; toolCallId?: string
  isMetaTool: boolean; inputJson: string; result?: string; isError: boolean
  durationMs: number; turnIndex?: number; timestamp: number
}

export interface EventRow {
  id: number; sessionId: string; type: string; entity?: string
  message: string; dataJson?: string; timestamp: number
}


// ── Raw SQLite row shapes ────────────────────────────────────────────────────

interface RawHelixSessionRow {
  id: string; goal: string; context: string | null; status: string
  unity_summary: string | null; yang_summary: string | null; yin_summary: string | null
  unity_conclusion: string | null; yang_conclusion: string | null; yin_conclusion: string | null
  convergence_points: string; unresolved_tensions: string; dialectic_stats: string
  quality_score: number | null; remaining_issues: string
  work_units_produced: number
  nudges_sent: number; nudges_acknowledged: number
  tokens_unity: number; tokens_yang: number; tokens_yin: number
  iterations_unity: number; iterations_yang: number; iterations_yin: number
  tool_calls_unity: number; tool_calls_yang: number; tool_calls_yin: number
  report_json: string | null; blackboard_snapshot: string | null
  files_modified: string; duration_ms: number | null; error: string | null
  model: string | null; provider: string | null
  created_at: number; completed_at: number | null
}

interface RawWorkStreamMessageRow {
  id: number; session_id: string; msg_type: string; from_role: string | null
  content: string; timestamp: number
}

interface RawConversationRow {
  id: number; session_id: string; role: string; turn_index: number
  msg_role: string; content_json: string; tokens_used: number; timestamp: number
}

interface RawToolCallRow {
  id: number; session_id: string; role: string; tool_name: string; tool_call_id: string | null
  is_meta_tool: number; input_json: string; result: string | null; is_error: number
  duration_ms: number; turn_index: number | null; timestamp: number
}

interface RawEventRow {
  id: number; session_id: string; type: string; entity: string | null
  message: string; data_json: string | null; timestamp: number
}
