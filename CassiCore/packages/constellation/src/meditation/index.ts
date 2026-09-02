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

import { BaseCognitiveModule } from '../vendor/base/cognitive-module.js'
import { MODEL_DEFAULTS } from '../vendor/config/system-settings.js'
import { isGamingMode } from '../ports/gaming-mode.js'
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
import type { MiniHelixDeps } from '../vendor/mini-helix/mini-helix-types.js'
import { buildCorpusCyclePrompt, getCorpusToolSchemas, buildCorpusHandlers } from './corpus-synthesis.js'
import { DEFAULT_CORPUS_PROMPTS, pickCorpusPromptThompson } from './corpus-prompt-library.js'
import type { CorpusPrompt } from './corpus-prompt-library.js'
import { buildEvaluationPrompt, getEvaluationToolSchemas, buildEvaluationHandlers } from './evaluation-runner.js'
import { buildMetaEvaluationPrompt, getMetaEvaluationToolSchemas, buildMetaEvaluationHandlers } from './meta-evaluation-runner.js'
import { buildOrganizingExplorerPrompt, getOrganizingToolSchemas, buildOrganizingHandlers, buildOrganizingCorpusPrompt } from './organizing-synthesis.js'
import type { OrganizingStats } from './organizing-synthesis.js'
import { buildSelfModelingExplorerPrompt, getSelfModelingToolSchemas, buildSelfModelingHandlers } from './self-modeling-synthesis.js'
import { FieldHealthAnalyzer } from './field-health.js'
import type { FieldHealthSnapshot } from './field-health.js'
import { MeditationFeedbackTracker } from './meditation-feedback.js'

import type { ConstellationOrchestrator } from '../constellation-orchestrator.js'
import type { ConstellationRegistry } from '../constellation-injection.js'
import type { MnemicField } from '@cassicore/mnemic-field'
import type { SelfModelField } from '@cassicore/mnemic-field'
import type { InterFieldBridge } from '@cassicore/mnemic-field'
import type { ILogger } from '../vendor/types/interfaces.js'
import type { CorticalField } from '@cassicore/cortex-pineal-dialectic'
import type { ICorpusTree } from '../corpus-types.js'
import type { Aurora } from '@cassicore/aurora'
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
  private selfModelField?: SelfModelField
  private interFieldBridge?: InterFieldBridge
  private meditationStore?: MeditationStore
  private handleFactory?: MiniHelixDeps['handleFactory']
  private cortex?: CorticalField
  private activeAbortController?: AbortController
  /** Cached by checkAndMeditate when health-based organizing is triggered */
  private cachedHealthSnapshot?: FieldHealthSnapshot
  private aurora?: Aurora
  private directedMeditationCount = 0


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

  setSelfModelField(field: SelfModelField): void {
    this.selfModelField = field
  }

  setInterFieldBridge(bridge: InterFieldBridge): void {
    this.interFieldBridge = bridge
  }

  setHandleFactory(factory: MiniHelixDeps['handleFactory']): void {
    this.handleFactory = factory
  }

  setCortex(cortex: CorticalField): void {
    this.cortex = cortex
  }


  /**
   * C1.3 Sub6 inlet: when Aurora has auto-scheduled meditation seeds, the idle
   * loop drains their topics here and runs a focused session against them
   * instead of LLM-discovered focus topics.
   */
  setAurora(aurora: Aurora): void {
    this.aurora = aurora
  }

  /**
   * MnemicReader interface for ContextRepo projection.
   * Returns engrams above the given potentiation threshold, newest first.
   */
  listForProjection(opts: { limit: number; minPotentiation: number }): import('../vendor/context-repo/projection.js').EngramLike[] {
    if (!this.mnemicField) return []
    const all = this.mnemicField.list(opts.limit * 2)
    return all
      .filter(e => e.potentiation >= opts.minPotentiation)
      .sort((a, b) => b.potentiation - a.potentiation)
      .slice(0, opts.limit)
      .map(e => ({
        id: e.id,
        nodeType: e.nodeType,
        content: e.content,
        potentiation: e.potentiation,
        pinned: false,
        tags: e.tags,
        metadata: e.metadata,
      }))
  }

  getMnemicField(): MnemicField | undefined {
    return this.mnemicField
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
    // Meditation is always-on — user activity does not stop it.
    // The Thalamus manages context growth for long-running sessions.
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
   *
   * When seedTopics is provided, forces focused style and uses those topics
   * directly (Aurora-driven path). Takes precedence over followUp.
   */
  async triggerMeditation(style?: MeditationStyle, followUp?: boolean, modelTier?: string, seedTopics?: string[]): Promise<MeditationSession | null> {
    this.logger.info('[Meditation] triggerMeditation called', { style, followUp, modelTier, seedTopics })
    if (this.state === 'meditating') {
      this.logger.info('[Meditation] Already meditating — ignoring trigger')
      return this.activeSession ?? null
    }

    if (!this.orchestrator || !this.registry) {
      this.logger.warn('[Meditation] Cannot meditate — orchestrator or registry not wired')
      return null
    }

    // seedTopics takes precedence: forces focused style, bypasses followUp
    if (seedTopics && seedTopics.length > 0) {
      return this.startMeditation('focused', modelTier, seedTopics)
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
   * Previously cancelled meditation for real Constellation work.
   * Now meditation runs alongside all other work at background priority —
   * the cost of one extra session is minimal and the continuous learning is valuable.
   */
  cancelForRealWork(): void {
    // No-op: meditation no longer stops for Constellation work
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

    // Meditation runs alongside active constellations — no blocking gate.
    // The background model tier keeps resource contention minimal.

    // Initial startup delay: wait for idle threshold once before first session.
    // After the first session starts, meditation runs continuously.
    const idleMs = Date.now() - this.lastTurnAt
    if (this.sessionCount === 0 && this.lastTurnAt > 0 && idleMs < this.meditationConfig.idleThresholdMs) return

    // Minimal cooldown between sessions (60s) to prevent thrashing on errors.
    // The full cooldownMs config is honored only for the initial startup.
    const sinceLast = Date.now() - this.lastMeditationAt
    const effectiveCooldown = this.sessionCount > 0 ? 60_000 : this.meditationConfig.cooldownMs
    if (this.lastMeditationAt > 0 && sinceLast < effectiveCooldown) return

    // C1.3 Sub6: Aurora-scheduled seeds preempt idle-driven style selection.
    // Topics from auto_schedule decisions feed directly into a focused session;
    // the seeder's own anxious-loop guard already throttles thrash.
    if (this.aurora) {
      try {
        const topics = this.aurora.collectAutoScheduledTopics(this.sessionCount, this.directedMeditationCount)
        if (topics.length > 0) {
          this.directedMeditationCount++
          emitMeditationEvent(this.eventBus, {
            type: 'meditation:style-selected',
            style: 'focused',
            reason: 'aurora auto-schedule',
            idleMs,
            timestamp: Date.now(),
          })
          await this.startMeditation('focused', undefined, topics)
          return
        }
      } catch (err) {
        this.logger.debug('[Meditation] Aurora auto-schedule probe failed (non-fatal)', { error: String(err) })
      }
    }

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
          const last = analyzer.getRecentSessions(1)[0]
          const sinceLast = last ? Date.now() - last.timestamp : Infinity
          if (sinceLast < this.meditationConfig.organizingCooldownMs) {
            this.logger.info('[Meditation] Skipping organizing upgrade — within cooldown', {
              sinceLastMs: sinceLast,
              cooldownMs: this.meditationConfig.organizingCooldownMs,
              score: health.score,
            })
          } else {
            style = 'organizing'
            this.cachedHealthSnapshot = analyzer.snapshot()
            this.logger.info('[Meditation] Health-based organizing upgrade', {
              reason: health.reason,
              score: health.score,
            })
          }
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


  private async startMeditation(
    style?: MeditationStyle,
    modelTier?: string,
    seedTopics?: string[],
  ): Promise<MeditationSession | null> {
    this.logger.info('[Meditation] startMeditation called', { style, modelTier, seedTopics })
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

    // Focused mode: seed the mnemic field before launching explorers.
    // When Aurora supplied topics, runFocusedSeeding skips its mini-helix
    // discovery and kindles those topics directly.
    if (resolvedStyle === 'focused' && this.mnemicField && this.memory && this.handleFactory) {
      try {
        const seedResult = await runFocusedSeeding({
          mnemicField: this.mnemicField,
          memory: this.memory,
          handleFactory: this.handleFactory,
          logger: this.logger,
          eventBus: this.eventBus,
          seedTopics,
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

    // ── Phase 7: Session Start Persistence ──────────────────────────────── // contributing:ignore
    // Record complete session start with configuration snapshot
    if (this.meditationStore) {
      try {
        // Record session start
        this.meditationStore.recordSessionStart({
          id: constellationId,
          started_at: Date.now(),
          style: resolvedStyle,
          config_snapshot: JSON.stringify(this.meditationConfig),
        })

        // Record configuration history for tracking evolution
        const now = Date.now()
        const configKeys = Object.keys(this.meditationConfig)
        for (const key of configKeys) {
          const value = (this.meditationConfig as any)[key]
          this.meditationStore.recordConfigHistory({
            session_id: constellationId,
            config_key: key,
            config_value: JSON.stringify(value),
            changed_at: now,
          })
        }

        // Record prompt assignments
        for (const assignment of promptAssignments) {
          this.meditationStore.recordPromptAssignment({
            session_id: constellationId,
            helix_id: `${constellationId}-${assignment.explorer}`,
            explorer_name: assignment.explorer,
            prompt_id: assignment.promptId,
            prompt_category: assignment.promptId.split('-')[0] ?? 'minimal',
            assigned_at: now,
            assignment_reason: this.meditationStore ? 'thompson' : 'sequential',
          })
        }

        this.logger.info('[Meditation] Session start persisted', { constellationId })
      } catch (err) {
        this.logger.warn('[Meditation] Session start persistence failed', { error: String(err) })
      }
    }

    emitMeditationEvent(this.eventBus, {
      type: 'meditation:started',
      constellationId,
      style: resolvedStyle,
      prompts: promptAssignments,
      timestamp: Date.now(),
    })

    // Duration safety valve — for always-on meditation, sessions can run
    // for up to 24 hours. The Thalamus manages context window growth.
    // This timer exists only as a safety limit; sessions normally end
    // when the agent calls complete_organizing or a style transition occurs.
    const maxDuration = Math.max(this.meditationConfig.maxDurationMs, 86_400_000)
    this.durationTimer = setTimeout(
      () => { void this.stopMeditation('max-duration') },
      maxDuration,
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

      if (resolvedStyle === 'self-modeling' && this.selfModelField && this.interFieldBridge) {
        this.runSelfModelingSession(constellationId, tier, abortController)
          .catch((err) => {
            this.logger.warn('[Meditation] Self-modeling session failed', { error: String(err) })
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
          if (this.mnemicField && this.meditationStore) {
            const corpusPrompt = this.pickCorpusPrompt(resolvedStyle)
            await this.runCorpusCycle(constellationId, corpusPrompt, soloResults)

            // Meta-evaluation — score the corpus prompt
            await this.runMetaEvaluation(constellationId, corpusPrompt, soloResults)
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
      await this.mnemicBridge.triggerConsolidation()
    }

    // Stop MnemicBridge
    if (this.mnemicBridge) {
      this.mnemicBridge.stop()
      this.mnemicBridge = undefined
    }

    /**
   * SoloRunner path: spike related engrams and consolidate directly via MnemicField.
   * The MnemicBridge is only used by the old Constellation path — SoloRunners
   * store insights via the store_insight tool, but without spiking or consolidation.
   */
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
      const result = await this.mnemicField.consolidate()
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


// ── Phase 7 Helper Methods ─────────────────────────────────────────── // contributing:ignore

/**
 * Count insights generated during this session.
 */
private async countSessionInsights(): Promise<number> {
  if (!this.memory || !this.activeSession) return 0
  
  try {
    const memAny = this.memory as any
    if (typeof memAny.getRecent !== 'function') return 0
    
    const recent = await memAny.getRecent(200)
    const sessionInsights = (recent ?? []).filter((e: any) =>
      e.metadata?.source === 'meditation' &&
      e.type === 'insight' &&
      e.createdAt && new Date(e.createdAt).getTime() > this.activeSession!.startedAt
    )
    return sessionInsights.length
  } catch {
    return 0
  }
}

/**
 * Calculate success rating based on session outcomes.
 * Returns 0-1 score reflecting session quality.
 */
private calculateSuccessRating(data: {
  insights: number
  steps: number
  engrams: { spiked: number; created: number }
  consolidations: number
}): number {
  // Weight factors:
  // - Insights generated: most important (weight 0.4)
  // - Steps taken: exploration breadth (weight 0.2)
  // - Engrams created: memory formation (weight 0.2)
  // - Consolidations: knowledge integration (weight 0.2)
  
  const insightScore = Math.min(data.insights / 5, 1) // 5 insights = max score
  const stepScore = Math.min(data.steps / 50, 1) // 50 steps = max score
  const engramScore = Math.min((data.engrams.spiked + data.engrams.created) / 10, 1) // 10 engrams = max
  const consolidationScore = Math.min(data.consolidations / 3, 1) // 3 consolidations = max
  
  return (
    insightScore * 0.4 +
    stepScore * 0.2 +
    engramScore * 0.2 +
    consolidationScore * 0.2
  )
}

/**
 * Count discoveries mentioned in transcript.
 * Simple heuristic: count "I noticed" phrases.
 */
private countDiscoveries(transcript?: string): number {
  if (!transcript) return 0
  const matches = transcript.match(/I noticed/gi)
  return matches ? matches.length : 0
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

    // Create feedback tracker for neural kindling learning
    const feedbackTracker = new MeditationFeedbackTracker(
      this.logger.child('meditation-feedback'),
      constellationId,
    )

    // Reuse cached snapshot from health check when available
    const beforeSnapshot = this.cachedHealthSnapshot ?? healthAnalyzer.snapshot()
    this.cachedHealthSnapshot = undefined

    const fieldStats = this.mnemicField.stats()
    const healthReport = healthAnalyzer.formatHealthReport(beforeSnapshot)
    const priorityRegions = healthAnalyzer.prioritizeRegions(5)
    const explorerPrompt = buildOrganizingExplorerPrompt(fieldStats, healthReport, priorityRegions)

    const { handlers, stats: organizingStats, touchedRegions } = buildOrganizingHandlers(
      this.mnemicField, this.logger, healthAnalyzer, this.meditationStore, feedbackTracker,
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
        orphansAssigned: organizingStats.orphansAssigned,
        embeddingsBackfilled: organizingStats.embeddingsBackfilled,
        batchKindles: organizingStats.batchKindles,
        batchBridges: organizingStats.batchBridges,
        nucleusDetections: organizingStats.nucleusDetections,
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

      // Send feedback to Mnemic Field for neural kindling learning
      if (this.mnemicField) {
        try {
          const feedbackResult = await feedbackTracker.sendToMnemicField(this.mnemicField)
          this.logger.info('[Meditation] Organizing feedback sent', {
            engramsTracked: feedbackResult.engramsTracked,
            helpfulCount: feedbackResult.helpfulCount,
            unhelpfulCount: feedbackResult.unhelpfulCount,
            helpfulRatio: feedbackResult.engramsTracked > 0
              ? (feedbackResult.helpfulCount / feedbackResult.engramsTracked).toFixed(2)
              : '0',
          })
        } catch (err) {
          this.logger.warn('[Meditation] Failed to send organizing feedback', { error: String(err) })
        }
      }

      // Expert enrichment: strengthen expert clusters that need updating
      if (this.mnemicField) {
        try {
          const { dormant, archived, hot } = this.mnemicField.checkExpertLifecycle()
          if (hot.length > 0) {
            this.logger.info('[Meditation] Enriching hot experts', { count: hot.length })
            for (const expertId of hot.slice(0, 3)) {
              const experts = this.mnemicField.findExpertEngrams({ limit: 50 })
              const target = experts.find(e => (e.metadata as any)?.expertId === expertId)
              if (target) {
                const richContent = `${target.content}\nMeditation enrichment pass at ${new Date().toISOString()}`
                this.mnemicField.store({
                  content: richContent,
                  nodeType: 'expert_summary' as const,
                  provenance: 'meditation.enrich',
                  metadata: {
                    ...target.metadata,
                    expertNewSinceSummary: 0,
                    enrichedAt: new Date().toISOString(),
                  },
                })
              }
            }
          }
          if (dormant.length > 0) {
            this.logger.debug('[Meditation] Dormant experts detected', { count: dormant.length })
          }
        } catch (err) {
          this.logger.warn('[Meditation] Expert enrichment failed', { error: String(err) })
        }
      }

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
        customHandlers: buildCorpusHandlers(this.mnemicField, this.logger, this.meditationStore, constellationId),
        customToolSchemas: getCorpusToolSchemas({ id: 'organizing', category: 'synthesizer', identity: '', approach: '', style: 'passive' as any }),
      })
    } catch (err) {
      this.logger.warn('[Meditation] Organizing corpus cycle failed', { error: String(err) })
    }
  }


  /**
   * Self-modeling session — single agent that cleans and sharpens architectural self-knowledge.
   */
  private async runSelfModelingSession(
    constellationId: string,
    tier: string,
    abortController: AbortController,
  ): Promise<void> {
    if (!this.selfModelField || !this.interFieldBridge || !this.handleFactory) {
      void this.stopMeditation('error')
      return
    }

    const portalStats = this.interFieldBridge.getPortalStats()
    const weaklyGroundedConcepts = portalStats
      .filter(p => p.episodicConnections <= 1)
      .map(p => p.concept)
      .slice(0, 12)
    const summary = {
      engramCount: this.selfModelField.stats().engramCount,
      domainCount: new Set(this.selfModelField.list('module', 10000).map(m => String((m.metadata as Record<string, unknown>)?.domain ?? 'other'))).size,
      portalCount: portalStats.length,
      weaklyGroundedConcepts,
    }
    const explorerPrompt = buildSelfModelingExplorerPrompt(summary)
    const { handlers, stats: selfModelingStats } = buildSelfModelingHandlers(
      this.selfModelField,
      this.interFieldBridge,
      this.logger,
    )

    try {
      const handle = await this.handleFactory({
        tier,
        purpose: 'meditation:self-modeling',
        sessionId: `${constellationId}-self-modeler`,
      })

      this.logger.info('[Meditation] Starting self-modeling session', {
        constellationId,
        engramCount: summary.engramCount,
        domainCount: summary.domainCount,
        portalCount: summary.portalCount,
        weaklyGroundedConcepts,
      })

      const result = await runSoloExplorer({
        sessionId: `${constellationId}-self-modeler`,
        name: 'self-modeler',
        instruction: explorerPrompt,
        handle,
        toolExecutor: this.toolExecutor!,
        toolRegistry: this.toolRegistry!,
        maxIterations: Math.max(20, Math.floor(this.meditationConfig.maxTotalSteps / 2)),
        logger: this.logger,
        eventBus: this.eventBus!,
        signal: abortController.signal,
        customHandlers: handlers,
        customToolSchemas: getSelfModelingToolSchemas(),
      })

      if (this.activeSession) {
        this.activeSession.soloResults = [{
          name: result.name,
          iterations: result.iterations,
          toolCalls: result.toolCalls,
          tokensUsed: result.tokensUsed,
          stoppedBy: result.stoppedBy,
          transcript: result.transcript,
        }]
      }

      this.logger.info('[Meditation] Self-modeling explorer completed', {
        constellationId,
        iterations: result.iterations,
        toolCalls: result.toolCalls,
        tokensUsed: result.tokensUsed,
        stoppedBy: result.stoppedBy,
        selfModelingStats,
      })

      emitMeditationEvent(this.eventBus, {
        type: 'meditation:self-modeling-complete',
        constellationId,
        domainsAudited: selfModelingStats.domainsAudited,
        modulesReclassified: selfModelingStats.modulesReclassified,
        groundingGapsFound: selfModelingStats.groundingGapsFound,
        principlesCreated: selfModelingStats.principlesCreated,
        patternsCreated: selfModelingStats.patternsCreated,
        weaknessesCreated: selfModelingStats.weaknessesCreated,
        groundingLinksSeeded: selfModelingStats.groundingLinksSeeded,
        durationMs: this.activeSession ? Date.now() - this.activeSession.startedAt : 0,
        timestamp: Date.now(),
      })

      if (this.meditationStore) {
        await this.runEvaluation(constellationId, [result])
      }

      void this.stopMeditation('natural')
    } catch (err) {
      this.logger.error('[Meditation] Self-modeling session failed', { error: String(err) })
      void this.stopMeditation('error')
    }
  }


  /**
   * Corpus synthesis — Cassi observes explorer transcripts and extracts insights.
   * Runs as a SoloRunner with custom handlers that write to the mnemic field.
   */
  private async runCorpusCycle(
    constellationId: string,
    corpusPrompt: CorpusPrompt,
    soloResults: SoloRunnerResult[],
  ): Promise<void> {
    if (!this.mnemicField || !this.handleFactory) return

    const prompt = buildCorpusCyclePrompt(corpusPrompt, soloResults.map(r => ({
      name: r.name,
      content: r.transcript || '(no transcript)',
    })), {
      style: corpusPrompt.style,
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
        customHandlers: buildCorpusHandlers(this.mnemicField, this.logger, this.meditationStore, constellationId),
        customToolSchemas: getCorpusToolSchemas(corpusPrompt),
      })
    } catch (err) {
      this.logger.warn('[Meditation] Corpus cycle failed', { error: String(err) })
    }
  }


  /**
   * Pick a corpus prompt via Thompson sampling.
   */
  private pickCorpusPrompt(style: MeditationStyle): CorpusPrompt {
    if (!this.meditationStore) {
      return DEFAULT_CORPUS_PROMPTS.find(p => p.style === style) ?? DEFAULT_CORPUS_PROMPTS[0]
    }

    const prompts = this.meditationStore.getAllCorpusPrompts()
    if (prompts.length === 0) {
      // Seed defaults
      this.meditationStore.seedCorpusPrompts(DEFAULT_CORPUS_PROMPTS.map(p => ({
        id: p.id, category: p.category, identity: p.identity,
        approach: p.approach, style: p.style,
      })))
      return DEFAULT_CORPUS_PROMPTS.find(p => p.style === style) ?? DEFAULT_CORPUS_PROMPTS[0]
    }

    const thompsonParams = this.meditationStore.getCorpusThompsonParams(style)
    const stylePrompts: CorpusPrompt[] = prompts
      .filter(p => p.style === style && p.retired_at === null)
      .map(p => ({
        id: p.id, category: p.category as CorpusPrompt['category'],
        identity: p.identity, approach: p.approach, style: p.style as MeditationStyle,
      }))
    return pickCorpusPromptThompson(style, stylePrompts, thompsonParams)
  }


  /**
   * Meta-evaluation — Cassi scores her own corpus observation prompt.
   */
  private async runMetaEvaluation(
    constellationId: string,
    corpusPrompt: CorpusPrompt,
    soloResults: SoloRunnerResult[],
  ): Promise<void> {
    if (!this.meditationStore || !this.handleFactory) return

    const corpusOutput = {
      iterations: soloResults.reduce((sum, r) => sum + r.iterations, 0),
      toolCalls: soloResults.reduce((sum, r) => sum + r.toolCalls, 0),
      toolsUsed: ['remember', 'create_engram', 'kindle', 'consolidate', 'record_learning', 'rest'],
      insightsStored: 0,
      consolidations: this.activeSession?.consolidations ?? 0,
    }

    const prompt = buildMetaEvaluationPrompt(
      this.activeSession!,
      corpusPrompt,
      corpusOutput,
      this.meditationStore,
    )

    try {
      const handle = await this.handleFactory({
        tier: 'background',
        purpose: 'meta-evaluation',
        sessionId: `${constellationId}-meta`,
      })

      await runSoloExplorer({
        sessionId: `${constellationId}-meta`,
        name: 'meta-evaluation',
        instruction: prompt,
        handle,
        toolExecutor: this.toolExecutor!,
        toolRegistry: this.toolRegistry!,
        maxIterations: 10,
        logger: this.logger,
        eventBus: this.eventBus!,
        signal: this.activeAbortController?.signal ?? new AbortController().signal,
        customHandlers: buildMetaEvaluationHandlers(this.meditationStore!, this.activeSession!, corpusPrompt.id, this.logger),
        customToolSchemas: getMetaEvaluationToolSchemas(),
      })
    } catch (err) {
      this.logger.warn('[Meditation] Meta-evaluation failed', { error: String(err) })
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

    // ── Phase 7: Session Completion Persistence ────────────────────────────── // contributing:ignore
    // Record complete session outcome
    if (this.meditationStore && this.activeSession) {
      try {
        // Collect final stats
        const soloResults = this.activeSession.soloResults ?? []
        const totalSteps = soloResults.reduce((sum, r) => sum + r.iterations, 0)
        const totalTokens = soloResults.reduce((sum, r) => sum + r.tokensUsed, 0)
        
        // Calculate success rating based on outcomes
        const insightsCount = await this.countSessionInsights()
        const successRating = this.calculateSuccessRating({
          insights: insightsCount,
          steps: totalSteps,
          engrams: this.activeSession.engrams,
          consolidations: this.activeSession.consolidations,
        })

        // Record session completion
        this.meditationStore.recordSessionCompletion({
          id: this.activeSession.constellationId,
          completed_at: Date.now(),
          duration_ms: Date.now() - this.activeSession.startedAt,
          total_steps: totalSteps,
          active_explorers: this.activeSession.prompts.length,
          stop_reason: 'natural',
          success_rating: successRating,
          total_tokens_used: totalTokens,
          insights_generated: insightsCount,
          engrams_spiked: this.activeSession.engrams.spiked,
          engrams_created: this.activeSession.engrams.created,
          consolidations: this.activeSession.consolidations,
          self_awareness_count: this.mnemicBridge?.getSelfAwarenessDetections().length ?? 0,
        })

        // Update prompt assignment outcomes
        for (const result of soloResults) {
          this.meditationStore.updatePromptAssignmentOutcome(
            this.activeSession.constellationId,
            `${this.activeSession.constellationId}-${result.name}`,
            {
              steps_taken: result.iterations,
              discoveries_count: this.countDiscoveries(result.transcript),
              tokens_used: result.tokensUsed,
              final_score: successRating,
            }
          )
        }

        this.logger.info('[Meditation] Session completion persisted', {
          constellationId: this.activeSession.constellationId,
          durationMs: Date.now() - this.activeSession.startedAt,
          insights: insightsCount,
          successRating,
        })

        // ── Phase 5: Aggregate session data for trend analysis ────────
        this.meditationStore.aggregateSessionData(this.activeSession.constellationId)
      } catch (err) {
        this.logger.warn('[Meditation] Session completion persistence failed', { error: String(err) })
      }
    }

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
