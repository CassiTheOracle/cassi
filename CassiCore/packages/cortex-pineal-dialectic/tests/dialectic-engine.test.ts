/**
 * DialecticEngine Tests — verifies the string→string reasoning kernel
 *
 * Tests both parallel mode (Yang ∥ Yin → Unity) and consolidated mode (single call).
 * Uses mock providers to verify prompt construction, parsing, and A/B/C selection.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { DialecticEngine, createDialecticEngine } from '../src/dialectic/engine.js'

// Mock Provider ─────────────────────────────────────────────────

function makeMockProvider(responses: string[]) {
  let callIndex = 0
  return {
    calls: [] as Array<{ messages: any[]; opts: any }>,
    complete(messages: any[], opts: any) {
      const response = responses[callIndex] ?? responses[responses.length - 1]
      callIndex++
      const self = this
      self.calls.push({ messages, opts })
      return (async function* () {
        yield { type: 'token', text: response }
        yield { type: 'done' }
      })()
    },
  } as any
}

// Test Fixtures ─────────────────────────────────────────────────

const YANG_RESPONSE = JSON.stringify({
  response: 'Consider using Redis for hot data and Postgres for the authoritative store — a tiered approach gives you the best of both.',
  branches: [
    {
      type: 'alternative_interpretation',
      content: 'The question assumes a binary choice, but the real answer might be both. Redis as a write-through cache in front of Postgres is a common pattern.',
      confidence: 0.85,
      novelty: 0.6,
    },
    {
      type: 'edge_case',
      content: 'If the cache needs to survive restarts, Redis persistence (AOF/RDB) adds complexity that approaches what Postgres gives you for free.',
      confidence: 0.7,
      novelty: 0.7,
    },
    {
      type: 'what_if',
      content: 'What if the "cache" grows to be the primary data store? Redis memory costs scale linearly — at 100GB this becomes very expensive.',
      confidence: 0.6,
      novelty: 0.5,
    },
  ],
})

const YIN_RESPONSE = JSON.stringify({
  response: 'Postgres with UNLOGGED tables gives you cache-like performance with proper SQL semantics and zero operational overhead of running a second system.',
  baselines: [
    {
      type: 'constraint',
      content: 'Running Redis alongside Postgres doubles your operational surface area — deployment, monitoring, failover, and connection management all need handling for both.',
      confidence: 0.9,
      relevance: 0.85,
    },
    {
      type: 'reality_check',
      content: 'Most applications bottleneck on network latency, not database latency. For sub-5ms queries, both Redis and Postgres deliver similar results from the application perspective.',
      confidence: 0.75,
      relevance: 0.7,
    },
  ],
})

const UNITY_RESPONSE = JSON.stringify({
  selected: 'C',
  output: 'Start with Postgres and its built-in caching capabilities (UNLOGGED tables, materialized views). Only add Redis if profiling shows Postgres is the bottleneck — most applications never reach that point. This avoids premature complexity while keeping the Redis escape hatch available.',
  reasoning: 'Yang correctly identifies that Redis may eventually be needed, but Yin rightly points out that Postgres alone handles most cases. The pragmatic path is to start simple and add complexity only when measured need demands it.',
  comparison: {
    yangStrengths: 'Correctly identified the tiered cache pattern and the long-term scaling concern.',
    yangWeaknesses: 'Jumped to a two-system architecture without considering whether a single system suffices.',
    yinStrengths: 'Grounded in operational reality — minimizing system count reduces maintenance burden.',
    yinWeaknesses: 'UNLOGGED tables have durability trade-offs that should be made explicit.',
  },
  synthesis: {
    fromYang: 'The Redis escape hatch concept — knowing when to add it.',
    fromYin: 'Start with Postgres-only to minimize operational overhead.',
    novel: 'The decision trigger — add Redis only when profiling shows Postgres is the measured bottleneck.',
  },
  confidence: 0.82,
  signal: {
    type: 'assumption',
    content: 'The assumption that a cache is needed at all should be validated with profiling before choosing an implementation.',
    confidence: 0.75,
    urgency: 'immediate',
  },
})

const CONSOLIDATED_RESPONSE = JSON.stringify({
  yang: {
    response: 'Use a tiered caching strategy.',
    branches: [
      { type: 'what_if', content: 'What if traffic doubles?', confidence: 0.7, novelty: 0.6 },
    ],
  },
  yin: {
    response: 'Keep it simple with Postgres.',
    baselines: [
      { type: 'constraint', content: 'Operational cost of two systems.', confidence: 0.8, relevance: 0.9 },
    ],
  },
  unity: {
    selected: 'B',
    output: 'Use Postgres with proper indexing. Add Redis only if profiling demands it.',
    reasoning: 'Simplicity wins when performance requirements are unproven.',
    comparison: {
      yangStrengths: 'Forward-thinking',
      yangWeaknesses: 'Premature optimization',
      yinStrengths: 'Practical',
      yinWeaknesses: 'May need revisiting at scale',
    },
    confidence: 0.78,
  },
  signal: null,
})

// Test Helpers ──────────────────────────────────────────────────

const mockLogger = {
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
  debug: vi.fn(),
  child: () => mockLogger,
} as any

// Tests ─────────────────────────────────────────────────────────

describe('DialecticEngine', () => {
  let engine: DialecticEngine

  beforeEach(() => {
    vi.clearAllMocks()
    engine = new DialecticEngine(mockLogger)
  })

  describe('construction', () => {
    it('creates with createDialecticEngine factory', () => {
      const e = createDialecticEngine(mockLogger)
      expect(e).toBeInstanceOf(DialecticEngine)
    })

    it('accepts custom config', () => {
      const e = new DialecticEngine(mockLogger, {
        maxBranches: 5,
        yangTemperature: 0.9,
        model: 'claude-3-opus',
      })
      expect(e).toBeInstanceOf(DialecticEngine)
    })
  })

  describe('reason() — string in, string out', () => {
    it('throws without a provider', async () => {
      await expect(engine.reason('test')).rejects.toThrow('no provider configured')
    })

    it('returns Unity output as a plain string in parallel mode', async () => {
      const provider = makeMockProvider([YANG_RESPONSE, YIN_RESPONSE, UNITY_RESPONSE])
      engine.setProvider(provider)

      const result = await engine.reason('Should we use Redis or Postgres for caching?')

      expect(typeof result).toBe('string')
      expect(result).toContain('Postgres')
      expect(result.length).toBeGreaterThan(50)
    })

    it('makes 3 provider calls in parallel mode (Yang, Yin, Unity)', async () => {
      const provider = makeMockProvider([YANG_RESPONSE, YIN_RESPONSE, UNITY_RESPONSE])
      engine.setProvider(provider)

      await engine.reason('test input')

      expect(provider.calls.length).toBe(3)
    })

    it('passes context to prompts when provided', async () => {
      const provider = makeMockProvider([YANG_RESPONSE, YIN_RESPONSE, UNITY_RESPONSE])
      engine.setProvider(provider)

      await engine.reason('test', { context: 'We are building a Node.js API' })

      // Both Yang and Yin should receive the context
      const yangPrompt = provider.calls[0].messages[0].content
      const yinPrompt = provider.calls[1].messages[0].content
      expect(yangPrompt).toContain('Node.js API')
      expect(yinPrompt).toContain('Node.js API')
    })
  })

  describe('reasonStructured() — full breakdown', () => {
    it('returns structured result with all fields populated', async () => {
      const provider = makeMockProvider([YANG_RESPONSE, YIN_RESPONSE, UNITY_RESPONSE])
      engine.setProvider(provider)

      const result = await engine.reasonStructured('Redis vs Postgres?')

      // Top-level output
      expect(result.output).toBeTruthy()
      expect(typeof result.output).toBe('string')

      // Yang
      expect(result.yang.response).toContain('Redis')
      expect(result.yang.branches.length).toBe(3)
      expect(result.yang.branches[0].type).toBe('alternative_interpretation')
      expect(result.yang.branches[0].confidence).toBeGreaterThan(0)
      expect(result.yang.meta.latencyMs).toBeGreaterThanOrEqual(0)

      // Yin
      expect(result.yin.response).toContain('Postgres')
      expect(result.yin.baselines.length).toBe(2)
      expect(result.yin.baselines[0].type).toBe('constraint')

      // Unity
      expect(result.unity.selected).toBe('C')
      expect(result.unity.reasoning).toBeTruthy()
      expect(result.unity.comparison.yangStrengths).toBeTruthy()
      expect(result.unity.synthesis).toBeTruthy()
      expect(result.unity.synthesis!.fromYang).toBeTruthy()
      expect(result.unity.confidence).toBeGreaterThan(0)

      // Signal
      expect(result.signal).not.toBeNull()
      expect(result.signal!.type).toBe('assumption')
      expect(result.signal!.urgency).toBe('immediate')

      // Quality
      expect(result.quality.dialecticQuality).toBeGreaterThan(0)
      expect(result.quality.tension).toBeGreaterThanOrEqual(0)
      expect(result.quality.agreement).toBeGreaterThanOrEqual(0)
      expect(result.quality.tension + result.quality.agreement).toBeCloseTo(1, 1)

      // Meta
      expect(result.meta.totalLatencyMs).toBeGreaterThanOrEqual(0)
      expect(result.meta.mode).toBe('parallel')
    })

    it('handles Unity selecting option A (Yang)', async () => {
      const unitySelectsA = JSON.stringify({
        selected: 'A',
        output: 'Use Redis for everything.',
        reasoning: 'Speed is paramount.',
        comparison: {
          yangStrengths: 'Fast', yangWeaknesses: 'Memory cost',
          yinStrengths: 'Simple', yinWeaknesses: 'Too conservative',
        },
        confidence: 0.9,
        signal: null,
      })
      const provider = makeMockProvider([YANG_RESPONSE, YIN_RESPONSE, unitySelectsA])
      engine.setProvider(provider)

      const result = await engine.reasonStructured('test')
      expect(result.unity.selected).toBe('A')
      expect(result.unity.synthesis).toBeUndefined()
      expect(result.signal).toBeNull()
    })

    it('handles Unity selecting option B (Yin)', async () => {
      const unitySelectsB = JSON.stringify({
        selected: 'B',
        output: 'Just use Postgres.',
        reasoning: 'Keep it simple.',
        comparison: {
          yangStrengths: 'Creative', yangWeaknesses: 'Overcomplicated',
          yinStrengths: 'Practical', yinWeaknesses: 'Limited scope',
        },
        confidence: 0.85,
        signal: null,
      })
      const provider = makeMockProvider([YANG_RESPONSE, YIN_RESPONSE, unitySelectsB])
      engine.setProvider(provider)

      const result = await engine.reasonStructured('test')
      expect(result.unity.selected).toBe('B')
    })
  })

  describe('consolidated mode', () => {
    it('makes a single provider call', async () => {
      const provider = makeMockProvider([CONSOLIDATED_RESPONSE])
      engine.setProvider(provider)

      const result = await engine.reasonStructured('test', { mode: 'consolidated' })

      expect(provider.calls.length).toBe(1)
      expect(result.meta.mode).toBe('consolidated')
      expect(result.unity.selected).toBe('B')
      expect(result.output).toContain('Postgres')
    })
  })

  describe('JSON repair / fallback', () => {
    it('handles non-JSON Yang response gracefully', async () => {
      const provider = makeMockProvider([
        'I think you should use Redis because its fast.',  // Not JSON
        YIN_RESPONSE,
        UNITY_RESPONSE,
      ])
      engine.setProvider(provider)

      const result = await engine.reasonStructured('test')
      // Yang response is the raw text, branches empty
      expect(result.yang.response).toContain('Redis')
      expect(result.yang.branches.length).toBe(0)
      // Overall flow still completes
      expect(result.output).toBeTruthy()
    })

    it('handles markdown-fenced JSON', async () => {
      const fenced = '```json\n' + YANG_RESPONSE + '\n```'
      const provider = makeMockProvider([fenced, YIN_RESPONSE, UNITY_RESPONSE])
      engine.setProvider(provider)

      const result = await engine.reasonStructured('test')
      expect(result.yang.branches.length).toBe(3)
    })

    it('repairs trailing commas in JSON', async () => {
      const broken = YANG_RESPONSE.replace('}]', '},]')
      const provider = makeMockProvider([broken, YIN_RESPONSE, UNITY_RESPONSE])
      engine.setProvider(provider)

      const result = await engine.reasonStructured('test')
      expect(result.yang.branches.length).toBe(3)
    })
  })

  describe('model overrides', () => {
    it('uses per-posture model overrides', async () => {
      const provider = makeMockProvider([YANG_RESPONSE, YIN_RESPONSE, UNITY_RESPONSE])
      engine.setProvider(provider)

      await engine.reason('test', {
        models: {
          yang: 'custom/yang-model',
          yin: 'custom/yin-model',
          unity: 'custom/unity-model',
        },
      })

      expect(provider.calls[0].opts.model).toBe('yang-model')
      expect(provider.calls[1].opts.model).toBe('yin-model')
      expect(provider.calls[2].opts.model).toBe('unity-model')
    })
  })

  describe('provider override', () => {
    it('uses a per-call provider override', async () => {
      const defaultProvider = makeMockProvider(['unused'])
      const overrideProvider = makeMockProvider([YANG_RESPONSE, YIN_RESPONSE, UNITY_RESPONSE])
      engine.setProvider(defaultProvider)

      await engine.reason('test', { provider: overrideProvider })

      expect(defaultProvider.calls.length).toBe(0)
      expect(overrideProvider.calls.length).toBe(3)
    })
  })

  describe('quality metrics', () => {
    it('calculates agreement and tension', async () => {
      const provider = makeMockProvider([YANG_RESPONSE, YIN_RESPONSE, UNITY_RESPONSE])
      engine.setProvider(provider)

      const result = await engine.reasonStructured('test')
      expect(result.quality.agreement).toBeGreaterThan(0)
      expect(result.quality.agreement).toBeLessThanOrEqual(1)
      expect(result.quality.tension).toBeGreaterThan(0)
      expect(result.quality.tension).toBeLessThanOrEqual(1)
    })
  })
})
