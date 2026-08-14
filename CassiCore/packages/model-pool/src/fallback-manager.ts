/**
 * FallbackManager for ModelPool
 *
 * Manages fallback chains per slot with circuit breaker integration.
 * Each named slot (yang, yin, executive, thinker) has its own FallbackChain
 * with ordered ModelSlotConfig[] sorted by priority.
 *
 * Features:
 * - Per-slot fallback chain with position tracking
 * - CircuitBreaker per provider:model pair for fast-fail
 * - Trigger-based chain advancement (rate_limit, timeout, model_unavailable, etc.)
 * - Success-based chain reset after N consecutive successes
 * - Event emission for observability
 */

import type { ModelSlotConfig, FallbackChain } from './types.js'
import type { ILogger, IEventBus } from '../../types/interfaces.js'
import { CircuitBreaker, CircuitState, CircuitOpenError } from '../utils/circuit-breaker.js'

/**
 * Configuration for FallbackManager
 */
export interface FallbackManagerConfig {
  /** Fallback chain definitions */
  chains: FallbackChain[]
  /** Circuit breaker configuration */
  circuitBreakerConfig?: {
    failureThreshold?: number
    resetTimeoutMs?: number
    halfOpenMaxAttempts?: number
  }
  /** Number of consecutive successes required to reset chain to index 0 */
  successResetThreshold?: number
  /** Logger for observability */
  logger: ILogger
  /** Event bus for emitting events */
  eventBus: IEventBus
}

/**
 * Internal state for a slot
 */
interface SlotState {
  /** Current position in the fallback chain */
  currentIndex: number
  /** Consecutive failures count */
  consecutiveFailures: number
  /** Consecutive successes count */
  consecutiveSuccesses: number
  /** Last model used (provider:model) */
  lastUsedModel: string | null
}

/**
 * FallbackManager manages fallback chains per slot with circuit breaker integration.
 *
 * @example
 * ```typescript
 * const manager = new FallbackManager({
 *   chains: [
 *     {
 *       slotName: 'yang',
 *       chain: [
 *         { role: 'yang', provider: 'github-copilot', model: 'gpt-4o', priority: 10 },
 *         { role: 'yang', provider: 'openai', model: 'gpt-4', priority: 5 },
 *       ],
 *       triggers: ['rate_limit', 'timeout', 'model_unavailable'],
 *     },
 *   ],
 *   logger: logger.child('FallbackManager'),
 *   eventBus: eventBus,
 * })
 *
 * const slot = manager.getNextAvailable('yang')
 * if (slot) {
 *   try {
 *     await useModel(slot)
 *     manager.reportSuccess('yang', slot.provider, slot.model)
 *   } catch (error) {
 *     manager.reportFailure('yang', slot.provider, slot.model, 'timeout')
 *   }
 * }
 * ```
 */
export class FallbackManager {
  private chains: Map<string, FallbackChain>
  private slotStates: Map<string, SlotState>
  private circuitBreakers: Map<string, CircuitBreaker<void>>
  private config: Required<Omit<FallbackManagerConfig, 'circuitBreakerConfig'>> & {
    circuitBreakerConfig: Required<NonNullable<FallbackManagerConfig['circuitBreakerConfig']>>
  }
  private disposed = false

  constructor(config: FallbackManagerConfig) {
    this.chains = new Map()
    this.slotStates = new Map()
    this.circuitBreakers = new Map()
    this.config = {
      chains: config.chains,
      circuitBreakerConfig: {
        failureThreshold: config.circuitBreakerConfig?.failureThreshold ?? 5,
        resetTimeoutMs: config.circuitBreakerConfig?.resetTimeoutMs ?? 60000,
        halfOpenMaxAttempts: config.circuitBreakerConfig?.halfOpenMaxAttempts ?? 3,
      },
      successResetThreshold: config.successResetThreshold ?? 3,
      logger: config.logger,
      eventBus: config.eventBus,
    }

    // Initialize chains and slot states
    for (const chain of config.chains) {
      this.chains.set(chain.slotName, chain)
      // Sort chain by priority (descending)
      chain.chain.sort((a, b) => b.priority - a.priority)
      this.slotStates.set(chain.slotName, {
        currentIndex: 0,
        consecutiveFailures: 0,
        consecutiveSuccesses: 0,
        lastUsedModel: null,
      })
    }

    this.config.logger.info('FallbackManager initialized', {
      chainCount: config.chains.length,
      slots: config.chains.map((c) => c.slotName),
    })
  }

  /**
   * Get the next available model slot for a given slot name.
   * Iterates through the fallback chain from current position,
   * skipping models with open circuit breakers.
   *
   * @param slotName - Name of the slot (e.g., "yang", "yin")
   * @returns First available ModelSlotConfig or null if chain exhausted
   */
  getNextAvailable(slotName: string): ModelSlotConfig | null {
    if (this.disposed) {
      this.config.logger.warn('getNextAvailable called on disposed FallbackManager')
      return null
    }

    const chain = this.chains.get(slotName)
    if (!chain) {
      this.config.logger.warn(`No fallback chain found for slot: ${slotName}`)
      return null
    }

    const state = this.slotStates.get(slotName)
    if (!state) {
      this.config.logger.warn(`No state found for slot: ${slotName}`)
      return null
    }

    // Iterate from current index to end of chain
    for (let i = state.currentIndex; i < chain.chain.length; i++) {
      const slotConfig = chain.chain[i]
      const circuitKey = this.getCircuitBreakerKey(slotConfig.provider, slotConfig.model)
      const circuitBreaker = this.getOrCreateCircuitBreaker(circuitKey)

      const circuitState = circuitBreaker.getState()

      // Skip if circuit is open
      if (circuitState === CircuitState.OPEN) {
        this.config.logger.debug(`Skipping ${slotConfig.provider}:${slotConfig.model} - circuit is ${circuitState}`, {
          slotName,
          circuitKey,
        })
        continue
      }

      // Found an available model
      state.lastUsedModel = circuitKey
      this.config.logger.debug(`Selected model for ${slotName}`, {
        provider: slotConfig.provider,
        model: slotConfig.model,
        priority: slotConfig.priority,
        chainPosition: i,
      })

      return slotConfig
    }

    // Chain exhausted
    this.config.logger.warn(`No available models in fallback chain for slot: ${slotName}`, {
      chainLength: chain.chain.length,
      currentIndex: state.currentIndex,
    })

    return null
  }

  /**
   * Report a failure for a specific model.
   * Advances the fallback chain and potentially opens the circuit breaker.
   *
   * @param slotName - Name of the slot
   * @param provider - Provider ID
   * @param model - Model ID
   * @param reason - Failure reason (rate_limit, timeout, model_unavailable, budget_exceeded, circuit_open, error)
   */
  reportFailure(
    slotName: string,
    provider: string,
    model: string,
    reason: 'rate_limit' | 'timeout' | 'model_unavailable' | 'budget_exceeded' | 'circuit_open' | 'error',
  ): void {
    if (this.disposed) {
      this.config.logger.warn('reportFailure called on disposed FallbackManager')
      return
    }

    const chain = this.chains.get(slotName)
    if (!chain) {
      this.config.logger.warn(`No fallback chain found for slot: ${slotName}`)
      return
    }

    const state = this.slotStates.get(slotName)
    if (!state) {
      this.config.logger.warn(`No state found for slot: ${slotName}`)
      return
    }

    // Record failure in circuit breaker first (always record, regardless of trigger)
    const circuitKey = this.getCircuitBreakerKey(provider, model)
    const circuitBreaker = this.getOrCreateCircuitBreaker(circuitKey)
    const previousCircuitState = circuitBreaker.getState()
    
    // Use synchronous recordFailure method
    circuitBreaker.recordFailure()
    
    // Check if circuit state changed and emit event
    const newCircuitState = circuitBreaker.getState()
    if (newCircuitState !== previousCircuitState) {
      this.config.eventBus
        .emit({
          type: 'circuit:stateChange',
          timestamp: new Date(),
          provider,
          model,
          state: newCircuitState,
          previousState: previousCircuitState,
        })
        .catch((err) => {
          this.config.logger.error('Failed to emit circuit:stateChange event', { error: err })
        })
    }

    // Check if this trigger should advance the chain
    if (!chain.triggers.includes(reason)) {
      this.config.logger.debug(`Failure reason "${reason}" does not trigger fallback for slot: ${slotName}`)
      return
    }

    // Only advance currentIndex if the failed model is at the current index
    const currentSlot = chain.chain[state.currentIndex]
    const failedModelIsCurrent = currentSlot.provider === provider && currentSlot.model === model

    if (!failedModelIsCurrent) {
      // The failed model is not the current one, don't advance the chain
      // This can happen when reporting failures for models that were already skipped
      this.config.logger.debug(`Failed model ${provider}:${model} is not at current index ${state.currentIndex}, not advancing chain`)
      return
    }

    // Track consecutive failures
    state.consecutiveFailures++
    state.consecutiveSuccesses = 0

    // Store the model we're failing from for event emission
    const fromModel = state.lastUsedModel

    // Advance to next model in chain
    const previousIndex = state.currentIndex
    if (state.currentIndex < chain.chain.length - 1) {
      state.currentIndex++
      this.config.logger.info(`Advanced fallback chain for ${slotName}`, {
        fromIndex: previousIndex,
        toIndex: state.currentIndex,
        reason,
        consecutiveFailures: state.consecutiveFailures,
      })

      // Emit fallback:triggered event
      const fromParts = fromModel?.split(':') ?? [provider, model]
      const nextSlot = chain.chain[state.currentIndex]
      this.config.eventBus
        .emit({
          type: 'fallback:triggered',
          timestamp: new Date(),
          slotName,
          fromProvider: fromParts[0],
          fromModel: fromParts[1],
          toProvider: nextSlot.provider,
          toModel: nextSlot.model,
          reason,
          consecutiveFailures: state.consecutiveFailures,
        })
        .catch((err) => {
          this.config.logger.error('Failed to emit fallback:triggered event', { error: err })
        })
    } else {
      // Chain exhausted
      this.config.logger.warn(`Fallback chain exhausted for ${slotName}`, {
        currentIndex: state.currentIndex,
        reason,
        consecutiveFailures: state.consecutiveFailures,
      })

      // Emit fallback:triggered event with null target
      const fromParts = fromModel?.split(':') ?? [provider, model]
      this.config.eventBus
        .emit({
          type: 'fallback:triggered',
          timestamp: new Date(),
          slotName,
          fromProvider: fromParts[0],
          fromModel: fromParts[1],
          toProvider: null,
          toModel: null,
          reason,
          consecutiveFailures: state.consecutiveFailures,
          chainExhausted: true,
        })
        .catch((err) => {
          this.config.logger.error('Failed to emit fallback:triggered event', { error: err })
        })
    }
  }

  /**
   * Report a success for a specific model.
   * Resets failure counters and potentially resets the chain to index 0
   * after N consecutive successes.
   *
   * @param slotName - Name of the slot
   * @param provider - Provider ID
   * @param model - Model ID
   */
  reportSuccess(slotName: string, provider: string, model: string): void {
    if (this.disposed) {
      this.config.logger.warn('reportSuccess called on disposed FallbackManager')
      return
    }

    const state = this.slotStates.get(slotName)
    if (!state) {
      this.config.logger.warn(`No state found for slot: ${slotName}`)
      return
    }

    // Record success in circuit breaker
    const circuitKey = this.getCircuitBreakerKey(provider, model)
    const circuitBreaker = this.getOrCreateCircuitBreaker(circuitKey)
    
    // Use synchronous recordSuccess method
    circuitBreaker.recordSuccess()

    // Track consecutive successes
    state.consecutiveSuccesses++
    state.consecutiveFailures = 0

    this.config.logger.debug(`Recorded success for ${slotName}`, {
      provider,
      model,
      consecutiveSuccesses: state.consecutiveSuccesses,
    })

    // Reset chain to index 0 after N consecutive successes
    if (state.consecutiveSuccesses >= this.config.successResetThreshold && state.currentIndex > 0) {
      const previousIndex = state.currentIndex
      state.currentIndex = 0
      this.config.logger.info(`Reset fallback chain to index 0 for ${slotName} after ${state.consecutiveSuccesses} consecutive successes`, {
        previousIndex,
        consecutiveSuccesses: state.consecutiveSuccesses,
      })
    }
  }

  /**
   * Get the current state of a slot's fallback chain.
   *
   * @param slotName - Name of the slot
   * @returns Current state or null if slot not found
   */
  getSlotState(slotName: string): {
    currentIndex: number
    consecutiveFailures: number
    consecutiveSuccesses: number
    chainLength: number
    lastUsedModel: string | null
  } | null {
    const chain = this.chains.get(slotName)
    const state = this.slotStates.get(slotName)

    if (!chain || !state) {
      return null
    }

    return {
      currentIndex: state.currentIndex,
      consecutiveFailures: state.consecutiveFailures,
      consecutiveSuccesses: state.consecutiveSuccesses,
      chainLength: chain.chain.length,
      lastUsedModel: state.lastUsedModel,
    }
  }

  /**
   * Get the circuit breaker state for a specific provider:model pair.
   * Returns the circuit state if the provider:model is in any chain,
   * or null if it's not configured in any chain.
   *
   * @param provider - Provider ID
   * @param model - Model ID
   * @returns CircuitState or null if provider:model is not in any chain
   */
  getCircuitState(provider: string, model: string): CircuitState | null {
    const circuitKey = this.getCircuitBreakerKey(provider, model)
    
    // Check if this provider:model is in any chain
    let isInChain = false
    for (const chain of this.chains.values()) {
      for (const slot of chain.chain) {
        if (slot.provider === provider && slot.model === model) {
          isInChain = true
          break
        }
      }
      if (isInChain) break
    }
    
    if (!isInChain) {
      return null
    }
    
    // Get or create the circuit breaker and return its state
    const circuitBreaker = this.getOrCreateCircuitBreaker(circuitKey)
    return circuitBreaker.getState()
  }

  /**
   * Manually reset a circuit breaker to CLOSED state.
   *
   * @param provider - Provider ID
   * @param model - Model ID
   */
  resetCircuit(provider: string, model: string): void {
    const circuitKey = this.getCircuitBreakerKey(provider, model)
    const circuitBreaker = this.circuitBreakers.get(circuitKey)
    if (circuitBreaker) {
      const previousState = circuitBreaker.getState()
      circuitBreaker.reset()
      this.config.logger.info(`Circuit breaker reset for ${provider}:${model}`, {
        previousState,
        newState: CircuitState.CLOSED,
      })
    }
  }

  /**
   * Manually reset a slot's fallback chain to index 0.
   *
   * @param slotName - Name of the slot
   */
  resetChain(slotName: string): void {
    const state = this.slotStates.get(slotName)
    if (state) {
      const previousIndex = state.currentIndex
      state.currentIndex = 0
      state.consecutiveFailures = 0
      state.consecutiveSuccesses = 0
      this.config.logger.info(`Fallback chain reset for ${slotName}`, {
        previousIndex,
        newIndex: 0,
      })
    }
  }

  /**
   * Dispose of all resources.
   * Clears all maps and prevents further operations.
   */
  dispose(): void {
    if (this.disposed) {
      return
    }

    this.config.logger.info('Disposing FallbackManager')

    // Clear all circuit breakers (they may hold timers)
    for (const [key, breaker] of Array.from(this.circuitBreakers.entries())) {
      breaker.reset()
    }

    this.circuitBreakers.clear()
    this.slotStates.clear()
    this.chains.clear()
    this.disposed = true
  }

  /**
   * Get circuit breaker key for a provider:model pair.
   */
  private getCircuitBreakerKey(provider: string, model: string): string {
    return `${provider}:${model}`
  }

  /**
   * Get or create a circuit breaker for a provider:model pair.
   */
  private getOrCreateCircuitBreaker(key: string): CircuitBreaker<void> {
    let breaker = this.circuitBreakers.get(key)
    if (!breaker) {
      breaker = new CircuitBreaker<void>({
        failureThreshold: this.config.circuitBreakerConfig.failureThreshold,
        resetTimeoutMs: this.config.circuitBreakerConfig.resetTimeoutMs,
        halfOpenMaxAttempts: this.config.circuitBreakerConfig.halfOpenMaxAttempts,
        onStateChange: (state, previousState) => {
          this.config.logger.info(`Circuit breaker state change for ${key}`, {
            previousState,
            newState: state,
          })

          // Emit circuit:stateChange event
          const [provider, model] = key.split(':')
          this.config.eventBus
            .emit({
              type: 'circuit:stateChange',
              timestamp: new Date(),
              provider,
              model,
              state,
              previousState,
            })
            .catch((err) => {
              this.config.logger.error('Failed to emit circuit:stateChange event', { error: err })
            })
        },
      })
      this.circuitBreakers.set(key, breaker)
    }
    return breaker
  }
}
