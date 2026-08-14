/**
 * B1.2 predicate + expression evaluator tests.
 *
 * Predicates: comparison ops over valence/arousal, label equality,
 * and/or composition. Expressions: linear arithmetic over affect dims.
 */

import { describe, it, expect } from 'vitest'

import { evaluatePredicate, evaluateExpr, evaluateStrength } from './predicate.js'
import { parseComposition } from './parser.js'
import type { Affect } from '../../mnemic-field/types.js'
import type { CompositionAst } from './types.js'

function predOf(dsl: string) {
  const r = parseComposition(dsl)
  if (r.ast.kind !== 'modulated') throw new Error('expected modulated AST')
  return r.ast.predicate
}

function exprOf(dsl: string) {
  const r = parseComposition(dsl)
  if (r.ast.kind !== 'scaledModulated') throw new Error('expected scaledModulated AST')
  return r.ast.expression
}

describe('evaluatePredicate', () => {
  const calm: Affect = { valence: 0.3, arousal: 0.2 }
  const frantic: Affect = { valence: -0.4, arousal: 0.85 }

  it('arousal < threshold', () => {
    const p = predOf('p = gate("x") | when arousal < 0.4')
    expect(evaluatePredicate(p, calm)).toBe(true)
    expect(evaluatePredicate(p, frantic)).toBe(false)
  })

  it('valence > threshold', () => {
    const p = predOf('p = gate("x") | when valence > 0')
    expect(evaluatePredicate(p, calm)).toBe(true)
    expect(evaluatePredicate(p, frantic)).toBe(false)
  })

  it('approximate (~) op uses tolerance band', () => {
    const p = predOf('p = gate("x") | when arousal ~ 0.2')
    expect(evaluatePredicate(p, { valence: 0, arousal: 0.2 })).toBe(true)
    expect(evaluatePredicate(p, { valence: 0, arousal: 0.25 })).toBe(true) // within 0.1
    expect(evaluatePredicate(p, { valence: 0, arousal: 0.4 })).toBe(false) // outside 0.1
  })

  it('label equality requires the resolved label argument', () => {
    const p = predOf('p = gate("x") | when label == "calm"')
    expect(evaluatePredicate(p, calm, 'calm')).toBe(true)
    expect(evaluatePredicate(p, calm, 'frustrated')).toBe(false)
    expect(evaluatePredicate(p, calm)).toBe(false) // missing label arg
  })

  it('and combines comparisons (both must hold)', () => {
    const p = predOf('p = gate("x") | when arousal < 0.4 and valence > 0')
    expect(evaluatePredicate(p, calm)).toBe(true)
    expect(evaluatePredicate(p, { valence: -0.1, arousal: 0.2 })).toBe(false)
    expect(evaluatePredicate(p, frantic)).toBe(false)
  })

  it('or combines comparisons (either may hold)', () => {
    const p = predOf('p = gate("x") | when arousal > 0.8 or valence < -0.3')
    expect(evaluatePredicate(p, frantic)).toBe(true)
    expect(evaluatePredicate(p, calm)).toBe(false)
    expect(evaluatePredicate(p, { valence: -0.5, arousal: 0.3 })).toBe(true)
  })

  it('parenthesized predicates compose', () => {
    const p = predOf('p = gate("x") | when (arousal < 0.4 or valence > 0.5) and label == "calm"')
    expect(evaluatePredicate(p, { valence: 0.3, arousal: 0.2 }, 'calm')).toBe(true)
    expect(evaluatePredicate(p, { valence: 0.3, arousal: 0.2 }, 'engaged')).toBe(false)
  })
})

describe('evaluateExpr / evaluateStrength', () => {
  const a: Affect = { valence: 0.6, arousal: 0.3 }

  it('reads valence and arousal as variables', () => {
    expect(evaluateExpr({ kind: 'var', name: 'valence' }, a)).toBe(0.6)
    expect(evaluateExpr({ kind: 'var', name: 'arousal' }, a)).toBe(0.3)
  })

  it('1 - arousal evaluates correctly', () => {
    const e = exprOf('p = gate("x") | scaled_by(1 - arousal)')
    expect(evaluateExpr(e, a)).toBeCloseTo(0.7)
  })

  it('valence + arousal evaluates correctly', () => {
    const e = exprOf('p = gate("x") | scaled_by(valence + arousal)')
    expect(evaluateExpr(e, a)).toBeCloseTo(0.9)
  })

  it('respects parens', () => {
    const e = exprOf('p = gate("x") | scaled_by((1 - arousal) - valence)')
    expect(evaluateExpr(e, a)).toBeCloseTo(0.1)
  })

  it('clamps strength to [0, 1]', () => {
    const e = exprOf('p = gate("x") | scaled_by(2 - arousal)')
    expect(evaluateStrength(e, a)).toBe(1) // clamped down from 1.7
    const e2 = exprOf('p = gate("x") | scaled_by(arousal - 1)')
    expect(evaluateStrength(e2, a)).toBe(0) // clamped up from -0.7
  })
})

describe('parser produces correct modulation AST kinds', () => {
  it('| when produces a modulated AST', () => {
    const r = parseComposition('p = gate("x") | when arousal < 0.5')
    expect(r.ast.kind).toBe('modulated')
  })

  it('| scaled_by produces a scaledModulated AST', () => {
    const r = parseComposition('p = gate("x") | scaled_by(1 - arousal)')
    expect(r.ast.kind).toBe('scaledModulated')
  })

  it('| modulation wraps any prior @ layer', () => {
    const r = parseComposition('p = gate("x") @ L20..L27 | when arousal < 0.5')
    expect(r.ast.kind).toBe('modulated')
    if (r.ast.kind !== 'modulated') return
    expect(r.ast.operand.kind).toBe('layered')
  })

  it('rejects unknown pipe keyword', () => {
    expect(() => parseComposition('p = gate("x") | confused arousal < 0.5')).toThrow()
  })
})
