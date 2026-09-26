/**
 * Default drift metric — mean L1 deviation across numeric measurement keys
 * keyed by probeId. Per-spec adapters can supply their own DriftMetricFn for
 * cases where L1 isn't the right notion of "different" (e.g., distribution
 * comparison for retrieval ranks would want a Spearman correlation; vector
 * projection magnitude wants per-layer cosine).
 *
 * Output magnitude is bounded to [0, 1] by tanh-normalization.
 */

import type {
  DriftMetricFn,
  DriftReport,
  MeasurementResult,
} from './types.js'
import { classifyDrift } from './types.js'

/** Per-probe per-key L1 average → tanh-normalized magnitude. */
export const meanL1DriftMetric: DriftMetricFn = (prior, current) => {
  const priorById = new Map(prior.map(r => [r.probeId, r]))
  const perProbeMagnitude: Record<string, number> = {}
  const affected: string[] = []
  let totalMagnitude = 0
  let probeCount = 0

  for (const cur of current) {
    const before = priorById.get(cur.probeId)
    if (!before) continue
    const keys = unionKeys(before.values, cur.values)
    if (keys.length === 0) continue
    let sum = 0
    for (const k of keys) {
      const a = before.values[k] ?? 0
      const b = cur.values[k] ?? 0
      sum += Math.abs(a - b)
    }
    const probeMag = Math.tanh(sum / keys.length)
    perProbeMagnitude[cur.probeId] = probeMag
    totalMagnitude += probeMag
    probeCount += 1
    if (probeMag >= 0.1) affected.push(cur.probeId)
  }

  const magnitude = probeCount === 0 ? 0 : totalMagnitude / probeCount
  return {
    magnitude,
    affected,
    recommendation: classifyDrift(magnitude),
    perProbeMagnitude,
  }
}

function unionKeys(a: Record<string, number>, b: Record<string, number>): string[] {
  const seen = new Set<string>()
  for (const k of Object.keys(a)) seen.add(k)
  for (const k of Object.keys(b)) seen.add(k)
  return [...seen]
}

/** Empty drift (no prior run available). */
export function emptyDrift(): DriftReport {
  return { magnitude: 0, affected: [], recommendation: 'no_action', perProbeMagnitude: {} }
}
