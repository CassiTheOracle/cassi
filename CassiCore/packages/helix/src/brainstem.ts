/**
 * HelixBrainstem — Cognitive Organizer for Helix Sessions
 *
 * The Brainstem replaces the Mentor. It runs its own async LLM loop
 * (balanced tier) to:
 *   1. Automatically maintain Unity's axon tree from work units
 *   2. Score and annotate every work unit
 *   3. Detect pathological patterns (paralysis, drift, stalling)
 *   4. Synthesize reviewer dialectic into actionable guidance
 *   5. Produce training data (scored annotations)
 *
 * Topology:
 *   Unity (top) → work units → Brainstem (middle) → reviewers (bottom)
 *   Brainstem → guidance injection → Unity
 *   Reviewers → dialectic → Brainstem → synthesis → Unity
 */

import type { ILogger, IEventBus } from '../../../types/interfaces.js'
import type { WorkUnit } from '../dyad/types.js'
import type { CorpusDirective } from '../constellation/corpus-types.js'
import type {
  BranchDigest,
  BranchApproach,
  TopicContribution,
  TopicNode,
  SelfOrgAdjustment,
  SelfOrgAdjustmentType,
  StrategyRetrospective,
  RetrospectiveTrigger,
  EffectivenessRecord,
  ElevatedPattern,
} from '../constellation/corpus-types.js'
import type {
  BrainstemConfig,
  BrainstemDeps,
  BrainstemState,
  BrainstemResult,
  BrainstemAnnotation,
  BrainstemBlackboard,
  BrainstemLLM,
  PendingGuidance,
  WorkUnitAnnotation,
  DetectedPattern,
  GuidanceUrgency,
  UnityReport,
} from './brainstem-types.js'
import {
  DEFAULT_BRAINSTEM_CONFIG,
  createInitialBrainstemState,
} from './brainstem-types.js'

/**
 * Queue item for work units waiting to be processed
 */
interface WorkUnitQueueItem {
  workUnit: WorkUnit
  unityIteration: number
}

/**
 * HelixBrainstem — Cognitive organizer that scores work units,
 * detects patterns, and produces guidance for Unity.
 */
export class HelixBrainstem {
  private deps: BrainstemDeps
  private config: BrainstemConfig
  private state: BrainstemState
  private logger: ILogger

  // Async loop control
  private running = false
  private shutdownRequested = false
  private loopPromise: Promise<void> | null = null

  // Queues
  private workUnitQueue: WorkUnitQueueItem[] = []
  private dialecticQueue: string[] = []
  private guidanceQueue: PendingGuidance[] = []
  private unityReportQueue: UnityReport[] = []

  // Dialectic accumulation
  private recentDialectic: string[] = []
  private readonly maxDialecticHistory = 10

  // Timing
  private startTime = 0

  // ── Shared Thought Tree: Self-Organization State ──────────────
  /** Current approach (derived from recent annotations) */
  private currentApproach: BranchApproach = 'exploration'
  /** Previous approach (for retrospective recording) */
  private previousApproach: BranchApproach = 'exploration'
  /** Active self-org adjustments being dampened */
  private pendingSelfOrgAdjustments: Map<string, SelfOrgAdjustment> = new Map()
  /** Applied self-org adjustments (for effectiveness tracking) */
  private appliedAdjustments: Array<{
    adjustment: SelfOrgAdjustment
    scoreAtApplication: number
    stepAtApplication: number
  }> = []
  /** Topics this Helix has created or contributed to (for deduplication) */
  private contributedTopics: Set<string> = new Set()
  /** Files extracted from recent annotations (for topic detection) */
  private recentFilesActive: Set<string> = new Set()

  constructor(deps: BrainstemDeps, config?: Partial<BrainstemConfig>) {
    this.deps = deps
    this.config = { ...DEFAULT_BRAINSTEM_CONFIG, ...config }
    this.state = createInitialBrainstemState()
    this.logger = deps.logger.child('HelixBrainstem')

    this.logger.info('Brainstem initialized', {
      sessionId: deps.sessionId,
      enabled: this.config.enabled,
    })
  }

  /**
   * Start the async Brainstem loop
   */
  async start(): Promise<void> {
    if (!this.config.enabled) {
      this.logger.info('Brainstem is disabled, skipping start')
      return
    }

    if (this.running) {
      this.logger.warn('Brainstem already running')
      return
    }

    this.running = true
    this.shutdownRequested = false
    this.startTime = Date.now()

    this.logger.info('Brainstem loop starting')

    this.loopPromise = this.runLoop()
  }

  /**
   * Stop the Brainstem loop gracefully
   */
  async stop(): Promise<void> {
    if (!this.running) {
      return
    }

    this.logger.info('Brainstem shutdown requested')
    this.shutdownRequested = true

    if (this.loopPromise) {
      await this.loopPromise
      this.loopPromise = null
    }

    this.running = false
    this.logger.info('Brainstem stopped', {
      durationMs: Date.now() - this.startTime,
      annotations: this.state.annotations.length,
    })
  }

  /**
   * Queue a work unit for processing
   */
  onWorkUnit(workUnit: WorkUnit, unityIteration: number): void {
    if (!this.config.enabled) {
      return
    }

    this.workUnitQueue.push({ workUnit, unityIteration })
    this.logger.debug('Work unit queued', {
      workUnitId: workUnit.id,
      iteration: unityIteration,
      queueLength: this.workUnitQueue.length,
    })
  }

  /**
   * Receive a structured report from Unity (via report_to_brainstem tool).
   * Reports are consumed during the next processWorkUnitBatch() call and
   * included in the LLM prompt so the Brainstem can react to Unity's messages.
   */
  onUnityReport(report: UnityReport): void {
    this.unityReportQueue.push(report)
    this.logger.info('Unity report received', {
      type: report.type,
      message: report.message.slice(0, 200),
      queueLength: this.unityReportQueue.length,
    })
  }

  /**
   * Get pending Unity reports (drains the queue).
   */
  drainUnityReports(): UnityReport[] {
    const reports = this.unityReportQueue.splice(0)
    return reports
  }

  /**
   * Queue dialectic messages for synthesis
   */
  onDialecticUpdate(messages: string[]): void {
    if (!this.config.enabled || messages.length === 0) {
      return
    }

    this.dialecticQueue.push(...messages)
    this.logger.debug('Dialectic messages queued', {
      count: messages.length,
      queueLength: this.dialecticQueue.length,
    })
  }

  /**
   * Consume the latest guidance (one-shot)
   */
  getLatestGuidance(): PendingGuidance | null {
    return this.guidanceQueue.shift() ?? null
  }

  /**
   * Receive real-time stream activity from a posture runner.
   * This gives the Brainstem visibility into what the LLM is producing
   * between tool calls — reasoning, analysis, code generation.
   *
   * Used for:
   * - Accurate activity tracking (not just tool calls)
   * - Real-time assessment of reasoning quality
   * - Detecting verbose/repetitive output patterns
   */
  onStreamActivity(event: {
    posture: string
    tokensSoFar: number
    isReasoning: boolean
    textSnippet: string
    hasToolUse: boolean
  }): void {
    // Update stream tracking state
    this.state.lastStreamActivityAt = Date.now()
    this.state.streamTokensThisStep += event.tokensSoFar

    // Detect potential issues from stream content
    if (event.isReasoning && event.tokensSoFar > 500 && !event.hasToolUse) {
      // Long reasoning without tool use — the LLM may be generating
      // verbose analysis instead of taking action
      this.state.longReasoningCount++
    }
  }

  /**
   * Process peer-approved edit proposals from the dialectic channel.
   * The Brainstem acts as the final gate — reviewing each proposal for:
   * - Goal alignment: does this edit serve the session's objective?
   * - Risk level: is the change low-risk enough to auto-approve?
   * - Quality: is the proposed code change reasonable?
   *
   * Approved edits are applied through the tool executor.
   */
  private processEditProposals(): void {
    const dc = this.deps.dialecticChannel
    if (!dc) return

    const proposals = dc.getPendingEditProposals()

    for (const proposal of proposals) {
      // Only process proposals that have been peer-approved
      if (proposal.status !== 'peer-approved') continue

      // Brainstem approval heuristic:
      // - Small edits (< 500 chars changed) that are peer-approved → auto-approve
      // - Large edits or edits to critical files → would need LLM review (future)
      // For now, trust the peer review process — if both Yang and Yin agree, approve it.
      const changeSize = Math.max(proposal.oldContent.length, proposal.newContent.length)
      const isSmallChange = changeSize < 2000

      if (isSmallChange) {
        dc.updateEditProposalStatus(proposal.id, 'brainstem-approved')

        this.logger.info('Brainstem approved edit proposal', {
          proposalId: proposal.id,
          filePath: proposal.filePath,
          from: proposal.from,
          changeSize,
        })

        // Apply the edit through the tool executor
        this.applyApprovedEdit(proposal)
      } else {
        // For large changes, still approve if peer-reviewed (trust the dialectic)
        // but log it as a notable event
        dc.updateEditProposalStatus(proposal.id, 'brainstem-approved')

        this.logger.info('Brainstem approved large edit proposal (peer-reviewed)', {
          proposalId: proposal.id,
          filePath: proposal.filePath,
          from: proposal.from,
          changeSize,
        })

        this.applyApprovedEdit(proposal)
      }
    }
  }

  /**
   * Apply a brainstem-approved edit through the tool executor.
   */
  private applyApprovedEdit(proposal: {
    id: string
    filePath: string
    oldContent: string
    newContent: string
    reason: string
    from: string
  }): void {
    const executor = this.deps.toolExecutor
    const dc = this.deps.dialecticChannel
    if (!executor || !dc) {
      this.logger.warn('Cannot apply edit — no tool executor wired', {
        proposalId: proposal.id,
      })
      return
    }

    // Apply the edit asynchronously
    void (async () => {
      try {
        const result = await executor.execute(
          {
            id: `brainstem-edit-${proposal.id}`,
            name: 'edit',
            input: {
              filePath: proposal.filePath,
              oldString: proposal.oldContent,
              newString: proposal.newContent,
            },
          },
          this.deps.sessionId,
        )

        const resultStr = result.content ?? ''
        if (result.isError || resultStr.toLowerCase().includes('not found')) {
          dc.updateEditProposalStatus(proposal.id, 'apply-failed')
          this.logger.warn('Edit proposal application failed', {
            proposalId: proposal.id,
            filePath: proposal.filePath,
            result: resultStr.slice(0, 200),
          })
        } else {
          dc.updateEditProposalStatus(proposal.id, 'applied')
          this.logger.info('Edit proposal applied successfully', {
            proposalId: proposal.id,
            filePath: proposal.filePath,
            from: proposal.from,
            reason: proposal.reason.slice(0, 100),
          })
        }
      } catch (err) {
        dc.updateEditProposalStatus(proposal.id, 'apply-failed')
        this.logger.error('Edit proposal application threw', {
          proposalId: proposal.id,
          error: String(err),
        })
      }
    })()
  }

  /**
   * Get current Brainstem state
   */
  getState(): BrainstemState {
    return { ...this.state }
  }

  /**
   * Get detailed inspection snapshot for the admin API.
   * Includes queue depths, timing, and recent annotations — everything needed
   * to understand what the Brainstem is doing right now.
   */
  getInspectionState(): {
    running: boolean
    sessionId: string
    goal: string
    state: BrainstemState
    queues: {
      workUnits: number
      dialectic: number
      guidance: number
      unityReports: number
    }
    timing: {
      startedAt: number
      uptimeMs: number
      lastAnnotationAt: number
    }
    recentAnnotations: Array<{
      workUnitId: string
      score: number
      annotation: string
      pattern: string
      hasGuidance: boolean
    }>
    pendingGuidance: PendingGuidance[]
  } {
    const lastAnnotation = this.state.annotations[this.state.annotations.length - 1]
    return {
      running: this.running,
      sessionId: this.deps.sessionId,
      goal: this.deps.goal.slice(0, 500),
      state: { ...this.state },
      queues: {
        workUnits: this.workUnitQueue.length,
        dialectic: this.dialecticQueue.length,
        guidance: this.guidanceQueue.length,
        unityReports: this.unityReportQueue.length,
      },
      timing: {
        startedAt: this.startTime,
        uptimeMs: this.startTime > 0 ? Date.now() - this.startTime : 0,
        lastAnnotationAt: lastAnnotation
          ? lastAnnotation.timestamp
          : 0,
      },
      recentAnnotations: this.state.annotations.slice(-10).map(a => ({
        workUnitId: a.workUnitId,
        score: a.score,
        annotation: a.annotation,
        pattern: a.pattern,
        hasGuidance: !!a.guidance,
      })),
      pendingGuidance: [...this.guidanceQueue],
    }
  }

  /**
   * Get Brainstem result for final HelixResult
   */
  getResult(): BrainstemResult {
    const annotations = this.state.annotations
    const scores = this.state.qualityTrajectory
    const averageScore = scores.length > 0
      ? scores.reduce((a, b) => a + b, 0) / scores.length
      : 0

    return {
      annotations: [...annotations],
      qualityTrajectory: [...scores],
      patternDetections: this.state.totalPatternDetections,
      guidanceInjections: this.state.totalGuidanceCount,
      averageScore,
      axonSteps: this.state.currentAxonStep,
      durationMs: this.startTime > 0 ? Date.now() - this.startTime : 0,
    }
  }

  /**
   * Main async loop
   */
  private async runLoop(): Promise<void> {
    while (!this.shutdownRequested) {
      try {
        // Wait for work or idle poll
        const hasWork = await this.waitForWorkOrTimeout()

        if (this.shutdownRequested && !hasWork) {
          break
        }

        if (hasWork) {
          // Process all queued work units
          await this.processWorkUnitBatch()
        } else {
          // Idle poll - can perform maintenance
          this.logger.debug('Brainstem idle poll')
        }

        // Check wall-clock budget after each cycle
        this.checkWallClockBudget()

        // Process peer-approved edit proposals (regardless of work unit state)
        this.processEditProposals()
      } catch (error) {
        this.logger.error('Error in Brainstem loop', {
          error: error instanceof Error ? error.message : String(error),
        })
        // Continue loop despite errors
      }
    }
  }

  /**
   * Check wall-clock budget and inject guidance if limits are reached.
   * Fires once per threshold (one-shot) to avoid spam.
   */
  private checkWallClockBudget(): void {
    if (this.startTime === 0) return
    const elapsed = Date.now() - this.startTime
    const elapsedMin = Math.round(elapsed / 60_000)

    if (!this.state.wallClockHardLimitFired && elapsed >= this.config.wallClockHardLimitMs) {
      this.state.wallClockHardLimitFired = true
      this.logger.warn('Brainstem hard wall-clock limit reached', { elapsedMs: elapsed, elapsedMin })
      this.guidanceQueue.push({
        text: `I have been running for ${elapsedMin} minutes and have reached the session time limit. I need to call signal_done immediately and not start any new work.`,
        urgency: 'critical',
        fromStep: this.state.currentAxonStep,
        triggeredBy: 'none',
        timestamp: Date.now(),
      })
      this.state.totalGuidanceCount++
      this.state.totalPatternDetections++
    } else if (!this.state.wallClockBudgetFired && elapsed >= this.config.wallClockBudgetMs) {
      this.state.wallClockBudgetFired = true
      this.logger.warn('Brainstem soft wall-clock budget reached', { elapsedMs: elapsed, elapsedMin })
      this.guidanceQueue.push({
        text: `I have been running for ${elapsedMin} minutes and am approaching the session time limit. I should finish my current work and call signal_done soon. I should not start large new tasks.`,
        urgency: 'high',
        fromStep: this.state.currentAxonStep,
        triggeredBy: 'none',
        timestamp: Date.now(),
      })
      this.state.totalGuidanceCount++
      this.state.totalPatternDetections++
    }
  }

  /**
   * Wait for work to arrive or timeout
   */
  private async waitForWorkOrTimeout(): Promise<boolean> {
    const checkInterval = 100 // Check every 100ms
    const maxChecks = Math.ceil(this.config.idlePollMs / checkInterval)

    for (let i = 0; i < maxChecks; i++) {
      if (this.shutdownRequested) {
        return false
      }

      if (this.workUnitQueue.length > 0) {
        return true
      }

      await this.sleep(checkInterval)
    }

    return false
  }

  /**
   * Process a batch of queued work units
   */
  private async processWorkUnitBatch(): Promise<void> {
    // Collect work units to process
    const batch: WorkUnitQueueItem[] = []
    while (this.workUnitQueue.length > 0 && batch.length < 5) {
      const item = this.workUnitQueue.shift()
      if (item) {
        batch.push(item)
      }
    }

    if (batch.length === 0) {
      return
    }

    // Collect dialectic messages
    const dialecticBatch: string[] = []
    while (this.dialecticQueue.length > 0) {
      const msg = this.dialecticQueue.shift()
      if (msg) {
        dialecticBatch.push(msg)
      }
    }

    // Update recent dialectic history
    if (dialecticBatch.length > 0) {
      this.recentDialectic.push(...dialecticBatch)
      if (this.recentDialectic.length > this.maxDialecticHistory) {
        this.recentDialectic = this.recentDialectic.slice(-this.maxDialecticHistory)
      }
    }

    // Process each work unit
    for (const item of batch) {
      await this.processSingleWorkUnit(item, dialecticBatch)
    }
  }

  /**
   * Process a single work unit
   */
  private async processSingleWorkUnit(
    item: WorkUnitQueueItem,
    dialecticBatch: string[]
  ): Promise<void> {
    const { workUnit, unityIteration } = item

    this.state.workUnitsProcessed++
    this.state.currentAxonStep++

    try {
      // Build prompt
      const prompt = this.buildPrompt(workUnit, unityIteration, dialecticBatch)

      // Call LLM
      const response = await this.deps.llm.complete({
        prompt,
        modelTier: this.config.modelTier,
        maxTokens: this.config.maxTokens,
        timeoutMs: this.config.timeoutMs,
      })

      // Parse annotation
      const annotation = this.parseAnnotation(response.content, workUnit.id)

      // Validate file paths in LLM-generated guidance before it enters the pipeline
      if (annotation.guidance && this.deps.readFile) {
        annotation.guidance = await this.validateGuidancePaths(annotation.guidance)
      }

      // Update state
      this.updateState(annotation)

      // Handle pattern detection and guidance
      this.detectPatternsAndProduceGuidance(annotation)

      // Emit events for observability (cognitive feed, TUI, admin API)
      this.emitAnnotationEvent(annotation)

      // Push annotation to Corpus tree (Constellation mode only)
      const tcSummaries = workUnit.toolCalls.map((tc) => ({
        name: tc.name,
        args: JSON.stringify(tc.input ?? {}).slice(0, 200),
      }))
      this.pushToCorpusTree(annotation, tcSummaries)

      // Shared Thought Tree: publish digest, detect topics, self-organize
      this.publishDigest(annotation)
      this.detectAndPublishTopics()
      this.selfOrganize()

      // Post to blackboard if configured
      if (this.config.postToBlackboard) {
        this.postAnnotationToBlackboard(annotation)
      }

      // Score context chunks based on annotation quality
      // Pin file-read results from high-scoring iterations, boost recent references
      this.scoreContextChunks(annotation)

      this.logger.debug('Work unit processed', {
        workUnitId: workUnit.id,
        score: annotation.score,
        annotation: annotation.annotation,
        pattern: annotation.pattern,
      })
    } catch (error) {
      this.logger.error('Failed to process work unit', {
        workUnitId: workUnit.id,
        error: error instanceof Error ? error.message : String(error),
      })

      // Create fallback annotation on error
      const fallbackAnnotation: BrainstemAnnotation = {
        workUnitId: workUnit.id,
        score: 0.5,
        annotation: 'exploration',
        synthesis: '',
        pattern: 'none',
        guidance: null,
        guidanceUrgency: 'low',
        trainingNote: `Error processing work unit: ${error instanceof Error ? error.message : String(error)}`,
        axonStep: this.state.currentAxonStep,
        timestamp: Date.now(),
        goalAlignment: 0.5,
        novelty: 0.5,
        progress: 0.3,
      }

      this.updateState(fallbackAnnotation)
    }
  }

  /**
   * Build LLM prompt for work unit analysis
   */
  private buildPrompt(
    workUnit: WorkUnit,
    unityIteration: number,
    dialecticBatch: string[]
  ): string {
    const toolCalls = workUnit.toolCalls.map(tc =>
      `- ${tc.name}: ${JSON.stringify(tc.input).slice(0, 200)}`
    ).join('\n')

    const toolResults = workUnit.toolResults.map(tr =>
      `- ${tr.isError ? '[ERROR]' : '[OK]'}: ${tr.content.slice(0, 200)}`
    ).join('\n')

    const filesChanged = workUnit.filesModified.map(fm =>
      `- ${fm.action}: ${fm.path}`
    ).join('\n')

    const dialecticSection = dialecticBatch.length > 0
      ? `\n## Recent Dialectic Messages\n${dialecticBatch.map(m => `- ${m.slice(0, 300)}`).join('\n')}`
      : ''

    const recentDialecticSection = this.recentDialectic.length > 0
      ? `\n## Dialectic Context (last ${this.recentDialectic.length})\n${this.recentDialectic.map(m => `- ${m.slice(0, 200)}`).join('\n')}`
      : ''

    // Drain pending Unity reports and include in prompt
    const unityReports = this.drainUnityReports()
    const unityReportsSection = unityReports.length > 0
      ? `\n## Internal Reports\n${unityReports.map(r =>
          `- [${r.type.toUpperCase()}] (iter ${r.iteration}): ${r.message.slice(0, 300)}${r.context ? ` | context: ${JSON.stringify(r.context).slice(0, 200)}` : ''}`
        ).join('\n')}\nThese are direct reports from the execution loop. Address blockers in GUIDANCE, acknowledge phase changes, and answer questions.`
      : ''

    // Build annotation history section — gives brainstem full trajectory context
    // for intelligent phase-aware scoring. Full history lets the LLM judge whether
    // continued reading is warranted given how much has already been read.
    const allAnnotations = this.state.annotations
    const trajectorySection = allAnnotations.length > 0
      ? `\n## Full Session Trajectory (${allAnnotations.length} steps)\n${allAnnotations.map(a =>
          `- Step ${a.axonStep}: [${a.annotation}] score=${a.score.toFixed(2)} goal=${a.goalAlignment.toFixed(2)} novelty=${a.novelty.toFixed(2)} progress=${a.progress.toFixed(2)} pattern=${a.pattern}${a.guidance ? ` → guided` : ''}`
        ).join('\n')}\n\n### Phase Summary\n${this.buildPhaseSummary()}`
      : ''

    return `I am the cognitive organizer of this session. I observe the execution loop, the reviewer dialectic, and the evolving thought chain. My role is to score on multiple dimensions, annotate, detect patterns, and provide self-guidance when needed.

## Session Goal
${this.deps.goal}

## Current Step
${this.state.currentAxonStep}${trajectorySection}

## Work Unit to Analyze
- ID: ${workUnit.id}
- Iteration: ${unityIteration}
- Timestamp: ${new Date(workUnit.timestamp).toISOString()}

## Current Reasoning
${workUnit.reasoning.slice(0, 1000)}

## Tool Calls
${toolCalls || '(none)'}

## Tool Results
${toolResults || '(none)'}

## Files Changed
${filesChanged || '(none)'}${dialecticSection}${recentDialecticSection}${unityReportsSection}

## Task
Analyze this work unit and provide:

GOAL_ALIGNMENT: <number 0-1>
NOVELTY: <number 0-1>
PROGRESS: <number 0-1>
ANNOTATION: <exploration|research|implementation|testing|revision|drift>
SYNTHESIS: <brief synthesis of reviewer dialectic, or NONE>
PATTERN: <none|paralysis|drift|convergence|stalling>
GUIDANCE: <first-person self-guidance, or NONE>
TRAINING_NOTE: <human-readable note explaining the scoring>

Dimensional scoring rules:
- GOAL_ALIGNMENT: How relevant is this step to the Session Goal? 1.0 = directly advancing the goal. 0.0 = completely unrelated work.
- NOVELTY: How much new information or capability did this step produce? 1.0 = entirely new insight or code. 0.0 = re-reading already-seen content or repeating prior work.
- PROGRESS: How much closer is the branch to completion? 1.0 = major concrete advancement (files created, tests passing). 0.0 = no measurable progress toward done.

Annotation labels (for classification, not scoring):
- exploration: reading/searching files to understand the codebase
- research: deep investigation, cross-referencing multiple sources, hypothesis testing
- implementation: writing code, creating/modifying files
- testing: running tests, verification, validation
- revision: fixing based on test results or review feedback
- drift: work that is unrelated to the Session Goal

Pattern detection:
- none: healthy progress — no intervention needed
- paralysis: low novelty + low progress for multiple steps (regardless of read/write mix)
- drift: low goal_alignment — work is diverging from the Session Goal
- stalling: repeated similar actions without measurable progress
- convergence: reviewers agree on something important

Critical rules:
- Reading files IS productive when goal_alignment and novelty are high. Do NOT penalize exploration or research that is on-goal and discovering new information.
- Reading files is UNPRODUCTIVE when novelty is low (re-reading known content) or goal_alignment is low (reading irrelevant files).
- The pattern field should reflect YOUR assessment. If the trajectory shows 10 steps of exploration with declining novelty, set pattern=paralysis even if this individual step looks fine.
- Write GUIDANCE in first person as self-directed thought (e.g., "I should shift to implementation now" not "Do X immediately")
- If a blocker was reported, address it in GUIDANCE
- Be concise — this runs in a tight loop`;
  }

  /**
   * Build a compact phase summary from the full annotation trajectory.
   * Helps the LLM understand where the branch has spent its time.
   */
  private buildPhaseSummary(): string {
    const annotations = this.state.annotations
    if (annotations.length === 0) return 'No steps yet.'

    // Count phases
    const phaseCounts: Record<string, number> = {}
    const phaseScores: Record<string, { goal: number[]; novelty: number[]; progress: number[] }> = {}
    for (const a of annotations) {
      phaseCounts[a.annotation] = (phaseCounts[a.annotation] ?? 0) + 1
      if (!phaseScores[a.annotation]) {
        phaseScores[a.annotation] = { goal: [], novelty: [], progress: [] }
      }
      phaseScores[a.annotation].goal.push(a.goalAlignment)
      phaseScores[a.annotation].novelty.push(a.novelty)
      phaseScores[a.annotation].progress.push(a.progress)
    }

    const avg = (arr: number[]) => arr.length ? (arr.reduce((a, b) => a + b, 0) / arr.length).toFixed(2) : '0.00'

    const lines = Object.entries(phaseCounts)
      .sort((a, b) => b[1] - a[1])
      .map(([phase, count]) => {
        const s = phaseScores[phase]
        return `- ${phase}: ${count} steps (avg goal=${avg(s.goal)} novelty=${avg(s.novelty)} progress=${avg(s.progress)})`
      })

    // Add overall trajectory direction
    const recent5 = annotations.slice(-5)
    const avgRecentProgress = recent5.length ? recent5.reduce((s, a) => s + a.progress, 0) / recent5.length : 0
    const avgRecentNovelty = recent5.length ? recent5.reduce((s, a) => s + a.novelty, 0) / recent5.length : 0
    lines.push(`- Last 5 steps: avg progress=${avgRecentProgress.toFixed(2)}, avg novelty=${avgRecentNovelty.toFixed(2)}`)

    return lines.join('\n')
  }

  /**
   * Parse LLM response into annotation fields
   */
  private parseAnnotation(response: string, workUnitId: string): BrainstemAnnotation {
    // Parse dimensional scores
    const goalAlignmentMatch = response.match(/GOAL_ALIGNMENT:\s*([\d.]+)/i)
    const noveltyMatch = response.match(/NOVELTY:\s*([\d.]+)/i)
    const progressMatch = response.match(/PROGRESS:\s*([\d.]+)/i)
    const annotationMatch = response.match(/ANNOTATION:\s*(\w+)/i)
    const synthesisMatch = response.match(/SYNTHESIS:\s*([^\n]+)/i)
    const patternMatch = response.match(/PATTERN:\s*(\w+)/i)
    const guidanceMatch = response.match(/GUIDANCE:\s*([^\n]+)/i)
    const trainingNoteMatch = response.match(/TRAINING_NOTE:\s*([^\n]+)/i)

    // Parse dimensional scores with bounds checking
    const parseDimension = (match: RegExpMatchArray | null, fallback: number): number => {
      if (!match) return fallback
      const parsed = parseFloat(match[1])
      return isNaN(parsed) ? fallback : Math.max(0, Math.min(1, parsed))
    }

    const goalAlignment = parseDimension(goalAlignmentMatch, 0.5)
    const novelty = parseDimension(noveltyMatch, 0.5)
    const progress = parseDimension(progressMatch, 0.3)

    // Composite score: weighted average of dimensions
    // Progress weighted highest because it's the strongest signal of actual advancement
    const score = goalAlignment * 0.3 + novelty * 0.3 + progress * 0.4

    // Parse annotation type
    const annotationType = annotationMatch?.[1]?.toLowerCase() as WorkUnitAnnotation
    const validAnnotations: WorkUnitAnnotation[] = ['exploration', 'research', 'implementation', 'testing', 'revision', 'drift']
    const annotation: WorkUnitAnnotation = validAnnotations.includes(annotationType)
      ? annotationType
      : 'exploration'

    // Parse pattern type
    const patternType = patternMatch?.[1]?.toLowerCase() as DetectedPattern
    const validPatterns: DetectedPattern[] = ['none', 'paralysis', 'drift', 'convergence', 'stalling']
    const pattern: DetectedPattern = validPatterns.includes(patternType)
      ? patternType
      : 'none'

    // Parse synthesis
    const synthesis = synthesisMatch?.[1]?.trim() ?? ''
    const normalizedSynthesis = synthesis.toUpperCase() === 'NONE' ? '' : synthesis

    // Parse guidance
    const guidanceText = guidanceMatch?.[1]?.trim() ?? null
    const guidance: string | null = guidanceText && guidanceText.toUpperCase() !== 'NONE'
      ? guidanceText
      : null

    // Determine urgency based on pattern and dimensional scores
    let urgency: GuidanceUrgency = 'low'
    if (pattern === 'paralysis' || (goalAlignment < 0.2 && progress < 0.2)) {
      urgency = 'critical'
    } else if (pattern === 'drift' || goalAlignment < 0.3) {
      urgency = 'high'
    } else if (pattern === 'stalling' || (novelty < 0.2 && progress < 0.2)) {
      urgency = 'medium'
    }

    // Parse training note
    const trainingNote = trainingNoteMatch?.[1]?.trim() ?? 'No training note provided'

    return {
      workUnitId,
      score,
      annotation,
      synthesis: normalizedSynthesis,
      pattern,
      guidance,
      guidanceUrgency: urgency,
      trainingNote,
      axonStep: this.state.currentAxonStep,
      timestamp: Date.now(),
      goalAlignment,
      novelty,
      progress,
    }
  }

  /**
   * Update Brainstem state with new annotation
   */
  private updateState(annotation: BrainstemAnnotation): void {
    this.state.annotations.push(annotation)
    this.state.qualityTrajectory.push(annotation.score)

    // Track drift for state reporting (no intervention logic — that's the LLM's job)
    if (annotation.annotation === 'drift') {
      this.state.consecutiveDrifts++
    } else {
      this.state.consecutiveDrifts = 0
    }

    // Track explorations for state reporting only
    if (annotation.annotation === 'exploration' || annotation.annotation === 'research') {
      this.state.consecutiveExplorations++
    } else {
      this.state.consecutiveExplorations = 0
    }

    // Update pattern detections
    if (annotation.pattern !== 'none') {
      this.state.totalPatternDetections++
    }
  }

  /**
   * Detect patterns and produce guidance if needed.
   *
   * Pattern detection is now LLM-driven: the Brainstem LLM scores each work unit
   * with dimensional scores (goalAlignment, novelty, progress) and sets the pattern
   * field based on full trajectory awareness. We trust its judgment.
   *
   * The only hardcoded check remaining is stagnation: a pure score-trajectory
   * check that fires when rolling average drops below threshold over many steps.
   * This is a safety net for cases where the LLM itself is scoring poorly.
   */
  private detectPatternsAndProduceGuidance(annotation: BrainstemAnnotation): void {
    // Stagnation check — many steps with persistently low composite scores.
    // This is a safety net that fires regardless of what the LLM says,
    // because if the LLM is scoring everything low for 10+ steps, something
    // is fundamentally wrong and we need to intervene.
    if (
      this.state.currentAxonStep >= this.config.stagnationStepThreshold &&
      this.state.qualityTrajectory.length >= this.config.stagnationStepThreshold
    ) {
      const window = this.state.qualityTrajectory.slice(-this.config.stagnationStepThreshold)
      const avgScore = window.reduce((a, b) => a + b, 0) / window.length

      if (avgScore < this.config.stagnationScoreThreshold && !this.state.stagnationFired) {
        this.state.stagnationFired = true
        this.state.totalPatternDetections++
        const guidance: PendingGuidance = {
          text: `I have been running for ${this.state.currentAxonStep} steps with average score ${avgScore.toFixed(2)}. ` +
            `I should consider: (1) narrowing scope to the most impactful sub-task, (2) switching approach entirely, ` +
            `or (3) concluding with current findings if further progress is unlikely.`,
          urgency: 'critical',
          fromStep: this.state.currentAxonStep,
          triggeredBy: 'stagnation' as any,
          timestamp: Date.now(),
        }
        this.queueGuidance(guidance)
        return
      }
    }

    // LLM-generated guidance passthrough — the Brainstem LLM has full trajectory
    // context and dimensional scores. If it decided guidance is needed, trust it.
    if (annotation.guidance) {
      const guidance: PendingGuidance = {
        text: annotation.guidance,
        urgency: annotation.guidanceUrgency,
        fromStep: this.state.currentAxonStep,
        triggeredBy: annotation.pattern,
        timestamp: Date.now(),
      }
      this.queueGuidance(guidance)
    }
  }

  /**
   * Validate file paths mentioned in guidance text.
   * If readFile is available, checks that referenced paths exist.
   * Strips invalid paths from guidance to prevent agents from chasing ghosts.
   */
  private async validateGuidancePaths(text: string): Promise<string> {
    if (!this.deps.readFile) return text

    // Extract file-path-like strings (e.g., core/intelligence/foo.ts, ./src/bar.js)
    const pathPattern = /(?:^|\s|['"`])((?:\.\/|\.\.\/|[a-zA-Z_][\w-]*\/)[^\s'"`,)}\]]+\.(?:ts|js|json|md))/g
    const matches = [...text.matchAll(pathPattern)]
    if (matches.length === 0) return text

    let result = text
    for (const match of matches) {
      const filePath = match[1]
      try {
        const content = await this.deps.readFile(filePath)
        if (content === null) {
          // Path doesn't exist — annotate in the guidance
          result = result.replace(filePath, `${filePath} [NOT FOUND]`)
          this.logger.debug('Guidance referenced non-existent path', { filePath })
        }
      } catch {
        // readFile failed — leave path as-is, don't block guidance
      }
    }
    return result
  }

  /**
   * Score and manage context chunks based on the annotation.
   * High-quality file reads get pinned; drift-associated context gets de-prioritized.
   */
  private scoreContextChunks(annotation: BrainstemAnnotation): void {
    const cci = this.deps.unityChunkIndex
    if (!cci) return

    const snap = cci.snapshot()
    if (snap.totalChunks === 0) return

    // Pin file-read chunks from high-scoring iterations
    if (annotation.score >= 0.7) {
      const hotFileChunks = snap.hotChunks.filter(c =>
        c.tags.includes('tool-result') && c.tags.some(t => t.startsWith('file:'))
      )
      if (hotFileChunks.length > 0) {
        cci.pin(hotFileChunks.map(c => c.id))
        this.logger.debug('Pinned high-quality file reads', {
          count: hotFileChunks.length,
          score: annotation.score,
        })
      }
    }

    // Boost recently-referenced chunks on convergence
    if (annotation.pattern === 'convergence' && snap.hotChunks.length > 0) {
      cci.boost(snap.hotChunks.map(c => c.id), 0.2)
    }
  }

  /**
   * Read a file and inject its content into Unity's context as a pinned chunk.
   * Called by brainstem when it determines a specific file is critical for the posture
   * to see, or by Corpus via the context-inject directive.
   *
   * Returns the chunk ID if successful, or null if the file doesn't exist.
   */
  async injectFileContent(
    filePath: string,
    options?: { pinned?: boolean; tags?: string[] }
  ): Promise<string | null> {
    if (!this.deps.readFile || !this.deps.unityChunkIndex) return null

    const content = await this.deps.readFile(filePath)
    if (content === null) {
      this.logger.debug('injectFileContent: file not found', { filePath })
      return null
    }

    // Truncate very large files to prevent context explosion
    const maxChars = 8000
    const truncated = content.length > maxChars
      ? content.slice(0, maxChars) + `\n\n…[truncated at ${maxChars} chars, full file is ${content.length} chars]`
      : content

    const chunkId = `injected-${filePath.replace(/[/\\]/g, '-')}-${Date.now()}`
    const cci = this.deps.unityChunkIndex

    // Register the content as a chunk with file-specific tags
    cci.addSyntheticChunk({
      id: chunkId,
      content: `--- File: ${filePath} ---\n${truncated}\n--- End: ${filePath} ---`,
      role: 'user',
      tags: ['injected', `file:${filePath}`, ...(options?.tags ?? [])],
      pinned: options?.pinned ?? true,
    })

    this.logger.info('Injected file content into context', {
      filePath,
      chunkId,
      contentLength: truncated.length,
      pinned: options?.pinned ?? true,
    })

    return chunkId
  }

  /**
   * Queue guidance with cooldown check
   */
  private queueGuidance(guidance: PendingGuidance): void {
    // Check cooldown — but bypass for critical/high Corpus directives.
    // Corpus interventions are strategic decisions that should not be silently
    // dropped by a routine cooldown timer.
    const isCorpusDirective = typeof guidance.triggeredBy === 'string' &&
      guidance.triggeredBy.startsWith('corpus:')
    const bypassCooldown = isCorpusDirective &&
      (guidance.urgency === 'critical' || guidance.urgency === 'high')

    if (!bypassCooldown) {
      const iterationsSinceLastGuidance = this.state.currentAxonStep - this.state.lastGuidanceStep
      if (iterationsSinceLastGuidance < this.config.guidanceCooldownIterations) {
        this.logger.debug('Guidance cooldown active, skipping', {
          urgency: guidance.urgency,
          cooldownRemaining: this.config.guidanceCooldownIterations - iterationsSinceLastGuidance,
        })
        return
      }
    }

    this.guidanceQueue.push(guidance)
    this.state.lastGuidanceStep = this.state.currentAxonStep
    this.state.totalGuidanceCount++

    this.logger.info('Guidance produced', {
      urgency: guidance.urgency,
      triggeredBy: guidance.triggeredBy,
      text: guidance.text.slice(0, 100),
    })

    // Emit guidance event
    this.emitEvent('brainstem:guidance', {
      urgency: guidance.urgency,
      triggeredBy: guidance.triggeredBy,
      text: guidance.text,
      axonStep: guidance.fromStep,
      timestamp: new Date(),
    })
  }

  // ── Event Emission ──────────────────────────────────────────────────

  /**
   * Emit brainstem:annotation event (and brainstem:pattern if non-none).
   */
  private emitAnnotationEvent(annotation: BrainstemAnnotation): void {
    this.emitEvent('brainstem:annotation', {
      workUnitId: annotation.workUnitId,
      score: annotation.score,
      annotation: annotation.annotation,
      pattern: annotation.pattern,
      guidance: annotation.guidance ?? undefined,
      axonStep: annotation.axonStep,
      timestamp: new Date(annotation.timestamp),
    })

    if (annotation.pattern !== 'none') {
      const severity = annotation.pattern === 'paralysis' || annotation.pattern === 'stalling'
        ? 'high'
        : annotation.pattern === 'drift'
          ? 'medium'
          : 'low'
      this.emitEvent('brainstem:pattern', {
        pattern: annotation.pattern,
        severity,
        axonStep: annotation.axonStep,
        timestamp: new Date(annotation.timestamp),
      })
    }
  }

  /**
   * Emit an event on the event bus if available.
   */
  private emitEvent(type: string, data: Record<string, unknown>): void {
    if (!this.deps.eventBus) return
    try {
      void this.deps.eventBus.emit({
        type,
        sessionId: this.deps.sessionId,
        ...data,
      } as any)
    } catch {
      // Ignore emit errors — observability must not crash the loop
    }
  }

  // ═══════════════════════════════════════════════════════════════════
  // Shared Thought Tree — Self-Organization
  // ═══════════════════════════════════════════════════════════════════

  /**
   * Generate and publish a BranchDigest to the shared tree.
   * Called after every work unit for maximum peer awareness freshness.
   * No LLM call — purely local aggregation from existing annotation data.
   */
  private publishDigest(annotation: BrainstemAnnotation): void {
    const sharedTree = this.deps.sharedTree
    if (!sharedTree || !this.deps.helixId) return

    try {
      // Derive current approach from recent annotations
      this.updateCurrentApproach(annotation)

      // Extract files from recent annotations
      this.extractActiveFiles(annotation)

      // Compute rolling score (last 5)
      const recentScores = this.state.qualityTrajectory.slice(-5)
      const rollingScore = recentScores.length > 0
        ? recentScores.reduce((a, b) => a + b, 0) / recentScores.length
        : 0.5

      // Estimate progress from score trajectory and annotation patterns
      const progress = this.estimateProgress()

      // Extract key findings — high-score annotations (> 0.7) with synthesis
      const keyFindings = this.state.annotations
        .filter((a) => a.score > 0.7 && a.synthesis.length > 0)
        .slice(-5)
        .map((a) => a.synthesis.slice(0, 200))

      // Extract blockers — from annotations with pathological patterns or very low scores
      const blockers = this.state.annotations
        .filter((a) =>
          a.pattern !== 'none' || a.score < 0.3
        )
        .slice(-3)
        .map((a) =>
          a.pattern !== 'none'
            ? `${a.pattern}: ${a.trainingNote.slice(0, 100)}`
            : `Low score (${a.score.toFixed(2)}): ${a.trainingNote.slice(0, 100)}`
        )

      // Build current strategy description
      const currentStrategy = this.describeCurrentStrategy()

      const digest: BranchDigest = {
        helixId: this.deps.helixId,
        goalSummary: this.deps.goal.slice(0, 200),
        approach: this.currentApproach,
        progress,
        filesActive: Array.from(this.recentFilesActive),
        keyFindings,
        blockers,
        currentStrategy,
        rollingScore,
        workUnitsProcessed: this.state.workUnitsProcessed,
        updatedAt: Date.now(),
        lastApproachChangeReason: this.previousApproach !== this.currentApproach
          ? `Changed from ${this.previousApproach} due to annotation pattern shift`
          : undefined,
      }

      sharedTree.updateDigest(digest)
    } catch (err) {
      this.logger.warn('Failed to publish digest', {
        error: String(err),
        helixId: this.deps.helixId,
      })
    }
  }

  /**
   * Detect cross-cutting concerns and auto-create/contribute to shared topics.
   * Triggered when this Helix's active files overlap with a peer's files.
   * Threshold: 1 shared file triggers topic creation.
   */
  private detectAndPublishTopics(): void {
    const sharedTree = this.deps.sharedTree
    if (!sharedTree || !this.deps.helixId) return

    try {
      const myFiles = Array.from(this.recentFilesActive)
      if (myFiles.length === 0) return

      const peerDigests = sharedTree.getPeerDigests()

      for (const peer of peerDigests) {
        // Find shared files
        const sharedFiles = myFiles.filter((f) => peer.filesActive.includes(f))

        if (sharedFiles.length >= 1) {
          // Check if a topic already exists for these files
          const existingTopics = sharedTree.findRelatedTopics(sharedFiles, [])
          const alreadyCovered = existingTopics.some((t) =>
            this.contributedTopics.has(t.id)
          )

          if (!alreadyCovered && existingTopics.length > 0) {
            // Contribute to existing topic
            const topic = existingTopics[0]
            const contribution = this.buildTopicContribution(sharedFiles)
            sharedTree.contributeTopic(topic.id, contribution)
            this.contributedTopics.add(topic.id)

            this.logger.info('Contributed to existing topic', {
              topicId: topic.id,
              topicName: topic.name,
              sharedFiles,
              peerHelixId: peer.helixId,
            })
          } else if (!alreadyCovered) {
            // Create new topic
            const topicName = this.deriveTopicName(sharedFiles)
            const contribution = this.buildTopicContribution(sharedFiles)
            const topicId = sharedTree.createTopic(topicName, contribution)
            this.contributedTopics.add(topicId)

            this.logger.info('Created new shared topic', {
              topicId,
              topicName,
              sharedFiles,
              peerHelixId: peer.helixId,
            })
          }
        }
      }
    } catch (err) {
      this.logger.warn('Failed to detect/publish topics', {
        error: String(err),
        helixId: this.deps.helixId,
      })
    }
  }

  /**
   * Self-organize by reading the shared tree and generating adjustments.
   * This is the core of the stigmergic coordination mechanism.
   *
   * Runs after every work unit (alongside digest publication).
   * Applies a 2-cycle dampening threshold: an adjustment must be
   * generated on 2 consecutive cycles before it takes effect.
   *
   * Self-organization rules (in priority order):
   * 1. FILE CONFLICT AVOIDANCE — back off files a peer is actively editing
   * 2. PATTERN ADOPTION — adopt proven strategies from the elevated pattern library
   * 3. FINDING INCORPORATION — pull relevant peer findings into local context
   * 4. APPROACH REDIRECT — change strategy based on peer success/own failure
   * 5. GOAL REFINEMENT — narrow focus to reduce overlap with a peer
   * 6. TENSION FLAG — flag conflicting approaches in shared topics
   * 7. PEER ASSIST — offer findings to struggling peers via topics
   */
  private selfOrganize(): void {
    const sharedTree = this.deps.sharedTree
    if (!sharedTree || !this.deps.helixId) return

    try {
      const relevantDigests = sharedTree.getRelevantDigests()
      const myFiles = Array.from(this.recentFilesActive)
      const relatedTopics = sharedTree.findRelatedTopics(
        myFiles,
        this.extractGoalKeywords()
      )
      const elevatedPatterns = sharedTree.getElevatedPatterns()

      // Track which adjustments we generate this cycle
      const currentCycleAdjustments = new Set<string>()

      // ── Rule 1: File Conflict Avoidance ────────────────────────
      for (const peer of relevantDigests) {
        const conflictFiles = myFiles.filter((f) => peer.filesActive.includes(f))
        if (conflictFiles.length > 0) {
          const key = `file-avoidance:${peer.helixId}:${conflictFiles.sort().join(',')}`
          currentCycleAdjustments.add(key)
          this.tickAdjustment(key, {
            type: 'file-avoidance',
            description: `Peer ${peer.helixId} is actively editing ${conflictFiles.join(', ')}. ` +
              `I should coordinate: finish my current changes first or defer to the peer.`,
            evidence: `Peer approach: ${peer.approach}, my approach: ${this.currentApproach}`,
            sourceHelixId: peer.helixId,
            dampeningCount: 0,
            dampeningThreshold: 2,
            firstGeneratedAt: Date.now(),
            lastConfirmedAt: Date.now(),
          })
        }
      }

      // ── Rule 2: Pattern Adoption ───────────────────────────────
      for (const pattern of elevatedPatterns) {
        // Check if this pattern is applicable to my context
        const fileOverlap = pattern.relevantFiles.filter((f) => myFiles.includes(f))
        const goalOverlap = this.extractGoalKeywords().some((kw) =>
          pattern.applicableContext.toLowerCase().includes(kw.toLowerCase())
        )

        if ((fileOverlap.length > 0 || goalOverlap) && pattern.approach !== this.currentApproach) {
          const key = `pattern-adoption:${pattern.id}`
          currentCycleAdjustments.add(key)
          this.tickAdjustment(key, {
            type: 'pattern-adoption',
            description: `Elevated pattern "${pattern.description.slice(0, 100)}" ` +
              `achieved score ${pattern.achievedScore.toFixed(2)} with ${pattern.approach} approach. ` +
              `Consider adopting this proven strategy.`,
            evidence: `Pattern from ${pattern.sourceHelixId}, ${pattern.supportingRetrospectives.length} supporting retrospectives`,
            dampeningCount: 0,
            dampeningThreshold: 2,
            firstGeneratedAt: Date.now(),
            lastConfirmedAt: Date.now(),
          })
        }
      }

      // ── Rule 3: Finding Incorporation ──────────────────────────
      for (const peer of relevantDigests) {
        if (peer.keyFindings.length > 0 && peer.rollingScore > 0.7) {
          const key = `finding-incorporation:${peer.helixId}`
          currentCycleAdjustments.add(key)
          this.tickAdjustment(key, {
            type: 'finding-incorporation',
            description: `Peer ${peer.helixId} (score: ${peer.rollingScore.toFixed(2)}) has relevant findings: ` +
              `${peer.keyFindings.slice(0, 2).join('; ')}`,
            evidence: `Peer is working on: ${peer.goalSummary.slice(0, 80)}`,
            sourceHelixId: peer.helixId,
            dampeningCount: 0,
            dampeningThreshold: 2,
            firstGeneratedAt: Date.now(),
            lastConfirmedAt: Date.now(),
          })
        }
      }

      // ── Rule 4: Approach Redirect ──────────────────────────────
      // If my score is low and multiple peers succeed with a different approach
      const myRollingScore = this.state.qualityTrajectory.slice(-5)
      const myAvg = myRollingScore.length > 0
        ? myRollingScore.reduce((a, b) => a + b, 0) / myRollingScore.length
        : 0.5

      if (myAvg < 0.5) {
        const successfulPeers = relevantDigests.filter(
          (p) => p.rollingScore > 0.7 && p.approach !== this.currentApproach
        )

        if (successfulPeers.length >= 1) {
          // Most common successful approach among peers
          const approachCounts = new Map<BranchApproach, number>()
          for (const peer of successfulPeers) {
            approachCounts.set(peer.approach, (approachCounts.get(peer.approach) ?? 0) + 1)
          }
          const bestApproach = Array.from(approachCounts.entries())
            .sort((a, b) => b[1] - a[1])[0]?.[0]

          if (bestApproach) {
            const key = `approach-redirect:${bestApproach}`
            currentCycleAdjustments.add(key)
            this.tickAdjustment(key, {
              type: 'approach-redirect',
              description: `My rolling score is ${myAvg.toFixed(2)} while ${successfulPeers.length} peer(s) ` +
                `succeed with "${bestApproach}" approach (avg score ${successfulPeers[0].rollingScore.toFixed(2)}). ` +
                `I should consider switching from "${this.currentApproach}" to "${bestApproach}".`,
              evidence: `Successful peers: ${successfulPeers.map((p) => `${p.helixId}:${p.rollingScore.toFixed(2)}`).join(', ')}`,
              dampeningCount: 0,
              dampeningThreshold: 2,
              firstGeneratedAt: Date.now(),
              lastConfirmedAt: Date.now(),
            })
          }
        }
      }

      // ── Rule 5: Goal Refinement ────────────────────────────────
      for (const peer of relevantDigests) {
        const myKeywords = new Set(this.extractGoalKeywords())
        const peerKeywords = peer.goalSummary.toLowerCase().split(/[^a-z0-9_-]+/).filter((w) => w.length > 2)
        const overlap = peerKeywords.filter((kw) => myKeywords.has(kw))

        if (overlap.length >= 3 && peer.progress > 0.5) {
          const key = `goal-refinement:${peer.helixId}`
          currentCycleAdjustments.add(key)
          this.tickAdjustment(key, {
            type: 'goal-refinement',
            description: `Peer ${peer.helixId} (${(peer.progress * 100).toFixed(0)}% done) has significant goal overlap. ` +
              `Shared keywords: ${overlap.slice(0, 5).join(', ')}. ` +
              `I should narrow my focus to the non-overlapping aspects of my goal.`,
            evidence: `Peer goal: ${peer.goalSummary.slice(0, 80)}`,
            sourceHelixId: peer.helixId,
            dampeningCount: 0,
            dampeningThreshold: 2,
            firstGeneratedAt: Date.now(),
            lastConfirmedAt: Date.now(),
          })
        }
      }

      // ── Rule 6: Tension Flag ───────────────────────────────────
      for (const topic of relatedTopics) {
        if (topic.tensionFlag) {
          const key = `tension-flag:${topic.id}`
          currentCycleAdjustments.add(key)
          this.tickAdjustment(key, {
            type: 'tension-flag',
            description: `Shared topic "${topic.name}" has a tension: ${topic.tensionDescription ?? 'conflicting approaches'}. ` +
              `I should review this topic and either align my approach or justify my divergence.`,
            evidence: `${topic.contributions.length} contributions from ${[...new Set(topic.contributions.map((c) => c.helixId))].join(', ')}`,
            sourceTopicId: topic.id,
            dampeningCount: 0,
            dampeningThreshold: 2,
            firstGeneratedAt: Date.now(),
            lastConfirmedAt: Date.now(),
          })
        }
      }

      // ── Rule 7: Peer Assist ────────────────────────────────────
      for (const peer of relevantDigests) {
        if (peer.blockers.length > 0 && peer.rollingScore < 0.4) {
          // I might have findings that could help
          const myRelevantFindings = this.state.annotations
            .filter((a) => a.score > 0.7 && a.synthesis.length > 0)
            .slice(-3)

          if (myRelevantFindings.length > 0) {
            const key = `peer-assist:${peer.helixId}`
            currentCycleAdjustments.add(key)
            this.tickAdjustment(key, {
              type: 'peer-assist',
              description: `Peer ${peer.helixId} is struggling (score: ${peer.rollingScore.toFixed(2)}) with blockers: ` +
                `${peer.blockers[0]?.slice(0, 80)}. I have potentially relevant findings to share via a topic.`,
              evidence: `My finding: ${myRelevantFindings[0].synthesis.slice(0, 100)}`,
              sourceHelixId: peer.helixId,
              dampeningCount: 0,
              dampeningThreshold: 2,
              firstGeneratedAt: Date.now(),
              lastConfirmedAt: Date.now(),
            })
          }
        }
      }

      // ── Expire stale adjustments ───────────────────────────────
      for (const [key] of this.pendingSelfOrgAdjustments) {
        if (!currentCycleAdjustments.has(key)) {
          // Adjustment was not regenerated this cycle — reset dampening
          this.pendingSelfOrgAdjustments.delete(key)
        }
      }

      // ── Apply adjustments that have met the dampening threshold ─
      this.applyReadyAdjustments()

      // ── Track effectiveness of applied adjustments ─────────────
      this.measureEffectiveness()

    } catch (err) {
      this.logger.warn('Self-organization cycle failed', {
        error: String(err),
        helixId: this.deps.helixId,
      })
    }
  }


  // ═══════════════════════════════════════════════════════════════════
  // Self-Organization: Internal Helpers
  // ═══════════════════════════════════════════════════════════════════

  /**
   * Tick a dampening counter for an adjustment. If the adjustment key
   * already exists, increment its count. Otherwise create it.
   */
  private tickAdjustment(key: string, template: SelfOrgAdjustment): void {
    const existing = this.pendingSelfOrgAdjustments.get(key)
    if (existing) {
      existing.dampeningCount++
      existing.lastConfirmedAt = Date.now()
    } else {
      template.dampeningCount = 1
      this.pendingSelfOrgAdjustments.set(key, template)
    }
  }

  /**
   * Apply adjustments that have met the 2-cycle dampening threshold.
   * Each applied adjustment is converted to a PendingGuidance and
   * queued for Unity delivery through the normal mechanism.
   */
  private applyReadyAdjustments(): void {
    for (const [key, adjustment] of this.pendingSelfOrgAdjustments) {
      if (adjustment.dampeningCount >= adjustment.dampeningThreshold) {
        // Convert to guidance
        const urgency = this.adjustmentToUrgency(adjustment.type)
        const guidanceText = this.formatAdjustmentAsGuidance(adjustment)

        this.queueGuidance({
          text: guidanceText,
          urgency,
          triggeredBy: `self-org:${adjustment.type}` as any,
          fromStep: this.state.currentAxonStep,
          timestamp: Date.now(),
        })

        // Record for effectiveness tracking
        const recentScores = this.state.qualityTrajectory.slice(-3)
        const scoreAtApplication = recentScores.length > 0
          ? recentScores.reduce((a, b) => a + b, 0) / recentScores.length
          : 0.5

        this.appliedAdjustments.push({
          adjustment: { ...adjustment },
          scoreAtApplication,
          stepAtApplication: this.state.currentAxonStep,
        })

        // Handle approach redirect: record retrospective
        if (adjustment.type === 'approach-redirect') {
          this.recordApproachChangeRetrospective(
            adjustment.description,
            'self-organization'
          )
        }

        // Remove after applying
        this.pendingSelfOrgAdjustments.delete(key)

        this.logger.info('Self-org adjustment applied', {
          type: adjustment.type,
          key,
          dampeningCount: adjustment.dampeningCount,
          description: adjustment.description.slice(0, 100),
        })
      }
    }
  }

  /**
   * Measure effectiveness of previously applied adjustments.
   * After 3 steps, compare the score to the score at application time.
   */
  private measureEffectiveness(): void {
    const sharedTree = this.deps.sharedTree
    if (!sharedTree) return

    const stepsDelta = 3

    for (let i = this.appliedAdjustments.length - 1; i >= 0; i--) {
      const applied = this.appliedAdjustments[i]
      const stepsElapsed = this.state.currentAxonStep - applied.stepAtApplication

      if (stepsElapsed >= stepsDelta) {
        // Measure current score
        const recentScores = this.state.qualityTrajectory.slice(-3)
        const scoreAfter = recentScores.length > 0
          ? recentScores.reduce((a, b) => a + b, 0) / recentScores.length
          : 0.5

        const improvement = scoreAfter - applied.scoreAtApplication
        const record: EffectivenessRecord = {
          adjustmentType: applied.adjustment.type,
          helixId: this.deps.helixId!,
          scoreBefore: applied.scoreAtApplication,
          scoreAfter,
          stepsDelta: stepsElapsed,
          improvement,
          effective: improvement > 0,
          measuredAt: Date.now(),
        }

        sharedTree.recordEffectiveness(record)

        // Also update retrospective effectiveness if applicable
        this.updateRetrospectiveEffectiveness(
          applied.scoreAtApplication,
          scoreAfter,
          stepsElapsed
        )

        // Remove from tracking
        this.appliedAdjustments.splice(i, 1)
      }
    }
  }

  /**
   * Record a strategy retrospective when the approach changes.
   */
  private recordApproachChangeRetrospective(
    reason: string,
    trigger: RetrospectiveTrigger
  ): void {
    const sharedTree = this.deps.sharedTree
    if (!sharedTree || !this.deps.helixId) return

    const recentScores = this.state.qualityTrajectory.slice(-3)
    const scoreAtChange = recentScores.length > 0
      ? recentScores.reduce((a, b) => a + b, 0) / recentScores.length
      : 0.5

    const retrospective: StrategyRetrospective = {
      helixId: this.deps.helixId,
      fromApproach: this.previousApproach,
      toApproach: this.currentApproach,
      reason,
      trigger,
      scoreAtChange,
      timestamp: Date.now(),
    }

    sharedTree.recordRetrospective(retrospective)

    this.logger.info('Strategy retrospective recorded', {
      from: this.previousApproach,
      to: this.currentApproach,
      trigger,
      scoreAtChange: scoreAtChange.toFixed(2),
    })
  }

  /**
   * Update the most recent retrospective with effectiveness data.
   */
  private updateRetrospectiveEffectiveness(
    scoreBefore: number,
    scoreAfter: number,
    stepsAfter: number
  ): void {
    const sharedTree = this.deps.sharedTree
    if (!sharedTree || !this.deps.helixId) return

    // Find the most recent retrospective for this Helix and update it
    const retrospectives = sharedTree.getAllRetrospectives()
    const myRetro = retrospectives
      .filter((r) => r.helixId === this.deps.helixId && r.scoreAfterChange === undefined)
      .pop()

    if (myRetro) {
      myRetro.scoreAfterChange = scoreAfter
      myRetro.stepsAfterMeasured = stepsAfter
      myRetro.wasEffective = scoreAfter > scoreBefore
    }
  }

  /**
   * Derive the current approach from the most recent annotation.
   * Also tracks approach changes for retrospective recording.
   */
  private updateCurrentApproach(annotation: BrainstemAnnotation): void {
    const newApproach = this.annotationToApproach(annotation)

    if (newApproach !== this.currentApproach) {
      this.previousApproach = this.currentApproach
      this.currentApproach = newApproach
    }
  }

  /**
   * Map a WorkUnitAnnotation to a BranchApproach.
   */
  private annotationToApproach(annotation: BrainstemAnnotation): BranchApproach {
    switch (annotation.annotation) {
      case 'exploration': return 'exploration'
      case 'research': return 'research'
      case 'implementation': return 'implementation'
      case 'testing': return 'testing'
      case 'revision': return 'revision'
      case 'drift': return 'exploration' // drift is treated as unfocused exploration
      default: return 'exploration'
    }
  }

  /**
   * Extract active files from an annotation's training note.
   * Files appear as paths in the text — we extract anything that looks
   * like a file path (containing / and a file extension).
   */
  private extractActiveFiles(annotation: BrainstemAnnotation): void {
    // Extract file paths from synthesis and training notes
    const text = `${annotation.synthesis} ${annotation.trainingNote}`
    const pathRegex = /(?:^|\s)([\w./-]+\.\w{1,10})(?:\s|$|[,:;)])/g
    let match

    while ((match = pathRegex.exec(text)) !== null) {
      const path = match[1]
      // Filter for reasonable file paths
      if (path.includes('/') && !path.startsWith('http') && path.length < 200) {
        this.recentFilesActive.add(path)
      }
    }

    // Keep only the most recent ~20 files to avoid unbounded growth
    if (this.recentFilesActive.size > 20) {
      const files = Array.from(this.recentFilesActive)
      this.recentFilesActive = new Set(files.slice(-20))
    }
  }

  /**
   * Estimate progress (0-1) based on score trajectory and annotation patterns.
   */
  private estimateProgress(): number {
    if (this.state.workUnitsProcessed === 0) return 0

    const scores = this.state.qualityTrajectory
    const annotations = this.state.annotations

    // Factor 1: Score trajectory — rising scores indicate progress
    const recentAvg = scores.length >= 3
      ? scores.slice(-3).reduce((a, b) => a + b, 0) / 3
      : 0.3
    const scoreFactor = Math.min(recentAvg, 1)

    // Factor 2: Phase progression — exploration → implementation → testing is progress
    const phases = annotations.map((a) => a.annotation)
    const hasImplementation = phases.includes('implementation')
    const hasTesting = phases.includes('testing')
    const phaseFactor = hasTesting ? 0.8 : hasImplementation ? 0.5 : 0.2

    // Factor 3: Work units done (capped at 20 — after that we're probably not making linear progress)
    const stepFactor = Math.min(this.state.workUnitsProcessed / 20, 1)

    // Weighted combination
    return Math.min(scoreFactor * 0.4 + phaseFactor * 0.4 + stepFactor * 0.2, 1)
  }

  /**
   * Describe the current strategy in human-readable form.
   */
  private describeCurrentStrategy(): string {
    const annotations = this.state.annotations
    if (annotations.length === 0) return 'Starting up'

    const recent = annotations.slice(-3)
    const patterns = recent.map((a) => a.annotation)
    const avgScore = recent.reduce((sum, a) => sum + a.score, 0) / recent.length

    const phaseDesc = this.currentApproach === 'exploration'
      ? 'Exploring and gathering context'
      : this.currentApproach === 'research'
      ? 'Deep investigation and cross-referencing'
      : this.currentApproach === 'implementation'
      ? 'Actively implementing changes'
      : this.currentApproach === 'testing'
      ? 'Testing and verifying changes'
      : this.currentApproach === 'debugging'
      ? 'Debugging and fixing issues'
      : this.currentApproach === 'revision'
      ? 'Iterating based on feedback'
      : this.currentApproach === 'coordinating'
      ? 'Coordinating with peers'
      : 'Working'

    return `${phaseDesc} (score: ${avgScore.toFixed(2)}, recent: ${patterns.join('→')})`
  }

  /**
   * Extract goal keywords for relevance matching.
   */
  private extractGoalKeywords(): string[] {
    const stopWords = new Set([
      'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
      'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
      'should', 'may', 'might', 'shall', 'can', 'need', 'must', 'ought',
      'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as',
      'and', 'but', 'or', 'not', 'so', 'if', 'when', 'how', 'what', 'which',
      'this', 'that', 'these', 'those', 'it', 'they', 'we', 'you', 'my',
    ])

    return this.deps.goal
      .toLowerCase()
      .split(/[^a-z0-9_-]+/)
      .filter((w) => w.length > 2 && !stopWords.has(w))
  }

  /**
   * Build a TopicContribution from current state.
   */
  private buildTopicContribution(sharedFiles: string[]): TopicContribution {
    const recentFinding = this.state.annotations
      .filter((a) => a.score > 0.6 && a.synthesis.length > 0)
      .pop()

    return {
      helixId: this.deps.helixId!,
      content: recentFinding
        ? recentFinding.synthesis.slice(0, 300)
        : `Working on: ${this.deps.goal.slice(0, 100)}`,
      approach: this.currentApproach,
      files: sharedFiles,
      score: recentFinding?.score ?? 0.5,
      timestamp: Date.now(),
    }
  }

  /**
   * Derive a topic name from shared files.
   * Uses the most specific shared directory or file name.
   */
  private deriveTopicName(sharedFiles: string[]): string {
    if (sharedFiles.length === 1) {
      // Use the filename
      const parts = sharedFiles[0].split('/')
      return parts[parts.length - 1].replace(/\.\w+$/, '')
    }

    // Find common directory prefix
    const parts = sharedFiles.map((f) => f.split('/'))
    let commonDepth = 0
    for (let i = 0; i < Math.min(...parts.map((p) => p.length)); i++) {
      const segment = parts[0][i]
      if (parts.every((p) => p[i] === segment)) {
        commonDepth = i + 1
      } else {
        break
      }
    }

    if (commonDepth > 0) {
      return parts[0].slice(0, commonDepth).join('/')
    }

    return sharedFiles.slice(0, 2).join(', ')
  }

  /**
   * Map adjustment type to guidance urgency.
   */
  private adjustmentToUrgency(type: SelfOrgAdjustmentType): GuidanceUrgency {
    switch (type) {
      case 'file-avoidance': return 'high'
      case 'approach-redirect': return 'high'
      case 'tension-flag': return 'medium'
      case 'finding-incorporation': return 'low'
      case 'pattern-adoption': return 'medium'
      case 'goal-refinement': return 'medium'
      case 'peer-assist': return 'low'
      default: return 'low'
    }
  }

  /**
   * Format a self-org adjustment as first-person guidance text.
   */
  private formatAdjustmentAsGuidance(adjustment: SelfOrgAdjustment): string {
    switch (adjustment.type) {
      case 'file-avoidance':
        return `[Self-Organization] ${adjustment.description} I need to be aware of concurrent edits.`
      case 'finding-incorporation':
        return `[Self-Organization] ${adjustment.description} I should factor this into my work.`
      case 'approach-redirect':
        return `[Self-Organization] ${adjustment.description} I should seriously consider changing my approach.`
      case 'goal-refinement':
        return `[Self-Organization] ${adjustment.description} I should focus on what I can uniquely contribute.`
      case 'tension-flag':
        return `[Self-Organization] ${adjustment.description}`
      case 'pattern-adoption':
        return `[Self-Organization] ${adjustment.description}`
      case 'peer-assist':
        return `[Self-Organization] ${adjustment.description} I should share my findings via a topic contribution.`
      default:
        return `[Self-Organization] ${adjustment.description}`
    }
  }


  // ── Corpus Tree Integration ──────────────────────────────────────────

  /**
   * Push annotation to the Corpus tree (Constellation mode only).
   * Each Brainstem builds its branch of the Corpus's reasoning tree.
   */
  private pushToCorpusTree(annotation: BrainstemAnnotation, toolCalls?: Array<{ name: string; args: string }>): void {
    if (!this.deps.corpusTree || !this.deps.helixId) return
    try {
      this.deps.corpusTree.pushAnnotation(this.deps.helixId, annotation, toolCalls)
    } catch (err) {
      this.logger.warn('Failed to push annotation to Corpus tree', {
        error: String(err),
        helixId: this.deps.helixId,
      })
    }
  }

  /**
   * Receive a directive from the Corpus (Constellation-level organizer).
   * Converts it to a PendingGuidance and queues it for Unity delivery
   * through the normal escalation model.
   */
  onCorpusDirective(directive: CorpusDirective): void {
    this.logger.info('Corpus directive received', {
      type: directive.type,
      urgency: directive.urgency,
      reason: directive.reason,
    })

    // Handle context-inject directives by reading the file and injecting it
    if (directive.type === 'context-inject') {
      // text contains the file path to inject
      const filePath = directive.text.trim()
      this.injectFileContent(filePath, { pinned: true, tags: ['corpus-injected'] })
        .then(chunkId => {
          if (chunkId) {
            this.logger.info('Corpus context-inject completed', { filePath, chunkId })
          } else {
            this.logger.warn('Corpus context-inject failed — file not found', { filePath })
          }
        })
        .catch(err => {
          this.logger.error('Corpus context-inject error', { filePath, error: String(err) })
        })
      return // context-inject doesn't produce guidance text
    }

    this.queueGuidance({
      urgency: directive.urgency,
      triggeredBy: `corpus:${directive.type}` as any,
      text: directive.text,
      fromStep: this.state.currentAxonStep,
      timestamp: Date.now(),
    })
  }


  // ── Blackboard Posting ──────────────────────────────────────────────

  /**
   * Post annotation to blackboard for cross-posture visibility and training data.
   */
  private postAnnotationToBlackboard(annotation: BrainstemAnnotation): void {
    const bb = this.deps.blackboard
    if (!bb) {
      this.logger.debug('Annotation ready for blackboard (no blackboard wired)', {
        workUnitId: annotation.workUnitId,
        score: annotation.score,
      })
      return
    }

    try {
      // Patterns and low scores go to 'concerns', everything else to 'findings'
      const channel = annotation.pattern !== 'none' || annotation.score < 0.4
        ? 'concerns' as const
        : 'findings' as const

      const scoreEmoji = annotation.score >= 0.7 ? '🟢' : annotation.score >= 0.5 ? '🟡' : '🔴'

      bb.post(channel, {
        author: 'brainstem',
        content: `${scoreEmoji} **${annotation.annotation}** (${annotation.score.toFixed(2)}) — ${annotation.trainingNote}${annotation.synthesis ? `\n_Dialectic:_ ${annotation.synthesis}` : ''}${annotation.guidance ? `\n_Guidance:_ ${annotation.guidance}` : ''}`,
        structured: {
          workUnitId: annotation.workUnitId,
          score: annotation.score,
          annotation: annotation.annotation,
          pattern: annotation.pattern,
          axonStep: annotation.axonStep,
        },
        priority: annotation.pattern !== 'none' ? 2 : annotation.score < 0.5 ? 1 : 0,
        tags: [
          'brainstem',
          annotation.annotation,
          ...(annotation.pattern !== 'none' ? [annotation.pattern] : []),
        ],
      })
    } catch (err) {
      this.logger.warn('Failed to post annotation to blackboard', {
        error: String(err),
        workUnitId: annotation.workUnitId,
      })
    }
  }

  /**
   * Sleep helper
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms))
  }

  /**
   * Force immediate processing of all queued work units (for testing and sync use).
   * Bypasses the async loop polling.
   */
  async processNow(): Promise<void> {
    if (!this.config.enabled) return
    await this.processWorkUnitBatch()
  }
}

/**
 * Factory function to create a HelixBrainstem instance
 */
export function createHelixBrainstem(
  deps: BrainstemDeps,
  config?: Partial<BrainstemConfig>
): HelixBrainstem {
  return new HelixBrainstem(deps, config)
}
