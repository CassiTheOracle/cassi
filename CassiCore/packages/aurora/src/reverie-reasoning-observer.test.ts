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

describe('analyzeWithEscalation', () => {
  // Builds a mock infer() that returns a different JSON payload depending on
  // tier. Tier is detected from the system prompt prefix ("quick sanity check"
  // for tier 1, "deep investigation" for tier 3, otherwise tier 2).
  function tieredInference(byTier: Record<1 | 2 | 3, unknown>) {
    const calls: number[] = []
    const infer = async (messages: any[]) => {
      const sys = String(messages.find(m => m.role === 'system')?.content ?? '')
      const tier: 1 | 2 | 3 = sys.includes('quick sanity check') ? 1
        : sys.includes('deep investigation') ? 3
        : 2
      calls.push(tier)
      return JSON.stringify(byTier[tier])
    }
    return { mock: { infer }, calls }
  }

  it('stops at tier 1 when no escalation is needed', async () => {
    const { mock, calls } = tieredInference({
      1: { insights: [{ kind: 'gap', content: 'clear gap', confidence: 0.9 }] },
      2: { insights: [] },
      3: { insights: [] },
    })

    const observer = new ReverieReasoningObserver(mock, mockLogger())
    const result = await observer.analyzeWithEscalation({ ...baseInput }, 5000)

    expect(calls).toEqual([1])
    expect(result.chain.length).toBe(1)
    expect(result.chain[0].tier).toBe(1)
    expect(result.escalated).toBe(false)
    expect(result.finalResult.tier).toBe(1)
    expect(result.finalResult.shouldEscalate).toBe(false)
    expect(result.totalDurationMs).toBeGreaterThanOrEqual(0)
  })

  it('cascades 1 -> 2 when tier 1 says shouldEscalate', async () => {
    const { mock, calls } = tieredInference({
      1: { insights: [{ kind: 'gap', content: 'fuzzy', confidence: 0.2 }] },
      2: { insights: [{ kind: 'gap', content: 'clearer', confidence: 0.85 }] },
      3: { insights: [] },
    })

    const observer = new ReverieReasoningObserver(mock, mockLogger())
    const result = await observer.analyzeWithEscalation({ ...baseInput }, 5000)

    expect(calls).toEqual([1, 2])
    expect(result.chain.map(r => r.tier)).toEqual([1, 2])
    expect(result.escalated).toBe(true)
    expect(result.finalResult.tier).toBe(2)
    expect(result.finalResult.shouldEscalate).toBe(false)
  })

  it('cascades 1 -> 2 -> 3 when both lower tiers escalate', async () => {
    const { mock, calls } = tieredInference({
      1: { insights: [{ kind: 'gap', content: 'fuzzy', confidence: 0.2 }] },
      2: { insights: [{ kind: 'contradiction', content: 'maybe', confidence: 0.3 }] },
      3: { insights: [{ kind: 'gap', content: 'still uncertain', confidence: 0.1 }] },
    })

    const observer = new ReverieReasoningObserver(mock, mockLogger())
    const result = await observer.analyzeWithEscalation({ ...baseInput }, 5000)

    expect(calls).toEqual([1, 2, 3])
    expect(result.chain.map(r => r.tier)).toEqual([1, 2, 3])
    expect(result.escalated).toBe(true)
    expect(result.finalResult.tier).toBe(3)
    expect(result.finalResult.shouldEscalate).toBe(false)
  })

  it('starts at highStakesMinTier when isHighStakes is set', async () => {
    const { mock, calls } = tieredInference({
      1: { insights: [{ kind: 'gap', content: 'fuzzy', confidence: 0.1 }] },
      2: { insights: [{ kind: 'gap', content: 'fine', confidence: 0.9 }] },
      3: { insights: [] },
    })

    const observer = new ReverieReasoningObserver(mock, mockLogger(), {
      highStakesMinTier: 2,
    })
    const result = await observer.analyzeWithEscalation({ ...baseInput }, 5000, { isHighStakes: true })

    expect(calls).toEqual([2])
    expect(result.chain.map(r => r.tier)).toEqual([2])
    expect(result.escalated).toBe(false)
    expect(result.finalResult.tier).toBe(2)
  })

  it('caps at tier 3 even if tier-3 result wants to escalate', async () => {
    const { mock, calls } = tieredInference({
      1: { insights: [] },
      2: { insights: [] },
      3: { insights: [{ kind: 'gap', content: 'still uncertain', confidence: 0.1 }] },
    })

    const observer = new ReverieReasoningObserver(mock, mockLogger())
    const result = await observer.analyzeWithEscalation({ ...baseInput }, 5000, { startTier: 3 })

    expect(calls).toEqual([3])
    expect(result.chain.length).toBe(1)
    expect(result.chain[0].tier).toBe(3)
    expect(result.chain[0].shouldEscalate).toBe(false)
    expect(result.escalated).toBe(false)
  })

  it('records full ReverieAnalysisResult for each chain entry', async () => {
    const { mock } = tieredInference({
      1: { insights: [{ kind: 'gap', content: 'fuzzy', confidence: 0.2 }] },
      2: { insights: [{ kind: 'breakthrough', content: 'aha', confidence: 0.95, suggestion: 'pursue this' }] },
      3: { insights: [] },
    })

    const observer = new ReverieReasoningObserver(mock, mockLogger())
    const result = await observer.analyzeWithEscalation({ ...baseInput }, 5000)

    expect(result.chain.length).toBe(2)
    for (const entry of result.chain) {
      expect(entry).toHaveProperty('insights')
      expect(entry).toHaveProperty('tier')
      expect(entry).toHaveProperty('shouldEscalate')
      expect(entry).toHaveProperty('durationMs')
      expect(entry.durationMs).toBeGreaterThanOrEqual(0)
    }
    expect(result.chain[0].insights[0].confidence).toBe(0.2)
    expect(result.chain[1].insights[0].kind).toBe('breakthrough')
    expect(result.chain[1].insights[0].suggestion).toBe('pursue this')
    expect(result.finalResult).toBe(result.chain[1])
  })
})
