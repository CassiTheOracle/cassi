/**
 * trigger.ts — Hybrid trigger logic for Reverie.
 *
 * Combines step-count cadence with manual pings and slow-run debouncing.
 */

import type { ReverieConfig, ReverieTrigger, ReverieTriggerKind } from './types.js'

interface SessionState {
  stepsSinceLastRun: number
  lastRunAt: number
  budgetUsed: number
  /** Outstanding skips after a slow run */
  skipsRemaining: number
  /** Manual pings queued */
  pendingPing: { reason: string; at: number } | null
  /** Last trigger emitted (for debounce) */
  lastTriggerAt: number
}

export class ReverieTriggerController {
  private sessions = new Map<string, SessionState>()

  constructor(private cfg: ReverieConfig) {}

  setConfig(cfg: ReverieConfig): void { this.cfg = cfg }

  /** Manually request a trigger — used by `cassi_lamina ping` or other agents. */
  ping(sessionId: string, reason: string): void {
    const s = this.ensure(sessionId)
    s.pendingPing = { reason, at: Date.now() }
  }

  /** Record a step (one LLM call by the primary). Returns trigger if cadence hits. */
  recordStep(sessionId: string, agentId: string): ReverieTrigger | null {
    if (!this.cfg.enabled) return null
    if (agentId === 'reverie' || agentId === 'meditation') return null  // cascade prevention
    const s = this.ensure(sessionId)
    s.stepsSinceLastRun++

    // Manual ping wins
    if (s.pendingPing) {
      const t: ReverieTrigger = {
        kind: 'ping_lamina',
        reason: s.pendingPing.reason,
        agentId: 'primary',
        occurredAt: Date.now(),
      }
      s.pendingPing = null
      return this.maybeEmit(s, t)
    }

    if (s.stepsSinceLastRun >= this.cfg.stepInterval) {
      const t: ReverieTrigger = {
        kind: 'step_count',
        reason: `${s.stepsSinceLastRun} steps since last reverie`,
        agentId: 'primary',
        occurredAt: Date.now(),
      }
      return this.maybeEmit(s, t)
    }
    return null
  }

  /** Called after Reverie runs to update budget + skip state. */
  recordRun(sessionId: string, opts: { tokens: number; durationMs: number; suppressed: boolean }): void {
    const s = this.ensure(sessionId)
    s.lastRunAt = Date.now()
    s.stepsSinceLastRun = 0
    s.budgetUsed += opts.tokens
    if (!opts.suppressed && opts.durationMs >= this.cfg.slowThresholdMs) {
      s.skipsRemaining = Math.max(s.skipsRemaining, this.cfg.slowSkipCount)
    }
  }

  /** Returns true if we should suppress (budget exhausted or skip cooldown). */
  shouldSuppress(sessionId: string): { suppress: boolean; reason?: string } {
    const s = this.ensure(sessionId)
    if (s.budgetUsed >= this.cfg.sessionTokenBudget) {
      return { suppress: true, reason: 'budget_exhausted' }
    }
    if (s.skipsRemaining > 0) {
      s.skipsRemaining--
      return { suppress: true, reason: 'slow_skip' }
    }
    return { suppress: false }
  }

  reset(sessionId: string): void { this.sessions.delete(sessionId) }

  snapshot(sessionId: string) {
    const s = this.sessions.get(sessionId)
    if (!s) return null
    return { ...s }
  }

  private ensure(sessionId: string): SessionState {
    let s = this.sessions.get(sessionId)
    if (!s) {
      s = { stepsSinceLastRun: 0, lastRunAt: 0, budgetUsed: 0, skipsRemaining: 0, pendingPing: null, lastTriggerAt: 0 }
      this.sessions.set(sessionId, s)
    }
    return s
  }

  private maybeEmit(s: SessionState, trigger: ReverieTrigger): ReverieTrigger | null {
    const now = Date.now()
    if (now - s.lastTriggerAt < this.cfg.minIntervalMs) return null
    s.lastTriggerAt = now
    return trigger
  }
}

export function describeTriggerKind(kind: ReverieTriggerKind): string {
  switch (kind) {
    case 'step_count': return 'cadence'
    case 'affect_spike': return 'affect'
    case 'ping_lamina': return 'ping'
    case 'manual': return 'manual'
    case 'idle': return 'idle'
  }
}
