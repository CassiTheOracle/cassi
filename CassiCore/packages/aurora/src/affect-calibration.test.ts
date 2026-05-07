/**
 * Tests for affect-calibration — drives `calibrateAffectSignatures` with
 * a stubbed gateKnn so we can verify accumulation, normalization, and
 * the min-activations cutoff without a real vindex.
 */

import { describe, it, expect } from 'vitest'

import { calibrateAffectSignatures, type ProbeGateKnnFn } from './affect-calibration.js'
import type { AffectProbe } from './affect-probes/v1.js'

function probe(id: string, label: AffectProbe['label'], text = id): AffectProbe {
  return { id, label, text }
}

describe('calibrateAffectSignatures', () => {
  it('builds signatures from probe activations and L2-normalizes', () => {
    const probes: AffectProbe[] = [
      probe('e1', 'excited'),
      probe('e2', 'excited'),
      probe('e3', 'excited'),
    ]
    const gateKnn: ProbeGateKnnFn = (_p, layer, _k) => {
      // Feature 1 at every layer for every probe — strong "excited" signal
      return layer === 20 ? [{ featureIndex: 1, score: 0.5 }] : []
    }
    const result = calibrateAffectSignatures(probes, gateKnn, {
      layers: [20],
      topK: 8,
      minActivations: 3,
    })
    expect(result.signatures).toHaveLength(1)
    const sig = result.signatures[0]
    expect(sig.layer).toBe(20)
    expect(sig.featureIndex).toBe(1)
    // L2-normalized: only one label, so its weight should be 1.0
    expect(sig.labels.excited).toBeCloseTo(1.0, 6)
    expect(sig.magnitude).toBe(1.0)
  })

  it('drops features below min-activations', () => {
    const probes: AffectProbe[] = [
      probe('e1', 'excited'),
      probe('e2', 'excited'),
      probe('e3', 'excited'),
    ]
    // Feature 1 hit by all 3 probes; feature 2 hit by only 1.
    const gateKnn: ProbeGateKnnFn = (p, _layer, _k) => {
      const hits: Array<{ featureIndex: number; score: number }> = [{ featureIndex: 1, score: 0.5 }]
      if (p.id === 'e1') hits.push({ featureIndex: 2, score: 0.5 })
      return hits
    }
    const result = calibrateAffectSignatures(probes, gateKnn, {
      layers: [20],
      minActivations: 2,
    })
    expect(result.signatures.find(s => s.featureIndex === 1)).toBeDefined()
    expect(result.signatures.find(s => s.featureIndex === 2)).toBeUndefined()
    expect(result.droppedBelowMinActivations).toBe(1)
  })

  it('mixes labels when same feature hits across multiple quadrants', () => {
    const probes: AffectProbe[] = [
      probe('e1', 'excited'),
      probe('e2', 'excited'),
      probe('m1', 'melancholy'),
      probe('m2', 'melancholy'),
    ]
    // Feature 1 hit by all 4 probes
    const gateKnn: ProbeGateKnnFn = (_p, _layer, _k) => [{ featureIndex: 1, score: 0.5 }]
    const result = calibrateAffectSignatures(probes, gateKnn, {
      layers: [20],
      minActivations: 3,
    })
    expect(result.signatures).toHaveLength(1)
    const sig = result.signatures[0]
    // Both labels present after normalization, equal weight (sqrt(2)/2 each)
    expect(sig.labels.excited).toBeCloseTo(Math.SQRT1_2, 4)
    expect(sig.labels.melancholy).toBeCloseTo(Math.SQRT1_2, 4)
  })

  it('reports per-label probe counts (balance check input)', () => {
    const probes: AffectProbe[] = [
      probe('e1', 'excited'),
      probe('e2', 'excited'),
      probe('c1', 'calm'),
      probe('m1', 'melancholy'),
    ]
    const gateKnn: ProbeGateKnnFn = () => []
    const result = calibrateAffectSignatures(probes, gateKnn, { layers: [20] })
    expect(result.perLabelProbeCount.excited).toBe(2)
    expect(result.perLabelProbeCount.calm).toBe(1)
    expect(result.perLabelProbeCount.melancholy).toBe(1)
  })

  it('counts totalCandidates as the number of distinct (layer, feature) hit at least once', () => {
    const probes: AffectProbe[] = [
      probe('e1', 'excited'),
      probe('e2', 'excited'),
      probe('e3', 'excited'),
    ]
    const gateKnn: ProbeGateKnnFn = (_p, layer, _k) => [
      { featureIndex: 1, score: 0.5 },
      { featureIndex: 2, score: 0.4 },
    ]
    const result = calibrateAffectSignatures(probes, gateKnn, {
      layers: [20, 22],
      minActivations: 3,
    })
    expect(result.totalCandidates).toBe(4) // (20,1) (20,2) (22,1) (22,2)
    expect(result.signatures).toHaveLength(4)
  })

  it('fires onProbeProgress callback once per probe', () => {
    const probes: AffectProbe[] = [
      probe('e1', 'excited'),
      probe('e2', 'excited'),
    ]
    const calls: number[] = []
    calibrateAffectSignatures(probes, () => [], {
      layers: [20],
      onProbeProgress: (i, total) => {
        calls.push(i)
        expect(total).toBe(2)
      },
    })
    expect(calls).toEqual([1, 2])
  })

  it('handles empty gateKnn results gracefully', () => {
    const probes: AffectProbe[] = [probe('e1', 'excited')]
    const result = calibrateAffectSignatures(probes, () => [], { layers: [20] })
    expect(result.signatures).toHaveLength(0)
    expect(result.totalCandidates).toBe(0)
  })
})
