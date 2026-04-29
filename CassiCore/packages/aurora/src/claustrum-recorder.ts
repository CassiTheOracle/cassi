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

import type { ILogger } from '../../../types/interfaces.js'
import { getDataDir } from '../../utils/paths.js'

export interface ClaustrumGateHit {
  readonly layer: number
  readonly featureIndex: number
  readonly score: number
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
      const dbPath = dbOrPath ?? path.join(getDataDir(), 'aurora-claustrum.db')
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
        (ts, source_path, cycle_id, query_concept, trigger, layer, feature_index, score)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
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
    `)
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

  close(): void {
    if (this.closed) return
    this.closed = true
    if (this.ownsDb) this.db.close()
  }
}
