/**
 * Generic Circuit Breaker with Half-Open State
 * 
 * Implements the circuit breaker pattern with full state machine:
 * CLOSED (normal) → OPEN (failing, fast-fail) → HALF_OPEN (testing recovery)
 * 
 * Type-agnostic and reusable across tools, providers, plugins, and services.
 */

import { rootLogger } from '@cassicore/events'

const logger = rootLogger.child('circuit-breaker')

/**
 * Circuit breaker states
 */
export enum CircuitState {
  /** Normal operation - all calls pass through */
  CLOSED = 'closed',
  /** Failing - calls are blocked with fast-fail error */
  OPEN = 'open',
  /** Testing recovery - limited calls allowed to probe health */
  HALF_OPEN = 'half-open',
}

/**
 * Options for circuit breaker configuration
 */
export interface CircuitBreakerOptions {
  /** Number of consecutive failures to open circuit. Default: 5 */
  failureThreshold?: number
  /** Time in ms before transitioning from OPEN to HALF_OPEN. Default: 60000 */
  resetTimeoutMs?: number
  /** Max attempts allowed in HALF_OPEN state before closing or reopening. Default: 3 */
  halfOpenMaxAttempts?: number
  /** Callback invoked when circuit state changes */
  onStateChange?: (state: CircuitState, previousState: CircuitState) => void
}

/**
 * Error thrown when circuit is open and call is rejected
 */
export class CircuitOpenError extends Error {
  public readonly state: CircuitState
  public readonly timeUntilRetry: number

  constructor(state: CircuitState, timeUntilRetry: number) {
    super(`Circuit breaker is ${state}. Retry after ${timeUntilRetry}ms`)
    this.name = 'CircuitOpenError'
    this.state = state
    this.timeUntilRetry = timeUntilRetry
  }
}

const DEFAULT_OPTIONS: CircuitBreakerOptions = {
  failureThreshold: 5,
  resetTimeoutMs: 60000,
  halfOpenMaxAttempts: 3,
}

interface CircuitStateInternal {
  state: CircuitState
  consecutiveFailures: number
  lastFailureTime: number
  lastStateChange: number
  halfOpenAttempts: number
  halfOpenSuccesses: number
  halfOpenFailures: number
}

/**
 * Generic Circuit Breaker implementation
 * 
 * @typeParam T - The return type of functions executed through the breaker
 * 
 * @example
 * ```typescript
 * const breaker = new CircuitBreaker<string>({
 *   failureThreshold: 3,
 *   resetTimeoutMs: 30000,
 *   onStateChange: (state, prev) => logger.info(`State changed: ${prev} → ${state}`)
 * })
 * 
 * const result = await breaker.execute(() => apiCall())
 * ```
 */
export class CircuitBreaker<T> {
  private config: Required<Pick<CircuitBreakerOptions, 'failureThreshold' | 'resetTimeoutMs' | 'halfOpenMaxAttempts'>> & Pick<CircuitBreakerOptions, 'onStateChange'>
  private state: CircuitStateInternal

  constructor(options: CircuitBreakerOptions = {}) {
    this.config = {
      failureThreshold: options.failureThreshold ?? 5,
      resetTimeoutMs: options.resetTimeoutMs ?? 60000,
      halfOpenMaxAttempts: options.halfOpenMaxAttempts ?? 3,
      onStateChange: options.onStateChange,
    }
    this.state = {
      state: CircuitState.CLOSED,
      consecutiveFailures: 0,
      lastFailureTime: 0,
      lastStateChange: Date.now(),
      halfOpenAttempts: 0,
      halfOpenSuccesses: 0,
      halfOpenFailures: 0,
    }
  }

  /**
   * Execute a function through the circuit breaker
   * 
   * @param fn - Async function to execute
   * @returns Promise resolving to function result
   * @throws CircuitOpenError if circuit is open
   * @throws The error from fn if it fails
   */
  async execute(fn: () => Promise<T>): Promise<T> {
    // Check if we should transition from OPEN to HALF_OPEN
    this.checkStateTransition()

    // Fast-fail if circuit is open
    if (this.state.state === CircuitState.OPEN) {
      const timeUntilRetry = this.getTimeUntilRetry()
      throw new CircuitOpenError(this.state.state, timeUntilRetry)
    }

    // Check if we've exceeded half-open attempts
    if (this.state.state === CircuitState.HALF_OPEN) {
      if (this.state.halfOpenAttempts >= this.config.halfOpenMaxAttempts) {
        // All half-open attempts exhausted - reopen circuit
        this.transitionTo(CircuitState.OPEN)
        const timeUntilRetry = this.config.resetTimeoutMs
        throw new CircuitOpenError(this.state.state, timeUntilRetry)
      }
      this.state.halfOpenAttempts++
    }

    try {
      const result = await fn()
      
      // Record success
      this._recordSuccess()
      
      return result
    } catch (error) {
      // Record failure
      this._recordFailure()
      
      // Re-throw the error
      throw error
    }
  }

  /**
   * Get the current circuit state
   */
  getState(): CircuitState {
    this.checkStateTransition()
    return this.state.state
  }

  /**
   * Manually reset the circuit to CLOSED state
   * 
   * Use this for manual recovery or testing
   */
  reset(): void {
    this.transitionTo(CircuitState.CLOSED)
    this.state.consecutiveFailures = 0
    this.state.halfOpenAttempts = 0
    this.state.halfOpenSuccesses = 0
    this.state.halfOpenFailures = 0
  }

  /**
   * Record a failure without executing a function.
   * 
   * Use this for external failure tracking (e.g., when the failure
   * occurs outside of execute() calls).
   */
  recordFailure(): void {
    this._recordFailure()
  }

  /**
   * Record a success without executing a function.
   * 
   * Use this for external success tracking (e.g., when the success
   * occurs outside of execute() calls).
   */
  recordSuccess(): void {
    this._recordSuccess()
  }

  /**
   * Get detailed metrics about the circuit state
   */
  getMetrics(): {
    state: CircuitState
    consecutiveFailures: number
    halfOpenAttempts: number
    halfOpenSuccesses: number
    halfOpenFailures: number
    timeUntilRetry?: number
  } {
    this.checkStateTransition()
    
    const metrics = {
      state: this.state.state,
      consecutiveFailures: this.state.consecutiveFailures,
      halfOpenAttempts: this.state.halfOpenAttempts,
      halfOpenSuccesses: this.state.halfOpenSuccesses,
      halfOpenFailures: this.state.halfOpenFailures,
    }

    if (this.state.state === CircuitState.OPEN) {
      return {
        ...metrics,
        timeUntilRetry: this.getTimeUntilRetry(),
      }
    }

    return metrics
  }

  /**
   * Check if state should transition from OPEN to HALF_OPEN
   */
  private checkStateTransition(): void {
    if (this.state.state === CircuitState.OPEN) {
      const elapsed = Date.now() - this.state.lastStateChange
      if (elapsed >= this.config.resetTimeoutMs) {
        this.transitionTo(CircuitState.HALF_OPEN)
        // Reset half-open counters
        this.state.halfOpenAttempts = 0
        this.state.halfOpenSuccesses = 0
        this.state.halfOpenFailures = 0
      }
    }
  }

  /**
   * Record a successful execution (internal method)
   */
  private _recordSuccess(): void {
    const previousState = this.state.state

    if (this.state.state === CircuitState.HALF_OPEN) {
      this.state.halfOpenSuccesses++
      
      // If we have at least one success in half-open, close the circuit
      // This implements the "any success closes" strategy
      if (this.state.halfOpenSuccesses >= 1) {
        this.transitionTo(CircuitState.CLOSED)
        this.state.consecutiveFailures = 0
      }
    } else if (this.state.state === CircuitState.CLOSED) {
      // Reset consecutive failures on success
      this.state.consecutiveFailures = 0
    }
  }

  /**
   * Record a failed execution (internal method)
   */
  private _recordFailure(): void {
    const previousState = this.state.state
    this.state.consecutiveFailures++
    this.state.lastFailureTime = Date.now()

    if (this.state.state === CircuitState.HALF_OPEN) {
      this.state.halfOpenFailures++
      
      // Any failure in half-open reopens the circuit
      this.transitionTo(CircuitState.OPEN)
    } else if (this.state.state === CircuitState.CLOSED) {
      // Check if we've reached the failure threshold
      if (this.state.consecutiveFailures >= this.config.failureThreshold) {
        this.transitionTo(CircuitState.OPEN)
      }
    }
  }

  /**
   * Transition to a new state and invoke callback
   */
  private transitionTo(newState: CircuitState): void {
    const previousState = this.state.state
    
    if (previousState === newState) {
      return
    }

    this.state.state = newState
    this.state.lastStateChange = Date.now()

    // Invoke state change callback
    if (this.config.onStateChange) {
      try {
        this.config.onStateChange(newState, previousState)
      } catch (callbackError) {
        // Don't let callback errors affect circuit breaker operation
        logger.error('State change callback error', { error: String(callbackError) })
      }
    }
  }

  /**
   * Calculate time until retry is allowed
   */
  private getTimeUntilRetry(): number {
    const elapsed = Date.now() - this.state.lastStateChange
    return Math.max(0, this.config.resetTimeoutMs - elapsed)
  }
}

/**
 * Create a circuit breaker with default options
 * 
 * @param options - Circuit breaker options
 * @returns New CircuitBreaker instance
 */
export function createCircuitBreaker<T>(options?: CircuitBreakerOptions): CircuitBreaker<T> {
  return new CircuitBreaker<T>(options)
}
