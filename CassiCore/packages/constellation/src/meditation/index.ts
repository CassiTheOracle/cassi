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
import { runFocusedSeeding } from './focused-seeding.js'
import { emitMeditationEvent } from './meditation-events.js'
import type { MiniHelixDeps } from '../../mini-helix/mini-helix-types.js'
import { buildCorpusCyclePrompt, getCorpusToolSchemas, buildCorpusHandlers } from './corpus-synthesis.js'
import { buildEvaluationPrompt, getEvaluationToolSchemas, buildEvaluationHandlers } from './evaluation-runner.js'
import { buildOrganizingExplorerPrompt, getOrganizingToolSchemas, buildOrganizingHandlers, buildOrganizingCorpusPrompt } from './organizing-synthesis.js'
import type { OrganizingStats } from './organizing-synthesis.js'
import { FieldHealthAnalyzer } from './field-health.js'
import type { FieldHealthSnapshot } from './field-health.js'

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
  /** Cached by checkAndMeditate when health-based organizing is triggered */
  private cachedHealthSnapshot?: FieldHealthSnapshot


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
    let style = selectStyle(this.lastTurnAt, this.meditationConfig.idleThresholdMs, this.meditationConfig.defaultStyle, affect, this.sessionCount)

    // Upgrade passive → focused when pending insights exist from a previous session.
    // This creates a feedback loop: passive exploration produces insights,
    // then focused meditation goes deeper on what was discovered.
    if (style === 'passive' && this.pendingInsightFollowUp) {
      style = 'focused'
      this.pendingInsightFollowUp = false
    }

    // Health-based organizing upgrade: if the field is significantly fragmented,
    // override the style to organizing regardless of what selectStyle chose.
    // This ensures organizing happens when the field genuinely needs it,
    // not just on a fixed interval.
    if (style !== 'reflective' && style !== 'organizing' && this.mnemicField) {
      try {
        const analyzer = new FieldHealthAnalyzer(this.mnemicField, this.logger, this.meditationStore)
        const health = analyzer.shouldOrganize()
        if (health.trigger) {
          style = 'organizing'
          this.cachedHealthSnapshot = analyzer.snapshot()
          this.logger.info('[Meditation] Health-based organizing upgrade', {
            reason: health.reason,
            score: health.score,
          })
        }
      } catch (err) {
        this.logger.debug('[Meditation] Health check failed (non-fatal)', { error: String(err) })
      }
    }

    const reason = style === 'reflective' ? 'non-neutral affect'
      : style === 'active' ? 'recent activity'
      : style === 'focused' ? 'insight follow-up'
      : style === 'organizing' ? 'field health or periodic reorganization'
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

      // Organizing mode: single agent with structural reorganization tools.
      // Instead of multiple free-exploring agents, organizing spawns one agent
      // that systematically surveys, kindles, bridges, and consolidates the
      // mnemic field to accelerate learning across all domains.
      if (resolvedStyle === 'organizing' && this.mnemicField) {
        this.runOrganizingSession(constellationId, tier, abortController)
          .catch((err) => {
            this.logger.warn('[Meditation] Organizing session failed', { error: String(err) })
            void this.stopMeditation('error')
          })
        return this.activeSession
      }

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

          // Capture SoloRunner results in the session
          if (this.activeSession) {
            this.activeSession.soloResults = soloResults.map(r => ({
              name: r.name, iterations: r.iterations,
              toolCalls: r.toolCalls, tokensUsed: r.tokensUsed,
              stoppedBy: r.stoppedBy,
              transcript: r.transcript,
            }))
          }

          this.logger.info('[Meditation] All explorers completed', {
            constellationId,
            explorers: soloResults.map(r => ({
              name: r.name, iterations: r.iterations,
              toolCalls: r.toolCalls, tokensUsed: r.tokensUsed,
              stoppedBy: r.stoppedBy,
            })),
          })

          // Corpus synthesis — Cassi observes what the explorers found
          if (this.mnemicField) {
            await this.runCorpusCycle(constellationId, resolvedStyle, soloResults)
          }

          // Evaluation — score prompts and mutate library
          if (this.meditationStore && this.handleFactory) {
            await this.runEvaluation(constellationId, soloResults)
          }

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

    // SoloRunner path: spike related engrams and consolidate directly via MnemicField.
    // The MnemicBridge is only used by the old Constellation path — SoloRunners
    // store insights via the store_insight tool, but without spiking or consolidation.
    if (!this.mnemicBridge && this.mnemicField && this.meditationConfig.consolidateOnComplete) {
      try {
        // Spike engrams related to this session's prompts to reinforce associations
        const prompts = this.activeSession?.prompts?.map(p => p.prompt) ?? []
        let spiked = 0
        for (const prompt of prompts) {
          try {
            const hits = this.mnemicField.searchText(prompt, 10)
            for (const hit of hits.filter(h => h.score >= 0.3).slice(0, 5)) {
              this.mnemicField.spike({
                engramId: hit.engram.id,
                magnitude: 0.5,
                taskContext: `meditation:${constellationId}`,
                outcome: 'unknown' as const,
              })
              spiked++
            }
          } catch {
            // best-effort spiking
          }
        }
        if (spiked > 0) {
          if (this.activeSession) this.activeSession.engrams.spiked = spiked
          this.logger.info('[Meditation] Post-session spiking complete', { spiked })
        }

        // Run consolidation on the mnemic field
        const result = this.mnemicField.consolidate()
        if (this.activeSession) this.activeSession.consolidations = 1
        this.logger.info('[Meditation] Post-session consolidation complete', {
          potentiationUpdates: result.potentiationUpdates,
          nuclei: result.nucleiDetected,
          abstractions: result.abstractionsCreated,
        })
      } catch (err) {
        this.logger.warn('[Meditation] Post-session mnemic processing failed', { error: String(err) })
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


  /**
   * Organizing session — single agent that restructures the mnemic field.
   *
   * Unlike standard meditation (multiple free explorers), organizing spawns
   * one purposeful agent with structural tools: survey, kindle, bridge,
   * consolidate, audit abstractions, and resolve tensions. After the organizer
   * finishes, the Corpus synthesis phase reviews what changed and records
   * meta-learning insights about the knowledge topology.
   */
  private async runOrganizingSession(
    constellationId: string,
    tier: string,
    abortController: AbortController,
  ): Promise<void> {
    if (!this.mnemicField || !this.handleFactory) {
      void this.stopMeditation('error')
      return
    }

    // Create health analyzer for before/after diagnostics
    const healthAnalyzer = new FieldHealthAnalyzer(this.mnemicField, this.logger, this.meditationStore)

    // Reuse cached snapshot from health check when available
    const beforeSnapshot = this.cachedHealthSnapshot ?? healthAnalyzer.snapshot()
    this.cachedHealthSnapshot = undefined

    const fieldStats = this.mnemicField.stats()
    const healthReport = healthAnalyzer.formatHealthReport(beforeSnapshot)
    const priorityRegions = healthAnalyzer.prioritizeRegions(5)
    const explorerPrompt = buildOrganizingExplorerPrompt(fieldStats, healthReport, priorityRegions)

    const { handlers, stats: organizingStats, touchedRegions } = buildOrganizingHandlers(
      this.mnemicField, this.logger, healthAnalyzer,
    )

    try {
      const handle = await this.handleFactory({
        tier,
        purpose: 'meditation:organizing',
        sessionId: `${constellationId}-organizer`,
      })

      this.logger.info('[Meditation] Starting organizing session', {
        constellationId,
        engramCount: fieldStats.engramCount,
        nucleusCount: fieldStats.nucleusCount,
        fragmentationScore: beforeSnapshot.fragmentationScore,
        priorityRegions: priorityRegions.map(r => r.label),
      })

      const organizerResult = await runSoloExplorer({
        sessionId: `${constellationId}-organizer`,
        name: 'organizer',
        instruction: explorerPrompt,
        handle,
        toolExecutor: this.toolExecutor!,
        toolRegistry: this.toolRegistry!,
        maxIterations: this.meditationConfig.maxTotalSteps,
        logger: this.logger,
        eventBus: this.eventBus!,
        signal: abortController.signal,
        customHandlers: handlers,
        customToolSchemas: getOrganizingToolSchemas(),
      })

      // Capture after-snapshot and compute delta
      const afterSnapshot = healthAnalyzer.snapshot()
      const { delta } = healthAnalyzer.recordOrganizingSession(
        constellationId,
        touchedRegions,
        beforeSnapshot,
        afterSnapshot,
      )

      // Capture result in the session
      if (this.activeSession) {
        this.activeSession.soloResults = [{
          name: organizerResult.name,
          iterations: organizerResult.iterations,
          toolCalls: organizerResult.toolCalls,
          tokensUsed: organizerResult.tokensUsed,
          stoppedBy: organizerResult.stoppedBy,
          transcript: organizerResult.transcript,
        }]
      }

      this.logger.info('[Meditation] Organizing explorer completed', {
        constellationId,
        iterations: organizerResult.iterations,
        toolCalls: organizerResult.toolCalls,
        tokensUsed: organizerResult.tokensUsed,
        stoppedBy: organizerResult.stoppedBy,
        organizingStats,
        delta: delta.summary,
        fragmentationBefore: beforeSnapshot.fragmentationScore.toFixed(3),
        fragmentationAfter: afterSnapshot.fragmentationScore.toFixed(3),
      })

      // Emit organizing-specific event
      emitMeditationEvent(this.eventBus, {
        type: 'meditation:organizing-complete',
        constellationId,
        regionsKindled: organizingStats.regionsKindled,
        bridgesCreated: organizingStats.bridgesCreated,
        consolidationsRun: organizingStats.consolidationsRun,
        abstractionsAudited: organizingStats.abstractionsAudited,
        tensionsSurfaced: organizingStats.tensionsSurfaced,
        durationMs: this.activeSession ? Date.now() - this.activeSession.startedAt : 0,
        timestamp: Date.now(),
      })

      // Corpus synthesis — Cassi reflects on what the organizing revealed
      await this.runOrganizingCorpusCycle(
        constellationId,
        organizerResult,
        organizingStats,
        delta,
      )

      // Evaluation — score the organizing prompts
      if (this.meditationStore) {
        await this.runEvaluation(constellationId, [organizerResult])
      }

      void this.stopMeditation('natural')
    } catch (err) {
      this.logger.error('[Meditation] Organizing session failed', { error: String(err) })
      void this.stopMeditation('error')
    }
  }


  /**
   * Corpus cycle for organizing mode — uses the organizing-specific prompt
   * that focuses on structural insights rather than exploration observations.
   */
  private async runOrganizingCorpusCycle(
    constellationId: string,
    organizerResult: SoloRunnerResult,
    organizingStats: OrganizingStats,
    delta?: import('./field-health.js').OrganizingDelta,
  ): Promise<void> {
    if (!this.mnemicField || !this.handleFactory) return

    const prompt = buildOrganizingCorpusPrompt(
      [{ name: organizerResult.name, content: organizerResult.transcript || '(no transcript)' }],
      organizingStats,
      delta ? { summary: delta.summary, improvements: delta.improvements as unknown as Record<string, number> } : undefined,
    )

    try {
      const handle = await this.handleFactory({
        tier: 'qwenPlus',
        purpose: 'corpus',
        sessionId: `${constellationId}-corpus`,
      })

      await runSoloExplorer({
        sessionId: `${constellationId}-corpus`,
        name: 'corpus',
        instruction: prompt,
        handle,
        toolExecutor: this.toolExecutor!,
        toolRegistry: this.toolRegistry!,
        maxIterations: 10,
        logger: this.logger,
        eventBus: this.eventBus!,
        signal: this.activeAbortController?.signal ?? new AbortController().signal,
        customHandlers: buildCorpusHandlers(this.mnemicField, this.logger),
        customToolSchemas: getCorpusToolSchemas('organizing'),
      })
    } catch (err) {
      this.logger.warn('[Meditation] Organizing corpus cycle failed', { error: String(err) })
    }
  }


  /**
   * Corpus synthesis — Cassi observes explorer transcripts and extracts insights.
   * Runs as a SoloRunner with custom handlers that write to the mnemic field.
   */
  private async runCorpusCycle(
    constellationId: string,
    style: MeditationStyle,
    soloResults: SoloRunnerResult[],
  ): Promise<void> {
    if (!this.mnemicField || !this.handleFactory) return

    const prompt = buildCorpusCyclePrompt(style, soloResults.map(r => ({
      name: r.name,
      content: r.transcript || '(no transcript)',
    })), {
      style,
      durationMs: this.activeSession ? Date.now() - this.activeSession.startedAt : 0,
      prompts: this.activeSession?.prompts ?? [],
      cycleNumber: 1,
      totalExplorers: soloResults.length,
    })

    try {
      const handle = await this.handleFactory({
        tier: 'qwenPlus',
        purpose: 'corpus',
        sessionId: `${constellationId}-corpus`,
      })

      await runSoloExplorer({
        sessionId: `${constellationId}-corpus`,
        name: 'corpus',
        instruction: prompt,
        handle,
        toolExecutor: this.toolExecutor!,
        toolRegistry: this.toolRegistry!,
        maxIterations: 10,
        logger: this.logger,
        eventBus: this.eventBus!,
        signal: this.activeAbortController?.signal ?? new AbortController().signal,
        customHandlers: buildCorpusHandlers(this.mnemicField, this.logger),
        customToolSchemas: getCorpusToolSchemas(style),
      })
    } catch (err) {
      this.logger.warn('[Meditation] Corpus cycle failed', { error: String(err) })
    }
  }


  /**
   * Evaluation — Cassi scores prompts and mutates the library.
   * Runs as a SoloRunner with custom handlers that use the MeditationStore.
   */
  private async runEvaluation(
    constellationId: string,
    soloResults: SoloRunnerResult[],
  ): Promise<void> {
    if (!this.meditationStore || !this.activeSession) return

    const prompt = buildEvaluationPrompt(
      this.activeSession,
      soloResults.map(r => ({ name: r.name, transcript: r.transcript })),
      this.meditationStore,
    )

    try {
      const handle = await this.handleFactory!({
        tier: 'background',
        purpose: 'evaluation',
        sessionId: `${constellationId}-eval`,
      })

      await runSoloExplorer({
        sessionId: `${constellationId}-eval`,
        name: 'evaluation',
        instruction: prompt,
        handle,
        toolExecutor: this.toolExecutor!,
        toolRegistry: this.toolRegistry!,
        maxIterations: 15,
        logger: this.logger,
        eventBus: this.eventBus!,
        signal: this.activeAbortController?.signal ?? new AbortController().signal,
        customHandlers: buildEvaluationHandlers(this.meditationStore!, this.activeSession!, this.logger),
        customToolSchemas: getEvaluationToolSchemas(),
      })
    } catch (err) {
      this.logger.warn('[Meditation] Evaluation failed', { error: String(err) })
    }
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
