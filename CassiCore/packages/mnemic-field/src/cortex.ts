import Database from 'better-sqlite3'
import { randomUUID } from 'node:crypto'
import type { ILogger } from '../../../types/interfaces.js'
import { initMnemicFieldSchema } from './schema.js'
import type {
  Engram, EngramCreate, EngramUpdate,
  MnemicSynapse, SynapseCreate,
  ActivationSpike, SpikeCreate,
  Nucleus, NucleusCreate,
  SpatialQuery, EngramSearchResult, TensionPair, FieldStats,
  EngramPosition, EngramType,
} from './types.js'

export function toFloatArray(buf: Buffer | null): Float32Array | null {
  if (!buf || buf.length === 0) return null
  return new Float32Array(buf.buffer, buf.byteOffset, buf.byteLength / 4)
}

export function fromFloatArray(arr: Float32Array | number[] | null | undefined): Buffer | null {
  if (!arr) return null
  const f32 = arr instanceof Float32Array ? arr : new Float32Array(arr)
  return Buffer.from(f32.buffer, f32.byteOffset, f32.byteLength)
}

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
        INSERT INTO engrams (id, content, node_type, x, y, t, potentiation, cluster_id, embedding, tags, provenance, created_at, accessed_at, metadata)
        VALUES (@id, @content, @node_type, @x, @y, @t, @potentiation, NULL, @embedding, @tags, @provenance, @created_at, NULL, @metadata)
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
      embedding: fromFloatArray(input.embedding ?? null),
      tags: JSON.stringify(input.tags ?? []),
      provenance: input.provenance ?? '',
      created_at: now,
      metadata: JSON.stringify(input.metadata ?? {}),
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
    if (update.embedding !== undefined) { setClauses.push('embedding = @embedding'); params.embedding = fromFloatArray(update.embedding) }
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
      `SELECT id, content FROM engrams WHERE embedding IS NULL LIMIT ?`
    ).all(limit) as Array<{ id: string; content: string }>
  }

  /**
   * Count engrams missing embeddings without loading them into memory.
   */
  countMissingEmbeddings(): number {
    return (this.db.prepare(`SELECT COUNT(*) as c FROM engrams WHERE embedding IS NULL`).get() as { c: number }).c
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

  close(): void {
    try {
      this.db.close()
      this.logger.info('Mnemic Cortex closed')
    } catch { /* already closed */ }
  }
}
