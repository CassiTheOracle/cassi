/**
 * SqliteVectorIndex — persistent vector storage backed by SQLite.
 *
 * Stores pre-computed embeddings for archived content so that retrieval
 * pipelines can skip on-demand embedding calls when a cached vector exists.
 * Uses brute-force cosine similarity for queries (fine up to ~100k vectors).
 *
 * Singleton: import { getVectorIndex } from './sqlite-index.js'
 */
import fs from 'fs'
import path from 'path'

import Database from 'better-sqlite3'

import type { ILogger } from '../../../types/interfaces.js'

export interface VectorHit {
  id: string
  score: number
  meta?: any
}

export interface VectorIndexStats {
  totalVectors: number
  oldestTs: number | null
  newestTs: number | null
}

export class SqliteVectorIndex {
  private db?: Database.Database
  private logger: ILogger
  private table = 'vector_index'

  // Prepared statements (cached for performance)
  private stmtInsert?: Database.Statement
  private stmtDelete?: Database.Statement
  private stmtHas?: Database.Statement
  private stmtGet?: Database.Statement
  private stmtCount?: Database.Statement
  private stmtListAll?: Database.Statement
  private stmtSelectAll?: Database.Statement
  private stmtStats?: Database.Statement
  private stmtPurgeBefore?: Database.Statement

  constructor(logger: ILogger, opts?: { dbPath?: string }) {
    this.logger = logger.child?.('vector-index') ?? logger
    const homedir = process.env.HOME || require('os').homedir()
    const dbPath = opts?.dbPath ?? path.join(homedir!, '.cassicore', 'data', 'vectors.db')

    try {
      const dir = path.dirname(dbPath)
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
      this.db = new Database(dbPath)
      this.db.pragma('busy_timeout = 5000')
      this.db.exec(`
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS ${this.table} (
          id TEXT PRIMARY KEY,
          vec TEXT NOT NULL,
          meta TEXT,
          ts INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_vector_ts ON ${this.table}(ts);
      `)
      this.prepareStatements()
      this.logger.info('SqliteVectorIndex: initialized', { dbPath })
    } catch (err) {
      this.logger.warn('SqliteVectorIndex: failed to initialize', { error: String(err) })
      this.db = undefined
    }
  }

  /** Whether the index is operational. */
  get available(): boolean {
    return !!this.db
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // WRITE OPERATIONS
  // ═══════════════════════════════════════════════════════════════════════════

  /** Insert or replace a single vector. */
  addVector(id: string, vector: number[], meta?: any): void {
    if (!this.db) return
    try {
      this.stmtInsert!.run(id, JSON.stringify(vector), meta ? JSON.stringify(meta) : null, Date.now())
    } catch (err) {
      this.logger.warn('SqliteVectorIndex: failed to add vector', { id, error: String(err) })
    }
  }

  /**
   * Insert multiple vectors in a single transaction (10-50× faster than individual inserts).
   * Skips entries that fail individually without aborting the batch.
   */
  addVectorBatch(entries: Array<{ id: string; vector: number[]; meta?: any }>): number {
    if (!this.db || entries.length === 0) return 0
    let inserted = 0
    const now = Date.now()
    try {
      const txn = this.db.transaction(() => {
        for (const { id, vector, meta } of entries) {
          try {
            this.stmtInsert!.run(id, JSON.stringify(vector), meta ? JSON.stringify(meta) : null, now)
            inserted++
          } catch (err) {
            this.logger.debug('SqliteVectorIndex: batch insert skip', { id, error: String(err) })
          }
        }
      })
      txn()
    } catch (err) {
      this.logger.warn('SqliteVectorIndex: batch insert failed', { error: String(err) })
    }
    return inserted
  }

  /** Remove a vector by ID. */
  removeVector(id: string): void {
    if (!this.db) return
    try {
      this.stmtDelete!.run(id)
    } catch (err) {
      this.logger.warn('SqliteVectorIndex: failed to remove vector', { id, error: String(err) })
    }
  }

  /** Purge vectors older than a given timestamp. Returns number removed. */
  purgeOlderThan(timestampMs: number): number {
    if (!this.db) return 0
    try {
      const result = this.stmtPurgeBefore!.run(timestampMs)
      return result.changes
    } catch (err) {
      this.logger.warn('SqliteVectorIndex: purge failed', { error: String(err) })
      return 0
    }
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // READ OPERATIONS
  // ═══════════════════════════════════════════════════════════════════════════

  /** Check whether a vector with the given ID exists. O(1). */
  hasVector(id: string): boolean {
    if (!this.db) return false
    try {
      const row = this.stmtHas!.get(id) as any
      return !!row
    } catch (err) {
      return false
    }
  }

  /** Retrieve a single vector by ID. Returns null if not found. */
  getVector(id: string): number[] | null {
    if (!this.db) return null
    try {
      const row = this.stmtGet!.get(id) as any
      if (!row) return null
      return JSON.parse(row.vec) as number[]
    } catch (err) {
      this.logger.debug('SqliteVectorIndex: getVector failed', { id, error: String(err) })
      return null
    }
  }

  /**
   * Retrieve vectors for multiple IDs. Returns a Map of id → vector.
   * Missing IDs are omitted from the result (no null entries).
   */
  getVectorBatch(ids: string[]): Map<string, number[]> {
    const result = new Map<string, number[]>()
    if (!this.db || ids.length === 0) return result
    try {
      // Use parameterized IN clause for safety and efficiency
      const placeholders = ids.map(() => '?').join(',')
      const rows = this.db.prepare(
        `SELECT id, vec FROM ${this.table} WHERE id IN (${placeholders})`
      ).all(...ids) as any[]
      for (const row of rows) {
        try {
          result.set(row.id, JSON.parse(row.vec) as number[])
        } catch { /* skip malformed */ }
      }
    } catch (err) {
      this.logger.debug('SqliteVectorIndex: getVectorBatch failed', { error: String(err) })
    }
    return result
  }

  /** Brute-force cosine similarity query. Returns topK results. */
  query(vector: number[], topK = 10): VectorHit[] {
    if (!this.db) return []
    try {
      const rows = this.stmtSelectAll!.all() as any[]
      const out: VectorHit[] = []
      for (const r of rows) {
        try {
          const vec = JSON.parse(r.vec) as number[]
          const score = this.cosineSimilarity(vector, vec)
          out.push({ id: r.id, score, meta: r.meta ? JSON.parse(r.meta) : undefined })
        } catch { /* skip malformed */ }
      }
      return out.sort((a, b) => b.score - a.score).slice(0, topK)
    } catch (err) {
      this.logger.warn('SqliteVectorIndex: query failed', { error: String(err) })
      return []
    }
  }

  /** List all stored IDs and metadata (without loading vectors). */
  listAll(): Array<{ id: string; meta?: any }> {
    if (!this.db) return []
    try {
      const rows = this.stmtListAll!.all() as any[]
      return rows.map(r => ({ id: r.id, meta: r.meta ? JSON.parse(r.meta) : undefined }))
    } catch (err) {
      this.logger.warn('SqliteVectorIndex: listAll failed', { error: String(err) })
      return []
    }
  }

  /** Get the total number of stored vectors. O(1). */
  count(): number {
    if (!this.db) return 0
    try {
      const row = this.stmtCount!.get() as any
      return row?.cnt ?? 0
    } catch (err) {
      return 0
    }
  }

  /** Get index statistics. */
  stats(): VectorIndexStats {
    if (!this.db) return { totalVectors: 0, oldestTs: null, newestTs: null }
    try {
      const row = this.stmtStats!.get() as any
      return {
        totalVectors: row?.cnt ?? 0,
        oldestTs: row?.oldest ?? null,
        newestTs: row?.newest ?? null,
      }
    } catch (err) {
      this.logger.debug('SqliteVectorIndex: stats failed', { error: String(err) })
      return { totalVectors: 0, oldestTs: null, newestTs: null }
    }
  }

  close(): void {
    try { this.db?.close() } catch (err) {
      this.logger.debug('SqliteVectorIndex: close failed', { error: String(err) })
    }
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // INTERNAL
  // ═══════════════════════════════════════════════════════════════════════════

  /** Cosine similarity between two vectors. Public for use by callers. */
  cosineSimilarity(a: number[] | null, b: number[] | null): number {
    if (!a || !b || a.length !== b.length) return 0
    let dot = 0, ma = 0, mb = 0
    for (let i = 0; i < a.length; i++) {
      dot += (a[i] || 0) * (b[i] || 0)
      ma += (a[i] || 0) * (a[i] || 0)
      mb += (b[i] || 0) * (b[i] || 0)
    }
    if (ma === 0 || mb === 0) return 0
    return dot / (Math.sqrt(ma) * Math.sqrt(mb))
  }

  private prepareStatements(): void {
    if (!this.db) return
    this.stmtInsert = this.db.prepare(
      `INSERT OR REPLACE INTO ${this.table} (id, vec, meta, ts) VALUES (?, ?, ?, ?)`
    )
    this.stmtDelete = this.db.prepare(`DELETE FROM ${this.table} WHERE id = ?`)
    this.stmtHas = this.db.prepare(`SELECT 1 FROM ${this.table} WHERE id = ? LIMIT 1`)
    this.stmtGet = this.db.prepare(`SELECT vec FROM ${this.table} WHERE id = ?`)
    this.stmtCount = this.db.prepare(`SELECT COUNT(*) as cnt FROM ${this.table}`)
    this.stmtListAll = this.db.prepare(`SELECT id, meta FROM ${this.table} ORDER BY ts DESC`)
    this.stmtSelectAll = this.db.prepare(`SELECT id, vec, meta FROM ${this.table}`)
    this.stmtStats = this.db.prepare(
      `SELECT COUNT(*) as cnt, MIN(ts) as oldest, MAX(ts) as newest FROM ${this.table}`
    )
    this.stmtPurgeBefore = this.db.prepare(`DELETE FROM ${this.table} WHERE ts < ?`)
  }
}

// ── Singleton ──────────────────────────────────────────────────────────────

let _instance: SqliteVectorIndex | null = null

/** Get the shared SqliteVectorIndex singleton. */
export function getVectorIndex(logger?: ILogger): SqliteVectorIndex {
  if (!_instance) {
    const fallbackLogger: ILogger = {
      debug() {}, info() {}, warn() {}, error() {},
      child() { return this },
    }
    _instance = new SqliteVectorIndex(logger || fallbackLogger)
  }
  return _instance
}

/** Reset the singleton (useful for tests). */
export function resetVectorIndex(): void {
  _instance?.close()
  _instance = null
}
