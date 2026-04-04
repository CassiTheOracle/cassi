/**
 * Constellation Audit Trail — Event-driven decision logging.
 *
 * Subscribes to Constellation lifecycle events via EventBus and writes
 * structured decision manifests to FileArtifactStore. Each Constellation
 * run gets a namespace `constellation:{sessionId}` with versioned JSON
 * files that capture decomposition plans, spawn decisions, and completion
 * summaries.
 *
 * The manifests are accessible via cassi://files/ URIs and the admin API,
 * providing git-independent auditability of Constellation reasoning.
 *
 * HOW: This module is purely reactive — it never modifies Constellation
 * behavior. It subscribes to events that are already emitted and creates
 * artifacts from them.
 */

import type { ILogger, IEventBus } from '../../../types/interfaces.js'
import type { EventType } from '../../../types/events.js'
import type { FileArtifactStore } from '../../file-artifact-store.js'


/** Minimal event shape from the EventBus */
interface ConstellationEvent {
  type: string
  data?: Record<string, unknown>
  sessionId?: string
  timestamp?: number
}


/**
 * Decision entry recorded in the audit trail.
 * Each entry is appended to the decisions manifest with a new version.
 */
export interface AuditDecision {
  type: 'spawn-approved' | 'spawn-rejected' | 'directive-issued' | 'branch-completed' | 'branch-failed' | 're-decomposition'
  timestamp: number
  details: Record<string, unknown>
}


/**
 * Plan manifest written when decomposition completes.
 */
export interface AuditPlan {
  goal: string
  strategy: string
  subTasks: Array<{
    goal: string
    template?: string
    priority: number
  }>
  templateCapabilities?: Record<string, unknown>
  createdAt: number
}


/**
 * Summary manifest written when a Constellation completes.
 */
export interface AuditSummary {
  goal: string
  sessionId: string
  status: 'completed' | 'failed' | 'cancelled'
  totalNodes: number
  totalDurationMs: number
  totalTokensUsed: number
  synthesis?: string
  spawnDecisions: number
  completedAt: number
}


/**
 * Create a Constellation audit trail writer.
 *
 * Call `start()` to begin listening to events, `stop()` to unsubscribe.
 * The writer is designed to be attached once when the daemon boots and
 * left running for the lifetime of the process.
 */
export function createConstellationAuditTrail(deps: {
  eventBus: IEventBus
  artifactStore: FileArtifactStore
  logger: ILogger
}): ConstellationAuditTrail {
  const { eventBus, artifactStore, logger } = deps
  const log = logger.child('constellation-audit-trail')
  const unsubscribers: Array<() => void> = []

  // Track active session namespaces and their decision counts
  const sessionDecisionCounts = new Map<string, number>()

  function namespace(sessionId: string): string {
    return `constellation:${sessionId}`
  }

  function writeArtifact(sessionId: string, path: string, content: unknown, message: string): void {
    try {
      artifactStore.write({
        namespace: namespace(sessionId),
        path,
        content: JSON.stringify(content, null, 2),
        mimeType: 'application/json',
        agentId: 'constellation-audit-trail',
        message,
        visibility: 'shared',
        tags: ['constellation', 'audit-trail'],
        pinned: true,
      })
    } catch (err) {
      log.warn('Failed to write audit artifact', { sessionId, path, error: String(err) })
    }
  }

  function writeDecompositionPlan(sessionId: string, goal: string, strategy: string, subTasks: AuditPlan['subTasks']): void {
    const plan: AuditPlan = {
      goal,
      strategy,
      subTasks,
      createdAt: Date.now(),
    }

    writeArtifact(sessionId, 'plan.json', plan, 'Constellation decomposition plan')
    sessionDecisionCounts.set(sessionId, 0)
    log.debug('Wrote decomposition plan', { sessionId })
  }

  function writeCompletionSummary(sessionId: string, data: Partial<AuditSummary>): void {
    const summary: AuditSummary = {
      goal: data.goal ?? '(unknown)',
      sessionId,
      status: data.status ?? 'completed',
      totalNodes: data.totalNodes ?? 0,
      totalDurationMs: data.totalDurationMs ?? 0,
      totalTokensUsed: data.totalTokensUsed ?? 0,
      synthesis: data.synthesis,
      spawnDecisions: sessionDecisionCounts.get(sessionId) ?? 0,
      completedAt: Date.now(),
    }

    writeArtifact(sessionId, 'summary.json', summary, 'Constellation completion summary')
    sessionDecisionCounts.delete(sessionId)
    log.debug('Wrote completion summary', { sessionId })
  }

  function onSpawnDecision(event: ConstellationEvent): void {
    const sessionId = event.sessionId ?? event.data?.sessionId as string ?? event.data?.constellationId as string
    if (!sessionId) return

    const data = event.data ?? {}
    const decision: AuditDecision = {
      type: data.approved ? 'spawn-approved' : 'spawn-rejected',
      timestamp: Date.now(),
      details: {
        requestId: data.requestId,
        goal: data.goal,
        reason: data.reason,
        suggestedTemplate: data.suggestedTemplate,
      },
    }

    const count = (sessionDecisionCounts.get(sessionId) ?? 0) + 1
    sessionDecisionCounts.set(sessionId, count)

    writeArtifact(sessionId, 'decisions.json', decision, `Spawn decision #${count}: ${decision.type}`)
    log.debug('Wrote spawn decision', { sessionId, type: decision.type })
  }

  function onDirective(event: ConstellationEvent): void {
    const sessionId = event.sessionId ?? event.data?.sessionId as string ?? event.data?.constellationId as string
    if (!sessionId) return

    const data = event.data ?? {}
    const decision: AuditDecision = {
      type: 'directive-issued',
      timestamp: Date.now(),
      details: {
        targetHelixId: data.targetHelixId,
        directiveType: data.type,
        urgency: data.urgency,
        content: typeof data.content === 'string' ? data.content.slice(0, 500) : undefined,
      },
    }

    const count = (sessionDecisionCounts.get(sessionId) ?? 0) + 1
    sessionDecisionCounts.set(sessionId, count)

    writeArtifact(sessionId, 'decisions.json', decision, `Directive #${count}: ${data.type}`)
  }

  function onBranchClosed(event: ConstellationEvent): void {
    const sessionId = event.sessionId ?? event.data?.sessionId as string ?? event.data?.constellationId as string
    if (!sessionId) return

    const data = event.data ?? {}
    const decision: AuditDecision = {
      type: 'branch-failed',
      timestamp: Date.now(),
      details: {
        helixId: data.helixId ?? data.targetHelixId,
        level: data.level,
        reason: data.reason,
      },
    }

    const count = (sessionDecisionCounts.get(sessionId) ?? 0) + 1
    sessionDecisionCounts.set(sessionId, count)

    writeArtifact(sessionId, 'decisions.json', decision, `Escalation: ${data.helixId ?? data.targetHelixId}`)
  }

  function onRedecomposition(event: ConstellationEvent): void {
    const sessionId = event.sessionId ?? event.data?.sessionId as string ?? event.data?.constellationId as string
    if (!sessionId) return

    const data = event.data ?? {}
    const decision: AuditDecision = {
      type: 're-decomposition',
      timestamp: Date.now(),
      details: {
        sourceHelixId: data.sourceHelixId,
        reason: data.reason,
        newSubTasks: data.newSubTasks,
        killSource: data.killSource,
      },
    }

    const count = (sessionDecisionCounts.get(sessionId) ?? 0) + 1
    sessionDecisionCounts.set(sessionId, count)

    writeArtifact(sessionId, 'decisions.json', decision, `Re-decomposition from ${data.sourceHelixId}`)
    log.debug('Wrote re-decomposition decision', { sessionId })
  }

  return {
    start() {
      // WHY: Event names match what's emitted in corpus.ts emitEvent().
      // The Corpus emits these as untyped (cast to `any`), so we cast to EventType.
      // WHY: Decomposition events are logged but not emitted — the audit trail
      // captures them indirectly through spawn decisions and branch events.
      const handlers: Array<[string, (e: ConstellationEvent) => void]> = [
        ['corpus:spawn-decision', onSpawnDecision],
        ['corpus:intervention', onDirective],
        ['corpus:redecomposition', onRedecomposition],
        ['corpus:escalation', onBranchClosed],
      ]

      for (const [type, handler] of handlers) {
        // WHY: Corpus emits events as `any` (see corpus.ts emitEvent).
        // These event names are not in the typed EventType union, so we
        // cast to EventType — same pattern used in event-bus.ts itself.
        const unsub = eventBus.on(type as EventType, handler as (event: unknown) => void)
        unsubscribers.push(unsub)
      }

      log.info('Constellation audit trail started', { events: handlers.map(h => h[0]) })
    },

    stop() {
      for (const unsub of unsubscribers) unsub()
      unsubscribers.length = 0
      sessionDecisionCounts.clear()
      log.info('Constellation audit trail stopped')
    },

    /** Get decision count for an active session */
    getDecisionCount(sessionId: string): number {
      return sessionDecisionCounts.get(sessionId) ?? 0
    },

    /**
     * Read the full audit trail for a session.
     * Returns plan, decisions, and summary if available.
     */
    readTrail(sessionId: string): { plan?: AuditPlan; decisions: AuditDecision[]; summary?: AuditSummary } {
      const ns = namespace(sessionId)
      const result: { plan?: AuditPlan; decisions: AuditDecision[]; summary?: AuditSummary } = {
        decisions: [],
      }

      function contentToString(content: string | Buffer): string {
        return typeof content === 'string' ? content : content.toString('utf-8')
      }

      try {
        const planResult = artifactStore.read({ namespace: ns, path: 'plan.json', admin: true })
        if (planResult) result.plan = JSON.parse(contentToString(planResult.content))
      } catch {
        // Plan not yet written or read failed
      }

      try {
        const versions = artifactStore.listVersions({ namespace: ns, path: 'decisions.json' })
        for (const v of versions) {
          try {
            const vResult = artifactStore.read({ namespace: ns, path: 'decisions.json', version: v.versionNumber, admin: true })
            if (vResult) result.decisions.push(JSON.parse(contentToString(vResult.content)))
          } catch {
            // Version read failed — skip
          }
        }
      } catch {
        // No decisions yet
      }

      try {
        const summaryResult = artifactStore.read({ namespace: ns, path: 'summary.json', admin: true })
        if (summaryResult) result.summary = JSON.parse(contentToString(summaryResult.content))
      } catch {
        // Summary not yet written
      }

      return result
    },

    writeDecompositionPlan,
    writeCompletionSummary,
  }
}


export interface ConstellationAuditTrail {
  start(): void
  stop(): void
  getDecisionCount(sessionId: string): number
  readTrail(sessionId: string): { plan?: AuditPlan; decisions: AuditDecision[]; summary?: AuditSummary }

  /**
   * Write a decomposition plan for a session.
   * Called by the pipeline after decomposition completes.
   * (Decomposition events are not emitted to EventBus, so this must be called directly.)
   */
  writeDecompositionPlan(sessionId: string, goal: string, strategy: string, subTasks: AuditPlan['subTasks']): void

  /**
   * Write a completion summary for a session.
   * Called by the pipeline when a Constellation finishes.
   * (Completion events are not emitted to EventBus, so this must be called directly.)
   */
  writeCompletionSummary(sessionId: string, data: Partial<AuditSummary>): void
}
