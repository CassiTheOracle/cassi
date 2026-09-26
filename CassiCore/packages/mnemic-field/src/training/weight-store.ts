import type Database from 'better-sqlite3'

export interface IndexerWeights {
  wDq: Float32Array
  wIuq: Float32Array
  wI: Float32Array
}

export interface IndexerDims {
  dEmb: number
  dC: number
  nH: number
  dIdx: number
}

export type IndexerVersionStatus = 'active' | 'archived' | 'rolled_back'

export interface IndexerVersionRow {
  version: number
  parentVersion: number | null
  weights: IndexerWeights
  dims: IndexerDims
  status: IndexerVersionStatus
  trainingSteps: number
  requestsConsumed: number
  validationLoss: number | null
  validationRecallAt5: number | null
  notes: string | null
  createdAt: string
}

export interface SaveSnapshotInput {
  parentVersion: number | null
  weights: IndexerWeights
  dims: IndexerDims
  trainingSteps: number
  requestsConsumed: number
  validationLoss?: number
  validationRecallAt5?: number
  notes?: string
  status?: IndexerVersionStatus
}

export interface RecordTrainingStepInput {
  version: number
  requestsInBatch: number
  lossBefore?: number
  lossAfter?: number
  learningRate: number
  muonMomentum?: number
  muonSteps: number
  adamwSteps: number
  gradNorm?: number
  durationMs: number
}

interface VersionRowRaw {
  version: number
  parent_version: number | null
  weights: Buffer
  d_emb: number
  d_c: number
  n_h: number
  d_idx: number
  status: IndexerVersionStatus
  training_steps: number
  requests_consumed: number
  validation_loss: number | null
  validation_recall_at_5: number | null
  notes: string | null
  created_at: string
}

export class WeightStore {
  constructor(private readonly db: Database.Database) {}

  saveSnapshot(input: SaveSnapshotInput): number {
    const blob = packWeights(input.weights, input.dims)
    const status = input.status ?? 'archived'
    const stmt = this.db.prepare(`
      INSERT INTO indexer_versions (
        parent_version, weights, d_emb, d_c, n_h, d_idx, status,
        training_steps, requests_consumed,
        validation_loss, validation_recall_at_5, notes, created_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `)
    const info = stmt.run(
      input.parentVersion,
      blob,
      input.dims.dEmb,
      input.dims.dC,
      input.dims.nH,
      input.dims.dIdx,
      status,
      input.trainingSteps,
      input.requestsConsumed,
      input.validationLoss ?? null,
      input.validationRecallAt5 ?? null,
      input.notes ?? null,
      new Date().toISOString(),
    )
    return Number(info.lastInsertRowid)
  }

  promote(version: number, opts?: { notes?: string }): void {
    const target = this.loadVersion(version)
    if (!target) throw new Error(`promote: version ${version} not found`)
    if (target.status === 'rolled_back') {
      throw new Error(`promote: refusing to promote rolled_back version ${version}`)
    }
    const tx = this.db.transaction(() => {
      this.db.prepare(`UPDATE indexer_versions SET status = 'archived' WHERE status = 'active'`).run()
      const result = this.db.prepare(`
        UPDATE indexer_versions
        SET status = 'active', notes = COALESCE(?, notes)
        WHERE version = ?
      `).run(opts?.notes ?? null, version)
      if (result.changes !== 1) throw new Error(`promote: expected 1 row update, got ${result.changes}`)
    })
    tx()
  }

  rollback(version: number, opts?: { notes?: string }): void {
    const target = this.loadVersion(version)
    if (!target) throw new Error(`rollback: version ${version} not found`)
    if (target.status !== 'active') {
      throw new Error(`rollback: version ${version} is not active (status=${target.status})`)
    }
    this.db.prepare(`
      UPDATE indexer_versions
      SET status = 'rolled_back', notes = COALESCE(?, notes)
      WHERE version = ?
    `).run(opts?.notes ?? null, version)
  }

  loadActive(): IndexerVersionRow | null {
    const row = this.db.prepare<[], VersionRowRaw>(`
      SELECT version, parent_version, weights, d_emb, d_c, n_h, d_idx, status,
             training_steps, requests_consumed,
             validation_loss, validation_recall_at_5, notes, created_at
      FROM indexer_versions
      WHERE status = 'active'
      LIMIT 1
    `).get()
    return row ? rowToVersion(row) : null
  }

  loadVersion(version: number): IndexerVersionRow | null {
    const row = this.db.prepare<[number], VersionRowRaw>(`
      SELECT version, parent_version, weights, d_emb, d_c, n_h, d_idx, status,
             training_steps, requests_consumed,
             validation_loss, validation_recall_at_5, notes, created_at
      FROM indexer_versions
      WHERE version = ?
    `).get(version)
    return row ? rowToVersion(row) : null
  }

  listVersions(opts?: { limit?: number; status?: IndexerVersionStatus }): IndexerVersionRow[] {
    const limit = opts?.limit ?? 50
    const params: unknown[] = []
    let where = ''
    if (opts?.status) {
      where = ' WHERE status = ?'
      params.push(opts.status)
    }
    params.push(limit)
    const rows = this.db.prepare<unknown[], VersionRowRaw>(`
      SELECT version, parent_version, weights, d_emb, d_c, n_h, d_idx, status,
             training_steps, requests_consumed,
             validation_loss, validation_recall_at_5, notes, created_at
      FROM indexer_versions${where}
      ORDER BY version DESC
      LIMIT ?
    `).all(...params)
    return rows.map(rowToVersion)
  }

  recordTrainingStep(input: RecordTrainingStepInput): number {
    const stmt = this.db.prepare(`
      INSERT INTO indexer_training_steps (
        version, requests_in_batch, loss_before, loss_after,
        learning_rate, muon_momentum, muon_steps, adamw_steps,
        grad_norm, duration_ms, created_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `)
    const info = stmt.run(
      input.version,
      input.requestsInBatch,
      input.lossBefore ?? null,
      input.lossAfter ?? null,
      input.learningRate,
      input.muonMomentum ?? null,
      input.muonSteps,
      input.adamwSteps,
      input.gradNorm ?? null,
      input.durationMs,
      new Date().toISOString(),
    )
    return Number(info.lastInsertRowid)
  }
}

function packWeights(w: IndexerWeights, dims: IndexerDims): Buffer {
  const expectedDq = dims.dC * dims.dEmb
  const expectedIuq = dims.nH * dims.dIdx * dims.dC
  const expectedI = dims.nH
  if (w.wDq.length !== expectedDq) {
    throw new Error(`packWeights: wDq length ${w.wDq.length} != ${expectedDq}`)
  }
  if (w.wIuq.length !== expectedIuq) {
    throw new Error(`packWeights: wIuq length ${w.wIuq.length} != ${expectedIuq}`)
  }
  if (w.wI.length !== expectedI) {
    throw new Error(`packWeights: wI length ${w.wI.length} != ${expectedI}`)
  }
  const totalFloats = expectedDq + expectedIuq + expectedI
  const out = new Float32Array(totalFloats)
  out.set(w.wDq, 0)
  out.set(w.wIuq, expectedDq)
  out.set(w.wI, expectedDq + expectedIuq)
  return Buffer.from(out.buffer, out.byteOffset, out.byteLength)
}

function unpackWeights(blob: Buffer, dims: IndexerDims): IndexerWeights {
  const expectedDq = dims.dC * dims.dEmb
  const expectedIuq = dims.nH * dims.dIdx * dims.dC
  const expectedI = dims.nH
  const totalFloats = expectedDq + expectedIuq + expectedI
  const expectedBytes = totalFloats * 4
  if (blob.byteLength !== expectedBytes) {
    throw new Error(`unpackWeights: blob size ${blob.byteLength} != ${expectedBytes}`)
  }
  const view = new Float32Array(blob.buffer, blob.byteOffset, totalFloats)
  return {
    wDq: Float32Array.from(view.subarray(0, expectedDq)),
    wIuq: Float32Array.from(view.subarray(expectedDq, expectedDq + expectedIuq)),
    wI: Float32Array.from(view.subarray(expectedDq + expectedIuq)),
  }
}

function rowToVersion(row: VersionRowRaw): IndexerVersionRow {
  const dims: IndexerDims = {
    dEmb: row.d_emb,
    dC: row.d_c,
    nH: row.n_h,
    dIdx: row.d_idx,
  }
  return {
    version: row.version,
    parentVersion: row.parent_version,
    weights: unpackWeights(row.weights, dims),
    dims,
    status: row.status,
    trainingSteps: row.training_steps,
    requestsConsumed: row.requests_consumed,
    validationLoss: row.validation_loss,
    validationRecallAt5: row.validation_recall_at_5,
    notes: row.notes,
    createdAt: row.created_at,
  }
}
