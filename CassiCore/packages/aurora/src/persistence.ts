/**
 * Aurora Persistence — cross-session state continuity.
 *
 * Persists Aurora's operational state (claustrum graph, reasoning log, focus
 * stack, momentum, affect history) across daemon restarts so each session
 * inherits yesterday's mental posture instead of rebuilding from scratch.
 *
 * Uses `~/.cassicore/data/aurora.db` (SQLite) as the persistence substrate.
 * Distinct from `aurora-claustrum.db` (which serves the A1 vindex provenance
 * pipeline) — this is the live operational state store.
 *
 * Construction is optional: if no `AuroraPersistence` is injected into Aurora,
 * she runs in pure in-memory mode exactly as before.
 *
 * See: docs/design/aurora-cross-session-continuity.md
 */

import path from 'node:path'
import fs from 'node:fs'
import Database from 'better-sqlite3'

import type { ILogger } from '@cassicore/foundation'
import { getDataDir } from '@cassicore/foundation'
import type {
  CognitiveNode,
  CognitiveEdge,
  CognitiveNodeSource,
  CognitiveEdgeOrigin,
  ReasoningRecord,
  ReasoningMomentum,
  ReasoningShift,
  ReverieInsight,
} from './types.js'

// section

export interface SessionMetadata {
  vindexId?: string
  modelId?: string
  workspace?: string
}

export interface SessionHandle {
  readonly sessionId: string
  readonly inheritsFrom: string | null
  readonly createdAt: string
}

export interface FocusState {
  foci: string[]
  occurredAt: string
  trigger: string | null
}

export interface AffectSample {
  label: string | null
  intensity: number
  metadata?: Record<string, unknown>
}

/**
 * A reasoning record that has been moved out of the live `aurora_reasoning`
 * table into the long-arc archive. Mirrors the live row plus an `archived_at`
 * stamp and a denormalised `session_id` (the archive has no FK back to
 * `aurora_sessions`, so archived rows survive session deletion).
 */
export interface ArchivedRecord {
  id: number
  sessionId: string
  turnCount: number
  occurredAt: string
  archivedAt: string
  concepts: string[]
  coherence: number | null
  integration: number | null
  insights: unknown[]
  textExcerpt: string | null
  metadata: Record<string, unknown>
}

export interface AuroraPersistenceConfig {
  /** Max reasoning records to load on hydration. Default: 200. */
  reasoningHydrationLimit?: number
  /** Node confidence decay half-life in days. Default: 14. */
  nodeDecayHalfLifeDays?: number
  /** Edge strength decay half-life in days. Default: 7. */
  edgeDecayHalfLifeDays?: number
  /** Affect intensity decay half-life in hours. Default: 6. */
  affectDecayHalfLifeHours?: number
  /** Minimum confidence to keep a node after decay. Default: 0.05. */
  minConfidenceThreshold?: number
}

const DEFAULT_CONFIG: Required<AuroraPersistenceConfig> = {
  reasoningHydrationLimit: 200,
  nodeDecayHalfLifeDays: 14,
  edgeDecayHalfLifeDays: 7,
  affectDecayHalfLifeHours: 6,
  minConfidenceThreshold: 0.05,
}

// section

interface Migration {
  version: number
  sql: string
}

const MIGRATIONS: Migration[] = [
  {
    version: 1,
    sql: `
      CREATE TABLE IF NOT EXISTS aurora_sessions (
        session_id TEXT PRIMARY KEY,
        inherits_from TEXT,
        created_at TEXT NOT NULL,
        ended_at TEXT,
        vindex_id TEXT,
        model_id TEXT,
        workspace TEXT,
        metadata TEXT DEFAULT '{}'
      );

      CREATE TABLE IF NOT EXISTS aurora_nodes (
        id TEXT PRIMARY KEY,
        label TEXT NOT NULL,
        source TEXT NOT NULL,
        confidence REAL NOT NULL,
        layer_min INTEGER,
        layer_max INTEGER,
        first_seen_at TEXT NOT NULL,
        last_activated_at TEXT NOT NULL,
        activation_count INTEGER NOT NULL DEFAULT 0,
        last_session_id TEXT REFERENCES aurora_sessions(session_id) ON DELETE SET NULL,
        metadata TEXT DEFAULT '{}'
      );

      CREATE INDEX IF NOT EXISTS idx_aurora_nodes_label ON aurora_nodes(label);
      CREATE INDEX IF NOT EXISTS idx_aurora_nodes_last_activated ON aurora_nodes(last_activated_at);

      CREATE TABLE IF NOT EXISTS aurora_edges (
        source_id TEXT NOT NULL REFERENCES aurora_nodes(id) ON DELETE CASCADE,
        target_id TEXT NOT NULL REFERENCES aurora_nodes(id) ON DELETE CASCADE,
        edge_type TEXT NOT NULL,
        origin TEXT NOT NULL,
        strength REAL NOT NULL,
        first_seen_at TEXT NOT NULL,
        last_reinforced_at TEXT NOT NULL,
        reinforcement_count INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (source_id, target_id, edge_type)
      );

      CREATE INDEX IF NOT EXISTS idx_aurora_edges_target ON aurora_edges(target_id);

      CREATE TABLE IF NOT EXISTS aurora_reasoning (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL REFERENCES aurora_sessions(session_id) ON DELETE CASCADE,
        turn_count INTEGER NOT NULL,
        occurred_at TEXT NOT NULL,
        concepts TEXT NOT NULL,
        coherence REAL,
        integration REAL,
        insights TEXT DEFAULT '[]',
        text_excerpt TEXT,
        metadata TEXT DEFAULT '{}'
      );

      CREATE INDEX IF NOT EXISTS idx_aurora_reasoning_session ON aurora_reasoning(session_id);
      CREATE INDEX IF NOT EXISTS idx_aurora_reasoning_occurred ON aurora_reasoning(occurred_at);

      CREATE TABLE IF NOT EXISTS aurora_focus_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL REFERENCES aurora_sessions(session_id) ON DELETE CASCADE,
        occurred_at TEXT NOT NULL,
        foci TEXT NOT NULL,
        weight REAL NOT NULL,
        trigger TEXT
      );

      CREATE TABLE IF NOT EXISTS aurora_affect_samples (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL REFERENCES aurora_sessions(session_id) ON DELETE CASCADE,
        occurred_at TEXT NOT NULL,
        affect_label TEXT,
        affect_intensity REAL,
        affect_metadata TEXT DEFAULT '{}'
      );

      CREATE TABLE IF NOT EXISTS aurora_schema_version (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
      );

      INSERT INTO aurora_schema_version (version, applied_at) VALUES (1, ?);
    `,
  },
  {
    version: 2,
    sql: `
      CREATE TABLE IF NOT EXISTS aurora_archived_reasoning (
        id INTEGER PRIMARY KEY,
        session_id TEXT NOT NULL,
        turn_count INTEGER NOT NULL,
        occurred_at TEXT NOT NULL,
        concepts TEXT NOT NULL,
        coherence REAL,
        integration REAL,
        insights TEXT DEFAULT '[]',
        text_excerpt TEXT,
        metadata TEXT DEFAULT '{}',
        archived_at TEXT NOT NULL
      );

      CREATE INDEX IF NOT EXISTS idx_aurora_archived_reasoning_archived
        ON aurora_archived_reasoning(archived_at);
      CREATE INDEX IF NOT EXISTS idx_aurora_archived_reasoning_occurred
        ON aurora_archived_reasoning(occurred_at);

      INSERT INTO aurora_schema_version (version, applied_at) VALUES (2, ?);
    `,
  },
  {
    version: 3,
    sql: `
      -- B2 affect-conditioned retrieval (spec §4.1):
      -- per-feature sparse affect signature, used by RetrievalPolicy's
      -- mode-driven re-scoring path. One row per (vindex, layer, feature).
      CREATE TABLE IF NOT EXISTS feature_affect_signatures (
        vindex_id TEXT NOT NULL,
        layer INTEGER NOT NULL,
        feature_index INTEGER NOT NULL,
        labels_json TEXT NOT NULL,
        magnitude REAL NOT NULL,
        computed_at TEXT NOT NULL,
        probe_set_id TEXT NOT NULL,
        PRIMARY KEY (vindex_id, layer, feature_index)
      );

      CREATE INDEX IF NOT EXISTS idx_fas_vindex_magnitude
        ON feature_affect_signatures(vindex_id, magnitude DESC);

      CREATE TABLE IF NOT EXISTS feature_affect_probe_sets (
        id TEXT PRIMARY KEY,
        vindex_id TEXT NOT NULL,
        description TEXT,
        probe_count_per_quadrant INTEGER NOT NULL,
        total_probes INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        metadata TEXT DEFAULT '{}'
      );

      INSERT INTO aurora_schema_version (version, applied_at) VALUES (3, ?);
    `,
  },
]

// section

export class AuroraPersistence {
  private readonly logger: ILogger
  private readonly db: Database.Database
  private readonly config: Required<AuroraPersistenceConfig>
  private readonly ownsDb: boolean
  private readonly dbPath?: string
  private closed = false

  /** Dirty tracking for periodic checkpoint. */
  private dirtyNodes = new Set<string>()
  private dirtyEdges = new Set<string>()

  constructor(
    dbOrPath: string | Database.Database,
    logger: ILogger,
    config?: AuroraPersistenceConfig,
  ) {
    this.logger = logger.child ? logger.child('aurora-persistence') : logger
    this.config = { ...DEFAULT_CONFIG, ...config }

    if (typeof dbOrPath === 'string') {
      const dir = path.dirname(dbOrPath)
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
      this.db = new Database(dbOrPath)
      this.db.pragma('journal_mode = WAL')
      this.db.pragma('busy_timeout = 5000')
      this.db.pragma('synchronous = NORMAL')
      this.ownsDb = true
      this.dbPath = dbOrPath
    } else {
      this.db = dbOrPath
      this.ownsDb = false
    }

    this.applyMigrations()
  }

  /** Returns the database path if this instance owns the DB, otherwise undefined. */
  getDbPath(): string | undefined {
    return this.dbPath
  }

  // section

  /**
   * Begin a new session. Creates a row in `aurora_sessions` and returns a
   * handle for subsequent writes.
   */
  beginSession(metadata: SessionMetadata = {}): SessionHandle {
    this.assertOpen()
    const now = new Date().toISOString()

    // Find the most recent ended session to chain from
    const prev = this.db.prepare(
      `SELECT session_id FROM aurora_sessions
       WHERE ended_at IS NOT NULL
       ORDER BY ended_at DESC LIMIT 1`,
    ).get() as { session_id: string } | undefined

    // Also handle crashed sessions (null ended_at)
    const crashed = this.db.prepare(
      `SELECT session_id FROM aurora_sessions
       WHERE ended_at IS NULL
       ORDER BY created_at DESC LIMIT 1`,
    ).get() as { session_id: string } | undefined

    // If there's a crashed session, inherit from it and close it
    let inheritsFrom = prev?.session_id ?? crashed?.session_id ?? null
    if (crashed && !prev) {
      inheritsFrom = crashed.session_id
    }

    const sessionId = `aur_sess_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`

    this.db.prepare(
      `INSERT INTO aurora_sessions (session_id, inherits_from, created_at, vindex_id, model_id, workspace, metadata)
       VALUES (?, ?, ?, ?, ?, ?, '{}')`,
    ).run(sessionId, inheritsFrom, now, metadata.vindexId ?? null, metadata.modelId ?? null, metadata.workspace ?? null)

    // Close any crashed sessions
    if (crashed) {
      this.db.prepare(
        `UPDATE aurora_sessions SET ended_at = ? WHERE session_id = ? AND ended_at IS NULL`,
      ).run(now, crashed.session_id)
    }

    this.logger.info('Aurora session begun', { sessionId, inheritsFrom })
    return { sessionId, inheritsFrom, createdAt: now }
  }

  /**
   * End a session gracefully. Sets `ended_at` to current timestamp.
   */
  endSession(handle: SessionHandle, status: 'graceful' | 'crashed' = 'graceful'): void {
    if (this.closed) return
    const now = new Date().toISOString()
    this.flushDirtyState()
    this.db.prepare(
      `UPDATE aurora_sessions SET ended_at = ?, metadata = json_set(metadata, '$.end_status', ?)
       WHERE session_id = ?`,
    ).run(now, status, handle.sessionId)
    this.logger.info('Aurora session ended', { sessionId: handle.sessionId, status })
  }

  // section

  /**
   * Hydrate claustrum nodes and edges from persistence.
   * Applies decay based on time elapsed since last activation.
   */
  hydrateClaustrum(now: Date = new Date()): {
    nodes: CognitiveNode[]
    edges: CognitiveEdge[]
  } {
    this.assertOpen()
    const cutoff = new Date(now.getTime() - 30 * 86_400_000).toISOString() // 30 days

    const rows = this.db.prepare(
      `SELECT * FROM aurora_nodes WHERE last_activated_at >= ?
       ORDER BY confidence DESC, last_activated_at DESC`,
    ).all(cutoff) as any[]

    const nodes: CognitiveNode[] = []
    for (const row of rows) {
      const decayed = this.decay(
        row.confidence,
        row.last_activated_at,
        now,
        this.config.nodeDecayHalfLifeDays * 86_400_000, // days → ms
      )
      if (decayed < this.config.minConfidenceThreshold) continue

      const meta = safeParseJson(row.metadata, {})
      nodes.push({
        id: row.id,
        label: row.label,
        source: row.source as CognitiveNodeSource,
        resonance: decayed,
        centrality: meta.centrality ?? 0.5,
        activated: false,
        modelConfidence: meta.modelConfidence,
        modelLayers: meta.modelLayers,
        potentiation: meta.potentiation,
        content: meta.content,
      })
    }

    // Load edges between surviving nodes
    const nodeIds = new Set(nodes.map(n => n.id))
    const edgeRows = this.db.prepare(
      `SELECT * FROM aurora_edges
       WHERE source_id IN (${placeholders(nodeIds.size)})
         AND target_id IN (${placeholders(nodeIds.size)})`,
    ).all(...nodeIds, ...nodeIds) as any[]

    const edges: CognitiveEdge[] = []
    for (const row of edgeRows) {
      if (!nodeIds.has(row.source_id) || !nodeIds.has(row.target_id)) continue
      const strength = this.decay(
        row.strength,
        row.last_reinforced_at,
        now,
        this.config.edgeDecayHalfLifeDays * 86_400_000,
      )
      if (strength < this.config.minConfidenceThreshold) continue
      edges.push({
        sourceId: row.source_id,
        targetId: row.target_id,
        origin: row.origin as CognitiveEdgeOrigin,
        edgeType: row.edge_type,
        weight: strength,
      })
    }

    this.logger.info('Claustrum hydrated', {
      nodesRequested: rows.length,
      nodesKept: nodes.length,
      edges: edges.length,
    })

    return { nodes, edges }
  }

  /**
   * Hydrate the reasoning log — last N records across all sessions.
   */
  hydrateReasoningLog(limit?: number): ReasoningRecord[] {
    this.assertOpen()
    const n = limit ?? this.config.reasoningHydrationLimit
    const rows = this.db.prepare(
      `SELECT * FROM aurora_reasoning ORDER BY occurred_at DESC LIMIT ?`,
    ).all(n) as any[]

    return rows.map(row => {
      const meta = safeParseJson(row.metadata, {})
      const concepts: string[] = safeParseJson(row.concepts, [])
      const insights: ReverieInsight[] = safeParseJson(row.insights, [])
      return {
        id: `rec_${row.id}`,
        text: row.text_excerpt ?? '',
        concepts,
        insights,
        shift: meta.shift ?? null,
        momentum: meta.momentum ?? { trendingConcepts: [], novelty: 0, confidence: 0.5, topicShift: false, turnsInDirection: 0 },
        activatedNodes: meta.activatedNodes ?? [],
        turnNumber: row.turn_count,
        recordedAt: new Date(row.occurred_at).getTime(),
        durationMs: meta.durationMs ?? 0,
        reverieAnalyzed: meta.reverieAnalyzed ?? false,
        sessionId: row.session_id,
      } satisfies ReasoningRecord
    }).reverse() // oldest first, matching in-memory log order
  }

  /**
   * Reconstruct momentum from the most recent reasoning records.
   */
  hydrateMomentum(): ReasoningMomentum | null {
    this.assertOpen()
    const row = this.db.prepare(
      `SELECT metadata FROM aurora_reasoning ORDER BY occurred_at DESC LIMIT 1`,
    ).get() as { metadata: string } | undefined
    if (!row) return null

    const meta = safeParseJson(row.metadata, {})
    return meta.momentum ?? null
  }

  /**
   * Get the last focus state.
   */
  hydrateFocus(): FocusState | null {
    this.assertOpen()
    const row = this.db.prepare(
      `SELECT * FROM aurora_focus_history ORDER BY occurred_at DESC LIMIT 1`,
    ).get() as any | undefined
    if (!row) return null

    return {
      foci: safeParseJson(row.foci, []),
      occurredAt: row.occurred_at,
      trigger: row.trigger,
    }
  }

  // section

  /**
   * Write a reasoning record to the persistence store.
   * Should be called on each `observeReasoning()`.
   */
  writeReasoning(handle: SessionHandle, record: ReasoningRecord): void {
    if (this.closed) return
    const now = new Date(record.recordedAt).toISOString()
    this.db.prepare(
      `INSERT INTO aurora_reasoning
        (session_id, turn_count, occurred_at, concepts, coherence, integration, insights, text_excerpt, metadata)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    ).run(
      handle.sessionId,
      record.turnNumber,
      now,
      JSON.stringify(record.concepts),
      null, // coherence — computed post-observation
      null, // integration
      JSON.stringify(record.insights.map(summarizeInsight)),
      record.text.slice(0, 500) || null,
      JSON.stringify({
        shift: record.shift,
        momentum: record.momentum,
        activatedNodes: record.activatedNodes,
        durationMs: record.durationMs,
        reverieAnalyzed: record.reverieAnalyzed,
      }),
    )
  }

  /**
   * Upsert a claustrum node. Marked dirty for periodic checkpoint.
   */
  upsertNode(node: CognitiveNode, sessionId?: string): void {
    if (this.closed) return
    const now = new Date().toISOString()
    const meta = JSON.stringify({
      modelConfidence: node.modelConfidence,
      modelLayers: node.modelLayers,
      potentiation: node.potentiation,
      content: node.content,
      centrality: node.centrality,
    })

    this.db.prepare(
      `INSERT INTO aurora_nodes (id, label, source, confidence, layer_min, layer_max, first_seen_at, last_activated_at, activation_count, last_session_id, metadata)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
       ON CONFLICT (id) DO UPDATE SET
         confidence = MAX(confidence, ?),
         last_activated_at = ?,
         activation_count = activation_count + 1,
         last_session_id = COALESCE(?, last_session_id),
         metadata = ?`,
    ).run(
      node.id, node.label, node.source, node.resonance,
      node.modelLayers?.[0] ?? null, node.modelLayers?.[node.modelLayers.length - 1] ?? null,
      now, now, sessionId ?? null, meta,
      // ON CONFLICT params
      node.resonance, now, sessionId ?? null, meta,
    )
    this.dirtyNodes.add(node.id)
  }

  /**
   * Upsert a claustrum edge. Marked dirty for periodic checkpoint.
   */
  upsertEdge(edge: CognitiveEdge): void {
    if (this.closed) return
    const now = new Date().toISOString()
    this.db.prepare(
      `INSERT INTO aurora_edges (source_id, target_id, edge_type, origin, strength, first_seen_at, last_reinforced_at, reinforcement_count)
       VALUES (?, ?, ?, ?, ?, ?, ?, 1)
       ON CONFLICT (source_id, target_id, edge_type) DO UPDATE SET
         strength = MAX(strength, ?),
         last_reinforced_at = ?,
         reinforcement_count = reinforcement_count + 1`,
    ).run(
      edge.sourceId, edge.targetId, edge.edgeType, edge.origin, edge.weight,
      now, now,
      // ON CONFLICT params
      edge.weight, now,
    )
    this.dirtyEdges.add(`${edge.sourceId}:${edge.targetId}:${edge.edgeType}`)
  }

  /**
   * Record a focus shift.
   */
  recordFocusShift(handle: SessionHandle, foci: string[], trigger?: string): void {
    if (this.closed) return
    const now = new Date().toISOString()
    this.db.prepare(
      `INSERT INTO aurora_focus_history (session_id, occurred_at, foci, weight, trigger)
       VALUES (?, ?, ?, 1.0, ?)`,
    ).run(handle.sessionId, now, JSON.stringify(foci), trigger ?? null)
  }

  /**
   * Record an affect sample.
   */
  recordAffectSample(handle: SessionHandle, sample: AffectSample): void {
    if (this.closed) return
    const now = new Date().toISOString()
    this.db.prepare(
      `INSERT INTO aurora_affect_samples (session_id, occurred_at, affect_label, affect_intensity, affect_metadata)
       VALUES (?, ?, ?, ?, ?)`,
    ).run(handle.sessionId, now, sample.label, sample.intensity, JSON.stringify(sample.metadata ?? {}))
  }

  // section

  /**
   * Flush dirty node/edge state to disk. Called on periodic checkpoint
   * and graceful shutdown.
   */
  flushDirtyState(): void {
    if (this.closed) return
    // Nodes and edges are already written via upsert — dirty tracking is for
    // future batched write optimization. For now, just clear the sets.
    const nodeCount = this.dirtyNodes.size
    const edgeCount = this.dirtyEdges.size
    this.dirtyNodes.clear()
    this.dirtyEdges.clear()
    if (nodeCount || edgeCount) {
      this.logger.debug('Dirty state flushed', { nodeCount, edgeCount })
    }
  }

  /**
   * Apply decay across all nodes and edges, dropping sub-threshold entries.
   */
  decayPass(now: Date = new Date()): { nodesDropped: number; edgesDropped: number } {
    this.assertOpen()

    // Drop decayed nodes
    const nodeRows = this.db.prepare(
      `SELECT id, confidence, last_activated_at FROM aurora_nodes`,
    ).all() as any[]

    let nodesDropped = 0
    const dropNodes = this.db.prepare(`DELETE FROM aurora_nodes WHERE id = ?`)
    for (const row of nodeRows) {
      const decayed = this.decay(
        row.confidence,
        row.last_activated_at,
        now,
        this.config.nodeDecayHalfLifeDays * 86_400_000,
      )
      if (decayed < this.config.minConfidenceThreshold) {
        dropNodes.run(row.id)
        nodesDropped++
      }
    }

    // Drop decayed edges (cascade from node deletion handles most)
    let edgesDropped = 0
    const edgeRows = this.db.prepare(
      `SELECT source_id, target_id, edge_type, strength, last_reinforced_at FROM aurora_edges`,
    ).all() as any[]

    const dropEdge = this.db.prepare(
      `DELETE FROM aurora_edges WHERE source_id = ? AND target_id = ? AND edge_type = ?`,
    )
    for (const row of edgeRows) {
      const decayed = this.decay(
        row.strength,
        row.last_reinforced_at,
        now,
        this.config.edgeDecayHalfLifeDays * 86_400_000,
      )
      if (decayed < this.config.minConfidenceThreshold) {
        dropEdge.run(row.source_id, row.target_id, row.edge_type)
        edgesDropped++
      }
    }

    this.logger.info('Decay pass complete', { nodesDropped, edgesDropped })
    return { nodesDropped, edgesDropped }
  }

  /**
   * Long-arc decay + archival pass for `aurora_reasoning` (B6.2).
   *
   * Runs as a single SQLite transaction:
   *  1. Decays the `coherence` score on every live reasoning row by
   *     `(1 - activationDecayRate)`. (Reasoning rows have no `activation`
   *     column, so we decay `coherence` — the closest score field.
   *     Coherence is NULL until populated post-observation, in which case
   *     the multiplication is a no-op and only age-based archival applies.)
   *  2. Archives rows whose `occurred_at` is older than `archiveAfterDays`,
   *     OR whose decayed `coherence` falls below `archiveActivationFloor`
   *     (NULL coherence is treated as not-below-floor, so it never triggers
   *     the floor branch on its own).
   *  3. Archived rows are inserted into `aurora_archived_reasoning` with
   *     their original `id` preserved and a fresh `archived_at` stamp,
   *     then deleted from the live table.
   *
   * The archive table has no FK to `aurora_sessions`, so archived rows
   * survive deletion of the session that produced them — that's the whole
   * point of long-arc memory.
   */
  runDecayAndArchive(options: {
    activationDecayRate?: number
    archiveAfterDays?: number
    archiveActivationFloor?: number
    now?: Date
  } = {}): { decayed: number; archived: number } {
    this.assertOpen()

    const decayRate = options.activationDecayRate ?? 0.05
    const archiveAfterDays = options.archiveAfterDays ?? 30
    const floor = options.archiveActivationFloor ?? 0.05
    const now = options.now ?? new Date()
    const cutoffIso = new Date(now.getTime() - archiveAfterDays * 86_400_000).toISOString()
    const archivedAt = now.toISOString()

    const tx = this.db.transaction((): { decayed: number; archived: number } => {
      const decayResult = this.db.prepare(
        `UPDATE aurora_reasoning
           SET coherence = coherence * ?
         WHERE coherence IS NOT NULL`,
      ).run(1 - decayRate)
      const decayed = Number(decayResult.changes ?? 0)

      this.db.prepare(
        `INSERT INTO aurora_archived_reasoning
           (id, session_id, turn_count, occurred_at, concepts, coherence,
            integration, insights, text_excerpt, metadata, archived_at)
         SELECT id, session_id, turn_count, occurred_at, concepts, coherence,
                integration, insights, text_excerpt, metadata, ?
           FROM aurora_reasoning
          WHERE occurred_at < ?
             OR (coherence IS NOT NULL AND coherence < ?)`,
      ).run(archivedAt, cutoffIso, floor)

      const deleteResult = this.db.prepare(
        `DELETE FROM aurora_reasoning
          WHERE occurred_at < ?
             OR (coherence IS NOT NULL AND coherence < ?)`,
      ).run(cutoffIso, floor)
      const archived = Number(deleteResult.changes ?? 0)

      return { decayed, archived }
    })

    const result = tx()
    this.logger.info('Aurora decay+archive complete', {
      decayed: result.decayed,
      archived: result.archived,
      decayRate,
      archiveAfterDays,
      floor,
    })
    return result
  }

  /**
   * Read archived reasoning records (B6.2). Defaults to the 100 most-recently
   * archived rows; pass `since` to filter by `archived_at` lower bound.
   */
  queryArchive(options: { since?: string; limit?: number } = {}): ArchivedRecord[] {
    this.assertOpen()
    const limit = options.limit ?? 100
    const since = options.since ?? null

    const sql = since
      ? `SELECT * FROM aurora_archived_reasoning
           WHERE archived_at >= ?
           ORDER BY archived_at DESC LIMIT ?`
      : `SELECT * FROM aurora_archived_reasoning
           ORDER BY archived_at DESC LIMIT ?`

    const rows = (since
      ? this.db.prepare(sql).all(since, limit)
      : this.db.prepare(sql).all(limit)) as any[]

    return rows.map(row => ({
      id: row.id,
      sessionId: row.session_id,
      turnCount: row.turn_count,
      occurredAt: row.occurred_at,
      archivedAt: row.archived_at,
      concepts: safeParseJson(row.concepts, []),
      coherence: row.coherence ?? null,
      integration: row.integration ?? null,
      insights: safeParseJson(row.insights, []),
      textExcerpt: row.text_excerpt ?? null,
      metadata: safeParseJson(row.metadata, {}),
    }))
  }

  /**
   * B6.3 — concepts that recur across N or more distinct sessions.
   *
   * Walks aurora_reasoning + aurora_archived_reasoning, aggregates
   * concept frequency by session, returns concepts seen in at least
   * `minSessions` sessions, sorted by sessionCount descending.
   *
   * Used by C1 (self-curing topology) to find longitudinally-active
   * concepts that warrant deeper investigation, and by Aurora's
   * narrative layer for "concepts I keep coming back to".
   */
  recurringConceptsAcrossSessions(opts: { minSessions?: number; limit?: number } = {}): Array<{
    concept: string
    sessionCount: number
    totalOccurrences: number
  }> {
    this.assertOpen()
    const minSessions = opts.minSessions ?? 2
    const limit = opts.limit ?? 50

    const aggregate = new Map<string, { sessions: Set<string>; total: number }>()
    const liveRows = this.db.prepare(
      `SELECT session_id, concepts FROM aurora_reasoning`,
    ).all() as Array<{ session_id: string; concepts: string }>
    const archivedRows = this.db.prepare(
      `SELECT session_id, concepts FROM aurora_archived_reasoning`,
    ).all() as Array<{ session_id: string; concepts: string }>

    for (const row of [...liveRows, ...archivedRows]) {
      const concepts = safeParseJson(row.concepts, []) as string[]
      for (const concept of concepts) {
        let entry = aggregate.get(concept)
        if (!entry) {
          entry = { sessions: new Set(), total: 0 }
          aggregate.set(concept, entry)
        }
        entry.sessions.add(row.session_id)
        entry.total++
      }
    }

    const out: Array<{ concept: string; sessionCount: number; totalOccurrences: number }> = []
    for (const [concept, entry] of aggregate) {
      if (entry.sessions.size < minSessions) continue
      out.push({
        concept,
        sessionCount: entry.sessions.size,
        totalOccurrences: entry.total,
      })
    }
    out.sort((a, b) => b.sessionCount - a.sessionCount || b.totalOccurrences - a.totalOccurrences)
    return out.slice(0, limit)
  }

  /**
   * B6.3 — reasoning records similar to a current concept set across
   * all sessions. Similarity = Jaccard over the concept sets, with a
   * `minSimilarity` floor. Returns records sorted by similarity
   * descending, limited.
   *
   * Feeds B3 (reasoning trace replay): when a new turn's concepts
   * resemble a past turn's concepts, that's a candidate for replay.
   */
  similarReasoningRecordsAcrossSessions(opts: {
    concepts: ReadonlyArray<string>
    minSimilarity?: number
    limit?: number
  }): Array<{
    sessionId: string
    occurredAt: string
    concepts: string[]
    similarity: number
    coherence: number | null
    integration: number | null
  }> {
    this.assertOpen()
    if (opts.concepts.length === 0) return []
    const querySet = new Set(opts.concepts.map(c => c.toLowerCase()))
    const minSim = opts.minSimilarity ?? 0.2
    const limit = opts.limit ?? 20

    const rows = this.db.prepare(`
      SELECT session_id, occurred_at, concepts, coherence, integration
      FROM aurora_reasoning
    `).all() as Array<{
      session_id: string; occurred_at: string; concepts: string;
      coherence: number | null; integration: number | null;
    }>

    const scored: Array<{
      sessionId: string; occurredAt: string; concepts: string[]; similarity: number;
      coherence: number | null; integration: number | null;
    }> = []

    for (const row of rows) {
      const recordConcepts = safeParseJson(row.concepts, []) as string[]
      if (recordConcepts.length === 0) continue
      const recordSet = new Set(recordConcepts.map((c: string) => c.toLowerCase()))
      let intersection = 0
      for (const c of querySet) if (recordSet.has(c)) intersection++
      const union = querySet.size + recordSet.size - intersection
      const similarity = union === 0 ? 0 : intersection / union
      if (similarity < minSim) continue
      scored.push({
        sessionId: row.session_id,
        occurredAt: row.occurred_at,
        concepts: recordConcepts,
        similarity,
        coherence: row.coherence,
        integration: row.integration,
      })
    }

    scored.sort((a, b) => b.similarity - a.similarity)
    return scored.slice(0, limit)
  }

  close(): void {
    if (this.closed) return
    this.closed = true
    this.flushDirtyState()
    if (this.ownsDb) this.db.close()
  }

  // section

  private assertOpen(): void {
    if (this.closed) throw new Error('AuroraPersistence is closed')
  }

  private applyMigrations(): void {
    // Check if the schema table exists at all (first run)
    const tableExists = this.db.prepare(
      "SELECT name FROM sqlite_master WHERE type='table' AND name='aurora_schema_version'",
    ).get() as { name: string } | undefined

    let currentVersion = 0
    if (tableExists) {
      const currentRow = this.db.prepare(
        'SELECT MAX(version) as v FROM aurora_schema_version',
      ).get() as { v: number | null } | undefined
      currentVersion = currentRow?.v ?? 0
    }

    for (const migration of MIGRATIONS) {
      if (migration.version > currentVersion) {
        this.db.exec(migration.sql.replace('?', `'${new Date().toISOString()}'`))
        this.logger.info('Applied migration', { version: migration.version })
      }
    }
  }

  /**
   * Exponential decay: `value * exp(-elapsed_ms / halfLife_ms * ln(2))`.
   */
  private decay(value: number, lastTs: string, now: Date, halfLifeMs: number): number {
    const elapsed = now.getTime() - new Date(lastTs).getTime()
    if (elapsed <= 0) return value
    return value * Math.exp(-elapsed / halfLifeMs * Math.LN2)
  }
}


// section

function safeParseJson(text: string, fallback: any): any {
  try { return JSON.parse(text) } catch { return fallback }
}

function summarizeInsight(insight: ReverieInsight): Record<string, unknown> {
  return { kind: insight.kind, content: insight.content, confidence: insight.confidence }
}

function placeholders(n: number): string {
  return Array.from({ length: n }, () => '?').join(',')
}
