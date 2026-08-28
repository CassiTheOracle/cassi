/**
 * Claustrum Recorder — provenance log for the claustrum-vindex pipeline.
 *
 * Every time Aurora's LarqlKnowledgeProvider runs `vindexGateKnn`, the
 * returned (layer, feature_index, score) triples are written to a SQLite
 * table. The full record set, queried with a time window, drives the
 * `larql snapshot-claustrum` step that materialises a use-pruned vindex.
 *
 * The recorder records *raw source-vindex feature IDs* — the snapshotter
 * later turns them into claustrum-local IDs via a feature_index_map.
 *
 * Why this exists at the provider layer (not the claustrum layer):
 *   The claustrum integrates four sources (model, mnemic, portal, dream).
 *   Only the model side has structural feature IDs we can prune by. The
 *   recorder lives at the model-side provider where those IDs are visible.
 *
 * See: docs/design/claustrum-vindex.md
 */

import path from 'node:path'
import fs from 'node:fs'
import Database from 'better-sqlite3'

import type { ILogger } from '@cassicore/foundation'
import { getDataDir } from '@cassicore/foundation'
import type { OverlayPatch, OverlayPatchOp } from './overlay-layer.js'

export interface ClaustrumGateHit {
  readonly layer: number
  readonly featureIndex: number
  readonly score: number
  /** B2.3 — pre-bias score, present only when a RetrievalPolicy was applied. */
  readonly rawScore?: number
  /** B2.3 — clamped [-1, +1] dot product of feature signature vs policy target. */
  readonly affectCompat?: number
  /** B2.3 — bias mode applied: 'consonant' / 'complementary' / 'directed'. */
  readonly biasMode?: 'consonant' | 'complementary' | 'directed'
  /** B2.3 — strength used (post welfare-cap). */
  readonly biasStrength?: number
}

/**
 * B2.3 retrieval-stats output: per-quadrant breakdown of which
 * feature-layer pairs were retrieved under which bias mode.
 */
export interface RetrievalStatsRow {
  readonly biasMode: string | null
  readonly hitCount: number
  readonly distinctFeatures: number
  readonly meanScore: number
  readonly meanAffectCompat: number | null
}

export interface ClaustrumRecordOptions {
  readonly cycleId: string | null
  readonly queryConcept: string
  readonly trigger: string
  readonly hits: ReadonlyArray<ClaustrumGateHit>
}

export interface ClaustrumWindow {
  readonly startTs?: string
  readonly endTs?: string
  readonly sourcePath?: string
}

export interface RetainedFeature {
  readonly layer: number
  readonly featureIndex: number
  readonly hitCount: number
  readonly maxScore: number
  readonly firstSeen: string
  readonly lastSeen: string
}

/**
 * Compact per-layer summary used by the snapshot builder to size output
 * buffers in a single round-trip to the recorder DB.
 */
export interface LayerFeatureSummary {
  readonly layer: number
  /** Number of distinct feature_index values retained in the window. */
  readonly distinctFeatures: number
  /** Total provenance row count for the layer (>= distinctFeatures). */
  readonly totalHits: number
}


export interface PatchAuditEntry {
  readonly id: string
  readonly patchId: string
  readonly op: OverlayPatchOp
  readonly layer: number
  readonly tokenId: number
  readonly label: string | null
  readonly author: string
  readonly reason: string
  readonly createdAt: string
  readonly conversationId: string | null
  readonly cycleId: string | null
  readonly status: 'applied' | 'rolled_back' | 'baked_down'
  readonly statusChangedAt: string
}

export interface PatchAuditQuery {
  readonly author?: string
  readonly layer?: number
  readonly op?: OverlayPatchOp
  readonly status?: PatchAuditEntry['status']
  readonly since?: string
  readonly until?: string
  readonly limit?: number
}

export interface PatchAuditSummary {
  readonly totalPatches: number
  readonly byStatus: Record<string, number>
  readonly byOp: Record<string, number>
  readonly byAuthor: Record<string, number>
}

export class ClaustrumRecorder {
  private readonly logger: ILogger
  private readonly db: Database.Database
  private readonly insertStmt: Database.Statement
  private readonly sourcePath: string
  private readonly ownsDb: boolean
  private closed = false

  constructor(
    logger: ILogger,
    sourcePath: string,
    dbOrPath?: Database.Database | string,
  ) {
    this.logger = logger.child ? logger.child('claustrum-recorder') : logger
    this.sourcePath = sourcePath

    if (typeof dbOrPath === 'string' || dbOrPath === undefined) {
      const dbPath = dbOrPath ?? path.join(getDataDir(), 'system-state.db')
      const dir = path.dirname(dbPath)
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
      this.db = new Database(dbPath)
      this.db.pragma('journal_mode = WAL')
      this.db.pragma('busy_timeout = 5000')
      this.db.pragma('synchronous = NORMAL')
      this.ownsDb = true
    } else {
      this.db = dbOrPath
      this.ownsDb = false
    }

    this.ensureSchema()
    this.insertStmt = this.db.prepare(
      `INSERT INTO claustrum_recorder
        (ts, source_path, cycle_id, query_concept, trigger, layer, feature_index, score,
         raw_score, affect_compat, bias_mode, bias_strength)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    )
  }

  private ensureSchema(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS claustrum_recorder (
        ts TEXT NOT NULL,
        source_path TEXT NOT NULL,
        cycle_id TEXT,
        query_concept TEXT NOT NULL,
        trigger TEXT NOT NULL,
        layer INTEGER NOT NULL,
        feature_index INTEGER NOT NULL,
        score REAL NOT NULL
      );

      CREATE INDEX IF NOT EXISTS idx_claustrum_layer_feat
        ON claustrum_recorder(layer, feature_index);
      CREATE INDEX IF NOT EXISTS idx_claustrum_ts
        ON claustrum_recorder(ts);
      CREATE INDEX IF NOT EXISTS idx_claustrum_concept
        ON claustrum_recorder(query_concept);
      CREATE INDEX IF NOT EXISTS idx_claustrum_source
        ON claustrum_recorder(source_path);

      CREATE TABLE IF NOT EXISTS overlay_patch_audit (
        id TEXT PRIMARY KEY,
        patch_id TEXT NOT NULL,
        op TEXT NOT NULL,
        layer INTEGER NOT NULL,
        token_id INTEGER NOT NULL,
        label TEXT,
        author TEXT NOT NULL,
        reason TEXT NOT NULL,
        created_at TEXT NOT NULL,
        conversation_id TEXT,
        cycle_id TEXT,
        status TEXT NOT NULL DEFAULT 'applied',
        status_changed_at TEXT NOT NULL
      );

      CREATE INDEX IF NOT EXISTS idx_overlay_audit_patch
        ON overlay_patch_audit(patch_id);
      CREATE INDEX IF NOT EXISTS idx_overlay_audit_status
        ON overlay_patch_audit(status);
      CREATE INDEX IF NOT EXISTS idx_overlay_audit_ts
        ON overlay_patch_audit(created_at);
      CREATE INDEX IF NOT EXISTS idx_overlay_audit_author
        ON overlay_patch_audit(author);
    `)

    // B2.3 — affect-context columns. ALTER TABLE is idempotent-safe via
    // try/catch on duplicate-column errors so re-running after a partial
    // migration is harmless.
    for (const column of [
      'raw_score REAL',
      'affect_compat REAL',
      'bias_mode TEXT',
      'bias_strength REAL',
    ]) {
      try {
        this.db.exec(`ALTER TABLE claustrum_recorder ADD COLUMN ${column}`)
      } catch (err: any) {
        if (!String(err?.message ?? '').includes('duplicate column')) throw err
      }
    }
  }

  /**
   * Record a batch of gate-KNN hits in a single transaction. Safe to call
   * with an empty hit list — it's a no-op.
   */
  recordGateHits(opts: ClaustrumRecordOptions): void {
    if (this.closed) return
    if (opts.hits.length === 0) return

    const ts = new Date().toISOString()
    const tx = this.db.transaction((hits: ReadonlyArray<ClaustrumGateHit>) => {
      for (const hit of hits) {
        this.insertStmt.run(
          ts,
          this.sourcePath,
          opts.cycleId,
          opts.queryConcept,
          opts.trigger,
          hit.layer,
          hit.featureIndex,
          hit.score,
          hit.rawScore ?? null,
          hit.affectCompat ?? null,
          hit.biasMode ?? null,
          hit.biasStrength ?? null,
        )
      }
    })

    try {
      tx(opts.hits)
    } catch (err) {
      this.logger.warn?.('Failed to record claustrum gate hits', {
        error: String(err),
        layer: opts.hits[0]?.layer,
        count: opts.hits.length,
      })
    }
  }

  /**
   * B2.3 retrieval stats — per-bias-mode breakdown of recorded gate hits
   * within an optional time window. The `null` row covers hits recorded
   * without affect bias (legacy or policy-disabled retrievals); other
   * rows correspond to the bias mode that was active.
   *
   * Returns rows sorted by hit count descending so callers can render
   * "what bias dominates this window" without further sorting.
   */
  retrievalStats(window: { startTs?: string; endTs?: string } = {}): RetrievalStatsRow[] {
    if (this.closed) return []
    const conditions: string[] = []
    const params: unknown[] = []
    if (window.startTs) { conditions.push('ts >= ?'); params.push(window.startTs) }
    if (window.endTs)   { conditions.push('ts <= ?'); params.push(window.endTs) }
    const where = conditions.length === 0 ? '' : `WHERE ${conditions.join(' AND ')}`
    const sql = `
      SELECT
        bias_mode AS biasMode,
        COUNT(*) AS hitCount,
        COUNT(DISTINCT (layer || ':' || feature_index)) AS distinctFeatures,
        AVG(score) AS meanScore,
        AVG(affect_compat) AS meanAffectCompat
      FROM claustrum_recorder
      ${where}
      GROUP BY bias_mode
      ORDER BY hitCount DESC
    `
    const rows = this.db.prepare(sql).all(...params) as Array<{
      biasMode: string | null
      hitCount: number
      distinctFeatures: number
      meanScore: number
      meanAffectCompat: number | null
    }>
    return rows.map(r => ({
      biasMode: r.biasMode,
      hitCount: r.hitCount,
      distinctFeatures: r.distinctFeatures,
      meanScore: r.meanScore,
      meanAffectCompat: r.meanAffectCompat,
    }))
  }

  /**
   * Return all retained (layer, feature_index) pairs in the window, with
   * aggregate stats useful for downstream pruning.
   *
   * Used by the future `larql snapshot-claustrum` builder.
   */
  retainedFeatures(window: ClaustrumWindow = {}): RetainedFeature[] {
    if (this.closed) return []

    const conditions: string[] = []
    const params: Record<string, string> = {}
    if (window.startTs) { conditions.push('ts >= @startTs'); params.startTs = window.startTs }
    if (window.endTs) { conditions.push('ts <= @endTs'); params.endTs = window.endTs }
    const sourcePath = window.sourcePath ?? this.sourcePath
    conditions.push('source_path = @sourcePath')
    params.sourcePath = sourcePath

    const where = `WHERE ${conditions.join(' AND ')}`
    const sql = `
      SELECT
        layer,
        feature_index AS featureIndex,
        COUNT(*) AS hitCount,
        MAX(score) AS maxScore,
        MIN(ts) AS firstSeen,
        MAX(ts) AS lastSeen
      FROM claustrum_recorder
      ${where}
      GROUP BY layer, feature_index
      ORDER BY layer ASC, feature_index ASC
    `
    return this.db.prepare(sql).all(params) as RetainedFeature[]
  }

  /**
   * Total number of provenance records in the window. Cheap to call —
   * used for status reporting and as a snapshot-readiness gate.
   */
  recordCount(window: ClaustrumWindow = {}): number {
    if (this.closed) return 0
    const conditions: string[] = []
    const params: Record<string, string> = {}
    if (window.startTs) { conditions.push('ts >= @startTs'); params.startTs = window.startTs }
    if (window.endTs) { conditions.push('ts <= @endTs'); params.endTs = window.endTs }
    const sourcePath = window.sourcePath ?? this.sourcePath
    conditions.push('source_path = @sourcePath')
    params.sourcePath = sourcePath
    const where = conditions.length ? `WHERE ${conditions.join(' AND ')}` : ''
    const row = this.db.prepare(
      `SELECT COUNT(*) AS n FROM claustrum_recorder ${where}`,
    ).get(params) as { n: number } | undefined
    return row?.n ?? 0
  }

  /**
   * Per-layer summary in the window — distinct feature count plus total hit
   * count. Used by the snapshot builder to size per-layer output buffers
   * (`gate_L<N>.bin`, `down_meta_L<N>.bin`, `feature_index_map_L<N>.bin`)
   * in a single query, before streaming the actual features.
   *
   * See: docs/design/claustrum-vindex.md §7 (Build Process)
   */
  distinctFeaturesByLayer(window: ClaustrumWindow = {}): LayerFeatureSummary[] {
    if (this.closed) return []
    const conditions: string[] = []
    const params: Record<string, string> = {}
    if (window.startTs) { conditions.push('ts >= @startTs'); params.startTs = window.startTs }
    if (window.endTs) { conditions.push('ts <= @endTs'); params.endTs = window.endTs }
    const sourcePath = window.sourcePath ?? this.sourcePath
    conditions.push('source_path = @sourcePath')
    params.sourcePath = sourcePath
    const where = `WHERE ${conditions.join(' AND ')}`
    const sql = `
      SELECT
        layer,
        COUNT(DISTINCT feature_index) AS distinctFeatures,
        COUNT(*) AS totalHits
      FROM claustrum_recorder
      ${where}
      GROUP BY layer
      ORDER BY layer ASC
    `
    return this.db.prepare(sql).all(params) as LayerFeatureSummary[]
  }


  private _insertAuditStmt: Database.Statement | null = null
  private _updateAuditStatusStmt: Database.Statement | null = null

  private get insertAuditStmt(): Database.Statement {
    if (!this._insertAuditStmt) {
      this._insertAuditStmt = this.db.prepare(
        `INSERT INTO overlay_patch_audit
          (id, patch_id, op, layer, token_id, label, author, reason,
           created_at, conversation_id, cycle_id, status, status_changed_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      )
    }
    return this._insertAuditStmt
  }

  private get updateAuditStatusStmt(): Database.Statement {
    if (!this._updateAuditStatusStmt) {
      this._updateAuditStatusStmt = this.db.prepare(
        `UPDATE overlay_patch_audit SET status = ?, status_changed_at = ? WHERE id = ?`,
      )
    }
    return this._updateAuditStatusStmt
  }

  /**
   * Record an overlay patch in the audit trail. Each patch gets one row
   * with full provenance for attribution queries.
   */
  recordPatchAudit(
    patch: OverlayPatch,
    author: string,
    reason: string,
    meta?: { conversationId?: string; cycleId?: string },
  ): void {
    if (this.closed) return
    const now = new Date().toISOString()
    const id = `${patch.id}:${patch.layer}:${patch.tokenId}`
    this.insertAuditStmt.run(
      id,
      patch.id,
      patch.op,
      patch.layer,
      patch.tokenId,
      patch.label ?? null,
      author,
      reason,
      now,
      meta?.conversationId ?? null,
      meta?.cycleId ?? null,
      'applied',
      now,
    )
    this.logger.debug('Recorded patch audit', { patchId: patch.id, op: patch.op, author })
  }

  /**
   * Mark all audit entries for a patch as rolled_back.
   */
  markPatchRolledBack(patchId: string): number {
    if (this.closed) return 0
    const now = new Date().toISOString()
    const result = this.db.prepare(
      `UPDATE overlay_patch_audit SET status = 'rolled_back', status_changed_at = ?
       WHERE patch_id = ? AND status = 'applied'`,
    ).run(now, patchId)
    this.logger.debug('Marked patch rolled back', { patchId, count: result.changes })
    return result.changes
  }

  /**
   * Mark all audit entries for a patch as baked_down (materialized into base vindex).
   */
  markPatchBakedDown(patchId: string): number {
    if (this.closed) return 0
    const now = new Date().toISOString()
    const result = this.db.prepare(
      `UPDATE overlay_patch_audit SET status = 'baked_down', status_changed_at = ?
       WHERE patch_id = ? AND status = 'applied'`,
    ).run(now, patchId)
    this.logger.debug('Marked patch baked down', { patchId, count: result.changes })
    return result.changes
  }

  /**
   * Query audit entries with filters. Returns entries ordered by created_at desc.
   */
  queryAuditTrail(query: PatchAuditQuery = {}): PatchAuditEntry[] {
    if (this.closed) return []
    const conditions: string[] = []
    const params: Record<string, string | number> = {}
    if (query.author) { conditions.push('author = @author'); params.author = query.author }
    if (query.layer !== undefined) { conditions.push('layer = @layer'); params.layer = query.layer }
    if (query.op) { conditions.push('op = @op'); params.op = query.op }
    if (query.status) { conditions.push('status = @status'); params.status = query.status }
    if (query.since) { conditions.push('created_at >= @since'); params.since = query.since }
    if (query.until) { conditions.push('created_at <= @until'); params.until = query.until }
    const where = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : ''
    const limit = query.limit ?? 100
    const sql = `SELECT * FROM overlay_patch_audit ${where} ORDER BY created_at DESC LIMIT ${limit}`
    return this.db.prepare(sql).all(params) as PatchAuditEntry[]
  }

  /**
   * Get the full audit trail for a specific patch, ordered by layer/token.
   */
  getPatchHistory(patchId: string): PatchAuditEntry[] {
    if (this.closed) return []
    return this.db.prepare(
      `SELECT * FROM overlay_patch_audit WHERE patch_id = ? ORDER BY layer ASC, token_id ASC`,
    ).all(patchId) as PatchAuditEntry[]
  }

  /**
   * Summary statistics for the audit trail, optionally filtered.
   */
  auditSummary(query: PatchAuditQuery = {}): PatchAuditSummary {
    if (this.closed) {
      return { totalPatches: 0, byStatus: {}, byOp: {}, byAuthor: {} }
    }
    const conditions: string[] = []
    const params: Record<string, string | number> = {}
    if (query.author) { conditions.push('author = @author'); params.author = query.author }
    if (query.since) { conditions.push('created_at >= @since'); params.since = query.since }
    if (query.until) { conditions.push('created_at <= @until'); params.until = query.until }
    const where = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : ''

    const total = this.db.prepare(`SELECT COUNT(*) as c FROM overlay_patch_audit ${where}`).get(params) as { c: number }

    const byStatus = this.db.prepare(
      `SELECT status, COUNT(*) as c FROM overlay_patch_audit ${where} GROUP BY status`,
    ).all(params) as Array<{ status: string; c: number }>

    const byOp = this.db.prepare(
      `SELECT op, COUNT(*) as c FROM overlay_patch_audit ${where} GROUP BY op`,
    ).all(params) as Array<{ op: string; c: number }>

    const byAuthor = this.db.prepare(
      `SELECT author, COUNT(*) as c FROM overlay_patch_audit ${where} GROUP BY author`,
    ).all(params) as Array<{ author: string; c: number }>

    return {
      totalPatches: total.c,
      byStatus: Object.fromEntries(byStatus.map(r => [r.status, r.c])),
      byOp: Object.fromEntries(byOp.map(r => [r.op, r.c])),
      byAuthor: Object.fromEntries(byAuthor.map(r => [r.author, r.c])),
    }
  }

  close(): void {
    if (this.closed) return
    this.closed = true
    if (this.ownsDb) this.db.close()
  }
}
