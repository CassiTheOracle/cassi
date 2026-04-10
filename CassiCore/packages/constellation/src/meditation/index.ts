/**
 * MeditationController — Idle-time constellation exploration with self-learning.
 *
 * When the constellation is sleeping (no active projects, no user activity),
 * spawns Helix sessions that explore with no objective. The agents receive
 * only what the memory system surfaces and read-only tools. They have no
 * awareness of being observed.
 *
 * The Corpus (as Cassi) watches silently, synthesizes, and stores insights.
 * The MnemicBridge feeds meditation activity into spatial memory, creating
 * implicit cross-pollination.
 *
 * After each session, Cassi evaluates which prompts produced the most
 * interesting exploration. Scores feed Thompson sampling, which shifts
 * future prompt selection toward what works. Three meditation styles
 * (passive, active, focused) control the character of each session.
 *
 * Priority: 16 (background — just above Dreamer at 15)
 */

import { BaseCognitiveModule } from '../../base/cognitive-module.js'
import { MODEL_DEFAULTS } from '../../../config/system-settings.js'
import { isGamingMode } from '../../gaming-mode.js'
import { MnemicBridge } from './mnemic-bridge.js'
import type { MeditationConfig, MeditationState, MeditationSession } from './types.js'
import { DEFAULT_MEDITATION_CONFIG, MEDITATION_PROMPTS, pickMeditationPrompt } from './types.js'
import { getTemplatePostures } from '../templates.js'
import { selectStyle } from './styles.js'
import type { MeditationStyle } from './styles.js'
import { MeditationStore } from './meditation-store.js'
import { pickPromptsThompson } from './thompson.js'
import { runPostMeditationEvaluation } from './evaluation.js'
import { runFocusedSeeding } from './focused-seeding.js'
import { emitMeditationEvent } from './meditation-events.js'
import type { MiniHelixDeps } from '../../mini-helix/mini-helix-types.js'

import type { ConstellationOrchestrator } from '../constellation-orchestrator.js'
import type { ConstellationRegistry } from '../constellation-injection.js'
import type { MnemicField } from '../../mnemic-field/index.js'
import type { ILogger } from '../../../../types/interfaces.js'
import type { CorticalField } from '../../cortex/index.js'
import type { ICorpusTree } from '../corpus-types.js'
import { runSoloExplorer } from './solo-runner.js'
import type { SoloRunnerResult } from './solo-runner.js'


export class MeditationController extends BaseCognitiveModule {
  readonly name = 'meditation'
  readonly priority = 16

  private meditationConfig: MeditationConfig = { ...DEFAULT_MEDITATION_CONFIG }
  private state: MeditationState = 'idle'

  private lastTurnAt = 0
  private lastMeditationAt = 0
  private sessionCount = 0
  private pendingInsightFollowUp = false

  private checkTimer?: NodeJS.Timeout
  private durationTimer?: NodeJS.Timeout
  private activeSession?: MeditationSession
  private activeTree?: ICorpusTree
  private mnemicBridge?: MnemicBridge

  private orchestrator?: ConstellationOrchestrator
  private registry?: ConstellationRegistry
  private mnemicField?: MnemicField
  private meditationStore?: MeditationStore
  private handleFactory?: MiniHelixDeps['handleFactory']
  private cortex?: CorticalField
  private activeAbortController?: AbortController


  constructor(logger: ILogger, config?: Partial<MeditationConfig>) {
    super(logger, {
      providerId: MODEL_DEFAULTS.reasoning.provider,
      model: MODEL_DEFAULTS.reasoning.model,
    })
    if (config) this.meditationConfig = { ...DEFAULT_MEDITATION_CONFIG, ...config }
  }


  setOrchestrator(orch: ConstellationOrchestrator): void {
    this.orchestrator = orch
  }

  setConstellationRegistry(reg: ConstellationRegistry): void {
    this.registry = reg
  }

  setMnemicField(field: MnemicField): void {
    this.mnemicField = field
  }

  setHandleFactory(factory: MiniHelixDeps['handleFactory']): void {
    this.handleFactory = factory
  }

  setCortex(cortex: CorticalField): void {
    this.cortex = cortex
  }



  getStore(): MeditationStore | undefined {
    return this.meditationStore
  }


  override async start(): Promise<void> {
    await super.start()
    if (!this.meditationConfig.enabled) {
      this.logger.info('[Meditation] Disabled by config — not starting idle check loop')
      return
    }

    try {
      this.meditationStore = MeditationStore.open(this.logger)
      this.meditationStore.seedPrompts(MEDITATION_PROMPTS)
    } catch (err) {
      this.logger.warn('[Meditation] MeditationStore failed to open — evaluation disabled', { error: String(err) })
    }

    this.startIdleCheckLoop()
    this.logger.info('[Meditation] Started idle-check loop', {
      checkIntervalMs: this.meditationConfig.checkIntervalMs,
      idleThresholdMs: this.meditationConfig.idleThresholdMs,
    })
  }

  override async stop(): Promise<void> {
    this.state = 'stopped'
    if (this.checkTimer) {
      clearInterval(this.checkTimer)
      this.checkTimer = undefined
    }
    if (this.activeSession) {
      await this.stopMeditation('module-stop')
    }
    if (this.meditationStore) {
      this.meditationStore.close()
      this.meditationStore = undefined
    }
    await super.stop()
  }


  protected override async onTurnEnd(
    _sessionId: string,
    _response: string,
    _durationMs: number,
  ): Promise<void> {
    this.lastTurnAt = Date.now()

    if (this.state === 'meditating') {
      await this.stopMeditation('user-activity')
    }
  }


  getState(): MeditationState {
    return this.state
  }

  getSession(): MeditationSession | undefined {
    return this.activeSession
  }

  getSelfAwarenessDetections(): import('./self-awareness-detector.js').SelfAwarenessDetection[] {
    return this.mnemicBridge?.getSelfAwarenessDetections() ?? []
  }


  /**
   * Force-start meditation. Bypasses idle check.
   * Safe to call from admin API.
   *
   * When followUp is true, forces focused style and seeds from previous
   * meditation insights — same as the automatic passive→focused upgrade
   * but triggered manually.
   *
   * When modelTier is specified, overrides the default model tier for all
   * explorers (e.g., 'opus' for deep introspection).
   */
  async triggerMeditation(style?: MeditationStyle, followUp?: boolean, modelTier?: string): Promise<MeditationSession | null> {
    this.logger.info('[Meditation] triggerMeditation called', { style, followUp, modelTier })
    if (this.state === 'meditating') {
      this.logger.info('[Meditation] Already meditating — ignoring trigger')
      return this.activeSession ?? null
    }

    if (!this.orchestrator || !this.registry) {
      this.logger.warn('[Meditation] Cannot meditate — orchestrator or registry not wired')
      return null
    }

    if (followUp) {
      this.pendingInsightFollowUp = true
      return this.startMeditation('focused', modelTier)
    }

    return this.startMeditation(style, modelTier)
  }


  /**
   * Force-stop meditation. Safe to call from admin API.
   */
  async forceStop(): Promise<void> {
    if (this.state === 'meditating') {
      await this.stopMeditation('force-stop')
    }
  }


  /**
   * Cancel any running meditation. Called by the orchestrator before
   * launching real work — preemption must be immediate.
   */
  cancelForRealWork(): void {
    if (this.state !== 'meditating' || !this.activeSession) return
    this.logger.info('[Meditation] Preempted by real work')
    void this.stopMeditation('preempted')
  }


  private startIdleCheckLoop(): void {
    this.checkTimer = setInterval(
      () => { void this.checkAndMeditate() },
      this.meditationConfig.checkIntervalMs,
    )
    if (this.checkTimer.unref) this.checkTimer.unref()
  }

  private async checkAndMeditate(): Promise<void> {
    if (this.state !== 'idle') return
    if (!this.meditationConfig.enabled) return
    if (isGamingMode()) return

    if (!this.orchestrator || !this.registry) return

    // No active constellations (check both registry and orchestrator's running map
    // to cover the gap between project() call and registry.register())
    if (this.registry.size > 0) return
    if (this.orchestrator.hasActiveWork()) return

    // Idle long enough
    const idleMs = Date.now() - this.lastTurnAt
    if (this.lastTurnAt > 0 && idleMs < this.meditationConfig.idleThresholdMs) return

    // Cooldown elapsed
    const sinceLast = Date.now() - this.lastMeditationAt
    if (this.lastMeditationAt > 0 && sinceLast < this.meditationConfig.cooldownMs) return

    const affect = this.cortex?.getAffectState() ?? undefined
    let style = selectStyle(this.lastTurnAt, this.meditationConfig.idleThresholdMs, this.meditationConfig.defaultStyle, affect)

    // Upgrade passive → focused when pending insights exist from a previous session.
    // This creates a feedback loop: passive exploration produces insights,
    // then focused meditation goes deeper on what was discovered.
    if (style === 'passive' && this.pendingInsightFollowUp) {
      style = 'focused'
      this.pendingInsightFollowUp = false
    }

    const reason = style === 'reflective' ? 'non-neutral affect'
      : style === 'active' ? 'recent activity'
      : style === 'focused' ? 'insight follow-up'
      : style === 'passive' ? 'deep idle' : 'default'
    emitMeditationEvent(this.eventBus, {
      type: 'meditation:style-selected',
      style,
      reason,
      idleMs,
      timestamp: Date.now(),
    })
    await this.startMeditation(style)
  }


  private async startMeditation(style?: MeditationStyle, modelTier?: string): Promise<MeditationSession | null> {
    this.logger.info('[Meditation] startMeditation called', { style, modelTier })
    if (!this.handleFactory || !this.toolExecutor || !this.toolRegistry) {
      this.logger.warn('[Meditation] Cannot meditate — missing handleFactory, toolExecutor, or toolRegistry')
      return null
    }

    const constellationId = `meditation-${Date.now()}`
    let resolvedStyle = style ?? this.meditationConfig.defaultStyle

    // Upgrade passive → focused when pending insights exist from a previous session.
    // This applies to both auto-triggered and manual meditation starts.
    if (resolvedStyle === 'passive' && this.pendingInsightFollowUp) {
      resolvedStyle = 'focused'
      this.pendingInsightFollowUp = false
      this.logger.info('[Meditation] Upgrading to focused style — following up on previous insights')
    }

    this.state = 'meditating'

    // Build postures with prompts — Thompson sampling when store is available, fallback otherwise
    const basePostures = getTemplatePostures('meditation')
    const promptAssignments: MeditationSession['prompts'] = []

    let pickedPrompts: Array<{ id: string; prompt: string }>
    if (this.meditationStore) {
      const picks = pickPromptsThompson(basePostures.length, this.meditationStore, resolvedStyle, MEDITATION_PROMPTS)
      pickedPrompts = picks.map(p => ({ id: p.id, prompt: p.prompt }))
    } else {
      pickedPrompts = basePostures.map((_, i) => {
        const p = pickMeditationPrompt(i, this.sessionCount)
        return { id: p.id, prompt: p.prompt }
      })
    }

    basePostures.forEach((posture, i) => {
      const picked = pickedPrompts[i]
      promptAssignments.push({ explorer: posture.name, promptId: picked.id, prompt: picked.prompt })
    })

    // Focused mode: seed the mnemic field before launching explorers
    if (resolvedStyle === 'focused' && this.mnemicField && this.memory && this.handleFactory) {
      try {
        const seedResult = await runFocusedSeeding({
          mnemicField: this.mnemicField,
          memory: this.memory,
          handleFactory: this.handleFactory,
          logger: this.logger,
          eventBus: this.eventBus,
        })
        emitMeditationEvent(this.eventBus, {
          type: 'meditation:focused-seeding',
          constellationId,
          focusTopics: seedResult.focusTopics,
          engramsKindled: seedResult.engramsKindled,
          seedingDurationMs: seedResult.durationMs,
          timestamp: Date.now(),
        })
        this.logger.info('[Meditation] Focused seeding complete', {
          topics: seedResult.focusTopics,
          engramsKindled: seedResult.engramsKindled,
          durationMs: seedResult.durationMs,
        })
      } catch (err) {
        this.logger.warn('[Meditation] Focused seeding failed — proceeding anyway', { error: String(err) })
      }
    }

    this.logger.info('[Meditation] Starting meditation session', {
      constellationId,
      style: resolvedStyle,
      prompts: promptAssignments.map(p => `${p.explorer}: [${p.promptId}] ${p.prompt}`),
    })

    this.activeSession = {
      constellationId,
      startedAt: Date.now(),
      style: resolvedStyle,
      engrams: { spiked: 0, created: 0 },
      consolidations: 0,
      prompts: promptAssignments,
    }
    this.sessionCount++

    emitMeditationEvent(this.eventBus, {
      type: 'meditation:started',
      constellationId,
      style: resolvedStyle,
      prompts: promptAssignments,
      timestamp: Date.now(),
    })

    // Start duration timer
    this.durationTimer = setTimeout(
      () => { void this.stopMeditation('max-duration') },
      this.meditationConfig.maxDurationMs,
    )
    if (this.durationTimer.unref) this.durationTimer.unref()

    try {
      // Resolve model tier for each explorer
      const tier = modelTier ?? this.meditationConfig.modelTier ?? 'qwenPlus'

      // Create abort controller for cancellation
      const abortController = new AbortController()
      this.activeAbortController = abortController

      // Acquire handles and spawn solo explorers in parallel
      const explorerPromises = promptAssignments.map(async (assignment) => {
        const handle = await this.handleFactory!({
          tier,
          purpose: `meditation:${assignment.explorer}`,
          sessionId: `${constellationId}-${assignment.explorer}`,
        })

        // Inject memory context if available
        let memoryContext: string | undefined
        if (this.memory) {
          try {
            const memories = await this.memory.search(assignment.prompt, { limit: 5 })
            if (memories && memories.length > 0) {
              memoryContext = memories.map((m: any) => m.content ?? String(m)).join('\n\n')
            }
          } catch {
            // best-effort memory injection
          }
        }

        return runSoloExplorer({
          sessionId: `${constellationId}-${assignment.explorer}`,
          name: assignment.explorer,
          instruction: assignment.prompt,
          handle,
          toolExecutor: this.toolExecutor!,
          toolRegistry: this.toolRegistry!,
          maxIterations: Math.floor(this.meditationConfig.maxTotalSteps / basePostures.length),
          logger: this.logger,
          eventBus: this.eventBus!,
          signal: abortController.signal,
          memoryContext,
        })
      })

      // Run all explorers in background — don't await
      Promise.allSettled(explorerPromises)
        .then(async (results) => {
          const soloResults = results
            .filter((r): r is PromiseFulfilledResult<SoloRunnerResult> => r.status === 'fulfilled')
            .map(r => r.value)

          this.logger.info('[Meditation] All explorers completed', {
            constellationId,
            explorers: soloResults.map(r => ({
              name: r.name, iterations: r.iterations,
              toolCalls: r.toolCalls, tokensUsed: r.tokensUsed,
              stoppedBy: r.stoppedBy,
            })),
          })

          void this.stopMeditation('natural')
        })
        .catch((err) => {
          this.logger.warn('[Meditation] Explorer execution failed', { error: String(err) })
          void this.stopMeditation('error')
        })

      return this.activeSession

    } catch (err) {
      this.logger.error('[Meditation] Failed to start solo explorers', { error: String(err) })
      this.state = 'idle'
      this.activeSession = undefined
      this.activeAbortController = undefined
      if (this.durationTimer) {
        clearTimeout(this.durationTimer)
        this.durationTimer = undefined
      }
      return null
    }
  }


  private async waitForTreeAndStartBridge(constellationId: string): Promise<MnemicBridge | undefined> {
    if (!this.mnemicField || !this.orchestrator) return undefined

    // Wait up to 10s for the live tree to become available
    for (let i = 0; i < 20; i++) {
      const liveTree = this.orchestrator.getLiveTree(constellationId)
      if (liveTree) {
        this.logger.info('[Meditation] Live corpusTree available — starting MnemicBridge with self-awareness detection')
        this.activeTree = liveTree
        const bridge = new MnemicBridge(this.mnemicField, liveTree, this.logger, undefined, this.eventBus)
        bridge.start()
        return bridge
      }
      await new Promise(resolve => setTimeout(resolve, 500))
      if (this.state !== 'meditating') return undefined
    }

    this.logger.warn('[Meditation] CorpusTree not available after 10s — MnemicBridge skipped')
    return undefined
  }


  private async stopMeditation(reason: string): Promise<void> {
    if (this.state !== 'meditating' && this.state !== 'stopping') return
    this.state = 'stopping'

    const constellationId = this.activeSession?.constellationId
    this.logger.info('[Meditation] Stopping meditation', { reason, constellationId })

    if (this.durationTimer) {
      clearTimeout(this.durationTimer)
      this.durationTimer = undefined
    }

    // Capture tree reference BEFORE cleanup — evaluation needs it alive.
    // Use the reference captured when the MnemicBridge started, since the
    // orchestrator's .finally() deletes the running entry before our .then() fires.
    const tree = this.activeTree

    // Collect MnemicBridge stats before stopping
    if (this.mnemicBridge) {
      const bridgeStats = this.mnemicBridge.getStats()
      if (this.activeSession) {
        this.activeSession.engrams.spiked = bridgeStats.spiked
        this.activeSession.engrams.created = bridgeStats.created
        this.activeSession.consolidations = bridgeStats.consolidations
      }
    }

    // Consolidation before bridge stops
    if (this.meditationConfig.consolidateOnComplete && this.mnemicBridge) {
      this.mnemicBridge.triggerConsolidation()
    }

    // Stop MnemicBridge
    if (this.mnemicBridge) {
      this.mnemicBridge.stop()
      this.mnemicBridge = undefined
    }

    // Post-session evaluation — runs for any stop reason if session ran long enough.
    // Very short sessions or error-only sessions won't have enough tree data
    // for meaningful evaluation. The duration threshold prevents wasted LLM calls.
    const sessionDurationMs = this.activeSession ? Date.now() - this.activeSession.startedAt : 0
    const shouldEvaluate = this.meditationConfig.evaluateOnComplete
      && this.meditationStore
      && this.handleFactory
      && this.activeSession
      && tree
      && sessionDurationMs >= this.meditationConfig.minEvalDurationMs

    if (shouldEvaluate) {
      try {
        this.meditationStore!.createEvaluationSession(
          this.activeSession!.constellationId,
          this.activeSession!.style,
          this.activeSession!.startedAt,
          reason,
        )
        const evalResult = await runPostMeditationEvaluation({
          session: this.activeSession!,
          tree: tree!,
          store: this.meditationStore!,
          handleFactory: this.handleFactory!,
          mnemicField: this.mnemicField,
          logger: this.logger,
        })
        emitMeditationEvent(this.eventBus, {
          type: 'meditation:evaluation-complete',
          constellationId: this.activeSession!.constellationId,
          style: this.activeSession!.style,
          scores: evalResult.scores,
          summary: evalResult.summary,
          evalDurationMs: evalResult.durationMs,
          evalTokensUsed: evalResult.tokensUsed,
          timestamp: Date.now(),
        })

        // Emit events for prompt mutations
        for (const m of evalResult.mutations) {
          emitMeditationEvent(this.eventBus, {
            type: 'meditation:prompt-created',
            promptId: m.promptId,
            parentId: m.parentId,
            content: m.content,
            category: m.category,
            rationale: m.rationale,
            timestamp: Date.now(),
          })
        }

        // Emit evolution adjustment event
        if (evalResult.evolutionAdjustment) {
          emitMeditationEvent(this.eventBus, {
            type: 'meditation:evolution-adjusted',
            oldTemperature: evalResult.evolutionAdjustment.oldTemp,
            newTemperature: evalResult.evolutionAdjustment.newTemp,
            recentMutationAvg: 0,
            recentLibraryAvg: 0,
            direction: evalResult.evolutionAdjustment.direction as any,
            timestamp: Date.now(),
          })
        }

        this.logger.info('[Meditation] Post-meditation evaluation complete', {
          scores: evalResult.scores.length,
          mutations: evalResult.mutations.length,
          durationMs: evalResult.durationMs,
          summary: evalResult.summary.slice(0, 100),
        })
      } catch (err) {
        this.logger.warn('[Meditation] Post-meditation evaluation failed', { error: String(err) })
      }
    }

    // Cancel running explorers
    if (this.activeAbortController) {
      this.activeAbortController.abort()
      this.activeAbortController = undefined
    }
    // Also cancel via orchestrator if a constellation-based session is still running
    if (constellationId && this.orchestrator) {
      this.orchestrator.cancel(constellationId)
    }

    await this.onMeditationComplete()
  }


  private async onMeditationComplete(): Promise<void> {
    if (this.state === 'idle' || this.state === 'stopped') return

    this.lastMeditationAt = Date.now()

    if (this.activeSession) {
      emitMeditationEvent(this.eventBus, {
        type: 'meditation:stopped',
        constellationId: this.activeSession.constellationId,
        style: this.activeSession.style,
        reason: 'complete',
        durationMs: Date.now() - this.activeSession.startedAt,
        engrams: this.activeSession.engrams,
        consolidations: this.activeSession.consolidations,
        timestamp: Date.now(),
      })
    }

    this.logger.info('[Meditation] Meditation session complete', {
      constellationId: this.activeSession?.constellationId,
      style: this.activeSession?.style,
      durationMs: this.activeSession ? Date.now() - this.activeSession.startedAt : 0,
      engrams: this.activeSession?.engrams,
      consolidations: this.activeSession?.consolidations,
    })

    if (this.activeSession?.style === 'reflective' && this.cortex?.getAffectState()) {
      try {
        this.cortex.signal('limbic', {
          type: 'perception',
          content: 'Emotional processing complete — affect settling toward baseline',
          author: 'meditation',
          salience: 0.3,
          valence: 0.1,
          tags: ['affect-settlement'],
        })
      } catch { /* fire-and-forget */ }
    }

    // Track whether passive meditation produced insights — flag for follow-up.
    // The next meditation will auto-upgrade to 'focused' to explore deeper.
    if (this.activeSession?.style === 'passive' && this.memory) {
      try {
        // getRecent is on MemoryModule but not in IMemory interface — cast for access
        const memAny = this.memory as any
        if (typeof memAny.getRecent !== 'function') {
          this.logger.warn('[Meditation] getRecent not available on memory module')
        } else {
          const recent = await memAny.getRecent(200)
          this.logger.info('[Meditation] Insight check', { recentCount: recent?.length ?? 0, sessionStart: this.activeSession.startedAt })
          const sessionInsights = (recent ?? []).filter((e: any) =>
            e.metadata?.source === 'meditation' &&
            e.type === 'insight' &&
            e.createdAt && new Date(e.createdAt).getTime() > (this.activeSession?.startedAt ?? 0)
          )
          this.logger.info('[Meditation] Insight check results', { sessionInsights: sessionInsights.length })
          if (sessionInsights.length > 0) {
            this.pendingInsightFollowUp = true
            this.logger.info('[Meditation] Passive session produced insights — flagging for follow-up', {
              insightCount: sessionInsights.length,
            })
          }
        }
      } catch (err) {
        this.logger.warn('[Meditation] Insight follow-up check failed', { error: String(err) })
      }
    }

    this.activeSession = undefined
    this.activeTree = undefined
    this.state = 'idle'
  }
}


export function createMeditationController(
  logger: ILogger,
  config?: Partial<MeditationConfig>,
): MeditationController {
  return new MeditationController(logger, config)
}
