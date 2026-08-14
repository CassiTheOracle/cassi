/**
 * External Corpus Protocol — Allow external agents to assume the Corpus role.
 *
 * Extracted from corpus.ts to improve modularity and testability.
 * When an external agent assumes Corpus, the internal LLM loop pauses
 * and all decisions route through the external agent's MCP tool calls.
 */

import type { ILogger, IEventBus } from '../vendor/types/interfaces.js'
import type {
  ExternalCorpusState,
  ExternalCorpusSnapshot,
  PendingExternalSpawnRequest,
  CorpusDirective,
  CorpusDirectiveType,
  ICorpusTree,
  CorpusProcessedState,
  SpawnDecision,
  CorpusDeps,
} from '../corpus-types.js'
import { createInitialExternalCorpusState, DEFAULT_EXTERNAL_CORPUS_HEARTBEAT_MS } from '../corpus-types.js'
import type { GuidanceUrgency } from '../vendor/helix/brainstem-types.js'


/**
 * Callbacks the ExternalCorpusProtocol needs from the parent Corpus.
 */
export interface ExternalCorpusCallbacks {
  /** Check if the Corpus is running */
  isRunning: () => boolean
  /** Check if the Corpus has been stopped */
  isStopped: () => boolean
  /** Get the constellation ID */
  getConstellationId: () => string
  /** Get a snapshot for external view */
  getExternalSnapshot: () => ExternalCorpusSnapshot
  /** Post synthesis to blackboard */
  postSynthesisToBlackboard: (content: string, author: string) => void
  /** Handle approved spawn request */
  onSpawnRequest: (request: { requestingHelixId: string; goal: string; context?: string; template?: string }) => void
  /** Record spawn decision */
  recordSpawnDecision: (decision: SpawnDecision) => void
  /** Send a directive to a branch */
  sendDirective: (directive: CorpusDirective) => void
  /** Emit an event */
  emitEvent: (type: string, data: Record<string, unknown>) => void
}


/**
 * ExternalCorpusProtocol — Manages external agent assumption of Corpus role.
 *
 * When an external agent assumes Corpus, the internal LLM loop pauses
 * and all Corpus decisions are routed through MCP tool calls from the
 * external agent instead. This enables any MCP-connected agent (including
 * humans via TUI, external orchestrators, or more powerful models) to act
 * as the strategic overseer of a Constellation.
 */
export class ExternalCorpusProtocol {
  private state: ExternalCorpusState
  private callbacks: ExternalCorpusCallbacks
  private logger: ILogger
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null

  constructor(deps: {
    callbacks: ExternalCorpusCallbacks
    logger: ILogger
  }) {
    this.state = createInitialExternalCorpusState()
    this.callbacks = deps.callbacks
    this.logger = deps.logger.child('ExternalCorpusProtocol')
  }

  /**
   * Allow an external agent to assume the Corpus role.
   *
   * HOW: The running loop continues processing steps and tracking state,
   * but LLM analysis is skipped while an external agent holds the lock.
   * Spawn requests queue up instead of auto-evaluating.
   */
  assume(
    agentId: string,
    heartbeatTimeoutMs?: number
  ): { assumed: boolean; snapshot: ExternalCorpusSnapshot | null; error?: string } {
    if (this.state.assumed) {
      return {
        assumed: false,
        snapshot: null,
        error: `Corpus is already assumed by agent "${this.state.agentId}"`,
      }
    }

    if (!this.callbacks.isRunning()) {
      return {
        assumed: false,
        snapshot: null,
        error: 'Corpus is not running',
      }
    }

    // Validate agentId format
    if (!agentId || typeof agentId !== 'string' || agentId.length > 128 || !/^[a-zA-Z0-9_-]+$/.test(agentId)) {
      return {
        assumed: false,
        snapshot: null,
        error: 'agentId must be 1-128 alphanumeric characters, hyphens, or underscores',
      }
    }

    this.state.assumed = true
    this.state.agentId = agentId
    this.state.assumedAt = Date.now()
    this.state.lastActionAt = Date.now()
    if (heartbeatTimeoutMs) {
      this.state.heartbeatTimeoutMs = heartbeatTimeoutMs
    }

    // Start heartbeat monitoring
    this.startHeartbeatMonitor()

    this.logger.info('External agent assumed Corpus role', {
      agentId,
      heartbeatTimeoutMs: this.state.heartbeatTimeoutMs,
    })

    this.callbacks.emitEvent('corpus:external-assumed', {
      agentId,
      constellationId: this.callbacks.getConstellationId(),
    })

    return {
      assumed: true,
      snapshot: this.callbacks.getExternalSnapshot(),
    }
  }

  /**
   * Release the Corpus role back to the internal LLM loop.
   * Can be called by the external agent or triggered by heartbeat timeout.
   */
  release(reason?: string): { released: boolean; error?: string } {
    if (!this.state.assumed) {
      return { released: false, error: 'No external agent holds the Corpus role' }
    }

    const agentId = this.state.agentId
    const heldForMs = Date.now() - (this.state.assumedAt ?? Date.now())

    // Stop heartbeat monitoring
    this.stopHeartbeatMonitor()

    // Clear pending spawn requests — they'll be re-evaluated by internal Corpus
    const pendingCount = this.state.pendingSpawnRequests.length

    // Reset external state
    this.state = createInitialExternalCorpusState()

    this.logger.info('External agent released Corpus role', {
      agentId,
      reason: reason ?? 'explicit release',
      heldForMs,
      pendingSpawnRequestsDropped: pendingCount,
    })

    this.callbacks.emitEvent('corpus:external-released', {
      agentId,
      reason: reason ?? 'explicit release',
      heldForMs,
      constellationId: this.callbacks.getConstellationId(),
    })

    return { released: true }
  }

  /**
   * Check if an external agent currently holds the Corpus role.
   */
  isAssumed(): boolean {
    return this.state.assumed
  }

  /**
   * Get the external Corpus state (for status queries).
   */
  getState(): ExternalCorpusState {
    return { ...this.state, pendingSpawnRequests: [...this.state.pendingSpawnRequests] }
  }

  /**
   * External agent sends a directive to a branch.
   * Updates heartbeat timestamp.
   */
  sendDirective(
    directive: Omit<CorpusDirective, 'timestamp'>
  ): { sent: boolean; error?: string } {
    if (!this.state.assumed) {
      return { sent: false, error: 'No external agent holds the Corpus role' }
    }

    // Validate directive type
    const allowedTypes = new Set(['guidance', 'redirect', 'throttle', 'priority-shift', 'cancel', 'context-inject'])
    if (!allowedTypes.has(directive.type)) {
      return { sent: false, error: `Invalid directive type "${directive.type}". Allowed: ${[...allowedTypes].join(', ')}` }
    }

    // Validate directive fields
    if (!directive.text || typeof directive.text !== 'string') {
      return { sent: false, error: 'Directive text is required' }
    }
    if (directive.text.length > 10_000) {
      return { sent: false, error: 'Directive text must be 10,000 characters or less' }
    }

    this.touchHeartbeat()

    this.callbacks.sendDirective({
      ...directive,
      timestamp: Date.now(),
    })

    this.callbacks.emitEvent('corpus:external-directive', {
      targetHelixId: directive.targetHelixId,
      type: directive.type,
      urgency: directive.urgency,
      agentId: this.state.agentId,
      textLength: directive.text.length,
    })

    return { sent: true }
  }

  /**
   * External agent decides on a pending spawn request.
   * Updates heartbeat timestamp.
   */
  decideSpawn(
    requestId: string,
    approved: boolean,
    reason: string,
    modifiedGoal?: string
  ): { decided: boolean; error?: string } {
    if (!this.state.assumed) {
      return { decided: false, error: 'No external agent holds the Corpus role' }
    }
    this.touchHeartbeat()

    const requestIdx = this.state.pendingSpawnRequests.findIndex(r => r.requestId === requestId)
    if (requestIdx === -1) {
      return { decided: false, error: `Spawn request "${requestId}" not found` }
    }

    const request = this.state.pendingSpawnRequests[requestIdx]
    this.state.pendingSpawnRequests.splice(requestIdx, 1)

    const decision: SpawnDecision = {
      requestId,
      requestingHelixId: request.requestingHelixId,
      goal: modifiedGoal ?? request.goal,
      approved,
      reason,
      evaluatedAt: Date.now(),
    }
    this.callbacks.recordSpawnDecision(decision)

    if (approved) {
      this.callbacks.onSpawnRequest({
        requestingHelixId: request.requestingHelixId,
        goal: modifiedGoal ?? request.goal,
        context: request.context,
        template: request.template,
      })
    }

    this.callbacks.emitEvent('corpus:external-spawn-decision', {
      requestId,
      approved,
      reason,
      agentId: this.state.agentId,
    })

    return { decided: true }
  }

  /**
   * External agent posts a synthesis visible to all branches.
   * Updates heartbeat timestamp.
   */
  postSynthesis(
    content: string,
    priority?: number,
    tags?: string[]
  ): { posted: boolean; error?: string } {
    if (!this.state.assumed) {
      return { posted: false, error: 'No external agent holds the Corpus role' }
    }

    if (!content || typeof content !== 'string') {
      return { posted: false, error: 'Synthesis content is required' }
    }
    if (content.length > 10_000) {
      return { posted: false, error: 'Synthesis content must be 10,000 characters or less' }
    }

    this.touchHeartbeat()

    this.callbacks.postSynthesisToBlackboard(content, `External Corpus (${this.state.agentId})`)

    this.callbacks.emitEvent('corpus:external-synthesis', {
      agentId: this.state.agentId,
      contentLength: content.length,
    })

    return { posted: true }
  }

  /**
   * Queue a spawn request for external decision (called internally when assumed).
   */
  queueSpawnRequest(request: {
    requestId: string
    requestingHelixId: string
    goal: string
    context?: string
    template?: string
    targetDepth: number
  }): void {
    this.state.pendingSpawnRequests.push({
      ...request,
      queuedAt: Date.now(),
    })
    this.logger.info('Spawn request queued for external Corpus', {
      requestId: request.requestId,
      agentId: this.state.agentId,
    })
    this.callbacks.emitEvent('corpus:external-spawn-queued', {
      requestId: request.requestId,
      agentId: this.state.agentId,
    })
  }

  /**
   * Get pending spawn requests.
   */
  getPendingSpawnRequests(): PendingExternalSpawnRequest[] {
    return [...this.state.pendingSpawnRequests]
  }

  /**
   * Get the current agent ID.
   */
  getAgentId(): string | null {
    return this.state.agentId
  }

  /** Update heartbeat timestamp */
  private touchHeartbeat(): void {
    this.state.lastActionAt = Date.now()
  }

  /** Start heartbeat monitoring interval */
  private startHeartbeatMonitor(): void {
    this.stopHeartbeatMonitor()
    const checkInterval = Math.min(10_000, this.state.heartbeatTimeoutMs / 3)
    this.heartbeatTimer = setInterval(() => {
      // HOW: Check stopped flag to prevent post-shutdown callbacks
      if (this.callbacks.isStopped() || !this.state.assumed) {
        this.stopHeartbeatMonitor()
        return
      }
      const elapsed = Date.now() - (this.state.lastActionAt ?? 0)
      if (elapsed > this.state.heartbeatTimeoutMs) {
        this.logger.warn('External Corpus heartbeat timeout — auto-releasing', {
          agentId: this.state.agentId,
          elapsedMs: elapsed,
          timeoutMs: this.state.heartbeatTimeoutMs,
        })
        this.release('heartbeat timeout')
      }
    }, checkInterval)
    // WHY: unref prevents the timer from keeping the event loop alive during shutdown
    if (typeof this.heartbeatTimer.unref === 'function') {
      this.heartbeatTimer.unref()
    }
  }

  /** Stop heartbeat monitoring interval */
  private stopHeartbeatMonitor(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  /** Stop heartbeat monitor (called during shutdown) */
  stop(): void {
    this.stopHeartbeatMonitor()
  }
}