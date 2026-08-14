/**
 * Tool Reliability Profiles with Circuit Breaker Pattern
 * 
 * Tracks per-tool success/failure metrics and implements automatic circuit breaking
 * with fallback routing for resilient tool execution.
 */

import type { ILogger } from "@cassicore/foundation"

export type CircuitState = 'closed' | 'half-open' | 'open'

export interface ToolReliabilityMetrics {
  toolName: string
  totalCalls: number
  successCount: number
  failureCount: number
  consecutiveFailures: number
  successRate: number
  avgDurationMs: number
  p95DurationMs: number
  circuitState: CircuitState
  lastStateChange: number
  lastCallTime: number
}

export interface ReliabilityConfig {
  /** Consecutive failures to open circuit. Default: 5 */
  failureThreshold: number
  /** Cooldown before half-open test (ms). Default: 30000 */
  cooldownMs: number
  /** Max duration samples to keep. Default: 100 */
  maxSamples: number
}

const DEFAULT_CONFIG: ReliabilityConfig = {
  failureThreshold: 5,
  cooldownMs: 30000,
  maxSamples: 100,
}

/**
 * Circular buffer for duration samples with O(1) insert and O(n) p95 calculation.
 * Maintains a rolling window of the most recent N samples.
 */
class DurationBuffer {
  private samples: number[]
  private index: number
  private count: number

  constructor(private maxSize: number) {
    this.samples = new Array(maxSize)
    this.index = 0
    this.count = 0
  }

  /** Add a duration sample, overwriting oldest if at capacity */
  add(durationMs: number): void {
    this.samples[this.index] = durationMs
    this.index = (this.index + 1) % this.maxSize
    if (this.count < this.maxSize) {
      this.count++
    }
  }

  /** Calculate the 95th percentile duration */
  p95(): number {
    if (this.count === 0) return 0
    if (this.count === 1) return this.samples[0]

    // Sort only the populated portion
    const sorted = [...this.samples.slice(0, this.count)].sort((a, b) => a - b)
    const p95Index = Math.floor(this.count * 0.95)
    return sorted[Math.min(p95Index, this.count - 1)]
  }

  /** Calculate the average duration */
  average(): number {
    if (this.count === 0) return 0
    const sum = this.samples.slice(0, this.count).reduce((a, b) => a + b, 0)
    return sum / this.count
  }

  /** Get the number of samples currently stored */
  size(): number {
    return this.count
  }
}

interface ToolState {
  totalCalls: number
  successCount: number
  failureCount: number
  consecutiveFailures: number
  durationBuffer: DurationBuffer
  circuitState: CircuitState
  lastStateChange: number
  lastCallTime: number
}

/**
 * Tool Reliability Tracker with Circuit Breaker Pattern
 * 
 * Monitors tool execution health and automatically opens circuits when tools
 * exhibit repeated failures. Supports automatic recovery through half-open
 * state testing.
 * 
 * State Machine:
 * - **closed** (normal): all calls pass through
 * - **open** (after N consecutive failures): calls are blocked
 * - **half-open**: next call is allowed as a test; success → closed, failure → open
 */
export class ToolReliabilityTracker {
  private toolStates: Map<string, ToolState>
  private config: ReliabilityConfig
  private logger: ILogger

  constructor(logger: ILogger, config?: Partial<ReliabilityConfig>) {
    this.logger = logger.child('tool-reliability')
    this.config = { ...DEFAULT_CONFIG, ...config }
    this.toolStates = new Map()
  }

  /**
   * Get or create state for a tool
   */
  private getState(toolName: string): ToolState {
    let state = this.toolStates.get(toolName)
    if (!state) {
      state = {
        totalCalls: 0,
        successCount: 0,
        failureCount: 0,
        consecutiveFailures: 0,
        durationBuffer: new DurationBuffer(this.config.maxSamples),
        circuitState: 'closed',
        lastStateChange: Date.now(),
        lastCallTime: 0,
      }
      this.toolStates.set(toolName, state)
    }
    return state
  }

  /**
   * Record a successful tool execution
   * 
   * @param toolName - The name of the tool that succeeded
   * @param durationMs - Execution duration in milliseconds
   */
  recordSuccess(toolName: string, durationMs: number): void {
    const state = this.getState(toolName)
    const now = Date.now()

    state.totalCalls++
    state.successCount++
    state.consecutiveFailures = 0
    state.durationBuffer.add(durationMs)
    state.lastCallTime = now

    // Transition from half-open to closed on success
    if (state.circuitState === 'half-open') {
      state.circuitState = 'closed'
      state.lastStateChange = now
      this.logger.info(`Circuit CLOSED for tool '${toolName}' after successful test`, {
        consecutiveFailures: state.consecutiveFailures,
        durationMs,
      })
    } else if (state.circuitState === 'closed') {
      this.logger.debug(`Recorded success for tool '${toolName}'`, {
        totalCalls: state.totalCalls,
        successRate: this.calculateSuccessRate(state),
        durationMs,
      })
    }
  }

  /**
   * Record a failed tool execution
   * 
   * @param toolName - The name of the tool that failed
   * @param durationMs - Execution duration in milliseconds (up to failure point)
   */
  recordFailure(toolName: string, durationMs: number): void {
    const state = this.getState(toolName)
    const now = Date.now()

    state.totalCalls++
    state.failureCount++
    state.consecutiveFailures++
    state.durationBuffer.add(durationMs)
    state.lastCallTime = now

    // Transition from half-open to open on failure
    if (state.circuitState === 'half-open') {
      state.circuitState = 'open'
      state.lastStateChange = now
      this.logger.warn(`Circuit OPEN for tool '${toolName}' after failed test`, {
        consecutiveFailures: state.consecutiveFailures,
        durationMs,
      })
    }
    // Transition from closed to open after threshold
    else if (state.circuitState === 'closed' && 
             state.consecutiveFailures >= this.config.failureThreshold) {
      state.circuitState = 'open'
      state.lastStateChange = now
      this.logger.warn(`Circuit OPEN for tool '${toolName}' after ${state.consecutiveFailures} consecutive failures`, {
        failureThreshold: this.config.failureThreshold,
        totalCalls: state.totalCalls,
        successRate: this.calculateSuccessRate(state),
      })
    } else {
      this.logger.debug(`Recorded failure for tool '${toolName}'`, {
        consecutiveFailures: state.consecutiveFailures,
        failureThreshold: this.config.failureThreshold,
        durationMs,
      })
    }
  }

  /**
   * Check if a tool can be executed based on circuit breaker state
   * 
   * @param toolName - The name of the tool to check
   * @returns true if the tool's circuit is closed or half-open (test request)
   * 
   * If the circuit is open and the cooldown period has elapsed, automatically
   * transitions to half-open state to allow a test execution.
   */
  canExecute(toolName: string): boolean {
    const state = this.getState(toolName)
    const now = Date.now()

    // Closed state: always allow
    if (state.circuitState === 'closed') {
      return true
    }

    // Open state: check if cooldown has elapsed
    if (state.circuitState === 'open') {
      const elapsed = now - state.lastStateChange
      if (elapsed >= this.config.cooldownMs) {
        // Transition to half-open for test
        state.circuitState = 'half-open'
        state.lastStateChange = now
        this.logger.info(`Circuit HALF-OPEN for tool '${toolName}' — allowing test execution`, {
          cooldownMs: this.config.cooldownMs,
          elapsedMs: elapsed,
        })
        return true
      }
      return false
    }

    // Half-open state: allow test execution
    if (state.circuitState === 'half-open') {
      this.logger.debug(`Circuit HALF-OPEN for tool '${toolName}' — allowing test execution`)
      return true
    }

    return false
  }

  /**
   * Get reliability metrics for a specific tool or all tools
   * 
   * @param toolName - Optional tool name. If omitted, returns metrics for all tools
   * @returns Metrics for the specified tool, or a map of all tool metrics
   */
  getMetrics(toolName?: string): ToolReliabilityMetrics | Map<string, ToolReliabilityMetrics> {
    if (toolName) {
      const state = this.getState(toolName)
      return this.buildMetrics(toolName, state)
    }

    const result = new Map<string, ToolReliabilityMetrics>()
    for (const [name, state] of this.toolStates.entries()) {
      result.set(name, this.buildMetrics(name, state))
    }
    return result
  }

  /**
   * Reset a tool's circuit state to closed
   * 
   * @param toolName - The name of the tool to reset
   */
  reset(toolName: string): void {
    const state = this.getState(toolName)
    const wasOpen = state.circuitState !== 'closed'
    
    state.circuitState = 'closed'
    state.consecutiveFailures = 0
    state.lastStateChange = Date.now()

    if (wasOpen) {
      this.logger.info(`Circuit RESET for tool '${toolName}'`, {
        previousState: state.circuitState,
      })
    }
  }

  /**
   * Build metrics object from internal state
   */
  private buildMetrics(toolName: string, state: ToolState): ToolReliabilityMetrics {
    return {
      toolName,
      totalCalls: state.totalCalls,
      successCount: state.successCount,
      failureCount: state.failureCount,
      consecutiveFailures: state.consecutiveFailures,
      successRate: this.calculateSuccessRate(state),
      avgDurationMs: state.durationBuffer.average(),
      p95DurationMs: state.durationBuffer.p95(),
      circuitState: state.circuitState,
      lastStateChange: state.lastStateChange,
      lastCallTime: state.lastCallTime,
    }
  }

  /**
   * Calculate success rate as a decimal (0.0 to 1.0)
   */
  private calculateSuccessRate(state: ToolState): number {
    if (state.totalCalls === 0) return 1.0
    return state.successCount / state.totalCalls
  }
}
