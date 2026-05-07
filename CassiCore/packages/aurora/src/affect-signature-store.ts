/**
 * B2 affect-signature persistence store.
 *
 * Reads/writes the `feature_affect_signatures` and
 * `feature_affect_probe_sets` tables (schema v3). Owns no business
 * logic — just storage and retrieval. The calibration command
 * computes signatures and writes them; the LarqlKnowledgeProvider
 * reads them at boot and surfaces them via
 * `setFeatureAffectSignatureProvider`.
 */

import type Database from 'better-sqlite3'
import type { ILogger } from '../../../types/interfaces.js'
import type { AffectLabel } from '../mnemic-field/types.js'
import type { FeatureAffectSignature } from './larql-provider.js'

export interface ProbeSetRecord {
  id: string
  vindexId: string
  description: string | null
  probeCountPerQuadrant: number
  totalProbes: number
  createdAt: string
  metadata: Record<string, unknown>
}

export class AffectSignatureStore {
  private readonly db: Database.Database
  private readonly logger: ILogger

  constructor(db: Database.Database, logger: ILogger) {
    this.db = db
    this.logger = logger.child ? logger.child('aurora:affect-sig-store') : logger
  }

  /**
   * Bulk-write signatures for a vindex. Replaces any existing row at the
   * same (vindex_id, layer, feature_index). Wraps in a transaction for
   * O(N) instead of O(N) commits.
   */
  upsertSignatures(
    vindexId: string,
    probeSetId: string,
    signatures: FeatureAffectSignature[],
  ): void {
    const stmt = this.db.prepare(`
      INSERT INTO feature_affect_signatures
        (vindex_id, layer, feature_index, labels_json, magnitude, computed_at, probe_set_id)
      VALUES (?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(vindex_id, layer, feature_index) DO UPDATE SET
        labels_json = excluded.labels_json,
        magnitude   = excluded.magnitude,
        computed_at = excluded.computed_at,
        probe_set_id = excluded.probe_set_id
    `)
    const now = new Date().toISOString()
    const tx = this.db.transaction((rows: FeatureAffectSignature[]) => {
      for (const s of rows) {
        stmt.run(vindexId, s.layer, s.featureIndex, JSON.stringify(s.labels), s.magnitude, now, probeSetId)
      }
    })
    tx(signatures)
    this.logger.debug?.('B2 signatures persisted', { vindexId, count: signatures.length, probeSetId })
  }

  /** Read a single signature; returns null when not present. */
  getSignature(vindexId: string, layer: number, featureIndex: number): FeatureAffectSignature | null {
    const row = this.db.prepare(`
      SELECT layer, feature_index, labels_json, magnitude
      FROM feature_affect_signatures
      WHERE vindex_id = ? AND layer = ? AND feature_index = ?
    `).get(vindexId, layer, featureIndex) as {
      layer: number; feature_index: number; labels_json: string; magnitude: number;
    } | undefined
    if (!row) return null
    return {
      layer: row.layer,
      featureIndex: row.feature_index,
      labels: JSON.parse(row.labels_json) as Partial<Record<AffectLabel, number>>,
      magnitude: row.magnitude,
    }
  }

  /**
   * Load all signatures for a vindex into memory as a Map keyed by
   * `${layer}:${featureIndex}`. The Map shape is exactly what the
   * provider's `FeatureAffectSignatureProvider` callback wants —
   * callers can wrap with `(layer, idx) => map.get(\`${layer}:${idx}\`) ?? null`.
   *
   * Returns an empty map when nothing's persisted for the vindex.
   */
  loadAllAsMap(vindexId: string): Map<string, FeatureAffectSignature> {
    const out = new Map<string, FeatureAffectSignature>()
    const rows = this.db.prepare(`
      SELECT layer, feature_index, labels_json, magnitude
      FROM feature_affect_signatures
      WHERE vindex_id = ?
    `).all(vindexId) as Array<{
      layer: number; feature_index: number; labels_json: string; magnitude: number;
    }>
    for (const row of rows) {
      out.set(`${row.layer}:${row.feature_index}`, {
        layer: row.layer,
        featureIndex: row.feature_index,
        labels: JSON.parse(row.labels_json) as Partial<Record<AffectLabel, number>>,
        magnitude: row.magnitude,
      })
    }
    return out
  }

  /** Count signatures stored for a vindex. */
  count(vindexId: string): number {
    const row = this.db.prepare(`
      SELECT COUNT(*) AS n FROM feature_affect_signatures WHERE vindex_id = ?
    `).get(vindexId) as { n: number }
    return row.n
  }

  /** Clear all signatures for a vindex. Returns rows deleted. */
  clear(vindexId: string): number {
    const r = this.db.prepare(`DELETE FROM feature_affect_signatures WHERE vindex_id = ?`).run(vindexId)
    return r.changes
  }

  /** Register a probe-set metadata row. Idempotent on id. */
  upsertProbeSet(rec: ProbeSetRecord): void {
    this.db.prepare(`
      INSERT INTO feature_affect_probe_sets
        (id, vindex_id, description, probe_count_per_quadrant, total_probes, created_at, metadata)
      VALUES (?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(id) DO UPDATE SET
        vindex_id = excluded.vindex_id,
        description = excluded.description,
        probe_count_per_quadrant = excluded.probe_count_per_quadrant,
        total_probes = excluded.total_probes,
        metadata = excluded.metadata
    `).run(
      rec.id, rec.vindexId, rec.description, rec.probeCountPerQuadrant,
      rec.totalProbes, rec.createdAt, JSON.stringify(rec.metadata ?? {}),
    )
  }

  /** Read a probe-set metadata row. */
  getProbeSet(id: string): ProbeSetRecord | null {
    const row = this.db.prepare(`
      SELECT id, vindex_id, description, probe_count_per_quadrant, total_probes, created_at, metadata
      FROM feature_affect_probe_sets
      WHERE id = ?
    `).get(id) as {
      id: string; vindex_id: string; description: string | null;
      probe_count_per_quadrant: number; total_probes: number;
      created_at: string; metadata: string;
    } | undefined
    if (!row) return null
    return {
      id: row.id,
      vindexId: row.vindex_id,
      description: row.description,
      probeCountPerQuadrant: row.probe_count_per_quadrant,
      totalProbes: row.total_probes,
      createdAt: row.created_at,
      metadata: JSON.parse(row.metadata) as Record<string, unknown>,
    }
  }
}
