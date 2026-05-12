/**
 * Corpus — Constellation-Level Cognitive Organizer
 *
 * The Corpus is to a Constellation what the Brainstem is to a Helix.
 * It maintains a shared reasoning tree with one branch per Helix,
 * built by each Helix's Brainstem pushing annotations as they're produced.
 *
 * The Corpus never polls external systems. Its data comes to it through
 * the shared tree. Its loop simply reads its own state, detects
 * cross-branch patterns, and produces strategic guidance.
 *
 * Four-tier intelligence hierarchy:
 *   Cassi (top)     — full system access, strategic decisions, user interface
 *   Corpus (mid)    — cross-Helix reasoning, spawn evaluation, coordination
 *   Brainstem (low) — per-Helix tactical scoring, local pattern detection
 *   Postures (base) — the actual work (Unity + Yang + Yin)
 *
 * Named after the corpus callosum — the nerve fiber tract connecting
 * brain hemispheres, enabling coordinated thought across regions.
 */

import type { ILogger, IEventBus } from '../../../types/interfaces.js'
import type {
  ICorpusTree,
  CorpusConfig,
  CorpusDeps,
  CorpusProcessedState,
  CorpusResult,
  BranchAssessment,
  BranchHealthStatus,
  CrossHelixPattern,
  CrossHelixPatternType,
  CorpusDirective,
  CorpusDirectiveType,
  CorpusIntervention,
  SpawnDecision,
  CorpusBlackboard,
  CorpusBranch,
  CorpusStep,
  EscalationLevel,
  EscalationThresholds,
  BranchBudget,
  QualityGateResult,
  QualityGateCheck,
  ReDecompositionRequest,
  DiscoveryEntry,
  DirectInjection,
  ResearchDigest,
  ParallelSplitRequest,
  ContextInjection,
  SelfOrgAdjustmentType,
  ExternalCorpusState,
  ExternalCorpusSnapshot,
  PendingExternalSpawnRequest,
} from './corpus-types.js'
import type { DecompositionTracker } from './decomposition-tracker.js'
import { ESCALATION_DEFAULTS, BRANCH_BUDGET_DEFAULTS, createInitialExternalCorpusState, DEFAULT_LLM_HEALTH_CONFIG } from './corpus-types.js'
import type { LLMHealthState, LLMHealthConfig, LLMHealthStatus } from './corpus-types.js'
import type { SpawnRequest, ConstellationTemplate } from './types.js'
import { getTemplateCapabilities, listTemplateCapabilities } from './templates.js'
import {
  DEFAULT_CORPUS_CONFIG,
  createInitialProcessedState,
} from './corpus-types.js'
import type { BrainstemAnnotation, WorkUnitAnnotation, DetectedPattern, GuidanceUrgency } from '../helix/brainstem-types.js'
import {
  executeCorpusTool,
  buildCorpusSystemPrompt,
  getCorpusToolDefinitions,
  getMeditationToolSet,
} from './corpus-tools.js'
import {
  normalizeDirectiveType,
  normalizeUrgency,
  extractFilePaths,
} from './corpus/corpus-utils.js'
import { PatternDetector } from './corpus/corpus-patterns.js'
import { ExternalCorpusProtocol } from './corpus/corpus-external.js'
import { BridgeDedupe, handleWorkspaceBroadcastForTerritory, type SiblingGoalEntry } from './territory-bridge.js'
import { SignalPatternBuffer, renderDigestMarkdown, shouldRecordForDigest } from './signal-pattern-digest.js'
import type { CognitiveSignal } from '../workspace/cognitive-signal.js'
import type { CorpusToolContext, ToolCallResult } from './corpus-tools.js'
import { Locus } from './locus/index.js'
import type { LocusSweepResult } from './locus/index.js'
import type { LocusSnapshot } from './locus/locus-types.js'
import { MnemicLocusMemoryPersistence } from './locus/mnemic-locus-memory-persistence.js'
import { SPAWN_EVALUATION_PHRASES, DIRECTIVE_QUALITY_PHRASES } from '../phrase-prototypes.js'

/**
 * Minimal interface for child Brainstem to avoid circular imports.
 * The Corpus only needs to send directives to registered Brainstems.
 */
interface MinimalBrainstem {
  onCorpusDirective?: (directive: CorpusDirective) => void
}

/**
 * Corpus — The strategic organizer of a Constellation.
 *
 * Reads from the shared CorpusTree, detects cross-branch patterns,
 * evaluates spawn requests, and sends directives to child Brainstems.
 */
export class Corpus {
  private tree: ICorpusTree
  private deps: CorpusDeps
  private config: CorpusConfig
  private state: CorpusProcessedState
  private logger: ILogger

  // Child Brainstems registry (helixId -> MinimalBrainstem)
  private childBrainstems: Map<string, MinimalBrainstem> = new Map()

  // Async loop control
  private running = false
  private shutdownRequested = false
  private loopPromise: Promise<void> | null = null

  // LLM health tracking (3-state: primary | fallback | rule_based)
  private llmHealthState: LLMHealthState = 'primary'
  private llmConsecFailures = 0
  private llmNextProbeAt = 0
  private llmRecoverySweepsLeft = 0

  // Adaptive cadence tracking
  private consecutiveFailures = 0

  // Timing
  private startTime = 0

  // Counter for LLM analysis triggering
  private newStepsSinceLLM = 0

  // Safety-net mode: tracks when the last LLM analysis ran
  private lastAnalysisSweep = 0
  // Escalation queue: reasons from Brainstems that self-org can't resolve
  private escalationQueue: Array<{ reason: string; context: Record<string, unknown> }> = []

  /** Cross-branch discovery log */
  private discoveries: Map<string, DiscoveryEntry> = new Map()
  /** Research digests from completed research branches */
  private researchDigests: ResearchDigest[] = []
  /** Re-decomposition requests executed */
  private reDecompositions: ReDecompositionRequest[] = []
  /** Direct injections performed */
  private directInjections: DirectInjection[] = []
  /** Parallel split requests executed */
  private parallelSplits: ParallelSplitRequest[] = []
  /** Context injections performed */
  private contextInjections: ContextInjection[] = []
  /** Quality gate results for completed branches */
  private qualityGateResults: Map<string, QualityGateResult> = new Map()
  /** Branch budgets (helixId -> BranchBudget) */
  private branchBudgets: Map<string, BranchBudget> = new Map()
  /** Discovery counter for IDs */
  private discoveryCounter = 0

  // Effectiveness tracking: baseline scores before interventions
  private interventionBaselines = new Map<string, { score: number; type: string; timestamp: number; step: number }>()

  // Periodic checkpointing
  private lastCheckpointAt = 0
  private static readonly CHECKPOINT_INTERVAL_MS = 60_000 // checkpoint every 60s

  // External Corpus Protocol — allow an external agent to assume the Corpus role
  private externalProtocol: ExternalCorpusProtocol
  private stopped = false

  // WHY: When new branches are created, the Corpus should wake up immediately
  // instead of sleeping for the remainder of its poll interval. Without this,
  // branches can exhaust their step budget before the Corpus ever observes them.
  private wakeRequested = false

  // Incremental re-decomposition tracker
  private decompositionTracker?: DecompositionTracker

  // Locus — Global Workspace (attention layer between Corpus and Brainstems)
  private locus: Locus
  private locusSweepResults: LocusSweepResult[] = []
  private locusPersistence: import('./locus/constellation-memory.js').LocusMemoryPersistence | undefined
  private patternDetector: PatternDetector

  // Territory awareness (PR-2 of cross-helix-territory-awareness spec):
  // index of sibling goal signals + cooldown dedupe for bridge-signal emission.
  private siblingGoalIndex: Map<string, SiblingGoalEntry> = new Map()
  private bridgeDedupe?: BridgeDedupe
  private workspaceUnsubscribe?: () => void

  // C-OBS-1 GWT-grounding supplement: rolling digest of recent qualifying
  // signals, fed from the same onWorkspaceBroadcast handler as territory awareness.
  private signalPatternBuffer: SignalPatternBuffer = new SignalPatternBuffer()

  constructor(tree: ICorpusTree, deps: CorpusDeps, config?: Partial<CorpusConfig>) {
    this.tree = tree
    this.deps = deps
    this.config = { ...DEFAULT_CORPUS_CONFIG, ...config }
    this.state = createInitialProcessedState()
    this.logger = deps.logger.child('Corpus')

    this.logger.info('Corpus initialized', {
      constellationId: deps.constellationId,
      enabled: this.config.enabled,
    })

    const locusPersistence = deps.mnemicField
      ? new MnemicLocusMemoryPersistence(deps.mnemicField, this.logger)
      : deps.store?.getLocusMemoryPersistence()

    this.locus = new Locus({
      logger: this.logger,
      sessionId: deps.constellationId,
      memoryPersistence: locusPersistence,
    })

    this.locusPersistence = locusPersistence

    this.patternDetector = new PatternDetector({
      tree,
      state: this.state,
      topology: deps.topology,
      eventBus: deps.eventBus,
      logger: this.logger,
    })

    // External Corpus Protocol — initialized with callbacks that reference this
    this.externalProtocol = new ExternalCorpusProtocol({
      callbacks: {
        isRunning: () => this.running,
        isStopped: () => this.stopped,
        getConstellationId: () => this.deps.constellationId,
        getExternalSnapshot: () => this.getExternalSnapshotInternal(),
        postSynthesisToBlackboard: (content, author) => this.postSynthesisToBlackboard(content, author),
        onSpawnRequest: (req) => this.deps.onSpawnRequest?.(req),
        recordSpawnDecision: (decision) => this.state.spawnDecisions.push(decision),
        sendDirective: (directive) => this.sendDirectiveInternal(directive),
        emitEvent: (type, data) => this.emitEvent(type, data),
      },
      logger: this.logger,
    })
  }

  /**
   * WHY: Inform the Corpus that CorpusObserverLayer handles cross-Helix LLM
   * analysis. The Corpus skips its own runLLMAnalysis() to avoid redundant
   * LLM calls with worse input data. (observer consolidation)
   */
  setCorpusObserverActive(active: boolean): void {
    this.deps = { ...this.deps, corpusObserverActive: active }
  }

  /**
   * Start the async Corpus loop
   */
  async start(): Promise<void> {
    if (!this.config.enabled) {
      this.logger.info('Corpus is disabled, skipping start')
      return
    }

    if (this.running) {
      this.logger.warn('Corpus already running')
      return
    }

    this.running = true
    this.shutdownRequested = false
    this.startTime = Date.now()

    this.logger.info('Corpus loop starting')

    if (this.deps.globalWorkspace) {
      this.bridgeDedupe = new BridgeDedupe(30_000)
      this.workspaceUnsubscribe = this.deps.globalWorkspace.onBroadcast(
        signals => this.onWorkspaceBroadcast(signals),
      )
      this.logger.debug('Corpus subscribed to GlobalWorkspace broadcasts for territory awareness')
    }

    this.loopPromise = this.runLoop()
  }

  /**
   * Stop the Corpus loop gracefully
   */
  async stop(): Promise<void> {
    if (!this.running) {
      return
    }

    this.logger.info('Corpus shutdown requested')
    this.shutdownRequested = true
    this.stopped = true

    if (this.workspaceUnsubscribe) {
      try { this.workspaceUnsubscribe() } catch { /* non-fatal */ }
      this.workspaceUnsubscribe = undefined
    }
    this.siblingGoalIndex.clear()

    // Release external Corpus if assumed
    if (this.externalProtocol.isAssumed()) {
      this.release('corpus shutting down')
    }
    this.externalProtocol.stop()

    if (this.loopPromise) {
      await this.loopPromise
      this.loopPromise = null
    }

    this.running = false

    // Consolidate Locus memory at end of constellation run
    const memResult = this.locus.consolidateMemory()
    if (memResult.promoted > 0 || memResult.invalidated > 0) {
      this.logger.info('Locus memory consolidated on shutdown', memResult)
    }

    this.logger.info('Corpus stopped', {
      durationMs: Date.now() - this.startTime,
      sweeps: this.state.sweepCount,
    })
  }

  /**
   * Check if Corpus is running
   */
  isRunning(): boolean {
    return this.running
  }

  /**
   * Workspace broadcast handler — PR-2 of cross-helix-territory-awareness spec.
   * Filters incoming `goal` signals by membership in childBrainstems, maintains
   * the sibling goal index, and emits `bridge` signals on territorial overlap.
   *
   * Bridge signals (source: 'corpus', type: 'bridge') flow back through
   * onBroadcast and re-enter this handler — the `if (sig.type !== 'goal')` guard
   * makes that loop a no-op.
   */
  private onWorkspaceBroadcast(signals: CognitiveSignal[]): void {
    if (!this.deps.globalWorkspace || !this.bridgeDedupe) return
    handleWorkspaceBroadcastForTerritory(
      signals,
      {
        siblingGoalIndex: this.siblingGoalIndex,
        isMember: id => this.childBrainstems.has(id),
      },
      this.deps.globalWorkspace,
      this.bridgeDedupe,
      this.deps.constellationId,
    )

    for (const sig of signals) {
      if (!shouldRecordForDigest(sig)) continue
      if (!this.childBrainstems.has(sig.sessionId)) continue
      this.signalPatternBuffer.record(sig)
    }
  }

  /**
   * C-OBS-1 GWT-grounding: rendered digest of recent workspace signals from
   * sibling Helixes. Returned as advisory input for both runLLMAnalysis (via
   * buildCorpusSystemPrompt) and CorpusObserverLayer (via its own prompt builder).
   * Returns undefined in meditation mode and when buffer is empty.
   */
  getSignalPatternDigest(): string | undefined {
    if (this.deps.meditationMode) return undefined
    return renderDigestMarkdown(this.signalPatternBuffer)
  }

  // --- External Corpus Protocol ---
  // All external protocol methods delegate to ExternalCorpusProtocol instance

  /**
   * Check if an external agent currently holds the Corpus role.
   */
  isExternallyAssumed(): boolean {
    return this.externalProtocol.isAssumed()
  }

  /**
   * Get the external Corpus state (for status queries).
   */
  getExternalState(): ExternalCorpusState {
    return this.externalProtocol.getState()
  }

  /**
   * Get the Locus snapshot for external introspection.
   */
  getLocusSnapshot(): LocusSnapshot | undefined {
    return this.locus.enabled ? this.locus.getSnapshot() : undefined
  }

  /**
   * Get active Locus memories for external introspection.
   */
  getLocusMemories(): import('./locus/memory-types.js').LocusMemoryEntry[] | undefined {
    return this.locus.enabled ? this.locus.getMemory().getActive() : undefined
  }

  getLocusMemoryPersistence(): import('./locus/constellation-memory.js').LocusMemoryPersistence | undefined {
    return this.locusPersistence
  }

  /**
   * Get a full snapshot of the Corpus state for an external agent.
   */
  getExternalSnapshot(): ExternalCorpusSnapshot {
    const assessments = Array.from(this.state.branchAssessments.values()).map((ba) => ({
      helixId: ba.helixId,
      status: ba.status,
      rollingScore: ba.rollingScore,
      dominantPattern: typeof ba.dominantPattern === 'string' ? ba.dominantPattern : String(ba.dominantPattern),
      avgGoalAlignment: ba.avgGoalAlignment,
      avgNovelty: ba.avgNovelty,
      avgProgress: ba.avgProgress,
      escalationLevel: ba.escalationLevel,
      ignoredDirectiveStreak: ba.ignoredDirectiveStreak,
      budgetConsumedSteps: ba.budget?.consumedSteps,
      budgetMaxSteps: ba.budget?.maxSteps,
    }))

    return {
      tree: this.tree.getSnapshot(),
      branchAssessments: assessments,
      crossPatterns: [...this.state.crossPatterns],
      pendingSpawnRequests: this.externalProtocol.getPendingSpawnRequests(),
      recentInterventions: [...this.state.interventions.slice(-10)],
      sweepCount: this.state.sweepCount,
      goal: this.deps.goal,
      locusSnapshot: this.locus.enabled ? this.locus.getSnapshot() : undefined,
    }
  }

  /**
   * Allow an external agent to assume the Corpus role.
   */
  assume(agentId: string, heartbeatTimeoutMs?: number): { assumed: boolean; snapshot: ExternalCorpusSnapshot | null; error?: string } {
    return this.externalProtocol.assume(agentId, heartbeatTimeoutMs)
  }

  /**
   * Release the Corpus role back to the internal LLM loop.
   */
  release(reason?: string): { released: boolean; error?: string } {
    return this.externalProtocol.release(reason)
  }

  /**
   * External agent sends a directive to a branch.
   */
  externalDirective(directive: Omit<CorpusDirective, 'timestamp'>): { sent: boolean; error?: string } {
    return this.externalProtocol.sendDirective(directive)
  }

  /**
   * External agent decides on a pending spawn request.
   */
  externalSpawnDecide(requestId: string, approved: boolean, reason: string, modifiedGoal?: string): { decided: boolean; error?: string } {
    return this.externalProtocol.decideSpawn(requestId, approved, reason, modifiedGoal)
  }

  /**
   * External agent posts a synthesis visible to all branches.
   */
  externalSynthesis(content: string, priority?: number, tags?: string[]): { posted: boolean; error?: string } {
    return this.externalProtocol.postSynthesis(content, priority, tags)
  }

  // Internal helpers for ExternalCorpusProtocol callbacks

  /** Internal helper for ExternalCorpusProtocol callback */
  private getExternalSnapshotInternal(): ExternalCorpusSnapshot {
    return this.getExternalSnapshot()
  }

  /** Internal helper for ExternalCorpusProtocol callback */
  private sendDirectiveInternal(directive: CorpusDirective): void {
    this.sendDirective(directive)
  }

  /**
   * Register a child Brainstem for directive delivery
   */
  registerBrainstem(helixId: string, brainstem: MinimalBrainstem): void {
    this.childBrainstems.set(helixId, brainstem)
    // Initialize budget for this branch
    this.initializeBudget(helixId)
    this.logger.debug('Brainstem registered', { helixId })
  }

  /**
   * Receive an escalation from a Brainstem whose self-organization
   * could not resolve an issue. This queues the escalation for the
   * next Corpus analysis cycle.
   */
  receiveEscalation(reason: string, context: Record<string, unknown>): void {
    this.escalationQueue.push({ reason, context })
    this.logger.info('Escalation received from Brainstem', {
      reason: reason.slice(0, 100),
      queueLength: this.escalationQueue.length,
    })
  }

  /**
   * Evaluate a spawn request via LLM (or queue for external agent)
   */
  async evaluateSpawnRequest(request: SpawnRequest): Promise<SpawnDecision> {
    if (this.externalProtocol.isAssumed()) {
      this.externalProtocol.queueSpawnRequest({
        requestId: request.requestId,
        requestingHelixId: request.requestingHelixId,
        goal: request.goal,
        context: request.context,
        template: request.template,
        targetDepth: request.targetDepth,
      })
      return {
        requestId: request.requestId,
        requestingHelixId: request.requestingHelixId,
        goal: request.goal,
        approved: false,
        reason: 'Queued for external Corpus decision',
        evaluatedAt: Date.now(),
      }
    }

    const preDecision = await this.preEvaluateSpawn(request)
    if (preDecision) {
      this.state.spawnDecisions.push(preDecision)
      this.emitEvent('corpus:spawn-decision', {
        requestId: request.requestId,
        approved: preDecision.approved,
        reason: preDecision.reason,
      })
      return preDecision
    }

    const decision = await this.runSpawnEvaluation(request)
    this.state.spawnDecisions.push(decision)
    this.emitEvent('corpus:spawn-decision', {
      requestId: request.requestId,
      approved: decision.approved,
      reason: decision.reason,
    })
    return decision
  }

  private async preEvaluateSpawn(request: SpawnRequest): Promise<SpawnDecision | null> {
    const mf = this.deps.mnemicField
    if (!mf) return null

    const combined = `Goal: ${request.goal}\nContext: ${request.context ?? ''}`
    const result = await mf.classifyPhrase(combined, SPAWN_EVALUATION_PHRASES).catch(() => null)
    if (!result || !result.label || result.score < 0.45) return null

    if (result.label === 'duplicate_work' && result.score > 0.55) {
      return {
        requestId: request.requestId,
        requestingHelixId: request.requestingHelixId,
        goal: request.goal,
        approved: false,
        reason: `duplicate_work (score=${result.score.toFixed(2)})`,
        evaluatedAt: Date.now(),
      }
    }
    if (result.label === 'out_of_scope' && result.score > 0.50) {
      return {
        requestId: request.requestId,
        requestingHelixId: request.requestingHelixId,
        goal: request.goal,
        approved: false,
        reason: `out_of_scope (score=${result.score.toFixed(2)})`,
        evaluatedAt: Date.now(),
      }
    }
    if (result.label === 'natural_subtask' && result.score > 0.45 && request.targetDepth <= 1) {
      return {
        requestId: request.requestId,
        requestingHelixId: request.requestingHelixId,
        goal: request.goal,
        approved: true,
        reason: `natural_subtask_auto (score=${result.score.toFixed(2)})`,
        evaluatedAt: Date.now(),
      }
    }
    if (result.label === 'high_dependency' && result.score > 0.50) {
      return {
        requestId: request.requestId,
        requestingHelixId: request.requestingHelixId,
        goal: request.goal,
        approved: true,
        reason: `critical_path (score=${result.score.toFixed(2)})`,
        evaluatedAt: Date.now(),
      }
    }

    return null
  }

  async preCheckDirectiveQuality(content: string, targetHelixId: string): Promise<void> {
    const mf = this.deps.mnemicField
    if (!mf) return

    const result = await mf.classifyPhrase(content, DIRECTIVE_QUALITY_PHRASES).catch(() => null)
    if (!result || !result.label || result.score < 0.50) return

    if (result.label === 'vague') {
      this.logger.warn('vague Corpus directive', { targetHelixId, score: result.score.toFixed(2) })
    }
    if (result.label === 'contradictory') {
      this.logger.warn('contradictory Corpus directive', { targetHelixId, score: result.score.toFixed(2) })
    }
  }

  /**
   * Get Corpus result for final ConstellationResult
   */
  getResult(): CorpusResult {
    const assessments = Array.from(this.state.branchAssessments.values()).map((ba) => ({
      helixId: ba.helixId,
      status: ba.status,
      rollingScore: ba.rollingScore,
      dominantPattern: ba.dominantPattern,
      avgGoalAlignment: ba.avgGoalAlignment,
      avgNovelty: ba.avgNovelty,
      avgProgress: ba.avgProgress,
      escalationLevel: ba.escalationLevel,
      ignoredDirectiveStreak: ba.ignoredDirectiveStreak,
      budgetConsumedSteps: ba.budget?.consumedSteps,
      budgetMaxSteps: ba.budget?.maxSteps,
    }))

    return {
      tree: this.tree.getSnapshot(),
      branchAssessments: assessments,
      crossPatterns: [...this.state.crossPatterns],
      interventions: [...this.state.interventions],
      spawnDecisions: [...this.state.spawnDecisions],
      reDecompositions: [...this.reDecompositions],
      qualityGateResults: Array.from(this.qualityGateResults.entries()).map(([helixId, result]) => ({ helixId, result })),
      discoveryCount: this.discoveries.size,
      directInjections: [...this.directInjections],
      researchDigests: [...this.researchDigests],
      parallelSplits: [...this.parallelSplits],
      contextInjections: [...this.contextInjections],
      sweepCount: this.state.sweepCount,
      llmHealthy: this.isLLMHealthy(),
      llmHealthState: this.llmHealthState,
      llmConsecFailures: this.llmConsecFailures,
      durationMs: this.startTime > 0 ? Date.now() - this.startTime : 0,
      locusSnapshot: this.locus.enabled ? this.locus.getSnapshot() : undefined,
    }
  }

  /**
   * Check if Corpus LLM is healthy (able to make strategic decisions)
   */
  isLLMHealthy(): boolean {
    return this.llmHealthState !== 'rule_based'
  }

  getLLMHealthStatus(): LLMHealthStatus {
    return {
      state: this.llmHealthState,
      consecutiveFailures: this.llmConsecFailures,
      nextProbeAt: this.llmNextProbeAt > 0 ? this.llmNextProbeAt : null,
      recoverySweepsLeft: this.llmRecoverySweepsLeft,
      hasFallback: !!this.deps.fallbackLLM,
    }
  }

  private getEffectiveLLMHealthConfig(): LLMHealthConfig {
    return { ...DEFAULT_LLM_HEALTH_CONFIG, ...this.config.llmHealth }
  }

  private getActiveLLM() {
    if (this.llmHealthState === 'fallback' && this.deps.fallbackLLM) {
      return this.deps.fallbackLLM
    }
    return this.deps.llm
  }

  /**
   * Get a progress snapshot for periodic persistence checkpoints
   */
  getProgressSnapshot(): { markdown: string; data: { activeBranches: number; totalBranches: number; completedBranches: number; failedBranches: number; sweepCount: number; lastSweepAt: number } } {
    const branches = this.tree.getAllBranches()
    const activeBranches = branches.filter((b) => b.status === 'active').length
    const completedBranches = branches.filter((b) => b.status === 'completed').length
    const failedBranches = branches.filter((b) => b.status === 'failed').length

    const branchLines = branches.map((b) => {
      const assessment = this.state.branchAssessments.get(b.helixId)
      const score = assessment?.rollingScore.toFixed(2) ?? 'N/A'
      return `- **${b.helixId}**: ${b.status} | score=${score} | steps=${b.steps.length}`
    }).join('\n')

    const markdown = [
      `## Constellation Progress`,
      `Sweep #${this.state.sweepCount} | ${branches.length} branches (${activeBranches} active, ${completedBranches} done, ${failedBranches} failed)`,
      ``,
      branchLines,
    ].join('\n')

    return {
      markdown,
      data: {
        activeBranches,
        totalBranches: branches.length,
        completedBranches,
        failedBranches,
        sweepCount: this.state.sweepCount,
        lastSweepAt: this.state.lastSweepAt,
      },
    }
  }

  /**
   * Main async loop
   */
  private async runLoop(): Promise<void> {
    while (!this.shutdownRequested) {
      try {
        // Count pending steps
        const pending = this.tree.pendingStepCount(this.state.cursors)

        if (pending === 0) {
          // Idle poll with adaptive interval (Recommendation E)
          const pollInterval = this.computeAdaptivePollInterval()
          await this.interruptibleSleep(pollInterval)
          if (this.shutdownRequested) continue
          continue
        }

        const isMeditation = !!this.deps.meditationMode

        // In meditation, only advance cursors (no scoring/assessment).
        // In normal mode, process steps with full assessment pipeline.
        if (isMeditation) {
          this.advanceCursors()
        } else {
          this.processNewSteps()
        }

        // Governance machinery — skip entirely in meditation
        let newPatterns: CrossHelixPattern[] = []
        let lastLocusSweep: LocusSweepResult | undefined

        if (!isMeditation) {
          // WHY: Split governance into Brainstem-specific (gated) and
          // observer-compatible (always runs). The analysis, pattern detection,
          // and cross-Helix mediation produce directives that now flow through
          // sendDirective() → ObserverBranchState → GlobalWorkspace → LLM.
          // Previously the entire block was gated by !observerCoordination,
          // meaning no cross-Helix intelligence ever ran in normal mode.
          // (c-36 fix — observers working)

          if (!this.deps.observerCoordination) {
            // Brainstem-specific governance — only when Brainstem is active
            this.trackBudgets()

            if (this.config.proactive.enableDiscoveryRouting) {
              this.routeDiscoveries()
            }

            await this.evaluateAllEscalations()
            await this.checkStuckBranchesForReDecomposition()

            if (this.config.proactive.enableReDecomposition && this.llmHealthState !== 'rule_based') {
              await this.evaluateReDecomposition()
            }

            if (this.config.proactive.enableParallelAcceleration && this.llmHealthState !== 'rule_based') {
              await this.evaluateParallelAcceleration()
            }

            if (this.config.proactive.enableContextInjection) {
              await this.evaluateContextInjection()
            }

            if (this.config.proactive.enableQualityGates) {
              await this.runQualityGates()
            }

            if (this.config.proactive.enableResearchCaching) {
              this.buildResearchDigests()
            }
          }

          // Cross-Helix intelligence — runs in ALL non-meditation modes
          newPatterns = this.patternDetector.detect()

          // During recovery window, only run analysis for critical patterns (gradual re-engagement).
          const hasCriticalPattern = newPatterns.some(p => p.severity === 'critical')
          const inRecovery = this.llmRecoverySweepsLeft > 0
          if (inRecovery) this.llmRecoverySweepsLeft--

          // WHY: Skip Corpus LLM analysis when CorpusObserverLayer is active.
          // The observer has superior input data (SynapseRollingSlice vs BranchDigest)
          // and already performs cross-Helix analysis every 12s. Running both is
          // redundant and costs 2x LLM calls. The Corpus still handles governance
          // via pattern detection + fallback directives. (observer consolidation)
          const observerHandlesAnalysis = !!this.deps.corpusObserverActive
          const shouldAnalyze = !observerHandlesAnalysis &&
            (newPatterns.length > 0 || this.shouldRunLLMAnalysis())
          const analysisGated = inRecovery && !hasCriticalPattern

          if (shouldAnalyze && !analysisGated) {
            if (this.llmHealthState !== 'rule_based') {
              await this.runLLMAnalysis(newPatterns)
            } else {
              this.sendFallbackDirectives(newPatterns)
            }
          }

          // Probe primary LLM health on every sweep when degraded (backoff enforced inside probeLLMHealth)
          if (this.llmHealthState !== 'primary' || this.llmRecoverySweepsLeft > 0) {
            await this.probeLLMHealth()
          }

          if (newPatterns.length > 0) {
            this.actOnTopologyPatterns(newPatterns)
          }

          this.checkAutoSpawn()
          this.mediateCrossHelixDialectic()
          this.checkInterventionEffectiveness()
        }

        // Locus sweep — runs in both modes (meditation spatial memory)
        if (this.locus.enabled) {
          const allDigests = this.tree.getAllDigests()
          const activeHelixIds = this.tree.getAllBranches()
            .filter(b => b.status === 'active')
            .map(b => b.helixId)

          // WHY: Provide guidance injection in observer mode via sendDirective
          // (which now routes to ObserverBranchState + GlobalWorkspace).
          // Previously undefined in observer mode, so Locus findings never reached branches.
          // (c-36 fix)
          const locusGuidance: typeof this.deps.injectGuidance = this.deps.observerCoordination
            ? (helixId, content, urgency) => {
                this.sendDirective({
                  targetHelixId: helixId,
                  type: 'context-inject',
                  urgency,
                  text: content,
                  reason: 'locus-guidance',
                  timestamp: Date.now(),
                })
              }
            : this.deps.injectGuidance
          lastLocusSweep = this.locus.sweep(allDigests, activeHelixIds, {
            crossPatterns: newPatterns,
            topology: this.deps.topology ?? undefined,
            assessments: this.state.branchAssessments,
            injectGuidance: isMeditation ? undefined : locusGuidance,
          })

          if (lastLocusSweep.sparksExtracted > 0 || lastLocusSweep.kindlingEvents.length > 0) {
            this.locusSweepResults.push(lastLocusSweep)
          }
        }

        // Checkpoint — runs in both modes
        if (Date.now() - this.lastCheckpointAt > Corpus.CHECKPOINT_INTERVAL_MS) {
          try {
            const snapshot = this.tree.getSnapshot()
            this.deps.store?.saveTreeCheckpoint(this.deps.constellationId, snapshot)
            this.emitEvent('corpus:checkpoint', {
              branches: snapshot.branches.length,
              interventions: this.state.interventions.length,
              spawnDecisions: this.state.spawnDecisions.length,
              sweepCount: this.state.sweepCount,
            })
          } catch (err) {
            this.logger.warn('Failed to save tree checkpoint', { error: String(err) })
          }
          this.lastCheckpointAt = Date.now()
        }

        // Training signals — runs in both modes
        this.recordSweepTrainingSignals(newPatterns, lastLocusSweep)

        // Update sweep stats
        this.state.sweepCount++
        this.state.lastSweepAt = Date.now()

        // Emit sweep event
        this.emitEvent('corpus:sweep', {
          branches: this.tree.activeBranchCount(),
          patterns: this.state.crossPatterns.length,
          sweepCount: this.state.sweepCount,
        })
        
        // Reset failure counter on successful sweep (Recommendation E)
        this.consecutiveFailures = 0
      } catch (error) {
        this.logger.error('Error in Corpus loop', {
          error: error instanceof Error ? error.message : String(error),
        })
        // Continue loop despite errors - use adaptive interval (Recommendation E)
        this.consecutiveFailures++
        const pollInterval = this.computeAdaptivePollInterval()
        await this.interruptibleSleep(pollInterval)
      }
    }
  }

  /**
   * Process new steps from all branches
   */
  private processNewSteps(): void {
    const branches = this.tree.getAllBranches()

    for (const branch of branches) {
      const cursor = this.state.cursors.get(branch.helixId) ?? 0
      const newSteps = branch.steps.slice(cursor)

      if (newSteps.length === 0) {
        continue
      }

      // Get or create branch assessment
      let assessment = this.state.branchAssessments.get(branch.helixId)
      if (!assessment) {
        assessment = this.createInitialBranchAssessment(branch.helixId)
        this.state.branchAssessments.set(branch.helixId, assessment)
      }

      // Update assessment with new steps
      this.updateBranchAssessment(assessment, newSteps, branch)

      // Advance cursor
      this.state.cursors.set(branch.helixId, cursor + newSteps.length)
      this.newStepsSinceLLM += newSteps.length
      
      // Track annotation timestamps for adaptive cadence (Recommendation E)
      for (const step of newSteps) {
        this.state.annotationTimestamps.push(step.pushedAt)
      }
      // Keep only last 5 minutes of timestamps to avoid memory growth
      const fiveMinutesAgo = Date.now() - 5 * 60_000
      this.state.annotationTimestamps = this.state.annotationTimestamps.filter(t => t > fiveMinutesAgo)
    }
  }

  /**
   * Advance cursors without scoring — meditation mode only.
   * Tracks where each thread is without computing assessments.
   */
  private advanceCursors(): void {
    const branches = this.tree.getAllBranches()
    for (const branch of branches) {
      const cursor = this.state.cursors.get(branch.helixId) ?? 0
      const newSteps = branch.steps.slice(cursor)
      if (newSteps.length === 0) continue
      this.state.cursors.set(branch.helixId, cursor + newSteps.length)
      this.newStepsSinceLLM += newSteps.length
      for (const step of newSteps) {
        this.state.annotationTimestamps.push(step.pushedAt)
      }
    }
    const fiveMinutesAgo = Date.now() - 5 * 60_000
    this.state.annotationTimestamps = this.state.annotationTimestamps.filter(t => t > fiveMinutesAgo)
  }

  /**
   * Create initial branch assessment
   */
  private createInitialBranchAssessment(helixId: string): BranchAssessment {
    return {
      helixId,
      status: 'active',
      rollingScore: 0.5,
      scoreTrajectory: [],
      dominantPattern: 'none',
      filesModified: new Set(),
      decliningScoreStreak: 0,
      lastActivityAt: Date.now(),
      avgGoalAlignment: 0.5,
      avgNovelty: 0.5,
      avgProgress: 0.3,
      directiveHistory: [],
      escalationLevel: 0,
      ignoredDirectiveStreak: 0,
      lowProgressStreak: 0,
      discoveries: [],
      contextInjectionsReceived: 0,
      researchDigestBuilt: false,
    }
  }

  /**
   * Update branch assessment with new steps
   */
  private updateBranchAssessment(
    assessment: BranchAssessment,
    newSteps: CorpusStep[],
    branch: CorpusBranch
  ): void {
    // Add new scores to trajectory
    for (const step of newSteps) {
      assessment.scoreTrajectory.push(step.annotation.score)
    }

    // Compute rolling score (average of last 5)
    const recentScores = assessment.scoreTrajectory.slice(-5)
    assessment.rollingScore =
      recentScores.reduce((a, b) => a + b, 0) / recentScores.length

    // Track dominant pattern (most frequent in last 5)
    const recentAnnotations = newSteps.slice(-5).map((s) => s.annotation.annotation)
    const patternCounts = new Map<WorkUnitAnnotation | 'none', number>()
    for (const ann of recentAnnotations) {
      patternCounts.set(ann, (patternCounts.get(ann) ?? 0) + 1)
    }
    let maxCount = 0
    let dominant: WorkUnitAnnotation | 'none' = 'none'
    for (const [pattern, count] of patternCounts.entries()) {
      if (count > maxCount) {
        maxCount = count
        dominant = pattern
      }
    }
    assessment.dominantPattern = dominant

    // Track files modified (extract actual file paths from tool calls)
    for (const step of newSteps) {
      if (step.toolCalls) {
        for (const tc of step.toolCalls) {
          // Match file-modifying tool operations
          if (/write|edit|cassi_write|cassi_edit|cassi_file|write_file|replace_content|replace_symbol|insert_after|insert_before/.test(tc.name)) {
            try {
              const args = typeof tc.args === 'string' ? JSON.parse(tc.args) : tc.args
              const filePath = args?.path ?? args?.filePath ?? args?.relative_path
              if (filePath && typeof filePath === 'string') {
                assessment.filesModified.add(filePath)
              }
            } catch {
              // Args parsing failed — skip this tool call
            }
          }
        }
      }
    }

    // Track declining score streak
    const trajectory = assessment.scoreTrajectory
    let decliningStreak = 0
    for (let i = trajectory.length - 1; i > 0; i--) {
      if (trajectory[i] < trajectory[i - 1]) {
        decliningStreak++
      } else {
        break
      }
    }
    assessment.decliningScoreStreak = decliningStreak

    const recentSteps = branch.steps.slice(-5)
    if (recentSteps.length > 0) {
      assessment.avgGoalAlignment = recentSteps.reduce((s, st) => s + (st.annotation.goalAlignment ?? 0.5), 0) / recentSteps.length
      assessment.avgNovelty = recentSteps.reduce((s, st) => s + (st.annotation.novelty ?? 0.5), 0) / recentSteps.length
      assessment.avgProgress = recentSteps.reduce((s, st) => s + (st.annotation.progress ?? 0.3), 0) / recentSteps.length
    }

    // Count consecutive steps where progress is below the escalation threshold.
    // Uses the template's threshold, falling back to 0.12 (standard default).
    const thresholds = this.getEscalationThresholds(branch.helixId)
    const latestAnnotation = newSteps[newSteps.length - 1]?.annotation
    if (latestAnnotation && (latestAnnotation.progress ?? 0.3) < thresholds.minProgressThreshold) {
      assessment.lowProgressStreak++
    } else {
      assessment.lowProgressStreak = 0
    }

    // For each pending directive, check if the last 3 post-directive
    // annotations show a behavioral change.
    this.evaluatePendingDirectives(assessment, branch)

    // Update status
    assessment.status = this.determineBranchHealthStatus(assessment, branch)
    assessment.lastActivityAt = Date.now()
  }

  /**
   * Determine branch health status based on assessment
   */
  private determineBranchHealthStatus(
    assessment: BranchAssessment,
    branch: CorpusBranch
  ): BranchHealthStatus {
    // Check branch lifecycle status first
    if (branch.status === 'completed') return 'completed'
    if (branch.status === 'failed') return 'failed'
    if (branch.status === 'cancelled') return 'completed'

    // Check for struggling
    if (assessment.rollingScore < this.config.strugglingScoreThreshold) {
      return 'struggling'
    }

    // Check for declining streak
    if (assessment.decliningScoreStreak >= this.config.decliningScoreThreshold) {
      return 'struggling'
    }

    // Check for drift
    if (assessment.dominantPattern === 'drift') {
      return 'drifting'
    }

    return 'productive'
  }

  /**
   * Check if we should run LLM analysis
   */
  private shouldRunLLMAnalysis(): boolean {
    // WHY: When an external agent holds the Corpus role, the internal LLM
    // should not run analysis — the external agent makes strategic decisions.
    if (this.externalProtocol.isAssumed()) {
      return false
    }

    // WHY: When CorpusObserverLayer is active, it handles cross-Helix LLM analysis
    // with superior input data (SynapseRollingSlice vs BranchDigest). Skip the
    // Corpus's own LLM analysis to avoid redundant calls. (observer consolidation)
    if (this.deps.corpusObserverActive) {
      return false
    }

    // WHY: When the CorpusMiniHelix is running, it handles strategic LLM
    // analysis via a proper tool-calling Helix session. The old Corpus LLM
    // loop would duplicate that work and fall back to legacy parsing.
    if (this.deps.miniHelixActive) {
      return false
    }

    // In active mode: same as before — trigger after enough new steps
    if (this.config.cadence === 'active') {
      return this.newStepsSinceLLM >= this.config.llmAnalysisThreshold
    }

    // In safety-net mode: only trigger on pathological conditions
    const sweepsSinceLast = this.state.sweepCount - this.lastAnalysisSweep

    // Respect minimum sweep spacing
    if (sweepsSinceLast < this.config.safetyNetMinSweepsBetweenAnalysis) {
      return false
    }

    // Trigger on escalation from Brainstems
    if (this.escalationQueue.length > 0) {
      return true
    }

    // Trigger on cascade failure pattern (critical severity)
    const criticalPatterns = this.state.crossPatterns.filter(
      (p) => p.severity === 'critical' && !p.actedUpon
    )
    if (criticalPatterns.length > 0) {
      return true
    }

    // Trigger on stuck branches that persist despite self-organization
    // (branch with health 'stuck' or 'struggling' for > 5 declining score steps)
    for (const [, assessment] of this.state.branchAssessments) {
      if (
        (assessment.status === 'stuck' || assessment.status === 'struggling') &&
        assessment.decliningScoreStreak >= 5
      ) {
        return true
      }
    }

    // Trigger on unresolved topic tensions that have persisted
    const allTopics = this.tree.getAllTopics()
    const persistentTensions = allTopics.filter(
      (t) => t.tensionFlag && (Date.now() - t.lastContributionAt) > 30_000
    )
    if (persistentTensions.length > 0) {
      return true
    }

    // In safety-net mode, don't trigger for routine step accumulation
    return false
  }

  /**
   * Compute adaptive poll interval based on load factors.
   * (Recommendation E: Implement Adaptive Cadence)
   */
  private computeAdaptivePollInterval(): number {
    const config = this.config.adaptiveCadence
    const branches = this.tree.getAllBranches()
    const activeBranches = branches.filter(b => b.status === 'active').length

    // Compute annotation rate (annotations per second over last minute)
    const oneMinuteAgo = Date.now() - 60_000
    const recentAnnotations = this.state.annotationTimestamps.filter(t => t > oneMinuteAgo)
    const annotationRate = recentAnnotations.length / 60  // per second (60s window)

    const escalationQueueLength = this.escalationQueue.length

    // Start with idlePollMs as base (allows tests to override via config)
    let pollMs = this.config.idlePollMs

    // Adjust for branch count
    if (activeBranches > config.branchThreshold) {
      const factor = activeBranches / config.branchThreshold
      pollMs = Math.max(config.minPollMs, pollMs / factor)
    }

    // Adjust for annotation rate
    if (annotationRate > config.annotationRateThreshold) {
      const factor = annotationRate / config.annotationRateThreshold
      pollMs = Math.max(config.minPollMs, pollMs / factor)
    }

    // Adjust for escalation queue
    if (escalationQueueLength > config.escalationThreshold) {
      const factor = escalationQueueLength / config.escalationThreshold
      pollMs = Math.max(config.minPollMs, pollMs / factor)
    }

    // Adjust for LLM failures
    if (this.consecutiveFailures > config.failureThreshold) {
      const factor = this.consecutiveFailures / config.failureThreshold
      pollMs = Math.min(config.maxPollMs, pollMs * factor)
    }

    // Clamp to min/max
    return Math.max(
      config.minPollMs,
      Math.min(config.maxPollMs, pollMs)
    )
  }

  /**
   * Check if any branch should be auto-spawned due to repeated intervention failure.
   *
   * Heuristic: if a branch has received >= autoSpawnInterventionThreshold interventions
   * AND its rollingScore is still below the struggling threshold, the current approach
   * (steering) has failed. Decompose the goal into a sub-Helix instead.
   *
   * We only auto-spawn once per branch to avoid spawn storms.
   */
  private checkAutoSpawn(): void {
    if (!this.deps.onSpawnRequest) return

    const minInterventions = this.config.autoSpawnInterventionThreshold ?? 5
    const branches = this.tree.getAllBranches()

    for (const branch of branches) {
      if (branch.status !== 'active') continue

      const assessment = this.state.branchAssessments.get(branch.helixId)
      if (!assessment) continue

      // Count interventions targeting this branch
      const branchInterventions = this.state.interventions.filter(
        (i) => i.targetHelixId === branch.helixId
      ).length

      // Only auto-spawn if: enough interventions, still struggling, hasn't already auto-spawned
      if (
        branchInterventions >= minInterventions &&
        assessment.rollingScore < this.config.strugglingScoreThreshold &&
        !assessment.autoSpawnTriggered
      ) {
        assessment.autoSpawnTriggered = true

        const spawnGoal = `Focused sub-task: break through the stalling on "${branch.goal.slice(0, 120)}". ` +
          `The parent branch has received ${branchInterventions} interventions without improvement ` +
          `(rollingScore=${assessment.rollingScore.toFixed(2)}). ` +
          `Take a different approach — prioritize concrete implementation over continued exploration.`

        this.deps.onSpawnRequest({
          requestingHelixId: branch.helixId,
          goal: spawnGoal,
          context: `Auto-spawn triggered: ${branchInterventions} interventions, rollingScore=${assessment.rollingScore.toFixed(2)}`,
        })

        try {
          this.deps.store?.recordCorpusDecision(this.deps.constellationId, {
            decisionType: 'spawn',
            helixId: branch.helixId,
            inputData: {
              reason: 'auto-spawn',
              interventions: branchInterventions,
              rollingScore: assessment.rollingScore,
              parentGoal: branch.goal,
            },
            outputData: {
              childGoal: spawnGoal,
            },
            confidence: 0.7,
          })
        } catch (err) {
          this.logger.warn('Failed to record auto-spawn decision', { error: String(err) })
        }

        this.logger.info('Auto-spawn triggered for struggling branch', {
          helixId: branch.helixId,
          interventions: branchInterventions,
          rollingScore: assessment.rollingScore.toFixed(2),
        })

        this.emitEvent('corpus:auto-spawn', {
          helixId: branch.helixId,
          interventions: branchInterventions,
          rollingScore: assessment.rollingScore,
        })
      }
    }
  }

  /**
   * Mediate cross-Helix dialectic tensions.
   * The Corpus acts as the Executive in the cross-branch dialectic —
   * reviewing tensions and injecting steering to resolve them.
   */
  private mediateCrossHelixDialectic(): void {
    const dialectic = this.deps.crossHelixDialectic
    if (!dialectic || !dialectic.shouldMediate()) return

    const snapshot = dialectic.getSnapshot()
    const unresolved = snapshot.unresolvedTensions.filter((t) => !t.escalatedToCorpus)

    if (unresolved.length > 0) {
      // Mediate the most recent tension
      const tension = unresolved[0]
      const mediationText =
        `MEDIATING CROSS-BRANCH TENSION: ` +
        `Branch "${tension.positionA.branchId}" asserts: "${tension.positionA.text.slice(0, 100)}". ` +
        `Branch "${tension.positionB.branchId}" counters: "${tension.positionB.text.slice(0, 100)}". ` +
        `Consider both perspectives and look for the synthesis — what would reconcile these positions?`

      dialectic.injectCorpusMediation(mediationText, 'all')
      tension.escalatedToCorpus = true

      this.logger.info('Corpus mediated cross-branch tension', {
        branchA: tension.positionA.branchId,
        branchB: tension.positionB.branchId,
      })
    } else if (snapshot.convergencePoints.length > 0) {
      // Reinforce convergence
      const latest = snapshot.convergencePoints[snapshot.convergencePoints.length - 1]
      dialectic.injectCorpusMediation(
        `CONVERGENCE REINFORCED: Branches ${latest.participants.join(' and ')} have converged on: ` +
        `"${latest.topic.slice(0, 120)}". Build on this agreement.`,
        'all',
      )
    }
  }

  /**
   * Run LLM analysis for strategic assessment
   */
  private async runLLMAnalysis(newPatterns: CrossHelixPattern[]): Promise<void> {
    // Track when this analysis ran (for safety-net cadence)
    this.lastAnalysisSweep = this.state.sweepCount

    if (this.config.useToolBasedAnalysis) {
      await this.runToolBasedAnalysis(newPatterns)
    } else {
      await this.runLegacyLLMAnalysis(newPatterns)
    }
  }

  /**
   * Tool-based analysis — the Corpus LLM calls structured tools
   * instead of generating freeform text that gets regex-parsed.
   *
   * The LLM receives a system prompt with the constellation's state,
   * then iterates through tool calls until it calls signal_done.
   */
  private async runToolBasedAnalysis(newPatterns: CrossHelixPattern[]): Promise<void> {
    try {
      const systemPrompt = buildCorpusSystemPrompt(
        this.deps.goal,
        this.state,
        this.tree,
        newPatterns,
        undefined,
        this.deps.meditationMode,
        this.deps.meditationStyle,
        this.getSignalPatternDigest(),
      )

      // Include escalation context if any
      let userMessage = 'Analyze the current constellation state.'
      if (this.escalationQueue.length > 0) {
        userMessage += '\n\nESCALATION FROM BRAINSTEMS (self-organization could not resolve):\n'
        for (const esc of this.escalationQueue) {
          userMessage += `- ${esc.reason}\n`
        }
        this.escalationQueue = [] // Clear after including
      }

      const toolDefs = this.deps.meditationMode
        ? getMeditationToolSet(this.deps.meditationStyle ?? 'passive')
        : getCorpusToolDefinitions()

      const ctx: CorpusToolContext = {
        tree: this.tree,
        state: this.state,
        deps: this.deps,
        config: this.config,
        logger: this.logger,
        crossHelixDialectic: this.deps.crossHelixDialectic as any,
        sendDirective: (directive) => this.sendDirective(directive),
        requestSpawn: (request) => this.deps.onSpawnRequest?.(request),
      }

      // Build conversation with tool definitions
      const fullPrompt =
        `${systemPrompt}\n\n` +
        `Available tools:\n${toolDefs.map((t) => `- ${t.name}: ${t.description}`).join('\n')}\n\n` +
        `${userMessage}\n\n` +
        `Call the tools you need, then call signal_done when your analysis is complete.`

      // Single LLM call with tool context
      // For now, we use the existing LLM.complete() interface but parse tool calls
      // from the response. When the mini-Helix migration happens, this becomes
      // a proper tool-calling loop.
      const response = await this.getActiveLLM().complete({
        prompt: fullPrompt,
        modelTier: this.config.modelTier,
        maxTokens: this.config.maxTokens,
        timeoutMs: this.config.timeoutMs,
      })

      // Parse tool calls from the response
      // The LLM should respond with JSON tool calls in a structured format
      const toolCalls = this.parseToolCallsFromResponse(response.content)

      let callCount = 0
      for (const call of toolCalls) {
        if (callCount >= this.config.maxToolCallsPerCycle) {
          this.logger.warn('Max tool calls per cycle reached', {
            max: this.config.maxToolCallsPerCycle,
            callCount,
          })
          break
        }

        const result = await executeCorpusTool(call.name, call.args, ctx)
        callCount++

        if (result.done) {
          this.logger.info('Corpus analysis cycle complete', {
            summary: result.content.slice(0, 100),
            nextCheck: result.nextCheckRecommendation,
            toolCallCount: callCount,
          })
          break
        }
      }

      this.newStepsSinceLLM = 0
      this.llmConsecFailures = 0
    } catch (error) {
      this.handleLLMFailure(error)
    }
  }

  /**
   * Parse tool calls from LLM response text.
   * Supports JSON-formatted tool calls in the response.
   */
  private parseToolCallsFromResponse(content: string): Array<{ name: string; args: Record<string, unknown> }> {
    const calls: Array<{ name: string; args: Record<string, unknown> }> = []

    // Try to find JSON tool call blocks in the response
    // Format: {"tool": "name", "args": {...}}
    const toolCallRegex = /\{[^{}]*"tool"\s*:\s*"([^"]+)"[^{}]*"args"\s*:\s*(\{[^}]*\})[^{}]*\}/g
    let match

    while ((match = toolCallRegex.exec(content)) !== null) {
      try {
        const name = match[1]
        const args = JSON.parse(match[2])
        calls.push({ name, args })
      } catch {
        // Skip unparseable tool calls
        continue
      }
    }

    // If no structured tool calls found, try to interpret as a signal_done
    // (backward compat with LLMs that don't structure their response)
    if (calls.length === 0) {
      // Fall back to legacy parsing
      this.parseAndApplyLLMResponse(content)
      calls.push({ name: 'signal_done', args: { summary: 'Legacy analysis cycle' } })
    }

    return calls
  }

  /**
   * Legacy LLM analysis — the original prompt/parse approach.
   * Kept for backward compatibility when useToolBasedAnalysis is false.
   */
  private async runLegacyLLMAnalysis(newPatterns: CrossHelixPattern[]): Promise<void> {
    const prompt = this.buildLLMPrompt(newPatterns)

    try {
      const response = await this.getActiveLLM().complete({
        prompt,
        modelTier: this.config.modelTier,
        maxTokens: this.config.maxTokens,
        timeoutMs: this.config.timeoutMs,
      })

      this.parseAndApplyLLMResponse(response.content)
      this.newStepsSinceLLM = 0
      this.llmConsecFailures = 0
    } catch (error) {
      this.handleLLMFailure(error)
    }
  }

  /**
   * Common error handling for LLM failures.
   */
  private handleLLMFailure(error: unknown): void {
    this.llmConsecFailures++
    const errorMsg = error instanceof Error ? error.message : String(error)
    const cfg = this.getEffectiveLLMHealthConfig()

    this.logger.warn('Corpus LLM analysis failed', {
      error: errorMsg,
      consecutiveFailures: this.llmConsecFailures,
      threshold: cfg.failureThreshold,
      state: this.llmHealthState,
    })

    if (this.llmConsecFailures < cfg.failureThreshold) return

    // Compute exponential backoff with proportional jitter (max 20% of base interval).
    // Jitter scales with base so tests using probeBackoffBase: 0 get zero jitter.
    const rawBackoff = Math.min(
      cfg.probeBackoffBase * Math.pow(2, this.llmConsecFailures - cfg.failureThreshold),
      cfg.probeBackoffMax,
    )
    const jitter = rawBackoff * 0.2 * Math.random()
    this.llmNextProbeAt = Date.now() + rawBackoff + jitter

    if (this.llmHealthState === 'primary' && this.deps.fallbackLLM) {
      this.llmHealthState = 'fallback'
      this.llmConsecFailures = 0
      this.logger.error('Corpus LLM primary failed — escalating to fallback adapter', {
        error: errorMsg,
        nextProbeAt: new Date(this.llmNextProbeAt).toISOString(),
        sweepCount: this.state.sweepCount,
      })
      this.emitEvent('corpus:degraded', {
        reason: 'llm_failure_escalated_to_fallback',
        error: errorMsg,
        nextProbeAt: this.llmNextProbeAt,
      })
    } else {
      this.llmHealthState = 'rule_based'
      this.logger.error('Corpus LLM is unhealthy — running without strategic oversight', {
        error: errorMsg,
        consecutiveFailures: this.llmConsecFailures,
        hasFallback: !!this.deps.fallbackLLM,
        nextProbeAt: new Date(this.llmNextProbeAt).toISOString(),
        sweepCount: this.state.sweepCount,
      })
      this.emitEvent('corpus:unhealthy', {
        reason: 'llm_failure',
        error: errorMsg,
        consecutiveFailures: this.llmConsecFailures,
        nextProbeAt: this.llmNextProbeAt,
        message: 'Corpus LLM failed repeatedly. Constellation Helix branches are running without strategic planning, intervention, or spawn decisions.',
      })
    }
  }

  /**
   * Lightweight health probe — attempt a trivial LLM call to check if the
   * provider has recovered. If it succeeds, mark the Corpus healthy again so
   * strategic analysis resumes. If it fails, remain unhealthy (no penalty).
   */
  private async probeLLMHealth(): Promise<void> {
    if (this.llmHealthState === 'primary' && this.llmRecoverySweepsLeft === 0) return

    if (Date.now() < this.llmNextProbeAt) {
      this.logger.debug('Corpus LLM probe skipped (backoff active)', {
        nextProbeAt: new Date(this.llmNextProbeAt).toISOString(),
        state: this.llmHealthState,
      })
      return
    }

    // Always probe the primary — the goal is to recover to primary, not to confirm the fallback works.
    try {
      this.logger.info('Probing primary LLM health (recovery check)', {
        state: this.llmHealthState,
        sweepCount: this.state.sweepCount,
      })
      const result = await this.deps.llm.complete({
        prompt: 'Respond with the single word "ok".',
        modelTier: this.config.modelTier,
        maxTokens: 10,
        timeoutMs: 15_000,
      })

      const cfg = this.getEffectiveLLMHealthConfig()
      const prevState = this.llmHealthState
      this.llmHealthState = 'primary'
      this.llmConsecFailures = 0
      this.llmNextProbeAt = 0
      this.llmRecoverySweepsLeft = cfg.recoveryWindow

      this.logger.info('Corpus LLM primary recovered — entering recovery window', {
        response: result.content.slice(0, 50),
        recoveryWindow: cfg.recoveryWindow,
        previousState: prevState,
        sweepCount: this.state.sweepCount,
      })
      this.emitEvent('corpus:healthy', {
        reason: 'health_probe_succeeded',
        previousState: prevState,
        recoveryWindow: cfg.recoveryWindow,
      })
    } catch (err) {
      this.logger.debug('Corpus LLM primary probe failed (staying in current state)', {
        error: String(err),
        state: this.llmHealthState,
      })
      // Extend backoff on repeated probe failure without inflating consecutiveFailures
      const cfg = this.getEffectiveLLMHealthConfig()
      const current = this.llmNextProbeAt > 0 ? this.llmNextProbeAt - Date.now() : cfg.probeBackoffBase
      const extended = Math.min(current * 1.5, cfg.probeBackoffMax)
      const jitter = extended * 0.2 * Math.random()
      this.llmNextProbeAt = Date.now() + extended + jitter
    }
  }

  /**
   * Rule-based fallback directives when the Corpus LLM is unhealthy.
   * Addresses critical patterns without strategic LLM analysis.
   */
  private sendFallbackDirectives(newPatterns: CrossHelixPattern[]): void {
    for (const pattern of newPatterns) {
      if (pattern.actedUpon) continue

      // Only act on critical/high-severity patterns
      if (pattern.severity !== 'critical') continue

      for (const helixId of pattern.helixIds) {
        const assessment = this.state.branchAssessments.get(helixId)
        if (!assessment || assessment.status === 'completed' || assessment.status === 'failed') continue

        const directiveText = pattern.type === 'cascade-failure'
          ? 'Multiple branches are failing simultaneously. Narrow your scope to only the core deliverable and produce output immediately.'
          : pattern.type === 'asymmetric-progress'
            ? 'Other branches are significantly ahead. Focus on producing concrete output rather than more exploration.'
            : `Critical pattern detected: ${pattern.type}. Produce concrete output now.`

        this.sendDirective({
          targetHelixId: helixId,
          type: 'redirect',
          urgency: 'critical',
          reason: `Fallback directive for ${pattern.type} (LLM unhealthy)`,
          text: directiveText,
          fromPattern: pattern.type,
          timestamp: Date.now(),
          maxIterationsRemaining: 10,
          requiredAction: 'produce_output',
        })
      }
    }

    if (newPatterns.length > 0) {
      this.logger.info('Sent fallback directives (LLM rule_based)', {
        patternCount: newPatterns.length,
        consecutiveFailures: this.llmConsecFailures,
      })
    }
  }

  /**
   * Act on topology-driven patterns automatically.
   * WHY: Topology patterns (redundancy, cluster-escalated conflicts) require spatial
   * awareness that the LLM prompt alone doesn't surface reliably. Rather than hoping
   * the LLM calls send_directive for these, we issue directives directly — similar
   * to how budget interventions work. This runs regardless of LLM health.
   *
   * HOW: For each un-acted topology pattern, we pick the lowest-scoring branch
   * in the group and redirect it. This is a conservative strategy: we don't
   * cancel branches, we nudge the weakest one to pivot.
   */
  private actOnTopologyPatterns(newPatterns: CrossHelixPattern[]): void {
    const topologyPatternTypes = new Set(['redundancy'])
    let actedCount = 0

    for (const pattern of newPatterns) {
      if (pattern.actedUpon) continue
      if (!topologyPatternTypes.has(pattern.type)) continue
      if (pattern.helixIds.length < 2) continue

      // Find the lowest-scoring active branch in the pattern group
      let weakest: { helixId: string; score: number } | undefined
      for (const helixId of pattern.helixIds) {
        const assessment = this.state.branchAssessments.get(helixId)
        if (!assessment || assessment.status === 'completed' || assessment.status === 'failed') continue
        const score = assessment.rollingScore
        if (!weakest || score < weakest.score) {
          weakest = { helixId, score }
        }
      }

      if (!weakest) continue

      // Only act if the weakest branch has a meaningfully lower score than the strongest
      const scores = pattern.helixIds
        .map(id => this.state.branchAssessments.get(id)?.rollingScore ?? 0.5)
      const maxScore = Math.max(...scores)
      if (maxScore - weakest.score < 0.15) continue

      this.sendDirective({
        targetHelixId: weakest.helixId,
        type: 'redirect',
        urgency: 'medium',
        reason: `Topology ${pattern.type}: ${pattern.description}`,
        text: pattern.type === 'redundancy'
          ? `Another branch in your cluster is doing similar work with better results (score ${maxScore.toFixed(2)} vs yours ${weakest.score.toFixed(2)}). Pivot to a different aspect of the problem — explore an angle they haven't covered, or focus on testing/review instead of implementation.`
          : `Topology pattern "${pattern.type}" detected. Consider adjusting your approach to reduce overlap with nearby branches.`,
        fromPattern: pattern.type,
        timestamp: Date.now(),
      })

      actedCount++
    }

    if (actedCount > 0) {
      this.logger.info('Acted on topology patterns', {
        acted: actedCount,
        total: newPatterns.filter(p => topologyPatternTypes.has(p.type)).length,
      })
    }
  }

  /**
   * Inject budget pressure from the constellation checkpoint timer.
   * WHY: Instead of force-killing branches (blunt), this tells the Corpus
   * to prioritize completion. Active branches with low scores get throttled;
   * branches near completion continue; new spawns are suppressed.
   */
  injectBudgetPressure(totalSteps: number, softBudget: number): void {
    const branches = this.tree.getAllBranches()
    const activeBranches = branches.filter(b => b.status === 'active')

    // Sort active branches by score (lowest first) — prune the weakest
    const sorted = activeBranches
      .map(b => ({ helixId: b.helixId, score: this.state.branchAssessments.get(b.helixId)?.rollingScore ?? 0.5 }))
      .sort((a, b) => a.score - b.score)

    // HOW: Throttle the bottom half of active branches, redirect the top half to wrap up
    const throttleCount = Math.ceil(sorted.length / 2)

    for (let i = 0; i < sorted.length; i++) {
      const { helixId, score } = sorted[i]
      if (i < throttleCount) {
        this.sendDirective({
          targetHelixId: helixId,
          type: 'throttle',
          urgency: 'high',
          reason: `Step budget pressure (${totalSteps}/${softBudget}). Low-scoring branch (${score.toFixed(2)}) — wrap up immediately.`,
          text: 'Step budget is exhausted. You are being throttled. Produce your best output NOW and finish. Do not start new work.',
          timestamp: Date.now(),
          maxIterationsRemaining: 3,
          requiredAction: 'produce_output',
        })
      } else {
        this.sendDirective({
          targetHelixId: helixId,
          type: 'priority-shift',
          urgency: 'medium',
          reason: `Step budget pressure (${totalSteps}/${softBudget}). Focus on completion.`,
          text: 'The constellation is nearing its step budget. Focus on producing concrete output and finishing your current task. Avoid starting new exploration.',
          timestamp: Date.now(),
          maxIterationsRemaining: 10,
        })
      }
    }

    this.logger.warn('Budget pressure injected', {
      totalSteps,
      softBudget,
      activeBranches: activeBranches.length,
      throttled: throttleCount,
      redirected: sorted.length - throttleCount,
    })
  }

  /**
   * Build a compact template capabilities context section for LLM prompts.
   *
   * HOW: Lists all available templates with their skill domains and best-for
   * tags so the Corpus LLM can reason about template fitness when evaluating
   * branches or spawn requests.
   */
  private buildTemplateCapsContext(): string {
    const caps = listTemplateCapabilities()
    const lines = caps.map(c =>
      `- **${c.template}** (${c.postureCount} postures): ${c.description}. Domains: ${c.primaryDomains.join(', ')}. Best for: ${c.bestFor.join(', ')}.`
    )
    return `\n\n## Template Capabilities Reference\n${lines.join('\n')}`
  }

  /**
   * Build first-person LLM prompt
   */
  private buildLLMPrompt(newPatterns: CrossHelixPattern[]): string {
    const branches = this.tree.getAllBranches()

    // Build rich per-branch blocks using cognitive model fields from digests
    const branchDetails = branches
      .map((b) => {
        const assessment = this.state.branchAssessments.get(b.helixId)
        const digest = this.tree.getDigestFor(b.helixId)
        const recentSteps = b.steps.slice(-3)
        const recentAnnotations = recentSteps
          .map((s) => `[${s.annotation.annotation}:${s.annotation.score.toFixed(2)}]`)
          .join(', ')

        const lines: string[] = [
          `### ${b.helixId} (${b.status})`,
          `Goal: ${b.goal}`,
          `Steps: ${b.steps.length} | Rolling score: ${assessment?.rollingScore.toFixed(2) ?? 'N/A'} | Pattern: ${assessment?.dominantPattern ?? 'none'} | Approach: ${digest?.approach ?? 'unknown'}`,
          `Recent: ${recentAnnotations || '(none yet)'}`,
        ]

        if (digest?.currentHypothesis) {
          lines.push(`Current hypothesis: ${digest.currentHypothesis}`)
        }
        if (digest?.allDiscoveries && digest.allDiscoveries.length > 0) {
          lines.push(`Discoveries:`)
          for (const d of digest.allDiscoveries.slice(-5)) lines.push(`  - ${d}`)
        }
        if (digest?.allDecisions && digest.allDecisions.length > 0) {
          lines.push(`Decisions made:`)
          for (const d of digest.allDecisions.slice(-3)) lines.push(`  - ${d}`)
        }
        if (digest?.blockers && digest.blockers.length > 0) {
          lines.push(`Active blockers:`)
          for (const bl of digest.blockers) lines.push(`  - ${bl}`)
        }
        if (digest?.currentBlockers && digest.currentBlockers.length > 0) {
          lines.push(`Blockers with severity:`)
          for (const bl of digest.currentBlockers) {
            lines.push(`  - [${bl.severity.toUpperCase()}] ${bl.description}`)
          }
        }
        if (digest?.confidenceLevel) {
          const cl = digest.confidenceLevel
          lines.push(`Confidence: ${(cl.score * 100).toFixed(0)}% (${cl.trend})${cl.factors.length > 0 ? ` — ${cl.factors.join('; ')}` : ''}`)
        }
        if (digest?.estimatedTimeToCompletion) {
          const etc = digest.estimatedTimeToCompletion
          lines.push(`ETA: ~${etc.minutes} min (${(etc.confidence * 100).toFixed(0)}% confidence, based on ${etc.basedOnSteps} steps)`)
        }
        if (digest?.currentNextSteps && digest.currentNextSteps.length > 0) {
          lines.push(`Planned next steps:`)
          for (const ns of digest.currentNextSteps.slice(0, 3)) lines.push(`  - ${ns}`)
        }
        if (digest?.recentOutputs && digest.recentOutputs.length > 0) {
          lines.push(`Recent outputs: ${digest.recentOutputs.slice(-3).join(', ')}`)
        }
        if (digest?.selfOrgSignals && digest.selfOrgSignals.length > 0) {
          lines.push(`Self-org signals (ready to fire — Brainstem deferred to Corpus):`)
          for (const s of digest.selfOrgSignals) {
            lines.push(`  - [${s.type}] ${s.description} | evidence: ${s.evidence}`)
          }
        }
        if (digest?.liveStreamSnippet?.trim()) {
          lines.push(`Currently generating:\n${digest.liveStreamSnippet}`)
        }

        return lines.join('\n')
      })
      .join('\n\n')

    const patternDetails =
      newPatterns.length > 0
        ? `\n## New Cross-Branch Patterns Detected\n${newPatterns
            .map((p) => `- ${p.type} (${p.severity}): ${p.description}`)
            .join('\n')}`
        : ''

    // Include cross-Helix dialectic state if available
    const dialecticSummary = this.deps.crossHelixDialectic?.getDialecticSummaryForCorpus() ?? ''
    const dialecticSection = dialecticSummary
      ? `\n${dialecticSummary}\n`
      : ''

    // Build intervention history so Corpus remembers its past decisions
    const recentInterventions = this.state.interventions.slice(-6)
    const interventionHistorySection = recentInterventions.length > 0
      ? `\n## My Previous Interventions (last ${recentInterventions.length})\n${recentInterventions.map(i =>
          `- ${i.type} → ${i.targetHelixId} [${i.urgency}]: "${i.text.slice(0, 120)}"`
        ).join('\n')}`
      : ''

    // Build spawn history
    const recentSpawns = this.state.spawnDecisions.slice(-4)
    const spawnHistorySection = recentSpawns.length > 0
      ? `\n## My Previous Spawn Decisions (last ${recentSpawns.length})\n${recentSpawns.map(s =>
          `- ${s.approved ? 'APPROVED' : 'REJECTED'}: "${s.goal.slice(0, 100)}" (from: ${s.requestingHelixId})`
        ).join('\n')}`
      : ''

    // Build template capabilities context so Corpus can reason about template fitness
    const templateCapsSection = this.buildTemplateCapsContext()

    // Build topology context so Corpus sees spatial clustering state
    let topologySection = ''
    const topology = this.deps.topology
    if (topology?.enabled) {
      const snap = topology.getSnapshot()
      if (snap.clusters.length > 0 || snap.links.length > 0) {
        const clusterLines = snap.clusters.map(c => {
          const depth = c.effectiveMergeDepth
          const stability = (c.stabilityScore * 100).toFixed(0)
          return `- Cluster "${c.clusterId}": [${c.members.join(', ')}] depth=${depth} stability=${stability}% avgDist=${c.averageInternalDistance.toFixed(2)}`
        })
        const linkLines = snap.links.slice(0, 10).map(l =>
          `- ${l.helixIdA} ↔ ${l.helixIdB}: dist=${l.distance.toFixed(2)} sim=${l.similarity.toFixed(2)} depth=${l.mergeDepth} (stable ${l.stabilityTicks} ticks)`
        )
        topologySection = `\n\n## Topology (Spatial Clustering)\nTick ${snap.tickCount} | ${snap.clusters.length} clusters | ${snap.links.length} links\n${clusterLines.length > 0 ? `### Clusters\n${clusterLines.join('\n')}` : ''}${linkLines.length > 0 ? `\n### Links\n${linkLines.join('\n')}` : ''}\nThreads in the same cluster share semantic context — consider coordinating their approaches or merging their findings.`
      }
    }

    return `I am the strategic organizer of this Constellation. My goal: ${this.deps.goal}. I oversee ${branches.length} active threads, each thinking in parallel. I synthesize their knowledge, detect patterns, provide specific guidance, and spawn new threads when gaps emerge.

## Active Threads
${branchDetails}${patternDetails}${dialecticSection}${interventionHistorySection}${spawnHistorySection}${templateCapsSection}${topologySection}

## Task
Provide strategic assessment using the following directives:

ASSESSMENT: <comprehensive assessment of constellation health — what has been learned collectively, what's working, what's stuck>
INTERVENTION[threadId]: <type:guidance|redirect|throttle|priority-shift|cancel>:<urgency:low|medium|high|critical>:<first-person guidance text>
SPAWN[parentThreadId]: <focused goal for a new thread>
SYNTHESIS: <cross-thread insight worth injecting — something one thread knows that another would benefit from, or NONE>

Guidelines:
- ASSESSMENT: Synthesize what all threads have collectively learned. Reference specific discoveries and decisions from the thread details above.
- INTERVENTION: Only when a specific thread needs steering. Use the thread ID shown in the "### threadId" heading above. Write guidance that draws on what the thread has already discovered: not "stop drifting" but "I've confirmed X and Y — I should now implement Z using the approach I identified in the decisions above". Avoid repeating an intervention that didn't work — escalate instead.
- SPAWN: Request a new thread when:
  (a) A thread reveals a sub-problem that would benefit from dedicated parallel work
  (b) A thread has blockers that a fresh perspective might resolve
  (c) A gap exists between what threads know collectively and what the goal requires
  Use the parent thread ID that surfaced the need.
- SYNTHESIS: If one thread has discovered something that directly helps another thread's blocker or next steps, inject that insight here. Otherwise NONE.
- Write all guidance in first person ("I should…" not "You should…"). Every thread is the same mind thinking in parallel — guidance is self-directed thought.
- NONE is valid for INTERVENTION, SPAWN, or SYNTHESIS if nothing is needed.`
  }

  /**
   * Parse LLM response and apply interventions.
   *
   * Uses forgiving parsing — tries the structured format first, falls back
   * to heuristic extraction when the LLM doesn't follow the exact template.
   */
  private parseAndApplyLLMResponse(response: string): void {
    // Parse ASSESSMENT — try structured, then fall back to first sentence
    const assessmentMatch = response.match(/ASSESSMENT:\s*(.+?)(?=\n(?:INTERVENTION|SYNTHESIS)|$)/is)
    let assessment = assessmentMatch?.[1]?.trim() ?? ''
    if (!assessment) {
      // Fallback: use the first non-empty line as the assessment
      const firstLine = response.split('\n').find((l) => l.trim().length > 0)?.trim()
      assessment = firstLine ?? 'No assessment provided'
      this.logger.debug('ASSESSMENT tag not found, using first line as assessment', {
        fallbackAssessment: assessment.slice(0, 100),
      })
    }

    // Parse INTERVENTION lines — try multiple formats
    // Format 1: INTERVENTION[helixId]: type:urgency:text
    // Format 2: INTERVENTION[helixId] type urgency text (space-separated)
    // Format 3: INTERVENTION helixId: type:urgency:text (no brackets)
    const interventionRegex = /INTERVENTION\s*[\[(\s]([^\]\):\n]+)[\])\s]*[:\s]\s*([^:\n]+)[:\s]+([^:\n]+)[:\s]+(.+)/gi
    let match
    let interventionCount = 0
    while ((match = interventionRegex.exec(response)) !== null) {
      const helixId = match[1].trim()
      const rawType = match[2].trim().toLowerCase()
      const rawUrgency = match[3].trim().toLowerCase()
      const text = match[4].trim()

      if (text.toUpperCase() === 'NONE') continue

      // Normalize type — accept partial matches
      const type = normalizeDirectiveType(rawType)
      const urgency = normalizeUrgency(rawUrgency)

      if (type && urgency) {
        const directive: CorpusDirective = {
          targetHelixId: helixId,
          type,
          urgency,
          reason: assessment,
          text,
          timestamp: Date.now(),
        }
        this.sendDirective(directive)
        interventionCount++
      } else {
        this.logger.debug('Skipping intervention with unrecognized type/urgency', {
          rawType, rawUrgency, helixId,
        })
      }
    }

    if (interventionCount === 0 && response.toLowerCase().includes('intervention')) {
      this.logger.debug('Response mentions intervention but regex did not match', {
        responseSnippet: response.slice(0, 300),
      })
    }

    // Parse SPAWN lines — SPAWN[parentHelixId]: <goal>
    const spawnRegex = /SPAWN\s*[\[(\s]([^\]\):\n]+)[\])\s]*[:\s]\s*(.+)/gi
    let spawnMatch
    while ((spawnMatch = spawnRegex.exec(response)) !== null) {
      const parentHelixId = spawnMatch[1].trim()
      const spawnGoal = spawnMatch[2].trim()

      if (spawnGoal.toUpperCase() === 'NONE') continue

      if (this.deps.onSpawnRequest) {
        this.deps.onSpawnRequest({
          requestingHelixId: parentHelixId,
          goal: spawnGoal,
          context: assessment,
        })

        try {
          this.deps.store?.recordCorpusDecision(this.deps.constellationId, {
            decisionType: 'spawn',
            helixId: parentHelixId,
            inputData: {
              reason: 'Corpus LLM analysis',
              parentGoal: this.tree.getBranch(parentHelixId)?.goal ?? 'unknown',
              assessment: assessment.slice(0, 500),
            },
            outputData: {
              childGoal: spawnGoal,
            },
            llmAnalysis: response.slice(0, 1000),
            confidence: 0.7,
          })
        } catch (err) {
          this.logger.warn('Failed to record spawn decision', { error: String(err) })
        }

        this.logger.info('Spawn request submitted from Corpus LLM analysis', {
          parentHelixId,
          goal: spawnGoal.slice(0, 100),
        })
        this.emitEvent('corpus:spawn-requested', {
          parentHelixId,
          goal: spawnGoal.slice(0, 100),
        })
      } else {
        this.logger.warn('Corpus LLM requested spawn but onSpawnRequest not wired', {
          parentHelixId,
          goal: spawnGoal.slice(0, 100),
        })
      }
    }

    // Parse SYNTHESIS — try structured, then fall back to last paragraph
    const synthesisMatch = response.match(/SYNTHESIS:\s*(.+?)(?=\n(?:ASSESSMENT|INTERVENTION|SPAWN)|$)/is)
    let synthesis = synthesisMatch?.[1]?.trim()
    if (!synthesis || synthesis.toUpperCase() === 'NONE') {
      // No explicit synthesis — that's fine, not every sweep needs one
      synthesis = undefined
    }
    if (synthesis) {
      this.postSynthesisToBlackboard(synthesis, assessment)
    }
  }

  /**
   * Send a directive to a child Brainstem or ObserverBranchState.
   * WHY: In observer coordination mode, branches use ObserverBranchState instead of
   * Brainstem. Previously this method returned early in observer mode, meaning all
   * directives were silently dropped — including those from the CrossHelixDialectic
   * and stagnation sentinel. Now it delivers via ObserverBranchState.onCorpusDirective()
   * and publishes to the GlobalWorkspace so the LLM sees the directive. (c-36 fix)
   */
   private sendDirective(directive: CorpusDirective): void {
    if (this.deps.observerCoordination) {
      const obs = this.deps.observerBranchStates?.get(directive.targetHelixId)
      if (obs) {
        obs.onCorpusDirective(directive)
        // WHY: Also publish to GlobalWorkspace so the posture runner's
        // injectWorkspaceBroadcasts() picks it up and delivers to the LLM.
        // Without this, the directive reaches the Corpus tree but never the LLM.
        const ws = this.deps.globalWorkspace
        if (ws) {
          ws.submit({
            signalId: `corpus-directive-${Date.now()}`,
            source: 'corpus',
            sessionId: directive.targetHelixId,
            type: 'suggestion',
            content: `[CORPUS DIRECTIVE · ${directive.urgency}] ${directive.text}`,
            createdAt: Date.now(),
            luminance: {
              novelty: 0.3,
              urgency: directive.urgency === 'critical' ? 1 : directive.urgency === 'high' ? 0.8 : 0.5,
              relevance: 0.8,
              sourceCredibility: 0.9,
              cognitiveResonance: 0, strategicImportance: 0,
              composite: 0.7,
            },
            urgencyHint: directive.urgency === 'critical' ? 1.0 : directive.urgency === 'high' ? 0.8 : 0.5,
            metadata: {
              helix: true,
              posture: 'corpus',
              kind: 'directive',
              reason: directive.reason,
            },
          })
        }
        this.logger.debug('Directive delivered to ObserverBranchState', {
          helixId: directive.targetHelixId,
          type: directive.type,
          urgency: directive.urgency,
        })
      } else {
        this.logger.debug('Observer directive: no ObserverBranchState for target', {
          helixId: directive.targetHelixId,
        })
      }
      return
    }
    if (this.deps.meditationMode) return
    const brainstem = this.childBrainstems.get(directive.targetHelixId)
    if (!brainstem) {
      this.logger.warn('Cannot send directive: Brainstem not registered', {
        helixId: directive.targetHelixId,
      })
      return
    }

    if (!brainstem.onCorpusDirective) {
      this.logger.warn('Brainstem does not support directives', {
        helixId: directive.targetHelixId,
      })
      return
    }

    try {
      brainstem.onCorpusDirective(directive)

      const intervention: CorpusIntervention = {
        ...directive,
        acknowledged: true,
        sweepNumber: this.state.sweepCount,
      }
      this.state.interventions.push(intervention)

      // WHY: Mark the source pattern as acted-upon so the Corpus doesn't
      // re-trigger the same intervention while the directive is in flight
      if (directive.fromPattern) {
        for (const pattern of this.state.crossPatterns) {
          if (
            pattern.type === directive.fromPattern &&
            pattern.helixIds.includes(directive.targetHelixId) &&
            !pattern.actedUpon
          ) {
            pattern.actedUpon = true
            break
          }
        }
      }

      const assessment = this.state.branchAssessments.get(directive.targetHelixId)
      const branch = this.tree.getBranch(directive.targetHelixId)
      const currentStep = branch ? branch.steps.length : 0
      const latestAnnotation = branch?.steps[branch.steps.length - 1]?.annotation

      if (assessment) {
        assessment.directiveHistory.push({
          directive,
          sentAtStep: currentStep,
          scoreAtSend: {
            goalAlignment: latestAnnotation?.goalAlignment ?? 0.5,
            novelty: latestAnnotation?.novelty ?? 0.5,
            progress: latestAnnotation?.progress ?? 0.3,
          },
          postDirectiveScores: [],
          outcome: 'pending',
        })
      }

      if (assessment && branch) {
        this.interventionBaselines.set(directive.targetHelixId, {
          score: assessment.rollingScore,
          type: directive.type,
          timestamp: Date.now(),
          step: currentStep,
        })
      }

      try {
        this.deps.store?.recordCorpusDecision(this.deps.constellationId, {
          decisionType: 'intervention',
          helixId: directive.targetHelixId,
          inputData: {
            branchAssessment: assessment ? {
              rollingScore: assessment.rollingScore,
              status: assessment.status,
              decliningScoreStreak: assessment.decliningScoreStreak,
            } : undefined,
            pattern: assessment?.dominantPattern,
          },
          outputData: {
            directive,
            urgency: directive.urgency,
          },
          llmAnalysis: undefined,
          confidence: 0.5,
        })
      } catch (err) {
        this.logger.warn('Failed to record intervention decision', { error: String(err) })
      }

      this.emitEvent('corpus:intervention', {
        helixId: directive.targetHelixId,
        type: directive.type,
        urgency: directive.urgency,
        sweepNumber: this.state.sweepCount,
      })

      this.logger.info('Directive sent to Brainstem', {
        helixId: directive.targetHelixId,
        type: directive.type,
        urgency: directive.urgency,
      })
    } catch (error) {
      this.logger.error('Failed to send directive', {
        helixId: directive.targetHelixId,
        error: error instanceof Error ? error.message : String(error),
      })
    }
  }

  /**
   * Evaluate pending directives for behavioral change.
   *
   * For each directive with outcome='pending', collect post-directive annotations.
   * After 3 annotations, determine if behavior changed by comparing dimensional
   * scores before vs after. A directive is 'effective' if at least one of:
   *   - The dimension the directive targeted improved by >= 0.15
   *   - The annotation type changed (e.g., exploration → implementation)
   *   - The pattern field cleared (was drift/paralysis, now none)
   */
  private evaluatePendingDirectives(assessment: BranchAssessment, branch: CorpusBranch): void {
    const pendingDirectives = assessment.directiveHistory.filter(d => d.outcome === 'pending')
    if (pendingDirectives.length === 0) return

    for (const record of pendingDirectives) {
      // Collect post-directive annotations (steps after sentAtStep)
      const postSteps = branch.steps.slice(record.sentAtStep)
      for (const step of postSteps) {
        if (record.postDirectiveScores.length >= 3) break
        // Only add if not already recorded
        if (record.postDirectiveScores.length < postSteps.indexOf(step) + 1) {
          record.postDirectiveScores.push({
            goalAlignment: step.annotation.goalAlignment ?? 0.5,
            novelty: step.annotation.novelty ?? 0.5,
            progress: step.annotation.progress ?? 0.3,
            annotation: step.annotation.annotation,
          })
        }
      }

      // Evaluate once we have 3 post-directive scores
      if (record.postDirectiveScores.length >= 3) {
        const before = record.scoreAtSend
        const after = record.postDirectiveScores
        const avgAfter = {
          goalAlignment: after.reduce((s, a) => s + a.goalAlignment, 0) / after.length,
          novelty: after.reduce((s, a) => s + a.novelty, 0) / after.length,
          progress: after.reduce((s, a) => s + a.progress, 0) / after.length,
        }

        // Check for meaningful improvement in any dimension
        const goalImproved = avgAfter.goalAlignment - before.goalAlignment >= 0.15
        const noveltyImproved = avgAfter.novelty - before.novelty >= 0.15
        const progressImproved = avgAfter.progress - before.progress >= 0.15
        // Check for annotation type change (e.g., exploration → implementation)
        const annotationChanged = after.some(a => a.annotation !== after[0].annotation)

        if (goalImproved || noveltyImproved || progressImproved || annotationChanged) {
          record.outcome = 'effective'
          // Reset ignored streak on effective directive
          assessment.ignoredDirectiveStreak = 0
          // De-escalate one level on effective directive (min 0)
          assessment.escalationLevel = Math.max(0, assessment.escalationLevel - 1) as EscalationLevel
        } else {
          record.outcome = 'ignored'
          assessment.ignoredDirectiveStreak++

          this.logger.warn('Directive was ignored by branch', {
            helixId: assessment.helixId,
            directiveType: record.directive.type,
            ignoredStreak: assessment.ignoredDirectiveStreak,
            escalationLevel: assessment.escalationLevel,
          })
        }
        record.evaluatedAt = Date.now()
      }
    }
  }

  /**
   * Check effectiveness of recent interventions by comparing baseline scores to current.
   * Called each sweep after annotations are processed.
   *
   * For each helix with a recorded baseline:
   * - Get current rolling score from assessment
   * - Calculate improvement
   * - Record effectiveness in the tree
   * - Clear the baseline (one-shot measurement)
   */
  private checkInterventionEffectiveness(): void {
    for (const [helixId, baseline] of this.interventionBaselines.entries()) {
      const assessment = this.state.branchAssessments.get(helixId)
      const branch = this.tree.getBranch(helixId)
      if (!assessment || !branch) {
        this.interventionBaselines.delete(helixId)
        continue
      }

      const currentStep = branch.steps.length
      const stepsSinceBaseline = currentStep - baseline.step
      if (stepsSinceBaseline < 2) {
        // Not enough steps yet for meaningful comparison
        continue
      }

      const improvement = assessment.rollingScore - baseline.score
      const effective = improvement > 0.05 // 5% improvement threshold

      // WHY: Map Corpus directive types to SelfOrgAdjustmentType for effectiveness tracking
      // This allows the constellation to learn which intervention strategies work
      const adjustmentTypeMap: Record<string, SelfOrgAdjustmentType> = {
        'guidance': 'approach-redirect',
        'redirect': 'approach-redirect',
        'throttle': 'goal-refinement',
        'priority-shift': 'goal-refinement',
        'cancel': 'tension-flag',
      }
      const adjustmentType = adjustmentTypeMap[baseline.type] ?? 'approach-redirect'

      this.tree.recordEffectiveness({
        helixId,
        adjustmentType,
        scoreBefore: baseline.score,
        scoreAfter: assessment.rollingScore,
        stepsDelta: stepsSinceBaseline,
        improvement,
        effective,
        measuredAt: Date.now(),
      })

      this.logger.debug('Intervention effectiveness measured', {
        helixId,
        type: baseline.type,
        baselineScore: baseline.score.toFixed(3),
        currentScore: assessment.rollingScore.toFixed(3),
        improvement: improvement.toFixed(3),
        effective,
      })

      // Persist as training signal
      this.deps.store?.recordTrainingSignal(this.deps.constellationId, {
        signalType: 'effectiveness_measured',
        sourceHelixId: helixId,
        data: {
          interventionType: baseline.type,
          adjustmentType,
          scoreBefore: baseline.score,
          scoreAfter: assessment.rollingScore,
          improvement,
          effective,
          stepsDelta: stepsSinceBaseline,
        },
        qualityScore: effective ? 0.9 : 0.4,
      })

      // WHY: Update the DirectiveRecord outcome so callers can inspect lifecycle state
      // rather than finding every record permanently 'pending'
      for (const record of assessment.directiveHistory) {
        if (record.outcome === 'pending') {
          record.outcome = effective ? 'effective' : 'ignored'
          record.evaluatedAt = Date.now()
          break // Update only the most recent pending directive
        }
      }

      // One-shot measurement — clear the baseline
      this.interventionBaselines.delete(helixId)
    }
  }

  /**
   * Get escalation thresholds for a branch based on its template.
   */
  private getEscalationThresholds(helixId: string): EscalationThresholds {
    const branch = this.tree.getBranch(helixId)
    // Look up template from branch metadata or fall back to 'standard'
    const templateName = (branch as any)?.template ?? 'standard'
    return ESCALATION_DEFAULTS[templateName] ?? ESCALATION_DEFAULTS.standard
  }

  /**
   * Evaluate whether a branch should be escalated.
   *
   * Combined escalation: both ignored directives and metric thresholds
   * contribute. A branch with declining scores AND ignored directives
   * escalates faster than one with just one signal.
   *
   * Levels:
   *   0 = normal (no intervention beyond LLM-generated guidance)
   *   1 = guidance directive sent by Corpus
   *   2 = critical injection (high-urgency directive)
   *   3 = kill branch (cancel + optional restart)
   *   4 = pause constellation for strategic reassessment
   *
   * Returns the new escalation level if it changed, or null if no escalation.
   */
  evaluateEscalation(assessment: BranchAssessment): EscalationLevel | null {
    const thresholds = this.getEscalationThresholds(assessment.helixId)
    const currentLevel = assessment.escalationLevel

    const directiveSignal = assessment.ignoredDirectiveStreak >= thresholds.directiveFailuresForEscalation

    const metricSignal = assessment.lowProgressStreak >= thresholds.lowProgressStepsForEscalation
      || (assessment.rollingScore < thresholds.lowScoreThreshold
          && assessment.scoreTrajectory.length >= thresholds.lowScoreStepsForEscalation)

    // Both signals → escalate by 2 levels (fast path)
    // One signal → escalate by 1 level
    // No signals → no change (or de-escalate if things improved)
    let newLevel = currentLevel

    if (directiveSignal && metricSignal) {
      newLevel = Math.min(4, currentLevel + 2) as EscalationLevel
    } else if (directiveSignal || metricSignal) {
      newLevel = Math.min(4, currentLevel + 1) as EscalationLevel
    }

    if (newLevel !== currentLevel) {
      assessment.escalationLevel = newLevel
      this.logger.info('Branch escalation level changed', {
        helixId: assessment.helixId,
        previousLevel: currentLevel,
        newLevel,
        directiveSignal,
        metricSignal,
        ignoredStreak: assessment.ignoredDirectiveStreak,
        lowProgressStreak: assessment.lowProgressStreak,
      })
      return newLevel
    }

    return null
  }

  /**
   * Evaluate escalation for all active branches and act on level changes.
   */
  private async evaluateAllEscalations(): Promise<void> {
    for (const [helixId, assessment] of this.state.branchAssessments) {
      // Skip completed/failed branches
      if (assessment.status === 'completed' || assessment.status === 'failed') continue

      const newLevel = this.evaluateEscalation(assessment)
      if (newLevel === null) continue

      // Act on the escalation level
      switch (newLevel) {
        case 1:
          // Level 1: Send guidance directive (soft) with scope constraint
          this.sendDirective({
            targetHelixId: helixId,
            type: 'guidance',
            urgency: 'medium',
            text: `Branch ${helixId} is underperforming. Please refocus on the goal and produce concrete output.`,
            reason: `Escalation to level 1: ignored=${assessment.ignoredDirectiveStreak} directives, lowProgress=${assessment.lowProgressStreak} steps`,
            timestamp: Date.now(),
            fromPattern: 'asymmetric-progress',
            maxIterationsRemaining: 20,
            requiredAction: 'narrow_scope',
          })
          break

        case 2: {
          // Level 2: Send critical redirect (hard) with output requirement
          this.sendDirective({
            targetHelixId: helixId,
            type: 'redirect',
            urgency: 'critical',
            text: `Branch ${helixId} has ignored multiple directives and metrics are declining. ` +
              `You must change approach immediately: narrow scope, switch strategy, or conclude with current findings.`,
            reason: `Escalation to level 2: ignored=${assessment.ignoredDirectiveStreak} directives, lowProgress=${assessment.lowProgressStreak} steps`,
            timestamp: Date.now(),
            fromPattern: 'cascade-failure',
            maxIterationsRemaining: 10,
            requiredAction: 'produce_output',
          })
          
          // Consider re-decomposition for branches at escalation level 2
          // The branch may be struggling because the task is too complex
          await this.considerReDecomposition(helixId, 'escalation level 2')
          break
        }

        case 3:
          // Level 3: Cancel the branch — force conclusion first if possible
          this.logger.warn('Escalation level 3: cancelling branch', { helixId })
          this.sendDirective({
            targetHelixId: helixId,
            type: 'cancel',
            urgency: 'critical',
            text: `Branch ${helixId} has reached escalation level 3. Cancelling due to sustained non-response to directives and declining metrics.`,
            reason: `Escalation to level 3: ignored=${assessment.ignoredDirectiveStreak} directives, score=${assessment.rollingScore.toFixed(2)}`,
            timestamp: Date.now(),
            maxIterationsRemaining: 5,
            requiredAction: 'conclude',
          })
          this.emitEvent('corpus:escalation', {
            helixId,
            level: 3,
            action: 'cancel',
          })
          break

        case 4:
          // Level 4: Pause constellation for reassessment
          this.logger.warn('Escalation level 4: requesting constellation pause', { helixId })
          this.emitEvent('corpus:escalation', {
            helixId,
            level: 4,
            action: 'pause-constellation',
          })
          break
      }
    }
  }

  /**
   * Run spawn evaluation via LLM
   */
  private async runSpawnEvaluation(request: SpawnRequest): Promise<SpawnDecision> {
    const branches = this.tree.getAllBranches()

    // Build template capabilities reference for informed template suggestions
    const caps = listTemplateCapabilities()
    const templateRef = caps.map(c =>
      `- ${c.template}: ${c.description}. Best for: ${c.bestFor.join(', ')}.`
    ).join('\n')

    const prompt = `I am evaluating a spawn request for this Constellation.

## Current Tree State
Active branches: ${branches.length}
Total steps: ${this.tree.totalStepCount()}

## Spawn Request
Requesting branch: ${request.requestingHelixId}
Proposed Goal: ${request.goal}
Proposed Template: ${request.template ?? 'standard'}
Target Depth: ${request.targetDepth}

## Available Templates
${templateRef}

## Task
Evaluate this spawn request:

DECISION: <APPROVED|REJECTED>
REASON: <brief reasoning>
SUGGESTED_TEMPLATE: <template name or NONE>
SUGGESTED_GOAL: <refined goal or NONE>

Guidelines:
- APPROVE if the goal is clear, non-redundant with existing branches, and resources allow
- REJECT if too many active branches, goal is unclear, or similar work is in progress
- Suggest refinements if the goal could be clearer
- When suggesting a template, pick the one whose "best for" tags most closely match the goal`

    try {
      const response = await this.deps.llm.complete({
        prompt,
        modelTier: this.config.modelTier,
        maxTokens: 3000,
        timeoutMs: this.config.timeoutMs,
      })

      const content = response.content

      // Parse DECISION — try structured format, then fuzzy matching
      const decisionMatch = content.match(/DECISION:\s*(APPROVED|REJECTED)/i)
      let approved: boolean
      if (decisionMatch) {
        approved = decisionMatch[1].toUpperCase() === 'APPROVED'
      } else {
        // Fuzzy: look for approval/rejection keywords anywhere in the response
        const lowerContent = content.toLowerCase()
        const hasApprove = /\bapprov(e|ed|ing)\b/.test(lowerContent)
        const hasReject = /\breject(ed|ing)?\b|\bdeny\b|\bdenied\b/.test(lowerContent)
        if (hasApprove && !hasReject) {
          approved = true
        } else {
          // Default to rejected when ambiguous — safer than spawning unnecessarily
          approved = false
        }
        this.logger.debug('DECISION tag not found in spawn evaluation, using fuzzy match', {
          approved,
          responseSnippet: content.slice(0, 200),
        })
      }

      // Parse REASON — try structured, fall back to first sentence
      const reasonMatch = content.match(/REASON:\s*(.+?)(?=\n|$)/i)
      let reason = reasonMatch?.[1]?.trim()
      if (!reason) {
        // Fallback: extract first substantive sentence
        const firstLine = content.split('\n').find((l) => l.trim().length > 10)?.trim()
        reason = firstLine ?? 'No reason provided'
      }

      // Parse SUGGESTED_TEMPLATE
      const templateMatch = content.match(/SUGGESTED_TEMPLATE:\s*([^\n]+)/i)
      const suggestedTemplateStr = templateMatch?.[1]?.trim()
      const suggestedTemplate: ConstellationTemplate | undefined =
        suggestedTemplateStr && suggestedTemplateStr.toUpperCase() !== 'NONE'
          ? (suggestedTemplateStr as ConstellationTemplate)
          : undefined

      // Parse SUGGESTED_GOAL
      const goalMatch = content.match(/SUGGESTED_GOAL:\s*([^\n]+)/i)
      const suggestedGoal =
        goalMatch?.[1]?.trim().toUpperCase() !== 'NONE' ? goalMatch?.[1]?.trim() : undefined

      // Validate file paths in the goal before finalizing the decision
      const finalGoal = suggestedGoal ?? request.goal
      let validatedGoal = finalGoal
      if (approved && this.deps.readFile) {
        validatedGoal = await this.validateGoalPaths(finalGoal)
      }

      return {
        requestId: request.requestId,
        requestingHelixId: request.requestingHelixId,
        goal: validatedGoal,
        approved,
        reason,
        suggestedTemplate,
        suggestedGoal: validatedGoal !== finalGoal ? validatedGoal : suggestedGoal,
        evaluatedAt: Date.now(),
      }
    } catch (error) {
      this.handleLLMFailure(error)
      this.logger.error('Spawn evaluation failed, defaulting to rejected', {
        error: error instanceof Error ? error.message : String(error),
        requestId: request.requestId,
      })

      return {
        requestId: request.requestId,
        requestingHelixId: request.requestingHelixId,
        goal: request.goal,
        approved: false,
        reason: `Evaluation failed: ${error instanceof Error ? error.message : String(error)}`,
        evaluatedAt: Date.now(),
      }
    }
  }

  /**
   * Validate file paths referenced in a spawn goal.
   * Annotates non-existent paths with [NOT FOUND] so the spawned Helix
   * doesn't waste time trying to read them.
   */
  private async validateGoalPaths(goal: string): Promise<string> {
    if (!this.deps.readFile) return goal

    const pathPattern = /(?:^|\s|['"`])((?:\.\/|\.\.\/|[a-zA-Z_][\w-]*\/)[^\s'"`,)}\]]+\.(?:ts|js|json|md))/g
    const matches = [...goal.matchAll(pathPattern)]
    if (matches.length === 0) return goal

    let result = goal
    for (const match of matches) {
      const filePath = match[1]
      try {
        const content = await this.deps.readFile(filePath)
        if (content === null) {
          result = result.replace(filePath, `${filePath} [NOT FOUND]`)
          this.logger.debug('Spawn goal referenced non-existent path', { filePath })
        }
      } catch {
        // readFile failed — leave as-is
      }
    }
    return result
  }

  /**
   * Post synthesis to blackboard
   */
  private postSynthesisToBlackboard(synthesis: string, assessment: string): void {
    const bb = this.deps.blackboard
    if (!bb) {
      this.logger.debug('Synthesis ready for blackboard (no blackboard wired)')
      return
    }

    try {
      bb.post('decisions', {
        author: 'corpus',
        content: `**Corpus Synthesis** — ${assessment}\n\n${synthesis}`,
        structured: {
          sweepCount: this.state.sweepCount,
          branches: this.tree.activeBranchCount(),
        },
        priority: 1,
        tags: ['corpus', 'synthesis'],
      })
    } catch (err) {
      this.logger.warn('Failed to post synthesis to blackboard', {
        error: String(err),
      })
    }
  }

  /**
   * Emit an event on the event bus if available
   */
  private emitEvent(type: string, data: Record<string, unknown>): void {
    // Persist to ConstellationStore (if callback provided)
    if (this.deps.persistEvent) {
      try {
        const entity = (data.helixId as string) ?? (data.requestId as string) ?? null
        const message = (data.reason as string) ?? (data.description as string) ?? type
        this.deps.persistEvent(type, entity, message.slice(0, 500), data)
      } catch {
        // Persistence failures must not crash the loop
      }
    }

    // Emit to EventBus (in-memory)
    if (!this.deps.eventBus) return
    try {
      void this.deps.eventBus.emit({
        type,
        constellationId: this.deps.constellationId,
        ...data,
      } as any)
    } catch {
      // Ignore emit errors — observability must not crash the loop
    }
  }

  /**
   * Sleep helper
   */
  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms))
  }

  /**
   * Interruptible sleep — checks shutdownRequested and wakeRequested every 50ms
   * to allow fast shutdown and fast response to new branches.
   */
  private async interruptibleSleep(ms: number): Promise<void> {
    const interval = 50
    for (let i = 0; i < ms && !this.shutdownRequested && !this.wakeRequested; i += interval) {
      await this.sleep(Math.min(interval, ms - i))
    }
    if (this.wakeRequested) {
      this.wakeRequested = false
      this.logger.debug('Corpus woke early due to wake request')
    }
  }

  /**
   * Signal the Corpus to wake up from idle sleep immediately.
   * WHY: Called when new branches are created so the Corpus can observe and
   * assess them without waiting for the full idle poll interval (10s default).
   */
  wake(): void {
    this.wakeRequested = true
  }


  // PROACTIVE BEHAVIORS — Budget, Discovery, Re-decomposition, etc.



  /**
   * Initialize budget for a branch based on template or decomposer suggestion.
   * Called when a new branch is first seen.
   */
  initializeBudget(helixId: string, budgetSteps?: number): void {
    if (this.branchBudgets.has(helixId)) return

    const template = this.deps.getHelixTemplate?.(helixId) ?? 'standard'
    const defaults = BRANCH_BUDGET_DEFAULTS[template] ?? BRANCH_BUDGET_DEFAULTS.standard

    const budget: BranchBudget = {
      maxSteps: budgetSteps ?? defaults.maxSteps,
      maxTimeMs: defaults.maxTimeMs,
      consumedSteps: 0,
      consumedTimeMs: 0,
      startedAt: Date.now(),
      source: budgetSteps ? 'decomposer' : 'template',
    }

    this.branchBudgets.set(helixId, budget)

    // Attach to assessment
    const assessment = this.state.branchAssessments.get(helixId)
    if (assessment) {
      assessment.budget = budget
    }

    this.logger.debug('Budget initialized', {
      helixId,
      maxSteps: budget.maxSteps,
      maxTimeMs: budget.maxTimeMs,
      source: budget.source,
    })
  }

  /**
   * Update budget consumption for all active branches.
   * Called every sweep cycle.
   */
  private trackBudgets(): void {
    const now = Date.now()

    for (const [helixId, budget] of this.branchBudgets) {
      const branch = this.tree.getBranch(helixId)
      if (!branch || branch.status !== 'active') continue

      budget.consumedSteps = branch.steps.length
      budget.consumedTimeMs = now - budget.startedAt

      // Check for budget overruns
      const stepsOverrun = budget.consumedSteps > budget.maxSteps
      const timeOverrun = budget.consumedTimeMs > budget.maxTimeMs
      const stepsPercentage = (budget.consumedSteps / budget.maxSteps) * 100
      const timePercentage = (budget.consumedTimeMs / budget.maxTimeMs) * 100

      if (stepsOverrun || timeOverrun) {
        const assessment = this.state.branchAssessments.get(helixId)
        const currentLevel = assessment?.escalationLevel ?? 0

        if (currentLevel < 2) {
          // Budget exceeded — inject warning directly
          this.logger.warn('Branch over budget', {
            helixId,
            stepsUsed: budget.consumedSteps,
            stepsMax: budget.maxSteps,
            timeUsedMs: budget.consumedTimeMs,
            timeMaxMs: budget.maxTimeMs,
          })

          this.performDirectInjection(helixId, [
            `⚠️ BUDGET EXCEEDED: You have used ${budget.consumedSteps}/${budget.maxSteps} steps ` +
            `and ${Math.round(budget.consumedTimeMs / 1000)}s/${Math.round(budget.maxTimeMs / 1000)}s wall time. ` +
            `Complete your current task immediately and call signal_done. Focus on delivering what you have ` +
            `rather than pursuing additional work.`,
          ].join(''), 'high')
        }
      } else if (stepsPercentage > 75 || timePercentage > 75) {
        // Approaching budget — send guidance through normal path
        const assessment = this.state.branchAssessments.get(helixId)
        if (assessment && !assessment.directiveHistory.some(d =>
          d.directive.type === 'redirect' && d.evaluatedAt && d.evaluatedAt > now - 60_000
        )) {
          this.sendDirective({
            targetHelixId: helixId,
            type: 'redirect',
            urgency: 'high',
            reason: 'Budget approaching limit',
            text: `You have consumed ${Math.round(stepsPercentage)}% of your step budget ` +
              `and ${Math.round(timePercentage)}% of your time budget. Start wrapping up — ` +
              `prioritize delivering concrete output over further exploration.`,
            timestamp: Date.now(),
          })
        }
      }
    }
  }



  /**
   * Extract discoveries from new annotations and route them to relevant branches.
   * Hybrid: push to branches with overlapping goals + broadcast to all via Brainstem.
   */
  private routeDiscoveries(): void {
    const branches = this.tree.getAllBranches()

    for (const branch of branches) {
      if (branch.status !== 'active') continue

      const cursor = this.state.cursors.get(branch.helixId) ?? 0
      // Look at recently processed steps (within last 3)
      const recentSteps = branch.steps.slice(Math.max(0, cursor - 3), cursor)

      for (const step of recentSteps) {
        const ann = step.annotation
        // Extract discoveries from exploration/research annotations with high novelty
        if (
          (ann.annotation === 'exploration' || ann.annotation === 'research') &&
          ann.novelty >= 0.6 &&
          ann.synthesis
        ) {
          const discoveryId = `${branch.helixId}-${branch.steps.indexOf(step)}`
          if (this.discoveries.has(discoveryId)) continue

          const discovery: DiscoveryEntry = {
            id: discoveryId,
            sourceHelixId: branch.helixId,
            content: ann.synthesis,
            type: this.classifyDiscovery(ann.synthesis),
            relatedFiles: (step.toolCalls ?? [])
              .flatMap(tc => extractFilePaths(tc.args))
              .filter(Boolean),
            timestamp: Date.now(),
            deliveredTo: new Set([branch.helixId]),
          }

          this.discoveries.set(discoveryId, discovery)
          this.discoveryCounter++

          this.emitEvent('corpus:discovery', {
            discoveryId,
            sourceHelixId: branch.helixId,
            content: ann.synthesis.slice(0, 300),
            type: discovery.type,
            relatedFiles: discovery.relatedFiles,
          })

          // Push to all other active branches
          for (const other of branches) {
            if (other.helixId === branch.helixId || other.status !== 'active') continue
            if (discovery.deliveredTo.has(other.helixId)) continue

            discovery.deliveredTo.add(other.helixId)

            // Deliver via Brainstem guidance
            const brainstem = this.childBrainstems.get(other.helixId)
            if (brainstem) {
            brainstem.onCorpusDirective?.({
              targetHelixId: other.helixId,
              type: 'guidance',
              urgency: 'low',
              reason: `Cross-branch discovery from ${branch.helixId}`,
              text: `Discovery from branch ${branch.helixId}: ${discovery.content}` +
                (discovery.relatedFiles.length > 0
                    ? `\nRelated files: ${discovery.relatedFiles.join(', ')}`
                    : ''),
              timestamp: Date.now(),
            })
            }
          }

          // Track in assessment
          const assessment = this.state.branchAssessments.get(branch.helixId)
          if (assessment) {
            assessment.discoveries.push(discovery.content)
          }
        }
      }
    }
  }

  /** Classify a discovery by its content */
  private classifyDiscovery(content: string): DiscoveryEntry['type'] {
    const lower = content.toLowerCase()
    if (lower.includes('architecture') || lower.includes('structure') || lower.includes('pattern'))
      return 'architecture'
    if (lower.includes('file') || lower.includes('path') || lower.includes('located'))
      return 'file_location'
    if (lower.includes('constraint') || lower.includes('limit') || lower.includes('requirement'))
      return 'constraint'
    if (lower.includes('decided') || lower.includes('chose') || lower.includes('decision'))
      return 'decision'
    return 'pattern'
  }



  /**
   * Consider incremental re-decomposition for a specific branch.
   * Called when a branch is stalled or over-budget to assess if it should be split.
   * 
   * @param helixId - The Helix session ID to assess
   * @param reason - Why re-decomposition is being considered
   * @returns true if the task was split, false otherwise
   */
  private async considerReDecomposition(
    helixId: string,
    reason: string,
  ): Promise<boolean> {
    if (!this.decompositionTracker) return false
    
    const task = this.decompositionTracker.getTaskByHelixId(helixId)
    if (!task || task.status !== 'in-progress') return false
    
    // Only consider re-decomposition if the branch has consumed >50% of its step budget
    // without proportional progress
    if (task.stepsConsumed && task.originalTask.budgetSteps) {
      const budgetRatio = task.stepsConsumed / task.originalTask.budgetSteps
      if (budgetRatio < 0.5) return false
    }
    
    this.logger.info('Considering re-decomposition', {
      helixId,
      reason,
      taskGoal: task.originalTask.goal,
    })
    
    // Use the Corpus LLM to decide whether to split
    const { content } = await this.deps.llm.complete({
      prompt: `A branch working on this task needs assessment:
Task: ${task.originalTask.goal}
Reason for assessment: ${reason}

Should this task be split into smaller sub-tasks? If yes, describe 2-3 sub-tasks.
Respond with JSON: { "split": true/false, "tasks": [{ "goal": "...", "priority": 1 }] }`,
      modelTier: this.config.modelTier,
      maxTokens: 1000,
      timeoutMs: 15000,
    })
    
    try {
      const decision = JSON.parse(content.replace(/```json?\n?/g, '').replace(/```/g, '').trim())
      if (decision.split && Array.isArray(decision.tasks) && decision.tasks.length > 0) {
        const newTaskIds = this.decompositionTracker.splitTask(task.id, decision.tasks)
        this.logger.info('Re-decomposed task', {
          originalTaskId: task.id,
          newTaskIds,
          newGoals: decision.tasks.map((t: any) => t.goal),
        })
        return true
      }
    } catch {
      // Parse failed — skip re-decomposition
    }
    
    return false
  }

  /**
   * Check for stuck or struggling branches and consider re-decomposition.
   * Called from the main analysis loop when branches show signs of being stuck.
   */
  private async checkStuckBranchesForReDecomposition(): Promise<void> {
    for (const [helixId, assessment] of this.state.branchAssessments) {
      // Skip completed/failed branches
      if (assessment.status === 'completed' || assessment.status === 'failed') continue
      
      // Check if branch is stuck or struggling with a declining score streak
      if (
        (assessment.status === 'stuck' || assessment.status === 'struggling') &&
        assessment.decliningScoreStreak >= 5
      ) {
        // Attempt re-decomposition for this stuck branch
        const split = await this.considerReDecomposition(helixId, 'branch stalled')
        if (split) {
          this.logger.info('Re-decomposition attempted for stuck branch', {
            helixId,
            decliningScoreStreak: assessment.decliningScoreStreak,
          })
        }
      }
    }
  }

  /**
   * Evaluate whether any active branch should be split into smaller sub-tasks.
   * Uses the Corpus LLM with full trajectory context across all branches.
   */
  private async evaluateReDecomposition(): Promise<void> {
    if (!this.deps.launchHelix || !this.deps.killHelix) return

    const branches = this.tree.getAllBranches().filter(b => b.status === 'active')
    if (branches.length === 0) return

    // Only evaluate branches that have been running long enough to assess
    const candidates = branches.filter(b => {
      const assessment = this.state.branchAssessments.get(b.helixId)
      if (!assessment) return false
      // Must have at least 8 steps to judge scope
      if (b.steps.length < 8) return false
      // Don't re-decompose branches that are already narrow (spawned from re-decomposition)
      if (this.reDecompositions.some(rd => rd.newSubTasks.some(st => st.goal.includes(b.helixId)))) return false
      // Only consider if scores suggest drift or multi-tasking
      return (assessment.avgProgress ?? 0) < 0.4 || b.steps.length > (assessment.budget?.maxSteps ?? 30) * 0.6
    })

    if (candidates.length === 0) return

    // Build full trajectory context for the LLM
    const trajectoryContext = this.buildFullTrajectoryContext()

    for (const branch of candidates) {
      const assessment = this.state.branchAssessments.get(branch.helixId)!
      const branchGoal = branch.goal ?? 'unknown goal'

      try {
        const prompt = [
          `You are the Corpus — a strategic coordinator for a multi-branch constellation.`,
          ``,
          `## Overall Goal`,
          this.deps.goal,
          ``,
          `## Full Trajectory (All Branches)`,
          trajectoryContext,
          ``,
          `## Branch Under Review: ${branch.helixId}`,
          `Goal: ${branchGoal}`,
          `Steps: ${branch.steps.length}, Avg Progress: ${(assessment.avgProgress ?? 0).toFixed(2)}, ` +
          `Avg GoalAlignment: ${(assessment.avgGoalAlignment ?? 0).toFixed(2)}`,
          `Budget: ${assessment.budget?.consumedSteps ?? '?'}/${assessment.budget?.maxSteps ?? '?'} steps`,
          ``,
          `## Question`,
          `Is this branch trying to do too much? Should it be split into smaller, more focused sub-tasks?`,
          ``,
          `Respond with one of:`,
          `KEEP — the branch is fine, let it continue`,
          `SPLIT — the branch should be split. Provide:`,
          `  REASON: <why it should be split>`,
          `  SUBTASK_1: <focused goal for new branch 1>`,
          `  SUBTASK_2: <focused goal for new branch 2>`,
          `  ... (as many as needed)`,
          `  NARROWED: <narrowed goal for the original branch, or KILL to terminate it>`,
        ].join('\n')

        const { content: response } = await this.deps.llm.complete({
          prompt,
          modelTier: this.config.modelTier,
          maxTokens: this.config.maxTokens,
          timeoutMs: this.config.timeoutMs,
        })

        if (response.includes('SPLIT')) {
          const reason = response.match(/REASON:\s*(.+)/)?.[1]?.trim() ?? 'Branch scope too large'
          const subtaskMatches = [...response.matchAll(/SUBTASK_\d+:\s*(.+)/g)]
          const narrowed = response.match(/NARROWED:\s*(.+)/)?.[1]?.trim()
          const killSource = narrowed?.toUpperCase() === 'KILL'

          if (subtaskMatches.length > 0) {
            const newSubTasks = subtaskMatches.map(m => ({
              goal: m[1].trim(),
              priority: 3,
            }))

            const request: ReDecompositionRequest = {
              sourceHelixId: branch.helixId,
              reason,
              newSubTasks,
              killSource,
              narrowedGoal: killSource ? undefined : narrowed,
            }

            // Execute the re-decomposition
            this.logger.info('Re-decomposing branch', {
              helixId: branch.helixId,
              reason,
              newBranches: newSubTasks.length,
              killSource,
            })

            // Spawn new branches
            for (const subTask of newSubTasks) {
              const researchDigestContext = this.getResearchDigestContext()
              const context = researchDigestContext
                ? `${researchDigestContext}\n\nOriginal branch goal: ${branchGoal}\nRe-decomposition reason: ${reason}`
                : `Original branch goal: ${branchGoal}\nRe-decomposition reason: ${reason}`

              try {
                const newHelixId = await this.deps.launchHelix!(subTask.goal, context, undefined)
                this.logger.info('Re-decomposition: spawned new branch', {
                  newHelixId,
                  goal: subTask.goal,
                  parentHelixId: branch.helixId,
                })
              } catch (err) {
                this.logger.error('Failed to spawn re-decomposed branch', { error: String(err) })
              }
            }

            // Kill or redirect original
            if (killSource) {
              this.deps.killHelix!(branch.helixId)
              this.logger.info('Re-decomposition: killed source branch', { helixId: branch.helixId })
            } else if (narrowed) {
              this.performDirectInjection(branch.helixId,
                `🔄 SCOPE CHANGE: Your goal has been narrowed. New goal: ${narrowed}\n` +
                `Other aspects of your original goal have been delegated to new branches. ` +
                `Focus exclusively on: ${narrowed}`,
                'critical')
            }

            this.reDecompositions.push(request)

            this.emitEvent('corpus:redecomposition', {
              helixId: branch.helixId,
              reason,
              newBranches: newSubTasks.length,
              killSource,
            })
          }
        }
      } catch (err) {
        this.logger.error('Re-decomposition evaluation failed', {
          helixId: branch.helixId,
          error: String(err),
        })
      }
    }
  }



  /**
   * Inject a critical message directly into a Helix session, bypassing Brainstem.
   * Pauses the session, injects the message, then resumes.
   */
  private performDirectInjection(helixId: string, message: string, urgency: 'critical' | 'high' | 'normal'): void {
    if (!this.config.proactive.enableDirectInjection) {
      // Fall back to normal directive
      this.sendDirective({
        targetHelixId: helixId,
        type: 'redirect',
        urgency: urgency === 'critical' ? 'critical' : 'high',
        reason: 'Direct injection fallback',
        text: message,
        timestamp: Date.now(),
      })
      return
    }

    const injection: DirectInjection = {
      targetHelixId: helixId,
      message,
      urgency,
      paused: false,
      timestamp: Date.now(),
    }

    // Try pause-inject-resume if hooks available
    if (this.deps.pauseHelix && this.deps.resumeHelix && this.deps.injectGuidance) {
      const paused = this.deps.pauseHelix(helixId)
      injection.paused = paused
      const pauseStart = Date.now()

      // Inject via guidance queue with critical urgency
      const guidanceUrgency = urgency === 'critical' ? 'critical' as const
        : urgency === 'high' ? 'high' as const
        : 'medium' as const
      this.deps.injectGuidance(helixId, message, guidanceUrgency)

      // Resume immediately
      if (paused) {
        this.deps.resumeHelix(helixId)
        injection.pauseDurationMs = Date.now() - pauseStart
      }

      this.logger.info('Direct injection performed', {
        helixId,
        urgency,
        paused,
        pauseDurationMs: injection.pauseDurationMs,
      })
    } else {
      // Fallback: send via Brainstem
      const brainstem = this.childBrainstems.get(helixId)
      if (brainstem) {
        brainstem.onCorpusDirective?.({
          targetHelixId: helixId,
          type: 'redirect',
          urgency: urgency === 'critical' ? 'critical' : 'high',
          reason: 'Direct injection fallback',
          text: message,
          timestamp: Date.now(),
        })
      }
    }

    this.directInjections.push(injection)
  }



  /**
   * When a research branch completes, build a full digest of its findings
   * for injection into implementation branches.
   */
  private buildResearchDigests(): void {
    const branches = this.tree.getAllBranches()

    for (const branch of branches) {
      if (branch.status !== 'completed') continue

      // Check if this branch's assessment marks it as research
      const assessment = this.state.branchAssessments.get(branch.helixId)
      if (!assessment || assessment.researchDigestBuilt) continue

      // Determine if this was a research branch (by template or annotation pattern)
      const template = this.deps.getHelixTemplate?.(branch.helixId)
      const isResearch = template === 'research' ||
        branch.steps.filter(s => s.annotation.annotation === 'exploration' || s.annotation.annotation === 'research').length
          > branch.steps.length * 0.5

      if (!isResearch) {
        assessment.researchDigestBuilt = true // Mark so we don't re-check
        continue
      }

      const digest: ResearchDigest = {
        sourceHelixId: branch.helixId,
        goal: branch.goal ?? 'unknown',
        annotations: branch.steps.map((s, idx) => ({
          step: idx,
          type: s.annotation.annotation,
          summary: s.annotation.synthesis,
          scores: {
            goalAlignment: s.annotation.goalAlignment,
            novelty: s.annotation.novelty,
            progress: s.annotation.progress,
          },
        })),
        discoveries: assessment.discoveries,
        filesExplored: [...new Set(
          branch.steps.flatMap(s =>
            (s.toolCalls ?? []).filter(tc => tc.name === 'read_file' || tc.name === 'list_directory')
              .flatMap(tc => extractFilePaths(tc.args))
          )
        )],
        filesModified: [...assessment.filesModified],
        architectureNotes: branch.steps
          .filter(s => s.annotation.novelty >= 0.7)
          .map(s => s.annotation.synthesis),
        conclusion: branch.steps[branch.steps.length - 1]?.annotation.synthesis ?? '',
        createdAt: Date.now(),
      }

      this.researchDigests.push(digest)
      assessment.researchDigestBuilt = true

      this.logger.info('Research digest built', {
        helixId: branch.helixId,
        discoveries: digest.discoveries.length,
        filesExplored: digest.filesExplored.length,
        annotationCount: digest.annotations.length,
      })

      // Inject digest into all active implementation branches
      this.injectResearchDigest(digest)
    }
  }

  /**
   * Inject a research digest into active implementation branches.
   */
  private injectResearchDigest(digest: ResearchDigest): void {
    const branches = this.tree.getAllBranches().filter(b => b.status === 'active')

    const digestText = [
      `📋 RESEARCH FINDINGS from branch ${digest.sourceHelixId}:`,
      `Goal: ${digest.goal}`,
      ``,
      `Key Discoveries:`,
      ...digest.discoveries.map(d => `  - ${d}`),
      ``,
      digest.filesExplored.length > 0
        ? `Files Explored: ${digest.filesExplored.slice(0, 20).join(', ')}${digest.filesExplored.length > 20 ? ` (+${digest.filesExplored.length - 20} more)` : ''}`
        : '',
      ``,
      digest.architectureNotes.length > 0
        ? `Architecture Notes:\n${digest.architectureNotes.map(n => `  - ${n}`).join('\n')}`
        : '',
      ``,
      `Conclusion: ${digest.conclusion}`,
    ].filter(Boolean).join('\n')

    for (const branch of branches) {
      const template = this.deps.getHelixTemplate?.(branch.helixId)
      const isImpl = template === 'implementation' || template === 'standard'

      if (isImpl) {
        this.performDirectInjection(branch.helixId, digestText, 'high')

        const assessment = this.state.branchAssessments.get(branch.helixId)
        if (assessment) {
          assessment.contextInjectionsReceived++
        }

        this.contextInjections.push({
          targetHelixId: branch.helixId,
          source: 'research_digest',
          content: digestText,
          reason: `Research branch ${digest.sourceHelixId} completed`,
          tokenEstimate: Math.ceil(digestText.length / 4),
          timestamp: Date.now(),
        })
      }
    }
  }

  /** Get combined research digest context for new branches */
  private getResearchDigestContext(): string | undefined {
    if (this.researchDigests.length === 0) return undefined

    return this.researchDigests.map(d => [
      `## Research from ${d.sourceHelixId}: ${d.goal}`,
      d.discoveries.map(disc => `- ${disc}`).join('\n'),
      d.architectureNotes.length > 0
        ? `Architecture: ${d.architectureNotes.join('; ')}`
        : '',
      `Files: ${d.filesExplored.slice(0, 15).join(', ')}`,
      `Conclusion: ${d.conclusion}`,
    ].filter(Boolean).join('\n')).join('\n\n')
  }



  /**
   * Run quality gates on branches that have just completed.
   */
  private async runQualityGates(): Promise<void> {
    if (!this.deps.runCommand) return

    const branches = this.tree.getAllBranches()

    for (const branch of branches) {
      if (branch.status !== 'completed') continue
      if (this.qualityGateResults.has(branch.helixId)) continue

      const assessment = this.state.branchAssessments.get(branch.helixId)
      if (!assessment) continue

      // Only run quality gates on branches that modified files
      const modifiedFiles = [...assessment.filesModified]
      if (modifiedFiles.length === 0) {
        // No files modified — skip gates but record pass
        this.qualityGateResults.set(branch.helixId, {
          passed: true,
          gates: [{ name: 'files_exist', passed: true, details: 'No files modified (research branch)' }],
          durationMs: 0,
        })
        continue
      }

      const startTime = Date.now()
      const gates: QualityGateCheck[] = []

      // Gate 1: Files exist
      try {
        const missingFiles: string[] = []
        for (const filePath of modifiedFiles.slice(0, 20)) {
          if (this.deps.readFile) {
            const content = await this.deps.readFile(filePath)
            if (content === null) missingFiles.push(filePath)
          }
        }
        gates.push({
          name: 'files_exist',
          passed: missingFiles.length === 0,
          details: missingFiles.length === 0
            ? `All ${modifiedFiles.length} modified files exist`
            : `${missingFiles.length} files not found`,
          failedFiles: missingFiles.length > 0 ? missingFiles : undefined,
        })
      } catch (err) {
        gates.push({ name: 'files_exist', passed: false, details: `Error: ${String(err)}` })
      }

      // Gate 2: Type check (tsc --noEmit)
      try {
        const result = await this.deps.runCommand('npx tsc --noEmit 2>&1 | tail -20', 60_000)
        const hasErrors = result.exitCode !== 0
        // Count only NEW errors related to our files
        const tsErrors = result.stdout.split('\n').filter(l =>
          modifiedFiles.some(f => l.includes(f)) && l.includes('error TS')
        )
        gates.push({
          name: 'type_check',
          passed: tsErrors.length === 0,
          details: tsErrors.length === 0
            ? 'Type check passed (no errors in modified files)'
            : `${tsErrors.length} type errors in modified files`,
          failedFiles: tsErrors.length > 0 ? [...new Set(tsErrors.map(l => l.split('(')[0].trim()))] : undefined,
        })
      } catch (err) {
        gates.push({ name: 'type_check', passed: false, details: `Error: ${String(err)}` })
      }

      // Gate 3: Test discovery and execution
      try {
        const testFiles = modifiedFiles.filter(f =>
          f.includes('.test.') || f.includes('.spec.') || f.includes('__tests__')
        )
        if (testFiles.length > 0) {
          const result = await this.deps.runCommand(
            `npx vitest run ${testFiles.join(' ')} --reporter=verbose 2>&1 | tail -30`,
            90_000
          )
          gates.push({
            name: 'tests',
            passed: result.exitCode === 0,
            details: result.exitCode === 0
              ? `Tests passed for ${testFiles.length} test files`
              : `Tests failed: ${result.stdout.split('\n').filter(l => l.includes('FAIL')).join('; ')}`,
            failedFiles: result.exitCode !== 0 ? testFiles : undefined,
          })
        } else {
          gates.push({
            name: 'tests',
            passed: true,
            details: 'No test files in modified files (skipped)',
          })
        }
      } catch (err) {
        gates.push({ name: 'tests', passed: false, details: `Error: ${String(err)}` })
      }

      // Gate 4: Placeholder/TODO scan
      try {
        const placeholderFiles: string[] = []
        for (const filePath of modifiedFiles.slice(0, 20)) {
          if (this.deps.readFile) {
            const content = await this.deps.readFile(filePath)
            if (content) {
              const hasPlaceholders = /\/\/\s*(TODO|FIXME|PLACEHOLDER|HACK|XXX)/i.test(content) ||
                /return\s+0\.5\s*[;]?\s*\/\//i.test(content) ||
                /['"]placeholder['"]/i.test(content)
              if (hasPlaceholders) placeholderFiles.push(filePath)
            }
          }
        }
        gates.push({
          name: 'placeholder_scan',
          passed: placeholderFiles.length === 0,
          details: placeholderFiles.length === 0
            ? 'No placeholder/TODO markers found'
            : `Found placeholder markers in ${placeholderFiles.length} files`,
          failedFiles: placeholderFiles.length > 0 ? placeholderFiles : undefined,
        })
      } catch (err) {
        gates.push({ name: 'placeholder_scan', passed: false, details: `Error: ${String(err)}` })
      }

      const allPassed = gates.every(g => g.passed)
      const result: QualityGateResult = {
        passed: allPassed,
        gates,
        durationMs: Date.now() - startTime,
      }

      this.qualityGateResults.set(branch.helixId, result)

      this.logger.info('Quality gates completed', {
        helixId: branch.helixId,
        passed: allPassed,
        gates: gates.map(g => `${g.name}:${g.passed ? 'pass' : 'FAIL'}`).join(', '),
        durationMs: result.durationMs,
      })

      // If quality gates failed, emit event
      if (!allPassed) {
        this.emitEvent('corpus:qualityGateFailed', {
          helixId: branch.helixId,
          failedGates: gates.filter(g => !g.passed).map(g => g.name),
        })
      }
    }
  }



  /**
   * When a branch shows consistently high scores, evaluate whether its
   * remaining work can be split into parallel sub-branches for speed.
   */
  private async evaluateParallelAcceleration(): Promise<void> {
    if (!this.deps.launchHelix) return

    const branches = this.tree.getAllBranches().filter(b => b.status === 'active')

    for (const branch of branches) {
      const assessment = this.state.branchAssessments.get(branch.helixId)
      if (!assessment) continue

      // Check for high-score streak
      const recentScores = assessment.scoreTrajectory.slice(-this.config.proactive.parallelSplitMinStreak)
      if (recentScores.length < this.config.proactive.parallelSplitMinStreak) continue

      const allHighScores = recentScores.every(s => s >= this.config.proactive.parallelSplitMinScore)
      if (!allHighScores) continue

      // Don't re-evaluate branches we've already split
      if (this.parallelSplits.some(ps => ps.sourceHelixId === branch.helixId)) continue

      // Must have significant budget remaining (at least 40%)
      const budget = this.branchBudgets.get(branch.helixId)
      if (budget && budget.consumedSteps > budget.maxSteps * 0.6) continue

      // Ask LLM if the branch can be parallelized
      try {
        const branchGoal = branch.goal ?? 'unknown'
        const recentAnnotations = branch.steps.slice(-5).map((s, idx) =>
          `Step ${branch.steps.length - 5 + idx}: [${s.annotation.annotation}] ${s.annotation.synthesis} (progress=${s.annotation.progress.toFixed(2)})`
        ).join('\n')

        const prompt = [
          `Branch ${branch.helixId} is performing well on: "${branchGoal}"`,
          ``,
          `Recent annotations:`,
          recentAnnotations,
          ``,
          `Can this branch's remaining work be split into parallel tracks?`,
          `Only split if there are clearly independent sub-tasks remaining.`,
          ``,
          `Respond with:`,
          `NO_SPLIT — keep as-is`,
          `SPLIT:`,
          `  REASON: <why splitting helps>`,
          `  CONTINUED: <narrowed goal for the original branch>`,
          `  PARALLEL_1: <goal for new parallel branch>`,
          `  PARALLEL_2: <goal for another parallel branch>`,
        ].join('\n')

        const { content: response } = await this.deps.llm.complete({
          prompt,
          modelTier: this.config.modelTier,
          maxTokens: this.config.maxTokens,
          timeoutMs: this.config.timeoutMs,
        })

        if (response.includes('SPLIT:')) {
          const reason = response.match(/REASON:\s*(.+)/)?.[1]?.trim() ?? 'Parallelizable work detected'
          const continued = response.match(/CONTINUED:\s*(.+)/)?.[1]?.trim() ?? branchGoal
          const parallelMatches = [...response.matchAll(/PARALLEL_\d+:\s*(.+)/g)]

          if (parallelMatches.length > 0) {
            const newSubTasks = parallelMatches.map(m => ({
              goal: m[1].trim(),
              priority: 3,
            }))

            const splitRequest: ParallelSplitRequest = {
              sourceHelixId: branch.helixId,
              reason,
              newSubTasks,
              continuedGoal: continued,
            }

            this.logger.info('Parallel acceleration: splitting branch', {
              helixId: branch.helixId,
              reason,
              newBranches: newSubTasks.length,
            })

            // Spawn parallel branches
            for (const subTask of newSubTasks) {
              try {
                const context = this.getResearchDigestContext() ?? ''
                const newHelixId = await this.deps.launchHelix!(subTask.goal, context || undefined, undefined)
                this.logger.info('Parallel acceleration: spawned branch', {
                  newHelixId,
                  goal: subTask.goal,
                })
              } catch (err) {
                this.logger.error('Failed to spawn parallel branch', { error: String(err) })
              }
            }

            // Redirect original branch to narrowed scope
            if (continued !== branchGoal) {
              this.performDirectInjection(branch.helixId,
                `🚀 PARALLEL ACCELERATION: Your work has been split for speed. ` +
                `New parallel branches are handling other parts. Your narrowed focus: ${continued}`,
                'high')
            }

            this.parallelSplits.push(splitRequest)

            this.emitEvent('corpus:parallelSplit', {
              helixId: branch.helixId,
              reason,
              newBranches: newSubTasks.length,
            })
          }
        }
      } catch (err) {
        this.logger.error('Parallel acceleration evaluation failed', {
          helixId: branch.helixId,
          error: String(err),
        })
      }
    }
  }



  /**
   * When a branch is struggling (low scores for multiple steps), inject
   * relevant context from code intelligence or direct file reads.
   */
  private async evaluateContextInjection(): Promise<void> {
    const branches = this.tree.getAllBranches().filter(b => b.status === 'active')
    const minSteps = this.config.proactive.contextInjectionAfterSteps

    for (const branch of branches) {
      const assessment = this.state.branchAssessments.get(branch.helixId)
      if (!assessment) continue

      // Must have enough steps and consistently low scores
      if (branch.steps.length < minSteps) continue
      if ((assessment.avgProgress ?? 0.5) > 0.4) continue
      if (assessment.contextInjectionsReceived >= 3) continue // Cap at 3 injections

      // Check recent scores are consistently low
      const recentScores = assessment.scoreTrajectory.slice(-3)
      const allLow = recentScores.length >= 3 && recentScores.every(s => s < 0.4)
      if (!allLow) continue

      // Determine what context would help
      const recentToolCalls = branch.steps.slice(-3).flatMap(s => s.toolCalls ?? [])
      const fileReads = recentToolCalls
        .filter(tc => tc.name === 'read_file')
        .flatMap(tc => extractFilePaths(tc.args))
      const searchQueries = recentToolCalls
        .filter(tc => tc.name === 'search_for_pattern' || tc.name === 'find_file')
        .map(tc => {
          try {
            const args = typeof tc.args === 'string' ? JSON.parse(tc.args) : tc.args
            return args.substring_pattern || args.file_mask || ''
          } catch { return '' }
        })
        .filter(Boolean)

      let injectedContent = ''
      let source: ContextInjection['source'] = 'code_intelligence'

      // Strategy 1: If branch is searching for files, help with direct file reads
      if (fileReads.length > 0 && this.deps.readFile) {
        const contents: string[] = []
        for (const path of fileReads.slice(0, 3)) {
          try {
            const content = await this.deps.readFile(path)
            if (content) {
              // Truncate to avoid massive injection
              const truncated = content.length > 2000 ? content.slice(0, 2000) + '\n... (truncated)' : content
              contents.push(`### ${path}\n\`\`\`\n${truncated}\n\`\`\``)
            }
          } catch { /* skip */ }
        }
        if (contents.length > 0) {
          injectedContent = `📖 CONTEXT INJECTION — Files you may need:\n\n${contents.join('\n\n')}`
          source = 'file_read'
        }
      }

      // Strategy 2: If branch is searching but not finding, inject discoveries from other branches
      if (!injectedContent && this.discoveries.size > 0) {
        const relevantDiscoveries = Array.from(this.discoveries.values())
          .filter(d => d.sourceHelixId !== branch.helixId)
          .slice(0, 5)
          .map(d => `- [${d.type}] ${d.content}`)

        if (relevantDiscoveries.length > 0) {
          injectedContent = `📖 CONTEXT INJECTION — Discoveries from other branches:\n\n${relevantDiscoveries.join('\n')}`
          source = 'cross_branch'
        }
      }

      // Strategy 3: If we have research digests, inject them
      if (!injectedContent && this.researchDigests.length > 0) {
        const digestContext = this.getResearchDigestContext()
        if (digestContext) {
          injectedContent = `📖 CONTEXT INJECTION — Research findings:\n\n${digestContext}`
          source = 'research_digest'
        }
      }

      if (injectedContent) {
        this.performDirectInjection(branch.helixId, injectedContent, 'normal')

        assessment.contextInjectionsReceived++

        this.contextInjections.push({
          targetHelixId: branch.helixId,
          source,
          content: injectedContent,
          reason: `Branch struggling for ${branch.steps.length} steps with avg progress ${(assessment.avgProgress ?? 0).toFixed(2)}`,
          tokenEstimate: Math.ceil(injectedContent.length / 4),
          timestamp: Date.now(),
        })

        this.logger.info('Context injected into struggling branch', {
          helixId: branch.helixId,
          source,
          tokenEstimate: Math.ceil(injectedContent.length / 4),
        })
      }
    }
  }



  /**
   * Build complete trajectory context for ALL branches.
   * Designed to leverage Qwen3 Max's 256k context window.
   */
  private buildFullTrajectoryContext(): string {
    const branches = this.tree.getAllBranches()
    const sections: string[] = []

    for (const branch of branches) {
      const assessment = this.state.branchAssessments.get(branch.helixId)
      const template = this.deps.getHelixTemplate?.(branch.helixId) ?? 'unknown'
      const budget = this.branchBudgets.get(branch.helixId)

      const header = [
        `### Branch: ${branch.helixId} [${branch.status}] (template: ${template})`,
        `Goal: ${branch.goal ?? 'unknown'}`,
        budget ? `Budget: ${budget.consumedSteps}/${budget.maxSteps} steps, ${Math.round(budget.consumedTimeMs / 1000)}/${Math.round(budget.maxTimeMs / 1000)}s` : '',
        assessment ? `Scores: goalAlign=${(assessment.avgGoalAlignment ?? 0).toFixed(2)} novelty=${(assessment.avgNovelty ?? 0).toFixed(2)} progress=${(assessment.avgProgress ?? 0).toFixed(2)} composite=${assessment.rollingScore.toFixed(2)}` : '',
        assessment ? `Escalation: level=${assessment.escalationLevel} ignoredDirectives=${assessment.ignoredDirectiveStreak}` : '',
        assessment?.discoveries.length ? `Discoveries: ${assessment.discoveries.length}` : '',
      ].filter(Boolean).join('\n')

      const steps = branch.steps.map((s, idx) => {
        const ann = s.annotation
        const scores = `[gA=${ann.goalAlignment.toFixed(1)} n=${ann.novelty.toFixed(1)} p=${ann.progress.toFixed(1)}]`
        const tools = (s.toolCalls ?? []).map(tc => tc.name).join(', ')
        return `  Step ${idx}: [${ann.annotation}] ${scores} ${ann.synthesis} (tools: ${tools})`
      }).join('\n')

      sections.push(`${header}\n${steps}`)
    }

    return sections.join('\n\n---\n\n')
  }


  /**
   * Record training signals from the current sweep.
   * Persists high-value events (Locus, cross-patterns, interventions,
   * effectiveness measurements) to training_signals for later ingest
   * into the training warehouse.
   */
  private recordSweepTrainingSignals(
    newPatterns: CrossHelixPattern[],
    locusSweep?: LocusSweepResult,
  ): void {
    const store = this.deps.store
    if (!store) return

    const sessionId = this.deps.constellationId

    // Locus kindling events (sparks that entered the workspace)
    if (locusSweep) {
      for (const event of locusSweep.kindlingEvents) {
        store.recordTrainingSignal(sessionId, {
          signalType: 'locus_kindling',
          sourceHelixId: event.spark.sourceHelixId,
          data: {
            sparkType: event.spark.type,
            content: event.spark.content,
            luminance: event.spark.luminance,
            slotIndex: event.slotIndex,
            eclipsed: event.eclipse ? {
              eclipsedType: event.eclipse.eclipsedSpark.type,
              luminanceDelta: event.eclipse.luminanceDelta,
              occupancyAtEclipse: event.eclipse.occupancyAtEclipse,
            } : null,
          },
          qualityScore: event.kindlingLuminance,
        })
      }

      // Locus radiance broadcasts
      for (const event of locusSweep.radianceEvents) {
        store.recordTrainingSignal(sessionId, {
          signalType: 'locus_radiance',
          sourceHelixId: event.source.spark.sourceHelixId,
          data: {
            sparkType: event.source.spark.type,
            recipientCount: event.recipients.length,
            recipientDistances: event.recipientDistances,
            kindlingLuminance: event.source.kindlingLuminance,
          },
          qualityScore: event.source.kindlingLuminance,
        })
      }

      // Locus radiance responses (measured on subsequent sweeps)
      for (const response of locusSweep.responses) {
        store.recordTrainingSignal(sessionId, {
          signalType: 'locus_response',
          sourceHelixId: response.helixId,
          data: {
            radianceId: response.radianceId,
            responseType: response.responseType,
            evidence: response.evidence,
            responseDelay: response.responseDelay,
          },
          qualityScore: response.responseType === 'incorporated' ? 1.0
            : response.responseType === 'noted' ? 0.6
            : response.responseType === 'contradicted' ? 0.3
            : 0.1,
        })
      }

      // Locus memory feedback (the closed loop: response → memory update)
      for (const feedback of locusSweep.memoryFeedback) {
        store.recordTrainingSignal(sessionId, {
          signalType: 'locus_memory_feedback',
          sourceHelixId: feedback.helixId,
          data: {
            memoryId: feedback.memoryId,
            radianceId: feedback.radianceId,
            feedbackType: feedback.feedbackType,
            evidence: feedback.evidence,
          },
          qualityScore: feedback.feedbackType === 'confirmation' ? 1.0
            : feedback.feedbackType === 'contradiction' ? 0.5
            : 0.2,
        })
      }
    }

    // Cross-branch patterns
    for (const pattern of newPatterns) {
      store.recordTrainingSignal(sessionId, {
        signalType: 'cross_pattern',
        data: {
          type: pattern.type,
          helixIds: pattern.helixIds,
          severity: pattern.severity,
          description: pattern.description,
          suggestedAction: pattern.suggestedAction,
        },
        qualityScore: pattern.severity === 'critical' ? 1.0
          : pattern.severity === 'high' ? 0.8
          : pattern.severity === 'medium' ? 0.5
          : 0.3,
      })
    }

    // Interventions sent this sweep
    const recentInterventions = this.state.interventions.filter(
      i => i.sweepNumber === this.state.sweepCount,
    )
    for (const intervention of recentInterventions) {
      store.recordTrainingSignal(sessionId, {
        signalType: 'intervention_sent',
        sourceHelixId: intervention.targetHelixId,
        data: {
          type: intervention.type,
          urgency: intervention.urgency,
          reason: intervention.reason,
          text: intervention.text,
          fromPattern: intervention.fromPattern,
          requiredAction: intervention.requiredAction,
        },
        qualityScore: intervention.urgency === 'critical' ? 1.0
          : intervention.urgency === 'high' ? 0.8
          : intervention.urgency === 'medium' ? 0.5
          : 0.3,
      })
    }
  }
}

/**
 * Factory function to create a Corpus instance
 * @dep callers: corpus-enforcement.test.ts (tests/corpus-enforcement.test.ts), corpus.test.ts (tests/corpus.test.ts)
 * @dep module: Unknown
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export function createCorpus(
  tree: ICorpusTree,
  deps: CorpusDeps,
  config?: Partial<CorpusConfig>
): Corpus {
  return new Corpus(tree, deps, config)
}
