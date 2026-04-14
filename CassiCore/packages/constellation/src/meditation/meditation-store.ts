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


const SCHEMA_VERSION = 4


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


const MIGRATE_V3_TO_V4 = `
  -- Complete session persistence for replay capability
  CREATE TABLE IF NOT EXISTS meditation_sessions_full (
    id                TEXT PRIMARY KEY,
    started_at        INTEGER NOT NULL,
    completed_at      INTEGER,
    style             TEXT NOT NULL,
    
    -- Configuration snapshot
    config_snapshot   TEXT NOT NULL,
    
    -- Session metadata
    duration_ms       INTEGER,
    total_steps       INTEGER DEFAULT 0,
    active_explorers  INTEGER DEFAULT 0,
    
    -- Outcome tracking
    stop_reason       TEXT,
    stop_detail       TEXT,
    success_rating    REAL,
    
    -- Resource tracking
    total_tokens_used INTEGER DEFAULT 0,
    peak_memory_mb    REAL,
    
    -- Learning outcomes
    insights_generated INTEGER DEFAULT 0,
    engrams_spiked    INTEGER DEFAULT 0,
    engrams_created   INTEGER DEFAULT 0,
    consolidations    INTEGER DEFAULT 0,
    
    -- Self-awareness summary
    self_awareness_count INTEGER DEFAULT 0,
    
    created_at        INTEGER NOT NULL
  );

  CREATE INDEX IF NOT EXISTS idx_sessions_full_started ON meditation_sessions_full(started_at DESC);
  CREATE INDEX IF NOT EXISTS idx_sessions_full_style ON meditation_sessions_full(style);
  CREATE INDEX IF NOT EXISTS idx_sessions_full_success ON meditation_sessions_full(success_rating DESC);

  -- Complete step recording for session replay
  CREATE TABLE IF NOT EXISTS meditation_steps (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        TEXT NOT NULL,
    helix_id          TEXT NOT NULL,
    step_index        INTEGER NOT NULL,
    
    -- Timestamp tracking
    started_at        INTEGER NOT NULL,
    completed_at      INTEGER,
    duration_ms       INTEGER,
    
    -- Prompt context
    prompt_id         TEXT NOT NULL,
    prompt_category   TEXT NOT NULL,
    
    -- Execution data
    reasoning         TEXT,
    discoveries       TEXT,
    decisions         TEXT,
    hypothesis        TEXT,
    next_steps        TEXT,
    
    -- Tool activity
    tool_calls        TEXT NOT NULL,
    tool_outputs      TEXT,
    
    -- Knowledge tracking
    knowledge_delta   TEXT,
    files_active      TEXT,
    
    -- Annotation data
    annotation        TEXT,
    
    -- Resource usage for this step
    tokens_used       INTEGER DEFAULT 0,
    
    FOREIGN KEY (session_id) REFERENCES meditation_sessions_full(id),
    FOREIGN KEY (prompt_id) REFERENCES prompts(id)
  );

  CREATE INDEX IF NOT EXISTS idx_steps_session ON meditation_steps(session_id);
  CREATE INDEX IF NOT EXISTS idx_steps_helix ON meditation_steps(session_id, helix_id);
  CREATE INDEX IF NOT EXISTS idx_steps_time ON meditation_steps(session_id, started_at DESC);

  -- Self-awareness event persistence
  CREATE TABLE IF NOT EXISTS self_awareness_events (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        TEXT NOT NULL,
    helix_id          TEXT NOT NULL,
    step_index        INTEGER NOT NULL,
    
    -- Detection metadata
    detected_at       INTEGER NOT NULL,
    confidence        REAL NOT NULL,
    
    -- Trigger classification
    trigger_category  TEXT,
    trigger_detail    TEXT,
    
    -- Pattern matching
    pattern_label     TEXT,
    pattern_excerpt   TEXT,
    
    -- Full context
    full_reasoning    TEXT NOT NULL,
    tool_calls        TEXT,
    knowledge_delta   TEXT,
    
    -- File context
    file_path         TEXT,
    file_section      TEXT,
    
    -- Outcome tracking
    acted_on          INTEGER DEFAULT 0,
    action_taken      TEXT,
    
    FOREIGN KEY (session_id) REFERENCES meditation_sessions_full(id)
  );

  CREATE INDEX IF NOT EXISTS idx_selfaware_session ON self_awareness_events(session_id);
  CREATE INDEX IF NOT EXISTS idx_selfaware_confidence ON self_awareness_events(confidence DESC);
  CREATE INDEX IF NOT EXISTS idx_selfaware_pattern ON self_awareness_events(pattern_label);

  -- Dedicated meditation insights storage
  CREATE TABLE IF NOT EXISTS meditation_insights (
    id                TEXT PRIMARY KEY,
    session_id        TEXT NOT NULL,
    
    -- Insight content
    content           TEXT NOT NULL,
    importance        INTEGER NOT NULL DEFAULT 5,
    
    -- Generation context
    generated_at      INTEGER NOT NULL,
    generation_step   INTEGER,
    helix_id          TEXT,
    prompt_id         TEXT,
    
    -- Attribution
    insight_type      TEXT NOT NULL,
    source_tags       TEXT,
    
    -- Quality metrics
    spike_score       REAL,
    consolidation_ref TEXT,
    
    -- Follow-up tracking
    acted_on          INTEGER DEFAULT 0,
    action_session_id TEXT,
    
    FOREIGN KEY (session_id) REFERENCES meditation_sessions_full(id),
    FOREIGN KEY (prompt_id) REFERENCES prompts(id)
  );

  CREATE INDEX IF NOT EXISTS idx_insights_session ON meditation_insights(session_id);
  CREATE INDEX IF NOT EXISTS idx_insights_importance ON meditation_insights(importance DESC);
  CREATE INDEX IF NOT EXISTS idx_insights_type ON meditation_insights(insight_type);

  -- Comprehensive error tracking
  CREATE TABLE IF NOT EXISTS meditation_errors (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        TEXT NOT NULL,
    helix_id          TEXT,
    
    -- Error classification
    error_type        TEXT NOT NULL,
    error_code        TEXT,
    error_message     TEXT NOT NULL,
    
    -- Context at failure
    occurred_at       INTEGER NOT NULL,
    step_index        INTEGER,
    active_prompt_id  TEXT,
    
    -- Diagnostic data
    stack_trace       TEXT,
    tool_call_context TEXT,
    memory_state      TEXT,
    constellation_state TEXT,
    
    -- Recovery attempts
    recovery_attempted INTEGER DEFAULT 0,
    recovery_method   TEXT,
    recovery_success  INTEGER DEFAULT 0,
    
    -- Impact assessment
    session_aborted   INTEGER DEFAULT 0,
    explorers_affected INTEGER DEFAULT 1,
    
    FOREIGN KEY (session_id) REFERENCES meditation_sessions_full(id)
  );

  CREATE INDEX IF NOT EXISTS idx_errors_session ON meditation_errors(session_id);
  CREATE INDEX IF NOT EXISTS idx_errors_type ON meditation_errors(error_type, occurred_at DESC);
  CREATE INDEX IF NOT EXISTS idx_errors_recovery ON meditation_errors(recovery_success);

  -- Resource usage tracking
  CREATE TABLE IF NOT EXISTS meditation_resource_usage (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        TEXT NOT NULL,
    
    -- Time bucket (5-minute intervals)
    time_bucket       INTEGER NOT NULL,
    
    -- Token usage
    tokens_used       INTEGER NOT NULL,
    tokens_by_explorer TEXT,
    
    -- Memory tracking
    memory_peak_mb    REAL,
    memory_avg_mb     REAL,
    
    -- CPU utilization
    cpu_percent_avg   REAL,
    cpu_percent_peak  REAL,
    
    -- API calls
    llm_calls_count   INTEGER DEFAULT 0,
    tool_calls_count  INTEGER DEFAULT 0,
    
    -- Network/activity
    files_read_count  INTEGER DEFAULT 0,
    searches_count    INTEGER DEFAULT 0,
    
    FOREIGN KEY (session_id) REFERENCES meditation_sessions_full(id)
  );

  CREATE INDEX IF NOT EXISTS idx_resource_session ON meditation_resource_usage(session_id);
  CREATE INDEX IF NOT EXISTS idx_resource_time ON meditation_resource_usage(session_id, time_bucket);

  -- ── Phase 2: Enhanced Session Tracking ──────────────────────────────
  
  -- Configuration history tracking
  CREATE TABLE IF NOT EXISTS meditation_config_history (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        TEXT NOT NULL,
    config_key        TEXT NOT NULL,
    config_value      TEXT NOT NULL,
    changed_at        INTEGER NOT NULL,
    
    FOREIGN KEY (session_id) REFERENCES meditation_sessions_full(id)
  );

  CREATE INDEX IF NOT EXISTS idx_config_history_session ON meditation_config_history(session_id);
  CREATE INDEX IF NOT EXISTS idx_config_history_key ON meditation_config_history(config_key, changed_at DESC);

  -- Prompt assignment tracking
  CREATE TABLE IF NOT EXISTS session_prompt_assignments (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        TEXT NOT NULL,
    helix_id          TEXT NOT NULL,
    explorer_name     TEXT NOT NULL,
    prompt_id         TEXT NOT NULL,
    prompt_category   TEXT NOT NULL,
    
    -- Assignment context
    assigned_at       INTEGER NOT NULL,
    assignment_reason TEXT,
    
    -- Outcome metrics
    steps_taken       INTEGER DEFAULT 0,
    discoveries_count INTEGER DEFAULT 0,
    tokens_used       INTEGER DEFAULT 0,
    final_score       REAL,
    
    FOREIGN KEY (session_id) REFERENCES meditation_sessions_full(id),
    FOREIGN KEY (prompt_id) REFERENCES prompts(id)
  );

  CREATE INDEX IF NOT EXISTS idx_assignments_session ON session_prompt_assignments(session_id);
  CREATE INDEX IF NOT EXISTS idx_assignments_prompt ON session_prompt_assignments(prompt_id);
  CREATE INDEX IF NOT EXISTS idx_assignments_helix ON session_prompt_assignments(session_id, helix_id);
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


// ── Phase 1: Complete Session & Step Persistence ───────────────

export interface SessionFullInsert {
  id: string
  started_at: number
  style: string
  config_snapshot: string
}

export interface SessionFullRow extends SessionFullInsert {
  completed_at: number | null
  duration_ms: number | null
  total_steps: number
  active_explorers: number
  stop_reason: string | null
  stop_detail: string | null
  success_rating: number | null
  total_tokens_used: number
  peak_memory_mb: number | null
  insights_generated: number
  engrams_spiked: number
  engrams_created: number
  consolidations: number
  self_awareness_count: number
  created_at: number
}

export interface SessionCompletionUpdate {
  id: string
  completed_at: number
  duration_ms: number
  total_steps: number
  active_explorers: number
  stop_reason: string
  stop_detail?: string
  success_rating?: number
  total_tokens_used: number
  peak_memory_mb?: number
  insights_generated: number
  engrams_spiked: number
  engrams_created: number
  consolidations: number
  self_awareness_count: number
}

export interface StepInsert {
  session_id: string
  helix_id: string
  step_index: number
  started_at: number
  prompt_id: string
  prompt_category: string
  tool_calls: string
}

export interface StepRow extends StepInsert {
  id: number
  completed_at: number | null
  duration_ms: number | null
  reasoning: string | null
  discoveries: string | null
  decisions: string | null
  hypothesis: string | null
  next_steps: string | null
  tool_outputs: string | null
  knowledge_delta: string | null
  files_active: string | null
  annotation: string | null
  tokens_used: number
}

export interface SelfAwarenessEventInsert {
  session_id: string
  helix_id: string
  step_index: number
  detected_at: number
  confidence: number
  full_reasoning: string
}

export interface SelfAwarenessEventRow extends SelfAwarenessEventInsert {
  id: number
  trigger_category: string | null
  trigger_detail: string | null
  pattern_label: string | null
  pattern_excerpt: string | null
  tool_calls: string | null
  knowledge_delta: string | null
  file_path: string | null
  file_section: string | null
  acted_on: number
  action_taken: string | null
}

export interface MeditationInsightInsert {
  id: string
  session_id: string
  content: string
  importance: number
  generated_at: number
  insight_type: string
}

export interface MeditationInsightRow extends MeditationInsightInsert {
  generation_step: number | null
  helix_id: string | null
  prompt_id: string | null
  source_tags: string | null
  spike_score: number | null
  consolidation_ref: string | null
  acted_on: number
  action_session_id: string | null
}

export interface MeditationErrorInsert {
  session_id: string
  error_type: string
  error_message: string
  occurred_at: number
}

export interface MeditationErrorRow extends MeditationErrorInsert {
  id: number
  helix_id: string | null
  error_code: string | null
  step_index: number | null
  active_prompt_id: string | null
  stack_trace: string | null
  tool_call_context: string | null
  memory_state: string | null
  constellation_state: string | null
  recovery_attempted: number
  recovery_method: string | null
  recovery_success: number
  session_aborted: number
  explorers_affected: number
}

export interface ResourceUsageInsert {
  session_id: string
  time_bucket: number
  tokens_used: number
}

export interface ResourceUsageRow extends ResourceUsageInsert {
  id: number
  tokens_by_explorer: string | null
  memory_peak_mb: number | null
  memory_avg_mb: number | null
  cpu_percent_avg: number | null
  cpu_percent_peak: number | null
  llm_calls_count: number
  tool_calls_count: number
  files_read_count: number
  searches_count: number
}


// ── Phase 2: Enhanced Session Tracking ───────────────────────────────

export interface ConfigHistoryInsert {
  session_id: string
  config_key: string
  config_value: string
  changed_at: number
}

export interface ConfigHistoryRow extends ConfigHistoryInsert {
  id: number
}

export interface PromptAssignmentInsert {
  session_id: string
  helix_id: string
  explorer_name: string
  prompt_id: string
  prompt_category: string
  assigned_at: number
}

export interface PromptAssignmentRow extends PromptAssignmentInsert {
  id: number
  assignment_reason: string | null
  steps_taken: number
  discoveries_count: number
  tokens_used: number
  final_score: number | null
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
      db.exec(MIGRATE_V3_TO_V4)
      db.prepare('INSERT OR REPLACE INTO schema_version (version) VALUES (?)').run(SCHEMA_VERSION)
    } else if (existing < 2) {
      db.exec(MIGRATE_V1_TO_V2)
      db.exec(MIGRATE_V2_TO_V3)
      db.exec(MIGRATE_V3_TO_V4)
      db.prepare('INSERT OR REPLACE INTO schema_version (version) VALUES (?)').run(SCHEMA_VERSION)
    } else if (existing < 3) {
      db.exec(MIGRATE_V2_TO_V3)
      db.exec(MIGRATE_V3_TO_V4)
      db.prepare('INSERT OR REPLACE INTO schema_version (version) VALUES (?)').run(SCHEMA_VERSION)
    } else if (existing < 4) {
      db.exec(MIGRATE_V3_TO_V4)
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
      
      // ── Phase 1: Complete Session Persistence ────────────────────
      
      // Session lifecycle
      insertSessionFull: this.db.prepare(`
        INSERT INTO meditation_sessions_full
          (id, started_at, style, config_snapshot, created_at)
        VALUES (@id, @started_at, @style, @config_snapshot, @created_at)
      `),
      completeSessionFull: this.db.prepare(`
        UPDATE meditation_sessions_full SET
          completed_at = @completed_at,
          duration_ms = @duration_ms,
          total_steps = @total_steps,
          active_explorers = @active_explorers,
          stop_reason = @stop_reason,
          stop_detail = @stop_detail,
          success_rating = @success_rating,
          total_tokens_used = @total_tokens_used,
          peak_memory_mb = @peak_memory_mb,
          insights_generated = @insights_generated,
          engrams_spiked = @engrams_spiked,
          engrams_created = @engrams_created,
          consolidations = @consolidations,
          self_awareness_count = @self_awareness_count
        WHERE id = @id
      `),
      getSessionFull: this.db.prepare('SELECT * FROM meditation_sessions_full WHERE id = ?'),
      getRecentSessionsFull: this.db.prepare('SELECT * FROM meditation_sessions_full ORDER BY started_at DESC LIMIT ?'),
      getSessionsByStyle: this.db.prepare('SELECT * FROM meditation_sessions_full WHERE style = ? ORDER BY started_at DESC LIMIT ?'),
      countSessionsFull: this.db.prepare('SELECT COUNT(*) FROM meditation_sessions_full').pluck(),
      
      // Step recording
      insertStep: this.db.prepare(`
        INSERT INTO meditation_steps
          (session_id, helix_id, step_index, started_at, prompt_id, prompt_category, tool_calls)
        VALUES (@session_id, @helix_id, @step_index, @started_at, @prompt_id, @prompt_category, @tool_calls)
      `),
      completeStep: this.db.prepare(`
        UPDATE meditation_steps SET
          completed_at = @completed_at,
          duration_ms = @duration_ms,
          reasoning = @reasoning,
          discoveries = @discoveries,
          decisions = @decisions,
          hypothesis = @hypothesis,
          next_steps = @next_steps,
          tool_outputs = @tool_outputs,
          knowledge_delta = @knowledge_delta,
          files_active = @files_active,
          annotation = @annotation,
          tokens_used = @tokens_used
        WHERE session_id = @session_id AND helix_id = @helix_id AND step_index = @step_index
      `),
      getStepsForSession: this.db.prepare('SELECT * FROM meditation_steps WHERE session_id = ? ORDER BY started_at ASC'),
      getStepsForHelix: this.db.prepare('SELECT * FROM meditation_steps WHERE session_id = ? AND helix_id = ? ORDER BY step_index ASC'),
      countStepsForSession: this.db.prepare('SELECT COUNT(*) FROM meditation_steps WHERE session_id = ?').pluck(),
      
      // Self-awareness events
      insertSelfAwarenessEvent: this.db.prepare(`
        INSERT INTO self_awareness_events
          (session_id, helix_id, step_index, detected_at, confidence, full_reasoning,
           trigger_category, trigger_detail, pattern_label, pattern_excerpt,
           tool_calls, knowledge_delta, file_path, file_section)
        VALUES (@session_id, @helix_id, @step_index, @detected_at, @confidence, @full_reasoning,
                @trigger_category, @trigger_detail, @pattern_label, @pattern_excerpt,
                @tool_calls, @knowledge_delta, @file_path, @file_section)
      `),
      getSelfAwarenessForSession: this.db.prepare('SELECT * FROM self_awareness_events WHERE session_id = ? ORDER BY detected_at ASC'),
      countSelfAwarenessForSession: this.db.prepare('SELECT COUNT(*) FROM self_awareness_events WHERE session_id = ?').pluck(),
      
      // Meditation insights
      insertMeditationInsight: this.db.prepare(`
        INSERT INTO meditation_insights
          (id, session_id, content, importance, generated_at, insight_type,
           generation_step, helix_id, prompt_id, source_tags)
        VALUES (@id, @session_id, @content, @importance, @generated_at, @insight_type,
                @generation_step, @helix_id, @prompt_id, @source_tags)
      `),
      getInsightsForSession: this.db.prepare('SELECT * FROM meditation_insights WHERE session_id = ? ORDER BY importance DESC, generated_at DESC'),
      getRecentInsights: this.db.prepare('SELECT * FROM meditation_insights ORDER BY generated_at DESC LIMIT ?'),
      countInsightsForSession: this.db.prepare('SELECT COUNT(*) FROM meditation_insights WHERE session_id = ?').pluck(),
      
      // Error tracking
      insertError: this.db.prepare(`
        INSERT INTO meditation_errors
          (session_id, helix_id, error_type, error_code, error_message, occurred_at,
           step_index, active_prompt_id, stack_trace, tool_call_context,
           memory_state, constellation_state)
        VALUES (@session_id, @helix_id, @error_type, @error_code, @error_message, @occurred_at,
                @step_index, @active_prompt_id, @stack_trace, @tool_call_context,
                @memory_state, @constellation_state)
      `),
      getErrorsForSession: this.db.prepare('SELECT * FROM meditation_errors WHERE session_id = ? ORDER BY occurred_at ASC'),
      getErrorsByType: this.db.prepare('SELECT * FROM meditation_errors WHERE error_type = ? ORDER BY occurred_at DESC LIMIT ?'),
      countErrorsForSession: this.db.prepare('SELECT COUNT(*) FROM meditation_errors WHERE session_id = ?').pluck(),
      
      // Resource usage
      insertResourceSample: this.db.prepare(`
        INSERT INTO meditation_resource_usage
          (session_id, time_bucket, tokens_used, tokens_by_explorer,
           memory_peak_mb, memory_avg_mb, cpu_percent_avg, cpu_percent_peak,
           llm_calls_count, tool_calls_count, files_read_count, searches_count)
        VALUES (@session_id, @time_bucket, @tokens_used, @tokens_by_explorer,
                @memory_peak_mb, @memory_avg_mb, @cpu_percent_avg, @cpu_percent_peak,
                @llm_calls_count, @tool_calls_count, @files_read_count, @searches_count)
      `),
      getResourceTimeline: this.db.prepare('SELECT * FROM meditation_resource_usage WHERE session_id = ? ORDER BY time_bucket ASC'),
      
      // ── Phase 2: Enhanced Session Tracking ────────────────────────
      
      // Config history
      insertConfigHistory: this.db.prepare(`
        INSERT INTO meditation_config_history
          (session_id, config_key, config_value, changed_at)
        VALUES (@session_id, @config_key, @config_value, @changed_at)
      `),
      getConfigHistoryForSession: this.db.prepare('SELECT * FROM meditation_config_history WHERE session_id = ? ORDER BY changed_at ASC'),
      getConfigHistoryByKey: this.db.prepare('SELECT * FROM meditation_config_history WHERE config_key = ? ORDER BY changed_at DESC LIMIT ?'),
      
      // Prompt assignments
      insertPromptAssignment: this.db.prepare(`
        INSERT INTO session_prompt_assignments
          (session_id, helix_id, explorer_name, prompt_id, prompt_category, assigned_at, assignment_reason)
        VALUES (@session_id, @helix_id, @explorer_name, @prompt_id, @prompt_category, @assigned_at, @assignment_reason)
      `),
      updatePromptAssignmentOutcome: this.db.prepare(`
        UPDATE session_prompt_assignments SET
          steps_taken = @steps_taken,
          discoveries_count = @discoveries_count,
          tokens_used = @tokens_used,
          final_score = @final_score
        WHERE session_id = @session_id AND helix_id = @helix_id
      `),
      getPromptAssignmentsForSession: this.db.prepare('SELECT * FROM session_prompt_assignments WHERE session_id = ?'),
      getPromptAssignmentsByPrompt: this.db.prepare('SELECT * FROM session_prompt_assignments WHERE prompt_id = ? ORDER BY assigned_at DESC LIMIT ?'),
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


  // ── Phase 1: Complete Session Persistence ──────────────────────────

  /**
   * Record the start of a meditation session with full configuration snapshot.
   */
  recordSessionStart(session: SessionFullInsert): void {
    const now = Date.now()
    this.stmts.insertSessionFull.run({
      id: session.id,
      started_at: session.started_at,
      style: session.style,
      config_snapshot: session.config_snapshot,
      created_at: now,
    })
  }

  /**
   * Record session completion with full outcome data.
   */
  recordSessionCompletion(completion: SessionCompletionUpdate): void {
    this.stmts.completeSessionFull.run({
      id: completion.id,
      completed_at: completion.completed_at,
      duration_ms: completion.duration_ms,
      total_steps: completion.total_steps,
      active_explorers: completion.active_explorers,
      stop_reason: completion.stop_reason,
      stop_detail: completion.stop_detail ?? null,
      success_rating: completion.success_rating ?? null,
      total_tokens_used: completion.total_tokens_used,
      peak_memory_mb: completion.peak_memory_mb ?? null,
      insights_generated: completion.insights_generated,
      engrams_spiked: completion.engrams_spiked,
      engrams_created: completion.engrams_created,
      consolidations: completion.consolidations,
      self_awareness_count: completion.self_awareness_count,
    })
  }

  /**
   * Get a complete session record by ID.
   */
  getSessionFull(id: string): SessionFullRow | undefined {
    return this.stmts.getSessionFull.get(id) as SessionFullRow | undefined
  }

  /**
   * Get recent meditation sessions.
   */
  getRecentSessionsFull(limit = 20): SessionFullRow[] {
    return this.stmts.getRecentSessionsFull.all(limit) as SessionFullRow[]
  }

  /**
   * Get sessions by style.
   */
  getSessionsByStyle(style: string, limit = 20): SessionFullRow[] {
    return this.stmts.getSessionsByStyle.all(style, limit) as SessionFullRow[]
  }

  /**
   * Count total meditation sessions.
   */
  countSessionsFull(): number {
    return (this.stmts.countSessionsFull.get() as number) ?? 0
  }


  // ── Step Recording ──────────────────────────────────────────────────

  /**
   * Record the start of a meditation step.
   */
  recordStepStart(step: StepInsert): void {
    this.stmts.insertStep.run({
      session_id: step.session_id,
      helix_id: step.helix_id,
      step_index: step.step_index,
      started_at: step.started_at,
      prompt_id: step.prompt_id,
      prompt_category: step.prompt_category,
      tool_calls: step.tool_calls,
    })
  }

  /**
   * Record step completion with full execution context.
   */
  recordStepCompletion(
    sessionId: string,
    helixId: string,
    stepIndex: number,
    completion: {
      completed_at: number
      duration_ms: number
      reasoning?: string
      discoveries?: string
      decisions?: string
      hypothesis?: string
      next_steps?: string
      tool_outputs?: string
      knowledge_delta?: string
      files_active?: string
      annotation?: string
      tokens_used: number
    },
  ): void {
    this.stmts.completeStep.run({
      session_id: sessionId,
      helix_id: helixId,
      step_index: stepIndex,
      completed_at: completion.completed_at,
      duration_ms: completion.duration_ms,
      reasoning: completion.reasoning ?? null,
      discoveries: completion.discoveries ?? null,
      decisions: completion.decisions ?? null,
      hypothesis: completion.hypothesis ?? null,
      next_steps: completion.next_steps ?? null,
      tool_outputs: completion.tool_outputs ?? null,
      knowledge_delta: completion.knowledge_delta ?? null,
      files_active: completion.files_active ?? null,
      annotation: completion.annotation ?? null,
      tokens_used: completion.tokens_used,
    })
  }

  /**
   * Get all steps for a session (for replay).
   */
  getStepsForSession(sessionId: string): StepRow[] {
    return this.stmts.getStepsForSession.all(sessionId) as StepRow[]
  }

  /**
   * Get steps for a specific helix branch.
   */
  getStepsForHelix(sessionId: string, helixId: string): StepRow[] {
    return this.stmts.getStepsForHelix.all(sessionId, helixId) as StepRow[]
  }

  /**
   * Count steps in a session.
   */
  countStepsForSession(sessionId: string): number {
    return (this.stmts.countStepsForSession.get(sessionId) as number) ?? 0
  }


  // ── Self-Awareness Events ────────────────────────────────────────────

  /**
   * Record a self-awareness detection event.
   */
  recordSelfAwarenessEvent(event: SelfAwarenessEventInsert & {
    trigger_category?: string
    trigger_detail?: string
    pattern_label?: string
    pattern_excerpt?: string
    tool_calls?: string
    knowledge_delta?: string
    file_path?: string
    file_section?: string
  }): void {
    this.stmts.insertSelfAwarenessEvent.run({
      session_id: event.session_id,
      helix_id: event.helix_id,
      step_index: event.step_index,
      detected_at: event.detected_at,
      confidence: event.confidence,
      full_reasoning: event.full_reasoning,
      trigger_category: event.trigger_category ?? null,
      trigger_detail: event.trigger_detail ?? null,
      pattern_label: event.pattern_label ?? null,
      pattern_excerpt: event.pattern_excerpt ?? null,
      tool_calls: event.tool_calls ?? null,
      knowledge_delta: event.knowledge_delta ?? null,
      file_path: event.file_path ?? null,
      file_section: event.file_section ?? null,
    })
  }

  /**
   * Get all self-awareness events for a session.
   */
  getSelfAwarenessForSession(sessionId: string): SelfAwarenessEventRow[] {
    return this.stmts.getSelfAwarenessForSession.all(sessionId) as SelfAwarenessEventRow[]
  }

  /**
   * Count self-awareness events in a session.
   */
  countSelfAwarenessForSession(sessionId: string): number {
    return (this.stmts.countSelfAwarenessForSession.get(sessionId) as number) ?? 0
  }


  // ── Meditation Insights ──────────────────────────────────────────────

  /**
   * Record a meditation-generated insight.
   */
  recordMeditationInsight(insight: MeditationInsightInsert & {
    generation_step?: number
    helix_id?: string
    prompt_id?: string
    source_tags?: string
  }): void {
    this.stmts.insertMeditationInsight.run({
      id: insight.id,
      session_id: insight.session_id,
      content: insight.content,
      importance: insight.importance,
      generated_at: insight.generated_at,
      insight_type: insight.insight_type,
      generation_step: insight.generation_step ?? null,
      helix_id: insight.helix_id ?? null,
      prompt_id: insight.prompt_id ?? null,
      source_tags: insight.source_tags ?? null,
    })
  }

  /**
   * Get insights for a session.
   */
  getInsightsForSession(sessionId: string): MeditationInsightRow[] {
    return this.stmts.getInsightsForSession.all(sessionId) as MeditationInsightRow[]
  }

  /**
   * Get recent meditation insights across all sessions.
   */
  getRecentMeditationInsights(limit = 20): MeditationInsightRow[] {
    return this.stmts.getRecentInsights.all(limit) as MeditationInsightRow[]
  }

  /**
   * Count insights in a session.
   */
  countInsightsForSession(sessionId: string): number {
    return (this.stmts.countInsightsForSession.get(sessionId) as number) ?? 0
  }


  // ── Error Tracking ────────────────────────────────────────────────────

  /**
   * Record a meditation error with full diagnostic context.
   */
  recordError(error: MeditationErrorInsert & {
    helix_id?: string
    error_code?: string
    step_index?: number
    active_prompt_id?: string
    stack_trace?: string
    tool_call_context?: string
    memory_state?: string
    constellation_state?: string
  }): void {
    this.stmts.insertError.run({
      session_id: error.session_id,
      helix_id: error.helix_id ?? null,
      error_type: error.error_type,
      error_code: error.error_code ?? null,
      error_message: error.error_message,
      occurred_at: error.occurred_at,
      step_index: error.step_index ?? null,
      active_prompt_id: error.active_prompt_id ?? null,
      stack_trace: error.stack_trace ?? null,
      tool_call_context: error.tool_call_context ?? null,
      memory_state: error.memory_state ?? null,
      constellation_state: error.constellation_state ?? null,
    })
  }

  /**
   * Get errors for a session.
   */
  getErrorsForSession(sessionId: string): MeditationErrorRow[] {
    return this.stmts.getErrorsForSession.all(sessionId) as MeditationErrorRow[]
  }

  /**
   * Get errors by type across all sessions.
   */
  getErrorsByType(errorType: string, limit = 20): MeditationErrorRow[] {
    return this.stmts.getErrorsByType.all(errorType, limit) as MeditationErrorRow[]
  }

  /**
   * Count errors in a session.
   */
  countErrorsForSession(sessionId: string): number {
    return (this.stmts.countErrorsForSession.get(sessionId) as number) ?? 0
  }


  // ── Resource Usage Tracking ───────────────────────────────────────────

  /**
   * Record a resource usage sample (5-minute bucket).
   */
  recordResourceSample(sample: ResourceUsageInsert & {
    tokens_by_explorer?: string
    memory_peak_mb?: number
    memory_avg_mb?: number
    cpu_percent_avg?: number
    cpu_percent_peak?: number
    llm_calls_count?: number
    tool_calls_count?: number
    files_read_count?: number
    searches_count?: number
  }): void {
    this.stmts.insertResourceSample.run({
      session_id: sample.session_id,
      time_bucket: sample.time_bucket,
      tokens_used: sample.tokens_used,
      tokens_by_explorer: sample.tokens_by_explorer ?? null,
      memory_peak_mb: sample.memory_peak_mb ?? null,
      memory_avg_mb: sample.memory_avg_mb ?? null,
      cpu_percent_avg: sample.cpu_percent_avg ?? null,
      cpu_percent_peak: sample.cpu_percent_peak ?? null,
      llm_calls_count: sample.llm_calls_count ?? 0,
      tool_calls_count: sample.tool_calls_count ?? 0,
      files_read_count: sample.files_read_count ?? 0,
      searches_count: sample.searches_count ?? 0,
    })
  }

  /**
   * Get resource usage timeline for a session.
   */
  getResourceTimeline(sessionId: string): ResourceUsageRow[] {
    return this.stmts.getResourceTimeline.all(sessionId) as ResourceUsageRow[]
  }


  // ── Phase 2: Enhanced Session Tracking ───────────────────────────────

  /**
   * Record a configuration value for historical tracking.
   */
  recordConfigHistory(config: ConfigHistoryInsert): void {
    this.stmts.insertConfigHistory.run({
      session_id: config.session_id,
      config_key: config.config_key,
      config_value: config.config_value,
      changed_at: config.changed_at,
    })
  }

  /**
   * Get all configuration history for a session.
   */
  getConfigHistoryForSession(sessionId: string): ConfigHistoryRow[] {
    return this.stmts.getConfigHistoryForSession.all(sessionId) as ConfigHistoryRow[]
  }

  /**
   * Get configuration history for a specific key across all sessions.
   */
  getConfigHistoryByKey(configKey: string, limit = 50): ConfigHistoryRow[] {
    return this.stmts.getConfigHistoryByKey.all(configKey, limit) as ConfigHistoryRow[]
  }

  /**
   * Record a prompt assignment to an explorer.
   */
  recordPromptAssignment(assignment: PromptAssignmentInsert & {
    assignment_reason?: string
  }): void {
    this.stmts.insertPromptAssignment.run({
      session_id: assignment.session_id,
      helix_id: assignment.helix_id,
      explorer_name: assignment.explorer_name,
      prompt_id: assignment.prompt_id,
      prompt_category: assignment.prompt_category,
      assigned_at: assignment.assigned_at,
      assignment_reason: assignment.assignment_reason ?? null,
    })
  }

  /**
   * Update prompt assignment outcome after session completion.
   */
  updatePromptAssignmentOutcome(
    sessionId: string,
    helixId: string,
    outcome: {
      steps_taken: number
      discoveries_count: number
      tokens_used: number
      final_score?: number
    },
  ): void {
    this.stmts.updatePromptAssignmentOutcome.run({
      session_id: sessionId,
      helix_id: helixId,
      steps_taken: outcome.steps_taken,
      discoveries_count: outcome.discoveries_count,
      tokens_used: outcome.tokens_used,
      final_score: outcome.final_score ?? null,
    })
  }

  /**
   * Get all prompt assignments for a session.
   */
  getPromptAssignmentsForSession(sessionId: string): PromptAssignmentRow[] {
    return this.stmts.getPromptAssignmentsForSession.all(sessionId) as PromptAssignmentRow[]
  }

  /**
   * Get prompt assignments by prompt ID across sessions.
   */
  getPromptAssignmentsByPrompt(promptId: string, limit = 50): PromptAssignmentRow[] {
    return this.stmts.getPromptAssignmentsByPrompt.all(promptId, limit) as PromptAssignmentRow[]
  }
}
