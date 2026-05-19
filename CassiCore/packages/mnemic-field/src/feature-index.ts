/**
 * FeatureIndex — bidirectional map from vindex features → engrams.
 *
 * When an engram is stored, its content is run through gate KNN to find
 * the model features it activates. Those feature keys (e.g. "L16:F4521")
 * are stored in the `feature_index` SQLite table. At retrieval time, the
 * query's gate KNN result directly points to engrams that activated the
 * same features — no ANN cosine scan needed for exact feature matches.
 *
 * This is the key that makes the vindex a substrate, not a bridge:
 * the model's internal activation pattern IS the retrieval index.
 *
 * SQLite-backed as of May 2026 — scales to 228K+ engrams without the
 * ~700MB memory pressure of in-memory Maps.
 */
import type Database from 'better-sqlite3'
import type { ILogger } from '../../../types/interfaces.js'
import type { Cortex } from './cortex.js'

/** Feature key format: "L{layer}:F{featureIndex}" */
function featureKey(layer: number, featureIndex: number): string {
  return `L${layer}:F${featureIndex}`
}

/** A vindex gate-KNN call: (text) => Array<{layer, featureIndex, score}> */
export type VindexGateKnnFn = (
  text: string,
  options?: { layers?: number[]; featuresPerLayer?: number; minScore?: number },
) => Array<{ layer: number; featureIndex: number; score: number }>

export interface FeatureIndexEntry {
  engramId: string
  /** Number of shared features — used for ordering direct-match hits. */
  sharedFeatureCount: number
}

export class FeatureIndex {
  private db: Database.Database
  private logger: ILogger
  private gateKnn: VindexGateKnnFn | null = null
  private ready = false

  /** Small read-cache for engram→features (used by removeEngram + findCorrelated). */
  private engramFeatureCache = new Map<string, string[]>()

  // Prepared statements
  private stmtInsert: Database.Statement | null = null
  private stmtDeleteEngram: Database.Statement | null = null
  private stmtCountByEngram: Database.Statement | null = null
  private stmtFeatureKeys: Database.Statement | null = null

  constructor(db: Database.Database, logger: ILogger) {
    this.db = db
    this.logger = logger.child ? logger.child('feature-index') : logger
  }

  /**
   * Prepare statements on first use (deferred — DB may not be fully migrated
   * when FeatureIndex is constructed).
   */
  private ensureStatements(): void {
    if (this.stmtInsert) return
    this.stmtInsert = this.db.prepare(
      `INSERT OR IGNORE INTO feature_index (feature_key, engram_id) VALUES (?, ?)`
    )
    this.stmtDeleteEngram = this.db.prepare(
      `DELETE FROM feature_index WHERE engram_id = ?`
    )
    this.stmtCountByEngram = this.db.prepare(
      `SELECT COUNT(*) as cnt FROM feature_index WHERE engram_id = ?`
    )
    this.stmtFeatureKeys = this.db.prepare(
      `SELECT feature_key FROM feature_index WHERE engram_id = ?`
    )
  }

  /** Wire the gate-KNN function. Required before index(). */
  setGateKnn(fn: VindexGateKnnFn | null): void {
    this.gateKnn = fn
    this.ready = !!fn
    this.logger.info('FeatureIndex gateKnn set', { ready: this.ready })
  }

  /** Whether the index is ready for queries. */
  isReady(): boolean {
    return this.ready
  }

  /**
   * Index an engram from its content. Gate-KNNs the content and inserts
   * feature→engramId mappings into the SQLite table.
   *
   * Call during storeForSession when vindex is available. Re-indexing
   * the same engramId with different content cleans up old mappings first.
   */
  indexEngram(
    engramId: string,
    content: string,
    options?: {
      layers?: number[]
      featuresPerLayer?: number
      minScore?: number
    },
  ): void {
    if (!this.ready || !this.gateKnn) return
    if (!content || content.length < 20) return

    // Clean up old feature mappings before re-indexing.
    this.removeEngram(engramId)

    try {
      const features = this.gateKnn(content, {
        layers: options?.layers,
        featuresPerLayer: options?.featuresPerLayer ?? 10,
        minScore: options?.minScore ?? 0.05,
      })

      if (features.length === 0) return

      const keys = features.map(f => featureKey(f.layer, f.featureIndex))

      // Batch insert within a transaction.
      this.ensureStatements()
      const tx = this.db.transaction(() => {
        for (const key of keys) {
          this.stmtInsert!.run(key, engramId)
        }
      })
      tx()

      // Update cache.
      this.engramFeatureCache.set(engramId, keys)
    } catch (err) {
      this.logger.debug?.('FeatureIndex.indexEngram failed', {
        engramId: engramId.slice(0, 12),
        error: String(err),
      })
    }
  }

  /**
   * Remove an engram from the index. Called when engram content changes
   * or the engram is deleted.
   */
  removeEngram(engramId: string): void {
    // Fetch keys from cache or DB before deleting.
    let keys = this.engramFeatureCache.get(engramId)
    if (!keys) {
      this.ensureStatements()
      const rows = this.stmtFeatureKeys!.all(engramId) as Array<{ feature_key: string }>
      keys = rows.map(r => r.feature_key)
    }

    this.ensureStatements()
    this.stmtDeleteEngram!.run(engramId)
    this.engramFeatureCache.delete(engramId)
  }

  /**
   * Find engrams that share features with the given text.
   * Runs gateKnn on the text, looks up matching engrams via SQL.
   *
   * Returns engrams ranked by number of shared features (descending).
   * This is the direct feature-indexed retrieval path — the model's
   * gate KNN activation pattern IS the query. No cosine scan needed.
   */
  lookup(
    text: string,
    options?: {
      layers?: number[]
      featuresPerLayer?: number
      minScore?: number
      limit?: number
    },
  ): FeatureIndexEntry[] {
    if (!this.ready || !this.gateKnn) return []
    if (!text) return []

    try {
      const features = this.gateKnn(text, {
        layers: options?.layers,
        featuresPerLayer: options?.featuresPerLayer ?? 10,
        minScore: options?.minScore ?? 0.05,
      })

      if (features.length === 0) return []

      const keys = features.map(f => featureKey(f.layer, f.featureIndex))
      const limit = options?.limit ?? 20

      // Build IN clause with parameterized query.
      // Join against engrams to exclude structural types at query time.
      const placeholders = keys.map(() => '?').join(',')
      const sql = `
        SELECT fi.engram_id, COUNT(*) as cnt
        FROM feature_index fi
        JOIN engrams e ON e.id = fi.engram_id
        WHERE fi.feature_key IN (${placeholders})
          AND e.node_type NOT IN ('message','tool_invocation','tool','thought_command',
                                  'replay_segment','expert_summary','bridge','session',
                                  'file','file_version','file_read','source_file','changeset')
        GROUP BY fi.engram_id
        ORDER BY cnt DESC
        LIMIT ?
      `
      const rows = this.db.prepare(sql).all(...keys, limit) as Array<{
        engram_id: string
        cnt: number
      }>

      return rows.map(r => ({
        engramId: r.engram_id,
        sharedFeatureCount: r.cnt,
      }))
    } catch (err) {
      this.logger.debug?.('FeatureIndex.lookup failed', { error: String(err) })
      return []
    }
  }

  /**
   * Build the index from existing engrams in the Cortex.
   * Iterates engrams with content, runs gate KNN, populates the table.
   *
   * Best-effort and throttled — yields to event loop every 50 engrams.
   * For bulk backfill of 228K engrams, use the separate backfill script
   * (core/intelligence/mnemic-field/feature-backfill.ts) which loads the
   * vindex via the native addon directly for 20× faster indexing.
   *
   * Returns the number of engrams indexed.
   */
  async buildFromCortex(
    cortex: Cortex,
    options?: {
      limit?: number
      layers?: number[]
      featuresPerLayer?: number
      minScore?: number
    },
  ): Promise<number> {
    if (!this.ready || !this.gateKnn) return 0

    const limit = options?.limit ?? 10000
    const engrams = cortex.listEngrams(limit).filter(
      e => e.content && e.content.length > 20 && e.content.length < 50000,
    )

    let indexed = 0
    for (let i = 0; i < engrams.length; i++) {
      const e = engrams[i]
      this.indexEngram(e.id, e.content, options)
      indexed++

      // Yield to event loop every 50 engrams
      if (indexed % 50 === 0) {
        await new Promise(resolve => setImmediate(resolve))
      }
    }

    const stats = this.stats()
    this.logger.info('FeatureIndex built from cortex', {
      scanned: engrams.length,
      indexed,
      featureKeys: stats.featureKeys,
    })

    return indexed
  }

  /** Statistics about the index. */
  stats(): { engrams: number; featureKeys: number; ready: boolean } {
    try {
      const row = this.db.prepare(`
        SELECT 
          COUNT(DISTINCT engram_id) as engrams,
          COUNT(DISTINCT feature_key) as feature_keys
        FROM feature_index
      `).get() as { engrams: number; feature_keys: number } | undefined
      return {
        engrams: row?.engrams ?? 0,
        featureKeys: row?.feature_keys ?? 0,
        ready: this.ready,
      }
    } catch {
      return { engrams: 0, featureKeys: 0, ready: this.ready }
    }
  }

  /**
   * Find engrams that share vindex features with the given engram.
   *
   * Uses a self-join on feature_index to find engrams whose gate
   * activation patterns overlap. Returns engrams ranked by number of
   * shared features (descending). Excludes self.
   *
   * These correlations become `vindex_correlation` synapses — the bridge
   * between continuous ANN space and discrete model-feature space.
   */
  findCorrelated(
    engramId: string,
    options?: { minOverlap?: number; limit?: number },
  ): Array<{ engramId: string; sharedFeatureCount: number }> {
    const minOverlap = options?.minOverlap ?? 2
    const limit = options?.limit ?? 20

    try {
      const rows = this.db.prepare(`
        SELECT fi2.engram_id, COUNT(*) as cnt
        FROM feature_index fi1
        JOIN feature_index fi2 ON fi1.feature_key = fi2.feature_key
        WHERE fi1.engram_id = ?
          AND fi2.engram_id != ?
        GROUP BY fi2.engram_id
        HAVING cnt >= ?
        ORDER BY cnt DESC
        LIMIT ?
      `).all(engramId, engramId, minOverlap, limit) as Array<{
        engram_id: string
        cnt: number
      }>

      return rows.map(r => ({
        engramId: r.engram_id,
        sharedFeatureCount: r.cnt,
      }))
    } catch (err) {
      this.logger.debug?.('FeatureIndex.findCorrelated failed', { error: String(err) })
      return []
    }
  }
}
