/**
 * FallbackManager Tests
 *
 * Tests for the ModelPool FallbackManager with CircuitBreaker integration.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { FallbackManager } from '../src/fallback-manager.js'
import type { FallbackChain } from '../src/types.js'
import type { ILogger, IEventBus } from '@cassicore/foundation'

// Mock logger
const createMockLogger = (): ILogger => ({
  debug: vi.fn(),
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
  child: (component: string) => createMockLogger(),
})

// Mock event bus
const createMockEventBus = (): IEventBus => ({
  emit: vi.fn().mockResolvedValue(undefined),
  on: vi.fn().mockReturnValue(() => {}),
  once: vi.fn(),
  off: vi.fn(),
  listenerCount: vi.fn().mockReturnValue(0),
  onAll: vi.fn().mockReturnValue(() => {}),
})

describe('FallbackManager', () => {
  let logger: ILogger
  let eventBus: IEventBus
  let chains: FallbackChain[]

  beforeEach(() => {
    logger = createMockLogger()
    eventBus = createMockEventBus()
    chains = [
      {
        slotName: 'yang',
        chain: [
          { role: 'yang', provider: 'github-copilot', model: 'gpt-4o', priority: 10 },
          { role: 'yang', provider: 'openai', model: 'gpt-4', priority: 5 },
          { role: 'yang', provider: 'anthropic', model: 'claude-3', priority: 1 },
        ],
        triggers: ['rate_limit', 'timeout', 'model_unavailable', 'budget_exceeded', 'error'],
      },
      {
        slotName: 'yin',
        chain: [
          { role: 'yin', provider: 'github-copilot', model: 'gpt-4o-mini', priority: 10 },
          { role: 'yin', provider: 'openai', model: 'gpt-3.5-turbo', priority: 5 },
        ],
        triggers: ['rate_limit', 'timeout', 'error'],
      },
    ]
  })

  describe('constructor', () => {
    it('initializes with provided chains', () => {
      const manager = new FallbackManager({ chains, logger, eventBus })
      expect(manager).toBeDefined()
    })

    it('sorts chains by priority (descending)', () => {
      const manager = new FallbackManager({ chains, logger, eventBus })
      const state = manager.getSlotState('yang')
      expect(state).toBeDefined()
      expect(state!.chainLength).toBe(3)
    })

    it('uses default circuit breaker config when not provided', () => {
      const manager = new FallbackManager({ chains, logger, eventBus })
      expect(manager).toBeDefined()
    })

    it('uses custom circuit breaker config when provided', () => {
      const manager = new FallbackManager({
        chains,
        logger,
        eventBus,
        circuitBreakerConfig: {
          failureThreshold: 3,
          resetTimeoutMs: 30000,
          halfOpenMaxAttempts: 2,
        },
      })
      expect(manager).toBeDefined()
    })

    it('uses custom success reset threshold when provided', () => {
      const manager = new FallbackManager({
        chains,
        logger,
        eventBus,
        successResetThreshold: 5,
      })
      expect(manager).toBeDefined()
    })
  })

  describe('getNextAvailable', () => {
    it('returns first model in chain for new slot', () => {
      const manager = new FallbackManager({ chains, logger, eventBus })
      const slot = manager.getNextAvailable('yang')
      expect(slot).toBeDefined()
      expect(slot?.provider).toBe('github-copilot')
      expect(slot?.model).toBe('gpt-4o')
      expect(slot?.priority).toBe(10)
    })

    it('returns null for non-existent slot', () => {
      const manager = new FallbackManager({ chains, logger, eventBus })
      const slot = manager.getNextAvailable('nonexistent')
      expect(slot).toBeNull()
    })

    it('skips models with open circuit breakers', () => {
      const manager = new FallbackManager({
        chains,
        logger,
        eventBus,
        circuitBreakerConfig: { failureThreshold: 2 },
      })

      // Force circuit breaker open for first model
      manager.reportFailure('yang', 'github-copilot', 'gpt-4o', 'error')
      manager.reportFailure('yang', 'github-copilot', 'gpt-4o', 'error')

      const slot = manager.getNextAvailable('yang')
      expect(slot).toBeDefined()
      expect(slot?.provider).toBe('openai')
      expect(slot?.model).toBe('gpt-4')
    })

    it('returns null when all models have open circuits', () => {
      const manager = new FallbackManager({
        chains: [
          {
            slotName: 'test',
            chain: [
              { role: 'test', provider: 'p1', model: 'm1', priority: 10 },
              { role: 'test', provider: 'p2', model: 'm2', priority: 5 },
            ],
            triggers: ['error'],
          },
        ],
        logger,
        eventBus,
        circuitBreakerConfig: { failureThreshold: 1 },
      })

      // Open all circuits
      manager.reportFailure('test', 'p1', 'm1', 'error')
      manager.reportFailure('test', 'p2', 'm2', 'error')

      const slot = manager.getNextAvailable('test')
      expect(slot).toBeNull()
    })

    it('returns null after chain is exhausted', () => {
      const manager = new FallbackManager({
        chains: [
          {
            slotName: 'single',
            chain: [{ role: 'single', provider: 'p1', model: 'm1', priority: 10 }],
            triggers: ['error'],
          },
        ],
        logger,
        eventBus,
        circuitBreakerConfig: { failureThreshold: 1 },
      })

      manager.reportFailure('single', 'p1', 'm1', 'error')
      const slot = manager.getNextAvailable('single')
      expect(slot).toBeNull()
    })
  })

  describe('reportFailure', () => {
    it('advances chain on failure with trigger reason', () => {
      const manager = new FallbackManager({ chains, logger, eventBus })

      // Start with first model
      const first = manager.getNextAvailable('yang')
      expect(first?.model).toBe('gpt-4o')

      // Report failure
      manager.reportFailure('yang', 'github-copilot', 'gpt-4o', 'timeout')

      // Should advance to next model
      const second = manager.getNextAvailable('yang')
      expect(second?.model).toBe('gpt-4')
    })

    it('does not advance chain on non-trigger reason', () => {
      const manager = new FallbackManager({ chains, logger, eventBus })

      // Start with first model
      const first = manager.getNextAvailable('yang')
      expect(first?.model).toBe('gpt-4o')

      // Report failure with non-trigger reason (circuit_open is not in triggers)
      manager.reportFailure('yang', 'github-copilot', 'gpt-4o', 'circuit_open')

      // Should stay on same model
      const second = manager.getNextAvailable('yang')
      expect(second?.model).toBe('gpt-4o')
    })

    it('emits fallback:triggered event when advancing chain', () => {
      const manager = new FallbackManager({ chains, logger, eventBus })

      manager.reportFailure('yang', 'github-copilot', 'gpt-4o', 'timeout')

      expect(eventBus.emit).toHaveBeenCalled()
      const event = (eventBus.emit as any).mock.calls[0][0]
      expect(event.type).toBe('fallback:triggered')
      expect(event.slotName).toBe('yang')
      expect(event.fromProvider).toBe('github-copilot')
      expect(event.fromModel).toBe('gpt-4o')
      expect(event.toProvider).toBe('openai')
      expect(event.toModel).toBe('gpt-4')
      expect(event.reason).toBe('timeout')
    })

    it('emits event with chainExhausted flag when at end of chain', () => {
      const manager = new FallbackManager({
        chains: [
          {
            slotName: 'single',
            chain: [{ role: 'single', provider: 'p1', model: 'm1', priority: 10 }],
            triggers: ['error'],
          },
        ],
        logger,
        eventBus,
      })

      manager.reportFailure('single', 'p1', 'm1', 'error')

      expect(eventBus.emit).toHaveBeenCalled()
      const event = (eventBus.emit as any).mock.calls[0][0]
      expect(event.type).toBe('fallback:triggered')
      expect(event.chainExhausted).toBe(true)
    })

    it('tracks consecutive failures', () => {
      const manager = new FallbackManager({ chains, logger, eventBus })

      manager.reportFailure('yang', 'github-copilot', 'gpt-4o', 'timeout')
      manager.reportFailure('yang', 'openai', 'gpt-4', 'timeout')

      const state = manager.getSlotState('yang')
      expect(state?.consecutiveFailures).toBe(2)
    })
  })

  describe('reportSuccess', () => {
    it('resets consecutive failures', () => {
      const manager = new FallbackManager({ chains, logger, eventBus })

      manager.reportFailure('yang', 'github-copilot', 'gpt-4o', 'timeout')
      manager.reportFailure('yang', 'openai', 'gpt-4', 'timeout')
      manager.reportSuccess('yang', 'openai', 'gpt-4')

      const state = manager.getSlotState('yang')
      expect(state?.consecutiveFailures).toBe(0)
      expect(state?.consecutiveSuccesses).toBe(1)
    })

    it('resets chain to index 0 after N consecutive successes', () => {
      const manager = new FallbackManager({
        chains,
        logger,
        eventBus,
        successResetThreshold: 2,
      })

      // Advance chain
      manager.reportFailure('yang', 'github-copilot', 'gpt-4o', 'timeout')
      let slot = manager.getNextAvailable('yang')
      expect(slot?.model).toBe('gpt-4')

      // Report successes
      manager.reportSuccess('yang', 'openai', 'gpt-4')
      manager.reportSuccess('yang', 'openai', 'gpt-4')

      // Chain should reset
      const resetSlot = manager.getNextAvailable('yang')
      expect(resetSlot?.model).toBe('gpt-4o')

      const state = manager.getSlotState('yang')
      expect(state?.currentIndex).toBe(0)
    })

    it('does not reset chain before threshold', () => {
      const manager = new FallbackManager({
        chains,
        logger,
        eventBus,
        successResetThreshold: 3,
      })

      // Advance chain
      manager.reportFailure('yang', 'github-copilot', 'gpt-4o', 'timeout')

      // Report only 2 successes (threshold is 3)
      manager.reportSuccess('yang', 'openai', 'gpt-4')
      manager.reportSuccess('yang', 'openai', 'gpt-4')

      // Chain should NOT reset yet
      const slot = manager.getNextAvailable('yang')
      expect(slot?.model).toBe('gpt-4')

      const state = manager.getSlotState('yang')
      expect(state?.currentIndex).toBeGreaterThan(0)
    })
  })

  describe('getSlotState', () => {
    it('returns current state for slot', () => {
      const manager = new FallbackManager({ chains, logger, eventBus })

      const state = manager.getSlotState('yang')
      expect(state).toBeDefined()
      expect(state?.currentIndex).toBe(0)
      expect(state?.consecutiveFailures).toBe(0)
      expect(state?.consecutiveSuccesses).toBe(0)
      expect(state?.chainLength).toBe(3)
      expect(state?.lastUsedModel).toBeNull()
    })

    it('returns null for non-existent slot', () => {
      const manager = new FallbackManager({ chains, logger, eventBus })

      const state = manager.getSlotState('nonexistent')
      expect(state).toBeNull()
    })

    it('tracks lastUsedModel', () => {
      const manager = new FallbackManager({ chains, logger, eventBus })

      manager.getNextAvailable('yang')
      let state = manager.getSlotState('yang')
      expect(state?.lastUsedModel).toBe('github-copilot:gpt-4o')

      manager.reportFailure('yang', 'github-copilot', 'gpt-4o', 'timeout')
      manager.getNextAvailable('yang')
      state = manager.getSlotState('yang')
      expect(state?.lastUsedModel).toBe('openai:gpt-4')
    })
  })

  describe('getCircuitState', () => {
    it('returns circuit state for provider:model', () => {
      const manager = new FallbackManager({ chains, logger, eventBus })

      const state = manager.getCircuitState('github-copilot', 'gpt-4o')
      expect(state).toBe('closed')
    })

    it('returns null for non-existent circuit', () => {
      const manager = new FallbackManager({ chains, logger, eventBus })

      const state = manager.getCircuitState('nonexistent', 'model')
      expect(state).toBeNull()
    })

    it('returns open state after failures', () => {
      const manager = new FallbackManager({
        chains,
        logger,
        eventBus,
        circuitBreakerConfig: { failureThreshold: 2 },
      })

      manager.reportFailure('yang', 'github-copilot', 'gpt-4o', 'error')
      manager.reportFailure('yang', 'github-copilot', 'gpt-4o', 'error')

      const state = manager.getCircuitState('github-copilot', 'gpt-4o')
      expect(state).toBe('open')
    })
  })

  describe('resetCircuit', () => {
    it('manually resets circuit to closed', () => {
      const manager = new FallbackManager({
        chains,
        logger,
        eventBus,
        circuitBreakerConfig: { failureThreshold: 1 },
      })

      // Open circuit
      manager.reportFailure('yang', 'github-copilot', 'gpt-4o', 'error')
      expect(manager.getCircuitState('github-copilot', 'gpt-4o')).toBe('open')

      // Reset circuit
      manager.resetCircuit('github-copilot', 'gpt-4o')
      expect(manager.getCircuitState('github-copilot', 'gpt-4o')).toBe('closed')
    })
  })

  describe('resetChain', () => {
    it('manually resets chain to index 0', () => {
      const manager = new FallbackManager({ chains, logger, eventBus })

      // Advance chain
      manager.reportFailure('yang', 'github-copilot', 'gpt-4o', 'timeout')
      let state = manager.getSlotState('yang')
      expect(state?.currentIndex).toBeGreaterThan(0)

      // Reset chain
      manager.resetChain('yang')
      state = manager.getSlotState('yang')
      expect(state?.currentIndex).toBe(0)
      expect(state?.consecutiveFailures).toBe(0)
      expect(state?.consecutiveSuccesses).toBe(0)
    })
  })

  describe('dispose', () => {
    it('clears all internal state', () => {
      const manager = new FallbackManager({ chains, logger, eventBus })

      // Use the manager
      manager.getNextAvailable('yang')
      manager.reportFailure('yang', 'github-copilot', 'gpt-4o', 'timeout')

      // Dispose
      manager.dispose()

      // Should return null after disposal
      const slot = manager.getNextAvailable('yang')
      expect(slot).toBeNull()

      const state = manager.getSlotState('yang')
      expect(state).toBeNull()
    })

    it('can be called multiple times safely', () => {
      const manager = new FallbackManager({ chains, logger, eventBus })
      manager.dispose()
      expect(() => manager.dispose()).not.toThrow()
    })

    it('logs warning on operations after disposal', () => {
      const manager = new FallbackManager({ chains, logger, eventBus })
      manager.dispose()

      manager.getNextAvailable('yang')
      expect(logger.warn).toHaveBeenCalled()
    })
  })

  describe('circuit breaker integration', () => {
    it('opens circuit after failureThreshold consecutive failures', () => {
      const manager = new FallbackManager({
        chains,
        logger,
        eventBus,
        circuitBreakerConfig: { failureThreshold: 3 },
      })

      // Should be closed initially
      expect(manager.getCircuitState('github-copilot', 'gpt-4o')).toBe('closed')

      // Record failures
      manager.reportFailure('yang', 'github-copilot', 'gpt-4o', 'error')
      expect(manager.getCircuitState('github-copilot', 'gpt-4o')).toBe('closed')

      manager.reportFailure('yang', 'github-copilot', 'gpt-4o', 'error')
      expect(manager.getCircuitState('github-copilot', 'gpt-4o')).toBe('closed')

      // Third failure should open circuit
      manager.reportFailure('yang', 'github-copilot', 'gpt-4o', 'error')
      expect(manager.getCircuitState('github-copilot', 'gpt-4o')).toBe('open')
    })

    it('emits circuit:stateChange event on state transition', () => {
      const manager = new FallbackManager({
        chains,
        logger,
        eventBus,
        circuitBreakerConfig: { failureThreshold: 1 },
      })

      manager.reportFailure('yang', 'github-copilot', 'gpt-4o', 'error')

      expect(eventBus.emit).toHaveBeenCalled()
      const calls = (eventBus.emit as any).mock.calls
      const circuitEvent = calls.find((c: any) => c[0].type === 'circuit:stateChange')
      expect(circuitEvent).toBeDefined()
      expect(circuitEvent[0].provider).toBe('github-copilot')
      expect(circuitEvent[0].model).toBe('gpt-4o')
      expect(circuitEvent[0].state).toBe('open')
      expect(circuitEvent[0].previousState).toBe('closed')
    })
  })

  describe('trigger conditions', () => {
    it('handles all trigger types', () => {
      const triggers: Array<'rate_limit' | 'timeout' | 'model_unavailable' | 'budget_exceeded' | 'circuit_open' | 'error'> = [
        'rate_limit',
        'timeout',
        'model_unavailable',
        'budget_exceeded',
        'error',
      ]

      for (const trigger of triggers) {
        const manager = new FallbackManager({
          chains: [
            {
              slotName: 'test',
              chain: [
                { role: 'test', provider: 'p1', model: 'm1', priority: 10 },
                { role: 'test', provider: 'p2', model: 'm2', priority: 5 },
              ],
              triggers: [trigger],
            },
          ],
          logger,
          eventBus,
        })

        const first = manager.getNextAvailable('test')
        expect(first?.model).toBe('m1')

        manager.reportFailure('test', 'p1', 'm1', trigger)

        const second = manager.getNextAvailable('test')
        expect(second?.model).toBe('m2')
      }
    })
  })
})
