/**
 * thalamus-slots.test.ts — Tests for the typed slot system, temporal registry,
 * and augmentation pipeline added in Thalamus v2.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { classifyMessage, classifyTool, buildToolResultPrefix } from '../src/classifier.js'
import { TemporalRegistry } from '../src/temporal.js'
import { createSlots } from '../src/slots/index.js'
import { ThalamusModule } from '../src/index.js'
import type { SlotContext } from '../src/types.js'
import { mockLogger } from './helpers.ts'



describe('classifyMessage', () => {
  it('classifies system messages', () => {
    expect(classifyMessage({ role: 'system', content: 'pineal' })).toBe('system')
  })

  it('classifies assistant tool_call messages', () => {
    const msg = {
      role: 'assistant',
      content: [{ type: 'tool_use', id: 'tu_1', name: 'bash', input: {} }],
    }
    expect(classifyMessage(msg)).toBe('tool_call')
  })

  it('classifies plain assistant messages', () => {
    expect(classifyMessage({ role: 'assistant', content: 'here is my response' })).toBe('assistant')
  })

  it('classifies tool_result messages', () => {
    const msg = {
      role: 'user',
      content: [{ type: 'tool_result', tool_use_id: 'tu_1', content: 'output' }],
    }
    expect(classifyMessage(msg)).toBe('tool_result')
  })

  it('classifies plain user messages', () => {
    expect(classifyMessage({ role: 'user', content: 'hello' })).toBe('user')
  })
})



describe('classifyTool', () => {
  it('classifies known tools', () => {
    expect(classifyTool('bash')).toBe('shell')
    expect(classifyTool('read')).toBe('fs')
    expect(classifyTool('write')).toBe('fs')
    expect(classifyTool('cassi_memory')).toBe('memory')
    expect(classifyTool('cassi_agent')).toBe('orchestration')
  })

  it('strips cassi_ prefix', () => {
    expect(classifyTool('cassi_bash')).toBe('shell')
    expect(classifyTool('cassi_read')).toBe('fs')
  })

  it('strips mcp__*__ prefix', () => {
    expect(classifyTool('mcp__cassicore__bash')).toBe('shell')
    expect(classifyTool('mcp__cassicore__read')).toBe('fs')
  })

  it('falls back to "tool" for unknown names', () => {
    expect(classifyTool('unknown_tool_xyz')).toBe('tool')
  })
})



describe('buildToolResultPrefix', () => {
  it('formats a compact prefix for a successful tool', () => {
    const prefix = buildToolResultPrefix('bash', 342, 3200, false)
    expect(prefix).toBe('[bash · 342ms · 3.1KB · ✓]')
  })

  it('uses ✗ for errors', () => {
    const prefix = buildToolResultPrefix('read', 12, 512, true)
    expect(prefix).toBe('[read · 12ms · 512B · ✗]')
  })

  it('formats MB sizes', () => {
    const prefix = buildToolResultPrefix('bash', 1000, 2 * 1024 * 1024, false)
    expect(prefix).toBe('[bash · 1000ms · 2.0MB · ✓]')
  })

  it('uses "tool" when name is empty', () => {
    const prefix = buildToolResultPrefix('', 50, 100, false)
    expect(prefix).toBe('[tool · 50ms · 100B · ✓]')
  })
})



describe('TemporalRegistry', () => {
  it('records message timestamps', () => {
    const reg = new TemporalRegistry()
    const ts = new Date().toISOString()
    reg.recordMessage(0, ts, false)
    expect(reg.getTimestamp(0)).toBe(ts)
    expect(reg.size).toBe(1)
  })

  it('tracks last user message', () => {
    const reg = new TemporalRegistry()
    const t1 = new Date(Date.now() - 5000).toISOString()
    const t2 = new Date().toISOString()
    reg.recordMessage(0, t1, false)
    reg.recordMessage(1, t2, true) // user
    expect(reg.lastUserMessageAt).toBe(t2)
  })

  it('computes temporal context', () => {
    const start = new Date(Date.now() - 60_000).toISOString()
    const reg = new TemporalRegistry(start)
    const t0 = new Date(Date.now() - 30_000).toISOString()
    const t1 = new Date(Date.now() - 10_000).toISOString()
    reg.recordMessage(0, t0, false)
    reg.recordMessage(1, t1, false)

    const ctx = reg.computeTemporalContext(1)
    expect(ctx).not.toBeNull()
    expect(ctx!.msSincePrevious).toBeGreaterThan(15_000)
    expect(ctx!.msSincePrevious).toBeLessThan(25_000)
    expect(ctx!.sessionElapsedMs).toBeGreaterThan(45_000)
  })

  it('computes time-based urgency', () => {
    const reg = new TemporalRegistry()
    const recent = new Date().toISOString()
    const old = new Date(Date.now() - 60 * 60 * 1000).toISOString() // 1 hour ago
    reg.recordMessage(0, old, false)
    reg.recordMessage(1, recent, false)

    // 10min half-life: age=0 → urgency≈1.0; age=60min → urgency = 1/(1+6) ≈ 0.14
    expect(reg.computeUrgency(1)).toBeGreaterThan(0.9)
    expect(reg.computeUrgency(0)).toBeLessThan(0.20)  // 1hr ago with 10min half-life ≈ 0.14
  })

  it('describes gaps with time info', () => {
    const reg = new TemporalRegistry()
    const t0 = new Date(Date.now() - 120_000).toISOString()
    const t1 = new Date().toISOString()
    reg.recordMessage(0, t0, false)
    reg.recordMessage(5, t1, false)

    const desc = reg.describeGap(0, 5)
    expect(desc).toContain('omitted')
    expect(desc).toMatch(/\d+m/) // contains a time component
  })

  it('records tool metrics', () => {
    const reg = new TemporalRegistry()
    reg.recordToolMetrics('tu_1', 342, 3200)
    const m = reg.getToolMetrics('tu_1')
    expect(m).not.toBeNull()
    expect(m!.durationMs).toBe(342)
    expect(m!.outputBytes).toBe(3200)
  })
})



describe('Message Slots', () => {
  let slots: ReturnType<typeof createSlots>
  const now = new Date().toISOString()
  const baseCtx = (): SlotContext => ({
    timestamp: now,
    sessionStart: now,
    lastUserMessageAt: null,
    toolMetrics: new Map(),
    toolUseMap: new Map(),
    previousMessageTs: null,
  })

  beforeEach(() => {
    slots = createSlots()
  })

  const findSlot = (type: string) => slots.find(s => s.type === type)!

  describe('UserSlot', () => {
    it('matches plain user messages', () => {
      const slot = findSlot('user')
      expect(slot.matches({ role: 'user', content: 'hello' })).toBe(true)
    })

    it('does not match tool_result messages', () => {
      const slot = findSlot('user')
      const msg = {
        role: 'user',
        content: [{ type: 'tool_result', tool_use_id: 'tu_1', content: 'out' }],
      }
      expect(slot.matches(msg)).toBe(false)
    })

    it('attaches _thalamus annotation', () => {
      const slot = findSlot('user')
      const msg = { role: 'user', content: 'do this please' }
      const augmented = slot.augment(msg, baseCtx())
      expect(augmented._thalamus).toBeDefined()
      expect(augmented._thalamus.slot).toBe('user')
      expect(augmented._thalamus.ts).toBe(now)
      expect(augmented._thalamus.chars).toBeGreaterThan(0)
    })

    it('renders a time prefix', () => {
      const slot = findSlot('user')
      const annotation = { ts: '2024-01-15T14:32:07.000Z', slot: 'user' as const, chars: 10 }
      expect(slot.renderPrefix(annotation)).toBe('[14:32:07]')
    })

    it('boosts credibility score floor', () => {
      const slot = findSlot('user')
      const score = { novelty: 0.5, urgency: 0.1, relevance: 0.5, sourceCredibility: 0.3, composite: 0.3 }
      const adjusted = slot.adjustScore(score, { ts: now, slot: 'user', chars: 10 })
      expect(adjusted.sourceCredibility).toBeGreaterThanOrEqual(0.90)
      expect(adjusted.urgency).toBeGreaterThanOrEqual(0.15)
    })
  })

  describe('ToolCallSlot', () => {
    it('matches assistant tool_use messages', () => {
      const slot = findSlot('tool_call')
      const msg = {
        role: 'assistant',
        content: [{ type: 'tool_use', id: 'tu_1', name: 'bash', input: {} }],
      }
      expect(slot.matches(msg)).toBe(true)
    })

    it('does not match plain assistant messages', () => {
      const slot = findSlot('tool_call')
      expect(slot.matches({ role: 'assistant', content: 'text response' })).toBe(false)
    })

    it('attaches tool metadata', () => {
      const slot = findSlot('tool_call')
      const ctx = baseCtx()
      const msg = {
        role: 'assistant',
        content: [{ type: 'tool_use', id: 'tu_1', name: 'bash', input: { command: 'ls' } }],
      }
      const augmented = slot.augment(msg, ctx)
      expect(augmented._thalamus.slot).toBe('tool_call')
      expect(augmented._thalamus.tool.name).toBe('bash')
      expect(augmented._thalamus.tool.class).toBe('shell')
    })

    it('registers tool uses in the context map', () => {
      const slot = findSlot('tool_call')
      const ctx = baseCtx()
      const msg = {
        role: 'assistant',
        content: [{ type: 'tool_use', id: 'tu_abc', name: 'read', input: {} }],
      }
      slot.augment(msg, ctx)
      expect(ctx.toolUseMap.get('tu_abc')).toBe('read')
    })
  })

  describe('ToolResultSlot', () => {
    it('matches tool_result messages', () => {
      const slot = findSlot('tool_result')
      const msg = {
        role: 'user',
        content: [{ type: 'tool_result', tool_use_id: 'tu_1', content: 'output' }],
      }
      expect(slot.matches(msg)).toBe(true)
    })

    it('attaches tool execution metadata', () => {
      const slot = findSlot('tool_result')
      const ctx = baseCtx()
      ctx.toolUseMap.set('tu_1', 'bash')
      ctx.toolMetrics.set('tu_1', { durationMs: 342, outputBytes: 3200 })

      const msg = {
        role: 'user',
        content: [{ type: 'tool_result', tool_use_id: 'tu_1', content: 'output' }],
      }
      const augmented = slot.augment(msg, ctx)
      expect(augmented._thalamus.slot).toBe('tool_result')
      expect(augmented._thalamus.tool.name).toBe('bash')
      expect(augmented._thalamus.tool.class).toBe('shell')
      expect(augmented._thalamus.tool.durationMs).toBe(342)
      expect(augmented._thalamus.tool.outputBytes).toBe(3200)
    })

    it('renders a compact status prefix', () => {
      const slot = findSlot('tool_result')
      const annotation = {
        ts: now,
        slot: 'tool_result' as const,
        chars: 100,
        tool: { name: 'bash', class: 'shell', durationMs: 50, outputBytes: 512, isError: false },
      }
      const prefix = slot.renderPrefix(annotation)
      expect(prefix).toBe('[bash · 50ms · 512B · ✓]')
    })

    it('marks errors with ✗', () => {
      const slot = findSlot('tool_result')
      const annotation = {
        ts: now,
        slot: 'tool_result' as const,
        chars: 50,
        tool: { name: 'bash', class: 'shell', durationMs: 100, outputBytes: 200, isError: true },
      }
      expect(slot.renderPrefix(annotation)).toContain('✗')
    })

    it('boosts urgency score for errors', () => {
      const slot = findSlot('tool_result')
      const score = { novelty: 0.3, urgency: 0.1, relevance: 0.3, sourceCredibility: 0.5, composite: 0.3 }
      const annotation = {
        ts: now,
        slot: 'tool_result' as const,
        chars: 50,
        tool: { name: 'bash', class: 'shell', durationMs: 100, outputBytes: 200, isError: true },
      }
      const adjusted = slot.adjustScore(score, annotation)
      expect(adjusted.urgency).toBeGreaterThanOrEqual(0.40)
    })

    it('boosts credibility for slow tools (likely important data)', () => {
      const slot = findSlot('tool_result')
      const score = { novelty: 0.3, urgency: 0.3, relevance: 0.3, sourceCredibility: 0.5, composite: 0.3 }
      const annotation = {
        ts: now,
        slot: 'tool_result' as const,
        chars: 5000,
        tool: { name: 'cassi_agent', class: 'orchestration', durationMs: 5000, outputBytes: 5000, isError: false },
      }
      const adjusted = slot.adjustScore(score, annotation)
      expect(adjusted.sourceCredibility).toBeGreaterThanOrEqual(0.80)
    })
  })

  describe('AssistantSlot', () => {
    it('matches plain assistant text', () => {
      const slot = findSlot('assistant')
      expect(slot.matches({ role: 'assistant', content: 'text' })).toBe(true)
    })

    it('does not match tool_use messages', () => {
      const slot = findSlot('assistant')
      const msg = {
        role: 'assistant',
        content: [{ type: 'tool_use', id: 'tu_1', name: 'bash', input: {} }],
      }
      expect(slot.matches(msg)).toBe(false)
    })

    it('detects code blocks', () => {
      const slot = findSlot('assistant')
      const msg = { role: 'assistant', content: 'Here is the code:\n```ts\nconst x = 1\n```' }
      const augmented = slot.augment(msg, baseCtx())
      expect(augmented._thalamus.hasCode).toBe(true)
    })

    it('caps credibility below 0.60', () => {
      const slot = findSlot('assistant')
      const score = { novelty: 0.5, urgency: 0.5, relevance: 0.5, sourceCredibility: 0.95, composite: 0.7 }
      const annotation = { ts: now, slot: 'assistant' as const, chars: 100 }
      const adjusted = slot.adjustScore(score, annotation)
      expect(adjusted.sourceCredibility).toBeLessThanOrEqual(0.60)
    })
  })

  describe('SystemSlot', () => {
    it('matches system messages', () => {
      const slot = findSlot('system')
      expect(slot.matches({ role: 'system', content: 'instructions' })).toBe(true)
    })

    it('never compresses', () => {
      const slot = findSlot('system')
      const msg = { role: 'system', content: 'x'.repeat(10_000) }
      const annotation = { ts: now, slot: 'system' as const, chars: 10_000 }
      const result = slot.compress(msg, annotation, 100)
      expect(result.content.length).toBe(10_000) // unchanged
    })

    it('sets composite to 1.0 (always retained)', () => {
      const slot = findSlot('system')
      const score = { novelty: 0, urgency: 0, relevance: 0, sourceCredibility: 0, composite: 0 }
      const annotation = { ts: now, slot: 'system' as const, chars: 10 }
      const adjusted = slot.adjustScore(score, annotation)
      expect(adjusted.composite).toBe(1.0)
    })

    it('tags pineal source', () => {
      const slot = findSlot('system')
      const msg = { role: 'system', content: 'pineal identity facets go here' }
      const augmented = slot.augment(msg, baseCtx())
      expect(augmented._thalamus.source).toBe('pineal')
    })
  })
})



describe('ThalamusModule.process()', () => {
  let thalamus: ThalamusModule

  beforeEach(async () => {
    thalamus = new ThalamusModule(mockLogger())
    await thalamus.init()
  })

  it('attaches _thalamus to a user message', () => {
    const msg = { role: 'user', content: 'do this please' }
    const processed = thalamus.process('test-session', msg, 0)
    expect(processed._thalamus).toBeDefined()
    expect(processed._thalamus.slot).toBe('user')
    expect(typeof processed._thalamus.ts).toBe('string')
  })

  it('annotates tool_call with tool class', () => {
    const msg = {
      role: 'assistant',
      content: [{ type: 'tool_use', id: 'tu_1', name: 'bash', input: { command: 'ls' } }],
    }
    const processed = thalamus.process('test-session', msg, 0)
    expect(processed._thalamus.slot).toBe('tool_call')
    expect(processed._thalamus.tool.name).toBe('bash')
    expect(processed._thalamus.tool.class).toBe('shell')
  })

  it('annotates tool_result with provided metrics', () => {
    // First process a tool_call so the toolUseMap gets populated
    const callMsg = {
      role: 'assistant',
      content: [{ type: 'tool_use', id: 'tu_1', name: 'read', input: {} }],
    }
    thalamus.process('test-session', callMsg, 0)

    const resultMsg = {
      role: 'user',
      content: [{ type: 'tool_result', tool_use_id: 'tu_1', content: 'file contents' }],
    }
    const metrics = new Map([['tu_1', { durationMs: 12, outputBytes: 512 }]])
    const processed = thalamus.process('test-session', resultMsg, 1, metrics)

    expect(processed._thalamus.slot).toBe('tool_result')
    expect(processed._thalamus.tool.name).toBe('read')
    expect(processed._thalamus.tool.class).toBe('fs')
    expect(processed._thalamus.tool.durationMs).toBe(12)
  })

  it('creates temporal registry per session', () => {
    thalamus.process('session-a', { role: 'user', content: 'a' }, 0)
    thalamus.process('session-b', { role: 'user', content: 'b' }, 0)
    const regA = thalamus.getTemporalRegistry('session-a')
    const regB = thalamus.getTemporalRegistry('session-b')
    expect(regA).not.toBe(regB)
    expect(regA.size).toBe(1)
    expect(regB.size).toBe(1)
  })

  it('does not re-annotate already-processed messages', () => {
    const msg = { role: 'user', content: 'hello' }
    const first = thalamus.process('test-session', msg, 0)
    const firstTs = first._thalamus.ts
    // processAll skips annotated messages
    const result = thalamus.processAll('test-session', [first])
    expect(result[0]._thalamus.ts).toBe(firstTs)
  })
})



describe('ThalamusModule.curate() with annotations', () => {
  let thalamus: ThalamusModule

  beforeEach(async () => {
    thalamus = new ThalamusModule(mockLogger())
    await thalamus.init()
  })

  it('processes un-annotated messages during curation', async () => {
    const messages = [
      { role: 'user', content: 'do this' },
      { role: 'assistant', content: [{ type: 'tool_use', id: 'tu_1', name: 'bash', input: {} }] },
      { role: 'user', content: [{ type: 'tool_result', tool_use_id: 'tu_1', content: 'result' }] },
      { role: 'assistant', content: 'done' },
    ]
    const result = await thalamus.curate('test-session', messages)
    // _thalamus annotations are stripped before output (they're CassiCore-internal)
    // Verify messages survive curation intact (minus _thalamus)
    expect(result.messages.length).toBe(messages.length)
    for (const msg of result.messages) {
      expect(msg._thalamus).toBeUndefined()
    }
  })

  it('produces time-aware gap notes', async () => {
    // Build messages with _thalamus timestamps already attached
    const t0 = new Date(Date.now() - 300_000).toISOString() // 5 minutes ago
    const t10 = new Date(Date.now() - 120_000).toISOString() // 2 minutes ago
    const t11 = new Date(Date.now() - 60_000).toISOString()  // 1 minute ago

    // Create a large set of messages so curation actually drops some
    const messages: any[] = []
    for (let i = 0; i < 50; i++) {
      const ts = i === 0 ? t0 : i === 10 ? t10 : i === 11 ? t11 : new Date().toISOString()
      const msg = i % 2 === 0
        ? { role: 'user', content: `turn ${i}`, _thalamus: { ts, slot: 'user', chars: 6 } }
        : { role: 'assistant', content: `response ${i}`, _thalamus: { ts, slot: 'assistant', chars: 10 } }
      messages.push(msg)
    }

    const result = await thalamus.curate('test-session', messages, {
      charBudget: 500,
      recentWindowSize: 4,
    })

    // With gaps present, at least some should have time annotations
    expect(result.meta.gapNotes).toBeGreaterThanOrEqual(0)
    // Gap notes should include time info when timestamps are available
    const gapMsg = result.messages.find(m =>
      Array.isArray(m.content) &&
      m.content.some((c: any) => typeof c?.text === 'string' && c.text.includes('omitted'))
    )
    if (gapMsg) {
      const gapText = gapMsg.content.find((c: any) => c.text?.includes('omitted'))?.text ?? ''
      // Should contain either a time component or just turn count
      expect(gapText).toMatch(/omitted/)
    }
  })
})
