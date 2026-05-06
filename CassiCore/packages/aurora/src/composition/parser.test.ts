/**
 * B1 parser tests — grammar coverage and welfare suppressive detection.
 */

import { describe, it, expect } from 'vitest'

import { parseComposition, detectSuppressive, CompositionParseError } from './parser.js'
import type { CompositionAst } from './types.js'

describe('parseComposition', () => {
  it('parses a simple sum definition', () => {
    const r = parseComposition('calm_focus = gate("calm") + gate("focus") - gate("reactivity")')
    expect(r.name).toBe('calm_focus')
    expect(r.ast.kind).toBe('sum')
    if (r.ast.kind !== 'sum') return
    expect(r.ast.operands).toHaveLength(3)
    expect(r.ast.operands[0]).toEqual({ kind: 'gate', label: 'calm' })
    expect(r.ast.operands[2]).toEqual({
      kind: 'scaled',
      operand: { kind: 'gate', label: 'reactivity' },
      factor: -1,
    })
  })

  it('parses scalar weighting', () => {
    const r = parseComposition('mix = gate("playfulness") * 0.4 + gate("craft")')
    expect(r.ast.kind).toBe('sum')
    if (r.ast.kind !== 'sum') return
    expect(r.ast.operands[0]).toEqual({
      kind: 'scaled',
      operand: { kind: 'gate', label: 'playfulness' },
      factor: 0.4,
    })
  })

  it('parses parenthesized expressions', () => {
    const r = parseComposition('p = (gate("a") + gate("b")) * 2')
    expect(r.ast).toEqual({
      kind: 'scaled',
      operand: {
        kind: 'sum',
        operands: [
          { kind: 'gate', label: 'a' },
          { kind: 'gate', label: 'b' },
        ],
      },
      factor: 2,
    })
  })

  it('parses unary minus on a primary', () => {
    const r = parseComposition('p = -gate("a")')
    expect(r.ast).toEqual({
      kind: 'scaled',
      operand: { kind: 'gate', label: 'a' },
      factor: -1,
    })
  })

  it('parses layer-restricted with L<n>..L<m>', () => {
    const r = parseComposition('deep = gate("warmth") @ L20..L27')
    expect(r.ast.kind).toBe('layered')
    if (r.ast.kind !== 'layered') return
    expect(r.ast.layers).toEqual({ range: [20, 27] })
    expect(r.layerPolicy).toBe('L20..L27')
  })

  it('parses layer-restricted with all', () => {
    const r = parseComposition('p = gate("a") @ all')
    if (r.ast.kind !== 'layered') throw new Error('expected layered')
    expect(r.ast.layers).toEqual({ all: true })
  })

  it('parses references and live selectors', () => {
    const r = parseComposition('combo = warmth + live("active_topic")')
    if (r.ast.kind !== 'sum') throw new Error('expected sum')
    expect(r.ast.operands).toEqual([
      { kind: 'reference', name: 'warmth' },
      { kind: 'live', selector: 'active_topic' },
    ])
  })

  it('parses affect() primaries with a known label', () => {
    const r = parseComposition('a = affect("calm")')
    expect(r.ast).toEqual({ kind: 'affect', label: 'calm' })
  })

  it('rejects unknown affect labels', () => {
    expect(() => parseComposition('a = affect("totally_zen")')).toThrow(CompositionParseError)
  })

  it('accepts a bare expression (no name)', () => {
    const r = parseComposition('gate("a") + gate("b")')
    expect(r.name).toBeNull()
    expect(r.ast.kind).toBe('sum')
  })

  it('rejects garbage trailing tokens', () => {
    expect(() => parseComposition('a = gate("x") foo')).toThrow(CompositionParseError)
  })

  it('rejects malformed function call (missing string)', () => {
    expect(() => parseComposition('a = gate(5)')).toThrow(CompositionParseError)
  })

  it('treats # as a line comment', () => {
    const r = parseComposition('# header\na = gate("x")  # trailing\n')
    expect(r.name).toBe('a')
  })

  it('accepts unicode minus sign and multiplication sign', () => {
    const r = parseComposition('p = gate("a") − gate("b") × 2')
    if (r.ast.kind !== 'sum') throw new Error('expected sum')
    expect((r.ast.operands[1] as Extract<CompositionAst, { kind: 'scaled' }>).factor).toBe(-2)
  })
})

describe('detectSuppressive', () => {
  it('flags subtraction of a suppressive affect label', () => {
    const r = parseComposition('p = gate("calm") - affect("frustrated")')
    expect(detectSuppressive(r.ast)).toBe(true)
  })

  it('flags subtraction via gate("frustrated")', () => {
    const r = parseComposition('p = gate("calm") - gate("frustrated")')
    expect(detectSuppressive(r.ast)).toBe(true)
  })

  it('does not flag addition of a suppressive label', () => {
    const r = parseComposition('p = affect("frustrated") + gate("calm")')
    expect(detectSuppressive(r.ast)).toBe(false)
  })

  it('does not flag subtraction of a non-suppressive label', () => {
    const r = parseComposition('p = gate("warmth") - gate("haste")')
    expect(detectSuppressive(r.ast)).toBe(false)
  })

  it('flags suppression nested under a scalar negation', () => {
    const r = parseComposition('p = -gate("uneasy")')
    expect(detectSuppressive(r.ast)).toBe(true)
  })

  it('does not flag double-negation (positive net sign)', () => {
    const r = parseComposition('p = gate("a") - (-gate("uneasy"))')
    expect(detectSuppressive(r.ast)).toBe(false)
  })
})
