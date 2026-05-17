import Database from 'better-sqlite3'
import { randomUUID } from 'node:crypto'
import type { ILogger } from '../../../types/interfaces.js'
import { initMnemicFieldSchema } from './schema.js'
import { PolarQuantCodec, isPolarQuantBlob } from './polar-quant.js'
import type {
  Engram, EngramCreate, EngramUpdate,
  MnemicSynapse, SynapseCreate,
  ActivationSpike, SpikeCreate,
  Nucleus, NucleusCreate,
  SpatialQuery, EngramSearchResult, TensionPair, FieldStats,
  EngramPosition, EngramType,
  ForwardTrace,
  LightningRetrievalEvent,
  LightningRetrievalEventQuery,
} from './types.js'
import type {
  RetrievalLabel,
  RetrievalLabelTriple,
} from '../reverie/retrieval-labeler-types.js'

const FORWARD_TRACE_AUTO_PRUNE_INTERVAL = 100
const FORWARD_TRACE_AUTO_MAX_AGE_MS = 3_600_000
const FORWARD_TRACE_AUTO_MAX_ROWS = 5_000

const DEFAULT_EMBEDDING_DIM = 1024
const EMBEDDING_QUANT_BITS = 3

const _pqCodecs = new Map<string, PolarQuantCodec>()
function getPqCodec(dim: number, bits: number = EMBEDDING_QUANT_BITS): PolarQuantCodec {
  const key = `${dim}:${bits}`
  let codec = _pqCodecs.get(key)
  if (!codec) {
    codec = new PolarQuantCodec(dim, bits)
    _pqCodecs.set(key, codec)
  }
  return codec
}

const PQ_HEADER_LEN = 12  // magic(4) + version(1) + bits(1) + dimension(2) + norm(4)

/**
 * @dep flows: WriteFileHandler → ToFloatArray (6/6)
 * @dep module: Unknown
 * @dep risk: LOW | 0 callers, 1 flow, 1 module
 */

export function toFloatArray(buf: Buffer | null): Float32Array | null {
  if (!buf || buf.length === 0) return null
  // PolarQuant blobs start with the 4-byte magic "PLQT" (1 in 2^32 false
  // positive rate). For raw Float32 BLOBs the first 4 bytes are the LSBs of
  // the first float, so collision is astronomically unlikely.
  if (isPolarQuantBlob(buf) && buf.length >= PQ_HEADER_LEN) {
    // Self-describing header: read dimension and bit-width from the blob.
    const dim = buf.readUInt16LE(6)
    const bits = buf[5]
    return getPqCodec(dim, bits).decode(buf)
  }
  return new Float32Array(buf.buffer, buf.byteOffset, buf.byteLength / 4)
}

export function fromFloatArray(arr: Float32Array | number[] | null | undefined): Buffer | null {
  if (!arr) return null
  const f32 = arr instanceof Float32Array ? arr : new Float32Array(arr)
  return Buffer.from(f32.buffer, f32.byteOffset, f32.byteLength)
}

export function compressEmbedding(arr: Float32Array | number[] | null | undefined): Buffer | null {
  if (!arr) return null
  const f32 = arr instanceof Float32Array ? arr : new Float32Array(arr)
  // PolarQuant requires power-of-2 dimension for the Walsh-Hadamard
  // transform and needs sufficient dimension (>= DEFAULT_EMBEDDING_DIM)
  // for 3-bit quantization to preserve per-element precision well enough
  // to maintain meaningful cosine similarity. For small or odd dimensions,
  // fall back to raw Float32Array storage.
  if (f32.length < DEFAULT_EMBEDDING_DIM || (f32.length & (f32.length - 1)) !== 0) {
    return fromFloatArray(f32)
  }
  return getPqCodec(f32.length).encode(f32)
}

/**
 * @dep flows: WriteFileHandler → ParseJsonSafe (6/6)
 * @dep module: Unknown
 * @dep risk: LOW | 0 callers, 1 flow, 1 module
 */

export function parseJsonSafe<T>(raw: string | null | undefined, fallback: T): T {
  if (!raw) return fallback
  try { return JSON.parse(raw) as T } catch { return fallback }
}

export function computeSpikeImportance(
  spikes: Array<{ timestamp: number; magnitude: number }>,
  decayRate: number,
): number {
  if (spikes.length === 0) return 0
  const now = Date.now()
  let sum = 0
  for (const spike of spikes) {
    const elapsed = Math.max(1, (now - spike.timestamp) / 1000)
    sum += spike.magnitude * Math.pow(elapsed, -decayRate)
  }
  return Math.log1p(sum)
}

export function computeAlpha(
  spikeCount: number,
  config: { alphaMin: number; alphaMax: number; alphaTau: number },
): number {
  return config.alphaMin + (config.alphaMax - config.alphaMin) * (1 - Math.exp(-spikeCount / config.alphaTau))
}

export function cosineSimilarity(a: ArrayLike<number>, b: ArrayLike<number>): number {
  if (a.length !== b.length || a.length === 0) return 0
  let dot = 0, normA = 0, normB = 0
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i]
    normA += a[i] * a[i]
    normB += b[i] * b[i]
  }
  const denom = Math.sqrt(normA) * Math.sqrt(normB)
  return denom > 0 ? dot / denom : 0
}

/**
 * @dep flows: WriteFileHandler → ToFloatArray (5/6), WriteFileHandler → ParseJsonSafe (5/6)
 * @dep module: Unknown
 * @dep risk: LOW | 0 callers, 2 flows, 1 module
 */

function rowToEngram(row: Record<string, unknown>): Engram {
  return {
    id: row.id as string,
    content: row.content as string,
    nodeType: row.node_type as Engram['nodeType'],
    x: row.x as number,
    y: row.y as number,
    t: row.t as number,
    potentiation: row.potentiation as number,
    clusterId: (row.cluster_id as string) || null,
    embedding: toFloatArray(row.embedding as Buffer | null),
    tags: parseJsonSafe(row.tags as string, []),
    provenance: (row.provenance as string) || '',
    createdAt: row.created_at as string,
    accessedAt: (row.accessed_at as string) || null,
    metadata: parseJsonSafe(row.metadata as string, {}),
  }
}

function rowToSynapse(row: Record<string, unknown>): MnemicSynapse {
  return {
    sourceId: row.source_id as string,
    targetId: row.target_id as string,
    edgeType: row.edge_type as MnemicSynapse['edgeType'],
    weight: row.weight as number,
    createdAt: row.created_at as string,
    metadata: parseJsonSafe(row.metadata as string, {}),
  }
}

function rowToSpike(row: Record<string, unknown>): ActivationSpike {
  return {
    id: row.id as number,
    engramId: row.engram_id as string,
    timestamp: row.timestamp as number,
    magnitude: row.magnitude as number,
    taskContext: (row.task_context as string) || null,
    outcome: (row.outcome as ActivationSpike['outcome']) || null,
  }
}

function rowToNucleus(row: Record<string, unknown>): Nucleus {
  return {
    id: row.id as string,
    label: (row.label as string) || '',
    centroidX: row.centroid_x as number,
    centroidY: row.centroid_y as number,
    memberCount: row.member_count as number,
    avgPotentiation: row.avg_potentiation as number,
    abstractionId: (row.abstraction_id as string) || null,
    createdAt: row.created_at as string,
    updatedAt: row.updated_at as string,
  }
}

export class Cortex {
  private db: Database.Database
  private logger: ILogger
  private stmts!: ReturnType<typeof this.prepareStatements>
  private traceWriteCount = 0

  constructor(db: Database.Database, logger: ILogger) {
    this.db = db
    this.logger = logger.child ? logger.child('mnemic-cortex') : logger
    initMnemicFieldSchema(db)
    this.stmts = this.prepareStatements()
    this.logger.info('Mnemic Cortex initialized')
  }

  private prepareStatements() {
    return {
      insertEngram: this.db.prepare(`
        INSERT INTO engrams (id, content, node_type, x, y, t, potentiation, cluster_id, embedding, tags, provenance, created_at, accessed_at, metadata, file_path, content_hash)
        VALUES (@id, @content, @node_type, @x, @y, @t, @potentiation, NULL, @embedding, @tags, @provenance, @created_at, NULL, @metadata, @file_path, @content_hash)
      `),
      getEngram: this.db.prepare(`SELECT * FROM engrams WHERE id = ?`),
      deleteEngram: this.db.prepare(`DELETE FROM engrams WHERE id = ?`),
      listEngrams: this.db.prepare(`SELECT * FROM engrams ORDER BY potentiation DESC LIMIT ?`),
      listEngramsByType: this.db.prepare(`SELECT * FROM engrams WHERE node_type = ? ORDER BY potentiation DESC LIMIT ?`),
      countEngrams: this.db.prepare(`SELECT COUNT(*) as count FROM engrams`),

      insertRtree: this.db.prepare(`
        INSERT INTO engram_rtree (id, x_min, x_max, y_min, y_max, t_min, t_max, potentiation_min, potentiation_max)
        VALUES (@id, @x, @x, @y, @y, @t, @t, @potentiation, @potentiation)
      `),
      updateRtree: this.db.prepare(`
        UPDATE engram_rtree SET x_min = @x, x_max = @x, y_min = @y, y_max = @y, t_min = @t, t_max = @t, potentiation_min = @p, potentiation_max = @p
        WHERE id = @id
      `),
      deleteRtree: this.db.prepare(`DELETE FROM engram_rtree WHERE id = ?`),

      insertSynapse: this.db.prepare(`
        INSERT OR REPLACE INTO mnemic_synapses (source_id, target_id, edge_type, weight, created_at, metadata)
        VALUES (@source_id, @target_id, @edge_type, @weight, @created_at, @metadata)
      `),
      getSynapse: this.db.prepare(`
        SELECT * FROM mnemic_synapses WHERE source_id = ? AND target_id = ? AND edge_type = ?
      `),
      deleteSynapse: this.db.prepare(`
        DELETE FROM mnemic_synapses WHERE source_id = ? AND target_id = ? AND edge_type = ?
      `),
      getOutgoingSynapses: this.db.prepare(`
        SELECT * FROM mnemic_synapses WHERE source_id = ?
      `),
      getIncomingSynapses: this.db.prepare(`
        SELECT * FROM mnemic_synapses WHERE target_id = ?
      `),
      getAllSynapses: this.db.prepare(`
        SELECT * FROM mnemic_synapses WHERE source_id = ? OR target_id = ?
      `),
      countSynapses: this.db.prepare(`SELECT COUNT(*) as count FROM mnemic_synapses`),

      getEngramsByIdPrefixAsc: this.db.prepare(`
        SELECT * FROM engrams WHERE id LIKE ? || '%' ORDER BY t ASC, id ASC LIMIT ? OFFSET ?
      `),
      getEngramsByIdPrefixDesc: this.db.prepare(`
        SELECT * FROM engrams WHERE id LIKE ? || '%' ORDER BY t DESC, id DESC LIMIT ? OFFSET ?
      `),
      getEngramsBySessionId: this.db.prepare(`
        SELECT * FROM engrams WHERE session_id = ? ORDER BY t ASC LIMIT ?
      `),
      getEngramsBySessionIdOffset: this.db.prepare(`
        SELECT * FROM engrams WHERE session_id = ? ORDER BY t ASC LIMIT ? OFFSET ?
      `),
      getOutgoingTypedSynapses: this.db.prepare(`
        SELECT * FROM mnemic_synapses WHERE source_id = ? AND edge_type = ?
      `),
      getIncomingTypedSynapses: this.db.prepare(`
        SELECT * FROM mnemic_synapses WHERE target_id = ? AND edge_type = ?
      `),
      findBranchEngramsByPrefix: this.db.prepare(`
        SELECT source_id AS engram_id, COUNT(*) AS out_degree
        FROM mnemic_synapses
        WHERE edge_type = ? AND source_id LIKE ? || '%'
        GROUP BY source_id
        HAVING COUNT(*) > 1
        ORDER BY source_id ASC
      `),

      insertSpike: this.db.prepare(`
        INSERT INTO activation_spikes (engram_id, timestamp, magnitude, task_context, outcome)
        VALUES (@engram_id, @timestamp, @magnitude, @task_context, @outcome)
      `),
      getSpikes: this.db.prepare(`
        SELECT * FROM activation_spikes WHERE engram_id = ? ORDER BY timestamp DESC LIMIT ?
      `),
      getSpikeCount: this.db.prepare(`
        SELECT COUNT(*) as count FROM activation_spikes WHERE engram_id = ?
      `),
      pruneSpikes: this.db.prepare(`
        DELETE FROM activation_spikes WHERE engram_id = ? AND id NOT IN (
          SELECT id FROM activation_spikes WHERE engram_id = ?
          ORDER BY timestamp DESC LIMIT ?
        )
      `),
      countSpikes: this.db.prepare(`SELECT COUNT(*) as count FROM activation_spikes`),

      insertNucleus: this.db.prepare(`
        INSERT INTO nuclei (id, label, centroid_x, centroid_y, member_count, avg_potentiation, abstraction_id, created_at, updated_at)
        VALUES (@id, @label, @centroid_x, @centroid_y, 0, 0, @abstraction_id, @created_at, @updated_at)
      `),
      getNucleus: this.db.prepare(`SELECT * FROM nuclei WHERE id = ?`),
      deleteNucleus: this.db.prepare(`DELETE FROM nuclei WHERE id = ?`),
      listNuclei: this.db.prepare(`SELECT * FROM nuclei ORDER BY avg_potentiation DESC`),
      countNuclei: this.db.prepare(`SELECT COUNT(*) as count FROM nuclei`),

      topByPotentiation: this.db.prepare(`
        SELECT id, content, potentiation FROM engrams ORDER BY potentiation DESC LIMIT ?
      `),

      searchFts: this.db.prepare(`
        SELECT e.* FROM engrams_fts fts
        JOIN engrams e ON e.rowid = fts.rowid
        WHERE engrams_fts MATCH ?
        ORDER BY rank LIMIT ?
      `),

      getTensionPairs: this.db.prepare(`
        SELECT s.*, ea.potentiation as pot_a, eb.potentiation as pot_b
        FROM mnemic_synapses s
        JOIN engrams ea ON ea.id = s.source_id
        JOIN engrams eb ON eb.id = s.target_id
        WHERE s.edge_type = 'contradicts'
        AND ea.potentiation > ? AND eb.potentiation > ?
        ORDER BY MIN(ea.potentiation, eb.potentiation) * s.weight DESC
        LIMIT ?
      `),

      findFileByPath: this.db.prepare(`
        SELECT * FROM engrams
        WHERE node_type = 'file' AND file_path = ?
        LIMIT 1
      `),

      findFileVersionsByPath: this.db.prepare(`
        SELECT * FROM engrams
        WHERE node_type = 'file_version'
          AND json_extract(metadata, '$.filePath') = ?
        ORDER BY t ASC
      `),

      pruneFileReads: this.db.prepare(`
        DELETE FROM engrams
        WHERE rowid IN (
          SELECT rowid FROM (
            SELECT e.rowid,
              ROW_NUMBER() OVER (
                PARTITION BY json_extract(e.metadata, '$.filePath')
                ORDER BY e.t DESC
              ) AS rn
            FROM engrams e
            WHERE e.node_type = 'file_read'
              AND e.created_at < ?
          )
          WHERE rn > ?
        )
      `),
    }
  }

  createEngram(input: EngramCreate): Engram {
    const now = new Date().toISOString()
    const id = input.id ?? randomUUID()
    const x = input.x ?? 0
    const y = input.y ?? 0
    const t = input.t ?? Date.now()
    const potentiation = input.initialPotentiation ?? 0

    this.stmts.insertEngram.run({
      id,
      content: input.content,
      node_type: input.nodeType,
      x, y, t,
      potentiation,
      embedding: compressEmbedding(input.embedding ?? null),
      tags: JSON.stringify(input.tags ?? []),
      provenance: input.provenance ?? '',
      created_at: input.createdAt ?? now,
      metadata: JSON.stringify(input.metadata ?? {}),
      file_path: (input.metadata as any)?.filePath ?? null,
      content_hash: (input.metadata as any)?.checksum ?? (input.metadata as any)?.currentChecksum ?? null,
    })

    const rowid = (this.db.prepare(`SELECT rowid FROM engrams WHERE id = ?`).get(id) as { rowid: number })?.rowid
    if (rowid != null) {
      this.stmts.insertRtree.run({ id: rowid, x, y, t, potentiation })
    }

    this.logger.debug('Engram created', { id, nodeType: input.nodeType })
    return this.getEngram(id)!
  }

  getEngram(id: string): Engram | null {
    const row = this.stmts.getEngram.get(id) as Record<string, unknown> | undefined
    return row ? rowToEngram(row) : null
  }

  /** Batch-fetch engrams by ID. Spread loop hot path — avoids N individual queries. */
  getEngrams(ids: string[]): Map<string, Engram> {
    if (ids.length === 0) return new Map()
    const placeholders = ids.map(() => '?').join(',')
    const rows = this.db.prepare(
      `SELECT * FROM engrams WHERE id IN (${placeholders})`
    ).all(...ids) as Record<string, unknown>[]
    const result = new Map<string, Engram>()
    for (const row of rows) {
      const e = rowToEngram(row)
      result.set(e.id, e)
    }
    return result
  }

  updateEngram(id: string, update: EngramUpdate): Engram | null {
    const existing = this.getEngram(id)
    if (!existing) return null

    const setClauses: string[] = []
    const params: Record<string, unknown> = { id }

    if (update.content !== undefined) { setClauses.push('content = @content'); params.content = update.content }
    if (update.nodeType !== undefined) { setClauses.push('node_type = @node_type'); params.node_type = update.nodeType }
    if (update.x !== undefined) { setClauses.push('x = @x'); params.x = update.x }
    if (update.y !== undefined) { setClauses.push('y = @y'); params.y = update.y }
    if (update.t !== undefined) { setClauses.push('t = @t'); params.t = update.t }
    if (update.potentiation !== undefined) { setClauses.push('potentiation = @potentiation'); params.potentiation = update.potentiation }
    if (update.clusterId !== undefined) { setClauses.push('cluster_id = @cluster_id'); params.cluster_id = update.clusterId }
    if (update.embedding !== undefined) { setClauses.push('embedding = @embedding'); params.embedding = compressEmbedding(update.embedding) }
    if (update.tags !== undefined) { setClauses.push('tags = @tags'); params.tags = JSON.stringify(update.tags) }
    if (update.accessedAt !== undefined) { setClauses.push('accessed_at = @accessed_at'); params.accessed_at = update.accessedAt }
    if (update.metadata !== undefined) { setClauses.push('metadata = @metadata'); params.metadata = JSON.stringify(update.metadata) }

    if (setClauses.length === 0) return existing

    this.db.prepare(`UPDATE engrams SET ${setClauses.join(', ')} WHERE id = @id`).run(params)

    if (update.x !== undefined || update.y !== undefined || update.t !== undefined || update.potentiation !== undefined) {
      const updated = this.getEngram(id)!
      const rowid = (this.db.prepare(`SELECT rowid FROM engrams WHERE id = ?`).get(id) as { rowid: number })?.rowid
      if (rowid != null) {
        this.stmts.updateRtree.run({ id: rowid, x: updated.x, y: updated.y, t: updated.t, p: updated.potentiation })
      }
    }

    return this.getEngram(id)
  }

  deleteEngram(id: string): boolean {
    const rowid = (this.db.prepare(`SELECT rowid FROM engrams WHERE id = ?`).get(id) as { rowid: number })?.rowid
    if (rowid != null) {
      this.stmts.deleteRtree.run(rowid)
    }
    const result = this.stmts.deleteEngram.run(id)
    return result.changes > 0
  }

  setEngramSessionId(id: string, sessionId: string): void {
    this.db.prepare(`UPDATE engrams SET session_id = ? WHERE id = ?`).run(sessionId, id)
  }

  listEngrams(limit = 100, nodeType?: string): Engram[] {
    const rows = nodeType
      ? this.stmts.listEngramsByType.all(nodeType, limit) as Record<string, unknown>[]
      : this.stmts.listEngrams.all(limit) as Record<string, unknown>[]
    return rows.map(rowToEngram)
  }

  createSynapse(input: SynapseCreate): MnemicSynapse {
    const now = new Date().toISOString()
    this.stmts.insertSynapse.run({
      source_id: input.sourceId,
      target_id: input.targetId,
      edge_type: input.edgeType,
      weight: input.weight ?? 1.0,
      created_at: now,
      metadata: JSON.stringify(input.metadata ?? {}),
    })
    this.logger.debug('Synapse created', { source: input.sourceId, target: input.targetId, type: input.edgeType })
    return this.getSynapse(input.sourceId, input.targetId, input.edgeType)!
  }

  getSynapse(sourceId: string, targetId: string, edgeType: string): MnemicSynapse | null {
    const row = this.stmts.getSynapse.get(sourceId, targetId, edgeType) as Record<string, unknown> | undefined
    return row ? rowToSynapse(row) : null
  }

  deleteSynapse(sourceId: string, targetId: string, edgeType: string): boolean {
    const result = this.stmts.deleteSynapse.run(sourceId, targetId, edgeType)
    return result.changes > 0
  }

  getNeighborSynapses(engramId: string, direction: 'outgoing' | 'incoming' | 'all' = 'all'): MnemicSynapse[] {
    let rows: Record<string, unknown>[]
    if (direction === 'outgoing') rows = this.stmts.getOutgoingSynapses.all(engramId) as Record<string, unknown>[]
    else if (direction === 'incoming') rows = this.stmts.getIncomingSynapses.all(engramId) as Record<string, unknown>[]
    else rows = this.stmts.getAllSynapses.all(engramId, engramId) as Record<string, unknown>[]
    return rows.map(rowToSynapse)
  }

  getNeighborEngrams(engramId: string): Engram[] {
    const synapses = this.getNeighborSynapses(engramId)
    const neighborIds = new Set<string>()
    for (const s of synapses) {
      if (s.sourceId !== engramId) neighborIds.add(s.sourceId)
      if (s.targetId !== engramId) neighborIds.add(s.targetId)
    }
    const result: Engram[] = []
    for (const nid of neighborIds) {
      const e = this.getEngram(nid)
      if (e) result.push(e)
    }
    return result
  }

  recordSpike(input: SpikeCreate): ActivationSpike {
    const ts = Date.now()
    this.stmts.insertSpike.run({
      engram_id: input.engramId,
      timestamp: ts,
      magnitude: input.magnitude,
      task_context: input.taskContext ?? null,
      outcome: input.outcome ?? null,
    })

    this.updateEngram(input.engramId, { accessedAt: new Date().toISOString(), t: ts })

    const lastId = (this.db.prepare(`SELECT last_insert_rowid() as id`).get() as { id: number }).id
    return {
      id: lastId,
      engramId: input.engramId,
      timestamp: ts,
      magnitude: input.magnitude,
      taskContext: input.taskContext ?? null,
      outcome: input.outcome ?? null,
    }
  }

  getSpikes(engramId: string, limit = 50): ActivationSpike[] {
    const rows = this.stmts.getSpikes.all(engramId, limit) as Record<string, unknown>[]
    return rows.map(rowToSpike)
  }

  getSpikeCount(engramId: string): number {
    return (this.stmts.getSpikeCount.get(engramId) as { count: number }).count
  }

  /**
   * Batch fetch spikes for many engrams in a single query.
   * Returns a Map keyed by engram_id with arrays of {timestamp, magnitude, taskContext}.
   */
  getAllSpikesForEngrams(ids: string[], limit: number): Map<string, Array<{ timestamp: number; magnitude: number; taskContext: string | null }>> {
    const result = new Map<string, Array<{ timestamp: number; magnitude: number; taskContext: string | null }>>()
    if (ids.length === 0) return result
    // Batch to avoid exceeding SQLite's variable limit (~32K)
    const BATCH = 500
    for (let i = 0; i < ids.length; i += BATCH) {
      const batch = ids.slice(i, i + BATCH)
      const placeholders = batch.map(() => '?').join(',')
      const rows = this.db.prepare(
        `SELECT engram_id, timestamp, magnitude, task_context FROM (
           SELECT engram_id, timestamp, magnitude, task_context,
                  ROW_NUMBER() OVER (PARTITION BY engram_id ORDER BY timestamp DESC) AS rn
           FROM activation_spikes WHERE engram_id IN (${placeholders})
         ) WHERE rn <= ?`
      ).all(...batch, limit) as Array<{ engram_id: string; timestamp: number; magnitude: number; task_context: string | null }>
      for (const row of rows) {
        const list = result.get(row.engram_id)
        const entry = { timestamp: row.timestamp, magnitude: row.magnitude, taskContext: row.task_context ?? null }
        if (list) {
          list.push(entry)
        } else {
          result.set(row.engram_id, [entry])
        }
      }
    }
    return result
  }

  /**
   * Batch fetch spike counts for many engrams in a single query.
   * Returns a Map keyed by engram_id with the spike count.
   */
  getAllSpikeCountsForEngrams(ids: string[]): Map<string, number> {
    const result = new Map<string, number>()
    if (ids.length === 0) return result
    const BATCH = 500
    for (let i = 0; i < ids.length; i += BATCH) {
      const batch = ids.slice(i, i + BATCH)
      const placeholders = batch.map(() => '?').join(',')
      const rows = this.db.prepare(
        `SELECT engram_id, COUNT(*) as count FROM activation_spikes WHERE engram_id IN (${placeholders}) GROUP BY engram_id`
      ).all(...batch) as Array<{ engram_id: string; count: number }>
      for (const row of rows) {
        result.set(row.engram_id, row.count)
      }
    }
    return result
  }

  /**
   * Batch fetch spike outcome counts for many engrams in a single query.
   * Returns a Map keyed by engram_id with success/failure/unknown counts.
   * Used by contrastive retrieval feedback to compute utility scores.
   */
  getAllSpikeOutcomesForEngrams(ids: string[]): Map<string, { success: number; failure: number; unknown: number }> {
    const result = new Map<string, { success: number; failure: number; unknown: number }>()
    if (ids.length === 0) return result
    const BATCH = 500
    for (let i = 0; i < ids.length; i += BATCH) {
      const batch = ids.slice(i, i + BATCH)
      const placeholders = batch.map(() => '?').join(',')
      const rows = this.db.prepare(
        `SELECT engram_id, outcome, COUNT(*) as count
         FROM activation_spikes
         WHERE engram_id IN (${placeholders}) AND outcome IS NOT NULL
         GROUP BY engram_id, outcome`
      ).all(...batch) as Array<{ engram_id: string; outcome: string; count: number }>
      for (const row of rows) {
        let entry = result.get(row.engram_id)
        if (!entry) {
          entry = { success: 0, failure: 0, unknown: 0 }
          result.set(row.engram_id, entry)
        }
        const oc = (row.outcome ?? 'unknown') as 'success' | 'failure' | 'unknown'
        if (oc === 'success' || oc === 'failure' || oc === 'unknown') {
          entry[oc] = row.count
        }
      }
    }
    return result
  }
  pruneSpikes(engramId: string, keepCount = 100): number {
    const result = this.stmts.pruneSpikes.run(engramId, engramId, keepCount)
    return result.changes
  }

  createNucleus(input: NucleusCreate): Nucleus {
    const now = new Date().toISOString()
    const id = input.id ?? randomUUID()
    this.stmts.insertNucleus.run({
      id,
      label: input.label,
      centroid_x: input.centroidX,
      centroid_y: input.centroidY,
      abstraction_id: input.abstractionId ?? null,
      created_at: now,
      updated_at: now,
    })
    this.logger.debug('Nucleus created', { id, label: input.label })
    return this.getNucleus(id)!
  }

  getNucleus(id: string): Nucleus | null {
    const row = this.stmts.getNucleus.get(id) as Record<string, unknown> | undefined
    return row ? rowToNucleus(row) : null
  }

  updateNucleus(id: string, update: Partial<Omit<Nucleus, 'id' | 'createdAt'>>): Nucleus | null {
    const existing = this.getNucleus(id)
    if (!existing) return null

    const setClauses: string[] = []
    const params: Record<string, unknown> = { id }

    if (update.label !== undefined) { setClauses.push('label = @label'); params.label = update.label }
    if (update.centroidX !== undefined) { setClauses.push('centroid_x = @cx'); params.cx = update.centroidX }
    if (update.centroidY !== undefined) { setClauses.push('centroid_y = @cy'); params.cy = update.centroidY }
    if (update.memberCount !== undefined) { setClauses.push('member_count = @mc'); params.mc = update.memberCount }
    if (update.avgPotentiation !== undefined) { setClauses.push('avg_potentiation = @ap'); params.ap = update.avgPotentiation }
    if (update.abstractionId !== undefined) { setClauses.push('abstraction_id = @aid'); params.aid = update.abstractionId }
    setClauses.push('updated_at = @updated_at'); params.updated_at = new Date().toISOString()

    if (setClauses.length <= 1) return existing

    this.db.prepare(`UPDATE nuclei SET ${setClauses.join(', ')} WHERE id = @id`).run(params)
    return this.getNucleus(id)
  }

  deleteNucleus(id: string): boolean {
    this.db.prepare(`UPDATE engrams SET cluster_id = NULL WHERE cluster_id = ?`).run(id)
    const result = this.stmts.deleteNucleus.run(id)
    return result.changes > 0
  }

  listNuclei(): Nucleus[] {
    const rows = this.stmts.listNuclei.all() as Record<string, unknown>[]
    return rows.map(rowToNucleus)
  }

  spatialQuery(query: SpatialQuery): Engram[] {
    const conditions: string[] = []
    const params: Record<string, number> = {}

    if (query.xMin !== undefined) { conditions.push('x_min >= @xMin'); params.xMin = query.xMin }
    if (query.xMax !== undefined) { conditions.push('x_max <= @xMax'); params.xMax = query.xMax }
    if (query.yMin !== undefined) { conditions.push('y_min >= @yMin'); params.yMin = query.yMin }
    if (query.yMax !== undefined) { conditions.push('y_max <= @yMax'); params.yMax = query.yMax }
    if (query.tMin !== undefined) { conditions.push('t_min >= @tMin'); params.tMin = query.tMin }
    if (query.tMax !== undefined) { conditions.push('t_max <= @tMax'); params.tMax = query.tMax }
    if (query.potentiationMin !== undefined) { conditions.push('potentiation_min >= @pMin'); params.pMin = query.potentiationMin }
    if (query.potentiationMax !== undefined) { conditions.push('potentiation_max <= @pMax'); params.pMax = query.potentiationMax }

    if (conditions.length === 0) return this.listEngrams(query.limit ?? 100)

    const limit = query.limit ?? 100
    const sql = `
      SELECT e.* FROM engram_rtree r
      JOIN engrams e ON e.rowid = r.id
      WHERE ${conditions.join(' AND ')}
      LIMIT ${limit}
    `
    const rows = this.db.prepare(sql).all(params) as Record<string, unknown>[]
    return rows.map(rowToEngram)
  }

  searchText(query: string, limit = 20): EngramSearchResult[] {
    try {
      const rows = this.stmts.searchFts.all(query, limit) as Record<string, unknown>[]
      return rows.map((row, i) => ({
        engram: rowToEngram(row),
        score: 1.0 - (i / limit),
      }))
    } catch (err) {
      this.logger.debug('FTS5 search failed, likely syntax issue', { query, error: String(err) })
      return []
    }
  }

  getTensionPairs(minPotentiation = 0.3, limit = 10): TensionPair[] {
    const rows = this.stmts.getTensionPairs.all(minPotentiation, minPotentiation, limit) as Record<string, unknown>[]
    return rows.map(row => {
      const engramA = this.getEngram(row.source_id as string)!
      const engramB = this.getEngram(row.target_id as string)!
      const synapse = rowToSynapse(row)
      const tension = Math.min(engramA.potentiation, engramB.potentiation) * synapse.weight
      return { engramA, engramB, synapse, tension }
    })
  }

  /**
   * Find a file engram by its filePath.
   * Uses json_extract(metadata, '$.filePath') — fast enough for the
   * hot path because the engrams table is indexed by node_type and
   * json_extract is optimized in recent SQLite versions.
   */
  findFileByPath(filePath: string): Engram | null {
    const row = this.stmts.findFileByPath.get(filePath) as Record<string, unknown> | undefined
    return row ? rowToEngram(row) : null
  }

  /**
   * Find all file_version engrams for a given filePath.
   * Returns all versions sorted by t (creation order) so the caller can
   * pick v1 (first), vN-1 (penultimate), etc. in a single DB round-trip.
   */
  findFileVersionsByPath(filePath: string): Engram[] {
    const rows = this.stmts.findFileVersionsByPath.all(filePath) as Record<string, unknown>[]
    return rows.map(rowToEngram)
  }

  /**
   * Prune stale file_read engrams older than a given threshold.
   * Keeps at most `keepPerPath` latest file_read engrams per file path.
   * Returns the number of deleted engrams.
   *
   * Safe to call periodically (every few hours) — uses a single DELETE
   * with a subquery to identify candidates.
   */
  pruneFileReads(olderThanMs: number, keepPerPath = 3): number {
    const olderThanIso = new Date(Date.now() - olderThanMs).toISOString()
    const result = this.stmts.pruneFileReads.run(olderThanIso, keepPerPath)
    return result.changes
  }

  bulkUpdatePotentiation(updates: Array<{ id: string; potentiation: number }>): void {
    const updateStmt = this.db.prepare(`UPDATE engrams SET potentiation = ? WHERE id = ?`)
    const updateRtreeStmt = this.db.prepare(`
      UPDATE engram_rtree SET potentiation_min = @p, potentiation_max = @p
      WHERE id = (SELECT rowid FROM engrams WHERE id = @id)
    `)

    const tx = this.db.transaction((items: typeof updates) => {
      for (const { id, potentiation } of items) {
        updateStmt.run(potentiation, id)
        updateRtreeStmt.run({ p: potentiation, id })
      }
    })
    tx(updates)
    this.logger.debug('Bulk potentiation update', { count: updates.length })
  }

  /**
   * Batched version that yields to the event loop between batches.
   * Prevents long SQLite transactions from blocking heartbeats and IPC
   * when updating thousands of rows.
   */
  async bulkUpdatePotentiationBatched(
    updates: Array<{ id: string; potentiation: number }>,
    batchSize = 1000,
  ): Promise<void> {
    for (let i = 0; i < updates.length; i += batchSize) {
      this.bulkUpdatePotentiation(updates.slice(i, i + batchSize))
      if (i + batchSize < updates.length) {
        await new Promise<void>(resolve => setImmediate(resolve))
      }
    }
  }

  bulkUpdatePositions(updates: Array<{ id: string; x: number; y: number }>): void {
    const updateStmt = this.db.prepare(`UPDATE engrams SET x = ?, y = ? WHERE id = ?`)
    const updateRtreeStmt = this.db.prepare(`
      UPDATE engram_rtree SET x_min = @x, x_max = @x, y_min = @y, y_max = @y
      WHERE id = (SELECT rowid FROM engrams WHERE id = @id)
    `)

    const tx = this.db.transaction((items: typeof updates) => {
      for (const { id, x, y } of items) {
        updateStmt.run(x, y, id)
        updateRtreeStmt.run({ x, y, id })
      }
    })
    tx(updates)
    this.logger.debug('Bulk position update', { count: updates.length })
  }

  /**
   * Batched version that yields between batches.
   */
  async bulkUpdatePositionsBatched(
    updates: Array<{ id: string; x: number; y: number }>,
    batchSize = 1000,
  ): Promise<void> {
    for (let i = 0; i < updates.length; i += batchSize) {
      this.bulkUpdatePositions(updates.slice(i, i + batchSize))
      if (i + batchSize < updates.length) {
        await new Promise<void>(resolve => setImmediate(resolve))
      }
    }
  }

  bulkUpdateEmbeddings(updates: Array<{ id: string; embedding: Float32Array }>): void {
    const updateStmt = this.db.prepare(`UPDATE engrams SET embedding = ? WHERE id = ?`)

    const tx = this.db.transaction((items: typeof updates) => {
      for (const { id, embedding } of items) {
        updateStmt.run(compressEmbedding(embedding), id)
      }
    })
    tx(updates)
    this.logger.debug('Bulk embedding update', { count: updates.length })
  }

  getAllEngrams(): Engram[] {
    return (this.db.prepare(`SELECT * FROM engrams`).all() as Record<string, unknown>[]).map(rowToEngram)
  }

  /**
   * Lean bulk query for CassiPrism — returns only position/type data.
   * Avoids loading content, embedding, and metadata BLOBs.
   * At 150K engrams this is ~900KB JSON vs ~150MB for getAllEngrams().
   */
  getPositions(limit?: number): EngramPosition[] {
    const l = limit ?? 999999
    const rows = this.db.prepare(
      `SELECT id, x, y, t, potentiation, node_type, cluster_id FROM engrams ORDER BY t ASC LIMIT ?`
    ).all(l) as Array<{ id: string; x: number; y: number; t: number; potentiation: number; node_type: string; cluster_id: string | null }>
    return rows.map(r => ({
      id: r.id,
      x: r.x,
      y: r.y,
      t: r.t,
      potentiation: r.potentiation,
      nodeType: r.node_type as EngramType,
      clusterId: r.cluster_id,
    }))
  }

  /**
   * Return only (id, embedding) pairs — avoids loading content/metadata blobs.
   * Critical for large fields where getAllEngrams() would OOM from blob pressure.
   */
  getEmbeddingVectors(maxCount?: number): Array<{ id: string; embedding: Float32Array }> {
    const limit = maxCount ?? 999999
    const rows = this.db.prepare(
      `SELECT id, embedding FROM engrams WHERE embedding IS NOT NULL AND LENGTH(embedding) > 0 LIMIT ?`
    ).all(limit) as Array<{ id: string; embedding: Buffer }>
    return rows
      .map(r => ({ id: r.id, embedding: toFloatArray(r.embedding)! }))
      .filter(r => r.embedding !== null) as Array<{ id: string; embedding: Float32Array }>
  }

  /**
   * Return (id, content) for engrams missing embeddings — no embedding blobs loaded.
   */
  getEngramsWithoutEmbedding(limit: number): Array<{ id: string; content: string }> {
    return this.db.prepare(
      `SELECT id, content FROM engrams
       WHERE embedding IS NULL
       AND LENGTH(content) > 10
       AND LENGTH(content) < 100000
       ORDER BY LENGTH(content) DESC
       LIMIT ?`
    ).all(limit) as Array<{ id: string; content: string }>
  }

  /**
   * Return conversation engrams missing semanticType classification.
   * Filters to engrams with conversation-relevant provenance (thalamus, hermes)
   * and short text content (not code blobs). Maximizes embedding ROI.
   */
  getUnclassifiedConversationEngrams(limit = 500): Engram[] {
    const all = this.db.prepare(
      `SELECT * FROM engrams
       WHERE (provenance LIKE 'thalamus%' OR provenance LIKE 'hermes%'
              OR provenance LIKE 'conversation%' OR provenance LIKE 'turn-pipeline%'
              OR provenance LIKE 'dialectic%' OR provenance LIKE 'memory:%'
              OR provenance LIKE 'system:%')
       AND metadata NOT LIKE '%"semanticType"%'
       AND LENGTH(content) BETWEEN 10 AND 2000
       ORDER BY t DESC
       LIMIT ?`
    ).all(limit) as Record<string, unknown>[]
    return all.map(rowToEngram)
  }

  /**
   * Count engrams missing embeddings without loading them into memory.
   */
  countMissingEmbeddings(): number {
    return (this.db.prepare(
      `SELECT COUNT(*) as c FROM engrams WHERE embedding IS NULL AND LENGTH(content) > 10 AND LENGTH(content) < 100000`
    ).get() as { c: number }).c
  }

  /**
   * Return (id, embedding, x, y) — for rebuilding projection state without full engram load.
   */
  getEmbeddingVectorsWithPositions(maxCount?: number): Array<{ id: string; embedding: Float32Array; x: number; y: number }> {
    const limit = maxCount ?? 999999
    const rows = this.db.prepare(
      `SELECT id, embedding, x, y FROM engrams WHERE embedding IS NOT NULL AND LENGTH(embedding) > 0 LIMIT ?`
    ).all(limit) as Array<{ id: string; embedding: Buffer; x: number; y: number }>
    return rows
      .map(r => {
        const emb = toFloatArray(r.embedding)
        return emb ? { id: r.id, embedding: emb, x: r.x, y: r.y } : null
      })
      .filter(Boolean) as Array<{ id: string; embedding: Float32Array; x: number; y: number }>
  }

  /**
   * Count engrams that have embeddings.
   */
  countEmbeddings(): number {
    return (this.db.prepare(
      `SELECT COUNT(*) as c FROM engrams WHERE embedding IS NOT NULL AND LENGTH(embedding) > 0`
    ).get() as { c: number }).c
  }

  /**
   * Count engrams that have valid (non-origin) positions.
   * Used to determine if projection state can be restored from DB.
   */
  countValidPositions(): number {
    return (this.db.prepare(
      `SELECT COUNT(*) as c FROM engrams WHERE embedding IS NOT NULL AND LENGTH(embedding) > 0 AND (x != 0 OR y != 0)`
    ).get() as { c: number }).c
  }

  /**
   * Get embedding dimension from the first available embedding.
   */
  getEmbeddingDim(): number {
    const row = this.db.prepare(
      `SELECT embedding FROM engrams WHERE embedding IS NOT NULL AND LENGTH(embedding) > 0 LIMIT 1`
    ).get() as { embedding: Buffer } | undefined
    if (!row) return 0
    const buf = row.embedding
    if (isPolarQuantBlob(buf)) {
      // PolarQuant blobs store dim in the header at offset 6 (uint16 LE)
      return buf.readUInt16LE(6)
    }
    return buf.length / 4
  }

  /**
   * Pack all embeddings directly into a SharedArrayBuffer for worker thread
   * transfer. Returns the SAB, the array of IDs, and the embedding dimension.
   * Uses an iterator-based approach to avoid loading all rows into memory at once.
   */
  packEmbeddingsIntoSAB(maxCount?: number): {
    buffer: SharedArrayBuffer
    ids: string[]
    dim: number
    count: number
  } {
    const limit = maxCount ?? 999999
    const dim = this.getEmbeddingDim()
    if (dim === 0) return { buffer: new SharedArrayBuffer(0), ids: [], dim: 0, count: 0 }

    const count = Math.min(this.countEmbeddings(), limit)
    // Use Float32 to match the DB storage format and halve memory usage
    const sab = new SharedArrayBuffer(count * dim * Float32Array.BYTES_PER_ELEMENT)
    const packed = new Float32Array(sab)
    const ids: string[] = []

    const stmt = this.db.prepare(
      `SELECT id, embedding FROM engrams WHERE embedding IS NOT NULL AND LENGTH(embedding) > 0 LIMIT ?`
    )

    let idx = 0
    for (const row of stmt.iterate(limit) as Iterable<{ id: string; embedding: Buffer }>) {
      const f32 = toFloatArray(row.embedding)
      if (!f32 || f32.length !== dim) continue

      const offset = idx * dim
      packed.set(f32, offset)
      ids.push(row.id)
      idx++
    }

    return { buffer: sab, ids, dim, count: idx }
  }

  getSpatialEngrams(maxCount = 10000): Engram[] {
    return (this.db.prepare(
      `SELECT * FROM engrams WHERE x != 0 OR y != 0 OR (embedding IS NOT NULL AND length(embedding) > 0)
       ORDER BY potentiation DESC LIMIT ?`
    ).all(maxCount) as Record<string, unknown>[]).map(rowToEngram)
  }

  getEngramsByCluster(clusterId: string): Engram[] {
    const rows = this.db.prepare(
      `SELECT * FROM engrams WHERE cluster_id = ? ORDER BY potentiation DESC`
    ).all(clusterId) as Record<string, unknown>[]
    return rows.map(rowToEngram)
  }

  getEngramsByIdPrefix(
    prefix: string,
    opts: { limit?: number; offset?: number; order?: 'asc' | 'desc' } = {},
  ): Engram[] {
    const limit = opts.limit ?? 1000
    const offset = opts.offset ?? 0
    const stmt = (opts.order ?? 'asc') === 'asc'
      ? this.stmts.getEngramsByIdPrefixAsc
      : this.stmts.getEngramsByIdPrefixDesc
    const rows = stmt.all(prefix, limit, offset) as Record<string, unknown>[]
    return rows.map(rowToEngram)
  }

  getEngramsBySessionId(sessionId: string, limit = 1000, offset = 0): Engram[] {
    if (offset > 0) {
      const rows = this.stmts.getEngramsBySessionIdOffset.all(sessionId, limit, offset) as Record<string, unknown>[]
      return rows.map(rowToEngram)
    }
    const rows = this.stmts.getEngramsBySessionId.all(sessionId, limit) as Record<string, unknown>[]
    return rows.map(rowToEngram)
  }

  getTypedSynapses(engramId: string, edgeType: string, direction: 'in' | 'out'): MnemicSynapse[] {
    const stmt = direction === 'out' ? this.stmts.getOutgoingTypedSynapses : this.stmts.getIncomingTypedSynapses
    const rows = stmt.all(engramId, edgeType) as Record<string, unknown>[]
    return rows.map(rowToSynapse)
  }

  findBranchEngrams(idPrefix: string, edgeType: string = 'temporal_neighbor'): Array<{ engramId: string; outDegree: number }> {
    const rows = this.stmts.findBranchEngramsByPrefix.all(edgeType, idPrefix) as Array<{ engram_id: string; out_degree: number }>
    return rows.map(r => ({ engramId: r.engram_id, outDegree: r.out_degree }))
  }

  getAllEngramsWithSynapses(): { engrams: Engram[]; synapses: MnemicSynapse[] } {
    const engrams = this.getAllEngrams()
    const synapses = (this.db.prepare(`SELECT * FROM mnemic_synapses`).all() as Record<string, unknown>[]).map(rowToSynapse)
    return { engrams, synapses }
  }

  stats(): FieldStats {
    const engramCount = (this.stmts.countEngrams.get() as { count: number }).count
    const synapseCount = (this.stmts.countSynapses.get() as { count: number }).count
    const spikeCount = (this.stmts.countSpikes.get() as { count: number }).count
    const nucleusCount = (this.stmts.countNuclei.get() as { count: number }).count
    const avgRow = this.db.prepare(`SELECT AVG(potentiation) as avg FROM engrams`).get() as { avg: number | null }
    const topRows = this.stmts.topByPotentiation.all(5) as Array<{ id: string; content: string; potentiation: number }>

    return {
      engramCount,
      synapseCount,
      spikeCount,
      nucleusCount,
      avgPotentiation: avgRow.avg ?? 0,
      topEngramsByPotentiation: topRows,
    }
  }

  getDatabase(): Database.Database {
    return this.db
  }


  /**
   * Migrate bridge engrams from nodeType 'pattern' to 'bridge'.
   * Returns the number of engrams updated.
   */
  migrateBridgeNodeTypes(): number {
    const result = this.db.prepare(
      `UPDATE engrams SET node_type = 'bridge' WHERE node_type = 'pattern' AND tags LIKE '%bridge%'`
    ).run()
    return result.changes
  }

  /**
   * Sample random orphan engrams (those not assigned to any nucleus).
   * Content is truncated to keep results lightweight for batch analysis.
   */
  sampleOrphans(limit = 20): Array<{ id: string; content: string; nodeType: string; potentiation: number; tags: string; provenance: string }> {
    return (this.db.prepare(
      `SELECT id, SUBSTR(content, 1, 200) as content, node_type as nodeType, potentiation, tags, provenance
       FROM engrams WHERE cluster_id IS NULL ORDER BY RANDOM() LIMIT ?`
    ).all(limit) as Array<{ id: string; content: string; nodeType: string; potentiation: number; tags: string; provenance: string }>)
  }

  /**
   * Count orphan engrams (not assigned to any nucleus).
   */
  orphanCount(): number {
    return (this.db.prepare(`SELECT COUNT(*) as c FROM engrams WHERE cluster_id IS NULL`).get() as { c: number }).c
  }

  /**
   * Distribution of orphan engrams by node_type and provenance.
   * Gives a structural overview of the unorganized memory space.
   */
  orphanDistribution(): {
    byNodeType: Array<{ nodeType: string; count: number }>
    byProvenance: Array<{ provenance: string; count: number }>
    total: number
  } {
    const byNodeType = this.db.prepare(
      `SELECT node_type as nodeType, COUNT(*) as count FROM engrams
       WHERE cluster_id IS NULL GROUP BY node_type ORDER BY count DESC`
    ).all() as Array<{ nodeType: string; count: number }>

    const byProvenance = this.db.prepare(
      `SELECT COALESCE(provenance, 'unknown') as provenance, COUNT(*) as count FROM engrams
       WHERE cluster_id IS NULL GROUP BY provenance ORDER BY count DESC LIMIT 20`
    ).all() as Array<{ provenance: string; count: number }>

    const total = this.orphanCount()
    return { byNodeType, byProvenance, total }
  }

  /**
   * Assign a batch of engrams to a nucleus.
   * Updates both the engram's cluster_id and the nucleus member count.
   */
  assignToNucleus(engramIds: string[], nucleusId: string): number {
    if (engramIds.length === 0) return 0

    const placeholders = engramIds.map(() => '?').join(',')
    const result = this.db.prepare(
      `UPDATE engrams SET cluster_id = ? WHERE id IN (${placeholders})`
    ).run(nucleusId, ...engramIds)

    const count = (this.db.prepare(
      `SELECT COUNT(*) as c FROM engrams WHERE cluster_id = ?`
    ).get(nucleusId) as { c: number }).c
    this.db.prepare(
      `UPDATE nuclei SET member_count = ? WHERE id = ?`
    ).run(count, nucleusId)

    return result.changes
  }

  /**
   * Tag frequency distribution across orphan engrams.
   * Parses the JSON tag arrays and aggregates counts to show
   * which topics dominate the unorganized memory.
   */
  orphanTagDistribution(limit = 30): Array<{ tag: string; count: number }> {
    const rows = this.db.prepare(
      `SELECT tags FROM engrams WHERE cluster_id IS NULL AND tags IS NOT NULL AND tags != '[]'`
    ).all() as Array<{ tags: string }>

    const tagCounts = new Map<string, number>()
    for (const row of rows) {
      try {
        const tags = JSON.parse(row.tags) as string[]
        for (const tag of tags) {
          tagCounts.set(tag, (tagCounts.get(tag) ?? 0) + 1)
        }
      } catch { /* skip malformed tag arrays */ }
    }

    return [...tagCounts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, limit)
      .map(([tag, count]) => ({ tag, count }))
  }


  storeForwardTrace(trace: ForwardTrace): void {
    this.db.prepare(`
      INSERT INTO forward_traces (id, created_at, seed_charges, records, output_charges, spark_point, luminal_ids)
      VALUES (@id, @created_at, @seed_charges, @records, @output_charges, @spark_point, @luminal_ids)
    `).run({
      id: trace.id,
      created_at: trace.createdAt,
      seed_charges: JSON.stringify(trace.seedCharges),
      records: JSON.stringify(trace.records),
      output_charges: JSON.stringify(trace.outputCharges),
      spark_point: trace.sparkPoint,
      luminal_ids: JSON.stringify(trace.luminalIds),
    })
    this.maybeAutoPruneTraces()
  }

  private maybeAutoPruneTraces(): void {
    this.traceWriteCount++
    if (this.traceWriteCount < FORWARD_TRACE_AUTO_PRUNE_INTERVAL) return
    this.traceWriteCount = 0
    try {
      const byAge = this.pruneOldTraces(FORWARD_TRACE_AUTO_MAX_AGE_MS)
      const byCap = this.enforceTraceRowCap(FORWARD_TRACE_AUTO_MAX_ROWS)
      if (byAge + byCap > 0) {
        this.logger.debug?.('forward_traces auto-pruned', { byAge, byCap })
      }
    } catch (err) {
      this.logger.warn?.('forward_traces auto-prune failed', { error: String(err) })
    }
  }

  enforceTraceRowCap(maxRows: number): number {
    const result = this.db.prepare(
      `DELETE FROM forward_traces WHERE id IN (
         SELECT id FROM forward_traces ORDER BY created_at DESC LIMIT -1 OFFSET ?
       )`
    ).run(maxRows)
    return result.changes
  }

  getForwardTrace(id: string): ForwardTrace | null {
    const row = this.db.prepare(`SELECT * FROM forward_traces WHERE id = ?`).get(id) as Record<string, unknown> | undefined
    if (!row) return null
    return {
      id: row.id as string,
      createdAt: row.created_at as number,
      seedCharges: JSON.parse(row.seed_charges as string),
      records: JSON.parse(row.records as string),
      outputCharges: JSON.parse(row.output_charges as string),
      sparkPoint: row.spark_point as number,
      luminalIds: JSON.parse(row.luminal_ids as string),
    }
  }

  storeGradientRequest(traceId: string, feedback: Record<string, boolean>): void {
    this.db.prepare(`
      INSERT INTO gradient_requests (trace_id, feedback, created_at)
      VALUES (@trace_id, @feedback, @created_at)
    `).run({
      trace_id: traceId,
      feedback: JSON.stringify(feedback),
      created_at: Date.now(),
    })
  }

  getPendingGradientRequests(limit = 100): Array<{ id: number; traceId: string; feedback: Record<string, boolean> }> {
    const rows = this.db.prepare(`
      SELECT id, trace_id, feedback FROM gradient_requests
      WHERE processed = 0 ORDER BY created_at ASC LIMIT ?
    `).all(limit) as Array<Record<string, unknown>>
    return rows.map(row => ({
      id: row.id as number,
      traceId: row.trace_id as string,
      feedback: JSON.parse(row.feedback as string),
    }))
  }

  markGradientRequestsProcessed(ids: number[]): void {
    if (ids.length === 0) return
    const placeholders = ids.map(() => '?').join(',')
    this.db.prepare(`UPDATE gradient_requests SET processed = 1 WHERE id IN (${placeholders})`).run(...ids)
  }

  pruneOldTraces(maxAgeMs: number): number {
    const cutoff = Date.now() - maxAgeMs
    const result = this.db.prepare(`DELETE FROM forward_traces WHERE created_at < ?`).run(cutoff)
    return result.changes
  }

  forwardTraceCount(): number {
    return (this.db.prepare(`SELECT COUNT(*) as c FROM forward_traces`).get() as { c: number }).c
  }

  pendingGradientCount(): number {
    return (this.db.prepare(`SELECT COUNT(*) as c FROM gradient_requests WHERE processed = 0`).get() as { c: number }).c
  }


  getOptimizerState(sourceId: string, targetId: string, edgeType: string): { m: number; v: number; step: number } | null {
    const row = this.db.prepare(
      `SELECT m, v, step FROM synapse_optimizer_state WHERE source_id = ? AND target_id = ? AND edge_type = ?`
    ).get(sourceId, targetId, edgeType) as { m: number; v: number; step: number } | undefined
    return row ?? null
  }

  upsertOptimizerState(sourceId: string, targetId: string, edgeType: string, m: number, v: number, step: number): void {
    this.db.prepare(`
      INSERT INTO synapse_optimizer_state (source_id, target_id, edge_type, m, v, step)
      VALUES (@source_id, @target_id, @edge_type, @m, @v, @step)
      ON CONFLICT(source_id, target_id, edge_type)
      DO UPDATE SET m = @m, v = @v, step = @step
    `).run({
      source_id: sourceId,
      target_id: targetId,
      edge_type: edgeType,
      m, v, step,
    })
  }

  bulkUpsertOptimizerStates(states: Array<{ sourceId: string; targetId: string; edgeType: string; m: number; v: number; step: number }>): void {
    if (states.length === 0) return
    const stmt = this.db.prepare(`
      INSERT INTO synapse_optimizer_state (source_id, target_id, edge_type, m, v, step)
      VALUES (@source_id, @target_id, @edge_type, @m, @v, @step)
      ON CONFLICT(source_id, target_id, edge_type)
      DO UPDATE SET m = @m, v = @v, step = @step
    `)
    const tx = this.db.transaction((items: typeof states) => {
      for (const s of items) {
        stmt.run({
          source_id: s.sourceId,
          target_id: s.targetId,
          edge_type: s.edgeType,
          m: s.m, v: s.v, step: s.step,
        })
      }
    })
    tx(states)
  }

  updateSynapseWeight(sourceId: string, targetId: string, edgeType: string, newWeight: number): boolean {
    const result = this.db.prepare(
      `UPDATE mnemic_synapses SET weight = ? WHERE source_id = ? AND target_id = ? AND edge_type = ?`
    ).run(newWeight, sourceId, targetId, edgeType)
    return result.changes > 0
  }

  bulkUpdateSynapseWeights(updates: Array<{ sourceId: string; targetId: string; edgeType: string; weight: number }>): number {
    if (updates.length === 0) return 0
    const stmt = this.db.prepare(
      `UPDATE mnemic_synapses SET weight = ? WHERE source_id = ? AND target_id = ? AND edge_type = ?`
    )
    let totalChanges = 0
    const tx = this.db.transaction((items: typeof updates) => {
      for (const u of items) {
        const result = stmt.run(u.weight, u.sourceId, u.targetId, u.edgeType)
        totalChanges += result.changes
      }
    })
    tx(updates)
    return totalChanges
  }

  optimizerStateCount(): number {
    return (this.db.prepare(`SELECT COUNT(*) as c FROM synapse_optimizer_state`).get() as { c: number }).c
  }

  getLightningGlobal(): {
    wDq: Float32Array
    wIuq: Float32Array
    wI: Float32Array
    dEmb: number
    dC: number
    nH: number
    dIdx: number
    version: number
    updatedAt: string
  } | null {
    const row = this.db.prepare(
      `SELECT w_dq, w_iuq, w_i, d_emb, d_c, n_h, d_idx, version, updated_at
       FROM lightning_index_global WHERE id = 1`
    ).get() as
      | { w_dq: Buffer; w_iuq: Buffer; w_i: Buffer; d_emb: number; d_c: number; n_h: number; d_idx: number; version: number; updated_at: string }
      | undefined

    if (!row) return null

    const wDq = toFloatArray(row.w_dq)
    const wIuq = toFloatArray(row.w_iuq)
    const wI = toFloatArray(row.w_i)
    if (!wDq || !wIuq || !wI) return null

    return {
      wDq,
      wIuq,
      wI,
      dEmb: row.d_emb,
      dC: row.d_c,
      nH: row.n_h,
      dIdx: row.d_idx,
      version: row.version,
      updatedAt: row.updated_at,
    }
  }

  setLightningGlobal(g: {
    wDq: Float32Array
    wIuq: Float32Array
    wI: Float32Array
    dEmb: number
    dC: number
    nH: number
    dIdx: number
    version: number
  }): void {
    const now = new Date().toISOString()
    this.db.prepare(
      `INSERT INTO lightning_index_global (id, w_dq, w_iuq, w_i, d_emb, d_c, n_h, d_idx, version, updated_at)
       VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
       ON CONFLICT(id) DO UPDATE SET
         w_dq = excluded.w_dq,
         w_iuq = excluded.w_iuq,
         w_i = excluded.w_i,
         d_emb = excluded.d_emb,
         d_c = excluded.d_c,
         n_h = excluded.n_h,
         d_idx = excluded.d_idx,
         version = excluded.version,
         updated_at = excluded.updated_at`
    ).run(
      fromFloatArray(g.wDq),
      fromFloatArray(g.wIuq),
      fromFloatArray(g.wI),
      g.dEmb,
      g.dC,
      g.nH,
      g.dIdx,
      g.version,
      now,
    )
  }

  getLightningKeys(ids: string[]): Map<string, Float32Array> {
    const out = new Map<string, Float32Array>()
    if (ids.length === 0) return out

    const placeholders = ids.map(() => '?').join(',')
    const rows = this.db.prepare(
      `SELECT engram_id, keys FROM lightning_index_keys WHERE engram_id IN (${placeholders})`
    ).all(...ids) as Array<{ engram_id: string; keys: Buffer }>

    for (const row of rows) {
      const arr = toFloatArray(row.keys)
      if (arr) out.set(row.engram_id, arr)
    }
    return out
  }

  bulkUpsertLightningKeys(entries: Array<{ engramId: string; keys: Float32Array | Buffer; version: number }>): number {
    if (entries.length === 0) return 0
    const now = new Date().toISOString()
    const stmt = this.db.prepare(
      `INSERT INTO lightning_index_keys (engram_id, keys, version, updated_at)
       VALUES (?, ?, ?, ?)
       ON CONFLICT(engram_id) DO UPDATE SET
         keys = excluded.keys,
         version = excluded.version,
         updated_at = excluded.updated_at`
    )
    const tx = this.db.transaction((items: typeof entries) => {
      for (const e of items) {
        const keysBuf = e.keys instanceof Buffer ? e.keys : fromFloatArray(e.keys as Float32Array)
        stmt.run(e.engramId, keysBuf, e.version, now)
      }
    })
    tx(entries)
    return entries.length
  }

  lightningKeysCount(): number {
    return (this.db.prepare(`SELECT COUNT(*) as c FROM lightning_index_keys`).get() as { c: number }).c
  }

  recordLightningRetrievalEvent(ev: LightningRetrievalEvent): void {
    const queryEmbBlob = ev.queryEmbedding ? compressEmbedding(ev.queryEmbedding) : null
    this.db.prepare(
      `INSERT INTO lightning_retrieval_events
        (retrieval_id, session_id, query_text, query_embedding, candidate_ids,
         indexer_scores, reranker_scores, indexer_version, mode, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
       ON CONFLICT(retrieval_id) DO UPDATE SET
         session_id = excluded.session_id,
         query_text = excluded.query_text,
         query_embedding = excluded.query_embedding,
         candidate_ids = excluded.candidate_ids,
         indexer_scores = excluded.indexer_scores,
         reranker_scores = excluded.reranker_scores,
         indexer_version = excluded.indexer_version,
         mode = excluded.mode,
         created_at = excluded.created_at`
    ).run(
      ev.retrievalId,
      ev.sessionId ?? null,
      ev.queryText,
      queryEmbBlob,
      JSON.stringify(ev.candidateIds),
      ev.indexerScores ? JSON.stringify(Array.from(ev.indexerScores)) : null,
      ev.rerankerScores ? JSON.stringify(Array.from(ev.rerankerScores)) : null,
      ev.indexerVersion ?? null,
      ev.mode,
      ev.createdAt ?? new Date().toISOString(),
    )
  }

  getLightningRetrievalEvent(retrievalId: string): LightningRetrievalEvent | null {
    const row = this.db.prepare(
      `SELECT retrieval_id, session_id, query_text, query_embedding, candidate_ids,
              indexer_scores, reranker_scores, indexer_version, mode, created_at
       FROM lightning_retrieval_events WHERE retrieval_id = ?`
    ).get(retrievalId) as
      | {
          retrieval_id: string
          session_id: string | null
          query_text: string
          query_embedding: Buffer | null
          candidate_ids: string
          indexer_scores: string | null
          reranker_scores: string | null
          indexer_version: number | null
          mode: string
          created_at: string
        }
      | undefined

    if (!row) return null
    return this._rowToRetrievalEvent(row)
  }

  queryLightningRetrievalEvents(q: LightningRetrievalEventQuery): LightningRetrievalEvent[] {
    const where: string[] = []
    const args: unknown[] = []
    if (q.sessionId !== undefined) { where.push('session_id = ?'); args.push(q.sessionId) }
    if (q.since !== undefined) { where.push('created_at >= ?'); args.push(q.since) }
    if (q.mode !== undefined) { where.push('mode = ?'); args.push(q.mode) }
    const limit = Math.max(1, Math.min(q.limit ?? 200, 1000))

    const sql = `
      SELECT retrieval_id, session_id, query_text, query_embedding, candidate_ids,
             indexer_scores, reranker_scores, indexer_version, mode, created_at
      FROM lightning_retrieval_events
      ${where.length ? `WHERE ${where.join(' AND ')}` : ''}
      ORDER BY created_at DESC
      LIMIT ?
    `
    const rows = this.db.prepare(sql).all(...args, limit) as Array<{
      retrieval_id: string
      session_id: string | null
      query_text: string
      query_embedding: Buffer | null
      candidate_ids: string
      indexer_scores: string | null
      reranker_scores: string | null
      indexer_version: number | null
      mode: string
      created_at: string
    }>
    return rows.map((r) => this._rowToRetrievalEvent(r))
  }

  pruneLightningRetrievalEvents(beforeIso: string): number {
    const r = this.db.prepare(
      `DELETE FROM lightning_retrieval_events WHERE created_at < ?`
    ).run(beforeIso)
    return r.changes ?? 0
  }

  lightningRetrievalEventsCount(): number {
    return (this.db.prepare(
      `SELECT COUNT(*) as c FROM lightning_retrieval_events`
    ).get() as { c: number }).c
  }

  private _rowToRetrievalEvent(row: {
    retrieval_id: string
    session_id: string | null
    query_text: string
    query_embedding: Buffer | null
    candidate_ids: string
    indexer_scores: string | null
    reranker_scores: string | null
    indexer_version: number | null
    mode: string
    created_at: string
  }): LightningRetrievalEvent {
    const candidateIds = JSON.parse(row.candidate_ids) as string[]
    const indexerScores = row.indexer_scores
      ? Float32Array.from(JSON.parse(row.indexer_scores) as number[])
      : null
    const rerankerScores = row.reranker_scores
      ? Float32Array.from(JSON.parse(row.reranker_scores) as number[])
      : null
    const queryEmbedding = row.query_embedding ? toFloatArray(row.query_embedding) : null
    return {
      retrievalId: row.retrieval_id,
      sessionId: row.session_id ?? undefined,
      queryText: row.query_text,
      queryEmbedding: queryEmbedding ?? undefined,
      candidateIds,
      indexerScores: indexerScores ?? undefined,
      rerankerScores: rerankerScores ?? undefined,
      indexerVersion: row.indexer_version ?? undefined,
      mode: row.mode as LightningRetrievalEvent['mode'],
      createdAt: row.created_at,
    }
  }

  recordIndexerTrainingRequests(triples: RetrievalLabelTriple[], _source?: string): number {
    if (triples.length === 0) return 0
    const merged = mergeTrainingTriples(triples)
    const stmt = this.db.prepare(
      `INSERT INTO lightning_training_requests
         (retrieval_id, candidate_id, label, weight, evidence,
          indexer_score, reranker_score, processed_at, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?)
       ON CONFLICT(retrieval_id, candidate_id) DO UPDATE SET
         label = excluded.label,
         weight = excluded.weight,
         evidence = excluded.evidence,
         indexer_score = COALESCE(excluded.indexer_score, indexer_score),
         reranker_score = COALESCE(excluded.reranker_score, reranker_score),
         processed_at = NULL,
         created_at = excluded.created_at
       WHERE
         (CASE excluded.label
            WHEN 'used' THEN 4
            WHEN 'should_have_been_retrieved' THEN 3
            WHEN 'contradicted' THEN 2
            WHEN 'ignored' THEN 1
            ELSE 0 END)
         >=
         (CASE label
            WHEN 'used' THEN 4
            WHEN 'should_have_been_retrieved' THEN 3
            WHEN 'contradicted' THEN 2
            WHEN 'ignored' THEN 1
            ELSE 0 END)`
    )
    const now = new Date().toISOString()
    let written = 0
    const tx = this.db.transaction((rows: RetrievalLabelTriple[]) => {
      for (const t of rows) {
        const result = stmt.run(
          t.retrievalId,
          t.candidateId,
          t.label,
          t.weight,
          JSON.stringify(t.evidence),
          t.indexerScore ?? null,
          t.rerankerScore ?? null,
          now,
        )
        if (result.changes > 0) written++
      }
    })
    tx(merged)
    return written
  }

  getPendingIndexerTrainingRequests(limit: number): RetrievalLabelTriple[] {
    const rows = this.db.prepare(
      `SELECT retrieval_id, candidate_id, label, weight, evidence,
              indexer_score, reranker_score
       FROM lightning_training_requests
       WHERE processed_at IS NULL
       ORDER BY created_at ASC
       LIMIT ?`
    ).all(limit) as Array<{
      retrieval_id: string
      candidate_id: string
      label: RetrievalLabel
      weight: number
      evidence: string
      indexer_score: number | null
      reranker_score: number | null
    }>
    return rows.map(r => ({
      retrievalId: r.retrieval_id,
      candidateId: r.candidate_id,
      label: r.label,
      weight: r.weight,
      evidence: parseJsonSafe(r.evidence, []),
      indexerScore: r.indexer_score ?? undefined,
      rerankerScore: r.reranker_score ?? undefined,
    }))
  }

  markIndexerTrainingRequestsProcessed(retrievalIds: string[]): number {
    if (retrievalIds.length === 0) return 0
    const placeholders = retrievalIds.map(() => '?').join(',')
    const result = this.db.prepare(
      `UPDATE lightning_training_requests
       SET processed_at = ?
       WHERE retrieval_id IN (${placeholders}) AND processed_at IS NULL`
    ).run(new Date().toISOString(), ...retrievalIds)
    return result.changes
  }

  countPendingIndexerTrainingRequests(): number {
    const row = this.db.prepare(
      `SELECT COUNT(*) AS n FROM lightning_training_requests WHERE processed_at IS NULL`
    ).get() as { n: number }
    return row.n
  }

  /** Alias: trainer-side name for the same query. */
  unprocessedTrainingRequestCount(): number {
    return this.countPendingIndexerTrainingRequests()
  }

  getEngramSummariesByIds(ids: string[]): Map<string, { id: string; content: string; tags: string[] }> {
    const out = new Map<string, { id: string; content: string; tags: string[] }>()
    if (ids.length === 0) return out
    const placeholders = ids.map(() => '?').join(',')
    const rows = this.db.prepare(
      `SELECT id, content, tags FROM engrams WHERE id IN (${placeholders})`
    ).all(...ids) as Array<{ id: string; content: string; tags: string }>
    for (const r of rows) {
      out.set(r.id, {
        id: r.id,
        content: r.content,
        tags: parseJsonSafe<string[]>(r.tags, []),
      })
    }
    return out
  }

  close(): void {
    try {
      this.db.close()
      this.logger.info('Mnemic Cortex closed')
    } catch { /* already closed */ }
  }
}

const LABEL_STRENGTH: Record<RetrievalLabel, number> = {
  used: 4,
  should_have_been_retrieved: 3,
  contradicted: 2,
  ignored: 1,
}

function mergeTrainingTriples(triples: RetrievalLabelTriple[]): RetrievalLabelTriple[] {
  const byKey = new Map<string, RetrievalLabelTriple>()
  for (const t of triples) {
    const key = `${t.retrievalId}|${t.candidateId}`
    const existing = byKey.get(key)
    if (!existing) {
      byKey.set(key, { ...t, evidence: [...t.evidence] })
      continue
    }
    const existingStrength = LABEL_STRENGTH[existing.label] ?? 0
    const incomingStrength = LABEL_STRENGTH[t.label] ?? 0
    const combinedEvidence = [...existing.evidence, ...t.evidence]
    if (incomingStrength > existingStrength) {
      byKey.set(key, {
        ...t,
        evidence: combinedEvidence,
        indexerScore: t.indexerScore ?? existing.indexerScore,
        rerankerScore: t.rerankerScore ?? existing.rerankerScore,
      })
    } else {
      existing.evidence = combinedEvidence
      existing.weight = Math.max(existing.weight, t.weight)
      if (existing.indexerScore === undefined && t.indexerScore !== undefined) {
        existing.indexerScore = t.indexerScore
      }
      if (existing.rerankerScore === undefined && t.rerankerScore !== undefined) {
        existing.rerankerScore = t.rerankerScore
      }
    }
  }
  return Array.from(byKey.values())
}
