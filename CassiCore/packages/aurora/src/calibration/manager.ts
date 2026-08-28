/**
 * UCF CalibrationManager — registers probe sets, runs them on demand,
 * compares against the prior run for drift, and surfaces drift through
 * the Aurora Event Journal when a journal is wired.
 *
 * The manager owns the runtime registry of MeasurementFn / DriftMetricFn
 * (which can't be serialized). The store owns probe-set metadata, probe
 * content, and result history.
 */

import type { ILogger } from '@cassicore/foundation'
import type { EventJournal } from '../event-journal.js'
import type {
  CalibrationProbeSet,
  CalibrationResult,
  DriftReport,
  MeasurementResult,
  RunOptions,
} from './types.js'
import { meanL1DriftMetric, emptyDrift } from './drift.js'
import { CalibrationStore } from './store.js'

export interface CalibrationManagerDeps {
  store: CalibrationStore
  logger: ILogger
  eventJournal?: EventJournal | null
}

interface RuntimeRegistration {
  probeSet: CalibrationProbeSet
}

export class CalibrationManager {
  private readonly logger: ILogger
  private readonly store: CalibrationStore
  private readonly eventJournal: EventJournal | null
  private readonly registry = new Map<string, RuntimeRegistration>()

  constructor(deps: CalibrationManagerDeps) {
    this.logger = deps.logger.child ? deps.logger.child('aurora:calibration') : deps.logger
    this.store = deps.store
    this.eventJournal = deps.eventJournal ?? null
  }

  /**
   * Register a probe set. Persists metadata/probes to the store and binds
   * the in-memory MeasurementFn / DriftMetricFn so runCalibration can call
   * them. Re-registering with the same id replaces the runtime callbacks
   * and updates the store rows.
   */
  registerProbeSet(probeSet: CalibrationProbeSet): void {
    this.store.upsertProbeSet(
      {
        id: probeSet.id,
        ownerSpec: probeSet.ownerSpec,
        description: probeSet.description,
        schedule: probeSet.schedule,
        metadata: probeSet.metadata,
      },
      probeSet.probes,
    )
    this.registry.set(probeSet.id, { probeSet })
    this.logger.debug?.('[UCF] Registered probe set', { id: probeSet.id, ownerSpec: probeSet.ownerSpec, probeCount: probeSet.probes.length })
  }

  /** Drop a probe set from the registry and the store. */
  unregisterProbeSet(id: string): boolean {
    this.registry.delete(id)
    return this.store.deleteProbeSet(id)
  }

  /** List probe sets that have been registered (in-memory, runtime view). */
  listRegistered(): CalibrationProbeSet[] {
    return [...this.registry.values()].map(r => r.probeSet)
  }

  /**
   * Run a single calibration: invoke the measurement function on each probe,
   * compare against the most recent prior result via the probe set's
   * driftMetric (or the default mean-L1), persist the result, and emit a
   * drift event when magnitude crosses the no_action threshold.
   *
   * `RunOptions.skipDriftComparison` short-circuits the comparison — useful
   * for the first calibration of a new probe set so the baseline doesn't
   * trigger a spurious drift event.
   */
  async runCalibration(probeSetId: string, opts: RunOptions = {}): Promise<CalibrationResult> {
    const reg = this.registry.get(probeSetId)
    if (!reg) throw new Error(`probe set "${probeSetId}" not registered`)
    const probeSet = reg.probeSet

    const results: MeasurementResult[] = []
    for (const probe of probeSet.probes) {
      const r = await probeSet.measurement(probe)
      results.push(r)
    }

    let drift: DriftReport | null = null
    if (!opts.skipDriftComparison) {
      const prior = this.store.latestResult(probeSetId)
      if (prior) {
        const metric = probeSet.driftMetric ?? meanL1DriftMetric
        drift = metric(prior.results, results)
      }
    }

    const id = `cal-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    const ranAt = new Date().toISOString()
    const result: CalibrationResult = {
      id,
      probeSetId,
      ranAt,
      results,
      drift,
      metadata: { sessionId: opts.sessionId ?? null },
    }
    this.store.recordResult(result)

    if (drift && drift.recommendation !== 'no_action') {
      this.surfaceDrift(probeSet, drift, ranAt)
    }
    return result
  }

  /**
   * Drift surveillance over recent history: compare the most recent run to
   * the one before it. Distinct from runCalibration in that it doesn't run
   * the measurement function — it just inspects what's already stored.
   */
  surveillDrift(probeSetId: string): DriftReport | null {
    const reg = this.registry.get(probeSetId)
    const recent = this.store.listResults(probeSetId, { limit: 2 })
    if (recent.length < 2) return null
    const metric = reg?.probeSet.driftMetric ?? meanL1DriftMetric
    return metric(recent[1].results, recent[0].results)
  }

  /** Run history for a probe set, newest first. */
  history(probeSetId: string, opts?: { since?: string; limit?: number }): CalibrationResult[] {
    return this.store.listResults(probeSetId, opts)
  }

  /**
   * Convenience for daemon ticks: run every registered probe set whose
   * schedule.triggeredBy === 'startup' or .frequency === 'manual' is FALSE
   * (i.e., we want the framework to pick it up on its own). Manual-only
   * probe sets are skipped.
   *
   * Returns one CalibrationResult per probe set actually run.
   */
  async runScheduled(opts: RunOptions = {}): Promise<CalibrationResult[]> {
    const out: CalibrationResult[] = []
    for (const reg of this.registry.values()) {
      if (reg.probeSet.schedule.frequency === 'manual' && reg.probeSet.schedule.triggeredBy !== 'startup') continue
      try {
        out.push(await this.runCalibration(reg.probeSet.id, opts))
      } catch (err) {
        this.logger.warn?.('[UCF] Scheduled run failed', { id: reg.probeSet.id, error: String(err) })
      }
    }
    return out
  }

  private surfaceDrift(probeSet: CalibrationProbeSet, drift: DriftReport, ranAt: string): void {
    if (!this.eventJournal) {
      this.logger.info?.('[UCF] Drift detected', {
        id: probeSet.id, magnitude: drift.magnitude, recommendation: drift.recommendation, affected: drift.affected.length,
      })
      return
    }
    this.eventJournal.emit({
      source: 'UCF',
      category: 'calibration_drift',
      text: `Probe set ${probeSet.id} (owner ${probeSet.ownerSpec}) shows ${(drift.magnitude * 100).toFixed(1)}% drift; ${drift.affected.length} probes significantly changed`,
      tags: ['calibration', 'drift', drift.recommendation],
      occurredAt: ranAt,
      metadata: {
        probeSetId: probeSet.id,
        ownerSpec: probeSet.ownerSpec,
        magnitude: drift.magnitude,
        recommendation: drift.recommendation,
        affected: drift.affected,
      },
    })
  }
}
