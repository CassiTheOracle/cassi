/**
 * CentralizedProvider - Provider Wrapper with Protections
 *
 * CentralizedProvider wraps any IProvider implementation with cross-cutting concerns
 * that protect the system from cascading failures and resource exhaustion:
 *
 *   - Request deduplication: Prevents simultaneous requests from the same session
 *   - Adaptive per-provider, per-model rate limiting: Learns limits from 429 responses
 *   - Multi-timescale rate tracking: Independent limits at 1m, 10m, and 1h windows
 *   - Error tracking with cooldown: Exponential backoff after consecutive errors
 *   - Request metrics and logging: Observability for all provider interactions
 *   - Event emission: Publishes provider lifecycle events to the event bus
 *   - Per-request timeout enforcement: Prevents hung requests from blocking indefinitely
 *   - Budget tracking integration: Records metered requests for quota management
 *
 * Rate limiting is not pre-configured — limits are learned empirically from 429 responses.
 * When a rate limit is hit, the system records the request rate that triggered it
 * (at all timescales) and throttles future requests to stay below 90% of that rate.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { CentralizedProvider, wrapProvidersWithCentralized } from '../src/centralized.js'
import type { IProvider, Message, CompletionOpts, CompletionChunk } from '@cassicore/foundation'
import type { ILogger, IEventBus } from '@cassicore/foundation'

// Mock factories for creating testable provider instances

/**
 * Creates a mock provider with configurable response sequence and call tracking.
 */
function makeMockProvider(id: string, responseSequence: string[] = ['response']): IProvider & { callCount: number } {
  let callCount = 0
  return {
    id,
    models: ['model-1'],
    get callCount() { return callCount },
    async *complete(): AsyncIterable<CompletionChunk> {
      callCount++
      await new Promise(r => setTimeout(r, 50))
      const resp = responseSequence[callCount - 1] ?? responseSequence[responseSequence.length - 1]
      yield { type: 'token', text: resp, tokensUsed: 10 }
      await new Promise(r => setTimeout(r, 10))
      yield { type: 'done' }
    },
    async countTokens(): Promise<number> { return 10 },
    async ping(): Promise<boolean> { return true },
  }
}

/**
 * Creates a mock provider that fails with a rate limit error after N successful requests.
 */
function makeRateLimitAfterNProvider(id: string, successCount: number): IProvider & { callCount: number } {
  let callCount = 0
  return {
    id,
    models: ['model-1'],
    get callCount() { return callCount },
    async *complete(): AsyncIterable<CompletionChunk> {
      callCount++
      await new Promise(r => setTimeout(r, 10))
      if (callCount > successCount) {
        throw new Error('HTTP 429: rate limit exceeded')
      }
      yield { type: 'token', text: 'ok', tokensUsed: 5 }
      yield { type: 'done' }
    },
    async countTokens(): Promise<number> { return 10 },
    async ping(): Promise<boolean> { return true },
  }
}

function makeMockLogger(): ILogger {
  return {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
    child: vi.fn(() => makeMockLogger()),
  } as unknown as ILogger
}

function makeMockBus(): IEventBus & { events: any[] } {
  const events: any[] = []
  return {
    events,
    emit: vi.fn((e: any) => events.push(e)),
    on: vi.fn(),
    off: vi.fn(),
  } as unknown as IEventBus & { events: any[] }
}

function makeMessages(sessionHint?: string): Message[] {
  const system = sessionHint
    ? `System prompt for session ${sessionHint}`
    : 'System prompt'
  return [
    { role: 'system', content: system },
    { role: 'user', content: 'Hello' },
  ]
}

describe('CentralizedProvider', () => {
  let logger: ReturnType<typeof makeMockLogger>
  let bus: ReturnType<typeof makeMockBus>

  beforeEach(() => {
    logger = makeMockLogger()
    bus = makeMockBus()
  })

  describe('basic operation', () => {
    it('forwards completion requests to the wrapped provider', async () => {
      const inner = makeMockProvider('test')
      const provider = new CentralizedProvider(inner, logger, bus)

      const chunks: CompletionChunk[] = []
      for await (const c of provider.complete(makeMessages(), { model: 'model-1' })) {
        chunks.push(c)
      }

      expect(chunks).toHaveLength(2)
      expect(chunks[0].type).toBe('token')
      expect(chunks[1].type).toBe('done')
      expect(inner.callCount).toBe(1)
    })

    it('emits provider:request_start and provider:request_end events', async () => {
      const inner = makeMockProvider('test')
      const provider = new CentralizedProvider(inner, logger, bus)

      for await (const _ of provider.complete(makeMessages(), { model: 'model-1' })) { }

      const startEvent = bus.events.find(e => e.type === 'provider:request_start')
      const endEvent = bus.events.find(e => e.type === 'provider:request_end')

      expect(startEvent).toBeDefined()
      expect(startEvent.providerId).toBe('test')
      expect(startEvent.model).toBe('model-1')
      expect(endEvent).toBeDefined()
      expect(endEvent.durationMs).toBeGreaterThanOrEqual(0)
    })

    it('delegates countTokens to the wrapped provider', async () => {
      const inner = makeMockProvider('test')
      inner.countTokens = vi.fn().mockResolvedValue(42)
      const provider = new CentralizedProvider(inner, logger, bus)

      const result = await provider.countTokens(makeMessages())
      expect(result).toBe(42)
      expect(inner.countTokens).toHaveBeenCalledWith(makeMessages())
    })

    it('delegates ping without rate limiting', async () => {
      const inner = makeMockProvider('test')
      inner.ping = vi.fn().mockResolvedValue(true)
      const provider = new CentralizedProvider(inner, logger, bus)

      const result = await provider.ping()
      expect(result).toBe(true)
      expect(inner.ping).toHaveBeenCalled()
    })
  })

  describe('request deduplication', () => {
    it('rejects simultaneous requests from the same session', async () => {
      const inner = makeMockProvider('test', ['slow-response'])
      const provider = new CentralizedProvider(inner, logger, bus, { errorCooldownMs: 0 })

      const messages: Message[] = [
        { role: 'system', content: 'session: test-session-123' },
        { role: 'user', content: 'Hello' },
      ]

      const firstPromise = (async () => {
        const chunks: CompletionChunk[] = []
        for await (const c of provider.complete(messages, { model: 'model-1' })) { chunks.push(c) }
        return chunks
      })()

      await new Promise(r => setTimeout(r, 10))

      const secondPromise = (async () => {
        const chunks: CompletionChunk[] = []
        for await (const c of provider.complete(messages, { model: 'model-1' })) { chunks.push(c) }
        return chunks
      })()

      await expect(secondPromise).rejects.toThrow(/already in progress/)
      await firstPromise

      const dedupEvent = bus.events.find(e => e.type === 'provider:deduplicated')
      expect(dedupEvent).toBeDefined()
      expect(inner.callCount).toBe(1)
    })

    it('allows sequential requests from the same session after completion', async () => {
      const inner = makeMockProvider('test')
      const provider = new CentralizedProvider(inner, logger, bus, { errorCooldownMs: 0 })

      const messages = makeMessages('session-xyz')
      for await (const _ of provider.complete(messages, { model: 'model-1' })) { }
      for await (const _ of provider.complete(messages, { model: 'model-1' })) { }

      expect(inner.callCount).toBe(2)
    })

    it('respects allowConcurrent to bypass deduplication', async () => {
      const inner = makeMockProvider('test', ['response-1', 'response-2'])
      const provider = new CentralizedProvider(inner, logger, bus, { errorCooldownMs: 0 })

      const messages: Message[] = [
        { role: 'system', content: 'session: concurrent-test' },
        { role: 'user', content: 'Hello' },
      ]

      const firstPromise = (async () => {
        const chunks: CompletionChunk[] = []
        for await (const c of provider.complete(messages, { model: 'model-1', allowConcurrent: true } as CompletionOpts)) { chunks.push(c) }
        return chunks
      })()

      await new Promise(r => setTimeout(r, 10))

      const secondPromise = (async () => {
        const chunks: CompletionChunk[] = []
        for await (const c of provider.complete(messages, { model: 'model-1', allowConcurrent: true } as CompletionOpts)) { chunks.push(c) }
        return chunks
      })()

      await expect(firstPromise).resolves.toBeDefined()
      await expect(secondPromise).resolves.toBeDefined()
      expect(inner.callCount).toBe(2)
    })
  })

  describe('adaptive rate limiting', () => {
    it('allows unlimited requests when no rate limit has been learned', async () => {
      const inner = makeMockProvider('test')
      const provider = new CentralizedProvider(inner, logger, bus, { errorCooldownMs: 0 })

      for (let i = 0; i < 10; i++) {
        for await (const _ of provider.complete(makeMessages(`s${i}`), { model: 'model-1' })) { }
      }

      expect(inner.callCount).toBe(10)
      expect(provider.getMetrics().rateLimited).toBe(0)
    })

    it('learns rate limit from 429 errors and emits provider:rate_learned', async () => {
      // Retry waits (sleepWithAbort uses setTimeout) are controlled with fake timers.
      vi.useFakeTimers()
      try {
        const inner = makeRateLimitAfterNProvider('test', 3)
        const provider = new CentralizedProvider(inner, logger, bus, { errorCooldownMs: 0 })

        for (let i = 0; i < 3; i++) {
          const p = (async () => {
            for await (const _ of provider.complete(makeMessages(`s${i}`), { model: 'model-1' })) { }
          })()
          await vi.runAllTimersAsync()
          await p
        }

        // 4th request hits a live 429 — retries MAX_RATE_LIMIT_RETRIES times, then gives up.
        // Attach expect().rejects BEFORE advancing timers to prevent unhandled rejection window.
        const rawPromise = (async () => {
          for await (const _ of provider.complete(makeMessages('s3'), { model: 'model-1' })) { }
        })()
        const failExpectation = expect(rawPromise).rejects.toThrow()

        // Advance through all retry wait timers (provider 10ms delay + retry wait per attempt)
        for (let r = 0; r <= 10; r++) await vi.runAllTimersAsync()

        await failExpectation

        const learnedEvent = bus.events.find(e => e.type === 'provider:rate_learned')
        expect(learnedEvent).toBeDefined()
        expect(learnedEvent.providerId).toBe('test')
        expect(learnedEvent.model).toBe('model-1')
        expect(learnedEvent.learnedWindows.length).toBeGreaterThan(0)

        const metrics = provider.getMetrics()
        expect(Object.keys(metrics.learnedLimits).length).toBeGreaterThan(0)
      } finally {
        vi.clearAllTimers()
        vi.clearAllTimers()
        vi.useRealTimers()
      }
    })

    it('detects various rate limit error patterns', async () => {
      vi.useFakeTimers()
      try {
        const errorPatterns = [
          'HTTP 429: Too Many Requests',
          'rate limit exceeded',
          'rate_limit_exceeded',
          'resource exhausted',
          'quota exceeded',
          'throttling error',
        ]

        for (const errorMsg of errorPatterns) {
          const bus = makeMockBus()
          let callCount = 0
          const failingProvider: IProvider = {
            id: 'fail-test',
            models: ['m1'],
            async *complete(): AsyncIterable<CompletionChunk> {
              callCount++
              if (callCount > 1) throw new Error(errorMsg)
              yield { type: 'token', text: 'ok', tokensUsed: 5 }
              yield { type: 'done' }
            },
            async countTokens(): Promise<number> { return 0 },
            async ping(): Promise<boolean> { return true },
          }

          const provider = new CentralizedProvider(failingProvider, logger, bus, { errorCooldownMs: 0 })

          const p1 = (async () => {
            for await (const _ of provider.complete(makeMessages('s1'), { model: 'm1' })) { }
          })()
          await vi.runAllTimersAsync()
          await p1

          // 2nd request gets the 429-variant error; exhausts retries
          const p2 = (async () => {
            for await (const _ of provider.complete(makeMessages('s2'), { model: 'm1' })) { }
          })().catch(() => {})
          for (let r = 0; r <= 10; r++) await vi.runAllTimersAsync()
          await p2

          const learnedEvent = bus.events.find(e => e.type === 'provider:rate_learned')
          expect(learnedEvent, `Should detect rate limit from: "${errorMsg}"`).toBeDefined()
        }
      } finally {
        vi.clearAllTimers()
        vi.useRealTimers()
      }
    })

    it('tracks rates per model independently', async () => {
      vi.useFakeTimers()
      try {
        let callCount = 0
        const multiModelProvider: IProvider = {
          id: 'multi',
          models: ['fast-model', 'slow-model'],
          async *complete(_msgs: Message[], opts: CompletionOpts): AsyncIterable<CompletionChunk> {
            callCount++
            await new Promise(r => setTimeout(r, 10))
            if (opts.model === 'fast-model' && callCount > 2) {
              throw new Error('HTTP 429: rate limit exceeded')
            }
            yield { type: 'token', text: 'ok', tokensUsed: 5 }
            yield { type: 'done' }
          },
          async countTokens(): Promise<number> { return 0 },
          async ping(): Promise<boolean> { return true },
        }

        const provider = new CentralizedProvider(multiModelProvider, logger, bus, { errorCooldownMs: 0 })

        for (const s of ['s1', 's2']) {
          const p = (async () => { for await (const _ of provider.complete(makeMessages(s), { model: 'fast-model' })) { } })()
          await vi.runAllTimersAsync()
          await p
        }

        // 3rd fast-model request triggers 429 and exhausts retries
        const p3 = (async () => {
          for await (const _ of provider.complete(makeMessages('s3'), { model: 'fast-model' })) { }
        })().catch(() => {})
        for (let r = 0; r <= 10; r++) await vi.runAllTimersAsync()
        await p3

        const metrics = provider.getMetrics()
        const learnedKeys = Object.keys(metrics.learnedLimits)
        expect(learnedKeys.some(k => k.startsWith('fast-model:'))).toBe(true)
        expect(learnedKeys.some(k => k.startsWith('slow-model:'))).toBe(false)

        callCount = 0
        const p4 = (async () => { for await (const _ of provider.complete(makeMessages('s4'), { model: 'slow-model' })) { } })()
        await vi.runAllTimersAsync()
        await p4
      } finally {
        vi.clearAllTimers()
        vi.useRealTimers()
      }
    })

    it('records learned limits at multiple timescales', async () => {
      vi.useFakeTimers()
      try {
        const inner = makeRateLimitAfterNProvider('test', 5)
        const provider = new CentralizedProvider(inner, logger, bus, { errorCooldownMs: 0 })

        for (let i = 0; i < 5; i++) {
          const p = (async () => { for await (const _ of provider.complete(makeMessages(`s${i}`), { model: 'model-1' })) { } })()
          await vi.runAllTimersAsync()
          await p
        }

        const p5 = (async () => {
          for await (const _ of provider.complete(makeMessages('s5'), { model: 'model-1' })) { }
        })().catch(() => {})
        for (let r = 0; r <= 10; r++) await vi.runAllTimersAsync()
        await p5

        const learnedEvent = bus.events.find(e => e.type === 'provider:rate_learned')
        expect(learnedEvent).toBeDefined()
        expect(learnedEvent.learnedWindows.length).toBe(3)

        for (const w of learnedEvent.learnedWindows) {
          expect(w.observedCount).toBe(6)
          expect(w.safeCount).toBe(5)
        }
      } finally {
        vi.clearAllTimers()
        vi.useRealTimers()
      }
    })
  })

  describe('error handling', () => {
    it('tracks consecutive errors and emits monitoring events', async () => {
      const failingProvider: IProvider = {
        id: 'failing',
        models: ['m1'],
        async *complete(): AsyncIterable<CompletionChunk> { throw new Error('API error') },
        async countTokens(): Promise<number> { return 0 },
        async ping(): Promise<boolean> { return false },
      }

      const provider = new CentralizedProvider(failingProvider, logger, bus, { errorCooldownMs: 100 })

      await expect(async () => {
        for await (const _ of provider.complete(makeMessages(), { model: 'm1' })) { }
      }).rejects.toThrow('API error')

      const errorEvent = bus.events.find(e => e.type === 'provider:request_error')
      expect(errorEvent).toBeDefined()
      expect(errorEvent.consecutiveErrors).toBe(1)
    })

    it('enforces error cooldown with exponential backoff', async () => {
      const failingProvider: IProvider = {
        id: 'failing',
        models: ['m1'],
        async *complete(): AsyncIterable<CompletionChunk> { throw new Error('API error') },
        async countTokens(): Promise<number> { return 0 },
        async ping(): Promise<boolean> { return false },
      }

      const provider = new CentralizedProvider(failingProvider, logger, bus, { errorCooldownMs: 100 })

      await expect(async () => {
        for await (const _ of provider.complete(makeMessages('s1'), { model: 'm1' })) { }
      }).rejects.toThrow()

      const retryPromise = (async () => {
        for await (const _ of provider.complete(makeMessages('s2'), { model: 'm1' })) { }
      })()

      await expect(retryPromise).rejects.toThrow(/cooling down/)

      await new Promise(r => setTimeout(r, 150))

      await expect(async () => {
        for await (const _ of provider.complete(makeMessages('s3'), { model: 'm1' })) { }
      }).rejects.toThrow('API error')
    })

    it('resets error state when resetErrorState is called', async () => {
      const failingProvider: IProvider = {
        id: 'failing',
        models: ['m1'],
        async *complete(): AsyncIterable<CompletionChunk> { throw new Error('API error') },
        async countTokens(): Promise<number> { return 0 },
        async ping(): Promise<boolean> { return false },
      }

      const provider = new CentralizedProvider(failingProvider, logger, bus, { errorCooldownMs: 1000 })

      await expect(async () => {
        for await (const _ of provider.complete(makeMessages('s1'), { model: 'm1' })) { }
      }).rejects.toThrow()

      expect(provider.getMetrics().consecutiveErrors).toBe(1)

      provider.resetErrorState()
      expect(provider.getMetrics().consecutiveErrors).toBe(0)

      const resetEvent = bus.events.find(e => e.type === 'provider:error_reset')
      expect(resetEvent).toBeDefined()
      expect(resetEvent.providerId).toBe('failing')
    })
  })

  describe('metrics', () => {
    it('accumulates total request and token counts', async () => {
      const inner = makeMockProvider('test')
      const provider = new CentralizedProvider(inner, logger, bus, { errorCooldownMs: 0 })

      for await (const _ of provider.complete(makeMessages('s1'), { model: 'm1' })) { }
      for await (const _ of provider.complete(makeMessages('s2'), { model: 'm1' })) { }

      const metrics = provider.getMetrics()
      expect(metrics.totalRequests).toBe(2)
      expect(metrics.totalTokens).toBeGreaterThan(0)
    })

    it('tracks in-flight request count', async () => {
      const inner = makeMockProvider('test', ['slow'])
      const provider = new CentralizedProvider(inner, logger, bus, { errorCooldownMs: 0 })

      expect(provider.getMetrics().inFlightCount).toBe(0)

      const iterator = provider.complete(makeMessages('s1'), { model: 'm1' })
      const asyncIter = iterator[Symbol.asyncIterator]()
      const firstChunkPromise = asyncIter.next()
      await new Promise(r => setTimeout(r, 10))
      expect(provider.getMetrics().inFlightCount).toBe(1)

      await firstChunkPromise
      for await (const _ of { [Symbol.asyncIterator]: () => asyncIter }) { }
      expect(provider.getMetrics().inFlightCount).toBe(0)
    })

    it('exposes current request rates per model and timescale', async () => {
      const inner = makeMockProvider('test')
      const provider = new CentralizedProvider(inner, logger, bus, { errorCooldownMs: 0 })

      expect(provider.getMetrics().currentRates).toEqual({})

      for await (const _ of provider.complete(makeMessages('s1'), { model: 'm1' })) { }

      const rates = provider.getMetrics().currentRates
      expect(rates['m1']).toBeDefined()
      expect(rates['m1']['1m']).toBe(1)
      expect(rates['m1']['10m']).toBe(1)
      expect(rates['m1']['1h']).toBe(1)
    })

    it('resets all metrics when resetAll is called', async () => {
      const inner = makeMockProvider('test')
      const provider = new CentralizedProvider(inner, logger, bus, { errorCooldownMs: 0 })

      for await (const _ of provider.complete(makeMessages('s1'), { model: 'm1' })) { }
      expect(provider.getMetrics().totalRequests).toBe(1)

      provider.resetAll()

      const metrics = provider.getMetrics()
      expect(metrics.totalRequests).toBe(0)
      expect(metrics.totalTokens).toBe(0)
      expect(metrics.totalErrors).toBe(0)
    })
  })

  describe('abortSession', () => {
    it('can abort an in-flight request', async () => {
      const inner = makeMockProvider('test', ['slow'])
      const provider = new CentralizedProvider(inner, logger, bus, { errorCooldownMs: 0 })

      const messages: Message[] = [
        { role: 'system', content: 'id: bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb' },
        { role: 'user', content: 'Hello' },
      ]

      const iterator = provider.complete(messages, { model: 'm1' })
      const asyncIter = iterator[Symbol.asyncIterator]()
      const firstChunkPromise = asyncIter.next()
      await new Promise(r => setTimeout(r, 20))

      expect(provider.getMetrics().inFlightCount).toBe(1)

      const aborted = provider.abortSession('sess_bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb')
      expect(aborted).toBe(true)

      await firstChunkPromise
      for await (const _ of { [Symbol.asyncIterator]: () => asyncIter }) { }

      const abortEvent = bus.events.find(e => e.type === 'provider:request_aborted')
      expect(abortEvent).toBeDefined()
    })

    it('returns false for non-existent session', () => {
      const inner = makeMockProvider('test')
      const provider = new CentralizedProvider(inner, logger, bus)

      const aborted = provider.abortSession('non-existent')
      expect(aborted).toBe(false)
    })

    it('exposes in-flight request details via getInFlight', async () => {
      const inner = makeMockProvider('test', ['slow'])
      const provider = new CentralizedProvider(inner, logger, bus, { errorCooldownMs: 0 })

      const messages: Message[] = [
        { role: 'system', content: 'id: test-session-123' },
        { role: 'user', content: 'Hello' },
      ]

      const iterator = provider.complete(messages, { model: 'm1' })
      const asyncIter = iterator[Symbol.asyncIterator]()
      const firstChunkPromise = asyncIter.next()
      await new Promise(r => setTimeout(r, 20))

      const inFlight = provider.getInFlight()
      expect(inFlight.length).toBe(1)
      expect(inFlight[0].sessionId).toBe('sess_123')
      expect(inFlight[0].providerId).toBe('test')

      await firstChunkPromise
      for await (const _ of { [Symbol.asyncIterator]: () => asyncIter }) { }
    })
  })

  describe('ping bypass', () => {
    it('does not apply rate limiting to ping', async () => {
      const inner = makeMockProvider('test')
      inner.ping = vi.fn().mockResolvedValue(true)

      const provider = new CentralizedProvider(inner, logger, bus, { errorCooldownMs: 0 })

      for await (const _ of provider.complete(makeMessages('s1'), { model: 'm1' })) { }

      const result = await provider.ping()
      expect(result).toBe(true)
    })
  })

  describe('edge cases', () => {
    it('handles empty message arrays', async () => {
      const inner = makeMockProvider('test')
      const provider = new CentralizedProvider(inner, logger, bus)

      const chunks: CompletionChunk[] = []
      for await (const c of provider.complete([], { model: 'model-1' })) { chunks.push(c) }

      expect(chunks).toHaveLength(2)
      expect(inner.callCount).toBe(1)
    })

    it('clears learned limits when resetRateLimitHistory is called', async () => {
      vi.useFakeTimers()
      try {
        const inner = makeRateLimitAfterNProvider('test', 2)
        const provider = new CentralizedProvider(inner, logger, bus, { errorCooldownMs: 0 })

        for (const s of ['s1', 's2']) {
          const p = (async () => { for await (const _ of provider.complete(makeMessages(s), { model: 'model-1' })) { } })()
          await vi.runAllTimersAsync()
          await p
        }

        // 3rd request hits 429 — exhaust retries to populate learnedLimits
        const p3 = (async () => {
          for await (const _ of provider.complete(makeMessages('s3'), { model: 'model-1' })) { }
        })().catch(() => {})
        for (let r = 0; r <= 10; r++) await vi.runAllTimersAsync()
        await p3

        expect(Object.keys(provider.getMetrics().learnedLimits).length).toBeGreaterThan(0)

        provider.resetRateLimitHistory()

        expect(Object.keys(provider.getMetrics().learnedLimits).length).toBe(0)
        expect(provider.getMetrics().currentRates).toEqual({})
      } finally {
        vi.clearAllTimers()
        vi.useRealTimers()
      }
    })

    it('passes through stats from wrapped provider', async () => {
      const inner = makeMockProvider('test')
      ;(inner as any).getStats = () => ({ activeRequests: 5, queueDepth: 2 })

      const provider = new CentralizedProvider(inner, logger, bus)
      const stats = provider.getStats()
      expect(stats).toEqual({ activeRequests: 5, queueDepth: 2 })
    })

    it('returns null for stats when not available', () => {
      const inner = makeMockProvider('test')
      const provider = new CentralizedProvider(inner, logger, bus)
      expect(provider.getStats()).toBeNull()
    })

    it('passes through active count from wrapped provider', () => {
      const inner = makeMockProvider('test')
      ;(inner as any).getActiveCount = () => 3

      const provider = new CentralizedProvider(inner, logger, bus)
      expect(provider.getActiveCount()).toBe(3)
    })

    it('returns 1 for active count when not available', () => {
      const inner = makeMockProvider('test')
      const provider = new CentralizedProvider(inner, logger, bus)
      expect(provider.getActiveCount()).toBe(1)
    })

    it('uses sensible default config (error cooldown only)', () => {
      const inner = makeMockProvider('test')
      const provider = new CentralizedProvider(inner, logger, bus)

      const metrics = provider.getMetrics()
      expect(metrics.globalConfig).toMatchObject({
        errorCooldownMs: 5_000,
      })
      expect(metrics.globalConfig).not.toHaveProperty('maxConcurrent')
      expect(metrics.globalConfig).not.toHaveProperty('maxRequests')
      expect(metrics.globalConfig).not.toHaveProperty('windowMs')
    })

    it('applies config-driven overrides via wrapProvidersWithCentralized', () => {
      const config = {
        get: (key: string, fallback: number) => {
          const values: Record<string, number> = {
            'providers.default.errorCooldownMs': 7_500,
            'providers.test.errorCooldownMs': 2_000,
          }
          return values[key] ?? fallback
        },
      }

      const wrapped = wrapProvidersWithCentralized(
        new Map([['test', makeMockProvider('test')]]),
        logger,
        bus,
        config as any,
      )

      const metrics = wrapped.get('test')?.getMetrics()
      expect(metrics?.globalConfig).toMatchObject({
        errorCooldownMs: 2_000,
      })
    })
  })
})
