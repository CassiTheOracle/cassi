/**
 * Context Feedback Tracker
 *
 * Tracks whether code context injections were actually useful to agents.
 * Uses SQLite for persistence and Bayesian scoring to learn which
 * specificity ranges and context modes produce the best results.
 *
 * Integrates with the existing StrategyTracker's Beta-Binomial model.
 */

import Database from 'better-sqlite3'
import { randomUUID } from 'node:crypto'
import { join } from 'node:path'
import { existsSync, mkdirSync } from 'node:fs'
import type { ILogger } from '../../../types/interfaces.js'
import type { ContextFeedbackRecord } from './types.js'

/** Database file location under CassiCore data dir. */
const DB_FILENAME = 'context-feedback.db'

/** Bayesian prior: weak prior (Beta(1,1) = uniform). */
const PRIOR_ALPHA = 1
const PRIOR_BETA = 1

/**
 * Manages feedback tracking for code context quality.
 */
export class ContextFeedbackTracker {
  private db: Database.Database | null = null
  private logger: ILogger

  constructor(logger: ILogger, dataDir?: string) {
    this.logger = logger
    this.initDb(dataDir)
  }

  private initDb(dataDir?: string): void {
    try {
      const dir = dataDir || join(process.env.HOME || '/tmp', '.cassi', 'data')
      if (!existsSync(dir)) mkdirSync(dir, { recursive: true })

      const dbPath = join(dir, DB_FILENAME)
      this.db = new Database(dbPath)
      this.db.pragma('journal_mode = WAL')
      this.db.pragma('busy_timeout = 5000')

      this.db.exec(`
        CREATE TABLE IF NOT EXISTS context_feedback (
          id TEXT PRIMARY KEY,
          session_id TEXT NOT NULL,
          query_text TEXT NOT NULL,
          specificity_score REAL NOT NULL,
          context_mode TEXT NOT NULL CHECK(context_mode IN ('full', 'file_only', 'skip')),
          files_suggested TEXT NOT NULL DEFAULT '[]',
          files_actually_used TEXT NOT NULL DEFAULT '[]',
          was_useful INTEGER NOT NULL DEFAULT 0,
          timestamp INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_feedback_session ON context_feedback(session_id);
        CREATE INDEX IF NOT EXISTS idx_feedback_mode ON context_feedback(context_mode);
        CREATE INDEX IF NOT EXISTS idx_feedback_timestamp ON context_feedback(timestamp);

        CREATE TABLE IF NOT EXISTS context_mode_scores (
          mode TEXT NOT NULL,
          specificity_bucket TEXT NOT NULL,
          alpha REAL NOT NULL DEFAULT ${PRIOR_ALPHA},
          beta REAL NOT NULL DEFAULT ${PRIOR_BETA},
          sample_count INTEGER NOT NULL DEFAULT 0,
          updated_at INTEGER NOT NULL,
          PRIMARY KEY (mode, specificity_bucket)
        );
      `)
    } catch (err) {
      this.logger.error('Failed to initialize context feedback database', { error: String(err) })
    }
  }

  /**
   * Record a context injection event.
   */
  recordInjection(
    sessionId: string,
    queryText: string,
    specificityScore: number,
    contextMode: 'full' | 'file_only' | 'skip',
    filesSuggested: string[],
  ): string {
    const id = randomUUID()
    try {
      this.db?.prepare(`
        INSERT INTO context_feedback (id, session_id, query_text, specificity_score, context_mode, files_suggested, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
      `).run(id, sessionId, queryText, specificityScore, contextMode, JSON.stringify(filesSuggested), Date.now())
    } catch (err) {
      this.logger.error('Failed to record context injection', { error: String(err) })
    }
    return id
  }

  /**
   * Record which files the agent actually used after context was injected.
   */
  recordUsage(id: string, filesUsed: string[]): void {
    try {
      // Determine if useful = intersection between suggested and used > 0
      const row = this.db?.prepare('SELECT files_suggested FROM context_feedback WHERE id = ?').get(id) as any
      if (!row) return

      const suggested = JSON.parse(row.files_suggested) as string[]
      const usedSet = new Set(filesUsed)
      const overlap = suggested.filter(f => usedSet.has(f))
      const wasUseful = overlap.length > 0 ? 1 : 0

      this.db?.prepare(`
        UPDATE context_feedback
        SET files_actually_used = ?, was_useful = ?
        WHERE id = ?
      `).run(JSON.stringify(filesUsed), wasUseful, id)

      // Update Bayesian scores
      const feedbackRow = this.db?.prepare('SELECT specificity_score, context_mode FROM context_feedback WHERE id = ?').get(id) as any
      if (feedbackRow) {
        this.updateBayesianScore(feedbackRow.context_mode, feedbackRow.specificity_score, wasUseful === 1)
      }
    } catch (err) {
      this.logger.error('Failed to record context usage', { error: String(err) })
    }
  }

  /**
   * Update Bayesian Beta-Binomial score for a mode + specificity bucket.
   */
  private updateBayesianScore(mode: string, specificityScore: number, wasUseful: boolean): void {
    const bucket = specificityScore < 0.3 ? 'low' : specificityScore < 0.6 ? 'medium' : 'high'

    try {
      const existing = this.db?.prepare(
        'SELECT alpha, beta, sample_count FROM context_mode_scores WHERE mode = ? AND specificity_bucket = ?',
      ).get(mode, bucket) as any

      if (existing) {
        const newAlpha = existing.alpha + (wasUseful ? 1 : 0)
        const newBeta = existing.beta + (wasUseful ? 0 : 1)
        this.db?.prepare(`
          UPDATE context_mode_scores
          SET alpha = ?, beta = ?, sample_count = sample_count + 1, updated_at = ?
          WHERE mode = ? AND specificity_bucket = ?
        `).run(newAlpha, newBeta, Date.now(), mode, bucket)
      } else {
        const alpha = PRIOR_ALPHA + (wasUseful ? 1 : 0)
        const beta = PRIOR_BETA + (wasUseful ? 0 : 1)
        this.db?.prepare(`
          INSERT INTO context_mode_scores (mode, specificity_bucket, alpha, beta, sample_count, updated_at)
          VALUES (?, ?, ?, ?, 1, ?)
        `).run(mode, bucket, alpha, beta, Date.now())
      }
    } catch (err) {
      this.logger.error('Failed to update Bayesian score', { error: String(err) })
    }
  }

  /**
   * Get effectiveness scores for all mode + bucket combinations.
   */
  getEffectivenessScores(): Array<{
    mode: string
    specificityBucket: string
    bayesMean: number
    sampleCount: number
    alpha: number
    beta: number
  }> {
    try {
      const rows = this.db?.prepare(
        'SELECT mode, specificity_bucket, alpha, beta, sample_count FROM context_mode_scores ORDER BY mode, specificity_bucket',
      ).all() as any[] || []

      return rows.map(r => ({
        mode: r.mode,
        specificityBucket: r.specificity_bucket,
        bayesMean: Math.round((r.alpha / (r.alpha + r.beta)) * 1000) / 1000,
        sampleCount: r.sample_count,
        alpha: r.alpha,
        beta: r.beta,
      }))
    } catch {
      return []
    }
  }

  /**
   * Get recent feedback records.
   */
  getRecent(limit = 20): ContextFeedbackRecord[] {
    try {
      const rows = this.db?.prepare(
        'SELECT * FROM context_feedback ORDER BY timestamp DESC LIMIT ?',
      ).all(limit) as any[] || []

      return rows.map(r => ({
        id: r.id,
        sessionId: r.session_id,
        queryText: r.query_text,
        specificityScore: r.specificity_score,
        contextMode: r.context_mode,
        filesSuggested: JSON.parse(r.files_suggested),
        filesActuallyUsed: JSON.parse(r.files_actually_used || '[]'),
        wasUseful: r.was_useful === 1,
        timestamp: r.timestamp,
      }))
    } catch {
      return []
    }
  }

  /**
   * Get summary statistics.
   */
  getStats(): { totalRecords: number; usefulRate: number; byMode: Record<string, { count: number; usefulRate: number }> } {
    try {
      const total = (this.db?.prepare('SELECT COUNT(*) as c FROM context_feedback').get() as any)?.c || 0
      const useful = (this.db?.prepare('SELECT COUNT(*) as c FROM context_feedback WHERE was_useful = 1').get() as any)?.c || 0

      const modeRows = this.db?.prepare(`
        SELECT context_mode, COUNT(*) as total, SUM(was_useful) as useful
        FROM context_feedback GROUP BY context_mode
      `).all() as any[] || []

      const byMode: Record<string, { count: number; usefulRate: number }> = {}
      for (const r of modeRows) {
        byMode[r.context_mode] = {
          count: r.total,
          usefulRate: r.total > 0 ? Math.round((r.useful / r.total) * 1000) / 1000 : 0,
        }
      }

      return {
        totalRecords: total,
        usefulRate: total > 0 ? Math.round((useful / total) * 1000) / 1000 : 0,
        byMode,
      }
    } catch {
      return { totalRecords: 0, usefulRate: 0, byMode: {} }
    }
  }

  /**
   * Close the database connection.
   */
  close(): void {
    try {
      this.db?.close()
    } catch {
      // Best-effort
    }
  }
}
