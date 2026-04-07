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
import type { CorpusTreeSnapshot, BranchAssessment, CrossHelixPattern, CorpusIntervention, ElevatedPattern } from './corpus-types.js'
import type { ConstellationResult, SpawnRequest } from './types.js'
import type { LocusMemoryEntry } from './locus/memory-types.js'
import type { LocusMemoryPersistence } from './locus/constellation-memory.js'
import { getDataDir } from '../../utils/paths.js'


const SCHEMA_VERSION = 4  // v4: locus_memories table
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

  -- Elevated Patterns Library (cross-constellation learning)
  CREATE TABLE IF NOT EXISTS elevated_patterns (
    id                TEXT PRIMARY KEY,
    session_id        TEXT,
    source_helix_id   TEXT NOT NULL,
    approach          TEXT NOT NULL,
    description       TEXT NOT NULL,
    applicable_context TEXT NOT NULL,
    achieved_score    REAL NOT NULL,
    relevant_files_json TEXT DEFAULT '[]',
    supporting_retros_json TEXT DEFAULT '[]',
    reference_count   INTEGER DEFAULT 0,
    elevated_at       INTEGER NOT NULL
  );

  CREATE INDEX IF NOT EXISTS idx_elevated_patterns_score ON elevated_patterns(achieved_score);
  CREATE INDEX IF NOT EXISTS idx_elevated_patterns_approach ON elevated_patterns(approach);
  CREATE INDEX IF NOT EXISTS idx_elevated_patterns_elevated ON elevated_patterns(elevated_at);

  -- Locus Memory (persistent experiential learning across constellations)
  CREATE TABLE IF NOT EXISTS locus_memories (
    id                TEXT PRIMARY KEY,
    content           TEXT NOT NULL,
    memory_type       TEXT NOT NULL,
    confidence        REAL NOT NULL DEFAULT 0.5,
    luminance         REAL NOT NULL,
    phase             TEXT NOT NULL DEFAULT 'provisional',
    origin_session_id TEXT NOT NULL,
    source_helix_id   TEXT NOT NULL,
    source_goal       TEXT NOT NULL DEFAULT '',
    relevant_files_json TEXT DEFAULT '[]',
    confirmations     INTEGER DEFAULT 0,
    contradictions    INTEGER DEFAULT 0,
    recall_count      INTEGER DEFAULT 0,
    created_at        INTEGER NOT NULL,
    last_recalled_at  INTEGER,
    last_updated_at   INTEGER NOT NULL
  );

  CREATE INDEX IF NOT EXISTS idx_locus_mem_phase ON locus_memories(phase);
  CREATE INDEX IF NOT EXISTS idx_locus_mem_confidence ON locus_memories(confidence);
  CREATE INDEX IF NOT EXISTS idx_locus_mem_type ON locus_memories(memory_type);
`


// Row Types (raw from SQLite)

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

interface RawElevatedPatternRow {
  id: string
  session_id: string | null
  source_helix_id: string
  approach: string
  description: string
  applicable_context: string
  achieved_score: number
  relevant_files_json: string
  supporting_retros_json: string
  reference_count: number
  elevated_at: number
}


// Public Row Types (parsed)

export type ConstellationStatus = 'running' | 'completed' | 'failed' | 'cancelled' | 'interrupted'
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

// New Persistence Types

export type CorpusDecisionType = 'spawn_evaluation' | 'spawn' | 'intervention' | 'pattern_detection' | 'synthesis' | 'health_assessment'

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

export type BranchLifecycleEventType = 'created' | 'scored' | 'intervention_received' | 'completed' | 'degraded' | 'failed' | 'pruned' | 'spawned_child'

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

export type TrainingSignalType = 'brainstem_annotation' | 'corpus_decision' | 'dialectic_outcome' | 'convergence' | 'tension_resolved' | 'intervention_effective' | 'locus_kindling' | 'locus_radiance' | 'locus_response' | 'locus_memory_feedback' | 'cross_pattern' | 'intervention_sent' | 'effectiveness_measured'

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


// ConstellationStore Class

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
    // Elevated patterns library
    insertElevatedPattern: Database.Statement
    selectElevatedPatterns: Database.Statement
    selectElevatedPatternsByApproach: Database.Statement
    incrementPatternRefCount: Database.Statement
    pruneElevatedPatterns: Database.Statement
    // Locus memory
    insertLocusMemory: Database.Statement
    updateLocusMemory: Database.Statement
    deleteLocusMemory: Database.Statement
    selectActiveLocusMemories: Database.Statement
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

    // Migration from version 2 to 3: elevated patterns library
    if (fromVersion < 3) {
      this.db.exec(`
        CREATE TABLE IF NOT EXISTS elevated_patterns (
          id                TEXT PRIMARY KEY,
          session_id        TEXT,
          source_helix_id   TEXT NOT NULL,
          approach          TEXT NOT NULL,
          description       TEXT NOT NULL,
          applicable_context TEXT NOT NULL,
          achieved_score    REAL NOT NULL,
          relevant_files_json TEXT DEFAULT '[]',
          supporting_retros_json TEXT DEFAULT '[]',
          reference_count   INTEGER DEFAULT 0,
          elevated_at       INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_elevated_patterns_score ON elevated_patterns(achieved_score);
        CREATE INDEX IF NOT EXISTS idx_elevated_patterns_approach ON elevated_patterns(approach);
        CREATE INDEX IF NOT EXISTS idx_elevated_patterns_elevated ON elevated_patterns(elevated_at);
      `)
    }

    // Migration from version 3 to 4: locus memory table
    if (fromVersion < 4) {
      this.db.exec(`
        CREATE TABLE IF NOT EXISTS locus_memories (
          id                TEXT PRIMARY KEY,
          content           TEXT NOT NULL,
          memory_type       TEXT NOT NULL,
          confidence        REAL NOT NULL DEFAULT 0.5,
          luminance         REAL NOT NULL,
          phase             TEXT NOT NULL DEFAULT 'provisional',
          origin_session_id TEXT NOT NULL,
          source_helix_id   TEXT NOT NULL,
          source_goal       TEXT NOT NULL DEFAULT '',
          relevant_files_json TEXT DEFAULT '[]',
          confirmations     INTEGER DEFAULT 0,
          contradictions    INTEGER DEFAULT 0,
          recall_count      INTEGER DEFAULT 0,
          created_at        INTEGER NOT NULL,
          last_recalled_at  INTEGER,
          last_updated_at   INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_locus_mem_phase ON locus_memories(phase);
        CREATE INDEX IF NOT EXISTS idx_locus_mem_confidence ON locus_memories(confidence);
        CREATE INDEX IF NOT EXISTS idx_locus_mem_type ON locus_memories(memory_type);
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
            completed_at = @completed_at,
            tree_snapshot_json = COALESCE(@tree_snapshot_json, tree_snapshot_json),
            progress_snapshot_json = COALESCE(@progress_snapshot_json, progress_snapshot_json),
            total_branches = COALESCE(@total_branches, total_branches),
            completed_branches = COALESCE(@completed_branches, completed_branches),
            failed_branches = COALESCE(@failed_branches, failed_branches),
            tokens_used = COALESCE(@tokens_used, tokens_used)
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
          WHERE status IN ('completed', 'failed', 'cancelled', 'interrupted')
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
        // Elevated patterns library
        insertElevatedPattern: this.db.prepare(`
          INSERT OR REPLACE INTO elevated_patterns (
            id, session_id, source_helix_id, approach, description,
            applicable_context, achieved_score, relevant_files_json,
            supporting_retros_json, reference_count, elevated_at
          ) VALUES (
            @id, @session_id, @source_helix_id, @approach, @description,
            @applicable_context, @achieved_score, @relevant_files_json,
            @supporting_retros_json, @reference_count, @elevated_at
          )
        `),
        selectElevatedPatterns: this.db.prepare(`
          SELECT * FROM elevated_patterns ORDER BY achieved_score DESC, elevated_at DESC
        `),
        selectElevatedPatternsByApproach: this.db.prepare(`
          SELECT * FROM elevated_patterns WHERE approach = @approach ORDER BY achieved_score DESC
        `),
        incrementPatternRefCount: this.db.prepare(`
          UPDATE elevated_patterns SET reference_count = reference_count + 1 WHERE id = @id
        `),
        pruneElevatedPatterns: this.db.prepare(`
          DELETE FROM elevated_patterns WHERE elevated_at < ? AND reference_count = 0
        `),
        // Locus memory
        insertLocusMemory: this.db.prepare(`
          INSERT INTO locus_memories (
            id, content, memory_type, confidence, luminance, phase,
            origin_session_id, source_helix_id, source_goal,
            relevant_files_json, confirmations, contradictions,
            recall_count, created_at, last_recalled_at, last_updated_at
          ) VALUES (
            @id, @content, @memory_type, @confidence, @luminance, @phase,
            @origin_session_id, @source_helix_id, @source_goal,
            @relevant_files_json, @confirmations, @contradictions,
            @recall_count, @created_at, @last_recalled_at, @last_updated_at
          )
        `),
        updateLocusMemory: this.db.prepare(`
          UPDATE locus_memories SET
            confidence = @confidence,
            phase = @phase,
            confirmations = @confirmations,
            contradictions = @contradictions,
            recall_count = @recall_count,
            last_recalled_at = @last_recalled_at,
            last_updated_at = @last_updated_at
          WHERE id = @id
        `),
        deleteLocusMemory: this.db.prepare(`
          DELETE FROM locus_memories WHERE id = ?
        `),
        selectActiveLocusMemories: this.db.prepare(`
          SELECT * FROM locus_memories WHERE phase != 'invalidated' ORDER BY confidence DESC
        `),
      }
    }
    return this._stmts
  }


  // Session Lifecycle

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

  /** Save a tree-only checkpoint (simplified version for periodic persistence) */
  saveTreeCheckpoint(id: string, tree: CorpusTreeSnapshot): void {
    const progress: ProgressSnapshot = {
      markdown: `Tree checkpoint: ${tree.activeBranches} active branches, ${tree.totalSteps} total steps`,
      data: {
        activeBranches: tree.activeBranches,
        totalBranches: tree.branches.length,
        completedBranches: tree.branches.filter(b => b.status === 'completed').length,
        failedBranches: tree.branches.filter(b => b.status === 'failed').length,
        sweepCount: 0,
        lastSweepAt: tree.snapshotAt,
      },
    }
    this.stmts.saveCheckpoint.run({
      id,
      tree_snapshot_json: JSON.stringify(tree),
      progress_snapshot_json: JSON.stringify(progress),
      sweep_count: 0,
      total_branches: tree.branches.length,
      completed_branches: progress.data.completedBranches,
      failed_branches: progress.data.failedBranches,
      tokens_used: 0,
      duration_ms: 0,
    })
    this.logger.debug('Saved tree checkpoint', { id })
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


  failSession(id: string, error: string, durationMs?: number, data?: {
    tree?: CorpusTreeSnapshot
    progress?: ProgressSnapshot
    totalBranches?: number
    completedBranches?: number
    failedBranches?: number
    tokensUsed?: number
  }): void {
    this.stmts.failSession.run({
      id,
      error,
      duration_ms: durationMs ?? 0,
      completed_at: Date.now(),
      tree_snapshot_json: data?.tree ? JSON.stringify(data.tree) : null,
      progress_snapshot_json: data?.progress ? JSON.stringify(data.progress) : null,
      total_branches: data?.totalBranches ?? null,
      completed_branches: data?.completedBranches ?? null,
      failed_branches: data?.failedBranches ?? null,
      tokens_used: data?.tokensUsed ?? null,
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


  interruptSession(id: string, durationMs?: number): void {
    this.db.prepare(`
      UPDATE constellation_sessions SET
        status = 'interrupted',
        duration_ms = ?,
        completed_at = ?
      WHERE id = ?
    `).run(durationMs ?? 0, Date.now(), id)
    this.logger.info(`Interrupted Constellation session ${id}`)
  }


  // Branch Management

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


  // Event Logging

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


  // Queries

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


  // Maintenance

  prune(maxAgeDays = DEFAULT_MAX_AGE_DAYS): number {
    const cutoff = Date.now() - maxAgeDays * 24 * 60 * 60 * 1000
    const result = this.stmts.pruneOld.run(cutoff)
    // Clean up orphaned branches and events
    this.stmts.pruneBranches.run()
    this.stmts.pruneEvents.run()
    // Prune unreferenced elevated patterns (longer retention: 2x session retention)
    this.pruneElevatedPatterns(maxAgeDays * 2)
    return result.changes
  }


  /**
   * Recover orphaned sessions that were left in 'running' status after a daemon restart.
   * Marks them as 'failed' with an appropriate error message and duration estimate.
   * Should be called once at daemon startup before any new constellations are launched.
   *
   * Returns the number of orphaned sessions recovered.
   */
  recoverOrphanedSessions(): { failed: number; interrupted: number } {
    const now = Date.now()

    // WHY: First, identify which orphaned sessions have checkpoint data.
    // Sessions with both tree and progress snapshots can be resumed.
    // Sessions without checkpoints are unrecoverable and marked failed.
    const orphans = this.db.prepare(`
      SELECT id, goal, tree_snapshot_json IS NOT NULL as has_tree,
             progress_snapshot_json IS NOT NULL as has_progress,
             sweep_count, total_branches, completed_branches, failed_branches
      FROM constellation_sessions
      WHERE status = 'running'
    `).all() as Array<{
      id: string; goal: string; has_tree: number; has_progress: number
      sweep_count: number; total_branches: number; completed_branches: number; failed_branches: number
    }>

    if (orphans.length === 0) return { failed: 0, interrupted: 0 }

    let interruptedCount = 0
    let failedCount = 0

    for (const orphan of orphans) {
      const hasCheckpoint = !!(orphan.has_tree && orphan.has_progress)
      this.logger.info('Recovering orphaned constellation session', {
        id: orphan.id,
        goal: orphan.goal.slice(0, 100),
        hasCheckpoint,
        sweepCount: orphan.sweep_count,
        totalBranches: orphan.total_branches,
        completedBranches: orphan.completed_branches,
        failedBranches: orphan.failed_branches,
      })

      if (hasCheckpoint) {
        // WHY: Sessions with checkpoint data are resumable — mark as 'interrupted'
        // so the daemon boot can auto-resume them.
        this.db.prepare(`
          UPDATE constellation_sessions SET
            status = 'interrupted',
            error = 'Process terminated unexpectedly (checkpoint available for resume)',
            completed_at = ?,
            duration_ms = CASE
              WHEN created_at IS NOT NULL THEN ? - created_at
              ELSE duration_ms
            END
          WHERE id = ?
        `).run(now, now, orphan.id)
        interruptedCount++
      } else {
        // WHY: Sessions without checkpoint data cannot be resumed — mark as failed.
        this.db.prepare(`
          UPDATE constellation_sessions SET
            status = 'failed',
            error = 'Process terminated unexpectedly (no checkpoint data)',
            completed_at = ?,
            duration_ms = CASE
              WHEN created_at IS NOT NULL THEN ? - created_at
              ELSE duration_ms
            END
          WHERE id = ?
        `).run(now, now, orphan.id)
        failedCount++
      }
    }

    if (interruptedCount > 0 || failedCount > 0) {
      this.logger.info('Recovered orphaned constellation sessions', {
        interrupted: interruptedCount,
        failed: failedCount,
      })
    }
    return { failed: failedCount, interrupted: interruptedCount }
  }


  // Elevated Patterns Library

  /**
   * Persist an elevated pattern to the cross-constellation library.
   * Uses INSERT OR REPLACE so re-elevation of the same pattern ID updates it.
   */
  saveElevatedPattern(pattern: ElevatedPattern, sessionId?: string): void {
    this.stmts.insertElevatedPattern.run({
      id: pattern.id,
      session_id: sessionId ?? null,
      source_helix_id: pattern.sourceHelixId,
      approach: pattern.approach,
      description: pattern.description,
      applicable_context: pattern.applicableContext,
      achieved_score: pattern.achievedScore,
      relevant_files_json: JSON.stringify(pattern.relevantFiles),
      supporting_retros_json: JSON.stringify(pattern.supportingRetrospectives),
      reference_count: pattern.referenceCount,
      elevated_at: pattern.elevatedAt,
    })
    this.logger.debug('Elevated pattern persisted', {
      id: pattern.id,
      approach: pattern.approach,
      score: pattern.achievedScore.toFixed(2),
    })
  }

  /**
   * Load all elevated patterns from the library, ordered by score descending.
   * Optionally filter by approach type and minimum score.
   */
  getElevatedPatterns(opts?: { approach?: string; minScore?: number; limit?: number }): ElevatedPattern[] {
    let rows: RawElevatedPatternRow[]
    if (opts?.approach) {
      rows = this.stmts.selectElevatedPatternsByApproach.all({ approach: opts.approach }) as RawElevatedPatternRow[]
    } else {
      rows = this.stmts.selectElevatedPatterns.all() as RawElevatedPatternRow[]
    }

    let patterns = rows.map(row => this.rowToElevatedPattern(row))

    if (opts?.minScore !== undefined) {
      patterns = patterns.filter(p => p.achievedScore >= opts.minScore!)
    }
    if (opts?.limit !== undefined) {
      patterns = patterns.slice(0, opts.limit)
    }

    return patterns
  }

  /**
   * Increment the reference count when a pattern is used by a branch.
   * Patterns with higher reference counts are kept longer during pruning.
   */
  incrementPatternReferenceCount(patternId: string): void {
    this.stmts.incrementPatternRefCount.run({ id: patternId })
  }

  /**
   * Prune old elevated patterns that have never been referenced.
   * Referenced patterns are kept indefinitely.
   */
  pruneElevatedPatterns(maxAgeDays: number): number {
    const cutoff = Date.now() - maxAgeDays * 24 * 60 * 60 * 1000
    const result = this.stmts.pruneElevatedPatterns.run(cutoff)
    if (result.changes > 0) {
      this.logger.info(`Pruned ${result.changes} unreferenced elevated pattern(s)`)
    }
    return result.changes
  }


  close(): void {
    this.db.close()
    this.logger.debug('ConstellationStore closed')
  }


  // Row Conversion Helpers

  /**
   * Safe JSON parser that returns a fallback value on parse error.
   * Used for all JSON fields in row conversion to prevent crashes on corrupted data.
   */
  private safeJsonParse<T>(json: string | null | undefined, fallback: T): T {
    if (!json) return fallback
    try {
      return JSON.parse(json) as T
    } catch {
      return fallback
    }
  }

  private rowToSession(row: RawSessionRow): ConstellationSessionRow {
    return {
      id: row.id,
      goal: row.goal,
      context: row.context,
      status: row.status as ConstellationStatus,
      template: row.template,
      treeSnapshot: row.tree_snapshot_json ? this.safeJsonParse(row.tree_snapshot_json, null) : null,
      progressSnapshot: row.progress_snapshot_json ? this.safeJsonParse(row.progress_snapshot_json, null) : null,
      branchAssessments: this.safeJsonParse(row.branch_assessments_json, []),
      spawnDecisions: this.safeJsonParse(row.spawn_decisions_json, []),
      crossPatterns: this.safeJsonParse(row.cross_patterns_json, []),
      interventions: this.safeJsonParse(row.interventions_json, []),
      sweepCount: row.sweep_count,
      helixSessionIds: this.safeJsonParse(row.helix_session_ids_json, []),
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
      filesModified: this.safeJsonParse(row.files_modified_json, []),
      createdAt: row.created_at,
      completedAt: row.completed_at,
    }
  }

  private rowToElevatedPattern(row: RawElevatedPatternRow): ElevatedPattern {
    return {
      id: row.id,
      sourceHelixId: row.source_helix_id,
      approach: row.approach as ElevatedPattern['approach'],
      description: row.description,
      applicableContext: row.applicable_context,
      achievedScore: row.achieved_score,
      relevantFiles: this.safeJsonParse(row.relevant_files_json, []),
      supportingRetrospectives: this.safeJsonParse(row.supporting_retros_json, []),
      referenceCount: row.reference_count,
      elevatedAt: row.elevated_at,
    }
  }


  // Cross-Helix Dialectic Persistence

  saveDialecticCheckpoint(
    sessionId: string,
    snapshot: {
      messages: unknown[]
      convergencePoints: unknown[]
      tensions: unknown[]
      participants: string[]
      stats: Record<string, unknown>
    }
  ): void {
    this.stmts.insertDialecticCheckpoint.run({
      session_id: sessionId,
      messages_json: JSON.stringify(snapshot.messages),
      convergence_points_json: JSON.stringify(snapshot.convergencePoints),
      tensions_json: JSON.stringify(snapshot.tensions),
      participants_json: JSON.stringify(snapshot.participants),
      stats_json: JSON.stringify(snapshot.stats),
      checkpoint_at: Date.now(),
    })
    this.logger.debug('Dialectic checkpoint saved', { sessionId, messageCount: snapshot.messages.length })
  }

  getDialecticCheckpoints(sessionId: string): CrossHelixDialecticRow[] {
    const rows = this.stmts.selectDialecticCheckpoints.all({ session_id: sessionId }) as {
      id: number
      session_id: string
      messages_json: string
      convergence_points_json: string
      tensions_json: string
      participants_json: string
      stats_json: string
      checkpoint_at: number
    }[]
    return rows.map(r => ({
      id: r.id,
      sessionId: r.session_id,
      messages: JSON.parse(r.messages_json),
      convergencePoints: JSON.parse(r.convergence_points_json),
      tensions: JSON.parse(r.tensions_json),
      participants: JSON.parse(r.participants_json),
      stats: JSON.parse(r.stats_json),
      checkpointAt: r.checkpoint_at,
    }))
  }


  // Corpus Decision History

  recordCorpusDecision(
    sessionId: string,
    decision: {
      decisionType: CorpusDecisionType
      helixId?: string
      inputData: unknown
      outputData: unknown
      llmAnalysis?: unknown
      confidence?: number
    }
  ): void {
    this.stmts.insertCorpusDecision.run({
      session_id: sessionId,
      decision_type: decision.decisionType,
      helix_id: decision.helixId ?? null,
      input_data_json: JSON.stringify(decision.inputData),
      output_data_json: JSON.stringify(decision.outputData),
      llm_analysis_json: decision.llmAnalysis ? JSON.stringify(decision.llmAnalysis) : null,
      confidence: decision.confidence ?? null,
      timestamp: Date.now(),
    })
    this.logger.debug('Corpus decision recorded', { sessionId, type: decision.decisionType })
  }

  getCorpusDecisions(sessionId: string, decisionType?: CorpusDecisionType): CorpusDecisionRow[] {
    let query = 'SELECT * FROM corpus_decisions WHERE session_id = ?'
    const params: (string | CorpusDecisionType)[] = [sessionId]
    if (decisionType) {
      query += ' AND decision_type = ?'
      params.push(decisionType)
    }
    query += ' ORDER BY timestamp DESC'
    const rows = this.db.prepare(query).all(...params) as {
      id: number
      session_id: string
      decision_type: string
      helix_id: string | null
      input_data_json: string
      output_data_json: string
      llm_analysis_json: string | null
      confidence: number | null
      timestamp: number
    }[]
    return rows.map(r => ({
      id: r.id,
      sessionId: r.session_id,
      decisionType: r.decision_type as CorpusDecisionType,
      helixId: r.helix_id,
      inputData: JSON.parse(r.input_data_json),
      outputData: JSON.parse(r.output_data_json),
      llmAnalysis: r.llm_analysis_json ? JSON.parse(r.llm_analysis_json) : null,
      confidence: r.confidence,
      timestamp: r.timestamp,
    }))
  }


  // Branch Lifecycle Tracking

  recordBranchLifecycleEvent(
    sessionId: string,
    helixId: string,
    event: {
      eventType: BranchLifecycleEventType
      metrics?: Record<string, unknown>
      context?: Record<string, unknown>
    }
  ): void {
    this.stmts.insertBranchLifecycleEvent.run({
      session_id: sessionId,
      helix_id: helixId,
      event_type: event.eventType,
      metrics_json: JSON.stringify(event.metrics ?? {}),
      context_json: event.context ? JSON.stringify(event.context) : null,
      timestamp: Date.now(),
    })
    this.logger.debug('Branch lifecycle event recorded', { sessionId, helixId, type: event.eventType })
  }

  getBranchLifecycleEvents(sessionId: string, helixId?: string): BranchLifecycleEventRow[] {
    if (helixId) {
      const rows = this.stmts.selectBranchLifecycleEvents.all({ session_id: sessionId, helix_id: helixId }) as {
        id: number
        session_id: string
        helix_id: string
        event_type: string
        metrics_json: string
        context_json: string | null
        timestamp: number
      }[]
      return rows.map(r => ({
        id: r.id,
        sessionId: r.session_id,
        helixId: r.helix_id,
        eventType: r.event_type as BranchLifecycleEventType,
        metrics: JSON.parse(r.metrics_json),
        context: r.context_json ? JSON.parse(r.context_json) : null,
        timestamp: r.timestamp,
      }))
    }
    // Get all events for session
    const rows = this.db.prepare(
      'SELECT * FROM branch_lifecycle_events WHERE session_id = ? ORDER BY timestamp DESC'
    ).all(sessionId) as {
      id: number
      session_id: string
      helix_id: string
      event_type: string
      metrics_json: string
      context_json: string | null
      timestamp: number
    }[]
    return rows.map(r => ({
      id: r.id,
      sessionId: r.session_id,
      helixId: r.helix_id,
      eventType: r.event_type as BranchLifecycleEventType,
      metrics: JSON.parse(r.metrics_json),
      context: r.context_json ? JSON.parse(r.context_json) : null,
      timestamp: r.timestamp,
    }))
  }


  // Blackboard Archive

  archiveBlackboard(
    sessionId: string,
    helixId: string | null,
    blackboardData: {
      channels: {
        findings: unknown[]
        concerns: unknown[]
        decisions: unknown[]
        artifacts: unknown[]
        requests: unknown[]
      }
      scratchpad?: Record<string, unknown>
      toolLog?: unknown[]
      artifacts?: unknown[]
      plan?: unknown
      report?: unknown
    }
  ): void {
    this.stmts.insertBlackboardArchive.run({
      session_id: sessionId,
      helix_id: helixId,
      channel_data_json: JSON.stringify(blackboardData.channels),
      scratchpad_json: blackboardData.scratchpad ? JSON.stringify(blackboardData.scratchpad) : null,
      tool_log_json: blackboardData.toolLog ? JSON.stringify(blackboardData.toolLog) : null,
      artifacts_json: blackboardData.artifacts ? JSON.stringify(blackboardData.artifacts) : null,
      plan_json: blackboardData.plan ? JSON.stringify(blackboardData.plan) : null,
      report_json: blackboardData.report ? JSON.stringify(blackboardData.report) : null,
      archived_at: Date.now(),
    })
    this.logger.debug('Blackboard archived', { sessionId, helixId, hasChannels: Object.keys(blackboardData.channels).length })
  }

  getBlackboardArchives(sessionId: string, helixId?: string): BlackboardArchiveRow[] {
    let query = 'SELECT * FROM blackboard_archives WHERE session_id = ?'
    const params: (string | null)[] = [sessionId]
    if (helixId) {
      query += ' AND helix_id = ?'
      params.push(helixId)
    }
    query += ' ORDER BY archived_at DESC'
    const rows = this.db.prepare(query).all(...params) as {
      id: number
      session_id: string
      helix_id: string | null
      channel_data_json: string
      scratchpad_json: string | null
      tool_log_json: string | null
      artifacts_json: string | null
      plan_json: string | null
      report_json: string | null
      archived_at: number
    }[]
    return rows.map(r => ({
      id: r.id,
      sessionId: r.session_id,
      helixId: r.helix_id,
      channelData: JSON.parse(r.channel_data_json),
      scratchpad: r.scratchpad_json ? JSON.parse(r.scratchpad_json) : null,
      toolLog: r.tool_log_json ? JSON.parse(r.tool_log_json) : null,
      artifacts: r.artifacts_json ? JSON.parse(r.artifacts_json) : null,
      plan: r.plan_json ? JSON.parse(r.plan_json) : null,
      report: r.report_json ? JSON.parse(r.report_json) : null,
      archivedAt: r.archived_at,
    }))
  }


  // Training Signals

  recordTrainingSignal(
    sessionId: string,
    signal: {
      signalType: TrainingSignalType
      sourceHelixId?: string
      data: Record<string, unknown>
      qualityScore?: number
    }
  ): void {
    this.stmts.insertTrainingSignal.run({
      session_id: sessionId,
      signal_type: signal.signalType,
      source_helix_id: signal.sourceHelixId ?? null,
      data_json: JSON.stringify(signal.data),
      quality_score: signal.qualityScore ?? null,
      extracted_at: Date.now(),
    })
    this.logger.debug('Training signal recorded', { sessionId, type: signal.signalType })
  }

  getTrainingSignals(sessionId: string, signalType?: TrainingSignalType): TrainingSignalRow[] {
    let query = 'SELECT * FROM training_signals WHERE session_id = ?'
    const params: (string | TrainingSignalType)[] = [sessionId]
    if (signalType) {
      query += ' AND signal_type = ?'
      params.push(signalType)
    }
    query += ' ORDER BY extracted_at DESC'
    const rows = this.db.prepare(query).all(...params) as {
      id: number
      session_id: string
      signal_type: string
      source_helix_id: string | null
      data_json: string
      quality_score: number | null
      extracted_at: number
    }[]
    return rows.map(r => ({
      id: r.id,
      sessionId: r.session_id,
      signalType: r.signal_type as TrainingSignalType,
      sourceHelixId: r.source_helix_id,
      data: JSON.parse(r.data_json),
      qualityScore: r.quality_score,
      extractedAt: r.extracted_at,
    }))
  }


  // Locus Memory Persistence

  /**
   * Get a LocusMemoryPersistence adapter for the Locus Memory module.
   * Decouples the memory module from the full ConstellationStore.
   */
  getLocusMemoryPersistence(): LocusMemoryPersistence {
    return {
      loadMemories: () => this.loadLocusMemories(),
      saveMemory: (entry) => this.saveLocusMemory(entry),
      updateMemory: (entry) => this.updateLocusMemory(entry),
      deleteMemory: (id) => this.deleteLocusMemory(id),
    }
  }

  private loadLocusMemories(): LocusMemoryEntry[] {
    const rows = this.stmts.selectActiveLocusMemories.all() as RawLocusMemoryRow[]
    return rows.map(r => ({
      id: r.id,
      content: r.content,
      memoryType: r.memory_type as LocusMemoryEntry['memoryType'],
      confidence: r.confidence,
      luminance: r.luminance,
      phase: r.phase as LocusMemoryEntry['phase'],
      originSessionId: r.origin_session_id,
      sourceHelixId: r.source_helix_id,
      sourceGoal: r.source_goal,
      relevantFiles: JSON.parse(r.relevant_files_json || '[]'),
      confirmations: r.confirmations,
      contradictions: r.contradictions,
      recallCount: r.recall_count,
      createdAt: r.created_at,
      lastRecalledAt: r.last_recalled_at,
      lastUpdatedAt: r.last_updated_at,
    }))
  }

  private saveLocusMemory(entry: LocusMemoryEntry): void {
    this.stmts.insertLocusMemory.run({
      id: entry.id,
      content: entry.content,
      memory_type: entry.memoryType,
      confidence: entry.confidence,
      luminance: entry.luminance,
      phase: entry.phase,
      origin_session_id: entry.originSessionId,
      source_helix_id: entry.sourceHelixId,
      source_goal: entry.sourceGoal,
      relevant_files_json: JSON.stringify(entry.relevantFiles),
      confirmations: entry.confirmations,
      contradictions: entry.contradictions,
      recall_count: entry.recallCount,
      created_at: entry.createdAt,
      last_recalled_at: entry.lastRecalledAt,
      last_updated_at: entry.lastUpdatedAt,
    })
  }

  private updateLocusMemory(entry: LocusMemoryEntry): void {
    this.stmts.updateLocusMemory.run({
      id: entry.id,
      confidence: entry.confidence,
      phase: entry.phase,
      confirmations: entry.confirmations,
      contradictions: entry.contradictions,
      recall_count: entry.recallCount,
      last_recalled_at: entry.lastRecalledAt,
      last_updated_at: entry.lastUpdatedAt,
    })
  }

  private deleteLocusMemory(id: string): void {
    this.stmts.deleteLocusMemory.run(id)
  }
}


interface RawLocusMemoryRow {
  id: string
  content: string
  memory_type: string
  confidence: number
  luminance: number
  phase: string
  origin_session_id: string
  source_helix_id: string
  source_goal: string
  relevant_files_json: string
  confirmations: number
  contradictions: number
  recall_count: number
  created_at: number
  last_recalled_at: number | null
  last_updated_at: number
}
