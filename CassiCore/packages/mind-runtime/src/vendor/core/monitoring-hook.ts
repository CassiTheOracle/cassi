/**
 * Runtime Self-Monitoring Hook
 * Minimal instrumentation layer for core orchestration
 * Captures: (a) tool call latency/failure patterns, (b) context window pressure, (c) loop detection
 */

import { createHash } from 'node:crypto'
import { rootLogger } from '@cassicore/events'
import type { ILogger } from '@cassicore/foundation'

const logger: ILogger = rootLogger.child('monitoring')

// ============================================================================
// Types
// ============================================================================

export type ToolCallStatus = 'success' | 'timeout' | 'failure'

export interface ToolCallMetric {
  toolName: string
  startTime: number
  endTime: number
  durationMs: number
  status: ToolCallStatus
  errorType?: string
  errorMessage?: string
  sessionId?: string
}

export interface ContextPressureAlert {
  timestamp: number
  tokenCount: number
  threshold: number
  pressureLevel: 'warning' | 'critical'
  sessionId?: string
}

export interface LoopDetectionResult {
  detected: boolean
  similarity: number
  patternHash: string
  occurrenceCount: number
  suggestedAction: 'continue' | 'warn' | 'interrupt'
}

export interface MonitoringConfig {
  // Tool monitoring
  toolTimeoutMs: number
  slowToolThresholdMs: number
  // Context pressure
  contextWarningThreshold: number
  contextCriticalThreshold: number
  // Loop detection
  loopSimilarityThreshold: number
  loopHistorySize: number
  loopInterruptThreshold: number
}

// ============================================================================
// Default Configuration
// ============================================================================

const DEFAULT_CONFIG: MonitoringConfig = {
  toolTimeoutMs: 60000,
  slowToolThresholdMs: 5000,
  contextWarningThreshold: 0.7,  // 70% of context window
  contextCriticalThreshold: 0.9, // 90% of context window
  loopSimilarityThreshold: 0.85,
  loopHistorySize: 10,
  loopInterruptThreshold: 3
}

// ============================================================================
// Tool Monitor - Captures per-call timing and error classification
// ============================================================================

export class ToolMonitor {
  private metrics: ToolCallMetric[] = []
  private inFlightCalls = new Map<string, { startTime: number; toolName: string }>()
  private config: MonitoringConfig

  constructor(config: Partial<MonitoringConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config }
  }

  /**
   * Start tracking a tool call
   * Returns a callId to use when ending the call
   */
  startCall(toolName: string, sessionId?: string): string {
    const callId = `${toolName}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
    this.inFlightCalls.set(callId, { startTime: Date.now(), toolName })
    return callId
  }

  /**
   * End tracking a tool call with result classification
   */
  endCall(
    callId: string,
    error?: Error,
    sessionId?: string
  ): ToolCallMetric | undefined {
    const call = this.inFlightCalls.get(callId)
    if (!call) {
      logger.warn('Attempted to end unknown tool call', { callId })
      return undefined
    }

    this.inFlightCalls.delete(callId)
    const endTime = Date.now()
    const durationMs = endTime - call.startTime

    // Classify error type
    let status: ToolCallStatus = 'success'
    let errorType: string | undefined
    let errorMessage: string | undefined

    if (error) {
      errorMessage = error.message
      if (error.message.toLowerCase().includes('timeout') || durationMs >= this.config.toolTimeoutMs) {
        status = 'timeout'
        errorType = 'timeout'
      } else {
        status = 'failure'
        errorType = error.name || 'unknown'
      }
    }

    const metric: ToolCallMetric = {
      toolName: call.toolName,
      startTime: call.startTime,
      endTime,
      durationMs,
      status,
      errorType,
      errorMessage,
      sessionId
    }

    this.metrics.push(metric)
    this.trimMetrics()

    // Log slow or failed calls
    if (status !== 'success') {
      logger.warn('Tool call failed', {
        toolName: call.toolName,
        status,
        durationMs,
        errorType,
        sessionId
      })
    } else if (durationMs > this.config.slowToolThresholdMs) {
      logger.info('Slow tool call detected', {
        toolName: call.toolName,
        durationMs,
        threshold: this.config.slowToolThresholdMs,
        sessionId
      })
    }

    return metric
  }

  /**
   * Get metrics for analysis
   */
  getMetrics(options: {
    toolName?: string
    status?: ToolCallStatus
    since?: number
    limit?: number
  } = {}): ToolCallMetric[] {
    let result = [...this.metrics]

    if (options.toolName) {
      result = result.filter(m => m.toolName === options.toolName)
    }
    if (options.status) {
      result = result.filter(m => m.status === options.status)
    }
    if (options.since) {
      const since = options.since
      result = result.filter(m => m.startTime >= since)
    }
    if (options.limit) {
      result = result.slice(-options.limit)
    }

    return result
  }

  /**
   * Get failure pattern summary for cascading timeout detection
   */
  getFailurePatterns(): Map<string, { count: number; timeouts: number; failures: number }> {
    const patterns = new Map<string, { count: number; timeouts: number; failures: number }>()

    for (const metric of this.metrics) {
      if (metric.status === 'success') continue

      const existing = patterns.get(metric.toolName) || { count: 0, timeouts: 0, failures: 0 }
      existing.count++
      if (metric.status === 'timeout') existing.timeouts++
      else existing.failures++
      patterns.set(metric.toolName, existing)
    }

    return patterns
  }

  private trimMetrics(maxSize = 1000): void {
    if (this.metrics.length > maxSize) {
      this.metrics = this.metrics.slice(-maxSize)
    }
  }

  /**
   * Detect cascading timeouts - multiple tools failing in sequence
   */
  detectCascadingTimeouts(windowMs = 60000): boolean {
    const recentFailures = this.metrics.filter(
      m => m.status !== 'success' && m.startTime > Date.now() - windowMs
    )

    if (recentFailures.length < 3) return false

    // Check for pattern of escalating failures
    const uniqueTools = new Set(recentFailures.map(m => m.toolName))
    return uniqueTools.size >= 2 && recentFailures.length >= 3
  }
}

// ============================================================================
// Context Monitor - Token threshold alerts
// ============================================================================

export class ContextMonitor {
  private alerts: ContextPressureAlert[] = []
  private lastAlertTime = 0
  private config: MonitoringConfig

  constructor(config: Partial<MonitoringConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config }
  }

  /**
   * Check context window pressure and emit alerts
   */
  checkPressure(
    tokenCount: number,
    maxTokens: number,
    sessionId?: string
  ): ContextPressureAlert | null {
    const ratio = tokenCount / maxTokens
    let pressureLevel: 'warning' | 'critical' | null = null

    if (ratio >= this.config.contextCriticalThreshold) {
      pressureLevel = 'critical'
    } else if (ratio >= this.config.contextWarningThreshold) {
      pressureLevel = 'warning'
    }

    if (!pressureLevel) return null

    // Debounce alerts - max one per 5 seconds
    const now = Date.now()
    if (now - this.lastAlertTime < 5000) return null
    this.lastAlertTime = now

    const alert: ContextPressureAlert = {
      timestamp: now,
      tokenCount,
      threshold: Math.floor(ratio * 100),
      pressureLevel,
      sessionId
    }

    this.alerts.push(alert)
    this.trimAlerts()

    // Log with appropriate severity
    if (pressureLevel === 'critical') {
      logger.error('Context window critical pressure', {
        tokenCount,
        maxTokens,
        ratio: ratio.toFixed(2),
        sessionId
      })
    } else {
      logger.warn('Context window pressure warning', {
        tokenCount,
        maxTokens,
        ratio: ratio.toFixed(2),
        sessionId
      })
    }

    return alert
  }

  /**
   * Estimate tokens from content (rough approximation)
   */
  estimateTokens(content: string): number {
    // Rough estimate: ~4 characters per token on average
    return Math.ceil(content.length / 4)
  }

  getAlerts(options: {
    level?: 'warning' | 'critical'
    since?: number
    limit?: number
  } = {}): ContextPressureAlert[] {
    let result = [...this.alerts]

    if (options.level) {
      result = result.filter(a => a.pressureLevel === options.level)
    }
    if (options.since) {
      const since = options.since
      result = result.filter(a => a.timestamp >= since)
    }
    if (options.limit) {
      result = result.slice(-options.limit)
    }

    return result
  }

  private trimAlerts(maxSize = 100): void {
    if (this.alerts.length > maxSize) {
      this.alerts = this.alerts.slice(-maxSize)
    }
  }
}

// ============================================================================
// Loop Detector - Thought similarity hashing
// ============================================================================

export class LoopDetector {
  private thoughtHistory: Array<{ hash: string; thought: string; timestamp: number }> = []
  private patternCounts = new Map<string, number>()
  private config: MonitoringConfig

  constructor(config: Partial<MonitoringConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config }
  }

  /**
   * Generate a similarity hash for a thought
   * Uses simplified simhash approach for semantic similarity
   */
  private hashThought(thought: string): string {
    // Normalize: lowercase, remove extra whitespace, limit length
    const normalized = thought
      .toLowerCase()
      .replace(/\s+/g, ' ')
      .trim()
      .slice(0, 500)

    // Create hash
    return createHash('sha256').update(normalized).digest('hex').slice(0, 16)
  }

  /**
   * Calculate similarity between two thoughts (0-1)
   */
  private calculateSimilarity(thought1: string, thought2: string): number {
    const hash1 = this.hashThought(thought1)
    const hash2 = this.hashThought(thought2)

    // Exact hash match = identical thoughts
    if (hash1 === hash2) return 1.0

    // Simple Jaccard similarity on word sets
    const words1 = new Set(thought1.toLowerCase().split(/\s+/))
    const words2 = new Set(thought2.toLowerCase().split(/\s+/))

    const intersection = new Set([...words1].filter(w => words2.has(w)))
    const union = new Set([...words1, ...words2])

    return intersection.size / union.size
  }

  /**
   * Detect if current thought represents a loop pattern
   */
  detect(currentThought: string, sessionId?: string): LoopDetectionResult {
    const currentHash = this.hashThought(currentThought)
    const now = Date.now()

    // Check for exact hash match in recent history
    let maxSimilarity = 0
    let matchingPatternHash = currentHash
    let occurrenceCount = 1

    for (const entry of this.thoughtHistory) {
      const similarity = this.calculateSimilarity(currentThought, entry.thought)
      if (similarity > maxSimilarity) {
        maxSimilarity = similarity
        matchingPatternHash = entry.hash
      }
    }

    // Update pattern count
    if (maxSimilarity >= this.config.loopSimilarityThreshold) {
      occurrenceCount = (this.patternCounts.get(matchingPatternHash) || 0) + 1
      this.patternCounts.set(matchingPatternHash, occurrenceCount)
    } else {
      // New pattern
      this.patternCounts.set(currentHash, 1)
    }

    // Add to history
    this.thoughtHistory.push({
      hash: currentHash,
      thought: currentThought,
      timestamp: now
    })
    this.trimHistory()

    // Determine suggested action
    let suggestedAction: 'continue' | 'warn' | 'interrupt' = 'continue'
    if (occurrenceCount >= this.config.loopInterruptThreshold) {
      suggestedAction = 'interrupt'
    } else if (occurrenceCount >= 2) {
      suggestedAction = 'warn'
    }

    return {
      detected: maxSimilarity >= this.config.loopSimilarityThreshold,
      similarity: maxSimilarity,
      patternHash: matchingPatternHash,
      occurrenceCount,
      suggestedAction
    }
  }

  /**
   * Get current loop statistics
   */
  getStats(): {
    totalPatterns: number
    maxOccurrences: number
    recentLoops: Array<{ patternHash: string; occurrences: number; lastSeen: number }>
  } {
    const entries = Array.from(this.patternCounts.entries())
    const maxOccurrences = entries.length > 0 
      ? Math.max(...entries.map(([, count]) => count))
      : 0
    
    const recentLoops = entries
      .filter(([, count]) => count >= 2)
      .map(([hash, occurrences]) => {
        const historyEntry = this.thoughtHistory.find(h => h.hash === hash)
        return {
          patternHash: hash,
          occurrences,
          lastSeen: historyEntry?.timestamp || Date.now()
        }
      })
      .sort((a, b) => b.occurrences - a.occurrences)
      .slice(0, 5)

    return {
      totalPatterns: entries.length,
      maxOccurrences,
      recentLoops
    }
  }

  /**
   * Clear history for a fresh start
   */
  reset(): void {
    this.thoughtHistory = []
    this.patternCounts.clear()
  }

  private trimHistory(): void {
    if (this.thoughtHistory.length > this.config.loopHistorySize) {
      this.thoughtHistory = this.thoughtHistory.slice(-this.config.loopHistorySize)
    }
  }
}

// ============================================================================
// Main Monitoring Hook - Unified interface
// ============================================================================

export class MonitoringHook {
  public readonly toolMonitor: ToolMonitor
  public readonly contextMonitor: ContextMonitor
  public readonly loopDetector: LoopDetector

  constructor(config: Partial<MonitoringConfig> = {}) {
    this.toolMonitor = new ToolMonitor(config)
    this.contextMonitor = new ContextMonitor(config)
    this.loopDetector = new LoopDetector(config)
  }

  /**
   * Capture tool call metrics with automatic timing
   * Usage: const end = monitoring.captureToolMetrics('toolName'); ...; end(error?)
   */
  captureToolMetrics(toolName: string, sessionId?: string): (error?: Error) => ToolCallMetric | undefined {
    const callId = this.toolMonitor.startCall(toolName, sessionId)
    return (error?: Error) => this.toolMonitor.endCall(callId, error, sessionId)
  }

  /**
   * Check context window pressure
   */
  checkContextPressure(tokenCount: number, maxTokens: number, sessionId?: string): ContextPressureAlert | null {
    return this.contextMonitor.checkPressure(tokenCount, maxTokens, sessionId)
  }

  /**
   * Detect repetitive planning loops
   */
  detectLoop(currentThought: string, sessionId?: string): LoopDetectionResult {
    return this.loopDetector.detect(currentThought, sessionId)
  }

  /**
   * Get comprehensive monitoring status with enhanced tool metrics
   */
  getStatus(): {
    cascadingTimeouts: boolean
    failurePatterns: Map<string, { count: number; timeouts: number; failures: number }>
    recentAlerts: ContextPressureAlert[]
    toolMetrics: {
      totalCalls: number
      successRate: number
      avgDurationMs: number
      slowestTools: Array<{ toolName: string; avgDurationMs: number; callCount: number }>
      recentErrors: Array<{ toolName: string; errorType: string; timestamp: number; message?: string }>
    }
    loopStats: {
      totalPatterns: number
      maxOccurrences: number
      recentLoops: Array<{ patternHash: string; occurrences: number; lastSeen: number }>
    }
  } {
    const metrics = this.toolMonitor.getMetrics()
    const totalCalls = metrics.length
    const successfulCalls = metrics.filter(m => m.status === 'success').length
    const avgDuration = totalCalls > 0 
      ? metrics.reduce((sum, m) => sum + m.durationMs, 0) / totalCalls 
      : 0
    
    // Calculate per-tool stats
    const toolStats = new Map<string, { totalDuration: number; count: number; errors: number }>()
    for (const m of metrics) {
      const stats = toolStats.get(m.toolName) || { totalDuration: 0, count: 0, errors: 0 }
      stats.totalDuration += m.durationMs
      stats.count++
      if (m.status !== 'success') stats.errors++
      toolStats.set(m.toolName, stats)
    }
    
    const slowestTools = Array.from(toolStats.entries())
      .map(([toolName, stats]) => ({
        toolName,
        avgDurationMs: Math.round(stats.totalDuration / stats.count),
        callCount: stats.count
      }))
      .sort((a, b) => b.avgDurationMs - a.avgDurationMs)
      .slice(0, 5)
    
    const recentErrors = metrics
      .filter(m => m.status !== 'success')
      .slice(-10)
      .map(m => ({ 
        toolName: m.toolName, 
        errorType: m.errorType || 'unknown', 
        timestamp: m.endTime,
        message: m.errorMessage 
      }))

    return {
      cascadingTimeouts: this.toolMonitor.detectCascadingTimeouts(),
      failurePatterns: this.toolMonitor.getFailurePatterns(),
      recentAlerts: this.contextMonitor.getAlerts({ limit: 5 }),
      toolMetrics: {
        totalCalls,
        successRate: totalCalls > 0 ? successfulCalls / totalCalls : 1,
        avgDurationMs: Math.round(avgDuration),
        slowestTools,
        recentErrors
      },
      loopStats: this.loopDetector.getStats()
    }
  }
}

// ============================================================================
// Factory function for easy instantiation
// ============================================================================

export function createMonitoringHook(config?: Partial<MonitoringConfig>): MonitoringHook {
  return new MonitoringHook(config)
}

// Default export
export default MonitoringHook
