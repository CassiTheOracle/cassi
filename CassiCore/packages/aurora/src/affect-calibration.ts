/**
 * B2 calibration runner — turns a probe set into per-feature affect
 * signatures. Pure function over (probes, layers, gateKnn, opts);
 * makes no assumptions about how gateKnn is implemented (real vindex,
 * stub, mock).
 *
 * Algorithm (spec §4.3):
 *   1. For each probe at each layer, gateKnn(probe.tokenized, topK).
 *   2. Accumulate `feature.labels[probe.label] += hit.score` per hit.
 *   3. Track `feature.activations` = number of distinct probes that hit it.
 *   4. Drop features below `minActivations`.
 *   5. L2-normalize each surviving feature's label vector.
 */

import type { AffectLabel } from '../mnemic-field/types.js'
import type { FeatureAffectSignature } from './larql-provider.js'

/**
 * Minimal probe shape the calibrator depends on. Both v1 (`AffectProbe`)
 * and v2 (`AffectProbeV2`) satisfy this — keeps the calibration pipeline
 * decoupled from probe-set provenance metadata.
 */
export interface CalibrationProbe {
  id: string
  text: string
  label: AffectLabel
}

export interface CalibrationOptions {
  /** Knowledge layers to scan. Default: 14..27 (Gemma 3 4B canonical). */
  layers?: number[]
  /** Top-K hits per gateKnn call. Default 32. */
  topK?: number
  /** Minimum distinct probes that must hit a feature for it to be kept. Default 3. */
  minActivations?: number
  /** Optional callback fired after each probe completes (progress reporting). */
  onProbeProgress?: (i: number, total: number, probe: CalibrationProbe) => void
}

export interface CalibrationResult {
  /** Surviving features (above min-activations threshold). */
  signatures: FeatureAffectSignature[]
  /** Total feature/layer pairs touched at least once across all probes. */
  totalCandidates: number
  /** Pairs dropped for being below min-activations. */
  droppedBelowMinActivations: number
  /** Per-quadrant probe counts (sanity: are probe sets balanced?). */
  perLabelProbeCount: Partial<Record<AffectLabel, number>>
}

/**
 * Caller-supplied gate-KNN function. Adapter responsibility:
 *   - Tokenize probe text
 *   - Run vindex.vindexGateKnn at the requested layer
 *   - Return hits as `[{ featureIndex, score }, ...]`
 *
 * Returning [] for any probe just means that probe contributed
 * nothing at that layer; calibration handles it gracefully.
 */
export type ProbeGateKnnFn = (
  probe: CalibrationProbe,
  layer: number,
  topK: number,
) => Array<{ featureIndex: number; score: number }>

interface FeatureAccumulator {
  layer: number
  featureIndex: number
  /** label → cumulative score across probes */
  labelScores: Map<AffectLabel, number>
  /** distinct probe ids that hit this feature */
  hitProbeIds: Set<string>
}

const DEFAULT_LAYERS = [14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27]
const DEFAULT_TOP_K = 32
const DEFAULT_MIN_ACTIVATIONS = 3

export function calibrateAffectSignatures(
  probes: CalibrationProbe[],
  gateKnn: ProbeGateKnnFn,
  opts: CalibrationOptions = {},
): CalibrationResult {
  const layers = opts.layers ?? DEFAULT_LAYERS
  const topK = opts.topK ?? DEFAULT_TOP_K
  const minActivations = opts.minActivations ?? DEFAULT_MIN_ACTIVATIONS

  const acc = new Map<string, FeatureAccumulator>()
  const perLabel: Partial<Record<AffectLabel, number>> = {}

  for (let i = 0; i < probes.length; i++) {
    const probe = probes[i]
    perLabel[probe.label] = (perLabel[probe.label] ?? 0) + 1
    for (const layer of layers) {
      const hits = gateKnn(probe, layer, topK)
      for (const hit of hits) {
        const key = `${layer}:${hit.featureIndex}`
        let row = acc.get(key)
        if (!row) {
          row = {
            layer,
            featureIndex: hit.featureIndex,
            labelScores: new Map(),
            hitProbeIds: new Set(),
          }
          acc.set(key, row)
        }
        row.labelScores.set(probe.label, (row.labelScores.get(probe.label) ?? 0) + hit.score)
        row.hitProbeIds.add(probe.id)
      }
    }
    opts.onProbeProgress?.(i + 1, probes.length, probe)
  }

  const totalCandidates = acc.size
  let dropped = 0
  const signatures: FeatureAffectSignature[] = []
  for (const row of acc.values()) {
    if (row.hitProbeIds.size < minActivations) {
      dropped++
      continue
    }
    const labels: Partial<Record<AffectLabel, number>> = {}
    let mag2 = 0
    // First pass: divide by hit count to get per-label avg
    const denom = row.hitProbeIds.size
    for (const [label, sum] of row.labelScores) {
      const avg = sum / denom
      labels[label] = avg
      mag2 += avg * avg
    }
    const rawMag = Math.sqrt(mag2)
    if (rawMag === 0) {
      dropped++
      continue
    }
    // L2-normalize so signatures live on the unit sphere across labels
    for (const k of Object.keys(labels)) {
      const lk = k as AffectLabel
      labels[lk] = (labels[lk] ?? 0) / rawMag
    }
    signatures.push({
      layer: row.layer,
      featureIndex: row.featureIndex,
      labels,
      magnitude: 1.0,
    })
  }

  return {
    signatures,
    totalCandidates,
    droppedBelowMinActivations: dropped,
    perLabelProbeCount: perLabel,
  }
}
