/**
 * BudgetMonitor — Token budget monitoring and alerting for agent sessions
 *
 * Tracks token usage per session and emits alerts when thresholds are reached.
 * Supports automatic actions (notify, pause, require_approval) when budgets are exceeded.
 *
 * Design goals:
 * - Real-time monitoring with configurable thresholds
 * - Parent session notifications for child sessions
 * - Automatic enforcement actions
 * - Integration with event bus for cross-session awareness
 */

import type { ILogger, IEventBus } from '@cassicore/foundation'

export interface BudgetThreshold {
  /** Maximum token limit */
  limit: number
  /** Action to take when threshold is reached */
  action: 'notify' | 'pause' | 'require_approval'
  /** Whether to notify parent session (for child sessions) */
  notifyParent?: boolean
  /** Custom alert message */
  message?: string
}

export interface BudgetAlert {
  sessionId: string
  parentSessionId?: string
  currentUsage: number
  limit: number
  percentUsed: number
  action: string
  timestamp: number
  message?: string
}

export interface BudgetUsage {
  sessionId: string
  inputTokens: number
  outputTokens: number
  totalTokens: number
  requestCount: number
  lastUpdated: number
}

export interface BudgetEvent {
  type: 'budget:alert' | 'budget:warning' | 'budget:exceeded'
  sessionId: string
  parentSessionId?: string
  alert: BudgetAlert
  timestamp: number
}

export class BudgetMonitor {
  private readonly thresholds = new Map<string, BudgetThreshold>()
  private readonly usage = new Map<string, BudgetUsage>()
  private readonly warningsSent = new Set<string>()
  private readonly eventBus?: IEventBus
  private readonly logger: ILogger
  
  /** Warning threshold as percentage of limit (default: 80%) */
  private readonly warningThreshold: number

  constructor(logger: ILogger, eventBus?: IEventBus, warningThreshold: number = 0.8) {
    this.logger = logger.child?.('budget-monitor') ?? logger
    this.eventBus = eventBus
    this.warningThreshold = warningThreshold
  }

  /**
   * Set a budget threshold for a session
   */
  setThreshold(sessionId: string, threshold: BudgetThreshold): void {
    this.thresholds.set(sessionId, threshold)
    
    // Initialize usage tracking if not exists
    if (!this.usage.has(sessionId)) {
      this.usage.set(sessionId, {
        sessionId,
        inputTokens: 0,
        outputTokens: 0,
        totalTokens: 0,
        requestCount: 0,
        lastUpdated: Date.now(),
      })
    }
    
    this.logger.debug('Set budget threshold', { sessionId, limit: threshold.limit, action: threshold.action })
  }

  /**
   * Get the threshold for a session
   */
  getThreshold(sessionId: string): BudgetThreshold | undefined {
    return this.thresholds.get(sessionId)
  }

  /**
   * Remove a threshold
   */
  removeThreshold(sessionId: string): void {
    this.thresholds.delete(sessionId)
  }

  /**
   * Record token usage for a session
   */
  recordUsage(sessionId: string, inputTokens: number, outputTokens: number): BudgetAlert | null {
    const currentUsage = this.getUsage(sessionId)
    if (!currentUsage) return null
    
    const usage = this.usage.get(sessionId)!
    usage.inputTokens += inputTokens
    usage.outputTokens += outputTokens
    usage.totalTokens += inputTokens + outputTokens
    usage.requestCount++
    usage.lastUpdated = Date.now()
    
    // Check if threshold is exceeded
    const threshold = this.thresholds.get(sessionId)
    if (!threshold) return null
    
    const alert = this.checkBudget(sessionId, usage.totalTokens)
    
    if (alert) {
      this.emitAlert(alert)
    }
    
    return alert
  }

  /**
   * Check if budget threshold is reached
   */
  checkBudget(sessionId: string, currentUsage: number): BudgetAlert | null {
    const threshold = this.thresholds.get(sessionId)
    if (!threshold) return null
    
    const percentUsed = currentUsage / threshold.limit
    
    // Check if already sent warning
    const warningKey = `${sessionId}:warning`
    if (percentUsed >= this.warningThreshold && !this.warningsSent.has(warningKey)) {
      this.warningsSent.add(warningKey)
      this.emitWarning(sessionId, currentUsage, threshold)
    }
    
    // Check if threshold exceeded
    if (currentUsage >= threshold.limit) {
      const alertKey = `${sessionId}:alert`
      // Only emit once per threshold
      if (!this.warningsSent.has(alertKey)) {
        this.warningsSent.add(alertKey)
        
        return {
          sessionId,
          currentUsage,
          limit: threshold.limit,
          percentUsed: Math.round(percentUsed * 100),
          action: threshold.action,
          timestamp: Date.now(),
          message: threshold.message,
        }
      }
    }
    
    return null
  }

  /**
   * Get current usage for a session
   */
  getUsage(sessionId: string): BudgetUsage | undefined {
    return this.usage.get(sessionId)
  }

  /**
   * Get usage for all tracked sessions
   */
  getAllUsage(): BudgetUsage[] {
    return Array.from(this.usage.values())
  }

  /**
   * Reset usage tracking for a session
   */
  resetUsage(sessionId: string): void {
    const existing = this.usage.get(sessionId)
    if (existing) {
      this.usage.set(sessionId, {
        ...existing,
        inputTokens: 0,
        outputTokens: 0,
        totalTokens: 0,
        requestCount: 0,
        lastUpdated: Date.now(),
      })
      
      // Clear warning flags
      this.warningsSent.delete(`${sessionId}:warning`)
      this.warningsSent.delete(`${sessionId}:alert`)
    }
  }

  /**
   * Get sessions approaching or exceeding budget
   */
  getAtRiskSessions(thresholdPercent: number = 0.8): Array<{
    sessionId: string
    usage: BudgetUsage
    threshold?: BudgetThreshold
    percentUsed: number
  }> {
    const atRisk: Array<{
      sessionId: string
      usage: BudgetUsage
      threshold?: BudgetThreshold
      percentUsed: number
    }> = []
    
    for (const [sessionId, usage] of Array.from(this.usage.entries())) {
      const threshold = this.thresholds.get(sessionId)
      if (!threshold || threshold.limit === 0) continue
      
      const percentUsed = usage.totalTokens / threshold.limit
      if (percentUsed >= thresholdPercent) {
        atRisk.push({
          sessionId,
          usage,
          threshold,
          percentUsed,
        })
      }
    }
    
    return atRisk.sort((a, b) => b.percentUsed - a.percentUsed)
  }

  /**
   * Emit a budget alert event
   */
  private emitAlert(alert: BudgetAlert): void {
    this.logger.warn('Budget alert', {
      sessionId: alert.sessionId,
      usage: alert.currentUsage,
      limit: alert.limit,
      action: alert.action,
    })
    
    if (this.eventBus) {
      ;(this.eventBus as any).emit('budget:alert', {
        type: 'budget:alert',
        sessionId: alert.sessionId,
        parentSessionId: alert.parentSessionId,
        alert,
        timestamp: Date.now(),
      })
    }
  }

  /**
   * Emit a budget warning event (threshold approaching)
   */
  private emitWarning(sessionId: string, currentUsage: number, threshold: BudgetThreshold): void {
    const percentUsed = Math.round((currentUsage / threshold.limit) * 100)
    
    this.logger.info('Budget warning', {
      sessionId,
      usage: currentUsage,
      limit: threshold.limit,
      percentUsed,
    })
    
    if (this.eventBus) {
      ;(this.eventBus as any).emit('budget:warning', {
        type: 'budget:warning',
        sessionId,
        alert: {
          sessionId,
          currentUsage,
          limit: threshold.limit,
          percentUsed,
          action: 'notify',
          timestamp: Date.now(),
          message: `Budget ${percentUsed}% used (${currentUsage}/${threshold.limit} tokens)`,
        },
        timestamp: Date.now(),
      })
    }
  }

  /**
   * Get summary statistics
   */
  getStats(): BudgetMonitorStats {
    const usage = Array.from(this.usage.values())
    const thresholds = Array.from(this.thresholds.entries())
    
    const totalUsage = usage.reduce((sum, u) => sum + u.totalTokens, 0)
    const totalLimit = thresholds.reduce((sum, [, t]) => sum + t.limit, 0)
    
    const sessionsOverBudget = usage.filter(u => {
      const threshold = this.thresholds.get(u.sessionId)
      return threshold && u.totalTokens >= threshold.limit
    }).length
    
    return {
      totalSessions: usage.length,
      sessionsWithThresholds: thresholds.length,
      totalUsage,
      totalLimit,
      overallPercentUsed: totalLimit > 0 ? Math.round((totalUsage / totalLimit) * 100) : 0,
      sessionsOverBudget,
      sessionsAtRisk: this.getAtRiskSessions().length,
    }
  }
}

export interface BudgetMonitorStats {
  totalSessions: number
  sessionsWithThresholds: number
  totalUsage: number
  totalLimit: number
  overallPercentUsed: number
  sessionsOverBudget: number
  sessionsAtRisk: number
}
