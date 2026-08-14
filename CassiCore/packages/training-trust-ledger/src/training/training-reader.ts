/**
 * Training Reader — Search, query, and export interface for the training warehouse.
 *
 * Provides:
 * - Full-text search over chunks (FTS5)
 * - Filtered queries by labels, quality, type, session
 * - Object resolution (ref key → full object with labels and metrics)
 * - Dataset assembly for JSONL export
 * - Stats and analytics
 */

import type { ILogger } from '@cassicore/foundation'
import { TrainingStore } from './training-store.js'
import type {
  TrainingObject,
  TrainingChunk,
  TrainingExample,
  AssembledTurn,
  TrainingWarehouseStats,
  QualityMetric,
} from './training-types.js'

// SEARCH TYPES

export interface ChunkSearchResult {
  chunk_id: string
  chunk_ref: string
  chunk_type: string
  text: string
  role: string | null
  session_id: string | null
  object_id: string
  object_type: string
  score: number
}

export interface ObjectSearchResult {
  object_id: string
  object_type: string
  subtype: string | null
  ref_key: string
  root_session_id: string | null
  created_at: number
  labels: Array<{ namespace: string; name: string; confidence: number; source: string }>
  quality: Record<string, number>
}

export interface SearchFilters {
  /** Full-text search query (FTS5 syntax). */
  query?: string
  /** Filter by object types. */
  objectTypes?: string[]
  /** Filter by label namespace:name pairs. */
  labels?: Array<{ namespace: string; name: string }>
  /** Minimum quality metric value. */
  minQuality?: { metric: string; value: number }
  /** Filter by session ID. */
  sessionId?: string
  /** Filter by role. */
  role?: string
  /** Filter by chunk type. */
  chunkType?: string
  /** Time range (unix ms). */
  startTime?: number
  endTime?: number
  /** Max results. */
  limit?: number
  /** Offset for pagination. */
  offset?: number
}

export interface ExportFilters {
  /** Minimum trainability score. */
  minTrainability?: number
  /** Maximum privacy risk score. */
  maxPrivacyRisk?: number
  /** Required label (namespace:name). */
  requiredLabels?: Array<{ namespace: string; name: string }>
  /** Excluded labels. */
  excludeLabels?: Array<{ namespace: string; name: string }>
  /** Session types to include. */
  sessionTypes?: string[]
  /** Max examples to export. */
  limit?: number
}

// READER CLASS

export class TrainingReader {
  private readonly store: TrainingStore
  private readonly logger: ILogger

  constructor(store: TrainingStore, logger: ILogger) {
    this.store = store
    this.logger = logger.child('training-reader')
  }

  // FULL-TEXT SEARCH

  /**
   * Search chunks using FTS5.
   * Supports full FTS5 query syntax (AND, OR, NEAR, prefix*, "phrase").
   */
  searchChunks(query: string, filters: SearchFilters = {}): ChunkSearchResult[] {
    const limit = filters.limit ?? 50
    const offset = filters.offset ?? 0

    const whereClauses: string[] = []
    const params: unknown[] = []

    // FTS match
    if (query && query.trim()) {
      whereClauses.push(`c.rowid IN (SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ?)`)
      params.push(query)
    }

    if (filters.role) {
      whereClauses.push(`c.role = ?`)
      params.push(filters.role)
    }
    if (filters.chunkType) {
      whereClauses.push(`c.chunk_type = ?`)
      params.push(filters.chunkType)
    }
    if (filters.sessionId) {
      whereClauses.push(`c.session_id = ?`)
      params.push(filters.sessionId)
    }
    if (filters.objectTypes?.length) {
      whereClauses.push(`o.object_type IN (${filters.objectTypes.map(() => '?').join(',')})`)
      params.push(...filters.objectTypes)
    }

    const whereStr = whereClauses.length ? `WHERE ${whereClauses.join(' AND ')}` : ''

    // Rank by FTS score if searching, otherwise by recency
    const orderBy = query?.trim()
      ? `ORDER BY rank`
      : `ORDER BY o.created_at DESC`

    const sql = `
      SELECT
        c.chunk_id, c.chunk_ref, c.chunk_type, c.text, c.role, c.session_id,
        c.object_id, o.object_type,
        ${query?.trim() ? `rank AS score` : `0 AS score`}
      FROM chunks c
      JOIN objects o ON o.object_id = c.object_id
      ${query?.trim() ? `JOIN chunks_fts fts ON fts.rowid = c.rowid` : ''}
      ${whereStr}
      ${orderBy}
      LIMIT ? OFFSET ?
    `
    params.push(limit, offset)

    return this.store.db.prepare(sql).all(...params) as ChunkSearchResult[]
  }

  // OBJECT SEARCH (with labels and quality)

  /**
   * Search objects with label and quality filters.
   * Returns objects enriched with their labels and quality metrics.
   */
  searchObjects(filters: SearchFilters = {}): ObjectSearchResult[] {
    const limit = filters.limit ?? 50
    const offset = filters.offset ?? 0

    const whereClauses: string[] = []
    const params: unknown[] = []

    if (filters.objectTypes?.length) {
      whereClauses.push(`o.object_type IN (${filters.objectTypes.map(() => '?').join(',')})`)
      params.push(...filters.objectTypes)
    }
    if (filters.sessionId) {
      whereClauses.push(`o.root_session_id = ?`)
      params.push(filters.sessionId)
    }
    if (filters.startTime) {
      whereClauses.push(`o.created_at >= ?`)
      params.push(filters.startTime)
    }
    if (filters.endTime) {
      whereClauses.push(`o.created_at <= ?`)
      params.push(filters.endTime)
    }

    // Label filter: require objects that have ALL specified labels
    if (filters.labels?.length) {
      for (let i = 0; i < filters.labels.length; i++) {
        const l = filters.labels[i]
        whereClauses.push(`EXISTS (
          SELECT 1 FROM object_labels ol${i}
          JOIN taxonomy_labels tl${i} ON tl${i}.label_id = ol${i}.label_id
          WHERE ol${i}.object_id = o.object_id
            AND tl${i}.namespace = ? AND tl${i}.name = ?
        )`)
        params.push(l.namespace, l.name)
      }
    }

    // Quality filter
    if (filters.minQuality) {
      whereClauses.push(`EXISTS (
        SELECT 1 FROM quality_metrics qm
        WHERE qm.object_id = o.object_id
          AND qm.metric = ? AND qm.value >= ?
      )`)
      params.push(filters.minQuality.metric, filters.minQuality.value)
    }

    const whereStr = whereClauses.length ? `WHERE ${whereClauses.join(' AND ')}` : ''

    const sql = `
      SELECT o.object_id, o.object_type, o.subtype, o.ref_key, o.root_session_id, o.created_at
      FROM objects o
      ${whereStr}
      ORDER BY o.created_at DESC
      LIMIT ? OFFSET ?
    `
    params.push(limit, offset)

    const rows = this.store.db.prepare(sql).all(...params) as Array<{
      object_id: string; object_type: string; subtype: string | null
      ref_key: string; root_session_id: string | null; created_at: number
    }>

    // Enrich with labels and quality
    return rows.map(row => ({
      ...row,
      labels: this.store.getLabels(row.object_id),
      quality: this.getQualityMap(row.object_id),
    }))
  }

  // RESOLVE — ref key or object_id to full object

  /**
   * Resolve a ref key (e.g., S12#T04.M00.C03) or object_id to a full object
   * with labels, quality metrics, and child chunks.
   */
  resolve(refKeyOrId: string): {
    object: TrainingObject | null
    labels: Array<{ namespace: string; name: string; confidence: number; source: string }>
    quality: Record<string, number>
    chunks: TrainingChunk[]
    edges: Array<{ target_id: string; relation: string; weight: number }>
  } | null {
    // Try by object_id first
    let obj = this.store.getObject(refKeyOrId)

    // Try by ref_key
    if (!obj) {
      const row = this.store.db.prepare(`
        SELECT * FROM objects WHERE ref_key = ? LIMIT 1
      `).get(refKeyOrId) as TrainingObject | undefined
      obj = row || undefined
    }

    if (!obj) return null

    const labels = this.store.getLabels(obj.object_id)
    const quality = this.getQualityMap(obj.object_id)

    const chunks = this.store.db.prepare(`
      SELECT * FROM chunks WHERE object_id = ? ORDER BY sequence
    `).all(obj.object_id) as TrainingChunk[]

    const edges = this.store.db.prepare(`
      SELECT target_id, relation, weight FROM object_edges WHERE source_id = ?
    `).all(obj.object_id) as Array<{ target_id: string; relation: string; weight: number }>

    return { object: obj, labels, quality, chunks, edges }
  }

  // DATASET EXPORT — assemble JSONL training examples

  /**
   * Assemble training examples from sessions.
   * Each example is a complete conversation (session → turns → messages)
   * with labels and quality metrics attached.
   */
  assembleExamples(filters: ExportFilters = {}): TrainingExample[] {
    const limit = filters.limit ?? 100

    const whereClauses = [`s.status IN ('completed', 'active')`]
    const params: unknown[] = []

    if (filters.sessionTypes?.length) {
      whereClauses.push(`s.session_type IN (${filters.sessionTypes.map(() => '?').join(',')})`)
      params.push(...filters.sessionTypes)
    }

    if (filters.minTrainability != null) {
      whereClauses.push(`EXISTS (
        SELECT 1 FROM quality_metrics qm
        WHERE qm.object_id = s.object_id AND qm.metric = 'trainability' AND qm.value >= ?
      )`)
      params.push(filters.minTrainability)
    }

    if (filters.maxPrivacyRisk != null) {
      whereClauses.push(`NOT EXISTS (
        SELECT 1 FROM quality_metrics qm
        WHERE qm.object_id = s.object_id AND qm.metric = 'privacy_risk' AND qm.value > ?
      )`)
      params.push(filters.maxPrivacyRisk)
    }

    // Required labels
    if (filters.requiredLabels?.length) {
      for (let i = 0; i < filters.requiredLabels.length; i++) {
        const l = filters.requiredLabels[i]
        whereClauses.push(`EXISTS (
          SELECT 1 FROM object_labels ol
          JOIN taxonomy_labels tl ON tl.label_id = ol.label_id
          WHERE ol.object_id = s.object_id AND tl.namespace = ? AND tl.name = ?
        )`)
        params.push(l.namespace, l.name)
      }
    }

    // Excluded labels
    if (filters.excludeLabels?.length) {
      for (let i = 0; i < filters.excludeLabels.length; i++) {
        const l = filters.excludeLabels[i]
        whereClauses.push(`NOT EXISTS (
          SELECT 1 FROM object_labels ol
          JOIN taxonomy_labels tl ON tl.label_id = ol.label_id
          WHERE ol.object_id = s.object_id AND tl.namespace = ? AND tl.name = ?
        )`)
        params.push(l.namespace, l.name)
      }
    }

    const whereStr = whereClauses.join(' AND ')
    params.push(limit)

    const sessions = this.store.db.prepare(`
      SELECT s.object_id, o.root_session_id, o.ref_key
      FROM sessions s
      JOIN objects o ON o.object_id = s.object_id
      WHERE ${whereStr}
      ORDER BY s.started_at DESC
      LIMIT ?
    `).all(...params) as Array<{ object_id: string; root_session_id: string; ref_key: string }>

    const examples: TrainingExample[] = []

    for (const sess of sessions) {
      const example = this.assembleSession(sess.object_id, sess.root_session_id)
      if (example && example.turns.length > 0) {
        examples.push(example)
      }
    }

    return examples
  }

  private assembleSession(sessionObjectId: string, rootSessionId: string): TrainingExample | null {
    // Get turns
    const turns = this.store.db.prepare(`
      SELECT t.object_id, t.sequence, t.role, t.subrole, t.has_tool_calls, t.has_reasoning
      FROM turns t
      WHERE t.session_id = ?
      ORDER BY t.sequence
    `).all(sessionObjectId) as Array<{
      object_id: string; sequence: number; role: string; subrole: string | null
      has_tool_calls: number; has_reasoning: number
    }>

    const assembledTurns: AssembledTurn[] = []

    for (const turn of turns) {
      // Get messages for this turn
      const msgs = this.store.db.prepare(`
        SELECT content_text, content_type FROM messages WHERE turn_id = ? ORDER BY sequence
      `).all(turn.object_id) as Array<{ content_text: string; content_type: string }>

      const content = msgs
        .filter(m => m.content_text)
        .map(m => m.content_text)
        .join('\n')

      if (!content) continue

      const assembled: AssembledTurn = {
        role: turn.role,
        content,
      }

      // Add tool calls if present
      if (turn.has_tool_calls) {
        const toolCalls = this.store.db.prepare(`
          SELECT tool_name, input_json, output_json, status
          FROM tool_calls WHERE turn_id = ? ORDER BY sequence
        `).all(turn.object_id) as Array<{
          tool_name: string; input_json: string; output_json: string; status: string
        }>

        assembled.tool_calls = toolCalls.map(tc => ({
          name: tc.tool_name,
          input: tc.input_json ? JSON.parse(tc.input_json) : null,
          output: tc.output_json ? JSON.parse(tc.output_json) : null,
          status: tc.status,
        }))
      }

      // Add reasoning if present
      if (turn.has_reasoning) {
        const traces = this.store.db.prepare(`
          SELECT object_id, reasoning_type FROM reasoning_traces WHERE turn_id = ? LIMIT 1
        `).all(turn.object_id) as Array<{ object_id: string; reasoning_type: string }>

        if (traces.length) {
          const trace = traces[0]
          const steps = this.store.db.prepare(`
            SELECT step_type, content, confidence FROM reasoning_steps
            WHERE trace_id = ? ORDER BY sequence
          `).all(trace.object_id) as Array<{ step_type: string; content: string; confidence: number }>

          assembled.reasoning = {
            type: trace.reasoning_type,
            steps: steps.map(s => ({
              role: s.step_type,
              content: s.content,
              confidence: s.confidence ?? 0,
            })),
          }
        }
      }

      assembledTurns.push(assembled)
    }

    if (!assembledTurns.length) return null

    // Get labels and quality for the session
    const labels = this.store.getLabels(sessionObjectId)
    const labelMap: Record<string, string[]> = {}
    for (const l of labels) {
      if (!labelMap[l.namespace]) labelMap[l.namespace] = []
      labelMap[l.namespace].push(l.name)
    }

    return {
      id: sessionObjectId,
      session_id: rootSessionId,
      turns: assembledTurns,
      labels: labelMap,
      quality: this.getQualityMap(sessionObjectId),
      metadata: {},
    }
  }

  // ANALYTICS

  /** Get full warehouse stats. */
  getStats(): TrainingWarehouseStats {
    return this.store.getStats()
  }

  /** Get label distribution across all objects. */
  getLabelDistribution(namespace?: string): Array<{ namespace: string; name: string; count: number }> {
    let sql = `
      SELECT tl.namespace, tl.name, COUNT(*) as count
      FROM object_labels ol
      JOIN taxonomy_labels tl ON tl.label_id = ol.label_id
    `
    const params: unknown[] = []
    if (namespace) {
      sql += ` WHERE tl.namespace = ?`
      params.push(namespace)
    }
    sql += ` GROUP BY tl.namespace, tl.name ORDER BY count DESC`

    return this.store.db.prepare(sql).all(...params) as Array<{ namespace: string; name: string; count: number }>
  }

  /** Get quality metric distribution. */
  getQualityDistribution(metric: string): {
    avg: number; min: number; max: number; count: number
    histogram: Array<{ bucket: string; count: number }>
  } {
    const stats = this.store.db.prepare(`
      SELECT AVG(value) as avg, MIN(value) as min, MAX(value) as max, COUNT(*) as count
      FROM quality_metrics WHERE metric = ?
    `).get(metric) as { avg: number; min: number; max: number; count: number }

    // Build 10-bucket histogram
    const histogram: Array<{ bucket: string; count: number }> = []
    for (let i = 0; i < 10; i++) {
      const lo = i / 10
      const hi = (i + 1) / 10
      const row = this.store.db.prepare(`
        SELECT COUNT(*) as count FROM quality_metrics
        WHERE metric = ? AND value >= ? AND value < ?
      `).get(metric, lo, hi === 1.0 ? 1.01 : hi) as { count: number }
      histogram.push({ bucket: `${lo.toFixed(1)}-${hi.toFixed(1)}`, count: row.count })
    }

    return { ...stats, histogram }
  }

  /** Get annotation run summary. */
  getAnnotationSummary(): {
    total: number; completed: number; failed: number
    totalTokens: number; byModel: Record<string, number>
  } {
    const total = (this.store.db.prepare(`SELECT COUNT(*) as c FROM annotation_runs`).get() as any).c
    const completed = (this.store.db.prepare(`SELECT COUNT(*) as c FROM annotation_runs WHERE status = 'completed'`).get() as any).c
    const failed = (this.store.db.prepare(`SELECT COUNT(*) as c FROM annotation_runs WHERE status = 'failed'`).get() as any).c
    const totalTokens = (this.store.db.prepare(`SELECT COALESCE(SUM(tokens_used), 0) as t FROM annotation_runs`).get() as any).t

    const byModelRows = this.store.db.prepare(`
      SELECT model, COUNT(*) as c FROM annotation_runs GROUP BY model
    `).all() as Array<{ model: string; c: number }>
    const byModel: Record<string, number> = {}
    for (const row of byModelRows) byModel[row.model] = row.c

    return { total, completed, failed, totalTokens, byModel }
  }

  // HELPERS

  private getQualityMap(objectId: string): Record<string, number> {
    const metrics = this.store.getQualityMetrics(objectId)
    const map: Record<string, number> = {}
    for (const m of metrics) map[m.metric] = m.value
    return map
  }
}
