/**
 * Helix Pipeline — Orchestrator for the inverted-triangle agent pattern.
 *
 * Wires three concurrent postures plus Brainstem:
 *   - Unity (worker): Full tools, posts work units via WorkStream
 *   - Yang (assertive reviewer): Read-only tools, DialecticChannel + WorkStream
 *   - Yin (cautious reviewer): Read-only tools, DialecticChannel + WorkStream
 *   - Brainstem (cognitive organizer): Replaces Mentor, scores work units, detects patterns
 *
 * Channels:
 *   - WorkStream: Unity ↔ reviewers (work units up, nudges down)
 *   - DialecticChannel: Yang ↔ Yin (findings, challenges, concessions)
 *   - Blackboard: Brainstem → Unity (guidance, flags, annotations)
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
import { ContextChunkIndex } from './context-chunk-index.js'
import type { ResearchSpawner } from './helix-posture-runner.js'
import { UNITY_POSTURE, YANG_REVIEWER_POSTURE, YIN_REVIEWER_POSTURE } from './helix-postures.js'
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
  /** @deprecated Mentor path removed — use brainstemDeps instead. Field retained for backward compat but ignored. */
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

  const useBrainstem = !!opts.brainstemDeps
  let brainstem: HelixBrainstem | undefined

  // Create Unity's chunk index early so brainstem can reference it
  const unityChunkIndex = new ContextChunkIndex(log)

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
    // Wire Unity's chunk index so brainstem can pin/evict/score context
    if (!opts.brainstemDeps!.unityChunkIndex) {
      opts.brainstemDeps!.unityChunkIndex = unityChunkIndex
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

  // Create per-posture ContextChunkIndex instances for intelligent context management
  // unityChunkIndex is created earlier so brainstem can reference it
  const yangChunkIndex = new ContextChunkIndex(log)
  const yinChunkIndex = new ContextChunkIndex(log)

  const unitySession = new HelixPostureRunner({
    ...commonOpts,
    role: 'unity',
    handle: opts.unityHandle,
    posture: UNITY_POSTURE,
    postureSlot: 'helix.unity',
    contextBudgetCoordinator,
    brainstem,
    contextChunkIndex: unityChunkIndex,
  })

  const yangSession = new HelixPostureRunner({
    ...commonOpts,
    role: 'yang',
    handle: opts.yangHandle,
    posture: YANG_REVIEWER_POSTURE,
    postureSlot: 'helix.yang',
    dialecticChannel,
    contextBudgetCoordinator,
    contextChunkIndex: yangChunkIndex,
  })

  const yinSession = new HelixPostureRunner({
    ...commonOpts,
    role: 'yin',
    handle: opts.yinHandle,
    posture: YIN_REVIEWER_POSTURE,
    postureSlot: 'helix.yin',
    dialecticChannel,
    contextBudgetCoordinator,
    contextChunkIndex: yinChunkIndex,
  })

  // Mentor path removed — Brainstem is the only cognitive organizer
  // Legacy mentorHandle field retained for backward compat but ignored

  cancelFns.push(
    () => unitySession.cancel(),
    () => yangSession.cancel(),
    () => yinSession.cancel(),
  )


  // ── Brainstem Dialectic Feed (Event-Driven) ─────────────────────────
  // Drain the 'mentor' cursor from the DialecticChannel when dialectic events occur.
  // Uses a small debounce to batch rapid dialectic exchanges.
  // This replaces the Mentor's direct dialecticChannel access.

  let dialecticFeedTimer: ReturnType<typeof setTimeout> | null = null
  const DIALECTIC_FEED_DEBOUNCE_MS = 200

  if (brainstem) {
    const feedDialecticToBrainstem = () => {
      try {
        const drained = dialecticChannel.drainForPosture('mentor')
        if (drained && drained.length > 0) {
          brainstem!.onDialecticUpdate([drained])
          onActivity()
        }
      } catch {
        // Dialectic drain failure is non-fatal
      }
    }

    // Subscribe to dialectic events for push-based feed
    const dialecticEventTypes = [
      'dialectic:finding',
      'dialectic:challenge',
      'dialectic:concession',
      'dialectic:investigation_request',
    ]

    for (const eventType of dialecticEventTypes) {
      opts.eventBus?.on(eventType as any, () => {
        // Debounce to batch rapid dialectic exchanges
        if (dialecticFeedTimer) clearTimeout(dialecticFeedTimer)
        dialecticFeedTimer = setTimeout(feedDialecticToBrainstem, DIALECTIC_FEED_DEBOUNCE_MS)
      })
    }

    log.info('Brainstem dialectic feed started (event-driven, debounce=' + DIALECTIC_FEED_DEBOUNCE_MS + 'ms)')
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

  // Phase 4: Lazy reviewer spawning
  // When brainstem has lazy spawning enabled, reviewers wait for the brainstem
  // to evaluate early work units before deciding whether to activate.
  // If the task is simple (high goal alignment, no detected patterns), reviewers
  // are skipped entirely — saving ~47% of token budget on simple tasks.

  const REVIEWER_ACTIVATION_CHECK_MS = 3_000
  const REVIEWER_ACTIVATION_MAX_WAIT_MS = 30_000
  let reviewersSkipped = false

  /**
   * Wait for brainstem to evaluate enough work units, then decide whether to
   * start reviewers. Returns immediately if brainstem doesn't support lazy spawning.
   */
  async function waitForReviewerDecision(): Promise<boolean> {
    if (!brainstem) return true // no brainstem = always start reviewers
    if (!brainstem.shouldActivateReviewers()) {
      // Not enough data yet — poll until brainstem can decide
      const start = Date.now()
      while (Date.now() - start < REVIEWER_ACTIVATION_MAX_WAIT_MS) {
        await new Promise(resolve => setTimeout(resolve, REVIEWER_ACTIVATION_CHECK_MS))
        if (cancelled) return false
        // Once brainstem has processed enough work units, it returns a real decision
        const shouldActivate = brainstem.shouldActivateReviewers()
        // If it returns true, it either means "activate" or "not enough data yet"
        // We need to check if it has processed enough to make a real decision
        if (brainstem.getWorkUnitsProcessed() >= (brainstem.getReviewerActivationThreshold())) {
          return shouldActivate
        }
      }
      // Timeout waiting for decision — default to activating reviewers
      log.info('Reviewer activation decision timed out, defaulting to activate')
      return true
    }
    return true
  }

  try {
    // Start Unity immediately — it's always needed
    const unityPromise = unitySession.runAsWorker(opts.goal, opts.context)
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
      })

    // Decide whether to start reviewers (may wait for brainstem evaluation)
    const shouldStartReviewers = await waitForReviewerDecision()

    let yangPromise: Promise<HelixPostureResult>
    let yinPromise: Promise<HelixPostureResult>

    if (shouldStartReviewers && !cancelled) {
      log.info('Starting reviewers (brainstem decision: activate)')
      opts.store?.appendEvent(sessionId, 'helix:reviewers:activated', 'session', 'Reviewers activated by brainstem decision')

      yangPromise = yangSession.runAsReviewer(opts.goal, opts.context)
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
        })

      yinPromise = yinSession.runAsReviewer(opts.goal, opts.context)
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
        })
    } else {
      reviewersSkipped = true
      log.info('Reviewers skipped (brainstem decision: task is simple)')
      opts.store?.appendEvent(sessionId, 'helix:reviewers:skipped', 'session', 'Reviewers skipped — brainstem assessed task as simple')
      opts.eventBus?.emit({ type: 'helix:reviewers:skipped' as any, sessionId } as any)

      // Return immediate not-started results for skipped reviewers
      yangPromise = Promise.resolve(buildErrorResult('Reviewers skipped — task assessed as simple'))
      yinPromise = Promise.resolve(buildErrorResult('Reviewers skipped — task assessed as simple'))
    }

    const postures: Promise<HelixPostureResult>[] = [unityPromise, yangPromise, yinPromise]
    const settled = await Promise.allSettled(postures)


    // ── Aggregate Results ────────────────────────────────────────────────

    const extract = (s: PromiseSettledResult<HelixPostureResult>) =>
      s.status === 'fulfilled' ? s.value : buildErrorResult(s.reason)

    const unityResult = extract(settled[0])
    const yangResult = extract(settled[1])
    const yinResult = extract(settled[2])
    // Mentor path removed — Brainstem is the only cognitive organizer

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
      yangStatus: reviewersSkipped ? 'not-started' : (yangResult.error ? 'errored' : 'completed'),
      yinStatus: reviewersSkipped ? 'not-started' : (yinResult.error ? 'errored' : 'completed'),
      mentorStatus: brainstem ? 'completed' : 'not-started',
      degraded: !!(unityResult.error || (!reviewersSkipped && (yangResult.error || yinResult.error))),
    }

    const result: HelixResult = {
      unitySummary: unityResult.conclusion,
      yangSummary: yangResult.conclusion,
      yinSummary: yinResult.conclusion,
      mentorSynthesis: undefined,

      unityConclusion: unityResult.conclusion,
      yangConclusion: yangResult.conclusion,
      yinConclusion: yinResult.conclusion,
      mentorConclusion: brainstemResult
        ? `Brainstem: ${brainstemResult.annotations.length} annotations, avg score ${brainstemResult.averageScore.toFixed(2)}`
        : '',

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
        mentor: 0,
      },
      iterationCounts: {
        unity: unityResult.iterationCount,
        yang: yangResult.iterationCount,
        yin: yinResult.iterationCount,
        mentor: 0,
      },
      toolCallCounts: {
        unity: unityResult.toolCallCount,
        yang: yangResult.toolCallCount,
        yin: yinResult.toolCallCount,
        mentor: 0,
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
    if (dialecticFeedTimer) clearTimeout(dialecticFeedTimer)

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
    // Legacy mentorHandle release — no-op for backward compat (Mentor path removed)
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
