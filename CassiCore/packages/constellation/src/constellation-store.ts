/**
 * ConstellationStore — SQLite-backed persistence for Constellation sessions.
 *
 * Lives at ~/.cassicore/data/constellation.db (separate from helix.db)
 * Persists Constellation session state, branch data, and events.
 *
 * Design:
 *   - constellation_sessions table: one row per Constellation (goal, tree snapshot, metrics)
 *   - constellation_branches table: one row per Helix branch (goal, status, assessments)
 *   - constellation_events table: append-only audit log per session
 *
 * Pattern follows HelixStore (core/intelligence/helix/helix-store.ts) —
 * WAL mode, JSON blobs for nested state, minimal schema normalization.
 *
 * Key differences from HelixStore:
 *   - Retention default: 180 days (configurable) vs Helix's 7 days
 *   - Tree snapshot captured only on completion (training warehouse stores iterations)
 *   - Branches table tracks the Helix tree structure
 */

import fs from 'node:fs'
import path from 'node:path'

import Database from 'better-sqlite3'

import type { ILogger } from '../../../types/interfaces.js'
import type { CorpusTreeSnapshot, BranchAssessment, CrossHelixPattern, CorpusIntervention } from './corpus-types.js'
import type { ConstellationResult, SpawnRequest } from './types.js'
import { getDataDir } from '../../utils/paths.js'


const SCHEMA_VERSION = 2  // Incremented for new tables
const DEFAULT_MAX_AGE_DAYS = 180  // Much longer retention than Helix's 7 days


const SCHEMA_SQL = `
  CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);

  CREATE TABLE IF NOT EXISTS constellation_sessions (
    id                      TEXT PRIMARY KEY,
    goal                    TEXT NOT NULL,
    context                 TEXT,
    status                  TEXT NOT NULL DEFAULT 'running',
    template                TEXT,

    -- Tree snapshot (captured on completion)
    tree_snapshot_json      TEXT,
    progress_snapshot_json  TEXT,

    -- Corpus analysis outputs
    branch_assessments_json TEXT DEFAULT '[]',
    spawn_decisions_json    TEXT DEFAULT '[]',
    cross_patterns_json     TEXT DEFAULT '[]',
    interventions_json      TEXT DEFAULT '[]',
    sweep_count             INTEGER DEFAULT 0,

    -- Configuration
    helix_session_ids_json  TEXT DEFAULT '[]',
    max_helixes             INTEGER,
    max_depth               INTEGER,
    timeout_ms              INTEGER,

    -- Metrics
    total_branches          INTEGER DEFAULT 0,
    completed_branches      INTEGER DEFAULT 0,
    failed_branches         INTEGER DEFAULT 0,
    tokens_used             INTEGER DEFAULT 0,
    duration_ms             INTEGER,
    error                   TEXT,

    -- Timestamps
    created_at              INTEGER NOT NULL,
    completed_at            INTEGER
  );

  CREATE TABLE IF NOT EXISTS constellation_branches (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        TEXT NOT NULL,
    helix_id          TEXT NOT NULL,
    helix_session_id  TEXT,
    parent_helix_id   TEXT,
    goal              TEXT NOT NULL,
    depth             INTEGER NOT NULL,
    status            TEXT NOT NULL DEFAULT 'active',
    health            TEXT,
    rolling_score     REAL,
    files_modified_json TEXT DEFAULT '[]',
    created_at        INTEGER NOT NULL,
    completed_at      INTEGER,
    FOREIGN KEY (session_id) REFERENCES constellation_sessions(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS constellation_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    type            TEXT NOT NULL,
    entity          TEXT,
    message         TEXT NOT NULL,
    data_json       TEXT,
    timestamp       INTEGER NOT NULL,
    FOREIGN KEY (session_id) REFERENCES constellation_sessions(id) ON DELETE CASCADE
  );

  CREATE INDEX IF NOT EXISTS idx_const_sess_status ON constellation_sessions(status);
  CREATE INDEX IF NOT EXISTS idx_const_sess_created ON constellation_sessions(created_at);
  CREATE INDEX IF NOT EXISTS idx_const_branch_session ON constellation_branches(session_id);
  CREATE INDEX IF NOT EXISTS idx_const_branch_helix ON constellation_branches(helix_id);
  CREATE INDEX IF NOT EXISTS idx_const_events_session ON constellation_events(session_id, timestamp);

  -- Cross-Helix Dialectic persistence
  CREATE TABLE IF NOT EXISTS constellation_dialectic (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        TEXT NOT NULL,
    messages_json     TEXT NOT NULL DEFAULT '[]',
    convergence_points_json TEXT DEFAULT '[]',
    tensions_json     TEXT DEFAULT '[]',
    participants_json TEXT DEFAULT '[]',
    stats_json        TEXT DEFAULT '{}',
    checkpoint_at     INTEGER NOT NULL,
    FOREIGN KEY (session_id) REFERENCES constellation_sessions(id) ON DELETE CASCADE
  );

  CREATE INDEX IF NOT EXISTS idx_const_dialectic_session ON constellation_dialectic(session_id, checkpoint_at);

  -- Corpus Decision History
  CREATE TABLE IF NOT EXISTS corpus_decisions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        TEXT NOT NULL,
    decision_type     TEXT NOT NULL,  -- 'spawn_evaluation', 'intervention', 'pattern_detection', 'synthesis'
    helix_id          TEXT,           -- optional: which branch this relates to
    input_data_json   TEXT NOT NULL,  -- the request/context that led to this decision
    output_data_json  TEXT NOT NULL,  -- the decision result
    llm_analysis_json TEXT,           -- optional: LLM reasoning/chain-of-thought
    confidence        REAL,           -- optional: confidence score
    timestamp         INTEGER NOT NULL,
    FOREIGN KEY (session_id) REFERENCES constellation_sessions(id) ON DELETE CASCADE
  );

  CREATE INDEX IF NOT EXISTS idx_corpus_decisions_session ON corpus_decisions(session_id, decision_type);
  CREATE INDEX IF NOT EXISTS idx_corpus_decisions_timestamp ON corpus_decisions(timestamp);

  -- Branch Lifecycle Tracking
  CREATE TABLE IF NOT EXISTS branch_lifecycle_events (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        TEXT NOT NULL,
    helix_id          TEXT NOT NULL,
    event_type        TEXT NOT NULL,  -- 'created', 'scored', 'intervention_received', 'completed', 'failed', 'pruned'
    metrics_json      TEXT DEFAULT '{}',  -- rolling_score, health, pattern, etc.
    context_json      TEXT,           -- additional context (files_modified, etc.)
    timestamp         INTEGER NOT NULL,
    FOREIGN KEY (session_id) REFERENCES constellation_sessions(id) ON DELETE CASCADE
  );

  CREATE INDEX IF NOT EXISTS idx_branch_lifecycle_session ON branch_lifecycle_events(session_id, helix_id);
  CREATE INDEX IF NOT EXISTS idx_branch_lifecycle_type ON branch_lifecycle_events(event_type, timestamp);

  -- Blackboard Archive
  CREATE TABLE IF NOT EXISTS blackboard_archives (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        TEXT NOT NULL,
    helix_id          TEXT,           -- null for constellation-level blackboard
    channel_data_json TEXT NOT NULL,  -- all channels: findings, concerns, decisions, artifacts, requests
    scratchpad_json   TEXT,           -- scratchpad state
    tool_log_json     TEXT,           -- tool execution log
    artifacts_json    TEXT,           -- tracked artifacts
    plan_json         TEXT,           -- plan steps
    report_json       TEXT,           -- report sections
    archived_at       INTEGER NOT NULL,
    FOREIGN KEY (session_id) REFERENCES constellation_sessions(id) ON DELETE CASCADE
  );

  CREATE INDEX IF NOT EXISTS idx_blackboard_session ON blackboard_archives(session_id, helix_id);

  -- Training Data Extraction (high-value signals for training warehouse)
  CREATE TABLE IF NOT EXISTS training_signals (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        TEXT NOT NULL,
    signal_type       TEXT NOT NULL,  -- 'brainstem_annotation', 'corpus_decision', 'dialectic_outcome', 'convergence', 'tension_resolved'
    source_helix_id   TEXT,           -- which branch produced this signal
    data_json         TEXT NOT NULL,  -- structured training data
    quality_score     REAL,           -- calculated quality/importance
    extracted_at      INTEGER NOT NULL,
    FOREIGN KEY (session_id) REFERENCES constellation_sessions(id) ON DELETE CASCADE
  );

  CREATE INDEX IF NOT EXISTS idx_training_session ON training_signals(session_id, signal_type);
  CREATE INDEX IF NOT EXISTS idx_training_quality ON training_signals(quality_score);
`


// ═══════════════════════════════════════════════════════════════════
// Row Types (raw from SQLite)
// ═══════════════════════════════════════════════════════════════════

interface RawSessionRow {
  id: string
  goal: string
  context: string | null
  status: string
  template: string | null
  tree_snapshot_json: string | null
  progress_snapshot_json: string | null
  branch_assessments_json: string
  spawn_decisions_json: string
  cross_patterns_json: string
  interventions_json: string
  sweep_count: number
  helix_session_ids_json: string
  max_helixes: number | null
  max_depth: number | null
  timeout_ms: number | null
  total_branches: number
  completed_branches: number
  failed_branches: number
  tokens_used: number
  duration_ms: number | null
  error: string | null
  created_at: number
  completed_at: number | null
}

interface RawBranchRow {
  id: number
  session_id: string
  helix_id: string
  helix_session_id: string | null
  parent_helix_id: string | null
  goal: string
  depth: number
  status: string
  health: string | null
  rolling_score: number | null
  files_modified_json: string
  created_at: number
  completed_at: number | null
}

interface RawEventRow {
  id: number
  session_id: string
  type: string
  entity: string | null
  message: string
  data_json: string | null
  timestamp: number
}


// ═══════════════════════════════════════════════════════════════════
// Public Row Types (parsed)
// ═══════════════════════════════════════════════════════════════════

export type ConstellationStatus = 'running' | 'completed' | 'failed' | 'cancelled'
export type BranchStatus = 'active' | 'completed' | 'failed' | 'pruned'
export type BranchHealth = 'productive' | 'active' | 'struggling' | 'stuck' | 'drifting' | 'completed' | 'failed'

export interface ConstellationSessionRow {
  id: string
  goal: string
  context: string | null
  status: ConstellationStatus
  template: string | null
  treeSnapshot: CorpusTreeSnapshot | null
  progressSnapshot: ProgressSnapshot | null
  branchAssessments: BranchAssessment[]
  spawnDecisions: SpawnDecision[]
  crossPatterns: CrossHelixPattern[]
  interventions: CorpusIntervention[]
  sweepCount: number
  helixSessionIds: string[]
  maxHelixes: number | null
  maxDepth: number | null
  timeoutMs: number | null
  totalBranches: number
  completedBranches: number
  failedBranches: number
  tokensUsed: number
  durationMs: number | null
  error: string | null
  createdAt: number
  completedAt: number | null
}

export interface ConstellationBranchRow {
  id: number
  sessionId: string
  helixId: string
  helixSessionId: string | null
  parentHelixId: string | null
  goal: string
  depth: number
  status: BranchStatus
  health: BranchHealth | null
  rollingScore: number | null
  filesModified: string[]
  createdAt: number
  completedAt: number | null
}

export interface ConstellationEventRow {
  id: number
  sessionId: string
  type: string
  entity: string | null
  message: string
  data: unknown
  timestamp: number
}

export interface ProgressSnapshot {
  markdown: string
  data: {
    activeBranches: number
    totalBranches: number
    completedBranches: number
    failedBranches: number
    sweepCount: number
    lastSweepAt: number
  }
}

export interface SpawnDecision {
  requestId: string
  helixId: string
  goal: string
  approved: boolean
  reason: string
  timestamp: number
}

// ═══════════════════════════════════════════════════════════════════
// New Persistence Types
// ═══════════════════════════════════════════════════════════════════

export type CorpusDecisionType = 'spawn_evaluation' | 'intervention' | 'pattern_detection' | 'synthesis' | 'health_assessment'

export interface CorpusDecisionRow {
  id: number
  sessionId: string
  decisionType: CorpusDecisionType
  helixId: string | null
  inputData: unknown
  outputData: unknown
  llmAnalysis: unknown | null
  confidence: number | null
  timestamp: number
}

export type BranchLifecycleEventType = 'created' | 'scored' | 'intervention_received' | 'completed' | 'failed' | 'pruned' | 'spawned_child'

export interface BranchLifecycleEventRow {
  id: number
  sessionId: string
  helixId: string
  eventType: BranchLifecycleEventType
  metrics: Record<string, unknown>
  context: Record<string, unknown> | null
  timestamp: number
}

export interface CrossHelixDialecticRow {
  id: number
  sessionId: string
  messages: unknown[]
  convergencePoints: unknown[]
  tensions: unknown[]
  participants: string[]
  stats: Record<string, unknown>
  checkpointAt: number
}

export interface BlackboardArchiveRow {
  id: number
  sessionId: string
  helixId: string | null
  channelData: {
    findings: unknown[]
    concerns: unknown[]
    decisions: unknown[]
    artifacts: unknown[]
    requests: unknown[]
  }
  scratchpad: Record<string, unknown> | null
  toolLog: unknown[] | null
  artifacts: unknown[] | null
  plan: unknown | null
  report: unknown | null
  archivedAt: number
}

export type TrainingSignalType = 'brainstem_annotation' | 'corpus_decision' | 'dialectic_outcome' | 'convergence' | 'tension_resolved' | 'intervention_effective'

export interface TrainingSignalRow {
  id: number
  sessionId: string
  signalType: TrainingSignalType
  sourceHelixId: string | null
  data: Record<string, unknown>
  qualityScore: number | null
  extractedAt: number
}

export interface CreateSessionOpts {
  context?: string
  template?: string
  maxHelixes?: number
  maxDepth?: number
  timeoutMs?: number
}

export interface CompleteSessionData {
  tree: CorpusTreeSnapshot
  progress: ProgressSnapshot
  branchAssessments?: BranchAssessment[]
  spawnDecisions?: SpawnDecision[]
  crossPatterns?: CrossHelixPattern[]
  interventions?: CorpusIntervention[]
  sweepCount?: number
  helixSessionIds?: string[]
  totalBranches?: number
  completedBranches?: number
  failedBranches?: number
  tokensUsed?: number
  durationMs?: number
}


// ═══════════════════════════════════════════════════════════════════
// ConstellationStore Class
// ═══════════════════════════════════════════════════════════════════

export class ConstellationStore {
  private db: InstanceType<typeof Database>
  private logger: ILogger

  private _stmts?: {
    insertSession: Database.Statement
    updateSessionStatus: Database.Statement
    saveCheckpoint: Database.Statement
    completeSession: Database.Statement
    failSession: Database.Statement
    insertBranch: Database.Statement
    updateBranch: Database.Statement
    insertEvent: Database.Statement
    selectSession: Database.Statement
    selectSessions: Database.Statement
    selectSessionsWithArchived: Database.Statement
    selectBranches: Database.Statement
    selectEvents: Database.Statement
    pruneOld: Database.Statement
    pruneBranches: Database.Statement
    pruneEvents: Database.Statement
    // New persistence tables
    insertDialecticCheckpoint: Database.Statement
    selectDialecticCheckpoints: Database.Statement
    insertCorpusDecision: Database.Statement
    selectCorpusDecisions: Database.Statement
    insertBranchLifecycleEvent: Database.Statement
    selectBranchLifecycleEvents: Database.Statement
    insertBlackboardArchive: Database.Statement
    selectBlackboardArchives: Database.Statement
    insertTrainingSignal: Database.Statement
    selectTrainingSignals: Database.Statement
  }

  private constructor(dbPath: string, logger: ILogger) {
    this.logger = logger.child('constellation-store')
    this.db = new Database(dbPath)
    this.db.pragma('journal_mode = WAL')
    this.db.pragma('synchronous = NORMAL')
    this.db.pragma('foreign_keys = ON')
    this.db.pragma('busy_timeout = 5000')
    this.migrate()
  }


  static open(logger: ILogger, dataDir?: string, maxAgeDays = DEFAULT_MAX_AGE_DAYS): ConstellationStore {
    const dir = dataDir ?? getDataDir()
    fs.mkdirSync(dir, { recursive: true })
    const dbPath = path.join(dir, 'constellation.db')
    const store = new ConstellationStore(dbPath, logger)
    const pruned = store.prune(maxAgeDays)
    if (pruned > 0) store.logger.info(`Pruned ${pruned} stale constellation session(s) (>${maxAgeDays}d old)`)
    store.logger.info(`ConstellationStore open — ${dbPath}`)
    return store
  }


  private migrate(): void {
    const row = this.db.prepare(
      `SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'`
    ).get() as { name: string } | undefined

    if (!row) {
      this.db.exec(SCHEMA_SQL)
      this.db.prepare('INSERT INTO schema_version (version) VALUES (?)').run(SCHEMA_VERSION)
      this.logger.info('ConstellationStore schema initialized', { version: SCHEMA_VERSION })
      return
    }

    const versionRow = this.db.prepare('SELECT version FROM schema_version LIMIT 1').get() as { version: number } | undefined
    const current = versionRow?.version ?? 0

    if (current < SCHEMA_VERSION) {
      this.runMigrations(current)
      this.db.prepare('UPDATE schema_version SET version = ?').run(SCHEMA_VERSION)
      this.logger.info('ConstellationStore schema migrated', { from: current, to: SCHEMA_VERSION })
    }
  }

  private runMigrations(fromVersion: number): void {
    // Migration from version 1 to 2: add new persistence tables
    if (fromVersion < 2) {
      this.db.exec(`
        -- Cross-Helix Dialectic persistence
        CREATE TABLE IF NOT EXISTS constellation_dialectic (
          id                INTEGER PRIMARY KEY AUTOINCREMENT,
          session_id        TEXT NOT NULL,
          messages_json     TEXT NOT NULL DEFAULT '[]',
          convergence_points_json TEXT DEFAULT '[]',
          tensions_json     TEXT DEFAULT '[]',
          participants_json TEXT DEFAULT '[]',
          stats_json        TEXT DEFAULT '{}',
          checkpoint_at     INTEGER NOT NULL,
          FOREIGN KEY (session_id) REFERENCES constellation_sessions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_const_dialectic_session ON constellation_dialectic(session_id, checkpoint_at);

        -- Corpus Decision History
        CREATE TABLE IF NOT EXISTS corpus_decisions (
          id                INTEGER PRIMARY KEY AUTOINCREMENT,
          session_id        TEXT NOT NULL,
          decision_type     TEXT NOT NULL,
          helix_id          TEXT,
          input_data_json   TEXT NOT NULL,
          output_data_json  TEXT NOT NULL,
          llm_analysis_json TEXT,
          confidence        REAL,
          timestamp         INTEGER NOT NULL,
          FOREIGN KEY (session_id) REFERENCES constellation_sessions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_corpus_decisions_session ON corpus_decisions(session_id, decision_type);
        CREATE INDEX IF NOT EXISTS idx_corpus_decisions_timestamp ON corpus_decisions(timestamp);

        -- Branch Lifecycle Tracking
        CREATE TABLE IF NOT EXISTS branch_lifecycle_events (
          id                INTEGER PRIMARY KEY AUTOINCREMENT,
          session_id        TEXT NOT NULL,
          helix_id          TEXT NOT NULL,
          event_type        TEXT NOT NULL,
          metrics_json      TEXT DEFAULT '{}',
          context_json      TEXT,
          timestamp         INTEGER NOT NULL,
          FOREIGN KEY (session_id) REFERENCES constellation_sessions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_branch_lifecycle_session ON branch_lifecycle_events(session_id, helix_id);
        CREATE INDEX IF NOT EXISTS idx_branch_lifecycle_type ON branch_lifecycle_events(event_type, timestamp);

        -- Blackboard Archive
        CREATE TABLE IF NOT EXISTS blackboard_archives (
          id                INTEGER PRIMARY KEY AUTOINCREMENT,
          session_id        TEXT NOT NULL,
          helix_id          TEXT,
          channel_data_json TEXT NOT NULL,
          scratchpad_json   TEXT,
          tool_log_json     TEXT,
          artifacts_json    TEXT,
          plan_json         TEXT,
          report_json       TEXT,
          archived_at       INTEGER NOT NULL,
          FOREIGN KEY (session_id) REFERENCES constellation_sessions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_blackboard_session ON blackboard_archives(session_id, helix_id);

        -- Training Data Extraction
        CREATE TABLE IF NOT EXISTS training_signals (
          id                INTEGER PRIMARY KEY AUTOINCREMENT,
          session_id        TEXT NOT NULL,
          signal_type       TEXT NOT NULL,
          source_helix_id   TEXT,
          data_json         TEXT NOT NULL,
          quality_score     REAL,
          extracted_at      INTEGER NOT NULL,
          FOREIGN KEY (session_id) REFERENCES constellation_sessions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_training_session ON training_signals(session_id, signal_type);
        CREATE INDEX IF NOT EXISTS idx_training_quality ON training_signals(quality_score);
      `)
    }
  }


  private get stmts() {
    if (!this._stmts) {
      this._stmts = {
        insertSession: this.db.prepare(`
          INSERT INTO constellation_sessions (
            id, goal, context, status, template,
            max_helixes, max_depth, timeout_ms, created_at
          ) VALUES (
            @id, @goal, @context, @status, @template,
            @max_helixes, @max_depth, @timeout_ms, @created_at
          )
        `),

        updateSessionStatus: this.db.prepare(`
          UPDATE constellation_sessions SET status = @status WHERE id = @id
        `),

        saveCheckpoint: this.db.prepare(`
          UPDATE constellation_sessions SET
            tree_snapshot_json = @tree_snapshot_json,
            progress_snapshot_json = @progress_snapshot_json,
            sweep_count = @sweep_count,
            total_branches = @total_branches,
            completed_branches = @completed_branches,
            failed_branches = @failed_branches,
            tokens_used = @tokens_used,
            duration_ms = @duration_ms
          WHERE id = @id
        `),

        completeSession: this.db.prepare(`
          UPDATE constellation_sessions SET
            status = @status,
            tree_snapshot_json = @tree_snapshot_json,
            progress_snapshot_json = @progress_snapshot_json,
            branch_assessments_json = @branch_assessments_json,
            spawn_decisions_json = @spawn_decisions_json,
            cross_patterns_json = @cross_patterns_json,
            interventions_json = @interventions_json,
            sweep_count = @sweep_count,
            helix_session_ids_json = @helix_session_ids_json,
            total_branches = @total_branches,
            completed_branches = @completed_branches,
            failed_branches = @failed_branches,
            tokens_used = @tokens_used,
            duration_ms = @duration_ms,
            completed_at = @completed_at
          WHERE id = @id
        `),

        failSession: this.db.prepare(`
          UPDATE constellation_sessions SET
            status = 'failed',
            error = @error,
            duration_ms = @duration_ms,
            completed_at = @completed_at
          WHERE id = @id
        `),

        insertBranch: this.db.prepare(`
          INSERT INTO constellation_branches (
            session_id, helix_id, helix_session_id, parent_helix_id,
            goal, depth, status, health, rolling_score, files_modified_json, created_at
          ) VALUES (
            @session_id, @helix_id, @helix_session_id, @parent_helix_id,
            @goal, @depth, @status, @health, @rolling_score, @files_modified_json, @created_at
          )
        `),

        updateBranch: this.db.prepare(`
          UPDATE constellation_branches SET
            status = @status,
            health = @health,
            rolling_score = @rolling_score,
            files_modified_json = @files_modified_json,
            completed_at = @completed_at
          WHERE session_id = @session_id AND helix_id = @helix_id
        `),

        insertEvent: this.db.prepare(`
          INSERT INTO constellation_events (session_id, type, entity, message, data_json, timestamp)
          VALUES (@session_id, @type, @entity, @message, @data_json, @timestamp)
        `),

        selectSession: this.db.prepare('SELECT * FROM constellation_sessions WHERE id = ?'),

        selectSessions: this.db.prepare(`
          SELECT * FROM constellation_sessions
          WHERE (@status IS NULL OR status = @status)
          ORDER BY created_at DESC
          LIMIT @limit
        `),

        selectSessionsWithArchived: this.db.prepare(`
          SELECT * FROM constellation_sessions
          WHERE (@status IS NULL OR status = @status)
            AND (@include_archived = 1 OR status = 'running')
          ORDER BY created_at DESC
          LIMIT @limit
        `),

        selectBranches: this.db.prepare(
          'SELECT * FROM constellation_branches WHERE session_id = ? ORDER BY depth ASC, created_at ASC'
        ),

        selectEvents: this.db.prepare(
          'SELECT * FROM constellation_events WHERE session_id = ? ORDER BY timestamp ASC'
        ),

        pruneOld: this.db.prepare(`
          DELETE FROM constellation_sessions
          WHERE status IN ('completed', 'failed', 'cancelled')
            AND created_at < ?
        `),

        pruneBranches: this.db.prepare(`
          DELETE FROM constellation_branches
          WHERE session_id NOT IN (SELECT id FROM constellation_sessions)
        `),

        pruneEvents: this.db.prepare(`
          DELETE FROM constellation_events
          WHERE session_id NOT IN (SELECT id FROM constellation_sessions)
        `),
        // New persistence statements
        insertDialecticCheckpoint: this.db.prepare(`
          INSERT INTO constellation_dialectic (
            session_id, messages_json, convergence_points_json, tensions_json,
            participants_json, stats_json, checkpoint_at
          ) VALUES (
            @session_id, @messages_json, @convergence_points_json, @tensions_json,
            @participants_json, @stats_json, @checkpoint_at
          )
        `),
        selectDialecticCheckpoints: this.db.prepare(`
          SELECT * FROM constellation_dialectic WHERE session_id = @session_id ORDER BY checkpoint_at DESC
        `),
        insertCorpusDecision: this.db.prepare(`
          INSERT INTO corpus_decisions (
            session_id, decision_type, helix_id, input_data_json, output_data_json,
            llm_analysis_json, confidence, timestamp
          ) VALUES (
            @session_id, @decision_type, @helix_id, @input_data_json, @output_data_json,
            @llm_analysis_json, @confidence, @timestamp
          )
        `),
        selectCorpusDecisions: this.db.prepare(`
          SELECT * FROM corpus_decisions WHERE session_id = @session_id ORDER BY timestamp DESC
        `),
        insertBranchLifecycleEvent: this.db.prepare(`
          INSERT INTO branch_lifecycle_events (
            session_id, helix_id, event_type, metrics_json, context_json, timestamp
          ) VALUES (
            @session_id, @helix_id, @event_type, @metrics_json, @context_json, @timestamp
          )
        `),
        selectBranchLifecycleEvents: this.db.prepare(`
          SELECT * FROM branch_lifecycle_events WHERE session_id = @session_id AND helix_id = @helix_id ORDER BY timestamp DESC
        `),
        insertBlackboardArchive: this.db.prepare(`
          INSERT INTO blackboard_archives (
            session_id, helix_id, channel_data_json, scratchpad_json, tool_log_json,
            artifacts_json, plan_json, report_json, archived_at
          ) VALUES (
            @session_id, @helix_id, @channel_data_json, @scratchpad_json, @tool_log_json,
            @artifacts_json, @plan_json, @report_json, @archived_at
          )
        `),
        selectBlackboardArchives: this.db.prepare(`
          SELECT * FROM blackboard_archives WHERE session_id = @session_id ORDER BY archived_at DESC
        `),
        insertTrainingSignal: this.db.prepare(`
          INSERT INTO training_signals (
            session_id, signal_type, source_helix_id, data_json, quality_score, extracted_at
          ) VALUES (
            @session_id, @signal_type, @source_helix_id, @data_json, @quality_score, @extracted_at
          )
        `),
        selectTrainingSignals: this.db.prepare(`
          SELECT * FROM training_signals WHERE session_id = @session_id ORDER BY extracted_at DESC
        `),
      }
    }
    return this._stmts
  }


  // ─────────────────────────────────────────────────────────────────
  // Session Lifecycle
  // ─────────────────────────────────────────────────────────────────

  createSession(id: string, goal: string, opts?: CreateSessionOpts): void {
    this.stmts.insertSession.run({
      id,
      goal,
      context: opts?.context ?? null,
      status: 'running',
      template: opts?.template ?? null,
      max_helixes: opts?.maxHelixes ?? null,
      max_depth: opts?.maxDepth ?? null,
      timeout_ms: opts?.timeoutMs ?? null,
      created_at: Date.now(),
    })
    this.logger.debug(`Created Constellation session ${id}`, { goal })
  }


  updateSessionStatus(id: string, status: ConstellationStatus): void {
    this.stmts.updateSessionStatus.run({ id, status })
    this.logger.debug(`Updated Constellation session status`, { id, status })
  }


  /** Save an intermediate checkpoint (tree + progress snapshot) during execution */
  saveCheckpoint(id: string, data: {
    tree: CorpusTreeSnapshot
    progress: ProgressSnapshot
    sweepCount?: number
    totalBranches?: number
    completedBranches?: number
    failedBranches?: number
    tokensUsed?: number
    durationMs?: number
  }): void {
    this.stmts.saveCheckpoint.run({
      id,
      tree_snapshot_json: JSON.stringify(data.tree),
      progress_snapshot_json: JSON.stringify(data.progress),
      sweep_count: data.sweepCount ?? 0,
      total_branches: data.totalBranches ?? 0,
      completed_branches: data.completedBranches ?? 0,
      failed_branches: data.failedBranches ?? 0,
      tokens_used: data.tokensUsed ?? 0,
      duration_ms: data.durationMs ?? 0,
    })
    this.logger.debug('Saved Constellation checkpoint', { id })
  }


  completeSession(id: string, data: CompleteSessionData): void {
    this.stmts.completeSession.run({
      id,
      status: 'completed',
      tree_snapshot_json: JSON.stringify(data.tree),
      progress_snapshot_json: JSON.stringify(data.progress),
      branch_assessments_json: JSON.stringify(data.branchAssessments ?? []),
      spawn_decisions_json: JSON.stringify(data.spawnDecisions ?? []),
      cross_patterns_json: JSON.stringify(data.crossPatterns ?? []),
      interventions_json: JSON.stringify(data.interventions ?? []),
      sweep_count: data.sweepCount ?? 0,
      helix_session_ids_json: JSON.stringify(data.helixSessionIds ?? []),
      total_branches: data.totalBranches ?? 0,
      completed_branches: data.completedBranches ?? 0,
      failed_branches: data.failedBranches ?? 0,
      tokens_used: data.tokensUsed ?? 0,
      duration_ms: data.durationMs ?? 0,
      completed_at: Date.now(),
    })
    this.logger.info(`Completed Constellation session ${id}`)
  }


  failSession(id: string, error: string, durationMs?: number): void {
    this.stmts.failSession.run({
      id,
      error,
      duration_ms: durationMs ?? 0,
      completed_at: Date.now(),
    })
    this.logger.warn(`Failed Constellation session ${id}`, { error })
  }


  cancelSession(id: string, durationMs?: number): void {
    this.db.prepare(`
      UPDATE constellation_sessions SET
        status = 'cancelled',
        duration_ms = ?,
        completed_at = ?
      WHERE id = ?
    `).run(durationMs ?? 0, Date.now(), id)
    this.logger.info(`Cancelled Constellation session ${id}`)
  }


  // ─────────────────────────────────────────────────────────────────
  // Branch Management
  // ─────────────────────────────────────────────────────────────────

  addBranch(
    sessionId: string,
    helixId: string,
    goal: string,
    depth: number,
    opts?: {
      helixSessionId?: string
      parentHelixId?: string
      health?: BranchHealth
      rollingScore?: number
    }
  ): void {
    this.stmts.insertBranch.run({
      session_id: sessionId,
      helix_id: helixId,
      helix_session_id: opts?.helixSessionId ?? null,
      parent_helix_id: opts?.parentHelixId ?? null,
      goal,
      depth,
      status: 'active',
      health: opts?.health ?? 'active',
      rolling_score: opts?.rollingScore ?? null,
      files_modified_json: '[]',
      created_at: Date.now(),
    })
  }


  updateBranch(
    sessionId: string,
    helixId: string,
    data: {
      status?: BranchStatus
      health?: BranchHealth
      rollingScore?: number
      filesModified?: string[]
      completed?: boolean
    }
  ): void {
    this.stmts.updateBranch.run({
      session_id: sessionId,
      helix_id: helixId,
      status: data.status ?? 'active',
      health: data.health ?? null,
      rolling_score: data.rollingScore ?? null,
      files_modified_json: JSON.stringify(data.filesModified ?? []),
      completed_at: data.completed ? Date.now() : null,
    })
  }


  // ─────────────────────────────────────────────────────────────────
  // Event Logging
  // ─────────────────────────────────────────────────────────────────

  appendEvent(sessionId: string, type: string, entity: string | null, message: string, data?: unknown): void {
    this.stmts.insertEvent.run({
      session_id: sessionId,
      type,
      entity,
      message,
      data_json: data ? JSON.stringify(data) : null,
      timestamp: Date.now(),
    })
  }


  // ─────────────────────────────────────────────────────────────────
  // Queries
  // ─────────────────────────────────────────────────────────────────

  getSession(id: string): ConstellationSessionRow | undefined {
    const row = this.stmts.selectSession.get(id) as RawSessionRow | undefined
    if (!row) return undefined
    return this.rowToSession(row)
  }


  getTree(sessionId: string): CorpusTreeSnapshot | null {
    const row = this.stmts.selectSession.get(sessionId) as RawSessionRow | undefined
    if (!row?.tree_snapshot_json) return null
    try {
      return JSON.parse(row.tree_snapshot_json) as CorpusTreeSnapshot
    } catch {
      return null
    }
  }


  getProgress(sessionId: string): ProgressSnapshot | null {
    const row = this.stmts.selectSession.get(sessionId) as RawSessionRow | undefined
    if (!row?.progress_snapshot_json) return null
    try {
      return JSON.parse(row.progress_snapshot_json) as ProgressSnapshot
    } catch {
      return null
    }
  }


  getBranches(sessionId: string): ConstellationBranchRow[] {
    const rows = this.stmts.selectBranches.all(sessionId) as RawBranchRow[]
    return rows.map(r => this.rowToBranch(r))
  }


  getEvents(sessionId: string): ConstellationEventRow[] {
    const rows = this.stmts.selectEvents.all(sessionId) as RawEventRow[]
    return rows.map(r => ({
      id: r.id,
      sessionId: r.session_id,
      type: r.type,
      entity: r.entity,
      message: r.message,
      data: r.data_json ? JSON.parse(r.data_json) : null,
      timestamp: r.timestamp,
    }))
  }


  listSessions(opts?: { limit?: number; status?: string; includeArchived?: boolean }): ConstellationSessionRow[] {
    const limit = opts?.limit ?? 100
    const status = opts?.status ?? null
    const includeArchived = opts?.includeArchived ?? true

    const rows = this.stmts.selectSessionsWithArchived.all({
      limit,
      status,
      include_archived: includeArchived ? 1 : 0,
    }) as RawSessionRow[]

    return rows.map(r => this.rowToSession(r))
  }


  /**
   * Get historical sessions for the /constellation/history endpoint.
   * Supports filtering by time range and status.
   */
  getHistory(opts?: {
    limit?: number
    since?: number  // timestamp
    until?: number  // timestamp
    status?: string
  }): ConstellationSessionRow[] {
    const limit = opts?.limit ?? 100
    const since = opts?.since ?? 0
    const until = opts?.until ?? Date.now()
    const status = opts?.status ?? null

    const rows = this.db.prepare(`
      SELECT * FROM constellation_sessions
      WHERE created_at >= ? AND created_at <= ?
        AND (@status IS NULL OR status = @status)
      ORDER BY created_at DESC
      LIMIT ?
    `).all(since, until, { status }, limit) as RawSessionRow[]

    return rows.map(r => this.rowToSession(r))
  }


  // ─────────────────────────────────────────────────────────────────
  // Maintenance
  // ─────────────────────────────────────────────────────────────────

  prune(maxAgeDays = DEFAULT_MAX_AGE_DAYS): number {
    const cutoff = Date.now() - maxAgeDays * 24 * 60 * 60 * 1000
    const result = this.stmts.pruneOld.run(cutoff)
    // Clean up orphaned branches and events
    this.stmts.pruneBranches.run()
    this.stmts.pruneEvents.run()
    return result.changes
  }


  close(): void {
    this.db.close()
    this.logger.debug('ConstellationStore closed')
  }


  // ─────────────────────────────────────────────────────────────────
  // Row Conversion Helpers
  // ─────────────────────────────────────────────────────────────────

  private rowToSession(row: RawSessionRow): ConstellationSessionRow {
    return {
      id: row.id,
      goal: row.goal,
      context: row.context,
      status: row.status as ConstellationStatus,
      template: row.template,
      treeSnapshot: row.tree_snapshot_json ? JSON.parse(row.tree_snapshot_json) : null,
      progressSnapshot: row.progress_snapshot_json ? JSON.parse(row.progress_snapshot_json) : null,
      branchAssessments: JSON.parse(row.branch_assessments_json || '[]'),
      spawnDecisions: JSON.parse(row.spawn_decisions_json || '[]'),
      crossPatterns: JSON.parse(row.cross_patterns_json || '[]'),
      interventions: JSON.parse(row.interventions_json || '[]'),
      sweepCount: row.sweep_count,
      helixSessionIds: JSON.parse(row.helix_session_ids_json || '[]'),
      maxHelixes: row.max_helixes,
      maxDepth: row.max_depth,
      timeoutMs: row.timeout_ms,
      totalBranches: row.total_branches,
      completedBranches: row.completed_branches,
      failedBranches: row.failed_branches,
      tokensUsed: row.tokens_used,
      durationMs: row.duration_ms,
      error: row.error,
      createdAt: row.created_at,
      completedAt: row.completed_at,
    }
  }

  private rowToBranch(row: RawBranchRow): ConstellationBranchRow {
    return {
      id: row.id,
      sessionId: row.session_id,
      helixId: row.helix_id,
      helixSessionId: row.helix_session_id,
      parentHelixId: row.parent_helix_id,
      goal: row.goal,
      depth: row.depth,
      status: row.status as BranchStatus,
      health: row.health as BranchHealth | null,
      rollingScore: row.rolling_score,
      filesModified: JSON.parse(row.files_modified_json || '[]'),
      createdAt: row.created_at,
      completedAt: row.completed_at,
    }
  }
}
