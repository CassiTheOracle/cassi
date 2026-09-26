import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import Database from 'better-sqlite3'
import { MnemicField } from '@cassicore/mnemic-field'
import { cosineSimilarity } from '@cassicore/mnemic-field'
import type { EngramCreate } from '@cassicore/mnemic-field'
import { mockLogger } from './helpers.ts'

function makeTestField(): MnemicField {
  const db = new Database(':memory:')
  db.pragma('foreign_keys = ON')
  return new MnemicField(mockLogger(), db)
}

describe('storeForSession', () => {
  let field: MnemicField

  beforeEach(() => {
    field = makeTestField()
  })

  it('stores an engram with session metadata', () => {
    const input: EngramCreate & { sessionId: string } = {
      sessionId: 'test-session-1',
      content: 'Test message content',
      nodeType: 'fact',
      provenance: 'test',
      metadata: {
        sessionId: 'test-session-1',
        messageIndex: 0,
        slotType: 'user',
      },
    }
    const result = field.storeForSession(input)
    expect(result.id).toBeTruthy()
    expect(result.content).toBe('Test message content')
    expect(result.metadata?.sessionId).toBe('test-session-1')
    expect(result.metadata?.messageIndex).toBe(0)
    expect(result.metadata?.slotType).toBe('user')
  })

  it('handles multiple messages in the same session', () => {
    const sessionId = 'test-session-2'
    for (let i = 0; i < 3; i++) {
      field.storeForSession({
        sessionId,
        content: `Message ${i}`,
        nodeType: 'fact',
        provenance: 'test',
        metadata: { sessionId, messageIndex: i, slotType: i % 2 === 0 ? 'user' : 'assistant' },
      })
    }
    const trace = field.getTrace({ sessionIds: [sessionId] })
    expect(trace.length).toBe(3)
    expect(trace[0].sessionId).toBe(sessionId)
    expect(trace[1].sessionId).toBe(sessionId)
  })

  it('preserves metadata across store and retrieval', () => {
    const id = 'msg-custom'
    field.storeForSession({
      id,
      sessionId: 's1',
      content: 'Custom metadata test',
      nodeType: 'fact',
      provenance: 'test',
      metadata: {
        sessionId: 's1',
        messageIndex: 0,
        slotType: 'tool_result',
        luminance: 0.85,
        isPinned: true,
      },
    })
    const retrieved = field.get(id)
    expect(retrieved).not.toBeNull()
    expect(retrieved!.metadata?.sessionId).toBe('s1')
    expect(retrieved!.metadata?.slotType).toBe('tool_result')
    expect(retrieved!.metadata?.luminance).toBe(0.85)
  })

  it('tolerates missing sessionId without error', () => {
    const result = field.storeForSession({
      content: 'No session ID',
      nodeType: 'fact',
      provenance: 'test',
      metadata: {},
    })
    expect(result.id).toBeTruthy()
    expect(result.content).toBe('No session ID')
  })
})

describe('findExpertEngrams', () => {
  let field: MnemicField

  beforeEach(() => {
    field = makeTestField()
    field.store({
      id: 'expert-auth',
      content: 'Auth middleware patterns using JWT and session tokens',
      nodeType: 'expert_summary',
      provenance: 'test',
      metadata: {
        expertId: 'expert-auth',
        expertKind: 'topic',
        expertDomain: 'praxis',
        expertConviction: 0.82,
        expertPinned: true,
        expertScope: null,
        expertVersion: 1,
        expertCentroid: [0.5, 0.3, 0.8, 0.1],
      },
    })
    field.store({
      id: 'expert-principle',
      content: 'Fail loudly on unexpected input. Prefer immutable state.',
      nodeType: 'expert_summary',
      provenance: 'test',
      metadata: {
        expertId: 'expert-principle',
        expertKind: 'principle',
        expertDomain: 'philosophy',
        expertConviction: 0.71,
        expertPinned: false,
        expertScope: null,
        expertVersion: 1,
        expertCentroid: [-0.2, -0.4, 0.1, 0.6],
      },
    })
  })

  it('filters by expertKind', () => {
    const results = field.findExpertEngrams({ expertKind: 'topic' })
    expect(results.length).toBe(1)
    expect(results[0].id).toBe('expert-auth')
  })

  it('filters by expertDomain', () => {
    const results = field.findExpertEngrams({ expertDomain: 'philosophy' })
    expect(results.length).toBe(1)
    expect(results[0].id).toBe('expert-principle')
  })

  it('filters by minConviction', () => {
    const high = field.findExpertEngrams({ minConviction: 0.8 })
    expect(high.length).toBe(1)
    expect(high[0].id).toBe('expert-auth')
    const low = field.findExpertEngrams({ minConviction: 0.5 })
    expect(low.length).toBe(2)
  })

  it('returns empty when no match', () => {
    const results = field.findExpertEngrams({ expertKind: 'skill' })
    expect(results.length).toBe(0)
  })

  it('returns all without filter', () => {
    const results = field.findExpertEngrams({ limit: 10 })
    expect(results.length).toBe(2)
  })

  it('sorts by conviction descending', () => {
    const results = field.findExpertEngrams({ limit: 10 })
    expect(results.length).toBe(2)
    expect(results[0].metadata?.expertConviction).toBe(0.82)
    expect(results[1].metadata?.expertConviction).toBe(0.71)
  })
})

describe('getTrace', () => {
  let field: MnemicField

  beforeEach(() => {
    field = makeTestField()
    const sessionId = 'trace-session'
    for (let i = 0; i < 4; i++) {
      field.storeForSession({
        sessionId,
        id: `trace-msg-${i}`,
        content: `Trace message ${i}`,
        nodeType: 'fact',
        provenance: 'test',
        metadata: { sessionId, messageIndex: i, slotType: i % 2 === 0 ? 'user' : 'assistant' },
      })
    }
  })

  it('returns all events for a session', () => {
    const events = field.getTrace({ sessionIds: ['trace-session'] })
    expect(events.length).toBe(4)
    events.forEach(e => expect(e.sessionId).toBe('trace-session'))
  })

  it('respects limit', () => {
    const events = field.getTrace({ sessionIds: ['trace-session'], limit: 2 })
    expect(events.length).toBeLessThanOrEqual(2)
  })

  it('returns empty for unknown session', () => {
    const events = field.getTrace({ sessionIds: ['unknown-session'] })
    expect(events.length).toBe(0)
  })
})

describe('cosineSimilarity', () => {
  it('returns 1 for identical vectors', () => {
    const a = [0.5, 0.3, 0.8]
    expect(cosineSimilarity(a, a)).toBeCloseTo(1, 5)
  })

  it('returns 0 for orthogonal vectors', () => {
    const a = [1, 0, 0]
    const b = [0, 1, 0]
    expect(cosineSimilarity(a, b)).toBeCloseTo(0, 5)
  })

  it('returns correct similarity for similar vectors', () => {
    const a = [0.5, 0.3, 0.8]
    const b = [0.52, 0.29, 0.79]
    expect(cosineSimilarity(a, b)).toBeGreaterThan(0.99)
  })

  it('handles zero vectors', () => {
    expect(cosineSimilarity([0, 0, 0], [1, 0, 0])).toBe(0)
  })
})

describe('EngramType additions', () => {
  it('includes new types in ENGRAM_TYPES', async () => {
    const { ENGRAM_TYPES } = await import('@cassicore/mnemic-field')
    expect(ENGRAM_TYPES).toContain('intent_span')
    expect(ENGRAM_TYPES).toContain('thought_command')
    expect(ENGRAM_TYPES).toContain('replay_segment')
    expect(ENGRAM_TYPES).toContain('expert_summary')
  })

  it('includes new types in SYNAPSE_TYPES', async () => {
    const { SYNAPSE_TYPES } = await import('@cassicore/mnemic-field')
    expect(SYNAPSE_TYPES).toContain('responds_to')
    expect(SYNAPSE_TYPES).toContain('triggered_by')
    expect(SYNAPSE_TYPES).toContain('commands')
    expect(SYNAPSE_TYPES).toContain('expert_summary')
    expect(SYNAPSE_TYPES).toContain('injected_for')
  })

  it('exports ExpertKind and ExpertDomain types', async () => {
    const m = await import('@cassicore/mnemic-field')
    expect(typeof m.ExpertKind).toBe('undefined') // type only, not value
  })
})
