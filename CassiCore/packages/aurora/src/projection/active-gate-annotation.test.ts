/**
 * A2.4 active-gate annotation rendering tests.
 */

import { describe, it, expect } from 'vitest'

import { renderActiveGateAnnotation } from './active-gate-annotation.js'
import type { GateContribution, VectorProjection } from '../types.js'

function contribution(opts: Partial<GateContribution> & { nodeId: string; label: string }): GateContribution {
  return {
    nodeId: opts.nodeId,
    label: opts.label,
    layers: opts.layers ?? [14],
    salience: opts.salience ?? 0.5,
    weight: opts.weight ?? 0.05,
  }
}

function projection(contributions: GateContribution[]): VectorProjection {
  return {
    perLayer: new Map(),
    contributions,
    metadata: {
      contributingNodes: contributions.map(c => c.nodeId),
      targetModelId: null,
      vindexId: null,
      composedAt: '2026-05-06T00:00:00Z',
    },
  }
}

describe('renderActiveGateAnnotation', () => {
  it('returns empty string for null projection', () => {
    expect(renderActiveGateAnnotation(null)).toBe('')
  })

  it('returns empty string when no contributions clear the weight floor', () => {
    const p = projection([contribution({ nodeId: 'a', label: 'a', weight: 0.001 })])
    expect(renderActiveGateAnnotation(p, { minWeight: 0.01 })).toBe('')
  })

  it('renders header + bullet per surfaced gate', () => {
    const p = projection([
      contribution({ nodeId: 'warmth', label: 'warmth', layers: [14, 15], weight: 0.08 }),
      contribution({ nodeId: 'rigor', label: 'rigor', layers: [20], weight: 0.05 }),
    ])
    const out = renderActiveGateAnnotation(p)
    expect(out).toContain('[Active steering — gate composition biasing residual]')
    expect(out).toContain('• warmth')
    expect(out).toContain('• rigor')
  })

  it('formats contiguous layers as L<lo>..L<hi>', () => {
    const p = projection([
      contribution({ nodeId: 'a', label: 'a', layers: [14, 15, 16, 17], weight: 0.05 }),
    ])
    expect(renderActiveGateAnnotation(p)).toContain('L14..L17')
  })

  it('formats non-contiguous layers as comma list', () => {
    const p = projection([
      contribution({ nodeId: 'a', label: 'a', layers: [14, 17, 20], weight: 0.05 }),
    ])
    expect(renderActiveGateAnnotation(p)).toContain('L14,L17,L20')
  })

  it('formats single layer as L<n>', () => {
    const p = projection([
      contribution({ nodeId: 'a', label: 'a', layers: [22], weight: 0.05 }),
    ])
    expect(renderActiveGateAnnotation(p)).toContain('L22')
  })

  it('includes weight as percent', () => {
    const p = projection([
      contribution({ nodeId: 'a', label: 'a', weight: 0.075 }),
    ])
    expect(renderActiveGateAnnotation(p)).toContain('w=7.5%')
  })

  it('honors maxGates and reports the skipped count', () => {
    const contribs: GateContribution[] = []
    for (let i = 0; i < 10; i++) {
      contribs.push(contribution({ nodeId: `n${i}`, label: `n${i}`, weight: 0.05 }))
    }
    const out = renderActiveGateAnnotation(projection(contribs), { maxGates: 3 })
    expect(out.split('\n').filter(l => l.includes('•'))).toHaveLength(3)
    expect(out).toContain('(+7 more gates below display threshold)')
  })

  it('does not append the skipped-count line when nothing was skipped', () => {
    const p = projection([
      contribution({ nodeId: 'a', label: 'a', weight: 0.05 }),
    ])
    expect(renderActiveGateAnnotation(p)).not.toContain('more gates')
  })
})
