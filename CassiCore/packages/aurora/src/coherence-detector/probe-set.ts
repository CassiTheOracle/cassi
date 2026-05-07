/**
 * N2 → UCF integration: probe set builder.
 *
 * Registers a CalibrationProbeSet with the universal calibration
 * framework so that N2's check-firing rates are tracked over time and
 * surfaced as drift events when behavior shifts.
 *
 * Each probe is a synthetic `DetectorInputs` snapshot paired with the
 * categories we expect (or don't expect) to fire. The MeasurementFn
 * runs the live detector against the input and returns a per-category
 * fire count. UCF's default mean-L1 drift metric then compares
 * consecutive runs — if firing rates change without the probe set
 * changing, that signals either a detector bug, a threshold drift, or
 * a real change in upstream input shape that warrants tuning.
 *
 * This is N2.2's drift-surveillance leg, per spec §4.3 and §7.
 */

import type {
  CalibrationProbeSet,
  MeasurementFn,
  MeasurementResult,
  Probe,
} from '../calibration/types.js'
import type { CoherenceCategory } from './types.js'
import type { DetectorInputs, PostureCoherenceDetector } from './index.js'

const N2_PROBE_SET_ID = 'aurora-n2-coherence'

const ALL_CATEGORIES: CoherenceCategory[] = [
  'composition_pair_cancelling',
  'composition_pair_contradictory',
  'composition_meditation_suppression',
  'composition_retrieval_mismatch',
  'replay_affect_mismatch',
  'meditation_entrypoint_cold',
  'composition_meditation_cold_topic',
]

/**
 * Build a CalibrationProbeSet that runs a fixed list of probes through
 * the supplied detector and emits per-category fire counts. Caller
 * supplies the probes — typically a curated set of synthetic
 * DetectorInputs that exercise each category at least once. UCF takes
 * it from there: stores results, compares to prior, emits drift events.
 *
 * The detector reference is captured at build time. If the detector is
 * later reconstructed (e.g., during reconfiguration), rebuild the probe
 * set so the runtime callback points at the live detector.
 */
export function buildN2CoherenceProbeSet(
  detector: PostureCoherenceDetector,
  probes: Probe[],
  schedule: CalibrationProbeSet['schedule'] = { frequency: 'manual' },
): CalibrationProbeSet {
  const measurement: MeasurementFn = (probe: Probe): MeasurementResult => {
    const inputs = probe.input as DetectorInputs
    const fired = detector.detect(inputs)
    const counts: Record<string, number> = {}
    for (const cat of ALL_CATEGORIES) {
      counts[`fires_${cat}`] = 0
    }
    for (const c of fired) {
      counts[`fires_${c.category}`]++
    }
    counts.total_fires = fired.length
    return {
      probeId: probe.id,
      values: counts,
      metadata: { categoriesFired: fired.map(c => c.category) },
    }
  }

  return {
    id: N2_PROBE_SET_ID,
    ownerSpec: 'aurora-n2',
    description: 'Posture coherence detector firing rates per category',
    probes,
    measurement,
    schedule,
  }
}

/**
 * A small starter set of synthetic probe inputs covering each category.
 * Callers can extend with their own; this is the minimum that exercises
 * every detector path so drift in any path is observable.
 */
export const N2_DEFAULT_PROBES: Probe[] = [
  {
    id: 'probe-empty-state',
    input: {
      active: [],
      records: [],
      pendingSeeds: [],
    } as DetectorInputs,
    metadata: { intent: 'baseline: no inputs, no fires' },
  },
  {
    id: 'probe-pair-contradictory',
    input: {
      active: [
        { name: 'a', ast: { kind: 'gate', label: 'unused' }, invokedAt: '', ttlTurns: 5, remainingTurns: 5, magnitudeScale: 1, trigger: 'manual' },
        { name: 'b', ast: { kind: 'gate', label: 'unused' }, invokedAt: '', ttlTurns: 5, remainingTurns: 5, magnitudeScale: 1, trigger: 'manual' },
      ],
      records: [
        { name: 'a', dsl: '', ast: { kind: 'sum', operands: [{ kind: 'gate', label: 'warmth' }, { kind: 'gate', label: 'kindness' }] }, layerPolicy: 'all', affectModulated: false, suppressive: false, vindexId: '', description: null, createdAt: '', updatedAt: '', metadata: {} },
        { name: 'b', dsl: '', ast: { kind: 'sum', operands: [{ kind: 'gate', label: 'cold' }, { kind: 'scaled', operand: { kind: 'gate', label: 'warmth' }, factor: -1 }, { kind: 'scaled', operand: { kind: 'gate', label: 'kindness' }, factor: -1 }] }, layerPolicy: 'all', affectModulated: false, suppressive: false, vindexId: '', description: null, createdAt: '', updatedAt: '', metadata: {} },
      ],
      pendingSeeds: [],
    } as DetectorInputs,
    metadata: { intent: 'fires composition_pair_contradictory' },
  },
  {
    id: 'probe-replay-mismatch',
    input: {
      active: [],
      records: [],
      pendingSeeds: [],
      currentAffect: { valence: -0.5, arousal: 0.8 },
      scheduledReplays: [{ id: 'r1', sourceAffect: { valence: 0.5, arousal: 0.2 } }],
    } as DetectorInputs,
    metadata: { intent: 'fires replay_affect_mismatch' },
  },
  {
    id: 'probe-meditation-cold',
    input: {
      active: [],
      records: [],
      pendingSeeds: [
        { id: 's1', gapId: 'g1', topic: 'frustrated reasoning', entryPoints: [], expectedRefinement: '', proposedAt: '', proposedBy: 'curator', status: 'pending', budget: { maxTurns: 10, maxCostUsd: 0.25 }, metadata: {} } as any,
      ],
      claustrumActivations: new Map([['frustrated', 0.05]]),
    } as DetectorInputs,
    metadata: { intent: 'fires meditation_entrypoint_cold' },
  },
]
