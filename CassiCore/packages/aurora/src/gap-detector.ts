/**
 * GapDetector — Topology-aware gap detection for Aurora's Claustrum.
 *
 * Detects underdeveloped subgraphs in the cognitive graph and emits
 * structured GapSignal records for downstream meditation seeding.
 *
 * Gap categories:
 *   UNDERCONNECTED   — nodes with too few edges relative to cluster average
 *   FRAGMENTED       — multiple disconnected components within a semantic region
 *   MISSING_FOCUS    — important concepts with high mention but low graph presence
 *   ISOLATED_NUCLEUS — well-connected cluster with no bridges to the rest of the graph
 *
 * See: docs/design/aurora-self-curing-topology.md §2
 */

import * as crypto from 'node:crypto'
import * as fs from 'node:fs'
import * as path from 'node:path'

import Database from 'better-sqlite3'

import type { ILogger } from '../../../types/interfaces.js'
import type { CognitiveNode, CognitiveEdge, UnifiedGraph } from './types.js'
import { getDataDir } from '../../utils/paths.js'



export type GapCategory =
  | 'underconnected'
  | 'fragmented'
  | 'missing_focus'
  | 'isolated_nucleus'

export type GapStatus =
  | 'pending'
  | 'scheduled'
  | 'in_meditation'
  | 'resolved'
  | 'leave_open'
  | 'unresolvable'

export type GapSignalType =
  | 'low_edge_density'
  | 'persistent_unresolved'
  | 'missing_portal'
  | 'low_coherence'
  | 'repeated_revisit'
  | 'reverie_explicit'

export interface SignalDetail {
  type: GapSignalType
  strength: number
  provenance: string
}

export interface GapCandidate {
  id: string
  category: GapCategory
  scope: {
    nodeIds: string[]
    expectedEdges?: Array<{ source: string; target: string; edgeType: string }>
    affectedModules?: string[]
  }
  signals: SignalDetail[]
  priority: number
  status: GapStatus
  observedSince: string
  lastObserved: string
  detectionCount: number
  metadata: Record<string, unknown>
}

export interface GapDetectorConfig {
  /** Edge-density ratio below which a node is underconnected (default 0.3). */
  lowEdgeDensityThreshold: number
  /** Minimum node count for a component to be considered a nucleus (default 3). */
  minNucleusSize: number
  /** Maximum bridge count for a nucleus to be considered isolated (default 1). */
  maxNucleusBridges: number
  /** Maximum gaps to return per detection cycle (default 20). */
  maxGaps: number
  /** Coherence threshold below which fragmentation is flagged (default 0.4). */
  fragmentationCoherenceThreshold: number
  /** Strategic value multipliers per module (default all 1.0). */
  strategicValues: Record<string, number>
}

const DEFAULT_CONFIG: GapDetectorConfig = {
  lowEdgeDensityThreshold: 0.3,
  minNucleusSize: 3,
  maxNucleusBridges: 1,
  maxGaps: 20,
  fragmentationCoherenceThreshold: 0.4,
  strategicValues: {},
}



const SCHEMA_VERSION = 1

const SCHEMA_V1 = `
  CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
  INSERT OR IGNORE INTO schema_version (version) VALUES (${SCHEMA_VERSION});

  CREATE TABLE IF NOT EXISTS gaps (
    id              TEXT PRIMARY KEY,
    category        TEXT NOT NULL,
    scope_node_ids  TEXT NOT NULL,
    scope_expected_edges TEXT,
    scope_affected_modules TEXT,
    signals         TEXT NOT NULL,
    priority        REAL NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    observed_since  TEXT NOT NULL,
    last_observed   TEXT NOT NULL,
    detection_count INTEGER NOT NULL DEFAULT 1,
    metadata        TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
  );

  CREATE INDEX IF NOT EXISTS idx_gaps_status ON gaps(status);
  CREATE INDEX IF NOT EXISTS idx_gaps_priority ON gaps(priority DESC);
  CREATE INDEX IF NOT EXISTS idx_gaps_category ON gaps(category);
  CREATE INDEX IF NOT EXISTS idx_gaps_observed_since ON gaps(observed_since);

  CREATE TABLE IF NOT EXISTS gap_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    gap_id      TEXT NOT NULL REFERENCES gaps(id),
    action      TEXT NOT NULL,
    details     TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
  );

  CREATE INDEX IF NOT EXISTS idx_gap_history_gap_id ON gap_history(gap_id);
`



export class GapDetector {
  private readonly logger: ILogger
  private readonly config: GapDetectorConfig
  private readonly db: Database.Database
  private readonly ownsDb: boolean

  // Prepared statements (lazily initialized)
  private stmtUpsertGap!: Database.Statement
  private stmtGetGap!: Database.Statement
  private stmtGetGapsByStatus!: Database.Statement
  private stmtUpdateStatus!: Database.Statement
  private stmtInsertHistory!: Database.Statement
  private stmtGetPending!: Database.Statement

  /**
   * Reverse adjacency cache, rebuilt at the start of each detectGaps() call.
   * Without this, every getInEdges/countInEdges call rescans the full edge map.
   */
  private reverseAdjCache: Map<string, string[]> | null = null

  constructor(
    dbOrPath: string | Database.Database,
    logger: ILogger,
    config?: Partial<GapDetectorConfig>,
  ) {
    this.logger = logger.child ? logger.child('gap-detector') : logger
    this.config = { ...DEFAULT_CONFIG, ...config }

    if (typeof dbOrPath === 'string') {
      const dir = path.dirname(dbOrPath)
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
      this.db = new Database(dbOrPath)
      this.db.pragma('journal_mode = WAL')
      this.db.pragma('busy_timeout = 5000')
      this.db.pragma('synchronous = NORMAL')
      this.ownsDb = true
    } else {
      this.db = dbOrPath
      this.ownsDb = false
    }

    this.initializeSchema()
    this.prepareStatements()
  }

  /** Factory that creates a detector at the standard path. */
  static create(logger: ILogger, config?: Partial<GapDetectorConfig>): GapDetector {
    const dbPath = path.join(getDataDir(), 'system-state.db')
    return new GapDetector(dbPath, logger, config)
  }


  private initializeSchema(): void {
    // Create table if it doesn't exist, then check version
    this.db.exec('CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)')
    const current = this.db.prepare('SELECT version FROM schema_version').get() as { version: number } | undefined
    if (!current) {
      this.db.exec(SCHEMA_V1)
      this.logger.info('Gap detector database initialized', { version: SCHEMA_VERSION })
    }
  }

  private prepareStatements(): void {
    this.stmtUpsertGap = this.db.prepare(`
      INSERT INTO gaps (id, category, scope_node_ids, scope_expected_edges, scope_affected_modules,
                        signals, priority, status, observed_since, last_observed, detection_count, metadata)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(id) DO UPDATE SET
        priority = MAX(excluded.priority, gaps.priority),
        last_observed = excluded.last_observed,
        detection_count = gaps.detection_count + 1,
        signals = excluded.signals,
        metadata = excluded.metadata,
        updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    `)

    this.stmtGetGap = this.db.prepare('SELECT * FROM gaps WHERE id = ?')
    this.stmtGetGapsByStatus = this.db.prepare('SELECT * FROM gaps WHERE status = ? ORDER BY priority DESC')
    this.stmtUpdateStatus = this.db.prepare(`
      UPDATE gaps SET status = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
      WHERE id = ?
    `)
    this.stmtInsertHistory = this.db.prepare(`
      INSERT INTO gap_history (gap_id, action, details) VALUES (?, ?, ?)
    `)
    this.stmtGetPending = this.db.prepare(`
      SELECT * FROM gaps WHERE status IN ('pending', 'scheduled')
      ORDER BY priority DESC
      LIMIT ?
    `)
  }


  /**
   * Run a full detection cycle on the given graph state.
   * Returns newly detected and updated gaps.
   */
  detectGaps(graph: UnifiedGraph): GapCandidate[] {
    const now = new Date().toISOString()
    const detected: GapCandidate[] = []

    // Reset memoized reverse-adjacency for this cycle; the helper builds it
    // lazily on first use, then all detectors share one map.
    this.reverseAdjCache = null

    detected.push(...this.detectUnderconnected(graph, now))
    detected.push(...this.detectFragmented(graph, now))
    detected.push(...this.detectMissingFocus(graph, now))
    detected.push(...this.detectIsolatedNuclei(graph, now))

    // Persist all detected gaps
    const persisted = this.persistGaps(detected, now)

    this.logger.info('Gap detection cycle complete', {
      detected: detected.length,
      persisted: persisted.length,
    })

    return persisted
  }

  /** Get a gap by ID. */
  getGap(id: string): GapCandidate | undefined {
    const row = this.stmtGetGap.get(id) as GapRow | undefined
    return row ? this.rowToCandidate(row) : undefined
  }

  /** Get all gaps with a given status. */
  getGapsByStatus(status: GapStatus): GapCandidate[] {
    const rows = this.stmtGetGapsByStatus.all(status) as GapRow[]
    return rows.map(r => this.rowToCandidate(r))
  }

  /** Get pending/scheduled gaps, ordered by priority. */
  getPendingGaps(limit: number = 20): GapCandidate[] {
    const rows = this.stmtGetPending.all(limit) as GapRow[]
    return rows.map(r => this.rowToCandidate(r))
  }

  /** Update a gap's status with audit trail. */
  updateStatus(id: string, status: GapStatus, details?: string): void {
    const now = new Date().toISOString()
    this.stmtUpdateStatus.run(status, id)
    this.stmtInsertHistory.run(id, `status:${status}`, details ?? null)
    this.logger.debug('Gap status updated', { id, status, details })
  }

  /** Close the database. */
  close(): void {
    if (this.ownsDb) {
      this.db.close()
    }
  }


  private detectUnderconnected(graph: UnifiedGraph, now: string): GapCandidate[] {
    if (graph.nodes.size === 0) return []

    const edgeCounts = new Map<string, number>()
    let totalEdges = 0

    for (const [nodeId] of graph.nodes) {
      const out = graph.edges.get(nodeId)?.length ?? 0
      const inCount = this.countInEdges(graph, nodeId)
      const degree = out + inCount
      edgeCounts.set(nodeId, degree)
      totalEdges += degree
    }

    // Average degree for the graph
    const avgDegree = totalEdges / graph.nodes.size
    const threshold = avgDegree * this.config.lowEdgeDensityThreshold
    if (threshold < 0.5) return [] // Graph too sparse to meaningfully detect

    const gaps: GapCandidate[] = []

    for (const [nodeId, degree] of edgeCounts) {
      if (degree < threshold && degree >= 0) {
        const node = graph.nodes.get(nodeId)!
        const ratio = avgDegree > 0 ? degree / avgDegree : 0
        const strength = Math.max(0, 1 - ratio)

        gaps.push(this.createGap(
          'underconnected',
          [nodeId],
          [{ type: 'low_edge_density', strength, provenance: `degree=${degree}/avg=${avgDegree.toFixed(1)}` }],
          now,
          { nodeLabel: node.label, degree, avgDegree: avgDegree.toFixed(2) },
        ))
      }
    }

    return gaps.slice(0, this.config.maxGaps)
  }

  private detectFragmented(graph: UnifiedGraph, now: string): GapCandidate[] {
    if (graph.nodes.size < 4) return []

    const components = this.findConnectedComponents(graph)
    if (components.length <= 1) return []

    // A fragmented graph has many components relative to node count
    // and no dominant component
    const sizes = components.map(c => c.length).sort((a, b) => b - a)
    const largestRatio = sizes[0] / graph.nodes.size

    if (largestRatio > (1 - this.config.fragmentationCoherenceThreshold)) {
      return [] // One dominant component — not fragmented enough
    }

    const gaps: GapCandidate[] = []

    // Flag small-to-medium components that should be connected
    for (let i = 1; i < components.length; i++) {
      const component = components[i]
      if (component.length < 2) continue // Skip isolated singletons

      const nodeLabels = component
        .slice(0, 5)
        .map(id => graph.nodes.get(id)?.label ?? id)

      gaps.push(this.createGap(
        'fragmented',
        component,
        [{
          type: 'low_coherence',
          strength: 1 - largestRatio,
          provenance: `component_size=${component.length}/total=${graph.nodes.size}`,
        }],
        now,
        { componentSize: component.length, sampleLabels: nodeLabels },
      ))
    }

    return gaps.slice(0, this.config.maxGaps)
  }

  private detectMissingFocus(graph: UnifiedGraph, now: string): GapCandidate[] {
    // Look for nodes mentioned in foci (from source metadata) but with
    // low graph presence — present in the graph but under-connected
    const gaps: GapCandidate[] = []

    for (const [nodeId, node] of graph.nodes) {
      // High-centrality nodes with low edge count are "known but underexplored"
      const outEdges = graph.edges.get(nodeId) ?? []
      const inEdges = this.countInEdges(graph, nodeId)
      const degree = outEdges.length + inEdges

      // A node with high resonance but low degree is a focus gap
      if (node.resonance > 0.5 && degree <= 1) {
        gaps.push(this.createGap(
          'missing_focus',
          [nodeId],
          [{
            type: 'missing_portal',
            strength: node.resonance,
            provenance: `resonance=${node.resonance.toFixed(2)}/degree=${degree}`,
          }],
          now,
          { nodeLabel: node.label, resonance: node.resonance, degree },
        ))
      }
    }

    return gaps.slice(0, this.config.maxGaps)
  }

  private detectIsolatedNuclei(graph: UnifiedGraph, now: string): GapCandidate[] {
    if (graph.nodes.size < this.config.minNucleusSize * 2) return []

    const components = this.findConnectedComponents(graph)
    const gaps: GapCandidate[] = []

    for (const component of components) {
      if (component.length < this.config.minNucleusSize) continue

      // Count bridges: edges from this component to other components
      const componentSet = new Set(component)
      let bridgeCount = 0
      const bridgeTargets = new Set<string>()

      for (const nodeId of component) {
        const outEdges = graph.edges.get(nodeId) ?? []
        for (const edge of outEdges) {
          if (!componentSet.has(edge.targetId)) {
            bridgeCount++
            bridgeTargets.add(edge.targetId)
          }
        }
        // Also check in-edges from outside
        const inEdges = this.getInEdges(graph, nodeId)
        for (const edge of inEdges) {
          if (!componentSet.has(edge.sourceId)) {
            bridgeCount++
            bridgeTargets.add(edge.sourceId)
          }
        }
      }

      if (bridgeCount <= this.config.maxNucleusBridges) {
        const nodeLabels = component
          .slice(0, 5)
          .map(id => graph.nodes.get(id)?.label ?? id)

        gaps.push(this.createGap(
          'isolated_nucleus',
          component,
          [{
            type: 'persistent_unresolved',
            strength: Math.min(1.0, component.length / graph.nodes.size),
            provenance: `size=${component.length}/bridges=${bridgeCount}`,
          }],
          now,
          { componentSize: component.length, bridgeCount, bridgeTargets: [...bridgeTargets], sampleLabels: nodeLabels },
        ))
      }
    }

    return gaps.slice(0, this.config.maxGaps)
  }


  private getReverseAdj(graph: UnifiedGraph): Map<string, string[]> {
    if (this.reverseAdjCache) return this.reverseAdjCache
    const reverse = new Map<string, string[]>()
    for (const [, outEdges] of graph.edges) {
      for (const edge of outEdges) {
        let bucket = reverse.get(edge.targetId)
        if (!bucket) {
          bucket = []
          reverse.set(edge.targetId, bucket)
        }
        bucket.push(edge.sourceId)
      }
    }
    this.reverseAdjCache = reverse
    return reverse
  }

  private countInEdges(graph: UnifiedGraph, nodeId: string): number {
    return this.getReverseAdj(graph).get(nodeId)?.length ?? 0
  }

  private getInEdges(graph: UnifiedGraph, nodeId: string): CognitiveEdge[] {
    const sources = this.getReverseAdj(graph).get(nodeId)
    if (!sources?.length) return []
    const result: CognitiveEdge[] = []
    for (const sourceId of sources) {
      const outEdges = graph.edges.get(sourceId) ?? []
      for (const edge of outEdges) {
        if (edge.targetId === nodeId) result.push(edge)
      }
    }
    return result
  }

  private findConnectedComponents(graph: UnifiedGraph): string[][] {
    const reverseAdj = this.getReverseAdj(graph)
    const visited = new Set<string>()
    const components: string[][] = []

    for (const [nodeId] of graph.nodes) {
      if (visited.has(nodeId)) continue

      const component: string[] = []
      const queue = [nodeId]
      visited.add(nodeId)

      while (queue.length > 0) {
        const current = queue.shift()!
        component.push(current)

        const outEdges = graph.edges.get(current) ?? []
        for (const edge of outEdges) {
          if (!visited.has(edge.targetId) && graph.nodes.has(edge.targetId)) {
            visited.add(edge.targetId)
            queue.push(edge.targetId)
          }
        }

        const inEdgeSources = reverseAdj.get(current) ?? []
        for (const sourceId of inEdgeSources) {
          if (!visited.has(sourceId) && graph.nodes.has(sourceId)) {
            visited.add(sourceId)
            queue.push(sourceId)
          }
        }
      }

      components.push(component)
    }

    return components.sort((a, b) => b.length - a.length)
  }


  private createGap(
    category: GapCategory,
    nodeIds: string[],
    signals: SignalDetail[],
    now: string,
    metadata: Record<string, unknown> = {},
  ): GapCandidate {
    const sortedIds = [...nodeIds].sort()
    const id = this.stableHash(category, sortedIds)

    return {
      id,
      category,
      scope: { nodeIds: sortedIds },
      signals,
      priority: this.computePriority(signals, sortedIds.length, metadata),
      status: 'pending',
      observedSince: now,
      lastObserved: now,
      detectionCount: 1,
      metadata,
    }
  }

  private computePriority(
    signals: SignalDetail[],
    scopeSize: number,
    metadata: Record<string, unknown>,
  ): number {
    // Signal strength: weighted average of signal strengths
    const signalStrength = signals.length > 0
      ? signals.reduce((sum, s) => sum + s.strength, 0) / signals.length
      : 0

    // Strategic value: check if any affected modules have multipliers
    const strategicValue = this.config.strategicValues[
      (metadata.affectedModules as string[])?.[0] ?? ''
    ] ?? 1.0

    // Composite priority with bounded output
    const raw = signalStrength * 0.7 * strategicValue
    return Math.min(1.0, Math.max(0.0, raw))
  }

  private stableHash(category: string, sortedIds: string[]): string {
    const payload = `${category}:${sortedIds.join(',')}`
    return crypto.createHash('sha256').update(payload).digest('hex').slice(0, 16)
  }

  private persistGaps(gaps: GapCandidate[], now: string): GapCandidate[] {
    const results: GapCandidate[] = []

    const upsert = this.db.transaction(() => {
      for (const gap of gaps) {
        // Check if gap already exists to preserve status
        const existing = this.stmtGetGap.get(gap.id) as GapRow | undefined

        if (existing && existing.status !== 'pending') {
          // Existing gap that's been scheduled or is in meditation —
          // update detection count and lastObserved but don't regress status
          this.db.prepare(`
            UPDATE gaps SET
              last_observed = ?,
              detection_count = detection_count + 1,
              signals = ?,
              updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE id = ?
          `).run(now, JSON.stringify(gap.signals), gap.id)

          results.push({
            ...gap,
            status: existing.status as GapStatus,
            detectionCount: existing.detection_count + 1,
            observedSince: existing.observed_since,
          })
        } else {
          // New gap or re-detected pending gap — upsert increments detection_count
          const prevRow = this.stmtGetGap.get(gap.id) as GapRow | undefined
          const prevCount = prevRow?.detection_count ?? 0

          this.stmtUpsertGap.run(
            gap.id,
            gap.category,
            JSON.stringify(gap.scope.nodeIds),
            gap.scope.expectedEdges ? JSON.stringify(gap.scope.expectedEdges) : null,
            gap.scope.affectedModules ? JSON.stringify(gap.scope.affectedModules) : null,
            JSON.stringify(gap.signals),
            gap.priority,
            gap.status,
            gap.observedSince,
            gap.lastObserved,
            gap.detectionCount,
            JSON.stringify(gap.metadata),
          )

          // Read back actual detection_count from DB (upsert may have incremented it)
          const upserted = this.stmtGetGap.get(gap.id) as GapRow | undefined
          results.push({
            ...gap,
            detectionCount: upserted?.detection_count ?? prevCount + 1,
            observedSince: upserted?.observed_since ?? gap.observedSince,
          })
        }

        this.stmtInsertHistory.run(gap.id, 'detected', JSON.stringify({ priority: gap.priority, signalCount: gap.signals.length }))
      }
    })

    upsert()
    return results
  }

  private rowToCandidate(row: GapRow): GapCandidate {
    return {
      id: row.id,
      category: row.category as GapCategory,
      scope: {
        nodeIds: JSON.parse(row.scope_node_ids),
        expectedEdges: row.scope_expected_edges ? JSON.parse(row.scope_expected_edges) : undefined,
        affectedModules: row.scope_affected_modules ? JSON.parse(row.scope_affected_modules) : undefined,
      },
      signals: JSON.parse(row.signals),
      priority: row.priority,
      status: row.status as GapStatus,
      observedSince: row.observed_since,
      lastObserved: row.last_observed,
      detectionCount: row.detection_count,
      metadata: JSON.parse(row.metadata),
    }
  }
}



interface GapRow {
  id: string
  category: string
  scope_node_ids: string
  scope_expected_edges: string | null
  scope_affected_modules: string | null
  signals: string
  priority: number
  status: string
  observed_since: string
  last_observed: string
  detection_count: number
  metadata: string
}
