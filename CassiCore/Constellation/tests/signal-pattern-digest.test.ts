import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  SignalPatternBuffer,
  renderDigestMarkdown,
  shouldRecordForDigest,
  type PatternEntry,
} from '../src/signal-pattern-digest.js'

import type { CognitiveSignal, SignalType } from '../src/vendor/workspace/cognitive-signal.js'

function makeSignal(overrides: Partial<CognitiveSignal> = {}): CognitiveSignal {
  return {
    signalId: 's-' + Math.random().toString(36).slice(2, 8),
    source: 'helix',
    sessionId: 'helix-1',
    type: 'tension' as SignalType,
    content: 'something tense',
    createdAt: Date.now(),
    luminance: { novelty: 0, urgency: 0, relevance: 0, sourceCredibility: 0, cognitiveResonance: 0, strategicImportance: 0, composite: 0 },
    ...overrides,
  }
}

describe('SignalPatternBuffer', () => {
  it('records signals with content preview truncated to 200 chars', () => {
    const buf = new SignalPatternBuffer()
    const longContent = 'x'.repeat(500)
    buf.record(makeSignal({ content: longContent }))
    const snap = buf.snapshot()
    expect(snap.length).toBe(1)
    expect(snap[0].contentPreview.length).toBe(200)
  })

  it('caps at maxEntries (oldest dropped first)', () => {
    const buf = new SignalPatternBuffer(3, 60_000)
    for (let i = 0; i < 5; i++) {
      buf.record(makeSignal({ signalId: `s-${i}`, content: `entry ${i}` }))
    }
    const snap = buf.snapshot()
    expect(snap.length).toBe(3)
    expect(snap[0].contentPreview).toBe('entry 2')
    expect(snap[2].contentPreview).toBe('entry 4')
  })

  it('prunes entries outside the time window', () => {
    vi.useFakeTimers()
    try {
      const buf = new SignalPatternBuffer(30, 60_000)
      buf.record(makeSignal({ createdAt: Date.now() }))
      vi.advanceTimersByTime(70_000)
      buf.record(makeSignal({ createdAt: Date.now() }))
      const snap = buf.snapshot()
      expect(snap.length).toBe(1)
    } finally {
      vi.useRealTimers()
    }
  })

  it('size() reflects pruning', () => {
    vi.useFakeTimers()
    try {
      const buf = new SignalPatternBuffer(30, 60_000)
      buf.record(makeSignal({ createdAt: Date.now() }))
      expect(buf.size()).toBe(1)
      vi.advanceTimersByTime(70_000)
      expect(buf.size()).toBe(0)
    } finally {
      vi.useRealTimers()
    }
  })

  it('clear() empties the buffer', () => {
    const buf = new SignalPatternBuffer()
    buf.record(makeSignal())
    buf.record(makeSignal())
    expect(buf.size()).toBe(2)
    buf.clear()
    expect(buf.size()).toBe(0)
  })
})

describe('shouldRecordForDigest', () => {
  it('rejects signals from source: corpus (self-feedback guard)', () => {
    expect(shouldRecordForDigest(makeSignal({ source: 'corpus' }))).toBe(false)
  })

  it('rejects type: goal (territory-awareness handles)', () => {
    expect(shouldRecordForDigest(makeSignal({ type: 'goal' }))).toBe(false)
  })

  it('rejects type: bridge (territory-awareness emits)', () => {
    expect(shouldRecordForDigest(makeSignal({ type: 'bridge' }))).toBe(false)
  })

  it('accepts tension/warning/insight/observation/convergence from non-corpus sources', () => {
    const accepted: SignalType[] = ['tension', 'warning', 'insight', 'observation', 'convergence']
    for (const t of accepted) {
      expect(shouldRecordForDigest(makeSignal({ type: t, source: 'helix' }))).toBe(true)
    }
  })
})

describe('renderDigestMarkdown', () => {
  it('returns undefined when buffer is empty', () => {
    const buf = new SignalPatternBuffer()
    expect(renderDigestMarkdown(buf)).toBeUndefined()
  })

  it('renders counts line for mixed-type entries', () => {
    const buf = new SignalPatternBuffer()
    buf.record(makeSignal({ type: 'tension' }))
    buf.record(makeSignal({ type: 'warning' }))
    buf.record(makeSignal({ type: 'tension' }))

    const out = renderDigestMarkdown(buf)
    expect(out).toBeDefined()
    expect(out).toContain('Recent workspace signals (last 3 in 60s window):')
    expect(out).toContain('Counts:')
    expect(out).toContain('tension=2')
    expect(out).toContain('warning=1')
  })

  it('fires tension-cluster advisory when one helix produces ≥3 tensions', () => {
    const buf = new SignalPatternBuffer()
    for (let i = 0; i < 4; i++) {
      buf.record(makeSignal({ type: 'tension', sessionId: 'helix-busy' }))
    }
    const out = renderDigestMarkdown(buf)
    expect(out).toContain('helix-bu')
    expect(out).toContain('produced 4 tension signals')
    expect(out).toContain('send_directive with narrowed framing')
    expect(out).toContain('request_spawn with narrowedGoal')
  })

  it('does NOT fire tension-cluster when below threshold (2 tensions)', () => {
    const buf = new SignalPatternBuffer()
    buf.record(makeSignal({ type: 'tension', sessionId: 'helix-x' }))
    buf.record(makeSignal({ type: 'tension', sessionId: 'helix-x' }))
    const out = renderDigestMarkdown(buf)
    expect(out).not.toContain('produced')
  })

  it('fires warning-coalition advisory when ≥2 distinct helixes raise warnings', () => {
    const buf = new SignalPatternBuffer()
    buf.record(makeSignal({ type: 'warning', sessionId: 'helix-a' }))
    buf.record(makeSignal({ type: 'warning', sessionId: 'helix-b' }))
    const out = renderDigestMarkdown(buf)
    expect(out).toContain('2 sibling Helixes raised warnings')
    expect(out).toContain('research subtask')
  })

  it('does NOT fire warning-coalition when same helix repeats (singleton)', () => {
    const buf = new SignalPatternBuffer()
    buf.record(makeSignal({ type: 'warning', sessionId: 'helix-a' }))
    buf.record(makeSignal({ type: 'warning', sessionId: 'helix-a' }))
    buf.record(makeSignal({ type: 'warning', sessionId: 'helix-a' }))
    const out = renderDigestMarkdown(buf)
    expect(out).not.toContain('sibling Helixes raised warnings')
  })

  it('includes Recent flavor (last 5 actionable signals)', () => {
    const buf = new SignalPatternBuffer()
    buf.record(makeSignal({ type: 'tension', content: 'first tension' }))
    buf.record(makeSignal({ type: 'observation', content: 'unimportant obs' }))
    buf.record(makeSignal({ type: 'warning', content: 'a warning' }))
    buf.record(makeSignal({ type: 'convergence', content: 'agreement' }))

    const out = renderDigestMarkdown(buf)
    expect(out).toContain('Recent:')
    expect(out).toContain('[tension]')
    expect(out).toContain('first tension')
    expect(out).toContain('[warning]')
    expect(out).toContain('[convergence]')
    expect(out).not.toContain('unimportant obs')
  })

  it('truncates at the char cap', () => {
    const buf = new SignalPatternBuffer(200, 60_000)
    for (let h = 0; h < 30; h++) {
      for (let i = 0; i < 4; i++) {
        buf.record(makeSignal({ type: 'tension', content: 'x'.repeat(60), sessionId: `helix-cluster-${h}-with-long-id` }))
      }
    }
    const out = renderDigestMarkdown(buf)
    expect(out).toBeDefined()
    expect(out!.length).toBeLessThanOrEqual(1500 + ' [truncated]'.length)
    expect(out).toContain('[truncated]')
  })
})

describe('Corpus handler integration (filter + record)', () => {
  let buffer: SignalPatternBuffer
  const isMember = (id: string) => id === 'helix-1' || id === 'helix-2'

  beforeEach(() => { buffer = new SignalPatternBuffer() })

  function processOne(sig: CognitiveSignal): void {
    if (!shouldRecordForDigest(sig)) return
    if (!isMember(sig.sessionId)) return
    buffer.record(sig)
  }

  it('records qualifying tension/warning signals from siblings', () => {
    processOne(makeSignal({ type: 'tension', sessionId: 'helix-1' }))
    processOne(makeSignal({ type: 'warning', sessionId: 'helix-2' }))
    expect(buffer.size()).toBe(2)
  })

  it('skips bridge signals (territory handles)', () => {
    processOne(makeSignal({ type: 'bridge', source: 'corpus', sessionId: 'helix-1' }))
    expect(buffer.size()).toBe(0)
  })

  it('skips goal signals (territory handles)', () => {
    processOne(makeSignal({ type: 'goal', sessionId: 'helix-1' }))
    expect(buffer.size()).toBe(0)
  })

  it('skips signals from non-sibling sessionId', () => {
    processOne(makeSignal({ type: 'tension', sessionId: 'helix-stranger' }))
    expect(buffer.size()).toBe(0)
  })

  it('skips signals from corpus (self-feedback guard)', () => {
    processOne(makeSignal({ type: 'suggestion', source: 'corpus', sessionId: 'helix-1' }))
    expect(buffer.size()).toBe(0)
  })
})
