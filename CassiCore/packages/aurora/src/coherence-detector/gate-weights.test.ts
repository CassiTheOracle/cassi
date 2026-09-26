/**
 * Gate-weight folding tests — the math layer beneath the pairwise coherence
 * detectors. We verify that AST → signed gate map produces the right weights
 * after scalar multipliers, sums, layered, and modulated wrappers fold in.
 */

import { describe, it, expect } from 'vitest'

import { gateWeights, l1Norm, cancellationOverlap, suppressedLabels } from './gate-weights.js'
import { parseComposition } from '../composition/parser.js'

function weightsOf(dsl: string) {
  const r = parseComposition(dsl)
  return gateWeights(r.ast)
}

describe('gateWeights', () => {
  it('folds a simple sum into per-label weights', () => {
    const w = weightsOf('p = gate("warmth") + gate("rigor") - gate("hedging")')
    expect(w.get('warmth')).toBe(1)
    expect(w.get('rigor')).toBe(1)
    expect(w.get('hedging')).toBe(-1)
  })

  it('applies scalar multipliers', () => {
    const w = weightsOf('p = gate("a") * 0.5 + gate("b") * 2 - gate("c")')
    expect(w.get('a')).toBe(0.5)
    expect(w.get('b')).toBe(2)
    expect(w.get('c')).toBe(-1)
  })

  it('combines repeats of the same gate label', () => {
    const w = weightsOf('p = gate("x") + gate("x") - gate("x") * 0.5')
    expect(w.get('x')).toBeCloseTo(1.5)
  })

  it('passes through layered, modulated, and scaledModulated wrappers', () => {
    const w1 = weightsOf('p = gate("a") @ L20..L27')
    expect(w1.get('a')).toBe(1)
    const w2 = weightsOf('p = gate("a") | when arousal < 0.4')
    expect(w2.get('a')).toBe(1)
    const w3 = weightsOf('p = gate("a") | scaled_by(1 - arousal)')
    expect(w3.get('a')).toBe(1)
  })

  it('skips reference and live nodes (cannot resolve without store)', () => {
    const w = weightsOf('p = gate("a") + warmth + live("topic")')
    expect(w.get('a')).toBe(1)
    expect(w.has('warmth')).toBe(false)
    expect(w.has('topic')).toBe(false)
  })
})

describe('l1Norm', () => {
  it('sums absolute weights', () => {
    const w = weightsOf('p = gate("a") + gate("b") - gate("c") * 0.5')
    expect(l1Norm(w)).toBeCloseTo(2.5)
  })
})

describe('cancellationOverlap', () => {
  it('finds opposite-sign overlap between two compositions', () => {
    const a = weightsOf('a = gate("warmth") + gate("rigor") - gate("haste")')
    const b = weightsOf('b = gate("haste") - gate("warmth")')
    const r = cancellationOverlap(a, b)
    expect(r.conflictingGates.sort()).toEqual(['haste', 'warmth'])
    expect(r.overlap).toBeCloseTo(2)
  })

  it('returns zero overlap when signs agree', () => {
    const a = weightsOf('a = gate("x") + gate("y")')
    const b = weightsOf('b = gate("x") + gate("z")')
    expect(cancellationOverlap(a, b)).toEqual({ overlap: 0, conflictingGates: [] })
  })

  it('uses min magnitude when weights differ', () => {
    const a = weightsOf('a = gate("x") * 2')
    const b = weightsOf('b = gate("x") * -0.5')
    const r = cancellationOverlap(a, b)
    expect(r.conflictingGates).toEqual(['x'])
    expect(r.overlap).toBe(0.5)
  })
})

describe('suppressedLabels', () => {
  it('returns labels with negative net weight', () => {
    const r = parseComposition('p = gate("calm") - affect("frustrated")')
    const sup = suppressedLabels(r.ast)
    expect(sup.has('frustrated')).toBe(true)
    expect(sup.has('calm')).toBe(false)
  })

  it('handles double-negation correctly (positive net = not suppressed)', () => {
    const r = parseComposition('p = gate("a") - (-gate("uneasy"))')
    expect(suppressedLabels(r.ast).has('uneasy')).toBe(false)
  })
})
