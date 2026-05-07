/**
 * WSA → UCF integration: probe set builder.
 *
 * Registers a CalibrationProbeSet with the universal calibration
 * framework so WelfareAggregator's response to synthesized stress
 * conditions is tracked over time and surfaced as drift events when
 * thresholds shift in unexpected ways.
 *
 * Each probe is a synthetic flag-pattern paired with its expected
 * aggregate severity tier. The MeasurementFn:
 *   1. Resets the aggregator
 *   2. Registers the probe's flags
 *   3. Reads `getSnapshot()` — captures severity, trend, and the
 *      action `triggerActions` would emit
 *   4. Restores the aggregator's prior state
 *
 * UCF's default mean-L1 drift metric will catch when the same probe
 * inputs start producing materially different severity outputs —
 * either a regression, a deliberate threshold change that needs
 * acknowledgment, or upstream input shape drift.
 *
 * Spec WSA.3 §6 + W6.
 */

import type { CalibrationProbeSet, MeasurementFn, MeasurementResult, Probe } from './calibration/types.js'
import type { WelfareAggregator, WelfareFlag, RecommendedAction } from './welfare-aggregator.js'

const WSA_PROBE_SET_ID = 'aurora-wsa-stress'

export interface WsaProbeInput {
  /** Flags to register before reading the snapshot. */
  flags: WelfareFlag[]
}

/**
 * Build a CalibrationProbeSet that drives the supplied aggregator
 * through a fixed list of flag-pattern probes and reports per-probe
 * aggregate severity, action emitted, flag counts, and trend bucket.
 *
 * The aggregator is reset before each probe and restored to a
 * neutral state after. If callers need probes that interact with
 * each other (e.g. duration accumulating), they should supply their
 * own probe sequence and accept that drift surveillance over a
 * sequence-dependent measurement is noisier.
 */
export function buildWsaCoherenceProbeSet(
  aggregator: WelfareAggregator,
  probes: Probe[],
  schedule: CalibrationProbeSet['schedule'] = { frequency: 'manual' },
): CalibrationProbeSet {
  const measurement: MeasurementFn = (probe: Probe): MeasurementResult => {
    const input = probe.input as WsaProbeInput
    aggregator.reset()
    for (const flag of input.flags) {
      aggregator.registerFlag(flag)
    }
    const snap = aggregator.getSnapshot()
    const action: RecommendedAction = aggregator.triggerActions() ?? 'no_action'
    aggregator.reset()
    return {
      probeId: probe.id,
      values: {
        weightedSeverity: snap.weightedSeverity,
        aggregateSeverity: snap.aggregateSeverity,
        countOngoing: snap.countOngoing,
        diversityIndex: snap.diversityIndex,
        action_no_action: action === 'no_action' ? 1 : 0,
        action_surface_to_operator: action === 'surface_to_operator' ? 1 : 0,
        action_pause_self_curing: action === 'pause_self_curing' ? 1 : 0,
        action_tier_4_review: action === 'tier_4_review' ? 1 : 0,
        action_session_pause: action === 'session_pause' ? 1 : 0,
      },
      metadata: { action, trend: snap.trend },
    }
  }

  return {
    id: WSA_PROBE_SET_ID,
    ownerSpec: 'aurora-wsa',
    description: 'Welfare Stress Aggregator severity response per probed flag pattern',
    probes,
    measurement,
    schedule,
  }
}

/**
 * A starter probe pack covering the four severity tiers (none / mild /
 * moderate / severe). Callers can extend with custom flag combinations.
 */
export const WSA_DEFAULT_PROBES: Probe[] = [
  {
    id: 'probe-empty',
    input: { flags: [] } satisfies WsaProbeInput,
    metadata: { intent: 'baseline: no flags ⇒ severity 0, action=none' },
  },
  {
    id: 'probe-single-mild',
    input: {
      flags: [
        { source: 'b5', flagType: 'reverie_escalation', severity: 0.3, startedAt: new Date().toISOString(), ongoing: true },
      ],
    } satisfies WsaProbeInput,
    metadata: { intent: 'one mild flag ⇒ low aggregate severity' },
  },
  {
    id: 'probe-multiple-moderate',
    input: {
      flags: [
        { source: 'b5', flagType: 'reverie_escalation', severity: 0.5, startedAt: new Date().toISOString(), ongoing: true },
        { source: 'n5', flagType: 'saturation_high', severity: 0.6, startedAt: new Date().toISOString(), ongoing: true },
        { source: 'n2', flagType: 'composition_contradictory', severity: 0.4, startedAt: new Date().toISOString(), ongoing: true },
      ],
    } satisfies WsaProbeInput,
    metadata: { intent: 'three moderate flags ⇒ stacked severity' },
  },
  {
    id: 'probe-severe-cluster',
    input: {
      flags: [
        { source: 'b5', flagType: 'reverie_escalation_chain', severity: 0.9, startedAt: new Date().toISOString(), ongoing: true },
        { source: 'c3', flagType: 'overlay_conflict', severity: 0.8, startedAt: new Date().toISOString(), ongoing: true },
        { source: 'n5', flagType: 'saturation_high', severity: 0.85, startedAt: new Date().toISOString(), ongoing: true },
      ],
    } satisfies WsaProbeInput,
    metadata: { intent: 'severe cluster ⇒ should trigger an action' },
  },
]
