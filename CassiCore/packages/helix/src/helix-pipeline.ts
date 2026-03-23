/*
 * Helix Pipeline — Orchestrator for the inverted-triangle agent pattern.
 *
 * Wires three concurrent postures:
 *   - Unity (worker): Full tools, posts work units via WorkStream
 *   - Yang (assertive reviewer): Read-only tools, DialecticChannel + WorkStream
 *   - Yin (cautious reviewer): Read-only tools, DialecticChannel + WorkStream
 *
 * Channels:
 *   - WorkStream: Unity ↔ reviewers (work units up, nudges down)
 *   - DialecticChannel: Yang ↔ Yin (findings, challenges, concessions)
 *
 * Watchdog: steer-then-kill (2min warn → 4min escalate → 6min kill)
 */

import type { ILogger, IEventBus } from '../../../types/interfaces.js'
import type { ModelHandle } from '../../model-pool/types.js'
import type { IModelDirective, ModelConfig } from '../../../types/model-routing.js'
import type { ToolExecutor } from '../../tools/executor.js'
import type { ToolRegistry } from '../../tools/registry.js'
import type { PlanHandler } from '../flux-team/plan-handler.js'
import type { DyadStore } from '../dyad/dyad-store.js'
import { Blackboard } from '../flux-team/blackboard.js'
import { WorkStream } from '../dyad/work-stream.js'
import { DialecticChannel } from '../lumen/dialectic-channel.js'
import { HelixAgentSession } from './helix-agent-session.js'
import { UNITY_POSTURE, YANG_REVIEWER_POSTURE, YIN_REVIEWER_POSTURE } from './helix-postures.js'
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

  // Infrastructure
  toolExecutor?: ToolExecutor
  toolRegistry?: ToolRegistry
  store?: DyadStore
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

  const unitySession = new HelixAgentSession({
    ...commonOpts,
    role: 'unity',
    handle: opts.unityHandle,
    posture: UNITY_POSTURE,
    postureSlot: 'helix.unity',
    // Unity only uses WorkStream, no dialectic channel
  })

  const yangSession = new HelixAgentSession({
    ...commonOpts,
    role: 'yang',
    handle: opts.yangHandle,
    posture: YANG_REVIEWER_POSTURE,
    postureSlot: 'helix.yang',
    dialecticChannel,
  })

  const yinSession = new HelixAgentSession({
    ...commonOpts,
    role: 'yin',
    handle: opts.yinHandle,
    posture: YIN_REVIEWER_POSTURE,
    postureSlot: 'helix.yin',
    dialecticChannel,
  })

  // ... (pipeline orchestration omitted for brevity) ...

  try {
    // (run sessions, gather results)

    // Build result
    const result: HelixResult = {
      startTime,
      sessionId,

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
      },
      iterationCounts: {
        unity: unityResult.iterationCount,
        yang: yangResult.iterationCount,
        yin: yinResult.iterationCount,
      },
      toolCallCounts: {
        unity: unityResult.toolCallCount,
        yang: yangResult.toolCallCount,
        yin: yinResult.toolCallCount,
      },

      durationMs: Date.now() - startTime,
      completionStatus,

      report: blackboard.getReport() ?? undefined,
      blackboard: blackboard.getSnapshot(),
    }

    // Persist
    opts.store?.completeSession(sessionId, result as any)
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
