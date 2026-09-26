import { describe, it, expect } from 'vitest'
import { parseThoughtCommands, ThoughtCommand } from '../src/types.js'

describe('parseThoughtCommands', () => {
  it('extracts a pin command with reason', () => {
    const text = 'Some response text <pin reason="load-bearing for B7 design">V4 Pro quant layout</pin> more text'
    const cmds = parseThoughtCommands(text)
    expect(cmds).toHaveLength(1)
    expect(cmds[0]).toEqual({
      type: 'pin',
      target: 'V4 Pro quant layout',
      reason: 'load-bearing for B7 design',
    })
  })

  it('extracts a recall command with query', () => {
    const text = '<recall query="gemini architecture decisions">need this back</recall>'
    const cmds = parseThoughtCommands(text)
    expect(cmds).toHaveLength(1)
    expect(cmds[0]).toEqual({
      type: 'recall',
      query: 'gemini architecture decisions',
      context: 'need this back',
    })
  })

  it('extracts a note for reverie', () => {
    const text = '<note for="reverie">this loop is intentional, not a bug</note>'
    const cmds = parseThoughtCommands(text)
    expect(cmds).toHaveLength(1)
    expect(cmds[0]).toEqual({
      type: 'note',
      recipient: 'reverie',
      message: 'this loop is intentional, not a bug',
    })
  })

  it('extracts a flag command', () => {
    const text = '<flag>critical: the scoring weights need rebalancing</flag>'
    const cmds = parseThoughtCommands(text)
    expect(cmds).toHaveLength(1)
    expect(cmds[0]).toEqual({
      type: 'flag',
      content: 'critical: the scoring weights need rebalancing',
    })
  })

  it('handles multiple commands in one message', () => {
    const text = `
      <pin reason="user directive">use React not Vue</pin>
      <note for="reverie">user prefers React ecosystem</note>
      <recall query="React patterns">find component examples</recall>
    `
    const cmds = parseThoughtCommands(text)
    expect(cmds).toHaveLength(3)
    expect(cmds[0].type).toBe('pin')
    expect(cmds[1].type).toBe('note')
    expect(cmds[2].type).toBe('recall')
  })

  it('returns empty array when no commands present', () => {
    const text = 'Regular assistant text with no thought commands.'
    const cmds = parseThoughtCommands(text)
    expect(cmds).toHaveLength(0)
  })

  it('handles empty tag content', () => {
    const text = '<pin reason="important"></pin>'
    const cmds = parseThoughtCommands(text)
    expect(cmds).toHaveLength(1)
    expect(cmds[0].target).toBe('')
  })

  it('handles missing reason attribute on pin', () => {
    const text = '<pin>V4 quant layout</pin>'
    const cmds = parseThoughtCommands(text)
    expect(cmds).toHaveLength(1)
    expect(cmds[0].reason).toBeUndefined()
  })
})
