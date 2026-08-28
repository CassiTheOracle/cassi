/**
 * B1.3 rule-evaluator tests — match policy + edge-trigger logic.
 */

import { describe, it, expect } from 'vitest'

import { ruleMatchesActiveConcepts, evaluateInvocationRules } from './rule-evaluator.js'
import type { InvocationRule } from './types.js'

function rule(id: string, keywords: string[], composition = 'unused'): InvocationRule {
  return { id, topicKeywords: keywords, composition, updatedAt: '2026-05-06T00:00:00Z' }
}

describe('ruleMatchesActiveConcepts', () => {
  it('returns false when topicKeywords is empty', () => {
    expect(ruleMatchesActiveConcepts(rule('r1', []), ['feedback'])).toBe(false)
  })

  it('returns false when activeConcepts is empty', () => {
    expect(ruleMatchesActiveConcepts(rule('r1', ['feedback']), [])).toBe(false)
  })

  it('matches case-insensitive substring', () => {
    expect(ruleMatchesActiveConcepts(rule('r1', ['REVIEW']), ['code review tonight'])).toBe(true)
    expect(ruleMatchesActiveConcepts(rule('r1', ['review']), ['CODE REVIEW'])).toBe(true)
  })

  it('matches if ANY keyword fires (OR semantics)', () => {
    expect(ruleMatchesActiveConcepts(rule('r1', ['x', 'feedback']), ['session feedback'])).toBe(true)
  })

  it('returns false when no keyword matches', () => {
    expect(ruleMatchesActiveConcepts(rule('r1', ['rigor', 'critique']), ['feedback', 'review'])).toBe(false)
  })

  it('skips empty keyword strings', () => {
    expect(ruleMatchesActiveConcepts(rule('r1', ['', 'feedback']), ['feedback'])).toBe(true)
    expect(ruleMatchesActiveConcepts(rule('r1', ['']), ['anything'])).toBe(false)
  })
})

describe('evaluateInvocationRules — edge-triggered firing', () => {
  it('fires on rising edge (false→true)', () => {
    const prior = new Set<string>()
    const result = evaluateInvocationRules(
      [rule('r1', ['feedback'])],
      ['feedback', 'session'],
      prior,
    )
    expect(result.fired).toEqual(['r1'])
    expect(result.unfired).toEqual([])
    expect(result.stillSatisfied).toEqual([])
    expect(prior.has('r1')).toBe(true)
  })

  it('does not re-fire while trigger remains satisfied', () => {
    const prior = new Set<string>()
    evaluateInvocationRules([rule('r1', ['feedback'])], ['feedback'], prior)
    const result = evaluateInvocationRules([rule('r1', ['feedback'])], ['feedback'], prior)
    expect(result.fired).toEqual([])
    expect(result.stillSatisfied).toEqual(['r1'])
  })

  it('reports falling edge in `unfired`', () => {
    const prior = new Set<string>()
    evaluateInvocationRules([rule('r1', ['feedback'])], ['feedback'], prior)
    const result = evaluateInvocationRules([rule('r1', ['feedback'])], ['rigor'], prior)
    expect(result.fired).toEqual([])
    expect(result.unfired).toEqual(['r1'])
    expect(prior.has('r1')).toBe(false)
  })

  it('handles multiple rules independently', () => {
    const prior = new Set<string>()
    const result = evaluateInvocationRules(
      [
        rule('r1', ['feedback']),
        rule('r2', ['rigor']),
        rule('r3', ['unrelated']),
      ],
      ['feedback', 'rigor'],
      prior,
    )
    expect(result.fired.sort()).toEqual(['r1', 'r2'])
    expect(result.unfired).toEqual([])
  })

  it('rising and falling edges in one tick', () => {
    const prior = new Set<string>(['r1'])
    const result = evaluateInvocationRules(
      [rule('r1', ['feedback']), rule('r2', ['rigor'])],
      ['rigor'], // r1 was satisfied, now isn't; r2 is newly satisfied
      prior,
    )
    expect(result.unfired).toEqual(['r1'])
    expect(result.fired).toEqual(['r2'])
  })

  it('mutates previouslySatisfied to reflect post-tick state', () => {
    const prior = new Set<string>()
    evaluateInvocationRules(
      [rule('r1', ['feedback']), rule('r2', ['rigor'])],
      ['feedback'],
      prior,
    )
    expect([...prior]).toEqual(['r1'])
    evaluateInvocationRules(
      [rule('r1', ['feedback']), rule('r2', ['rigor'])],
      ['rigor'],
      prior,
    )
    expect([...prior]).toEqual(['r2'])
  })
})
