/**
 * Training Store — SQLite schema initialization and low-level data access
 * for the training warehouse (training.db).
 *
 * Owns:
 * - Schema creation and migration
 * - Prepared statement cache
 * - Primitive CRUD for every table
 * - FTS5 indexing of chunks
 *
 * Does NOT own:
 * - Ingestion orchestration (training-ingest.ts)
 * - LLM annotation (training-tagger.ts)
 * - Search and export (training-reader.ts)
 */

import Database from 'better-sqlite3'
import * as path from 'node:path'
import * as fs from 'node:fs'
import type { ILogger } from '../../../types/interfaces.js'
import type {
  TrainingObject,
  TrainingSession,
  TrainingTurn,
  TrainingMessage,
  TrainingChunk,
  TrainingToolCall,
  TrainingReasoningTrace,
  TrainingReasoningStep,
  TrainingEvent,
  TrainingArtifact,
  ObjectEdge,
  TaxonomyLabel,
  ObjectLabel,
  AnnotationRun,
  AnnotationEvidence,
  QualityMetric,
  PrivacySpan,
  ModelRecord,
  ObjectEmbedding,
  IngestCheckpoint,
  TrainingWarehouseStats,
} from './training-types.js'

// SCHEMA VERSION — bump on every DDL change

const SCHEMA_VERSION = '1.0.0'

// DDL

const DDL = `
-- ── PRAGMAs ──────────────────────────────────────────────────────────────
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
PRAGMA cache_size = -64000;

-- ── Schema Version ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS schema_meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
INSERT OR IGNORE INTO schema_meta (key, value) VALUES ('version', '${SCHEMA_VERSION}');
INSERT OR IGNORE INTO schema_meta (key, value) VALUES ('created_at', datetime('now'));

-- ── Models Registry ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS models (
  model_id       TEXT PRIMARY KEY,
  provider       TEXT NOT NULL,
  model_name     TEXT NOT NULL,
  version        TEXT,
  fingerprint    TEXT,
  role           TEXT NOT NULL DEFAULT 'producer',  -- producer | annotator | embedder
  first_seen_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_models_provider ON models(provider);

-- ── Objects — universal registry ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS objects (
  object_id        TEXT PRIMARY KEY,
  object_type      TEXT NOT NULL,
  subtype          TEXT,
  parent_object_id TEXT,
  root_session_id  TEXT,
  ref_key          TEXT NOT NULL,
  source_db        TEXT,
  source_id        TEXT,
  created_at       INTEGER NOT NULL,
  ingested_at      INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_objects_type       ON objects(object_type);
CREATE INDEX IF NOT EXISTS idx_objects_parent     ON objects(parent_object_id);
CREATE INDEX IF NOT EXISTS idx_objects_root       ON objects(root_session_id);
CREATE INDEX IF NOT EXISTS idx_objects_source     ON objects(source_db, source_id);
CREATE INDEX IF NOT EXISTS idx_objects_ref        ON objects(ref_key);
CREATE INDEX IF NOT EXISTS idx_objects_created    ON objects(created_at);

-- ── Sessions ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sessions (
  object_id          TEXT PRIMARY KEY REFERENCES objects(object_id),
  session_type       TEXT NOT NULL,
  channel            TEXT,
  parent_session_id  TEXT,
  started_at         INTEGER NOT NULL,
  ended_at           INTEGER,
  status             TEXT NOT NULL DEFAULT 'active',
  turn_count         INTEGER NOT NULL DEFAULT 0,
  total_tokens       INTEGER NOT NULL DEFAULT 0,
  model_primary      TEXT,
  provider_primary   TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_type   ON sessions(session_type);
CREATE INDEX IF NOT EXISTS idx_sessions_parent ON sessions(parent_session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);

-- ── Turns ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS turns (
  object_id       TEXT PRIMARY KEY REFERENCES objects(object_id),
  session_id      TEXT NOT NULL,
  sequence        INTEGER NOT NULL,
  role            TEXT NOT NULL,
  subrole         TEXT,
  branch_id       TEXT,
  prev_turn_id    TEXT,
  next_turn_id    TEXT,
  parent_turn_id  TEXT,
  has_tool_calls  INTEGER NOT NULL DEFAULT 0,
  has_reasoning   INTEGER NOT NULL DEFAULT 0,
  has_error       INTEGER NOT NULL DEFAULT 0,
  is_recovery     INTEGER NOT NULL DEFAULT 0,
  outcome         TEXT,
  token_count_in  INTEGER,
  token_count_out INTEGER,
  latency_ms      INTEGER,
  started_at      INTEGER NOT NULL,
  ended_at        INTEGER
);
CREATE INDEX IF NOT EXISTS idx_turns_session  ON turns(session_id, sequence);
CREATE INDEX IF NOT EXISTS idx_turns_role     ON turns(role);

-- ── Messages ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS messages (
  object_id         TEXT PRIMARY KEY REFERENCES objects(object_id),
  turn_id           TEXT NOT NULL,
  sequence          INTEGER NOT NULL,
  role              TEXT NOT NULL,
  content_type      TEXT NOT NULL,
  content_text      TEXT,
  content_json      TEXT,
  producer_model    TEXT,
  producer_provider TEXT,
  token_count       INTEGER,
  is_error          INTEGER NOT NULL DEFAULT 0,
  error_class       TEXT
);
CREATE INDEX IF NOT EXISTS idx_messages_turn ON messages(turn_id, sequence);

-- ── Search Chunks — the atomic training/retrieval unit ───────────────────
CREATE TABLE IF NOT EXISTS chunks (
  chunk_id       TEXT PRIMARY KEY,
  object_id      TEXT NOT NULL,
  chunk_type     TEXT NOT NULL,
  chunk_ref      TEXT NOT NULL,
  sequence       INTEGER NOT NULL,
  text           TEXT NOT NULL,
  token_estimate INTEGER NOT NULL DEFAULT 0,
  language       TEXT,
  role           TEXT,
  session_id     TEXT
);
CREATE INDEX IF NOT EXISTS idx_chunks_object  ON chunks(object_id);
CREATE INDEX IF NOT EXISTS idx_chunks_ref     ON chunks(chunk_ref);
CREATE INDEX IF NOT EXISTS idx_chunks_type    ON chunks(chunk_type);
CREATE INDEX IF NOT EXISTS idx_chunks_session ON chunks(session_id);

-- FTS5 for chunk full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  chunk_ref,
  chunk_type,
  role,
  text,
  content='chunks',
  content_rowid='rowid',
  tokenize='porter unicode61'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
  INSERT INTO chunks_fts(rowid, chunk_ref, chunk_type, role, text)
  VALUES (new.rowid, new.chunk_ref, new.chunk_type, new.role, new.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, chunk_ref, chunk_type, role, text)
  VALUES ('delete', old.rowid, old.chunk_ref, old.chunk_type, old.role, old.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, chunk_ref, chunk_type, role, text)
  VALUES ('delete', old.rowid, old.chunk_ref, old.chunk_type, old.role, old.text);
  INSERT INTO chunks_fts(rowid, chunk_ref, chunk_type, role, text)
  VALUES (new.rowid, new.chunk_ref, new.chunk_type, new.role, new.text);
END;

-- ── Tool Calls ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tool_calls (
  object_id    TEXT PRIMARY KEY REFERENCES objects(object_id),
  turn_id      TEXT NOT NULL,
  message_id   TEXT,
  tool_name    TEXT NOT NULL,
  tool_use_id  TEXT,
  input_json   TEXT,
  output_json  TEXT,
  status       TEXT NOT NULL DEFAULT 'success',
  error_class  TEXT,
  duration_ms  INTEGER,
  sequence     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_tool_calls_turn ON tool_calls(turn_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_name ON tool_calls(tool_name);
CREATE INDEX IF NOT EXISTS idx_tool_calls_status ON tool_calls(status);

-- ── Reasoning Traces ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reasoning_traces (
  object_id          TEXT PRIMARY KEY REFERENCES objects(object_id),
  turn_id            TEXT NOT NULL,
  reasoning_type     TEXT NOT NULL,
  depth              TEXT,
  synthesis          TEXT,
  decision           TEXT,
  overall_confidence REAL,
  step_count         INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_reasoning_turn ON reasoning_traces(turn_id);
CREATE INDEX IF NOT EXISTS idx_reasoning_type ON reasoning_traces(reasoning_type);

-- ── Reasoning Steps ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reasoning_steps (
  object_id   TEXT PRIMARY KEY REFERENCES objects(object_id),
  trace_id    TEXT NOT NULL,
  step_type   TEXT NOT NULL,
  sequence    INTEGER NOT NULL,
  content     TEXT NOT NULL,
  confidence  REAL,
  tokens_used INTEGER
);
CREATE INDEX IF NOT EXISTS idx_rsteps_trace ON reasoning_steps(trace_id, sequence);

-- ── Events ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS events (
  object_id     TEXT PRIMARY KEY REFERENCES objects(object_id),
  session_id    TEXT,
  event_type    TEXT NOT NULL,
  event_subtype TEXT,
  content_json  TEXT,
  severity      TEXT,
  timestamp     INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_type    ON events(event_type);

-- ── Artifacts ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS artifacts (
  object_id     TEXT PRIMARY KEY REFERENCES objects(object_id),
  session_id    TEXT,
  artifact_type TEXT NOT NULL,
  name          TEXT,
  content_text  TEXT,
  content_json  TEXT,
  mime_type     TEXT,
  byte_size     INTEGER
);
CREATE INDEX IF NOT EXISTS idx_artifacts_session ON artifacts(session_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_type    ON artifacts(artifact_type);

-- ── Object Edges (graph) ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS object_edges (
  source_id     TEXT NOT NULL,
  target_id     TEXT NOT NULL,
  relation      TEXT NOT NULL,
  weight        REAL NOT NULL DEFAULT 1.0,
  metadata_json TEXT,
  PRIMARY KEY (source_id, target_id, relation)
);
CREATE INDEX IF NOT EXISTS idx_edges_target   ON object_edges(target_id);
CREATE INDEX IF NOT EXISTS idx_edges_relation ON object_edges(relation);

-- ── Taxonomy Namespaces ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS taxonomy_namespaces (
  namespace   TEXT PRIMARY KEY,
  description TEXT,
  created_at  INTEGER NOT NULL
);
INSERT OR IGNORE INTO taxonomy_namespaces (namespace, description, created_at) VALUES
  ('topic',               'Subject matter topics',                             strftime('%s','now') * 1000),
  ('task',                'Task types (coding, debugging, explaining, etc.)',   strftime('%s','now') * 1000),
  ('domain',              'Knowledge domains (frontend, backend, devops)',      strftime('%s','now') * 1000),
  ('interaction_pattern', 'Conversation patterns (multi-turn, Q&A, etc.)',     strftime('%s','now') * 1000),
  ('tool',                'Tool categories',                                   strftime('%s','now') * 1000),
  ('error_type',          'Error taxonomies',                                  strftime('%s','now') * 1000),
  ('quality',             'Quality signals',                                   strftime('%s','now') * 1000),
  ('privacy',             'Privacy/sensitivity levels',                        strftime('%s','now') * 1000),
  ('memory_class',        'Cognitive memory classes (episodic/semantic/procedural)', strftime('%s','now') * 1000),
  ('training_value',      'Training value assessment',                         strftime('%s','now') * 1000);

-- ── Taxonomy Labels ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS taxonomy_labels (
  label_id        TEXT PRIMARY KEY,
  namespace       TEXT NOT NULL REFERENCES taxonomy_namespaces(namespace),
  name            TEXT NOT NULL,
  display_name    TEXT,
  description     TEXT,
  parent_label_id TEXT,
  UNIQUE(namespace, name)
);
CREATE INDEX IF NOT EXISTS idx_labels_namespace ON taxonomy_labels(namespace);

-- Seed core labels
INSERT OR IGNORE INTO taxonomy_labels (label_id, namespace, name, display_name) VALUES
  -- memory classes
  ('mc_episodic',   'memory_class',   'episodic',   'Episodic Memory'),
  ('mc_semantic',   'memory_class',   'semantic',   'Semantic Memory'),
  ('mc_procedural', 'memory_class',   'procedural', 'Procedural Memory'),
  -- training value
  ('tv_high',       'training_value', 'high',       'High Training Value'),
  ('tv_medium',     'training_value', 'medium',     'Medium Training Value'),
  ('tv_low',        'training_value', 'low',        'Low Training Value'),
  ('tv_skip',       'training_value', 'skip',       'Skip (not useful)'),
  -- task types
  ('task_coding',     'task', 'coding',      'Coding / Implementation'),
  ('task_debugging',  'task', 'debugging',   'Debugging'),
  ('task_explaining', 'task', 'explaining',  'Explaining Code'),
  ('task_refactoring','task', 'refactoring', 'Refactoring'),
  ('task_reviewing',  'task', 'reviewing',   'Code Review'),
  ('task_planning',   'task', 'planning',    'Planning / Architecture'),
  ('task_research',   'task', 'research',    'Research / Investigation'),
  ('task_config',     'task', 'config',      'Configuration / Setup'),
  ('task_testing',    'task', 'testing',     'Testing'),
  -- interaction patterns
  ('ip_single_turn',  'interaction_pattern', 'single_turn',  'Single Turn Q&A'),
  ('ip_multi_turn',   'interaction_pattern', 'multi_turn',   'Multi-Turn Conversation'),
  ('ip_tool_heavy',   'interaction_pattern', 'tool_heavy',   'Tool-Heavy Interaction'),
  ('ip_reasoning',    'interaction_pattern', 'reasoning',    'Deep Reasoning'),
  ('ip_delegation',   'interaction_pattern', 'delegation',   'Agent Delegation'),
  ('ip_error_recovery','interaction_pattern','error_recovery','Error Recovery'),
  -- quality signals
  ('q_exemplary',   'quality', 'exemplary',    'Exemplary Quality'),
  ('q_good',        'quality', 'good',         'Good Quality'),
  ('q_acceptable',  'quality', 'acceptable',   'Acceptable Quality'),
  ('q_poor',        'quality', 'poor',         'Poor Quality'),
  ('q_toxic',       'quality', 'toxic',        'Toxic / Harmful');

-- ── Object Labels (many-to-many) ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS object_labels (
  object_id         TEXT NOT NULL,
  label_id          TEXT NOT NULL REFERENCES taxonomy_labels(label_id),
  confidence        REAL NOT NULL DEFAULT 1.0,
  source            TEXT NOT NULL DEFAULT 'heuristic',  -- heuristic | llm | human | imported
  annotation_run_id TEXT,
  is_primary        INTEGER NOT NULL DEFAULT 0,
  created_at        INTEGER NOT NULL,
  PRIMARY KEY (object_id, label_id, source)
);
CREATE INDEX IF NOT EXISTS idx_ol_label  ON object_labels(label_id);
CREATE INDEX IF NOT EXISTS idx_ol_source ON object_labels(source);

-- ── Annotation Runs ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS annotation_runs (
  run_id           TEXT PRIMARY KEY,
  model            TEXT NOT NULL,
  provider         TEXT,
  prompt_version   TEXT NOT NULL,
  input_hash       TEXT,
  target_object_id TEXT,
  target_scope     TEXT NOT NULL,
  tokens_used      INTEGER,
  cost_estimate    REAL,
  status           TEXT NOT NULL DEFAULT 'pending',
  response_json    TEXT,
  started_at       INTEGER NOT NULL,
  completed_at     INTEGER
);
CREATE INDEX IF NOT EXISTS idx_ar_status ON annotation_runs(status);
CREATE INDEX IF NOT EXISTS idx_ar_target ON annotation_runs(target_object_id);

-- ── Annotation Evidence ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS annotation_evidence (
  evidence_id TEXT PRIMARY KEY,
  run_id      TEXT NOT NULL REFERENCES annotation_runs(run_id),
  label_id    TEXT NOT NULL REFERENCES taxonomy_labels(label_id),
  chunk_id    TEXT,
  object_id   TEXT NOT NULL,
  score       REAL NOT NULL DEFAULT 1.0,
  explanation TEXT
);
CREATE INDEX IF NOT EXISTS idx_ae_run    ON annotation_evidence(run_id);
CREATE INDEX IF NOT EXISTS idx_ae_object ON annotation_evidence(object_id);

-- ── Quality Metrics (tall table) ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS quality_metrics (
  object_id         TEXT NOT NULL,
  metric            TEXT NOT NULL,
  value             REAL NOT NULL,
  source            TEXT NOT NULL DEFAULT 'heuristic',
  annotation_run_id TEXT,
  updated_at        INTEGER NOT NULL,
  PRIMARY KEY (object_id, metric, source)
);
CREATE INDEX IF NOT EXISTS idx_qm_metric ON quality_metrics(metric);

-- ── Privacy Spans ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS privacy_spans (
  span_id      TEXT PRIMARY KEY,
  chunk_id     TEXT NOT NULL,
  start_offset INTEGER NOT NULL,
  end_offset   INTEGER NOT NULL,
  category     TEXT NOT NULL,
  severity     TEXT NOT NULL DEFAULT 'medium',
  redacted     INTEGER NOT NULL DEFAULT 0,
  replacement  TEXT
);
CREATE INDEX IF NOT EXISTS idx_ps_chunk ON privacy_spans(chunk_id);
CREATE INDEX IF NOT EXISTS idx_ps_category ON privacy_spans(category);

-- ── Object Embeddings ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS object_embeddings (
  object_id  TEXT NOT NULL,
  model_id   TEXT NOT NULL,
  vector_json TEXT NOT NULL,
  dimensions INTEGER NOT NULL,
  created_at INTEGER NOT NULL,
  PRIMARY KEY (object_id, model_id)
);

-- ── Ingest Checkpoints ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ingest_checkpoints (
  source_db         TEXT NOT NULL,
  source_table      TEXT NOT NULL,
  last_processed_id TEXT,
  last_processed_ts INTEGER,
  rows_ingested     INTEGER NOT NULL DEFAULT 0,
  updated_at        INTEGER NOT NULL,
  PRIMARY KEY (source_db, source_table)
);
`

// STORE CLASS

export class TrainingStore {
  readonly db: Database.Database
  private readonly logger: ILogger
  private stmtCache = new Map<string, Database.Statement>()

  constructor(dataDir: string, logger: ILogger) {
    this.logger = logger.child('training-store')

    fs.mkdirSync(dataDir, { recursive: true })
    const dbPath = path.join(dataDir, 'training.db')

    this.db = new Database(dbPath)
    this.initSchema()
    this.logger.info('Training warehouse initialized', { path: dbPath, version: SCHEMA_VERSION })
  }


  private initSchema(): void {
    // Execute DDL line by line (split on semicolons that end a statement)
    const statements = DDL
      .split(';')
      .map(s => s.trim())
      .filter(s => s.length > 0)

    try {
      this.db.transaction(() => {
        for (const sql of statements) {
          try {
            this.db.exec(sql + ';')
          } catch (err) {
            // Ignore "already exists" errors for idempotency
            const msg = String(err)
            if (!msg.includes('already exists')) {
              this.logger.warn('Schema statement failed', { sql: sql.slice(0, 120), error: msg })
            }
          }
        }
      })()
    } catch (err) {
      // DDL can cause implicit commits in SQLite, breaking the transaction wrapper.
      // This is benign — each statement executed individually regardless.
      const msg = String(err)
      if (msg.includes('no transaction is active') || msg.includes('cannot commit')) {
        this.logger.debug('Schema init: transaction wrapper exited (DDL implicit commits)', { error: msg })
      } else {
        this.logger.warn('Schema init failed', { error: msg })
      }
    }
  }


  private stmt(key: string, sql: string): Database.Statement {
    let s = this.stmtCache.get(key)
    if (!s) {
      s = this.db.prepare(sql)
      this.stmtCache.set(key, s)
    }
    return s
  }


  static genId(prefix: string): string {
    return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
  }


  transaction<T>(fn: () => T): T {
    return this.db.transaction(fn)()
  }

  // OBJECTS (universal registry)

  insertObject(obj: TrainingObject): void {
    this.stmt('ins_object', `
      INSERT OR IGNORE INTO objects
        (object_id, object_type, subtype, parent_object_id, root_session_id,
         ref_key, source_db, source_id, created_at, ingested_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      obj.object_id, obj.object_type, obj.subtype,
      obj.parent_object_id, obj.root_session_id,
      obj.ref_key, obj.source_db, obj.source_id,
      obj.created_at, obj.ingested_at,
    )
  }

  getObject(objectId: string): TrainingObject | undefined {
    return this.stmt('get_object', `
      SELECT * FROM objects WHERE object_id = ?
    `).get(objectId) as TrainingObject | undefined
  }

  objectExists(sourceDb: string, sourceId: string): boolean {
    const row = this.stmt('obj_exists', `
      SELECT 1 FROM objects WHERE source_db = ? AND source_id = ? LIMIT 1
    `).get(sourceDb, sourceId) as { '1': number } | undefined
    return !!row
  }

  // SESSIONS

  insertSession(sess: TrainingSession): void {
    this.stmt('ins_session', `
      INSERT OR IGNORE INTO sessions
        (object_id, session_type, channel, parent_session_id, started_at, ended_at,
         status, turn_count, total_tokens, model_primary, provider_primary)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      sess.object_id, sess.session_type, sess.channel,
      sess.parent_session_id, sess.started_at, sess.ended_at,
      sess.status, sess.turn_count, sess.total_tokens,
      sess.model_primary, sess.provider_primary,
    )
  }

  // TURNS

  insertTurn(turn: TrainingTurn): void {
    this.stmt('ins_turn', `
      INSERT OR IGNORE INTO turns
        (object_id, session_id, sequence, role, subrole, branch_id,
         prev_turn_id, next_turn_id, parent_turn_id,
         has_tool_calls, has_reasoning, has_error, is_recovery,
         outcome, token_count_in, token_count_out, latency_ms,
         started_at, ended_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      turn.object_id, turn.session_id, turn.sequence,
      turn.role, turn.subrole, turn.branch_id,
      turn.prev_turn_id, turn.next_turn_id, turn.parent_turn_id,
      turn.has_tool_calls, turn.has_reasoning, turn.has_error, turn.is_recovery,
      turn.outcome, turn.token_count_in, turn.token_count_out, turn.latency_ms,
      turn.started_at, turn.ended_at,
    )
  }

  // MESSAGES

  insertMessage(msg: TrainingMessage): void {
    this.stmt('ins_message', `
      INSERT OR IGNORE INTO messages
        (object_id, turn_id, sequence, role, content_type,
         content_text, content_json, producer_model, producer_provider,
         token_count, is_error, error_class)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      msg.object_id, msg.turn_id, msg.sequence,
      msg.role, msg.content_type,
      msg.content_text, msg.content_json,
      msg.producer_model, msg.producer_provider,
      msg.token_count, msg.is_error, msg.error_class,
    )
  }

  // CHUNKS

  insertChunk(chunk: TrainingChunk): void {
    this.stmt('ins_chunk', `
      INSERT OR IGNORE INTO chunks
        (chunk_id, object_id, chunk_type, chunk_ref, sequence,
         text, token_estimate, language, role, session_id)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      chunk.chunk_id, chunk.object_id, chunk.chunk_type, chunk.chunk_ref,
      chunk.sequence, chunk.text, chunk.token_estimate,
      chunk.language, chunk.role, chunk.session_id,
    )
  }

  // TOOL CALLS

  insertToolCall(tc: TrainingToolCall): void {
    this.stmt('ins_tool_call', `
      INSERT OR IGNORE INTO tool_calls
        (object_id, turn_id, message_id, tool_name, tool_use_id,
         input_json, output_json, status, error_class, duration_ms, sequence)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      tc.object_id, tc.turn_id, tc.message_id,
      tc.tool_name, tc.tool_use_id,
      tc.input_json, tc.output_json,
      tc.status, tc.error_class, tc.duration_ms, tc.sequence,
    )
  }

  // REASONING

  insertReasoningTrace(trace: TrainingReasoningTrace): void {
    this.stmt('ins_rtrace', `
      INSERT OR IGNORE INTO reasoning_traces
        (object_id, turn_id, reasoning_type, depth, synthesis, decision,
         overall_confidence, step_count)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      trace.object_id, trace.turn_id, trace.reasoning_type,
      trace.depth, trace.synthesis, trace.decision,
      trace.overall_confidence, trace.step_count,
    )
  }

  insertReasoningStep(step: TrainingReasoningStep): void {
    this.stmt('ins_rstep', `
      INSERT OR IGNORE INTO reasoning_steps
        (object_id, trace_id, step_type, sequence, content, confidence, tokens_used)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(
      step.object_id, step.trace_id, step.step_type,
      step.sequence, step.content, step.confidence, step.tokens_used,
    )
  }

  // EVENTS & ARTIFACTS

  insertEvent(evt: TrainingEvent): void {
    this.stmt('ins_event', `
      INSERT OR IGNORE INTO events
        (object_id, session_id, event_type, event_subtype, content_json, severity, timestamp)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(
      evt.object_id, evt.session_id, evt.event_type,
      evt.event_subtype, evt.content_json, evt.severity, evt.timestamp,
    )
  }

  insertArtifact(art: TrainingArtifact): void {
    this.stmt('ins_artifact', `
      INSERT OR IGNORE INTO artifacts
        (object_id, session_id, artifact_type, name, content_text, content_json, mime_type, byte_size)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      art.object_id, art.session_id, art.artifact_type,
      art.name, art.content_text, art.content_json, art.mime_type, art.byte_size,
    )
  }

  // EDGES

  insertEdge(edge: ObjectEdge): void {
    this.stmt('ins_edge', `
      INSERT OR IGNORE INTO object_edges
        (source_id, target_id, relation, weight, metadata_json)
      VALUES (?, ?, ?, ?, ?)
    `).run(edge.source_id, edge.target_id, edge.relation, edge.weight, edge.metadata_json)
  }

  // TAXONOMY & LABELS

  ensureLabel(namespace: string, name: string, displayName?: string, description?: string): string {
    const labelId = `${namespace}:${name}`.replace(/[^a-z0-9:_-]/gi, '_').toLowerCase()

    this.stmt('upsert_label', `
      INSERT OR IGNORE INTO taxonomy_labels
        (label_id, namespace, name, display_name, description)
      VALUES (?, ?, ?, ?, ?)
    `).run(labelId, namespace, name.toLowerCase(), displayName || null, description || null)

    return labelId
  }

  attachLabel(objectId: string, labelId: string, opts?: {
    confidence?: number; source?: string; runId?: string; isPrimary?: boolean
  }): void {
    this.stmt('ins_ol', `
      INSERT OR REPLACE INTO object_labels
        (object_id, label_id, confidence, source, annotation_run_id, is_primary, created_at)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(
      objectId, labelId,
      opts?.confidence ?? 1.0,
      opts?.source ?? 'heuristic',
      opts?.runId ?? null,
      opts?.isPrimary ? 1 : 0,
      Date.now(),
    )
  }

  getLabels(objectId: string): Array<{ label_id: string; namespace: string; name: string; confidence: number; source: string }> {
    return this.stmt('get_labels', `
      SELECT ol.label_id, tl.namespace, tl.name, ol.confidence, ol.source
      FROM object_labels ol
      JOIN taxonomy_labels tl ON tl.label_id = ol.label_id
      WHERE ol.object_id = ?
      ORDER BY ol.confidence DESC
    `).all(objectId) as any[]
  }

  // ANNOTATION RUNS

  insertAnnotationRun(run: AnnotationRun): void {
    this.stmt('ins_ar', `
      INSERT OR IGNORE INTO annotation_runs
        (run_id, model, provider, prompt_version, input_hash,
         target_object_id, target_scope, tokens_used, cost_estimate,
         status, response_json, started_at, completed_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      run.run_id, run.model, run.provider, run.prompt_version,
      run.input_hash, run.target_object_id, run.target_scope,
      run.tokens_used, run.cost_estimate,
      run.status, run.response_json, run.started_at, run.completed_at,
    )
  }

  completeAnnotationRun(runId: string, responseJson: string, tokensUsed: number): void {
    this.stmt('complete_ar', `
      UPDATE annotation_runs
      SET status = 'completed', response_json = ?, tokens_used = ?, completed_at = ?
      WHERE run_id = ?
    `).run(responseJson, tokensUsed, Date.now(), runId)
  }

  failAnnotationRun(runId: string, error: string): void {
    this.stmt('fail_ar', `
      UPDATE annotation_runs
      SET status = 'failed', response_json = ?, completed_at = ?
      WHERE run_id = ?
    `).run(JSON.stringify({ error }), Date.now(), runId)
  }

  // ANNOTATION EVIDENCE

  insertEvidence(ev: AnnotationEvidence): void {
    this.stmt('ins_ae', `
      INSERT OR IGNORE INTO annotation_evidence
        (evidence_id, run_id, label_id, chunk_id, object_id, score, explanation)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(ev.evidence_id, ev.run_id, ev.label_id, ev.chunk_id, ev.object_id, ev.score, ev.explanation)
  }

  // QUALITY METRICS

  setQualityMetric(qm: QualityMetric): void {
    this.stmt('upsert_qm', `
      INSERT OR REPLACE INTO quality_metrics
        (object_id, metric, value, source, annotation_run_id, updated_at)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(qm.object_id, qm.metric, qm.value, qm.source, qm.annotation_run_id, qm.updated_at)
  }

  getQualityMetrics(objectId: string): QualityMetric[] {
    return this.stmt('get_qm', `
      SELECT * FROM quality_metrics WHERE object_id = ?
    `).all(objectId) as QualityMetric[]
  }

  // PRIVACY SPANS

  insertPrivacySpan(span: PrivacySpan): void {
    this.stmt('ins_ps', `
      INSERT OR IGNORE INTO privacy_spans
        (span_id, chunk_id, start_offset, end_offset, category, severity, redacted, replacement)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      span.span_id, span.chunk_id, span.start_offset, span.end_offset,
      span.category, span.severity, span.redacted, span.replacement,
    )
  }

  // MODELS

  ensureModel(provider: string, modelName: string, role = 'producer'): string {
    const modelId = `${provider}:${modelName}`.replace(/[^a-z0-9:_.-]/gi, '_').toLowerCase()
    this.stmt('upsert_model', `
      INSERT OR IGNORE INTO models
        (model_id, provider, model_name, role, first_seen_at)
      VALUES (?, ?, ?, ?, ?)
    `).run(modelId, provider, modelName, role, Date.now())
    return modelId
  }

  // EMBEDDINGS

  insertEmbedding(emb: ObjectEmbedding): void {
    this.stmt('ins_emb', `
      INSERT OR REPLACE INTO object_embeddings
        (object_id, model_id, vector_json, dimensions, created_at)
      VALUES (?, ?, ?, ?, ?)
    `).run(emb.object_id, emb.model_id, emb.vector_json, emb.dimensions, emb.created_at)
  }

  // INGEST CHECKPOINTS

  getCheckpoint(sourceDb: string, sourceTable: string): IngestCheckpoint | undefined {
    return this.stmt('get_cp', `
      SELECT * FROM ingest_checkpoints WHERE source_db = ? AND source_table = ?
    `).get(sourceDb, sourceTable) as IngestCheckpoint | undefined
  }

  setCheckpoint(cp: IngestCheckpoint): void {
    this.stmt('upsert_cp', `
      INSERT OR REPLACE INTO ingest_checkpoints
        (source_db, source_table, last_processed_id, last_processed_ts, rows_ingested, updated_at)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(cp.source_db, cp.source_table, cp.last_processed_id, cp.last_processed_ts, cp.rows_ingested, cp.updated_at)
  }

  // STATS

  getStats(): TrainingWarehouseStats {
    const totalObjects = (this.db.prepare('SELECT COUNT(*) as c FROM objects').get() as any).c
    const totalChunks = (this.db.prepare('SELECT COUNT(*) as c FROM chunks').get() as any).c
    const totalLabels = (this.db.prepare('SELECT COUNT(*) as c FROM object_labels').get() as any).c
    const totalEdges = (this.db.prepare('SELECT COUNT(*) as c FROM object_edges').get() as any).c
    const totalRuns = (this.db.prepare('SELECT COUNT(*) as c FROM annotation_runs').get() as any).c
    const totalEmbs = (this.db.prepare('SELECT COUNT(*) as c FROM object_embeddings').get() as any).c
    const totalSpans = (this.db.prepare('SELECT COUNT(*) as c FROM privacy_spans').get() as any).c

    const byTypeRows = this.db.prepare(`
      SELECT object_type, COUNT(*) as c FROM objects GROUP BY object_type
    `).all() as Array<{ object_type: string; c: number }>

    const byType: Record<string, number> = {}
    for (const row of byTypeRows) byType[row.object_type] = row.c

    // DB file size
    const dbPath = this.db.pragma('database_list') as Array<{ file: string }>
    let dbSizeBytes = 0
    try {
      if (dbPath[0]?.file) {
        dbSizeBytes = fs.statSync(dbPath[0].file).size
      }
    } catch { /* ignore */ }

    return {
      total_objects: totalObjects,
      by_type: byType,
      total_chunks: totalChunks,
      total_labels: totalLabels,
      total_edges: totalEdges,
      total_annotation_runs: totalRuns,
      total_embeddings: totalEmbs,
      total_privacy_spans: totalSpans,
      schema_version: SCHEMA_VERSION,
      db_size_bytes: dbSizeBytes,
    }
  }

  // CLEANUP

  close(): void {
    try {
      this.db.pragma('wal_checkpoint(TRUNCATE)')
    } catch { /* ignore */ }
    this.stmtCache.clear()
    this.db.close()
    this.logger.info('Training warehouse closed')
  }
}
