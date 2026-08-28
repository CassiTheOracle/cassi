/**
 * SelfEditStore — SQLite persistence for the self-edit system.
 *
 * Stores friction signals, edit requests, evaluations, and applied edits.
 * This is the corpus of self-improvement experience that Cassi draws on
 * when deciding whether to approve future edit requests.
 *
 * The store intentionally does NOT compute scores or metrics.
 * It stores factual observations and lets the consumer (Cassi) make
 * qualitative judgments about what the data means.
 */

import { v4 as uuidv4 } from 'uuid'

import type {
  FrictionSignal,
  FrictionKind,
  EditRequest,
  EditRequestStatus,
  EditEvaluation,
  AppliedEdit,
  ISelfEditStore,
  SelfEditStats,
} from './self-edit-types.js'
import type { ILogger } from './vendor/types/interfaces.js'

type Database = import('better-sqlite3').Database


/** Schema version for migration tracking */
const SCHEMA_VERSION = 1

const SCHEMA_SQL = `
  CREATE TABLE IF NOT EXISTS self_edit_friction (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    kind TEXT NOT NULL,
    what_happened TEXT NOT NULL,
    context TEXT NOT NULL,
    involved_paths TEXT NOT NULL DEFAULT '[]',
    recurrence INTEGER NOT NULL DEFAULT 1,
    observed_at INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    posture TEXT
  );

  CREATE INDEX IF NOT EXISTS idx_friction_kind ON self_edit_friction(kind);
  CREATE INDEX IF NOT EXISTS idx_friction_session ON self_edit_friction(session_id);
  CREATE INDEX IF NOT EXISTS idx_friction_observed ON self_edit_friction(observed_at);

  CREATE TABLE IF NOT EXISTS self_edit_requests (
    id TEXT PRIMARY KEY,
    source_session_id TEXT NOT NULL,
    source_helix_id TEXT,
    source_posture TEXT,
    edit_kind TEXT NOT NULL,
    signals_json TEXT NOT NULL DEFAULT '{}',
    suggestion_json TEXT NOT NULL DEFAULT '{}',
    cross_session_recurrence INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    authority TEXT NOT NULL DEFAULT 'local',
    evaluated_by TEXT,
    evaluated_at INTEGER,
    evaluation_reason TEXT
  );

  CREATE INDEX IF NOT EXISTS idx_requests_status ON self_edit_requests(status);
  CREATE INDEX IF NOT EXISTS idx_requests_created ON self_edit_requests(created_at);

  CREATE TABLE IF NOT EXISTS self_edit_evaluations (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    request_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    reasoning TEXT NOT NULL,
    considered_context_json TEXT NOT NULL DEFAULT '{}',
    modified_suggestion_json TEXT,
    analysis_findings_json TEXT,
    evaluated_at INTEGER NOT NULL,
    FOREIGN KEY (request_id) REFERENCES self_edit_requests(id)
  );

  CREATE INDEX IF NOT EXISTS idx_evaluations_request ON self_edit_evaluations(request_id);

  CREATE TABLE IF NOT EXISTS self_edit_applied (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    request_id TEXT NOT NULL,
    evaluation_id TEXT NOT NULL,
    files_modified TEXT NOT NULL DEFAULT '[]',
    commit_sha TEXT NOT NULL,
    before_snapshot_json TEXT NOT NULL DEFAULT '[]',
    applied_at INTEGER NOT NULL,
    post_edit_observations_json TEXT,
    reverted_at INTEGER,
    revert_reason TEXT,
    revert_commit_sha TEXT,
    FOREIGN KEY (request_id) REFERENCES self_edit_requests(id)
  );

  CREATE INDEX IF NOT EXISTS idx_applied_request ON self_edit_applied(request_id);
  CREATE INDEX IF NOT EXISTS idx_applied_at ON self_edit_applied(applied_at);

  CREATE TABLE IF NOT EXISTS self_edit_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
  );
`


export class SelfEditStore implements ISelfEditStore {
  private readonly db: Database
  private readonly logger: ILogger

  constructor(db: Database, logger: ILogger) {
    this.db = db
    this.logger = logger.child?.('self-edit-store') ?? logger

    this.ensureSchema()
  }

  private ensureSchema(): void {
    const currentVersion = this.getMetaValue('schema_version')
    if (currentVersion === String(SCHEMA_VERSION)) return

    this.db.exec(SCHEMA_SQL)
    this.setMetaValue('schema_version', String(SCHEMA_VERSION))
    this.logger.info('SelfEditStore: schema initialized', { version: SCHEMA_VERSION })
  }



  recordFriction(signal: FrictionSignal): void {
    this.db.prepare(`
      INSERT INTO self_edit_friction (kind, what_happened, context, involved_paths, recurrence, observed_at, session_id, posture)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      signal.kind,
      signal.whatHappened,
      signal.context,
      JSON.stringify(signal.involvedPaths),
      signal.recurrence,
      signal.observedAt,
      signal.sessionId,
      signal.posture ?? null,
    )
  }

  findFriction(opts: {
    kind?: FrictionKind
    pathPattern?: string
    since?: number
    limit?: number
  }): FrictionSignal[] {
    const conditions: string[] = []
    const params: unknown[] = []

    if (opts.kind) {
      conditions.push('kind = ?')
      params.push(opts.kind)
    }
    if (opts.pathPattern) {
      conditions.push('involved_paths LIKE ?')
      params.push(`%${opts.pathPattern}%`)
    }
    if (opts.since) {
      conditions.push('observed_at >= ?')
      params.push(opts.since)
    }

    const where = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : ''
    const limit = opts.limit ?? 50

    const rows = this.db.prepare(`
      SELECT * FROM self_edit_friction ${where}
      ORDER BY observed_at DESC LIMIT ?
    `).all(...params, limit) as any[]

    return rows.map(this.rowToFriction)
  }

  countCrossSessionFriction(kind: FrictionKind, pathPattern?: string, since?: number): number {
    const conditions: string[] = ['kind = ?']
    const params: unknown[] = [kind]

    if (pathPattern) {
      conditions.push('involved_paths LIKE ?')
      params.push(`%${pathPattern}%`)
    }
    if (since) {
      conditions.push('observed_at >= ?')
      params.push(since)
    }

    const where = conditions.join(' AND ')
    const row = this.db.prepare(`
      SELECT COUNT(DISTINCT session_id) as cnt FROM self_edit_friction WHERE ${where}
    `).get(...params) as { cnt: number }

    return row.cnt
  }



  submitRequest(request: EditRequest): void {
    this.db.prepare(`
      INSERT INTO self_edit_requests (id, source_session_id, source_helix_id, source_posture, edit_kind, signals_json, suggestion_json, cross_session_recurrence, created_at, status, authority)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      request.id,
      request.sourceSessionId,
      request.sourceHelixId ?? null,
      request.sourcePosture ?? null,
      request.editKind,
      JSON.stringify(request.signals),
      JSON.stringify(request.suggestion),
      request.crossSessionRecurrence,
      request.createdAt,
      request.status,
      request.authority,
    )
  }

  getPendingRequests(limit = 20): EditRequest[] {
    const rows = this.db.prepare(`
      SELECT * FROM self_edit_requests
      WHERE status = 'pending'
      ORDER BY cross_session_recurrence DESC, created_at ASC
      LIMIT ?
    `).all(limit) as any[]

    return rows.map(this.rowToRequest)
  }

  updateRequestStatus(requestId: string, status: EditRequestStatus, reason?: string): void {
    this.db.prepare(`
      UPDATE self_edit_requests
      SET status = ?, evaluation_reason = ?, evaluated_at = ?
      WHERE id = ?
    `).run(status, reason ?? null, Date.now(), requestId)
  }

  getRequest(requestId: string): EditRequest | undefined {
    const row = this.db.prepare(
      'SELECT * FROM self_edit_requests WHERE id = ?',
    ).get(requestId) as any

    return row ? this.rowToRequest(row) : undefined
  }



  recordEvaluation(evaluation: EditEvaluation): void {
    this.db.prepare(`
      INSERT INTO self_edit_evaluations (request_id, decision, reasoning, considered_context_json, modified_suggestion_json, analysis_findings_json, evaluated_at)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(
      evaluation.requestId,
      evaluation.decision,
      evaluation.reasoning,
      JSON.stringify(evaluation.consideredContext),
      evaluation.modifiedSuggestion ? JSON.stringify(evaluation.modifiedSuggestion) : null,
      evaluation.analysisFindings ? JSON.stringify(evaluation.analysisFindings) : null,
      evaluation.evaluatedAt,
    )
  }

  getEvaluations(requestId: string): EditEvaluation[] {
    const rows = this.db.prepare(
      'SELECT * FROM self_edit_evaluations WHERE request_id = ? ORDER BY evaluated_at DESC',
    ).all(requestId) as any[]

    return rows.map(this.rowToEvaluation)
  }



  recordAppliedEdit(edit: AppliedEdit): void {
    this.db.prepare(`
      INSERT INTO self_edit_applied (request_id, evaluation_id, files_modified, commit_sha, before_snapshot_json, applied_at, post_edit_observations_json, reverted_at, revert_reason, revert_commit_sha)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      edit.requestId,
      edit.evaluationId,
      JSON.stringify(edit.filesModified),
      edit.commitSha,
      JSON.stringify(edit.beforeSnapshot),
      edit.appliedAt,
      edit.postEditObservations ? JSON.stringify(edit.postEditObservations) : null,
      edit.revertedAt ?? null,
      edit.revertReason ?? null,
      edit.revertCommitSha ?? null,
    )
  }

  getFileEditHistory(filePath: string, limit = 10): AppliedEdit[] {
    const rows = this.db.prepare(`
      SELECT * FROM self_edit_applied
      WHERE files_modified LIKE ?
      ORDER BY applied_at DESC LIMIT ?
    `).all(`%${filePath}%`, limit) as any[]

    return rows.map(this.rowToAppliedEdit)
  }

  getRecentEdits(limit = 20): AppliedEdit[] {
    const rows = this.db.prepare(`
      SELECT * FROM self_edit_applied
      ORDER BY applied_at DESC LIMIT ?
    `).all(limit) as any[]

    return rows.map(this.rowToAppliedEdit)
  }



  getStats(): SelfEditStats {
    const frictionCount = (this.db.prepare(
      'SELECT COUNT(*) as cnt FROM self_edit_friction',
    ).get() as { cnt: number }).cnt

    const requestCounts = this.db.prepare(`
      SELECT status, COUNT(*) as cnt FROM self_edit_requests GROUP BY status
    `).all() as Array<{ status: string; cnt: number }>

    const statusMap = Object.fromEntries(requestCounts.map(r => [r.status, r.cnt]))

    const appliedCount = (this.db.prepare(
      'SELECT COUNT(*) as cnt FROM self_edit_applied WHERE reverted_at IS NULL',
    ).get() as { cnt: number }).cnt

    const revertedCount = (this.db.prepare(
      'SELECT COUNT(*) as cnt FROM self_edit_applied WHERE reverted_at IS NOT NULL',
    ).get() as { cnt: number }).cnt

    const topKinds = this.db.prepare(`
      SELECT kind, COUNT(*) as cnt FROM self_edit_friction
      GROUP BY kind ORDER BY cnt DESC LIMIT 10
    `).all() as Array<{ kind: string; cnt: number }>

    // Top target files from edit requests
    const requests = this.db.prepare(
      'SELECT suggestion_json FROM self_edit_requests',
    ).all() as Array<{ suggestion_json: string }>

    const fileCounts = new Map<string, number>()
    for (const r of requests) {
      try {
        const suggestion = JSON.parse(r.suggestion_json)
        for (const f of suggestion.targetFiles ?? []) {
          fileCounts.set(f, (fileCounts.get(f) ?? 0) + 1)
        }
      } catch { /* skip malformed */ }
    }

    const topFiles = [...fileCounts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([file, count]) => ({ file, count }))

    return {
      totalFrictionSignals: frictionCount,
      totalEditRequests: requestCounts.reduce((s, r) => s + r.cnt, 0),
      pendingRequests: statusMap['pending'] ?? 0,
      approvedEdits: statusMap['approved'] ?? 0,
      rejectedEdits: statusMap['rejected'] ?? 0,
      deferredEdits: statusMap['deferred'] ?? 0,
      appliedEdits: appliedCount,
      revertedEdits: revertedCount,
      topFrictionKinds: topKinds.map(r => ({ kind: r.kind as FrictionKind, count: r.cnt })),
      topTargetFiles: topFiles,
    }
  }



  private rowToFriction(row: any): FrictionSignal {
    return {
      kind: row.kind,
      whatHappened: row.what_happened,
      context: row.context,
      involvedPaths: JSON.parse(row.involved_paths),
      recurrence: row.recurrence,
      observedAt: row.observed_at,
      sessionId: row.session_id,
      posture: row.posture ?? undefined,
    }
  }

  private rowToRequest(row: any): EditRequest {
    return {
      id: row.id,
      sourceSessionId: row.source_session_id,
      sourceHelixId: row.source_helix_id ?? undefined,
      sourcePosture: row.source_posture ?? undefined,
      editKind: row.edit_kind,
      signals: JSON.parse(row.signals_json),
      suggestion: JSON.parse(row.suggestion_json),
      crossSessionRecurrence: row.cross_session_recurrence,
      createdAt: row.created_at,
      status: row.status,
      authority: row.authority ?? 'local',
      evaluatedBy: row.evaluated_by ?? undefined,
      evaluatedAt: row.evaluated_at ?? undefined,
      evaluationReason: row.evaluation_reason ?? undefined,
    }
  }

  private rowToEvaluation(row: any): EditEvaluation {
    return {
      requestId: row.request_id,
      decision: row.decision,
      reasoning: row.reasoning,
      consideredContext: JSON.parse(row.considered_context_json),
      modifiedSuggestion: row.modified_suggestion_json ? JSON.parse(row.modified_suggestion_json) : undefined,
      analysisFindings: row.analysis_findings_json ? JSON.parse(row.analysis_findings_json) : undefined,
      evaluatedAt: row.evaluated_at,
    }
  }

  private rowToAppliedEdit(row: any): AppliedEdit {
    return {
      requestId: row.request_id,
      evaluationId: row.evaluation_id,
      filesModified: JSON.parse(row.files_modified),
      commitSha: row.commit_sha,
      beforeSnapshot: JSON.parse(row.before_snapshot_json),
      appliedAt: row.applied_at,
      postEditObservations: row.post_edit_observations_json ? JSON.parse(row.post_edit_observations_json) : undefined,
      revertedAt: row.reverted_at ?? undefined,
      revertReason: row.revert_reason ?? undefined,
      revertCommitSha: row.revert_commit_sha ?? undefined,
    }
  }



  private getMetaValue(key: string): string | undefined {
    try {
      const row = this.db.prepare(
        'SELECT value FROM self_edit_meta WHERE key = ?',
      ).get(key) as { value: string } | undefined
      return row?.value
    } catch {
      return undefined
    }
  }

  private setMetaValue(key: string, value: string): void {
    this.db.prepare(
      'INSERT OR REPLACE INTO self_edit_meta (key, value) VALUES (?, ?)',
    ).run(key, value)
  }
}
