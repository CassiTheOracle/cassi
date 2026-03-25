/**
 * Helix Pipeline — Orchestrator for the inverted-triangle agent pattern.
 *
 * Wires four concurrent postures:
 *   - Unity (worker): Full tools, posts work units via WorkStream
 *   - Yang (assertive reviewer): Read-only tools, DialecticChannel + WorkStream
 *   - Yin (cautious reviewer): Read-only tools, DialecticChannel + WorkStream
 *   - Mentor (moderator): Read-only tools, observes dialectic, steers + synthesizes
 *
 * Channels:
 *   - WorkStream: Unity ↔ reviewers (work units up, nudges down)
 *   - DialecticChannel: Yang ↔ Yin (findings, challenges, concessions)
 *   - Blackboard: Mentor → all (steering, flags, synthesis)
 *
 * Watchdog: steer-then-kill (2min warn → 4min escalate → 6min kill)
 */

import type { ILogger, IEventBus } from '../../../types/interfaces.js'
import type { ModelHandle } from '../../model-pool/types.js'
import type { IModelDirective, ModelConfig } from '../../../types/model-routing.js'
import type { ToolExecutor } from '../../tools/executor.js'
import type { ToolRegistry } from '../../tools/registry.js'
import type { PlanHandler } from '../flux-team/plan-handler.js'
import type { HelixStore } from './helix-store.js'
import { Blackboard } from '../flux-team/blackboard.js'
import { WorkStream } from '../dyad/work-stream.js'
import { ContextBudgetCoordinator } from '../cassi-agent/context-budget-coordinator.js'
import { DialecticChannel } from '../lumen/dialectic-channel.js'
import { HelixAgentSession } from './helix-agent-session.js'
import type { ResearchSpawner } from './helix-agent-session.js'
import { UNITY_POSTURE, YANG_REVIEWER_POSTURE, YIN_REVIEWER_POSTURE, MENTOR_POSTURE } from './helix-postures.js'
import type { HelixResult, HelixCompletionStatus, HelixPostureResult } from './types.js'


// ─── Constants ─────────────────────────────────────────────────────────────

const DEFAULT_TIMEOUT_MS = 600_000
const DEFAULT_MAX_MESSAGES = 5000
const DEFAULT_BACKPRESSURE_THRESHOLD = 10
const INACTIVITY_WARN_MS = 120_000
const INACTIVITY_ESCALATE_MS = 240_000
const INACTIVITY_KILL_MS = 360_000


// ─── Pipeline Options ──────────────────────────────────────────────────────

export interface HelixPipelineOpts {
  goal: string
  context?: string
  sessionId: string
  jobId?: string
  logger: ILogger
  timeoutMs?: number

  // Model handles for each posture
  unityHandle: ModelHandle
  yangHandle: ModelHandle
  yinHandle: ModelHandle
  mentorHandle?: ModelHandle

  // Infrastructure
  toolExecutor?: ToolExecutor
  toolRegistry?: ToolRegistry
  store?: HelixStore
  eventBus?: IEventBus
  planHandler?: PlanHandler
  blackboard?: Blackboard
  modelDirective?: IModelDirective
  handleFactory?: (config: ModelConfig) => Promise<ModelHandle>

  // Callbacks
  onCancelRegistered?: (cancelFn: () => void) => void
  onBlackboardCreated?: (bb: Blackboard) => void
  onWorkStreamCreated?: (ws: WorkStream) => void
  onDialecticChannelCreated?: (dc: DialecticChannel) => void

  // Artifact/session context
  artifactNamespace?: string
  sessionType?: 'dyad' | 'lumen' | 'flux' | 'helix' | 'standalone'
  teamId?: string
  moduleDebugSessionId?: string

  /** Optional research spawner — passed to mentor for eager research execution */
  researchSpawner?: ResearchSpawner
}


// ─── Pipeline Function ─────────────────────────────────────────────────────

export async function runHelixPipeline(opts: HelixPipelineOpts): Promise<HelixResult> {
  const startTime = Date.now()
  const {
    sessionId,
    logger,
    timeoutMs = DEFAULT_TIMEOUT_MS,
  } = opts
  const log = logger.child('helix-pipeline')

  log.info('Helix pipeline starting', { sessionId, goal: opts.goal.slice(0, 200) })

  // Emit start event
  opts.eventBus?.emit({
    type: 'team:event' as any,
    teamId: sessionId,
    data: { event: 'helix:started', goal: opts.goal, timestamp: Date.now() },
  } as any)

  // Persist session
  opts.store?.createSession(sessionId, opts.goal, opts.context)
  opts.store?.appendEvent(sessionId, 'helix:started', 'session', 'Helix pipeline started')


  // ── Create Channels ──────────────────────────────────────────────────

  const workStream = new WorkStream(
    DEFAULT_MAX_MESSAGES,
    DEFAULT_BACKPRESSURE_THRESHOLD,
    opts.eventBus,
    sessionId,
  )

  const dialecticChannel = new DialecticChannel(500, opts.eventBus, sessionId)

  // Auto-create Blackboard if not provided
  const blackboard = opts.blackboard ?? new Blackboard(log, sessionId)
  opts.onBlackboardCreated?.(blackboard)
  if (!opts.blackboard) {
    blackboard.initPlan(opts.goal)
    blackboard.initReport(opts.goal)
  }

  opts.onWorkStreamCreated?.(workStream)
  opts.onDialecticChannelCreated?.(dialecticChannel)


  // ── Cancellation ─────────────────────────────────────────────────────

  let cancelled = false
  const cancelFns: Array<() => void> = []

  const cancelAll = () => {
    if (cancelled) return
    cancelled = true
    workStream.forceCancel()
    for (const fn of cancelFns) fn()
  }

  opts.onCancelRegistered?.(cancelAll)


  // ── Session Context ──────────────────────────────────────────────────

  if (opts.toolExecutor && !opts.toolExecutor.hasSessionContext(sessionId)) {
    opts.toolExecutor.setSessionContext(sessionId, {
      artifactNamespace: opts.artifactNamespace ?? `helix:${sessionId}`,
      sessionType: opts.sessionType ?? 'helix',
      teamId: opts.teamId,
    })
  }


  // ── Activity Tracking ────────────────────────────────────────────────

  let lastActivity = Date.now()
  const onActivity = () => { lastActivity = Date.now() }


  // ── Create Agent Sessions ────────────────────────────────────────────

  const commonOpts = {
    sessionId,
    jobId: opts.jobId,
    workStream,
    toolExecutor: opts.toolExecutor,
    toolRegistry: opts.toolRegistry,
    store: opts.store,
    eventBus: opts.eventBus,
    logger: log,
    planHandler: opts.planHandler,
    blackboard,
    modelDirective: opts.modelDirective,
    handleFactory: opts.handleFactory,
    onActivity,
    moduleDebugSessionId: opts.moduleDebugSessionId,
  }

  // Create intelligent context budget coordinator for all postures
  const contextBudgetCoordinator = new ContextBudgetCoordinator(log)

  const unitySession = new HelixAgentSession({
    ...commonOpts,
    role: 'unity',
    handle: opts.unityHandle,
    posture: UNITY_POSTURE,
    postureSlot: 'helix.unity',
    contextBudgetCoordinator,
    // Unity only uses WorkStream, no dialectic channel
  })

  const yangSession = new HelixAgentSession({
    ...commonOpts,
    role: 'yang',
    handle: opts.yangHandle,
    posture: YANG_REVIEWER_POSTURE,
    postureSlot: 'helix.yang',
    dialecticChannel,
    contextBudgetCoordinator,
  })

  const yinSession = new HelixAgentSession({
    ...commonOpts,
    role: 'yin',
    handle: opts.yinHandle,
    posture: YIN_REVIEWER_POSTURE,
    postureSlot: 'helix.yin',
    dialecticChannel,
    contextBudgetCoordinator,
  })

  // Mentor is optional — only created if a mentorHandle is provided
  const mentorSession = opts.mentorHandle ? new HelixAgentSession({
    ...commonOpts,
    role: 'mentor',
    handle: opts.mentorHandle,
    posture: MENTOR_POSTURE,
    postureSlot: 'helix.mentor',
    dialecticChannel,
    contextBudgetCoordinator,
    researchSpawner: opts.researchSpawner,
  }) : null

  cancelFns.push(
    () => unitySession.cancel(),
    () => yangSession.cancel(),
    () => yinSession.cancel(),
  )
  if (mentorSession) cancelFns.push(() => mentorSession.cancel())


  // ── Watchdog (steer-then-kill) ───────────────────────────────────────

  let inactivityWarnSent = false
  let inactivityEscalated = false

  const watchdogInterval = setInterval(() => {
    const silentMs = Date.now() - lastActivity

    // Stage 3: Hard kill (6 min) — log once, cancel, stop the watchdog
    if (silentMs > INACTIVITY_KILL_MS) {
      if (!cancelled) {
        log.warn('Helix pipeline inactivity kill', { sessionId, silentMs })
        cancelAll()
      }
      clearInterval(watchdogInterval)
      return
    }

    // Stage 2: High-severity nudge (4 min)
    if (silentMs > INACTIVITY_ESCALATE_MS && !inactivityEscalated) {
      inactivityEscalated = true
      log.warn('Helix pipeline inactivity escalation', { sessionId, silentMs })
      try {
        workStream.sendNudge({
          id: `inactivity-escalation-${Date.now()}`,
          from: 'apex', to: 'unity',
          severity: 'high',
          content: 'URGENT: Pipeline inactive for 4+ minutes. If stuck, try a different approach. Wrap up current work.',
          timestamp: Date.now(),
          acknowledged: false,
        }, 0)
      } catch (err) {
        log.warn('Inactivity escalation nudge failed (cooldown)', { error: String(err) })
      }
      opts.eventBus?.emit({ type: 'helix:inactivity:escalated' as any, sessionId, silentMs } as any)
      return
    }

    // Stage 1: Gentle nudge (2 min)
    if (silentMs > INACTIVITY_WARN_MS && !inactivityWarnSent) {
      inactivityWarnSent = true
      log.info('Helix pipeline inactivity warning', { sessionId, silentMs })
      workStream.sendNudge({
        id: `inactivity-warn-${Date.now()}`,
        from: 'apex', to: 'unity',
        severity: 'low',
        content: 'Pipeline quiet for 2+ minutes. If working, continue. If stuck, try an alternative approach.',
        timestamp: Date.now(),
        acknowledged: false,
      }, 0)
      opts.eventBus?.emit({ type: 'helix:inactivity:warned' as any, sessionId, silentMs } as any)
      return
    }

    // Reset when activity resumes
    if (silentMs < INACTIVITY_WARN_MS) {
      inactivityWarnSent = false
      inactivityEscalated = false
    }
  }, 15_000)


  // ── Timeout ──────────────────────────────────────────────────────────

  const timeoutHandle = setTimeout(() => {
    log.warn('Helix pipeline timeout', { sessionId, timeoutMs })
    cancelAll()
  }, timeoutMs)


  // ── Run All Postures Concurrently ─────────────────────────────────────

  try {
    const postures: Promise<HelixPostureResult>[] = [
      // Unity: continuous worker loop
      unitySession.runAsWorker(opts.goal, opts.context)
        .catch(err => {
          log.error('Unity failed', { error: String(err) })
          opts.store?.appendEvent(sessionId, 'helix:role:failed', 'unity', String(err))
          opts.eventBus?.emit({ type: 'helix:role:failed' as any, sessionId, role: 'unity', error: String(err) } as any)
          return buildErrorResult(err)
        })
        .finally(() => {
          opts.store?.appendEvent(sessionId, 'helix:role:completed', 'unity', 'Unity completed')
          opts.eventBus?.emit({ type: 'helix:role:completed' as any, sessionId, role: 'unity' } as any)
          onActivity()
        }),

      // Yang: assertive reviewer loop
      yangSession.runAsReviewer(opts.goal, opts.context)
        .catch(err => {
          log.error('Yang reviewer failed', { error: String(err) })
          opts.store?.appendEvent(sessionId, 'helix:role:failed', 'yang', String(err))
          opts.eventBus?.emit({ type: 'helix:role:failed' as any, sessionId, role: 'yang', error: String(err) } as any)
          return buildErrorResult(err)
        })
        .finally(() => {
          opts.store?.appendEvent(sessionId, 'helix:role:completed', 'yang', 'Yang completed')
          opts.eventBus?.emit({ type: 'helix:role:completed' as any, sessionId, role: 'yang' } as any)
          onActivity()
        }),

      // Yin: cautious reviewer loop
      yinSession.runAsReviewer(opts.goal, opts.context)
        .catch(err => {
          log.error('Yin reviewer failed', { error: String(err) })
          opts.store?.appendEvent(sessionId, 'helix:role:failed', 'yin', String(err))
          opts.eventBus?.emit({ type: 'helix:role:failed' as any, sessionId, role: 'yin', error: String(err) } as any)
          return buildErrorResult(err)
        })
        .finally(() => {
          opts.store?.appendEvent(sessionId, 'helix:role:completed', 'yin', 'Yin completed')
          opts.eventBus?.emit({ type: 'helix:role:completed' as any, sessionId, role: 'yin' } as any)
          onActivity()
        }),
    ]

    // Mentor runs concurrently if available (dedicated moderator loop)
    if (mentorSession) {
      postures.push(
        mentorSession.runAsMentor(opts.goal, opts.context)
          .catch(err => {
            log.error('Mentor failed', { error: String(err) })
            opts.store?.appendEvent(sessionId, 'helix:role:failed', 'mentor', String(err))
            opts.eventBus?.emit({ type: 'helix:role:failed' as any, sessionId, role: 'mentor', error: String(err) } as any)
            return buildErrorResult(err)
          })
          .finally(() => {
            opts.store?.appendEvent(sessionId, 'helix:role:completed', 'mentor', 'Mentor completed')
            opts.eventBus?.emit({ type: 'helix:role:completed' as any, sessionId, role: 'mentor' } as any)
            onActivity()
          })
      )
    }

    const settled = await Promise.allSettled(postures)


    // ── Aggregate Results ────────────────────────────────────────────────

    const extract = (s: PromiseSettledResult<HelixPostureResult>) =>
      s.status === 'fulfilled' ? s.value : buildErrorResult(s.reason)

    const unityResult = extract(settled[0])
    const yangResult = extract(settled[1])
    const yinResult = extract(settled[2])
    const mentorResult = settled[3] ? extract(settled[3]) : buildErrorResult('Mentor not configured')

    const pipelineStats = workStream.getStats()
    const dialecticStats = dialecticChannel.getStats()
    const convergencePoints = dialecticChannel.buildConvergencePoints()
    const unresolvedChallenges = dialecticChannel.getUnresolvedChallenges('yang')
      .concat(dialecticChannel.getUnresolvedChallenges('yin'))

    const completionStatus: HelixCompletionStatus = {
      complete: !cancelled,
      unityStatus: unityResult.error ? 'errored' : 'completed',
      yangStatus: yangResult.error ? 'errored' : 'completed',
      yinStatus: yinResult.error ? 'errored' : 'completed',
      mentorStatus: mentorSession ? (mentorResult.error ? 'errored' : 'completed') : 'not-started',
      degraded: !!(unityResult.error || yangResult.error || yinResult.error),
    }

    const result: HelixResult = {
      unitySummary: unityResult.conclusion,
      yangSummary: yangResult.conclusion,
      yinSummary: yinResult.conclusion,
      mentorSynthesis: mentorSession ? mentorResult.conclusion : undefined,

      unityConclusion: unityResult.conclusion,
      yangConclusion: yangResult.conclusion,
      yinConclusion: yinResult.conclusion,
      mentorConclusion: mentorSession ? mentorResult.conclusion : '',

      convergencePoints,
      unresolvedTensions: unresolvedChallenges.map(c => ({
        yangPosition: c.from === 'yang' ? c.counterargument : '',
        yinPosition: c.from === 'yin' ? c.counterargument : '',
        challengeChain: [c.id],
      })),

      dialecticStats: {
        findings: dialecticStats.findings,
        challenges: dialecticStats.challenges,
        concessions: dialecticStats.concessions,
        convergencePoints: convergencePoints.length,
        unresolvedChallenges: unresolvedChallenges.length,
      },

      pipelineStats: {
        workUnitsProduced: pipelineStats.workUnits,
        nudgesSent: pipelineStats.nudges.low + pipelineStats.nudges.high,
        nudgesAcknowledged: pipelineStats.nudges.acknowledged,
      },

      tokensUsed: {
        unity: unityResult.tokensUsed,
        yang: yangResult.tokensUsed,
        yin: yinResult.tokensUsed,
        mentor: mentorResult.tokensUsed,
      },
      iterationCounts: {
        unity: unityResult.iterationCount,
        yang: yangResult.iterationCount,
        yin: yinResult.iterationCount,
        mentor: mentorResult.iterationCount,
      },
      toolCallCounts: {
        unity: unityResult.toolCallCount,
        yang: yangResult.toolCallCount,
        yin: yinResult.toolCallCount,
        mentor: mentorResult.toolCallCount,
      },

      durationMs: Date.now() - startTime,
      completionStatus,

      report: blackboard.getReport() ?? undefined,
      blackboard: blackboard.getSnapshot(),
    }

    // Persist
    opts.store?.completeSession(sessionId, result as any)
    opts.store?.saveWorkStreamMessages(sessionId, workStream.getFullLog())
    opts.store?.appendEvent(sessionId, 'helix:completed', 'session', 'Pipeline completed')
    opts.eventBus?.emit({
      type: 'team:event' as any,
      teamId: sessionId,
      data: { event: 'helix:completed', durationMs: result.durationMs, timestamp: Date.now() },
    } as any)

    log.info('Helix pipeline completed', {
      sessionId,
      durationMs: result.durationMs,
      unityTokens: result.tokensUsed.unity,
      yangTokens: result.tokensUsed.yang,
      yinTokens: result.tokensUsed.yin,
      mentorTokens: result.tokensUsed.mentor,
      findings: result.dialecticStats.findings,
      challenges: result.dialecticStats.challenges,
      workUnits: result.pipelineStats.workUnitsProduced,
      nudges: result.pipelineStats.nudgesSent,
    })

    return result
  } finally {
    clearInterval(watchdogInterval)
    clearTimeout(timeoutHandle)

    // Release model handles
    try { opts.unityHandle.release() } catch { /* best-effort */ }
    try { opts.yangHandle.release() } catch { /* best-effort */ }
    try { opts.yinHandle.release() } catch { /* best-effort */ }
    if (opts.mentorHandle) {
      try { opts.mentorHandle.release() } catch { /* best-effort */ }
    }

    // Clean up session context
    if (opts.toolExecutor) {
      opts.toolExecutor.clearSessionContext(sessionId)
    }
  }
}


// ─── Helpers ───────────────────────────────────────────────────────────────

function buildErrorResult(err: unknown): HelixPostureResult {
  return {
    conclusion: `Errored: ${err instanceof Error ? err.message : String(err)}`,
    confidence: 0,
    keyPoints: [],
    iterationCount: 0,
    toolCallCount: 0,
    tokensUsed: 0,
    durationMs: 0,
    error: err instanceof Error ? err.message : String(err),
  }
}
