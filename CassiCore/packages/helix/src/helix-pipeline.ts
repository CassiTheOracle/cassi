/**
 * Helix Pipeline — Orchestrator for the three-posture collaborative agent pattern.
 *
 * Wires three equally capable postures plus Brainstem:
 *   - Unity: Full tools, posts work units via WorkStream
 *   - Yang: Read-only tools, DialecticChannel + WorkStream
 *   - Yin: Read-only tools, DialecticChannel + WorkStream
 *   - Brainstem (cognitive organizer): Scores work units, detects patterns
 *
 * Channels:
 *   - WorkStream: Postures ↔ Postures (work units up, nudges down)
 *   - DialecticChannel: Yang ↔ Yin (findings, challenges, concessions)
 *   - ContextSources: Brainstem → Postures (guidance, flags, annotations)
 *   REMOVED: Blackboard deprecated — now uses GlobalWorkspace + LaminaField
 *
 * Watchdog: steer-then-kill (2min warn → 4min escalate → 6min kill)
 */

import type { ILogger, IEventBus } from '@cassicore/foundation'
import type { ModelHandle } from '@cassicore/model-pool/types'
import type { IModelDirective, ModelConfig } from '@cassicore/foundation'
import type { ToolExecutor } from '@cassicore/tools'
import type { ToolRegistry } from '@cassicore/tools'
import type { PlanHandler } from './vendor/core/intelligence/flux-team/plan-handler.js'
import type { HelixStore } from './helix-store.js'
// REMOVED: Blackboard import — deprecated. Now uses LaminaField + GlobalWorkspace
// SessionState replaces deprecated Blackboard for plan/report tracking

/** Minimal session state tracker (replaces Blackboard) */
export class SessionState {
  private plan: { goal: string; steps: Array<{ title: string; status: string }> } | null = null
  private report: { sections: Array<{ type: string; title: string; content: string }> } = { sections: [] }

  initPlan(goal: string) {
    this.plan = { goal, steps: [] }
  }
  initReport(goal: string) {
    this.report = { sections: [{ type: 'summary', title: 'Goal', content: goal }] }
  }
  getPlan() { return this.plan }
  getReport() { return this.report }
  getSnapshot() {
    return { plan: this.plan, report: this.report }
  }
}
import { WorkStream } from './work-stream.js'
import { ContextBudgetCoordinator } from './vendor/core/intelligence/cassi-agent/context-budget-coordinator.js'
import { DialecticChannel } from './dialectic-channel.js'
import { HelixCoordinator, HelixWorkStream, HelixDialecticMesh } from './helix-coordinator.js'
import { HelixPostureRunner } from './helix-posture-runner.js'
import { ContextChunkIndex } from './context-chunk-index.js'
import { UNITY_POSTURE, YANG_REVIEWER_POSTURE, YIN_REVIEWER_POSTURE } from './helix-postures.js'
import type { HelixResult, HelixCompletionStatus, HelixPostureResult } from './types.js'
import { signalPromise } from '@cassicore/utils'
import { HelixBrainstem, createHelixBrainstem } from './brainstem.js'
import type { BrainstemDeps } from './brainstem-types.js'
import { HelixSynapse } from './helix-synapse.js'
import type { HelixSynapseConfig, HelixSynapseLLM } from './helix-synapse.js'
import { PostureModule } from './posture-module.js'
import { HelixTelemetry } from './helix-telemetry.js'
import { HelixConductor, shouldUseConductor } from './helix-conductor.js'
import type { GlobalWorkspace } from '@cassicore/workspace'
import type { MnemicField } from '@cassicore/mnemic-field'
import type { Aurora } from '@cassicore/aurora'



const DEFAULT_TIMEOUT_MS = 600_000
const DEFAULT_MAX_MESSAGES = 5000
const DEFAULT_BACKPRESSURE_THRESHOLD = 10
const INACTIVITY_WARN_MS = 120_000
const INACTIVITY_ESCALATE_MS = 240_000
const INACTIVITY_KILL_MS = 360_000



/**
 * Tool profile determines which subset of tools are exposed to a posture.
 * Used to reduce tool bloat (80+ tools → ~20 focused tools) based on task type.
 *
 * @since Phase 1.1 posture-independence refactor
 */
export type HelixToolProfile = 'full' | 'implementation' | 'review' | 'exploration'

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
  modelDirective?: IModelDirective
  handleFactory?: (config: ModelConfig) => Promise<ModelHandle>

  // Callbacks
  onCancelRegistered?: (cancelFn: () => void) => void
  onWorkStreamCreated?: (ws: WorkStream) => void
  onDialecticChannelCreated?: (dc: DialecticChannel) => void
  onCoordinatorCreated?: (coordinator: HelixCoordinator) => void
  onBrainstemCreated?: (brainstem: HelixBrainstem) => void
  onSynapseCreated?: (synapse: HelixSynapse) => void
  onWorkUnit?: (wu: import('./work-types.js').WorkUnit, iteration: number) => void

  // Artifact/session context
  artifactNamespace?: string
  sessionType?: 'dyad' | 'lumen' | 'flux' | 'helix' | 'standalone'
  teamId?: string
  moduleDebugSessionId?: string

  /** Thalamus for context curation during long-running sessions */
  thalamus?: import('@cassicore/thalamus').ThalamusModule

  /** Cross-session topic index for sharing Thalamus insights across sessions */
  crossSessionIndex?: import('@cassicore/thalamus').CrossSessionTopicIndex

  /** Constellation ID this Helix session belongs to (for cross-session scoping) */
  constellationId?: string

  /**
   * LaminaField — when provided, the conductor + posture runners write
   * coordination/mentor entries to this Helix's `helix-goal` lamina.
   * Threaded through from the Constellation; standalone Helix invocations
   * can omit it.
   */
  lamina?: import('@cassicore/lamina-locus-bridge').LaminaField

  /** Configurable thresholds for UnityStatus proactive signals to reviewers */
  unityStatusThresholds?: import('./work-stream.js').UnityStatusThresholds

  /** Use Helix-native coordinator with broadcast semantics instead of borrowed primitives */
  useNativeCoordinator?: boolean

  /** Brainstem dependencies — if provided, Brainstem replaces Mentor */
  brainstemDeps?: BrainstemDeps

  /**
   * New Helix-level Synapse observer. When provided, the pipeline starts an
   * always-active observer that watches rolling context slices from Unity/Yang/Yin
   * and broadcasts direct observations back into those posture contexts.
   */
  synapseDeps?: {
    llm: HelixSynapseLLM
    config?: Partial<HelixSynapseConfig>
  }

  /** Configurable inactivity thresholds (ms). Defaults: warn=120s, escalate=240s, kill=360s. */
  inactivityThresholds?: {
    warnMs?: number
    escalateMs?: number
    killMs?: number
  }

  /**
   * Working directory override for this Helix session.
   * When set (e.g., by Constellation worktree isolation), all tool execution
   * uses this path instead of the default project root.
   */
  workingDir?: string

  /**
   * Separate review context for other postures.
   * @why Other postures only need editing rules and review criteria, not full file
   *      assignments. Splitting context saves tokens when the goal is large
   *      (e.g., mass-edit tasks with hundreds of file assignments).
   */
  reviewerContext?: string

  /**
   * Override tool access levels for each posture.
   * When set, these replace the hardcoded posture defaults (e.g., full for unity).
   * Used by Constellation to enforce template-defined access levels
   * (e.g., read-only for meditation explorers).
   */
  toolAccessOverrides?: {
    unity?: import('./vendor/core/intelligence/constellation/types.js').ToolAccessLevel
    yang?: import('./vendor/core/intelligence/constellation/types.js').ToolAccessLevel
    yin?: import('./vendor/core/intelligence/constellation/types.js').ToolAccessLevel
  }

  /**
   * Tool filter for this Helix session.
   * Applied on top of posture-level tool access.
   */
  toolFilter?: {
    allow?: string[]
    deny?: string[]
  }

  /**
   * Per-posture tool profile — selects which subset of tools are exposed.
   * When absent, defaults to 'full' (all 80+ tools) for back-compat.
   *
   * Profiles:
   *   - 'full': All tools (legacy behavior, 80+)
   *   - 'implementation': Action-focused (~15 tools) — code, file, bash, signal_done
   *   - 'review': Audit-focused (~12 tools) — read-only + dialectic + signal_conclusion
   *   - 'exploration': Research-focused (~8 tools) — file, web, collect_thoughts
   *
   * Used by Constellation to give Unity 'implementation' while Yang/Yin get 'review'.
   */
  toolProfiles?: {
    unity?: HelixToolProfile
    yang?: HelixToolProfile
    yin?: HelixToolProfile
  }

  /**
   * Phase A brain-integration flag. When true together with `globalWorkspace`,
   * each posture is wrapped in a PostureModule and publishes CognitiveSignals
   * alongside its existing WorkStream / DialecticChannel writes (dual-publish).
   * No-op when either is unset. Default false.
   */
  brainIntegration?: boolean
  /** Brain's GlobalWorkspace instance (required when brainIntegration is true). */
  globalWorkspace?: GlobalWorkspace
  /**
   * Optional telemetry sink for session metrics and spans. A fresh one is
   * created when brainIntegration is on and this is unset.
   */
  telemetry?: HelixTelemetry
  /**
   * Optional Mnemic Field — when provided alongside brainIntegration,
   * the Conductor spins up a HelixMnemicBridge that writes milestone
   * engrams (session/outcome/concern/decision/anomaly) for cross-session
   * kindling via spreading activation.
   */
  mnemicField?: MnemicField
  /**
   * Optional Aurora — when provided alongside brainIntegration, posture
   * reasoning text is piped through `aurora.observeReasoning()` so the
   * unified mental-state graph grows during the session.
   */
  aurora?: Aurora
}



/**
 * @dep callers: project (core/intelligence/helix/index.ts), launchHelix (core/intelligence/constellation/constellation-pipeline.ts)
 * @dep calls: now, createSession, cancel, on, emit [+32]
 * @dep flows: RunHelixPipeline → Delete (1/4)
 * @dep module: Flux-team
 * @dep risk: LOW | 2 callers, 1 flow, 1 module
 */

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
    type: 'helix:started',
    sessionId,
    goal: opts.goal.slice(0, 500),
    constellationId: opts.constellationId,
    timestamp: Date.now(),
  } as any)

  // Persist session
  opts.store?.createSession(sessionId, opts.goal, opts.context)
  opts.store?.appendEvent(sessionId, 'helix:started', 'session', 'Helix pipeline started')



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

  // Auto-create session state if not provided (replaces deprecated Blackboard)
  const sessionState = new SessionState()
  sessionState.initPlan(opts.goal)
  sessionState.initReport(opts.goal)

  opts.onWorkStreamCreated?.(workStream)
  opts.onDialecticChannelCreated?.(dialecticChannel)



  const useBrainstem = !!opts.brainstemDeps
  let brainstem: HelixBrainstem | undefined
  let helixSynapse: HelixSynapse | undefined

  // Create Unity's chunk index early so brainstem can reference it
  const unityChunkIndex = new ContextChunkIndex(log)

  if (useBrainstem) {
    // REMOVED: Blackboard injection — now uses contextSources (GlobalWorkspace + LaminaField)
    // Brainstem posts annotations via contextSources.globalWorkspace.broadcast()
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

  if (opts.synapseDeps) {
    helixSynapse = new HelixSynapse({
      helixId: sessionId,
      goal: opts.goal,
      logger: log,
      eventBus: opts.eventBus,
      llm: opts.synapseDeps.llm,
      memory: opts.mnemicField,
      crossSessionIndex: opts.crossSessionIndex,
      config: opts.synapseDeps.config,
    })
    helixSynapse.start()
    opts.onSynapseCreated?.(helixSynapse)
    log.info('Helix Synapse started (observer-layer coordination)')
  }



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



  if (opts.toolExecutor && !opts.toolExecutor.hasSessionContext(sessionId)) {
    opts.toolExecutor.setSessionContext(sessionId, {
      artifactNamespace: opts.artifactNamespace ?? `helix:${sessionId}`,
      sessionType: opts.sessionType ?? 'helix',
      teamId: opts.teamId,
      // WHY: When running in a worktree-isolated Constellation branch,
      // all tool execution should use the worktree path instead of the main project root.
      ...(opts.workingDir ? { workingDir: opts.workingDir } : {}),
    })
  }



  let lastActivity = Date.now()
  let watchdog: import('./inactivity-watchdog.js').InactivityWatchdog | undefined
  let hardCapTimeout: import('@cassicore/utils').ActivityTimeout | undefined
  const onActivity = () => {
    lastActivity = Date.now()
    hardCapTimeout?.touch()
    watchdog?.touch()
  }



  const commonOpts = {
    sessionId,
    jobId: opts.jobId,
    workStream,
    dialecticChannel,
    sessionState,
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
    toolFilter: opts.toolFilter,
    lamina: opts.lamina,
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

  // Brain integration: when the flag + a GlobalWorkspace are present, spin
  // up a HelixConductor that owns the PostureModules, journals every signal
  // and lifecycle event, and takes periodic snapshots. Pipeline code stays
  // unchanged when the flag is off — conductor is optional.
  const brainIntegrationEnabled = shouldUseConductor(opts)
  let conductor: HelixConductor | undefined
  let helixTelemetry: HelixTelemetry | undefined
  let unityPostureModule: PostureModule | undefined
  let yangPostureModule: PostureModule | undefined
  let yinPostureModule: PostureModule | undefined

  if (brainIntegrationEnabled && opts.globalWorkspace) {
    conductor = new HelixConductor({
      sessionId,
      goal: opts.goal,
      logger: log,
      globalWorkspace: opts.globalWorkspace,
      eventBus: opts.eventBus,
      telemetry: opts.telemetry,
      mnemicField: opts.mnemicField,
      lamina: opts.lamina,
      aurora: opts.aurora,
      quiescence: false,  // Disabled — activity tracking is incomplete (doesn't see
                          // tool calls or LLM turns), kills active branches prematurely.
                          // Constellation uses stagnation sentinel instead.
    })
    await conductor.start()
    helixTelemetry = conductor.telemetry

    const modules = conductor.getPostureModules()
    unityPostureModule = modules['unity']
    yangPostureModule = modules['yang']
    yinPostureModule = modules['yin']

    log.info('HelixConductor started — postures publishing to GlobalWorkspace', {
      sessionId,
      journal: conductor.journal.getDbPath(),
    })
  }

  const unitySession = new HelixPostureRunner({
    ...commonOpts,
    role: 'unity',
    handle: opts.unityHandle,
    posture: UNITY_POSTURE,
    postureSlot: 'helix.unity',
    flexToolAccess: opts.toolAccessOverrides?.unity ?? UNITY_POSTURE.toolAccess,
    toolProfile: opts.toolProfiles?.unity ?? 'implementation',
    contextBudgetCoordinator,
    brainstem,
    helixSynapse,
    contextChunkIndex: unityChunkIndex,
    thalamus: opts.thalamus,
    crossSessionIndex: opts.crossSessionIndex,
    postureModule: unityPostureModule,
    telemetry: helixTelemetry,
    aurora: conductor?.aurora,
    journal: conductor?.journal,
  })

  const yangSession = new HelixPostureRunner({
    ...commonOpts,
    role: 'yang',
    handle: opts.yangHandle,
    posture: YANG_REVIEWER_POSTURE,
    postureSlot: 'helix.yang',
    flexToolAccess: opts.toolAccessOverrides?.yang ?? YANG_REVIEWER_POSTURE.toolAccess,
    toolProfile: opts.toolProfiles?.yang ?? 'review',
    dialecticChannel,
    contextBudgetCoordinator,
    brainstem,
    helixSynapse,
    contextChunkIndex: yangChunkIndex,
    thalamus: opts.thalamus,
    crossSessionIndex: opts.crossSessionIndex,
    postureModule: yangPostureModule,
    telemetry: helixTelemetry,
    aurora: conductor?.aurora,
    journal: conductor?.journal,
  })

  const yinSession = new HelixPostureRunner({
    ...commonOpts,
    role: 'yin',
    handle: opts.yinHandle,
    posture: YIN_REVIEWER_POSTURE,
    postureSlot: 'helix.yin',
    flexToolAccess: opts.toolAccessOverrides?.yin ?? YIN_REVIEWER_POSTURE.toolAccess,
    toolProfile: opts.toolProfiles?.yin ?? 'review',
    dialecticChannel,
    contextBudgetCoordinator,
    brainstem,
    helixSynapse,
    contextChunkIndex: yinChunkIndex,
    thalamus: opts.thalamus,
    crossSessionIndex: opts.crossSessionIndex,
    postureModule: yinPostureModule,
    telemetry: helixTelemetry,
    aurora: conductor?.aurora,
    journal: conductor?.journal,
  })

  // Mentor path removed — Brainstem is the only cognitive organizer
  // Legacy mentorHandle field retained for backward compat but ignored

  cancelFns.push(
    () => unitySession.cancel(),
    () => yangSession.cancel(),
    () => yinSession.cancel(),
  )


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



  const inactivityWarnMs = opts.inactivityThresholds?.warnMs ?? INACTIVITY_WARN_MS
  const inactivityEscalateMs = opts.inactivityThresholds?.escalateMs ?? INACTIVITY_ESCALATE_MS
  const inactivityKillMs = opts.inactivityThresholds?.killMs ?? INACTIVITY_KILL_MS

  // Three-stage inactivity watchdog (extracted to InactivityWatchdog module).
  // Replaces the previous 60-line inline watchdog block — same semantics, isolated logic.
  const { InactivityWatchdog } = await import('./inactivity-watchdog.js')
  watchdog = new InactivityWatchdog({
    warnMs: inactivityWarnMs,
    escalateMs: inactivityEscalateMs,
    killMs: inactivityKillMs,
    onWarn: (silentMs) => {
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
    },
    onEscalate: (silentMs) => {
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
    },
    onKill: (silentMs) => {
      if (!cancelled) {
        log.warn('Helix pipeline inactivity kill', { sessionId, silentMs })
        cancelAll()
      }
    },
  })



  const { ActivityTimeout } = await import('@cassicore/utils')
  hardCapTimeout = new ActivityTimeout({
    inactivityMs: inactivityKillMs,
    label: `helix-pipeline:${sessionId}`,
  })
  signalPromise(hardCapTimeout.signal).then(() => {
    if (!cancelled) {
      log.warn('Helix pipeline inactivity timeout', { sessionId, reason: hardCapTimeout!.reason })
      cancelAll()
    }
  }).catch(() => {})



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
        // Once brainstem has processed enough work units, call shouldActivateReviewers() fresh
        const workUnits = brainstem.getState().workUnitsProcessed
        const threshold = brainstem.getReviewerActivationThreshold()
        if (workUnits >= threshold) {
          return brainstem.shouldActivateReviewers()
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

      yangPromise = yangSession.runAsReviewer(opts.goal, opts.reviewerContext ?? opts.context)
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

      yinPromise = yinSession.runAsReviewer(opts.goal, opts.reviewerContext ?? opts.context)
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
    const autoReport = brainstem?.getAutoReport() ?? []

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

      // WHY: Copy confidence and keyPoints from posture results so callers
      // (Constellation, status endpoints) get real values instead of undefined.
      // Previously these declared fields were never populated (c-36 postmortem Root Cause C).
      unityConfidence: unityResult.confidence,
      yangConfidence: yangResult.confidence,
      yinConfidence: yinResult.confidence,
      unityKeyPoints: unityResult.keyPoints,
      yangKeyPoints: yangResult.keyPoints,
      yinKeyPoints: yinResult.keyPoints,

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

      report: (sessionState.getReport() as any) ?? undefined,
      autoReport: autoReport.length > 0 ? autoReport : undefined,
      sessionState: sessionState.getSnapshot(),
    }

    // Persist
    opts.store?.completeSession(sessionId, result as any)
    opts.store?.saveWorkStreamMessages(sessionId, workStream.getFullLog())
    opts.store?.appendEvent(sessionId, 'helix:completed', 'session', 'Pipeline completed')
    opts.eventBus?.emit({
      type: 'helix:completed',
      sessionId,
      durationMs: result.durationMs,
      tokensUsed: result.tokensUsed,
      completionStatus: result.completionStatus,
      unityConclusion: result.unityConclusion?.slice(0, 300),
      timestamp: Date.now(),
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
  } catch (pipelineError) {
    // WHY: When the pipeline throws (timeout, LLM failure, etc.), we need to
    // persist whatever stats were accumulated.  Without this, killed sessions
    // show iterations=0 tokens=0 in the helix_sessions table.
    const partialStats: Record<string, unknown> = {}
    try {
      // HOW: The posture results may not exist (pipeline killed before allSettled),
      // so we pull stats from workStream and brainstem instead.
      const pipelineStats = workStream?.getStats?.()
      partialStats.pipelineStats = {
        workUnitsProduced: pipelineStats?.workUnits ?? 0,
        nudgesSent: (pipelineStats?.nudges?.low ?? 0) + (pipelineStats?.nudges?.high ?? 0),
        nudgesAcknowledged: pipelineStats?.nudges?.acknowledged ?? 0,
      }
      partialStats.durationMs = Date.now() - startTime
      if (brainstem) {
        const bsState = brainstem.getState()
        partialStats.tokensUsed = { unity: 0, yang: 0, yin: 0 }
        partialStats.iterationCounts = { unity: bsState.workUnitsProcessed, yang: 0, yin: 0 }
        partialStats.toolCallCounts = { unity: 0, yang: 0, yin: 0 }
      }
    } catch {
      // best-effort stats collection
    }

    opts.store?.failSession(sessionId, String(pipelineError), partialStats as any)
    opts.store?.appendEvent(sessionId, 'helix:failed', 'session',
      `Pipeline failed: ${pipelineError instanceof Error ? pipelineError.message : String(pipelineError)}`)

    opts.eventBus?.emit({
      type: 'helix:failed',
      sessionId,
      error: String(pipelineError).slice(0, 300),
      durationMs: partialStats.durationMs as number ?? Date.now() - startTime,
      partialTokens: partialStats.tokensUsed as Record<string, number> ?? { unity: 0, yang: 0, yin: 0 },
      constellationId: opts.constellationId,
      timestamp: Date.now(),
    } as any)

    log.error('Helix pipeline failed', {
      sessionId,
      error: String(pipelineError),
      durationMs: partialStats.durationMs,
    })

    throw pipelineError
  } finally {
    watchdog?.dispose()
    hardCapTimeout?.dispose()
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

    if (helixSynapse) {
      try {
        await helixSynapse.stop()
        log.info('Helix Synapse stopped')
      } catch (err) {
        log.warn('Helix Synapse stop failed', { error: String(err) })
      }
    }

    // Stop the conductor (owns PostureModules, journal, telemetry, session store)
    if (conductor) {
      try {
        await conductor.stop('ok')
      } catch (err) {
        log.warn('HelixConductor stop failed', { error: String(err) })
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



/**
 * @dep callers: extract (core/intelligence/helix/helix-pipeline.ts), runHelixPipeline (core/intelligence/helix/helix-pipeline.ts)
 * @dep module: Flux-team
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

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
