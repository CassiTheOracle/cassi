/**
 * ReasoningBank — Cache and retrieve successful reasoning traces
 *
 * Stores high-quality reasoning traces from completed Helix sessions in a
 * dedicated SQLite database with FTS5 full-text search. Traces are scored
 * by quality, recency, and usage frequency. Retrieved traces are injected
 * into Helix branch context to give new sessions the benefit of past
 * successful approaches.
 *
 * Storage: Dedicated SQLite DB (reasoning-bank.db) with FTS5 indexing.
 * Retrieval: Hybrid BM25 text search + quality/recency scoring.
 * Ingestion: Called after Helix sessions complete with quality > threshold.
 */

import fs from 'fs'
import path from 'path'

import Database from 'better-sqlite3'

import { getDataDir } from '@cassicore/foundation'

import type { ILogger } from '@cassicore/foundation'
import type {
  ReasoningTrace,
  StoreTraceOpts,
  SearchTracesOpts,
  SearchResult,
  ReasoningBankStats,
  ReasoningBankOpts,
} from './types.js'

const SCHEMA = `
CREATE TABLE IF NOT EXISTS reasoning_traces (
  id               TEXT PRIMARY KEY,
  source_helix_id  TEXT NOT NULL,
  goal             TEXT NOT NULL,
  approach         TEXT NOT NULL,
  content          TEXT NOT NULL,
  quality_score    REAL NOT NULL,
  succeeded        INTEGER NOT NULL DEFAULT 1,
  relevant_files   TEXT,
  task_type        TEXT NOT NULL DEFAULT 'general',
  reference_count  INTEGER NOT NULL DEFAULT 0,
  created_at       INTEGER NOT NULL,
  last_retrieved_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_rt_quality ON reasoning_traces(quality_score DESC);
CREATE INDEX IF NOT EXISTS idx_rt_task_type ON reasoning_traces(task_type);
CREATE INDEX IF NOT EXISTS idx_rt_created ON reasoning_traces(created_at DESC);

CREATE VIRTUAL TABLE IF NOT EXISTS reasoning_fts USING fts5(
  id UNINDEXED,
  goal,
  approach,
  content,
  content='reasoning_traces',
  content_rowid='rowid',
  tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS rt_ai AFTER INSERT ON reasoning_traces BEGIN
  INSERT INTO reasoning_fts(rowid, id, goal, approach, content)
  VALUES (NEW.rowid, NEW.id, NEW.goal, NEW.approach, NEW.content);
END;

CREATE TRIGGER IF NOT EXISTS rt_ad AFTER DELETE ON reasoning_traces BEGIN
  INSERT INTO reasoning_fts(reasoning_fts, rowid, id, goal, approach, content)
  VALUES ('delete', OLD.rowid, OLD.id, OLD.goal, OLD.approach, OLD.content);
END;

CREATE TRIGGER IF NOT EXISTS rt_au AFTER UPDATE ON reasoning_traces BEGIN
  INSERT INTO reasoning_fts(reasoning_fts, rowid, id, goal, approach, content)
  VALUES ('delete', OLD.rowid, OLD.id, OLD.goal, OLD.approach, OLD.content);
  INSERT INTO reasoning_fts(rowid, id, goal, approach, content)
  VALUES (NEW.rowid, NEW.id, NEW.goal, NEW.approach, NEW.content);
END;
`

/** Default options */
const DEFAULTS: Required<ReasoningBankOpts> = {
  dbPath: '',
  minQualityThreshold: 0.6,
  maxAgeDays: 90,
  maxTraces: 1000,
}

export class ReasoningBank {
  private db: Database.Database
  private readonly log: ILogger
  private readonly opts: Required<ReasoningBankOpts>
  private stmtCache = new Map<string, Database.Statement>()

  constructor(logger: ILogger, opts?: ReasoningBankOpts) {
    this.log = logger.child('reasoning-bank')
    this.opts = {
      ...DEFAULTS,
      ...opts,
      dbPath: opts?.dbPath || path.join(getDataDir(), 'system-state.db'),
    }

    const dir = path.dirname(this.opts.dbPath)
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true })
    }

    this.db = new Database(this.opts.dbPath)
    this.db.pragma('journal_mode = WAL')
    this.db.pragma('synchronous = NORMAL')
    this.db.exec(SCHEMA)

    this.log.info('ReasoningBank initialized', {
      dbPath: this.opts.dbPath,
      minQualityThreshold: this.opts.minQualityThreshold,
    })
  }

  /** Cached prepared statement helper */
  private stmt(key: string, sql: string): Database.Statement {
    let s = this.stmtCache.get(key)
    if (!s) {
      s = this.db.prepare(sql)
      this.stmtCache.set(key, s)
    }
    return s
  }

  /**
   * Store a reasoning trace. Rejects traces below the quality threshold.
   * Returns the trace ID if stored, null if rejected.
   */
  store(opts: StoreTraceOpts): string | null {
    if (opts.qualityScore < this.opts.minQualityThreshold) {
      this.log.debug('Trace rejected: below quality threshold', {
        score: opts.qualityScore,
        threshold: this.opts.minQualityThreshold,
        sourceHelixId: opts.sourceHelixId,
      })
      return null
    }

    const id = `rt-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    const now = Date.now()

    this.stmt('insert_trace', `
      INSERT INTO reasoning_traces
        (id, source_helix_id, goal, approach, content, quality_score,
         succeeded, relevant_files, task_type, reference_count, created_at, last_retrieved_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, NULL)
    `).run(
      id,
      opts.sourceHelixId,
      opts.goal,
      opts.approach,
      opts.content,
      opts.qualityScore,
      opts.succeeded ? 1 : 0,
      opts.relevantFiles?.length ? JSON.stringify(opts.relevantFiles) : null,
      opts.taskType || 'general',
      now,
    )

    this.log.info('Reasoning trace stored', {
      id,
      sourceHelixId: opts.sourceHelixId,
      qualityScore: opts.qualityScore,
      taskType: opts.taskType || 'general',
    })

    // Enforce max traces limit
    this.enforceLimit()

    return id
  }

  /**
   * Search for relevant reasoning traces by query.
   * Uses BM25 full-text search combined with quality and recency scoring.
   */
  search(opts: SearchTracesOpts): SearchResult[] {
    const limit = opts.limit ?? 5
    const minQuality = opts.minQuality ?? 0
    const successOnly = opts.successOnly ?? false

    // HOW: Build a hybrid query that combines FTS5 BM25 relevance with
    // quality score and recency. The final score is a weighted blend.
    const conditions: string[] = []
    const params: any[] = []

    conditions.push('reasoning_fts MATCH ?')
    params.push(this.sanitizeFtsQuery(opts.query))

    if (minQuality > 0) {
      conditions.push('rt.quality_score >= ?')
      params.push(minQuality)
    }

    if (successOnly) {
      conditions.push('rt.succeeded = 1')
    }

    if (opts.taskType) {
      conditions.push('rt.task_type = ?')
      params.push(opts.taskType)
    }

    const whereClause = conditions.join(' AND ')

    // HOW: Scoring formula blends BM25 relevance (60%), quality (25%),
    // and recency (15%). Reference count provides a small tiebreaker.
    const sql = `
      SELECT
        rt.*,
        (
          (-rank * 0.6) +
          (rt.quality_score * 0.25) +
          (1.0 / (1.0 + (CAST(? AS REAL) - rt.created_at) / 86400000.0) * 0.15) +
          (MIN(rt.reference_count, 10) / 10.0 * 0.05)
        ) AS combined_score
      FROM reasoning_fts
      JOIN reasoning_traces rt ON reasoning_fts.id = rt.id
      WHERE ${whereClause}
      ORDER BY combined_score DESC
      LIMIT ?
    `

    const now = Date.now()
    params.unshift(now)
    params.push(limit)

    try {
      const rows = this.db.prepare(sql).all(...params) as any[]

      // Track access for returned traces
      if (rows.length > 0) {
        const ids = rows.map(r => r.id)
        this.trackAccess(ids)
      }

      // Filter by relevant files if specified
      let results = rows.map(row => this.rowToSearchResult(row))

      if (opts.relevantFiles?.length) {
        results = results.filter(r => {
          if (r.trace.relevantFiles.length === 0) return true
          return r.trace.relevantFiles.some(f =>
            opts.relevantFiles!.some(rf => f.includes(rf) || rf.includes(f))
          )
        })
      }

      return results
    } catch (err) {
      this.log.warn('FTS search failed, falling back to LIKE', { error: String(err) })
      return this.fallbackSearch(opts, limit)
    }
  }

  /**
   * Retrieve traces relevant to a Helix branch goal.
   * Returns a formatted string suitable for context injection, or null if
   * no relevant traces are found.
   */
  retrieveForBranch(goal: string, taskType?: string): string | null {
    const results = this.search({
      query: goal,
      minQuality: 0.6,
      successOnly: true,
      taskType: taskType as any,
      limit: 3,
    })

    if (results.length === 0) return null

    const lines: string[] = ['## Reasoning Bank — Relevant Past Approaches']

    for (const { trace, relevance } of results) {
      lines.push('')
      lines.push(`### ${trace.approach} (quality: ${trace.qualityScore.toFixed(2)}, relevance: ${relevance.toFixed(2)})`)
      lines.push(`Goal: ${trace.goal}`)
      if (trace.relevantFiles.length > 0) {
        lines.push(`Files: ${trace.relevantFiles.slice(0, 5).join(', ')}`)
      }
      lines.push('')
      // HOW: Truncate content to avoid bloating context
      const maxContentLength = 500
      const content = trace.content.length > maxContentLength
        ? trace.content.slice(0, maxContentLength) + '...'
        : trace.content
      lines.push(content)
    }

    return lines.join('\n')
  }

  /**
   * Get statistics about the reasoning bank.
   */
  getStats(): ReasoningBankStats {
    const row = this.db.prepare(`
      SELECT
        COUNT(*) as total,
        SUM(CASE WHEN succeeded = 1 THEN 1 ELSE 0 END) as successful,
        AVG(quality_score) as avgQuality,
        SUM(reference_count) as totalRefs,
        SUM(CASE WHEN reference_count = 0 THEN 1 ELSE 0 END) as neverReferenced
      FROM reasoning_traces
    `).get() as any

    const taskTypes = this.db.prepare(`
      SELECT task_type, COUNT(*) as count
      FROM reasoning_traces
      GROUP BY task_type
    `).all() as any[]

    const byTaskType: Record<string, number> = {}
    for (const t of taskTypes) {
      byTaskType[t.task_type] = t.count
    }

    return {
      totalTraces: row?.total ?? 0,
      successfulTraces: row?.successful ?? 0,
      averageQuality: row?.avgQuality ?? 0,
      totalReferences: row?.totalRefs ?? 0,
      tracesNeverReferenced: row?.neverReferenced ?? 0,
      byTaskType,
    }
  }

  /**
   * Prune old, low-quality, or excess traces.
   * Returns the number of traces removed.
   */
  prune(): number {
    const maxAge = this.opts.maxAgeDays * 24 * 60 * 60 * 1000
    const cutoff = Date.now() - maxAge

    // Remove old traces that have never been referenced and have low quality
    const result = this.db.prepare(`
      DELETE FROM reasoning_traces
      WHERE created_at < ?
        AND reference_count = 0
        AND quality_score < 0.75
    `).run(cutoff)

    const pruned = result.changes

    if (pruned > 0) {
      this.log.info('Pruned stale reasoning traces', { pruned })
    }

    return pruned
  }

  /** Close the database */
  close(): void {
    this.stmtCache.clear()
    this.db.close()
  }

  /** Private helpers */

  /** Track access for retrieved trace IDs (fire-and-forget) */
  private trackAccess(ids: string[]): void {
    try {
      const now = Date.now()
      const update = this.stmt('track_access', `
        UPDATE reasoning_traces
        SET reference_count = reference_count + 1,
            last_retrieved_at = ?
        WHERE id = ?
      `)
      const tx = this.db.transaction(() => {
        for (const id of ids) {
          update.run(now, id)
        }
      })
      tx()
    } catch (err) {
      this.log.warn('Failed to track reasoning trace access', { error: String(err) })
    }
  }

  /** Enforce the maximum trace limit by removing lowest-scoring old traces */
  private enforceLimit(): void {
    try {
      const count = (this.db.prepare('SELECT COUNT(*) as c FROM reasoning_traces').get() as any)?.c ?? 0
      if (count <= this.opts.maxTraces) return

      const excess = count - this.opts.maxTraces
      // HOW: Remove lowest scoring traces that haven't been referenced recently
      this.db.prepare(`
        DELETE FROM reasoning_traces
        WHERE id IN (
          SELECT id FROM reasoning_traces
          ORDER BY (quality_score * 0.5 + (reference_count / 10.0) * 0.3 + (created_at / ${Date.now()}.0) * 0.2) ASC
          LIMIT ?
        )
      `).run(excess)

      this.log.info('Enforced trace limit', { removed: excess, maxTraces: this.opts.maxTraces })
    } catch (err) {
      this.log.warn('Failed to enforce trace limit', { error: String(err) })
    }
  }

  /** Sanitize FTS5 query — escape special characters */
  private sanitizeFtsQuery(query: string): string {
    // HOW: Remove FTS5 special operators that could cause syntax errors,
    // but preserve meaningful words. Quote multi-word phrases.
    return query
      .replace(/['"(){}[\]*:^~]/g, ' ')
      .replace(/\b(AND|OR|NOT|NEAR)\b/gi, '')
      .split(/\s+/)
      .filter(w => w.length > 2)
      .slice(0, 15)
      .join(' OR ')
      || query.slice(0, 50)
  }

  /** Fallback search using LIKE when FTS fails */
  private fallbackSearch(opts: SearchTracesOpts, limit: number): SearchResult[] {
    const words = opts.query.split(/\s+/).filter(w => w.length > 3).slice(0, 5)
    if (words.length === 0) return []

    const likeConditions = words.map(() => '(goal LIKE ? OR content LIKE ? OR approach LIKE ?)').join(' OR ')
    const params: any[] = []
    for (const w of words) {
      params.push(`%${w}%`, `%${w}%`, `%${w}%`)
    }

    if (opts.successOnly) {
      params.push(1)
    }

    const sql = `
      SELECT * FROM reasoning_traces
      WHERE (${likeConditions})
      ${opts.successOnly ? 'AND succeeded = ?' : ''}
      ORDER BY quality_score DESC
      LIMIT ?
    `
    params.push(limit)

    const rows = this.db.prepare(sql).all(...params) as any[]
    return rows.map(row => this.rowToSearchResult(row, 0.5))
  }

  /** Convert a database row to a SearchResult */
  private rowToSearchResult(row: any, defaultRelevance?: number): SearchResult {
    const trace: ReasoningTrace = {
      id: row.id,
      sourceHelixId: row.source_helix_id,
      goal: row.goal,
      approach: row.approach,
      content: row.content,
      qualityScore: row.quality_score,
      succeeded: row.succeeded === 1,
      relevantFiles: row.relevant_files ? JSON.parse(row.relevant_files) : [],
      taskType: row.task_type,
      referenceCount: row.reference_count,
      createdAt: row.created_at,
      lastRetrievedAt: row.last_retrieved_at,
    }

    return {
      trace,
      relevance: defaultRelevance ?? Math.min(1.0, row.combined_score ?? 0.5),
    }
  }
}
