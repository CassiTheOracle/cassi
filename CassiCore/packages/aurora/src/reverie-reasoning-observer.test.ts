/**
 * Tests for ReverieReasoningObserver — multi-tier LLM semantic analysis.
 */

import { describe, it, expect } from 'vitest'
import { ReverieReasoningObserver } from './reverie-reasoning-observer.js'
import type { MentalState } from './types.js'

function mockLogger() {
  return {
    debug: () => {},
    info: () => {},
    warn: () => {},
    error: () => {},
    child: () => mockLogger(),
  } as any
}

const baseInput = {
  text: 'Some reasoning.',
  currentState: null,
  activeTask: null,
  recentDecisions: [] as string[],
  extractedConcepts: [] as string[],
  shiftDetected: false,
}

describe('ReverieReasoningObserver', () => {
  it('should parse insights from valid JSON response', async () => {
    const mockInference = {
      infer: async () => JSON.stringify({
        insights: [
          { kind: 'gap', content: 'Missing error handling', confidence: 0.85 },
          { kind: 'contradiction', content: 'Claims P0 but does P1', confidence: 0.7, suggestion: 'Clarify priority' },
        ],
      }),
    }

    const observer = new ReverieReasoningObserver(mockInference, mockLogger())
    const result = await observer.analyze({
      ...baseInput,
      text: 'We should fix P0 bugs only. Let me refactor the auth module.',
      recentDecisions: ['P0 fixes only'],
      extractedConcepts: ['P0', 'auth module'],
    }, 5000)

    expect(result.insights.length).toBe(2)
    expect(result.insights[0].kind).toBe('gap')
    expect(result.insights[0].confidence).toBe(0.85)
    expect(result.insights[1].kind).toBe('contradiction')
    expect(result.insights[1].suggestion).toBe('Clarify priority')
    expect(result.tier).toBe(2)
    expect(result.shouldEscalate).toBe(false)
  })

  it('should return empty insights for empty response', async () => {
    const mockInference = {
      infer: async () => JSON.stringify({ insights: [] }),
    }

    const observer = new ReverieReasoningObserver(mockInference, mockLogger())
    const result = await observer.analyze({ ...baseInput }, 5000)

    expect(result.insights).toEqual([])
    expect(result.shouldEscalate).toBe(false)
  })

  it('should return empty insights on parse failure', async () => {
    const mockInference = {
      infer: async () => 'not valid json',
    }

    const observer = new ReverieReasoningObserver(mockInference, mockLogger())
    const result = await observer.analyze({ ...baseInput }, 5000)

    expect(result.insights).toEqual([])
    expect(result.shouldEscalate).toBe(false)
  })

  it('should return empty insights when inference throws', async () => {
    const throwingMock = {
      infer: async () => { throw new Error('network error') },
    }
    const observer = new ReverieReasoningObserver(throwingMock, mockLogger())
    const result = await observer.analyze({ ...baseInput }, 5000)

    expect(result.insights).toEqual([])
    expect(result.shouldEscalate).toBe(false)
  })

  it('should include mental state context in prompt', async () => {
    let capturedPrompt = ''
    const mockInference = {
      infer: async (messages: any[]) => {
        capturedPrompt = messages.find(m => m.role === 'user')?.content ?? ''
        return JSON.stringify({ insights: [] })
      },
    }

    const state: MentalState = {
      graph: { nodes: new Map(), edges: new Map(), reverseEdges: new Map(), sourceBreakdown: { model: 0, memory: 0, knowledge: 0, observer: 0, both: 0 }, edgeCount: 0, builtAt: Date.now() },
      resonanceHubs: [],
      gaps: [],
      recentDiscoveries: [],
      affect: null,
      foci: ['cognitive architecture', 'memory systems'],
      momentum: { trendingConcepts: [], novelty: 0, confidence: 0.5, topicShift: false, turnsInDirection: 0 },
      coherence: 0.7,
      integration: 0.6,
      computedAt: Date.now(),
      durationMs: 1,
    }

    const observer = new ReverieReasoningObserver(mockInference, mockLogger())
    await observer.analyze({
      text: 'We need to redesign the observer pattern.',
      currentState: state,
      activeTask: 'Implement Reverie-enhanced observeReasoning',
      recentDecisions: ['Use async fire-and-forget for slow path'],
      extractedConcepts: ['observer pattern', 'Reverie'],
      shiftDetected: true,
    }, 5000)

    expect(capturedPrompt).toContain('cognitive architecture')
    expect(capturedPrompt).toContain('memory systems')
    expect(capturedPrompt).toContain('Implement Reverie-enhanced observeReasoning')
    expect(capturedPrompt).toContain('Use async fire-and-forget for slow path')
    expect(capturedPrompt).toContain('reasoning shift was detected')
  })

  it('should clamp confidence to [0, 1]', async () => {
    const mockInference = {
      infer: async () => JSON.stringify({
        insights: [
          { kind: 'gap', content: 'overconfident', confidence: 1.5 },
          { kind: 'gap', content: 'underconfident', confidence: -0.3 },
        ],
      }),
    }

    const observer = new ReverieReasoningObserver(mockInference, mockLogger())
    const result = await observer.analyze({ ...baseInput }, 5000)

    expect(result.insights[0].confidence).toBe(1)
    expect(result.insights[1].confidence).toBe(0)
  })

  it('should reject invalid insight kinds', async () => {
    const mockInference = {
      infer: async () => JSON.stringify({
        insights: [
          { kind: 'gap', content: 'valid', confidence: 0.8 },
          { kind: 'bogus', content: 'invalid kind', confidence: 0.5 },
          { kind: 'breakthrough', content: 'also valid', confidence: 0.9 },
        ],
      }),
    }

    const observer = new ReverieReasoningObserver(mockInference, mockLogger())
    const result = await observer.analyze({ ...baseInput }, 5000)

    expect(result.insights.length).toBe(2)
    expect(result.insights.map(i => i.kind)).toEqual(['gap', 'breakthrough'])
  })

  it('should use active task and recent decisions in prompt', async () => {
    let capturedPrompt = ''
    const mockInference = {
      infer: async (messages: any[]) => {
        capturedPrompt = messages.find(m => m.role === 'user')?.content ?? ''
        return JSON.stringify({ insights: [] })
      },
    }

    const observer = new ReverieReasoningObserver(mockInference, mockLogger())
    await observer.analyze({
      ...baseInput,
      text: 'We need to fix the bug.',
      activeTask: 'Fix critical authentication bug before deploy',
      recentDecisions: ['No new features until P0s are fixed', 'Use async/await pattern'],
      extractedConcepts: ['bug', 'authentication'],
    }, 5000)

    expect(capturedPrompt).toContain('Fix critical authentication bug before deploy')
    expect(capturedPrompt).toContain('No new features until P0s are fixed')
    expect(capturedPrompt).toContain('Use async/await pattern')
  })


  it('should flag escalation when all insights have low confidence', async () => {
    const mockInference = {
      infer: async () => JSON.stringify({
        insights: [
          { kind: 'gap', content: 'vague observation', confidence: 0.2 },
          { kind: 'assumption', content: 'weak assumption', confidence: 0.3 },
        ],
      }),
    }

    const observer = new ReverieReasoningObserver(mockInference, mockLogger(), {
      lowConfidenceThreshold: 0.4,
    })
    const result = await observer.analyze({ ...baseInput }, 5000)

    expect(result.shouldEscalate).toBe(true)
    expect(result.escalateReason).toContain('max confidence')
  })

  it('should flag escalation for uncertain contradictions', async () => {
    const mockInference = {
      infer: async () => JSON.stringify({
        insights: [
          { kind: 'contradiction', content: 'maybe conflicting', confidence: 0.3 },
          { kind: 'gap', content: 'something', confidence: 0.8 },
        ],
      }),
    }

    const observer = new ReverieReasoningObserver(mockInference, mockLogger(), {
      contradictionThreshold: 0.5,
    })
    const result = await observer.analyze({ ...baseInput }, 5000)

    expect(result.shouldEscalate).toBe(true)
    expect(result.escalateReason).toContain('contradiction')
  })

  it('should not escalate at tier 3 (max tier)', async () => {
    const mockInference = {
      infer: async () => JSON.stringify({
        insights: [
          { kind: 'gap', content: 'very uncertain', confidence: 0.1 },
        ],
      }),
    }

    const observer = new ReverieReasoningObserver(mockInference, mockLogger())
    const result = await observer.analyze({ ...baseInput }, 5000, 3)

    expect(result.tier).toBe(3)
    expect(result.shouldEscalate).toBe(false)
  })

  it('should not escalate when insights are confident', async () => {
    const mockInference = {
      infer: async () => JSON.stringify({
        insights: [
          { kind: 'gap', content: 'clear issue', confidence: 0.85 },
          { kind: 'contradiction', content: 'definite conflict', confidence: 0.9 },
        ],
      }),
    }

    const observer = new ReverieReasoningObserver(mockInference, mockLogger())
    const result = await observer.analyze({ ...baseInput }, 5000)

    expect(result.shouldEscalate).toBe(false)
  })

  it('should accept tier parameter and report it in result', async () => {
    const mockInference = {
      infer: async () => JSON.stringify({ insights: [] }),
    }

    const observer = new ReverieReasoningObserver(mockInference, mockLogger())
    const result = await observer.analyze({ ...baseInput }, 5000, 1)

    expect(result.tier).toBe(1)
  })

  it('should report durationMs', async () => {
    const mockInference = {
      infer: async () => JSON.stringify({ insights: [] }),
    }

    const observer = new ReverieReasoningObserver(mockInference, mockLogger())
    const result = await observer.analyze({ ...baseInput }, 5000)

    expect(result.durationMs).toBeGreaterThanOrEqual(0)
  })
})
