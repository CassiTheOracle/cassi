/**
 * UCF default drift metric tests.
 */

import { describe, it, expect } from 'vitest'

import { meanL1DriftMetric, emptyDrift } from './drift.js'
import { classifyDrift, DRIFT_TIERS } from './types.js'

const r = (probeId: string, values: Record<string, number>) => ({ probeId, values })

describe('meanL1DriftMetric', () => {
  it('returns zero magnitude when results are identical', () => {
    const a = [r('p1', { x: 1, y: 2 }), r('p2', { x: 0.5, y: 0.5 })]
    const b = [r('p1', { x: 1, y: 2 }), r('p2', { x: 0.5, y: 0.5 })]
    const d = meanL1DriftMetric(a, b)
    expect(d.magnitude).toBe(0)
    expect(d.affected).toEqual([])
    expect(d.recommendation).toBe('no_action')
  })

  it('detects per-probe magnitude when values shift', () => {
    const a = [r('p1', { x: 0 }), r('p2', { x: 0 })]
    const b = [r('p1', { x: 0.5 }), r('p2', { x: 1.0 })]
    const d = meanL1DriftMetric(a, b)
    expect(d.magnitude).toBeGreaterThan(0)
    expect(d.perProbeMagnitude!.p2).toBeGreaterThan(d.perProbeMagnitude!.p1)
  })

  it('flags affected probes when probe magnitude >= 0.1', () => {
    const a = [r('p1', { x: 0 }), r('p2', { x: 0 })]
    const b = [r('p1', { x: 0.001 }), r('p2', { x: 5 })]
    const d = meanL1DriftMetric(a, b)
    expect(d.affected).toContain('p2')
    expect(d.affected).not.toContain('p1')
  })

  it('handles missing probe ids in current run gracefully', () => {
    const a = [r('p1', { x: 0 }), r('p2', { x: 0 })]
    const b = [r('p1', { x: 1 })]
    const d = meanL1DriftMetric(a, b)
    expect(d.perProbeMagnitude!.p1).toBeGreaterThan(0)
    expect(d.perProbeMagnitude!.p2).toBeUndefined()
  })

  it('returns zero magnitude when prior list is empty', () => {
    const d = meanL1DriftMetric([], [r('p1', { x: 1 })])
    expect(d.magnitude).toBe(0)
  })

  it('union-merges keys across runs (missing keys treated as 0)', () => {
    const a = [r('p1', { x: 1 })]
    const b = [r('p1', { x: 1, y: 2 })]
    const d = meanL1DriftMetric(a, b)
    expect(d.perProbeMagnitude!.p1).toBeGreaterThan(0)
  })
})

describe('classifyDrift', () => {
  it('maps magnitude tiers to recommendations', () => {
    expect(classifyDrift(0)).toBe('no_action')
    expect(classifyDrift(DRIFT_TIERS.low - 0.001)).toBe('no_action')
    expect(classifyDrift(DRIFT_TIERS.low)).toBe('investigate')
    expect(classifyDrift(DRIFT_TIERS.moderate)).toBe('recalibrate')
    expect(classifyDrift(DRIFT_TIERS.high)).toBe('serious_drift_review')
    expect(classifyDrift(0.99)).toBe('serious_drift_review')
  })
})

describe('emptyDrift', () => {
  it('represents the no-prior baseline correctly', () => {
    const d = emptyDrift()
    expect(d.magnitude).toBe(0)
    expect(d.affected).toEqual([])
    expect(d.recommendation).toBe('no_action')
  })
})
