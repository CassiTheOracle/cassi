/**
 * MeditationStore — SQLite-backed persistence for prompt evolution.
 *
 * Lives at ~/.cassicore/data/meditation.db
 *
 * Schema v2 stores:
 *   - Prompt library with Thompson sampling params + lineage tracking
 *   - Per-session evaluation scores from Cassi
 *   - Style-specific Thompson params (same prompt, different performance per style)
 *   - Evolution meta-parameters (mutation temperature, etc.)
 *   - Full-text search on evaluation narratives
 *
 * Pattern follows ConstellationStore — static factory, WAL mode,
 * prepared statements, JSON blobs for nested state.
 */

import fs from 'node:fs'
import path from 'node:path'

import Database from 'better-sqlite3'

import type { ILogger } from '../../../../types/interfaces.js'
import type { MeditationPrompt } from './types.js'
import type { MeditationStyle } from './styles.js'
import { getDataDir } from '../../../utils/paths.js'


const SCHEMA_VERSION = 3


const SCHEMA_V1 = `
  CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);

  CREATE TABLE IF NOT EXISTS prompts (
    id          TEXT PRIMARY KEY,
    category    TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    alpha       REAL NOT NULL DEFAULT 1.0,
    beta        REAL NOT NULL DEFAULT 1.0,
    times_used  INTEGER NOT NULL DEFAULT 0,
    avg_score   REAL NOT NULL DEFAULT 0.0,
    last_used_at INTEGER,
    created_at  INTEGER NOT NULL
  );

  CREATE INDEX IF NOT EXISTS idx_prompts_category ON prompts(category);
  CREATE INDEX IF NOT EXISTS idx_prompts_avg_score ON prompts(avg_score DESC);

  CREATE TABLE IF NOT EXISTS prompt_scores (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT NOT NULL,
    explorer_name       TEXT NOT NULL,
    prompt_id           TEXT NOT NULL,
    style               TEXT NOT NULL DEFAULT 'passive',
    exploration_depth   REAL,
    curiosity_signal    REAL,
    connection_quality  REAL,
    overall_score       REAL NOT NULL,
    evaluation_text     TEXT,
    step_count          INTEGER,
    stop_reason         TEXT,
    scored_at           INTEGER NOT NULL,
    FOREIGN KEY (prompt_id) REFERENCES prompts(id)
  );

  CREATE INDEX IF NOT EXISTS idx_scores_prompt ON prompt_scores(prompt_id);
  CREATE INDEX IF NOT EXISTS idx_scores_session ON prompt_scores(session_id);
  CREATE INDEX IF NOT EXISTS idx_scores_scored ON prompt_scores(scored_at DESC);

  CREATE TABLE IF NOT EXISTS evaluation_sessions (
    id              TEXT PRIMARY KEY,
    style           TEXT NOT NULL DEFAULT 'passive',
    started_at      INTEGER NOT NULL,
    evaluated_at    INTEGER,
    eval_duration_ms INTEGER,
    eval_tokens_used INTEGER,
    eval_summary    TEXT,
    stop_reason     TEXT NOT NULL,
    prompts_scored  INTEGER DEFAULT 0
  );
`


const MIGRATE_V1_TO_V2 = `
  -- Prompt evolution: authorship and lineage
  ALTER TABLE prompts ADD COLUMN author TEXT DEFAULT 'library';
  ALTER TABLE prompts ADD COLUMN parent_id TEXT REFERENCES prompts(id);
  ALTER TABLE prompts ADD COLUMN retired_at INTEGER;

  -- Style-specific Thompson params (same prompt, different behavior per style)
  CREATE TABLE IF NOT EXISTS prompt_style_stats (
    prompt_id   TEXT NOT NULL,
    style       TEXT NOT NULL,
    alpha       REAL NOT NULL DEFAULT 1.0,
    beta        REAL NOT NULL DEFAULT 1.0,
    times_used  INTEGER NOT NULL DEFAULT 0,
    avg_score   REAL NOT NULL DEFAULT 0.0,
    last_used_at INTEGER,
    PRIMARY KEY (prompt_id, style),
    FOREIGN KEY (prompt_id) REFERENCES prompts(id)
  );

  -- Evolution meta-parameters (mutation temperature, etc.)
  CREATE TABLE IF NOT EXISTS meta_params (
    key         TEXT PRIMARY KEY,
    value_real  REAL,
    value_text  TEXT,
    updated_at  INTEGER NOT NULL
  );

  -- Full-text search on evaluation narratives
  CREATE VIRTUAL TABLE IF NOT EXISTS evaluation_fts USING fts5(
    evaluation_text,
    content=prompt_scores,
    content_rowid=id
  );

  -- FTS5 sync triggers
  CREATE TRIGGER IF NOT EXISTS eval_fts_insert AFTER INSERT ON prompt_scores
  WHEN NEW.evaluation_text IS NOT NULL BEGIN
    INSERT INTO evaluation_fts(rowid, evaluation_text) VALUES (NEW.id, NEW.evaluation_text);
  END;

  CREATE TRIGGER IF NOT EXISTS eval_fts_delete AFTER DELETE ON prompt_scores BEGIN
    INSERT INTO evaluation_fts(evaluation_fts, rowid, evaluation_text) VALUES ('delete', OLD.id, COALESCE(OLD.evaluation_text, ''));
  END;

  -- Seed default meta params
  INSERT OR IGNORE INTO meta_params (key, value_real, updated_at) VALUES ('mutation_temperature', 0.5, ${Date.now()});
  INSERT OR IGNORE INTO meta_params (key, value_real, updated_at) VALUES ('max_cassi_prompts', 20, ${Date.now()});
`


const MIGRATE_V2_TO_V3 = `
  -- Corpus prompt evolution: parallel to explorer prompts
  CREATE TABLE IF NOT EXISTS corpus_prompts (
    id          TEXT PRIMARY KEY,
    category    TEXT NOT NULL,
    identity    TEXT NOT NULL,
    approach    TEXT NOT NULL,
    style       TEXT NOT NULL,
    alpha       REAL NOT NULL DEFAULT 1.0,
    beta        REAL NOT NULL DEFAULT 1.0,
    times_used  INTEGER NOT NULL DEFAULT 0,
    avg_score   REAL NOT NULL DEFAULT 0.0,
    last_used_at INTEGER,
    author      TEXT DEFAULT 'library',
    parent_id   TEXT REFERENCES corpus_prompts(id),
    retired_at  INTEGER,
    created_at  INTEGER NOT NULL
  );

  CREATE INDEX IF NOT EXISTS idx_corpus_prompts_style ON corpus_prompts(style);
  CREATE INDEX IF NOT EXISTS idx_corpus_prompts_avg_score ON corpus_prompts(avg_score DESC);

  CREATE TABLE IF NOT EXISTS corpus_prompt_scores (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT NOT NULL,
    corpus_prompt_id    TEXT NOT NULL,
    style               TEXT NOT NULL,
    insight_quality     REAL,
    tool_diversity      REAL,
    depth               REAL,
    self_reflection     REAL,
    overall_score       REAL NOT NULL,
    evaluation_text     TEXT,
    scored_at           INTEGER NOT NULL,
    FOREIGN KEY (corpus_prompt_id) REFERENCES corpus_prompts(id)
  );

  CREATE INDEX IF NOT EXISTS idx_corpus_scores_prompt ON corpus_prompt_scores(corpus_prompt_id);
  CREATE INDEX IF NOT EXISTS idx_corpus_scores_scored ON corpus_prompt_scores(scored_at DESC);
`


export interface PromptRow {
  id: string
  category: string
  prompt_text: string
  alpha: number
  beta: number
  times_used: number
  avg_score: number
  last_used_at: number | null
  created_at: number
  author: string
  parent_id: string | null
  retired_at: number | null
}

export interface PromptScoreInsert {
  session_id: string
  explorer_name: string
  prompt_id: string
  style: MeditationStyle
  exploration_depth?: number
  curiosity_signal?: number
  connection_quality?: number
  overall_score: number
  evaluation_text?: string
  step_count?: number
  stop_reason?: string
}

export interface PromptScoreRow extends PromptScoreInsert {
  id: number
  scored_at: number
}

export interface StyleStatsRow {
  prompt_id: string
  style: string
  alpha: number
  beta: number
  times_used: number
  avg_score: number
}

export interface CorpusPromptRow {
  id: string
  category: string
  identity: string
  approach: string
  style: string
  alpha: number
  beta: number
  times_used: number
  avg_score: number
  last_used_at: number | null
  author: string
  parent_id: string | null
  retired_at: number | null
  created_at: number
}

export interface CorpusPromptScoreInsert {
  session_id: string
  corpus_prompt_id: string
  style: MeditationStyle
  insight_quality?: number
  tool_diversity?: number
  depth?: number
  self_reflection?: number
  overall_score: number
  evaluation_text?: string
}


export class MeditationStore {
  private db: Database.Database
  private logger: ILogger
  private _stmts?: ReturnType<MeditationStore['prepareStatements']>


  private constructor(db: Database.Database, logger: ILogger) {
    this.db = db
    this.logger = logger
  }


  static open(logger: ILogger, dataDir?: string): MeditationStore {
    const dir = dataDir ?? getDataDir()
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true })
    }

    const dbPath = path.join(dir, 'meditation.db')
    const db = new Database(dbPath)
    db.pragma('journal_mode = WAL')
    db.pragma('synchronous = NORMAL')
    db.pragma('foreign_keys = ON')
    db.pragma('busy_timeout = 5000')

    let existing: number | undefined
    try {
      existing = db.prepare('SELECT version FROM schema_version LIMIT 1').pluck().get() as number | undefined
    } catch {
      existing = undefined
    }

    if (!existing) {
      db.exec(SCHEMA_V1)
      db.exec(MIGRATE_V1_TO_V2)
      db.exec(MIGRATE_V2_TO_V3)
      db.prepare('INSERT OR REPLACE INTO schema_version (version) VALUES (?)').run(SCHEMA_VERSION)
    } else if (existing < 2) {
      db.exec(MIGRATE_V1_TO_V2)
      db.exec(MIGRATE_V2_TO_V3)
      db.prepare('INSERT OR REPLACE INTO schema_version (version) VALUES (?)').run(SCHEMA_VERSION)
    } else if (existing < 3) {
      db.exec(MIGRATE_V2_TO_V3)
      db.prepare('INSERT OR REPLACE INTO schema_version (version) VALUES (?)').run(SCHEMA_VERSION)
    }

    const store = new MeditationStore(db, logger)
    logger.info('[MeditationStore] Opened', { dbPath, version: SCHEMA_VERSION })
    return store
  }


  /**
   * Upsert library prompts. Preserves accumulated scores if prompt text unchanged.
   */
  seedPrompts(prompts: MeditationPrompt[]): void {
    const upsert = this.db.prepare(`
      INSERT INTO prompts (id, category, prompt_text, author, created_at)
      VALUES (@id, @category, @prompt_text, 'library', @created_at)
      ON CONFLICT(id) DO UPDATE SET
        category = @category,
        prompt_text = @prompt_text
    `)

    const now = Date.now()
    const txn = this.db.transaction(() => {
      for (const p of prompts) {
        upsert.run({ id: p.id, category: p.category, prompt_text: p.prompt, created_at: now })
      }
    })
    txn()

    this.logger.info('[MeditationStore] Seeded prompts', { count: prompts.length })
  }


  private get stmts() {
    if (!this._stmts) this._stmts = this.prepareStatements()
    return this._stmts
  }

  private prepareStatements() {
    return {
      // Prompt queries
      getPrompt: this.db.prepare('SELECT id, category, prompt_text as prompt_text, alpha, beta, times_used, avg_score, last_used_at, created_at, author, parent_id, retired_at FROM prompts WHERE id = ?'),
      getAllPrompts: this.db.prepare('SELECT * FROM prompts WHERE retired_at IS NULL ORDER BY avg_score DESC'),
      getPromptsByCategory: this.db.prepare('SELECT * FROM prompts WHERE category = ? AND retired_at IS NULL ORDER BY avg_score DESC'),
      getActivePromptCount: this.db.prepare('SELECT COUNT(*) FROM prompts WHERE retired_at IS NULL').pluck(),
      getCassiPromptCount: this.db.prepare("SELECT COUNT(*) FROM prompts WHERE author = 'cassi' AND retired_at IS NULL").pluck(),

      // Prompt mutation
      insertMutatedPrompt: this.db.prepare(`
        INSERT INTO prompts (id, category, prompt_text, author, parent_id, created_at)
        VALUES (@id, @category, @prompt_text, 'cassi', @parent_id, @created_at)
      `),
      retirePrompt: this.db.prepare('UPDATE prompts SET retired_at = ? WHERE id = ?'),
      getPromptLineage: this.db.prepare(`
        WITH RECURSIVE lineage(id, parent_id, depth) AS (
          SELECT id, parent_id, 0 FROM prompts WHERE id = ?
          UNION ALL
          SELECT p.id, p.parent_id, l.depth + 1
          FROM prompts p JOIN lineage l ON p.id = l.parent_id
          WHERE l.depth < 10
        )
        SELECT p.* FROM prompts p JOIN lineage l ON p.id = l.id ORDER BY l.depth
      `),

      // Score recording
      insertScore: this.db.prepare(`
        INSERT INTO prompt_scores
          (session_id, explorer_name, prompt_id, style,
           exploration_depth, curiosity_signal, connection_quality,
           overall_score, evaluation_text, step_count, stop_reason, scored_at)
        VALUES
          (@session_id, @explorer_name, @prompt_id, @style,
           @exploration_depth, @curiosity_signal, @connection_quality,
           @overall_score, @evaluation_text, @step_count, @stop_reason, @scored_at)
      `),
      updatePromptAggregates: this.db.prepare(`
        UPDATE prompts SET
          alpha = alpha + @score,
          beta = beta + (1.0 - @score),
          times_used = times_used + 1,
          avg_score = (avg_score * times_used + @score) / (times_used + 1),
          last_used_at = @now
        WHERE id = @id
      `),

      // Style-specific stats
      upsertStyleStats: this.db.prepare(`
        INSERT INTO prompt_style_stats (prompt_id, style, alpha, beta, times_used, avg_score, last_used_at)
        VALUES (@prompt_id, @style, 1.0 + @score, 1.0 + (1.0 - @score), 1, @score, @now)
        ON CONFLICT(prompt_id, style) DO UPDATE SET
          alpha = alpha + @score,
          beta = beta + (1.0 - @score),
          times_used = times_used + 1,
          avg_score = (avg_score * times_used + @score) / (times_used + 1),
          last_used_at = @now
      `),
      getStyleThompsonParams: this.db.prepare(`
        SELECT ps.prompt_id as id, p.category, ps.alpha, ps.beta
        FROM prompt_style_stats ps
        JOIN prompts p ON p.id = ps.prompt_id
        WHERE ps.style = ? AND p.retired_at IS NULL
      `),
      getStyleLeaderboard: this.db.prepare(`
        SELECT ps.prompt_id as id, p.category, p.prompt_text, ps.avg_score, ps.times_used, ps.alpha, ps.beta
        FROM prompt_style_stats ps
        JOIN prompts p ON p.id = ps.prompt_id
        WHERE ps.style = ? AND p.retired_at IS NULL
        ORDER BY ps.avg_score DESC
      `),

      // Score queries
      getScoresForPrompt: this.db.prepare('SELECT * FROM prompt_scores WHERE prompt_id = ? ORDER BY scored_at DESC LIMIT ?'),
      getRecentScores: this.db.prepare('SELECT * FROM prompt_scores ORDER BY scored_at DESC LIMIT ?'),
      getThompsonParams: this.db.prepare('SELECT id, category, alpha, beta FROM prompts WHERE retired_at IS NULL'),
      getLeaderboard: this.db.prepare('SELECT id, category, prompt_text, avg_score, times_used, alpha, beta, author, parent_id FROM prompts WHERE retired_at IS NULL ORDER BY avg_score DESC'),

      getCategoryStats: this.db.prepare(`
        SELECT category,
          COUNT(*) as prompt_count,
          SUM(times_used) as total_uses,
          AVG(CASE WHEN times_used > 0 THEN avg_score ELSE NULL END) as category_avg_score,
          AVG(alpha / (alpha + beta)) as category_expected_value
        FROM prompts WHERE retired_at IS NULL
        GROUP BY category
        ORDER BY category_avg_score DESC
      `),

      // Mutation performance comparison
      getMutationPerformance: this.db.prepare(`
        SELECT
          author,
          COUNT(*) as prompt_count,
          AVG(CASE WHEN times_used > 0 THEN avg_score ELSE NULL END) as avg_score,
          SUM(times_used) as total_uses
        FROM prompts WHERE retired_at IS NULL AND times_used > 0
        GROUP BY author
      `),

      // Evaluation sessions
      createEvalSession: this.db.prepare(`
        INSERT INTO evaluation_sessions (id, style, started_at, stop_reason)
        VALUES (@id, @style, @started_at, @stop_reason)
      `),
      completeEvalSession: this.db.prepare(`
        UPDATE evaluation_sessions SET
          evaluated_at = @evaluated_at, eval_duration_ms = @eval_duration_ms,
          eval_tokens_used = @eval_tokens_used, eval_summary = @eval_summary,
          prompts_scored = @prompts_scored
        WHERE id = @id
      `),

      // Meta params
      getMetaParam: this.db.prepare('SELECT value_real, value_text FROM meta_params WHERE key = ?'),
      setMetaParamReal: this.db.prepare(`
        INSERT INTO meta_params (key, value_real, updated_at) VALUES (@key, @value, @now)
        ON CONFLICT(key) DO UPDATE SET value_real = @value, updated_at = @now
      `),
      setMetaParamText: this.db.prepare(`
        INSERT INTO meta_params (key, value_text, updated_at) VALUES (@key, @value, @now)
        ON CONFLICT(key) DO UPDATE SET value_text = @value, updated_at = @now
      `),

      // Stats
      countScores: this.db.prepare('SELECT COUNT(*) FROM prompt_scores').pluck(),
      countSessions: this.db.prepare('SELECT COUNT(*) FROM evaluation_sessions').pluck(),
      avgOverallScore: this.db.prepare('SELECT AVG(overall_score) FROM prompt_scores').pluck(),

      // Cleanup
      pruneScores: this.db.prepare('DELETE FROM prompt_scores WHERE scored_at < ?'),
      pruneSessions: this.db.prepare('DELETE FROM evaluation_sessions WHERE started_at < ?'),

      // Corpus prompts
      seedCorpusPrompt: this.db.prepare(`
        INSERT INTO corpus_prompts (id, category, identity, approach, style, author, created_at)
        VALUES (@id, @category, @identity, @approach, @style, @author, @created_at)
        ON CONFLICT(id) DO UPDATE SET
          category = @category, identity = @identity, approach = @approach, style = @style
      `),
      getCorpusPrompt: this.db.prepare('SELECT * FROM corpus_prompts WHERE id = ?'),
      getCorpusPromptsByStyle: this.db.prepare('SELECT * FROM corpus_prompts WHERE style = ? AND retired_at IS NULL ORDER BY avg_score DESC'),
      getAllCorpusPrompts: this.db.prepare('SELECT * FROM corpus_prompts WHERE retired_at IS NULL ORDER BY avg_score DESC'),
      getCassiCorpusPromptCount: this.db.prepare("SELECT COUNT(*) FROM corpus_prompts WHERE author = 'cassi' AND retired_at IS NULL").pluck(),
      insertCorpusMutation: this.db.prepare(`
        INSERT INTO corpus_prompts (id, category, identity, approach, style, author, parent_id, created_at)
        VALUES (@id, @category, @identity, @approach, @style, 'cassi', @parent_id, @created_at)
      `),
      retireCorpusPrompt: this.db.prepare('UPDATE corpus_prompts SET retired_at = ? WHERE id = ?'),
      insertCorpusScore: this.db.prepare(`
        INSERT INTO corpus_prompt_scores
          (session_id, corpus_prompt_id, style, insight_quality, tool_diversity, depth, self_reflection, overall_score, evaluation_text, scored_at)
        VALUES (@session_id, @corpus_prompt_id, @style, @insight_quality, @tool_diversity, @depth, @self_reflection, @overall_score, @evaluation_text, @scored_at)
      `),
      updateCorpusPromptAggregates: this.db.prepare(`
        UPDATE corpus_prompts SET
          alpha = alpha + @score,
          beta = beta + (1.0 - @score),
          times_used = times_used + 1,
          avg_score = (avg_score * times_used + @score) / (times_used + 1),
          last_used_at = @now
        WHERE id = @id
      `),
      getCorpusThompsonParams: this.db.prepare('SELECT id, category, style, alpha, beta FROM corpus_prompts WHERE retired_at IS NULL'),
      getCorpusLeaderboard: this.db.prepare('SELECT id, category, identity, approach, style, avg_score, times_used, alpha, beta, author, parent_id FROM corpus_prompts WHERE retired_at IS NULL ORDER BY avg_score DESC'),
      getCorpusScoresForPrompt: this.db.prepare('SELECT * FROM corpus_prompt_scores WHERE corpus_prompt_id = ? ORDER BY scored_at DESC LIMIT ?'),
    }
  }


  // ── Prompt Queries ──────────────────────────────────────────────

  getPrompt(id: string): PromptRow | undefined {
    return this.stmts.getPrompt.get(id) as PromptRow | undefined
  }

  getAllPrompts(): PromptRow[] {
    return this.stmts.getAllPrompts.all() as PromptRow[]
  }

  getPromptsByCategory(category: string): PromptRow[] {
    return this.stmts.getPromptsByCategory.all(category) as PromptRow[]
  }

  getPromptLineage(id: string): PromptRow[] {
    return this.stmts.getPromptLineage.all(id) as PromptRow[]
  }


  // ── Prompt Mutation ─────────────────────────────────────────────

  /**
   * Create a Cassi-authored prompt. Returns false if cap reached.
   */
  createMutatedPrompt(
    id: string,
    content: string,
    category: string,
    parentId: string,
  ): boolean {
    const maxCassi = this.getMetaReal('max_cassi_prompts') ?? 20
    const current = (this.stmts.getCassiPromptCount.get() as number) ?? 0
    if (current >= maxCassi) {
      this.logger.info('[MeditationStore] Cassi prompt cap reached', { current, max: maxCassi })
      return false
    }

    this.stmts.insertMutatedPrompt.run({
      id,
      category,
      prompt_text: content,
      parent_id: parentId,
      created_at: Date.now(),
    })
    return true
  }

  retirePrompt(id: string): void {
    this.stmts.retirePrompt.run(Date.now(), id)
  }

  getCassiPromptCount(): number {
    return (this.stmts.getCassiPromptCount.get() as number) ?? 0
  }


  // ── Score Recording ─────────────────────────────────────────────

  /**
   * Record a score and atomically update global + style-specific Thompson params.
   */
  recordScore(score: PromptScoreInsert): void {
    const now = Date.now()
    const txn = this.db.transaction(() => {
      this.stmts.insertScore.run({
        session_id: score.session_id,
        explorer_name: score.explorer_name,
        prompt_id: score.prompt_id,
        style: score.style,
        exploration_depth: score.exploration_depth ?? null,
        curiosity_signal: score.curiosity_signal ?? null,
        connection_quality: score.connection_quality ?? null,
        overall_score: score.overall_score,
        evaluation_text: score.evaluation_text ?? null,
        step_count: score.step_count ?? null,
        stop_reason: score.stop_reason ?? null,
        scored_at: now,
      })
      // Update global params
      this.stmts.updatePromptAggregates.run({
        id: score.prompt_id,
        score: score.overall_score,
        now,
      })
      // Update style-specific params
      this.stmts.upsertStyleStats.run({
        prompt_id: score.prompt_id,
        style: score.style,
        score: score.overall_score,
        now,
      })
    })
    txn()
  }


  // ── Score Queries ───────────────────────────────────────────────

  getScoresForPrompt(id: string, limit = 20): PromptScoreRow[] {
    return this.stmts.getScoresForPrompt.all(id, limit) as PromptScoreRow[]
  }

  getRecentScores(limit = 20): PromptScoreRow[] {
    return this.stmts.getRecentScores.all(limit) as PromptScoreRow[]
  }

  searchEvaluations(query: string, limit = 20): PromptScoreRow[] {
    try {
      const ids = this.db.prepare(
        'SELECT rowid FROM evaluation_fts WHERE evaluation_text MATCH ? LIMIT ?',
      ).pluck().all(query, limit) as number[]
      if (ids.length === 0) return []
      const placeholders = ids.map(() => '?').join(',')
      return this.db.prepare(
        `SELECT * FROM prompt_scores WHERE id IN (${placeholders}) ORDER BY scored_at DESC`,
      ).all(...ids) as PromptScoreRow[]
    } catch {
      return []
    }
  }


  // ── Thompson Sampling ───────────────────────────────────────────

  getThompsonParams(): Array<{ id: string; category: string; alpha: number; beta: number }> {
    return this.stmts.getThompsonParams.all() as Array<{ id: string; category: string; alpha: number; beta: number }>
  }

  /**
   * Get style-specific Thompson params. Falls back to global if no style data exists.
   */
  getStyleThompsonParams(style: MeditationStyle): Array<{ id: string; category: string; alpha: number; beta: number }> {
    const styleParams = this.stmts.getStyleThompsonParams.all(style) as Array<{ id: string; category: string; alpha: number; beta: number }>
    if (styleParams.length > 0) return styleParams
    return this.getThompsonParams()
  }


  // ── Leaderboard & Stats ─────────────────────────────────────────

  getPromptLeaderboard(): Array<{
    id: string; category: string; prompt_text: string
    avg_score: number; times_used: number; alpha: number; beta: number
    author: string; parent_id: string | null
    expected_value: number; confidence: number
  }> {
    const rows = this.stmts.getLeaderboard.all() as Array<{
      id: string; category: string; prompt_text: string
      avg_score: number; times_used: number; alpha: number; beta: number
      author: string; parent_id: string | null
    }>
    return rows.map(r => ({
      ...r,
      expected_value: r.alpha / (r.alpha + r.beta),
      confidence: 1 / Math.sqrt(r.alpha + r.beta),
    }))
  }

  getStyleLeaderboard(style: MeditationStyle): Array<{
    id: string; category: string; prompt_text: string
    avg_score: number; times_used: number; alpha: number; beta: number
    expected_value: number; confidence: number
  }> {
    const rows = this.stmts.getStyleLeaderboard.all(style) as Array<{
      id: string; category: string; prompt_text: string
      avg_score: number; times_used: number; alpha: number; beta: number
    }>
    return rows.map(r => ({
      ...r,
      expected_value: r.alpha / (r.alpha + r.beta),
      confidence: 1 / Math.sqrt(r.alpha + r.beta),
    }))
  }

  getCategoryStats(): Array<{
    category: string; prompt_count: number; total_uses: number
    category_avg_score: number | null; category_expected_value: number
  }> {
    return this.stmts.getCategoryStats.all() as any[]
  }

  /**
   * Compare mutation (Cassi-authored) vs library prompt performance.
   */
  getMutationPerformance(): Array<{ author: string; prompt_count: number; avg_score: number | null; total_uses: number }> {
    return this.stmts.getMutationPerformance.all() as any[]
  }

  getOverallStats(): {
    totalSessions: number; totalScores: number; avgOverallScore: number
    activePrompts: number; cassiPrompts: number; mutationTemperature: number
  } {
    return {
      totalSessions: (this.stmts.countSessions.get() as number) ?? 0,
      totalScores: (this.stmts.countScores.get() as number) ?? 0,
      avgOverallScore: (this.stmts.avgOverallScore.get() as number) ?? 0,
      activePrompts: (this.stmts.getActivePromptCount.get() as number) ?? 0,
      cassiPrompts: (this.stmts.getCassiPromptCount.get() as number) ?? 0,
      mutationTemperature: this.getMetaReal('mutation_temperature') ?? 0.5,
    }
  }


  // ── Evaluation Sessions ─────────────────────────────────────────

  createEvaluationSession(id: string, style: string, startedAt: number, stopReason: string): void {
    this.stmts.createEvalSession.run({ id, style, started_at: startedAt, stop_reason: stopReason })
  }

  completeEvaluationSession(
    id: string, summary: string, durationMs: number, tokensUsed: number, promptsScored: number,
  ): void {
    this.stmts.completeEvalSession.run({
      id, evaluated_at: Date.now(), eval_duration_ms: durationMs,
      eval_tokens_used: tokensUsed, eval_summary: summary, prompts_scored: promptsScored,
    })
  }


  // ── Meta Parameters ─────────────────────────────────────────────

  getMetaReal(key: string): number | undefined {
    const row = this.stmts.getMetaParam.get(key) as { value_real: number | null; value_text: string | null } | undefined
    return row?.value_real ?? undefined
  }

  getMetaText(key: string): string | undefined {
    const row = this.stmts.getMetaParam.get(key) as { value_real: number | null; value_text: string | null } | undefined
    return row?.value_text ?? undefined
  }

  setMetaReal(key: string, value: number): void {
    this.stmts.setMetaParamReal.run({ key, value, now: Date.now() })
  }

  setMetaText(key: string, value: string): void {
    this.stmts.setMetaParamText.run({ key, value, now: Date.now() })
  }

  getMutationTemperature(): number {
    return this.getMetaReal('mutation_temperature') ?? 0.5
  }

  setMutationTemperature(value: number): void {
    this.setMetaReal('mutation_temperature', Math.max(0, Math.min(1, value)))
  }


  // ── Cleanup ─────────────────────────────────────────────────────

  prune(maxAgeDays: number): number {
    const cutoff = Date.now() - (maxAgeDays * 86_400_000)
    const scores = this.stmts.pruneScores.run(cutoff).changes
    const sessions = this.stmts.pruneSessions.run(cutoff).changes
    return scores + sessions
  }

  close(): void {
    this.db.close()
  }


  // ── Corpus Prompt Library ───────────────────────────────────────

  seedCorpusPrompts(prompts: Array<{ id: string; category: string; identity: string; approach: string; style: MeditationStyle }>): void {
    const now = Date.now()
    const txn = this.db.transaction(() => {
      for (const p of prompts) {
        this.stmts.seedCorpusPrompt.run({
          id: p.id, category: p.category, identity: p.identity,
          approach: p.approach, style: p.style, author: 'library', created_at: now,
        })
      }
    })
    txn()
    this.logger.info('[MeditationStore] Seeded corpus prompts', { count: prompts.length })
  }

  getCorpusPrompt(id: string): CorpusPromptRow | undefined {
    return this.stmts.getCorpusPrompt.get(id) as CorpusPromptRow | undefined
  }

  getCorpusPromptsByStyle(style: MeditationStyle): CorpusPromptRow[] {
    return this.stmts.getCorpusPromptsByStyle.all(style) as CorpusPromptRow[]
  }

  getAllCorpusPrompts(): CorpusPromptRow[] {
    return this.stmts.getAllCorpusPrompts.all() as CorpusPromptRow[]
  }

  getCorpusPromptLeaderboard(): Array<{
    id: string; category: string; identity: string; approach: string; style: string
    avg_score: number; times_used: number; alpha: number; beta: number
    author: string; parent_id: string | null
    expected_value: number; confidence: number
  }> {
    const rows = this.stmts.getCorpusLeaderboard.all() as Array<{
      id: string; category: string; identity: string; approach: string; style: string
      avg_score: number; times_used: number; alpha: number; beta: number
      author: string; parent_id: string | null
    }>
    return rows.map(r => ({
      ...r,
      expected_value: r.alpha / (r.alpha + r.beta),
      confidence: 1 / Math.sqrt(r.alpha + r.beta),
    }))
  }

  getCorpusThompsonParams(style: MeditationStyle): Array<{ id: string; category: string; style: string; alpha: number; beta: number }> {
    return this.stmts.getCorpusThompsonParams.all() as Array<{ id: string; category: string; style: string; alpha: number; beta: number }>
  }

  recordCorpusScore(score: CorpusPromptScoreInsert): void {
    const now = Date.now()
    const txn = this.db.transaction(() => {
      this.stmts.insertCorpusScore.run({
        session_id: score.session_id,
        corpus_prompt_id: score.corpus_prompt_id,
        style: score.style,
        insight_quality: score.insight_quality ?? null,
        tool_diversity: score.tool_diversity ?? null,
        depth: score.depth ?? null,
        self_reflection: score.self_reflection ?? null,
        overall_score: score.overall_score,
        evaluation_text: score.evaluation_text ?? null,
        scored_at: now,
      })
      this.stmts.updateCorpusPromptAggregates.run({
        id: score.corpus_prompt_id,
        score: score.overall_score,
        now,
      })
    })
    txn()
  }

  createCorpusMutation(
    id: string,
    identity: string,
    approach: string,
    category: string,
    style: MeditationStyle,
    parentId: string,
  ): boolean {
    const maxCassi = this.getMetaReal('max_cassi_prompts') ?? 20
    const current = (this.stmts.getCassiCorpusPromptCount.get() as number) ?? 0
    if (current >= maxCassi) {
      this.logger.info('[MeditationStore] Cassi corpus prompt cap reached', { current, max: maxCassi })
      return false
    }
    this.stmts.insertCorpusMutation.run({
      id, category, identity, approach, style, parent_id: parentId, created_at: Date.now(),
    })
    return true
  }

  retireCorpusPrompt(id: string): void {
    this.stmts.retireCorpusPrompt.run(Date.now(), id)
  }

  getCorpusScoresForPrompt(id: string, limit = 20): Array<{ id: number; session_id: string; corpus_prompt_id: string; style: string; overall_score: number; scored_at: number }> {
    return this.stmts.getCorpusScoresForPrompt.all(id, limit) as any[]
  }
}
