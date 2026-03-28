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
import { HelixCoordinator, HelixWorkStream, HelixDialecticMesh } from './helix-coordinator.js'
import { HelixPostureRunner } from './helix-posture-runner.js'
import type { ResearchSpawner } from './helix-posture-runner.js'
import { UNITY_POSTURE, YANG_REVIEWER_POSTURE, YIN_REVIEWER_POSTURE, MENTOR_POSTURE } from './helix-postures.js'
import type { HelixResult, HelixCompletionStatus, HelixPostureResult } from './types.js'
import { HelixBrainstem, createHelixBrainstem } from './brainstem.js'
import type { BrainstemDeps } from './brainstem-types.js'


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
  onCoordinatorCreated?: (coordinator: HelixCoordinator) => void
  onBrainstemCreated?: (brainstem: HelixBrainstem) => void
  onWorkUnit?: (wu: import('../dyad/types.js').WorkUnit, iteration: number) => void

  // Artifact/session context
  artifactNamespace?: string
  sessionType?: 'dyad' | 'lumen' | 'flux' | 'helix' | 'standalone'
  teamId?: string
  moduleDebugSessionId?: string

  /** Optional research spawner — passed to mentor for eager research execution */
  researchSpawner?: ResearchSpawner

  /** Configurable thresholds for UnityStatus proactive signals to reviewers */
  unityStatusThresholds?: import('../dyad/work-stream.js').UnityStatusThresholds

  /** Use Helix-native coordinator with broadcast semantics instead of borrowed primitives */
  useNativeCoordinator?: boolean

  /** Brainstem dependencies — if provided, Brainstem replaces Mentor */
  brainstemDeps?: BrainstemDeps

  /** Configurable inactivity thresholds (ms). Defaults: warn=120s, escalate=240s, kill=360s. */
  inactivityThresholds?: {
    warnMs?: number
    escalateMs?: number
    killMs?: number
  }
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

  let workStream: WorkStream
  let dialecticChannel: DialecticChannel
  let coordinator: HelixCoordinator | undefined

  if (opts.useNativeCoordinator) {
    // Helix-native coordinator with broadcast semantics
    coordinator = new HelixCoordinator({
      sessionId,
      logger: log,
      eventBus: opts.eventBus,
      maxMessages: DEFAULT_MAX_MESSAGES,
      backpressureThreshold: DEFAULT_BACKPRESSURE_THRESHOLD,
    })
    workStream = coordinator.workStream     // HelixWorkStream extends WorkStream
    dialecticChannel = coordinator.dialecticMesh  // HelixDialecticMesh extends DialecticChannel
    opts.onCoordinatorCreated?.(coordinator)
    log.info('Using Helix-native coordinator (broadcast work units, dialectic mesh)')
  } else {
    // Legacy borrowed primitives
    workStream = new WorkStream(
      DEFAULT_MAX_MESSAGES,
      DEFAULT_BACKPRESSURE_THRESHOLD,
      opts.eventBus,
      sessionId,
    )
    dialecticChannel = new DialecticChannel(500, opts.eventBus, sessionId)
  }

  // Auto-create Blackboard if not provided
  const blackboard = opts.blackboard ?? new Blackboard(log, sessionId)
  opts.onBlackboardCreated?.(blackboard)
  if (!opts.blackboard) {
    blackboard.initPlan(opts.goal)
    blackboard.initReport(opts.goal)
  }

  opts.onWorkStreamCreated?.(workStream)
  opts.onDialecticChannelCreated?.(dialecticChannel)


  // ── Create Brainstem (replaces Mentor when brainstemDeps provided) ─────

  let brainstem: HelixBrainstem | undefined
  const useBrainstem = !!opts.brainstemDeps
  const useMentor = !useBrainstem && !!opts.mentorHandle

  if (useBrainstem) {
    // Inject the Helix blackboard into brainstemDeps so the Brainstem can
    // post annotations to the findings/concerns channels. Without this,
    // postToBlackboard silently no-ops when deps.blackboard is undefined.
    if (!opts.brainstemDeps!.blackboard) {
      opts.brainstemDeps!.blackboard = blackboard
    }
    // Wire dialectic channel and tool executor for edit proposal approval
    if (!opts.brainstemDeps!.dialecticChannel) {
      opts.brainstemDeps!.dialecticChannel = dialecticChannel
    }
    if (!opts.brainstemDeps!.toolExecutor && opts.toolExecutor) {
      opts.brainstemDeps!.toolExecutor = opts.toolExecutor
    }
    brainstem = createHelixBrainstem(opts.brainstemDeps!)
    brainstem.start()
    opts.onBrainstemCreated?.(brainstem)
    log.info('Brainstem started (replacing Mentor)')
  }


  // ── Cancellation ─────────────────────────────────────────────────────

  let cancelled = false
  const cancelFns: Array<() => void> = []

  const cancelAll = () => {
    if (cancelled) return
    cancelled = true
    workStream.forceCancel()
    for (const fn of cancelFns) fn()
    // Stop brainstem to prevent zombie LLM annotation calls
    if (brainstem) {
      brainstem.stop().catch(err =>
        log.warn('Error stopping brainstem during cancel', { error: String(err) })
      )
    }
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
    dialecticChannel,
    blackboard,
    logger: log,
    toolExecutor: opts.toolExecutor,
    toolRegistry: opts.toolRegistry,
    store: opts.store,
    eventBus: opts.eventBus,
    modelDirective: opts.modelDirective,
    unityStatusThresholds: opts.unityStatusThresholds,
    planHandler: opts.planHandler,
    onWorkUnit: opts.onWorkUnit,
    onActivity,
    // Forward stream activity to Brainstem for real-time token stream visibility
    onStreamActivity: brainstem
      ? (event: import('./helix-posture-runner.js').StreamActivityEvent) => brainstem!.onStreamActivity(event)
      : undefined,
  }

  const contextBudgetCoordinator = new ContextBudgetCoordinator(log)

  const unitySession = new HelixPostureRunner({
    ...commonOpts,
    role: 'unity',
    handle: opts.unityHandle,
    posture: UNITY_POSTURE,
    postureSlot: 'helix.unity',
    contextBudgetCoordinator,
    brainstem,
  })

  const yangSession = new HelixPostureRunner({
    ...commonOpts,
    role: 'yang',
    handle: opts.yangHandle,
    posture: YANG_REVIEWER_POSTURE,
    postureSlot: 'helix.yang',
    dialecticChannel,
    contextBudgetCoordinator,
  })

  const yinSession = new HelixPostureRunner({
    ...commonOpts,
    role: 'yin',
    handle: opts.yinHandle,
    posture: YIN_REVIEWER_POSTURE,
    postureSlot: 'helix.yin',
    dialecticChannel,
    contextBudgetCoordinator,
  })

  // Mentor only created if brainstem is NOT being used and mentorHandle is provided
  const mentorSession = useMentor ? new HelixPostureRunner({
    ...commonOpts,
    role: 'mentor',
    handle: opts.mentorHandle!,
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


  // ── Brainstem Dialectic Feed ───────────────────────────────────────
  // Drain the 'mentor' cursor from the DialecticChannel periodically,
  // formatting messages as strings and feeding them to the Brainstem.
  // This replaces the Mentor's direct dialecticChannel access.

  let dialecticFeedInterval: ReturnType<typeof setInterval> | null = null

  if (brainstem) {
    const DIALECTIC_POLL_MS = 5_000

    dialecticFeedInterval = setInterval(() => {
      try {
        const drained = dialecticChannel.drainForPosture('mentor')
        if (drained && drained.length > 0) {
          brainstem!.onDialecticUpdate([drained])
          onActivity()
        }
      } catch {
        // Dialectic drain failure is non-fatal
      }
    }, DIALECTIC_POLL_MS)

    log.info('Brainstem dialectic feed started', { pollMs: DIALECTIC_POLL_MS })
  }


  // ── Watchdog (steer-then-kill) ───────────────────────────────────────

  const inactivityWarnMs = opts.inactivityThresholds?.warnMs ?? INACTIVITY_WARN_MS
  const inactivityEscalateMs = opts.inactivityThresholds?.escalateMs ?? INACTIVITY_ESCALATE_MS
  const inactivityKillMs = opts.inactivityThresholds?.killMs ?? INACTIVITY_KILL_MS

  let inactivityWarnSent = false
  let inactivityEscalated = false

  const watchdogInterval = setInterval(() => {
    const silentMs = Date.now() - lastActivity

    // Stage 3: Hard kill — log once, cancel, stop the watchdog
    if (silentMs > inactivityKillMs) {
      if (!cancelled) {
        log.warn('Helix pipeline inactivity kill', { sessionId, silentMs })
        cancelAll()
      }
      clearInterval(watchdogInterval)
      return
    }

    // Stage 2: High-severity nudge
    if (silentMs > inactivityEscalateMs && !inactivityEscalated) {
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

    // Stage 1: Gentle nudge
    if (silentMs > inactivityWarnMs && !inactivityWarnSent) {
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
    if (silentMs < inactivityWarnMs) {
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
    // Only if Brainstem is NOT being used
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
    // mentorResult only exists if Mentor was used (not Brainstem)
    const mentorResult = mentorSession && settled[3] ? extract(settled[3]) : buildErrorResult('Mentor not configured')

    const pipelineStats = workStream.getStats()
    const dialecticStats = dialecticChannel.getStats()
    const convergencePoints = dialecticChannel.buildConvergencePoints()
    const unresolvedChallenges = dialecticChannel.getUnresolvedChallenges('yang')
      .concat(dialecticChannel.getUnresolvedChallenges('yin'))

    // Populate reviewer iteration counts into metrics for the snapshot
    if (coordinator) {
      for (let i = 0; i < yangResult.iterationCount; i++) coordinator.recordReviewerIteration('yang')
      for (let i = 0; i < yinResult.iterationCount; i++) coordinator.recordReviewerIteration('yin')
    }

    // Get Brainstem result if available
    const brainstemResult = brainstem?.getResult()

    const completionStatus: HelixCompletionStatus = {
      complete: !cancelled,
      unityStatus: unityResult.error ? 'errored' : 'completed',
      yangStatus: yangResult.error ? 'errored' : 'completed',
      yinStatus: yinResult.error ? 'errored' : 'completed',
      mentorStatus: useBrainstem
        ? (brainstem ? 'completed' : 'not-started')
        : (mentorSession ? (mentorResult.error ? 'errored' : 'completed') : 'not-started'),
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
      mentorConclusion: useBrainstem
        ? (brainstemResult ? `Brainstem: ${brainstemResult.annotations.length} annotations, avg score ${brainstemResult.averageScore.toFixed(2)}` : '')
        : (mentorSession ? mentorResult.conclusion : ''),

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
        mentor: useBrainstem ? 0 : mentorResult.tokensUsed,
      },
      iterationCounts: {
        unity: unityResult.iterationCount,
        yang: yangResult.iterationCount,
        yin: yinResult.iterationCount,
        mentor: useBrainstem ? 0 : mentorResult.iterationCount,
      },
      toolCallCounts: {
        unity: unityResult.toolCallCount,
        yang: yangResult.toolCallCount,
        yin: yinResult.toolCallCount,
        mentor: useBrainstem ? 0 : mentorResult.toolCallCount,
      },

      durationMs: Date.now() - startTime,
      completionStatus,

      // Consolidated metrics from HelixCoordinator (if native coordinator)
      metrics: coordinator?.getMetricsSnapshot(),

      // Brainstem result (replaces/supersedes mentor)
      brainstem: brainstemResult,

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
      brainstemAnnotations: brainstemResult?.annotations.length ?? 0,
      brainstemAvgScore: brainstemResult?.averageScore ?? 0,
      findings: result.dialecticStats.findings,
      challenges: result.dialecticStats.challenges,
      workUnits: result.pipelineStats.workUnitsProduced,
      nudges: result.pipelineStats.nudgesSent,
    })

    return result
  } finally {
    clearInterval(watchdogInterval)
    clearTimeout(timeoutHandle)
    if (dialecticFeedInterval) clearInterval(dialecticFeedInterval)

    // Stop Brainstem if running
    if (brainstem) {
      try {
        await brainstem.stop()
        log.info('Brainstem stopped')
      } catch (err) {
        log.warn('Brainstem stop failed', { error: String(err) })
      }
    }

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
