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
} from './corpus-types.js'
import type { SpawnRequest, ConstellationTemplate } from './types.js'
import {
  DEFAULT_CORPUS_CONFIG,
  createInitialProcessedState,
} from './corpus-types.js'
import type { BrainstemAnnotation, WorkUnitAnnotation, DetectedPattern, GuidanceUrgency } from '../helix/brainstem-types.js'

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

  // Timing
  private startTime = 0

  // Counter for LLM analysis triggering
  private newStepsSinceLLM = 0

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

    if (this.loopPromise) {
      await this.loopPromise
      this.loopPromise = null
    }

    this.running = false
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
   * Register a child Brainstem for directive delivery
   */
  registerBrainstem(helixId: string, brainstem: MinimalBrainstem): void {
    this.childBrainstems.set(helixId, brainstem)
    this.logger.debug('Brainstem registered', { helixId })
  }

  /**
   * Evaluate a spawn request via LLM
   */
  async evaluateSpawnRequest(request: SpawnRequest): Promise<SpawnDecision> {
    const decision = await this.runSpawnEvaluation(request)
    this.state.spawnDecisions.push(decision)
    this.emitEvent('corpus:spawn-decision', {
      requestId: request.requestId,
      approved: decision.approved,
      reason: decision.reason,
    })
    return decision
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
    }))

    return {
      tree: this.tree.getSnapshot(),
      branchAssessments: assessments,
      crossPatterns: [...this.state.crossPatterns],
      interventions: [...this.state.interventions],
      spawnDecisions: [...this.state.spawnDecisions],
      sweepCount: this.state.sweepCount,
      durationMs: this.startTime > 0 ? Date.now() - this.startTime : 0,
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
          // Idle poll
          await this.sleep(this.config.idlePollMs)
          continue
        }

        // Process new steps
        this.processNewSteps()

        // Detect cross-branch patterns
        const newPatterns = this.detectCrossPatterns()

        // Run LLM analysis if needed
        if (newPatterns.length > 0 || this.shouldRunLLMAnalysis()) {
          await this.runLLMAnalysis(newPatterns)
        }

        // Update sweep stats
        this.state.sweepCount++
        this.state.lastSweepAt = Date.now()

        // Emit sweep event
        this.emitEvent('corpus:sweep', {
          branches: this.tree.activeBranchCount(),
          patterns: this.state.crossPatterns.length,
          sweepCount: this.state.sweepCount,
        })
      } catch (error) {
        this.logger.error('Error in Corpus loop', {
          error: error instanceof Error ? error.message : String(error),
        })
        // Continue loop despite errors
        await this.sleep(this.config.idlePollMs)
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
    }
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

    // Track files modified (using workUnitId as proxy)
    for (const step of newSteps) {
      assessment.filesModified.add(step.annotation.workUnitId)
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
   * Detect cross-branch patterns
   */
  private detectCrossPatterns(): CrossHelixPattern[] {
    const patterns: CrossHelixPattern[] = []
    const assessments = Array.from(this.state.branchAssessments.values())
    const branches = this.tree.getAllBranches()

    // 1. Conflict: filesModified Set intersection across branches
    for (let i = 0; i < assessments.length; i++) {
      for (let j = i + 1; j < assessments.length; j++) {
        const a = assessments[i]
        const b = assessments[j]
        const intersection = new Set(
          [...a.filesModified].filter((x) => b.filesModified.has(x))
        )
        if (intersection.size > 0) {
          patterns.push({
            type: 'conflict',
            helixIds: [a.helixId, b.helixId],
            severity: 'high',
            description: `Branches ${a.helixId} and ${b.helixId} may be modifying the same work units`,
            detectedAt: Date.now(),
            actedUpon: false,
          })
        }
      }
    }

    // 2. Asymmetric progress: one branch has 3+ more steps than sibling
    const branchMap = new Map(branches.map((b) => [b.helixId, b]))
    for (const branch of branches) {
      if (!branch.parentId) continue
      const siblings = branches.filter(
        (b) => b.parentId === branch.parentId && b.helixId !== branch.helixId
      )
      for (const sibling of siblings) {
        const diff = branch.steps.length - sibling.steps.length
        if (diff >= 3) {
          const siblingAssessment = this.state.branchAssessments.get(sibling.helixId)
          if (siblingAssessment && siblingAssessment.rollingScore < 0.5) {
            patterns.push({
              type: 'asymmetric-progress',
              helixIds: [branch.helixId, sibling.helixId],
              severity: 'medium',
              description: `${sibling.helixId} is lagging behind ${branch.helixId} with low scores`,
              detectedAt: Date.now(),
              actedUpon: false,
            })
          }
        }
      }
    }

    // 3. Cascade failure: 2+ branches 'failed'/'struggling' created within 30s
    const strugglingBranches = branches.filter(
      (b) => b.status === 'failed' || this.state.branchAssessments.get(b.helixId)?.status === 'struggling'
    )
    if (strugglingBranches.length >= 2) {
      const timestamps = strugglingBranches.map((b) => b.createdAt).sort((a, b) => a - b)
      if (timestamps[timestamps.length - 1] - timestamps[0] < 30000) {
        patterns.push({
          type: 'cascade-failure',
          helixIds: strugglingBranches.map((b) => b.helixId),
          severity: 'critical',
          description: `Multiple branches failing within 30 seconds: ${strugglingBranches.map((b) => b.helixId).join(', ')}`,
          detectedAt: Date.now(),
          actedUpon: false,
        })
      }
    }

    // 4. Convergence: 2+ branches with dominantPattern 'implementation' and rollingScore > 0.7
    const highPerformingImpls = assessments.filter(
      (a) => a.dominantPattern === 'implementation' && a.rollingScore > 0.7
    )
    if (highPerformingImpls.length >= 2) {
      patterns.push({
        type: 'convergence',
        helixIds: highPerformingImpls.map((a) => a.helixId),
        severity: 'low',
        description: `Multiple branches showing strong implementation progress`,
        detectedAt: Date.now(),
        actedUpon: false,
      })
    }

    // De-duplicate against existing patterns
    const newPatterns: CrossHelixPattern[] = []
    for (const pattern of patterns) {
      const isDuplicate = this.state.crossPatterns.some(
        (existing) =>
          existing.type === pattern.type &&
          existing.helixIds.length === pattern.helixIds.length &&
          existing.helixIds.every((id) => pattern.helixIds.includes(id)) &&
          Date.now() - existing.detectedAt < 60000 // Within 1 minute
      )
      if (!isDuplicate) {
        newPatterns.push(pattern)
        this.state.crossPatterns.push(pattern)
        this.emitEvent('corpus:pattern', {
          type: pattern.type,
          helixIds: pattern.helixIds,
          severity: pattern.severity,
        })
      }
    }

    return newPatterns
  }

  /**
   * Check if we should run LLM analysis
   */
  private shouldRunLLMAnalysis(): boolean {
    return this.newStepsSinceLLM >= this.config.llmAnalysisThreshold
  }

  /**
   * Run LLM analysis for strategic assessment
   */
  private async runLLMAnalysis(newPatterns: CrossHelixPattern[]): Promise<void> {
    const prompt = this.buildLLMPrompt(newPatterns)

    try {
      const response = await this.deps.llm.complete({
        prompt,
        modelTier: this.config.modelTier,
        maxTokens: this.config.maxTokens,
        timeoutMs: this.config.timeoutMs,
      })

      this.parseAndApplyLLMResponse(response.content)
      this.newStepsSinceLLM = 0
    } catch (error) {
      this.logger.warn('LLM analysis failed, continuing loop', {
        error: error instanceof Error ? error.message : String(error),
      })
    }
  }

  /**
   * Build first-person LLM prompt
   */
  private buildLLMPrompt(newPatterns: CrossHelixPattern[]): string {
    const branches = this.tree.getAllBranches()
    const assessments = Array.from(this.state.branchAssessments.values())

    const branchDetails = branches
      .map((b) => {
        const assessment = this.state.branchAssessments.get(b.helixId)
        const recentSteps = b.steps.slice(-3)
        const recentAnnotations = recentSteps
          .map((s) => `[${s.annotation.annotation}:${s.annotation.score.toFixed(2)}]`)
          .join(', ')
        return `- ${b.helixId}: goal="${b.goal}", status=${b.status}, steps=${b.steps.length}, rollingScore=${assessment?.rollingScore.toFixed(2) ?? 'N/A'}, dominantPattern=${assessment?.dominantPattern ?? 'N/A'}, recent=[${recentAnnotations}]`
      })
      .join('\n')

    const patternDetails =
      newPatterns.length > 0
        ? `\n## New Cross-Branch Patterns Detected\n${newPatterns
            .map((p) => `- ${p.type} (${p.severity}): ${p.description}`)
            .join('\n')}`
        : ''

    return `I am the Corpus — the strategic organizer of this Constellation. My goal: ${this.deps.goal}. I oversee ${branches.length} branches, analyzing cross-Helix patterns and making spawn/intervention decisions.

## Branch Assessments
${branchDetails}${patternDetails}

## My Task
Provide strategic assessment:

ASSESSMENT: <brief assessment of overall constellation health>
INTERVENTION[helixId]: <directive type:guidance|redirect|throttle|priority-shift|cancel>:<urgency:low|medium|high|critical>:<guidance text> (or NONE)
SYNTHESIS: <strategic synthesis for Cassi, or NONE>

Guidelines:
- ASSESSMENT: Summarize the health of all branches and any concerning patterns
- INTERVENTION: Only if a specific Helix needs steering. Use helixId from above.
- SYNTHESIS: Strategic insights for the Constellation level, or NONE if routine
- Be concise — this runs in a tight loop`
  }

  /**
   * Parse LLM response and apply interventions
   */
  private parseAndApplyLLMResponse(response: string): void {
    // Parse ASSESSMENT
    const assessmentMatch = response.match(/ASSESSMENT:\s*([^\n]+)/i)
    const assessment = assessmentMatch?.[1]?.trim() ?? 'No assessment provided'

    // Parse INTERVENTION lines
    const interventionRegex = /INTERVENTION\[([^\]]+)\]:\s*([^:]+):([^:]+):(.+)/gi
    let match
    while ((match = interventionRegex.exec(response)) !== null) {
      const helixId = match[1].trim()
      const type = match[2].trim() as CorpusDirectiveType
      const urgency = match[3].trim() as GuidanceUrgency
      const text = match[4].trim()

      if (text.toUpperCase() !== 'NONE') {
        const directive: CorpusDirective = {
          targetHelixId: helixId,
          type,
          urgency,
          reason: assessment,
          text,
          timestamp: Date.now(),
        }
        this.sendDirective(directive)
      }
    }

    // Parse SYNTHESIS
    const synthesisMatch = response.match(/SYNTHESIS:\s*([^\n]+)/i)
    const synthesis = synthesisMatch?.[1]?.trim()
    if (synthesis && synthesis.toUpperCase() !== 'NONE') {
      this.postSynthesisToBlackboard(synthesis, assessment)
    }
  }

  /**
   * Send a directive to a child Brainstem
   */
  private sendDirective(directive: CorpusDirective): void {
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
   * Run spawn evaluation via LLM
   */
  private async runSpawnEvaluation(request: SpawnRequest): Promise<SpawnDecision> {
    const branches = this.tree.getAllBranches()
    const prompt = `I am the Corpus — evaluating a spawn request for this Constellation.

## Current Tree State
Active branches: ${branches.length}
Total steps: ${this.tree.totalStepCount()}

## Spawn Request
Requesting Helix: ${request.requestingHelixId}
Proposed Goal: ${request.goal}
Proposed Template: ${request.template ?? 'standard'}
Target Depth: ${request.targetDepth}

## My Task
Evaluate this spawn request and respond:

DECISION: <APPROVED|REJECTED>
REASON: <brief reasoning>
SUGGESTED_TEMPLATE: <template name or NONE>
SUGGESTED_GOAL: <refined goal or NONE>

Guidelines:
- APPROVE if the goal is clear, non-redundant with existing branches, and resources allow
- REJECT if too many active branches, goal is unclear, or similar work is in progress
- Suggest refinements if the goal could be clearer`

    try {
      const response = await this.deps.llm.complete({
        prompt,
        modelTier: this.config.modelTier,
        maxTokens: 400,
        timeoutMs: this.config.timeoutMs,
      })

      const decisionMatch = response.content.match(/DECISION:\s*(APPROVED|REJECTED)/i)
      const reasonMatch = response.content.match(/REASON:\s*([^\n]+)/i)
      const templateMatch = response.content.match(/SUGGESTED_TEMPLATE:\s*([^\n]+)/i)
      const goalMatch = response.content.match(/SUGGESTED_GOAL:\s*([^\n]+)/i)

      const approved = decisionMatch?.[1]?.toUpperCase() === 'APPROVED'
      const reason = reasonMatch?.[1]?.trim() ?? 'No reason provided'
      const suggestedTemplateStr = templateMatch?.[1]?.trim()
      const suggestedTemplate: ConstellationTemplate | undefined =
        suggestedTemplateStr && suggestedTemplateStr.toUpperCase() !== 'NONE'
          ? (suggestedTemplateStr as ConstellationTemplate)
          : undefined
      const suggestedGoal =
        goalMatch?.[1]?.trim().toUpperCase() !== 'NONE' ? goalMatch?.[1]?.trim() : undefined

      return {
        requestId: request.requestId,
        requestingHelixId: request.requestingHelixId,
        goal: request.goal,
        approved,
        reason,
        suggestedTemplate,
        suggestedGoal,
        evaluatedAt: Date.now(),
      }
    } catch (error) {
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
}

/**
 * Factory function to create a Corpus instance
 */
export function createCorpus(
  tree: ICorpusTree,
  deps: CorpusDeps,
  config?: Partial<CorpusConfig>
): Corpus {
  return new Corpus(tree, deps, config)
}
