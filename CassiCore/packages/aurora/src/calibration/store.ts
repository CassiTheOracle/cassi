/**
 * UCF SQLite store — probe sets, probes, and run results.
 *
 * MeasurementFn / DriftMetricFn are NOT serialized; they live in the
 * registered runtime object. The store persists everything else so probe
 * sets and history survive restarts.
 */

import * as fs from 'fs'
import * as path from 'path'
import Database from 'better-sqlite3'

import type { ILogger } from '../../../../types/interfaces.js'
import type {
  CalibrationProbeSet,
  CalibrationResult,
  CalibrationSchedule,
  Probe,
  MeasurementResult,
  DriftReport,
} from './types.js'

const SCHEMA_V1 = `
  CREATE TABLE IF NOT EXISTS calibration_schema_version (
    version INTEGER PRIMARY KEY
  );

  CREATE TABLE IF NOT EXISTS calibration_probe_sets (
    id           TEXT PRIMARY KEY,
    owner_spec   TEXT NOT NULL,
    description  TEXT NOT NULL,
    schedule     TEXT NOT NULL DEFAULT '{}',
    metadata     TEXT NOT NULL DEFAULT '{}'
  );

  CREATE TABLE IF NOT EXISTS calibration_probes (
    probe_set_id TEXT NOT NULL REFERENCES calibration_probe_sets(id) ON DELETE CASCADE,
    probe_id     TEXT NOT NULL,
    input        TEXT NOT NULL,
    expected     TEXT,
    weight       REAL NOT NULL DEFAULT 1.0,
    metadata     TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (probe_set_id, probe_id)
  );

  CREATE TABLE IF NOT EXISTS calibration_results (
    id           TEXT PRIMARY KEY,
    probe_set_id TEXT NOT NULL REFERENCES calibration_probe_sets(id) ON DELETE CASCADE,
    ran_at       TEXT NOT NULL,
    results      TEXT NOT NULL,
    drift        TEXT,
    new_params   TEXT,
    metadata     TEXT NOT NULL DEFAULT '{}'
  );

  CREATE INDEX IF NOT EXISTS idx_calibration_results_set_ran
    ON calibration_results(probe_set_id, ran_at DESC);

  INSERT OR IGNORE INTO calibration_schema_version (version) VALUES (1);
`

interface ProbeSetRow {
  id: string
  owner_spec: string
  description: string
  schedule: string
  metadata: string
}

interface ProbeRow {
  probe_set_id: string
  probe_id: string
  input: string
  expected: string | null
  weight: number
  metadata: string
}

interface ResultRow {
  id: string
  probe_set_id: string
  ran_at: string
  results: string
  drift: string | null
  new_params: string | null
  metadata: string
}

export type StoredProbeSet = Omit<CalibrationProbeSet, 'measurement' | 'driftMetric'>

export class CalibrationStore {
  private readonly logger: ILogger
  private readonly db: Database.Database
  private readonly ownsDb: boolean

  private stmtUpsertProbeSet!: Database.Statement
  private stmtUpsertProbe!: Database.Statement
  private stmtListProbeSets!: Database.Statement
  private stmtGetProbeSet!: Database.Statement
  private stmtListProbesFor!: Database.Statement
  private stmtDeleteProbeSet!: Database.Statement
  private stmtDeleteProbe!: Database.Statement
  private stmtInsertResult!: Database.Statement
  private stmtListResults!: Database.Statement
  private stmtLatestResult!: Database.Statement

  constructor(dbOrPath: string | Database.Database, logger: ILogger) {
    this.logger = logger.child ? logger.child('aurora:calibration-store') : logger
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
    this.initSchema()
    this.prepareStatements()
  }

  private initSchema(): void { this.db.exec(SCHEMA_V1) }

  private prepareStatements(): void {
    this.stmtUpsertProbeSet = this.db.prepare(`
      INSERT INTO calibration_probe_sets (id, owner_spec, description, schedule, metadata)
      VALUES (?, ?, ?, ?, ?)
      ON CONFLICT(id) DO UPDATE SET
        owner_spec  = excluded.owner_spec,
        description = excluded.description,
        schedule    = excluded.schedule,
        metadata    = excluded.metadata
    `)
    this.stmtUpsertProbe = this.db.prepare(`
      INSERT INTO calibration_probes (probe_set_id, probe_id, input, expected, weight, metadata)
      VALUES (?, ?, ?, ?, ?, ?)
      ON CONFLICT(probe_set_id, probe_id) DO UPDATE SET
        input    = excluded.input,
        expected = excluded.expected,
        weight   = excluded.weight,
        metadata = excluded.metadata
    `)
    this.stmtListProbeSets = this.db.prepare(`SELECT * FROM calibration_probe_sets ORDER BY id`)
    this.stmtGetProbeSet = this.db.prepare(`SELECT * FROM calibration_probe_sets WHERE id = ?`)
    this.stmtListProbesFor = this.db.prepare(`SELECT * FROM calibration_probes WHERE probe_set_id = ? ORDER BY probe_id`)
    this.stmtDeleteProbeSet = this.db.prepare(`DELETE FROM calibration_probe_sets WHERE id = ?`)
    this.stmtDeleteProbe = this.db.prepare(`DELETE FROM calibration_probes WHERE probe_set_id = ? AND probe_id = ?`)
    this.stmtInsertResult = this.db.prepare(`
      INSERT INTO calibration_results (id, probe_set_id, ran_at, results, drift, new_params, metadata)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `)
    this.stmtListResults = this.db.prepare(`
      SELECT * FROM calibration_results
      WHERE probe_set_id = ? AND ran_at >= ?
      ORDER BY ran_at DESC
      LIMIT ?
    `)
    this.stmtLatestResult = this.db.prepare(`
      SELECT * FROM calibration_results
      WHERE probe_set_id = ?
      ORDER BY ran_at DESC
      LIMIT 1
    `)
  }

  upsertProbeSet(meta: { id: string; ownerSpec: string; description: string; schedule: CalibrationSchedule; metadata?: Record<string, unknown> }, probes: Probe[]): void {
    const tx = this.db.transaction(() => {
      this.stmtUpsertProbeSet.run(
        meta.id,
        meta.ownerSpec,
        meta.description,
        JSON.stringify(meta.schedule),
        JSON.stringify(meta.metadata ?? {}),
      )
      for (const probe of probes) {
        this.stmtUpsertProbe.run(
          meta.id,
          probe.id,
          JSON.stringify(probe.input),
          probe.expected !== undefined ? JSON.stringify(probe.expected) : null,
          probe.weight ?? 1.0,
          JSON.stringify(probe.metadata ?? {}),
        )
      }
    })
    tx()
  }

  getProbeSet(id: string): StoredProbeSet | null {
    const row = this.stmtGetProbeSet.get(id) as ProbeSetRow | undefined
    if (!row) return null
    return {
      id: row.id,
      ownerSpec: row.owner_spec,
      description: row.description,
      schedule: parseJsonOr(row.schedule, { frequency: 'manual' as const }),
      probes: this.listProbes(id),
      metadata: parseJsonOr(row.metadata, {}),
    }
  }

  listProbeSets(): StoredProbeSet[] {
    const rows = this.stmtListProbeSets.all() as ProbeSetRow[]
    return rows.map(r => ({
      id: r.id,
      ownerSpec: r.owner_spec,
      description: r.description,
      schedule: parseJsonOr(r.schedule, { frequency: 'manual' as const }),
      probes: this.listProbes(r.id),
      metadata: parseJsonOr(r.metadata, {}),
    }))
  }

  listProbes(probeSetId: string): Probe[] {
    const rows = this.stmtListProbesFor.all(probeSetId) as ProbeRow[]
    return rows.map(r => ({
      id: r.probe_id,
      input: parseJsonOr(r.input, null),
      expected: r.expected !== null ? parseJsonOr(r.expected, null) : undefined,
      weight: r.weight,
      metadata: parseJsonOr(r.metadata, {}),
    }))
  }

  deleteProbeSet(id: string): boolean {
    return this.stmtDeleteProbeSet.run(id).changes > 0
  }

  deleteProbe(probeSetId: string, probeId: string): boolean {
    return this.stmtDeleteProbe.run(probeSetId, probeId).changes > 0
  }

  recordResult(result: CalibrationResult): void {
    this.stmtInsertResult.run(
      result.id,
      result.probeSetId,
      result.ranAt,
      JSON.stringify(result.results),
      result.drift ? JSON.stringify(result.drift) : null,
      result.newParameters ? JSON.stringify(result.newParameters) : null,
      JSON.stringify(result.metadata ?? {}),
    )
  }

  listResults(probeSetId: string, opts: { since?: string; limit?: number } = {}): CalibrationResult[] {
    const since = opts.since ?? '1970-01-01T00:00:00.000Z'
    const limit = opts.limit ?? 50
    const rows = this.stmtListResults.all(probeSetId, since, limit) as ResultRow[]
    return rows.map(r => this.rowToResult(r))
  }

  latestResult(probeSetId: string): CalibrationResult | null {
    const row = this.stmtLatestResult.get(probeSetId) as ResultRow | undefined
    return row ? this.rowToResult(row) : null
  }

  close(): void {
    if (this.ownsDb && this.db.open) this.db.close()
  }

  private rowToResult(row: ResultRow): CalibrationResult {
    return {
      id: row.id,
      probeSetId: row.probe_set_id,
      ranAt: row.ran_at,
      results: parseJsonOr<MeasurementResult[]>(row.results, []),
      drift: row.drift ? parseJsonOr<DriftReport>(row.drift, { magnitude: 0, affected: [], recommendation: 'no_action' }) : null,
      newParameters: row.new_params ? parseJsonOr<Record<string, unknown>>(row.new_params, {}) : undefined,
      metadata: parseJsonOr(row.metadata, {}),
    }
  }
}

function parseJsonOr<T>(text: string, fallback: T): T {
  try { return JSON.parse(text) as T } catch { return fallback }
}
