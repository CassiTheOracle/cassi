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
import type { ICorpusTree, CorpusProcessedState, BranchAssessment, CrossHelixPattern, CorpusIntervention, SpawnDecision, CorpusResult, CorpusDirective, CorpusConfig, CorpusDeps } from './corpus-types.js'
import type { BrainstemAnnotation, WorkUnitAnnotation, DetectedPattern } from '../helix/brainstem-types.js'
import { DEFAULT_CORPUS_CONFIG, createInitialProcessedState } from './corpus-types.js'

/**
 * Minimal interface for Brainstem references to avoid circular imports.
 * The Corpus only needs to send directives to child Brainstems.
 */
interface MinimalBrainstem {
  onCorpusDirective?: (directive: CorpusDirective) => void
}

/**
 * Sleep helper for async delays.
 */
function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms))
}

/**
 * Corpus — The strategic organizer of a Constellation.
 *
 * Has its own async LLM loop that reads the shared CorpusTree,
 * detects cross-branch patterns, evaluates spawn requests,
 * and sends directives to child Brainstems.
 */
export class Corpus {
  private tree: ICorpusTree
  private deps: CorpusDeps
  private config: CorpusConfig
  private state: CorpusProcessedState
  private logger: ILogger

  // Child Brainstem registry
  private childBrainstems: Map<string, MinimalBrainstem>

  // Async loop control
  private running = false
  private shutdownRequested = false
  private loopPromise: Promise<void> | null = null

  // Timing
  private startTime = 0

  // Steps processed since last LLM analysis
  private stepsSinceLastAnalysis = 0

  constructor(tree: ICorpusTree, deps: CorpusDeps, config?: Partial<CorpusConfig>) {
    this.tree = tree
    this.deps = deps
    this.config = { ...DEFAULT_CORPUS_CONFIG, ...config }
    this.state = createInitialProcessedState()
    this.logger = deps.logger.child('Corpus')
    this.childBrainstems = new Map()

    this.logger.info('Corpus initialized', {
      constellationId: deps.constellationId,
      enabled: this.config.enabled,
    })
  }

  /**
   * Start the async Corpus loop.
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
   * Stop the Corpus loop gracefully.
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
      interventions: this.state.interventions.length,
    })
  }

  /**
   * Check if the Corpus loop is running.
   */
  isRunning(): boolean {
    return this.running
  }

  /**
   * Register a child Brainstem to receive directives.
   */
  registerBrainstem(helixId: string, brainstem: MinimalBrainstem): void {
    this.childBrainstems.set(helixId, brainstem)
    this.logger.debug('Brainstem registered', { helixId })
  }

  /**
   * Evaluate a spawn request using LLM analysis.
   */
  async evaluateSpawnRequest(request: {
    helixId: string
    template: string
    goal: string
    depth: number
    reason: string
  }): Promise<SpawnDecision> {
    const prompt = this.buildSpawnEvaluationPrompt(request)

    try {
      const response = await this.deps.llm.complete({
        prompt,
        modelTier: this.config.modelTier,
        maxTokens: this.config.maxTokens,
        timeoutMs: this.config.timeoutMs,
      })

      const decision = this.parseSpawnDecision(response.content, request)

      this.state.spawnDecisions.push(decision)
      this.emitEvent('corpus:spawn-evaluated', {
        helixId: request.helixId,
        approved: decision.approved,
        reason: decision.reason,
      })

      return decision
    } catch (error) {
      this.logger.error('Failed to evaluate spawn request', {
        error: error instanceof Error ? error.message : String(error),
        helixId: request.helixId,
      })

      // Return rejected decision on error
      const fallbackDecision: SpawnDecision = {
        approved: false,
        reason: `LLM evaluation failed: ${error instanceof Error ? error.message : String(error)}`,
        evaluatedAt: Date.now(),
        request,
      }
      this.state.spawnDecisions.push(fallbackDecision)
      return fallbackDecision
    }
  }

  /**
   * Get the Corpus result for final ConstellationResult.
   */
  getResult(): CorpusResult {
    return {
      treeSnapshot: this.tree.getSnapshot(),
      branchAssessments: this.state.branchAssessments,
      crossPatterns: this.state.crossPatterns,
      interventions: this.state.interventions,
      spawnDecisions: this.state.spawnDecisions,
      sweepCount: this.state.sweepCount,
      durationMs: this.startTime > 0 ? Date.now() - this.startTime : 0,
    }
  }

  /**
   * Main async loop.
   */
  private async runLoop(): Promise<void> {
    while (!this.shutdownRequested) {
      try {
        const pending = this.tree.pendingStepCount(this.state.cursors)

        if (pending === 0) {
          await sleep(this.config.idlePollMs)
          continue
        }

        // Process new steps from all branches
        this.processNewSteps()

        // Detect cross-branch patterns
        const newPatterns = this.detectCrossPatterns()

        // If enough new data or patterns found, run LLM analysis
        if (newPatterns.length > 0 || this.shouldRunLLMAnalysis()) {
          await this.runLLMAnalysis(newPatterns)
        }

        this.state.sweepCount++
        this.state.lastSweepAt = Date.now()

        // Emit sweep event
        this.emitEvent('corpus:sweep', {
          branches: this.tree.activeBranchCount(),
          patterns: newPatterns.length,
        })
      } catch (error) {
        this.logger.error('Error in Corpus loop', {
          error: error instanceof Error ? error.message : String(error),
        })
        // Continue loop despite errors
        await sleep(this.config.idlePollMs)
      }
    }
  }

  /**
   * Process new steps from all branches.
   */
  private processNewSteps(): void {
    for (const branch of this.tree.getAllBranches()) {
      const cursor = this.state.cursors.get(branch.helixId) ?? 0
      const newSteps = branch.steps.slice(cursor)

      if (newSteps.length === 0) {
        continue
      }

      // Get or create branch assessment
      let assessment = this.state.branchAssessments.get(branch.helixId)
      if (!assessment) {
        assessment = {
          helixId: branch.helixId,
          status: 'productive',
          rollingScore: 0,
          scoreTrajectory: [],
          dominantPattern: 'none',
          filesModified: new Set(),
          decliningScoreStreak: 0,
          lastActivityAt: Date.now(),
        }
        this.state.branchAssessments.set(branch.helixId, assessment)
      }

      // Process new steps
      for (const step of newSteps) {
        this.updateAssessment(assessment, step.annotation)
      }

      // Advance cursor
      this.state.cursors.set(branch.helixId, cursor + newSteps.length)
      this.stepsSinceLastAnalysis += newSteps.length
    }
  }

  /**
   * Update a branch assessment with a new annotation.
   */
  private updateAssessment(
    assessment: BranchAssessment,
    annotation: BrainstemAnnotation
  ): void {
    // Add score to trajectory
    assessment.scoreTrajectory.push(annotation.score)
    if (assessment.scoreTrajectory.length > 20) {
      assessment.scoreTrajectory.shift()
    }

    // Compute rolling score (average of last 5)
    const recentScores = assessment.scoreTrajectory.slice(-5)
    assessment.rollingScore =
      recentScores.reduce((a, b) => a + b, 0) / recentScores.length

    // Track dominant pattern (most frequent in last 5)
    const recentAnnotations = assessment.scoreTrajectory
      .slice(-5)
      .map((_, i) => {
        const idx = assessment.scoreTrajectory.length - 5 + i
        // We need to track annotations separately, but for now use the pattern
        return annotation.annotation
      })
    assessment.dominantPattern = this.computeDominantPattern(recentAnnotations)

    // Track files modified (use workUnitId as proxy)
    assessment.filesModified.add(annotation.workUnitId)

    // Track declining score streak
    if (assessment.scoreTrajectory.length >= 2) {
      const last = assessment.scoreTrajectory[assessment.scoreTrajectory.length - 1]
      const prev = assessment.scoreTrajectory[assessment.scoreTrajectory.length - 2]
      if (last < prev) {
        assessment.decliningScoreStreak++
      } else {
        assessment.decliningScoreStreak = 0
      }
    }

    // Update status based on conditions
    if (assessment.rollingScore < this.config.strugglingScoreThreshold) {
      assessment.status = 'struggling'
    } else if (assessment.decliningScoreStreak >= this.config.decliningScoreThreshold) {
      assessment.status = 'struggling'
    } else if (assessment.dominantPattern === 'drift') {
      assessment.status = 'drifting'
    } else {
      assessment.status = 'productive'
    }

    assessment.lastActivityAt = Date.now()
  }

  /**
   * Compute the dominant pattern from recent annotations.
   */
  private computeDominantPattern(annotations: WorkUnitAnnotation[]): WorkUnitAnnotation | 'none' {
    if (annotations.length === 0) return 'none'

    const counts = new Map<WorkUnitAnnotation, number>()
    for (const ann of annotations) {
      counts.set(ann, (counts.get(ann) ?? 0) + 1)
    }

    let maxCount = 0
    let dominant: WorkUnitAnnotation | 'none' = 'none'
    for (const [ann, count] of counts) {
      if (count > maxCount) {
        maxCount = count
        dominant = ann
      }
    }

    return dominant
  }

  /**
   * Detect cross-branch patterns.
   */
  private detectCrossPatterns(): CrossHelixPattern[] {
    const newPatterns: CrossHelixPattern[] = []
    const assessments = Array.from(this.state.branchAssessments.values())
    const branches = this.tree.getAllBranches()

    // 1. Conflict detection: Compare filesModified Sets across branches
    for (let i = 0; i < assessments.length; i++) {
      for (let j = i + 1; j < assessments.length; j++) {
        const a = assessments[i]
        const b = assessments[j]

        // Check for intersection in filesModified
        for (const file of a.filesModified) {
          if (b.filesModified.has(file)) {
            const pattern: CrossHelixPattern = {
              type: 'conflict',
              helixIds: [a.helixId, b.helixId],
              severity: 'high',
              detectedAt: Date.now(),
              description: `Branches ${a.helixId} and ${b.helixId} both modified work unit ${file}`,
              actedUpon: false,
            }
            if (this.isNewPattern(pattern)) {
              newPatterns.push(pattern)
              this.state.crossPatterns.push(pattern)
            }
            break
          }
        }
      }
    }

    // 2. Asymmetric progress: If one branch has 3+ more steps than a sibling
    for (const branch of branches) {
      if (!branch.parentId) continue

      const siblings = branches.filter(
        (b) => b.parentId === branch.parentId && b.depth === branch.depth
      )

      for (const sibling of siblings) {
        if (sibling.helixId === branch.helixId) continue

        const siblingAssessment = this.state.branchAssessments.get(sibling.helixId)
        if (!siblingAssessment) continue

        const stepDiff = branch.steps.length - sibling.steps.length
        if (stepDiff >= 3 && siblingAssessment.rollingScore < 0.5) {
          const pattern: CrossHelixPattern = {
            type: 'asymmetric-progress',
            helixIds: [branch.helixId, sibling.helixId],
            severity: 'medium',
            detectedAt: Date.now(),
            description: `${branch.helixId} has ${stepDiff} more steps than struggling sibling ${sibling.helixId}`,
            actedUpon: false,
          }
          if (this.isNewPattern(pattern)) {
            newPatterns.push(pattern)
            this.state.crossPatterns.push(pattern)
          }
        }
      }
    }

    // 3. Cascade failure: If 2+ branches have status 'failed' or 'struggling'
    // and were created within 30s of each other
    const problematicBranches = branches.filter(
      (b) => b.status === 'failed' || b.status === 'cancelled'
    )
    const strugglingAssessments = assessments.filter((a) => a.status === 'struggling')

    for (const assessment of strugglingAssessments) {
      const branch = branches.find((b) => b.helixId === assessment.helixId)
      if (branch) {
        problematicBranches.push(branch)
      }
    }

    for (let i = 0; i < problematicBranches.length; i++) {
      for (let j = i + 1; j < problematicBranches.length; j++) {
        const a = problematicBranches[i]
        const b = problematicBranches[j]

        if (Math.abs(a.createdAt - b.createdAt) <= 30000) {
          const pattern: CrossHelixPattern = {
            type: 'cascade-failure',
            helixIds: [a.helixId, b.helixId],
            severity: 'critical',
            detectedAt: Date.now(),
            description: `Cascade failure: ${a.helixId} and ${b.helixId} failed within 30s`,
            actedUpon: false,
          }
          if (this.isNewPattern(pattern)) {
            newPatterns.push(pattern)
            this.state.crossPatterns.push(pattern)
          }
        }
      }
    }

    // 4. Convergence: If 2+ branches have same dominantPattern === 'implementation'
    // and rollingScore > 0.7
    const implementationBranches = assessments.filter(
      (a) => a.dominantPattern === 'implementation' && a.rollingScore > 0.7
    )

    for (let i = 0; i < implementationBranches.length; i++) {
      for (let j = i + 1; j < implementationBranches.length; j++) {
        const a = implementationBranches[i]
        const b = implementationBranches[j]

        const pattern: CrossHelixPattern = {
          type: 'convergence',
          helixIds: [a.helixId, b.helixId],
          severity: 'low',
          detectedAt: Date.now(),
          description: `${a.helixId} and ${b.helixId} both in productive implementation`,
          actedUpon: false,
        }
        if (this.isNewPattern(pattern)) {
          newPatterns.push(pattern)
          this.state.crossPatterns.push(pattern)
        }
      }
    }

    // Emit pattern events
    for (const pattern of newPatterns) {
      this.emitEvent('corpus:pattern', pattern)
    }

    return newPatterns
  }

  /**
   * Check if a pattern is new (not already in state with same type+helixIds and actedUpon=false).
   */
  private isNewPattern(pattern: CrossHelixPattern): boolean {
    return !this.state.crossPatterns.some(
      (p) =>
        p.type === pattern.type &&
        p.helixIds.length === pattern.helixIds.length &&
        p.helixIds.every((id) => pattern.helixIds.includes(id)) &&
        !p.actedUpon
    )
  }

  /**
   * Check if we should run LLM analysis.
   */
  private shouldRunLLMAnalysis(): boolean {
    return this.stepsSinceLastAnalysis >= this.config.llmAnalysisThreshold
  }

  /**
   * Run LLM analysis with detected patterns.
   */
  private async runLLMAnalysis(patterns: CrossHelixPattern[]): Promise<void> {
    const prompt = this.buildLLMPrompt(patterns)

    try {
      const response = await this.deps.llm.complete({
        prompt,
        modelTier: this.config.modelTier,
        maxTokens: this.config.maxTokens,
        timeoutMs: this.config.timeoutMs,
      })

      const result = this.parseLLMResponse(response.content)

      // Send directives for interventions
      if (result.interventions) {
        for (const intervention of result.interventions) {
          await this.sendDirective(intervention)
        }
      }

      // Post synthesis to blackboard
      if (result.synthesis) {
        this.postToBlackboard('findings', result.synthesis, 'corpus-synthesis')
      }

      // Reset steps counter
      this.stepsSinceLastAnalysis = 0

      this.logger.info('LLM analysis completed', {
        assessment: result.assessment,
        interventionCount: result.interventions?.length ?? 0,
      })
    } catch (error) {
      this.logger.warn('LLM analysis failed', {
        error: error instanceof Error ? error.message : String(error),
      })
      // Continue loop despite LLM failure
    }
  }

  /**
   * Build LLM prompt for analysis.
   */
  private buildLLMPrompt(patterns: CrossHelixPattern[]): string {
    const branches = this.tree.getAllBranches()
    const assessments = Array.from(this.state.branchAssessments.values())

    const branchSummaries = branches
      .map((branch) => {
        const assessment = this.state.branchAssessments.get(branch.helixId)
        const recentSteps = branch.steps.slice(-3)
        const recentAnnotations = recentSteps
          .map((s) => `- ${s.annotation.annotation} (score: ${s.annotation.score.toFixed(2)}): ${s.annotation.trainingNote.slice(0, 100)}`)
          .join('\n')

        return `Branch: ${branch.helixId}
  Goal: ${branch.goal}
  Status: ${assessment?.status ?? 'unknown'}
  Rolling Score: ${assessment?.rollingScore.toFixed(2) ?? 'N/A'}
  Step Count: ${branch.steps.length}
  Dominant Pattern: ${assessment?.dominantPattern ?? 'none'}
  Recent Annotations:
${recentAnnotations || '  (none)'}`
      })
      .join('\n\n')

    const patternList = patterns
      .map((p) => `- [${p.severity}] ${p.type}: ${p.description}`)
      .join('\n') || 'None detected'

    return `I am the Corpus — the strategic organizer of this Constellation.
My goal: ${this.deps.goal}

I oversee ${branches.length} Helix branches, each with its own Brainstem handling tactical work.
My role is strategic: detect cross-branch patterns, coordinate effort, prevent waste.

Current branches:
${branchSummaries}

Detected cross-branch patterns:
${patternList}

Based on this, I will:
1. Assess the overall constellation health
2. Identify any branches that need intervention
3. Produce a strategic synthesis

ASSESSMENT: <one-line overall health>
INTERVENTION[helixId]: <urgency> <directive text>
SYNTHESIS: <strategic summary for Cassi>`
  }

  /**
   * Parse LLM response.
   */
  private parseLLMResponse(content: string): {
    assessment: string
    interventions: CorpusDirective[]
    synthesis: string
  } {
    const assessmentMatch = content.match(/ASSESSMENT:\s*(.+)/i)
    const synthesisMatch = content.match(/SYNTHESIS:\s*(.+)/i)

    const interventions: CorpusDirective[] = []
    const interventionRegex = /INTERVENTION\[([^\]]+)\]:\s*(\w+)\s*(.+)/gi
    let match
    while ((match = interventionRegex.exec(content)) !== null) {
      interventions.push({
        targetHelixId: match[1].trim(),
        urgency: match[2].trim() as 'low' | 'medium' | 'high' | 'critical',
        message: match[3].trim(),
        issuedAt: Date.now(),
      })
    }

    return {
      assessment: assessmentMatch?.[1]?.trim() ?? 'unknown',
      interventions,
      synthesis: synthesisMatch?.[1]?.trim() ?? '',
    }
  }

  /**
   * Send a directive to a child Brainstem.
   */
  private async sendDirective(directive: CorpusDirective): Promise<void> {
    const brainstem = this.childBrainstems.get(directive.targetHelixId)

    if (!brainstem) {
      this.logger.warn('Brainstem not found for directive', {
        helixId: directive.targetHelixId,
      })
      return
    }

    if (brainstem.onCorpusDirective) {
      try {
        brainstem.onCorpusDirective(directive)
      } catch (error) {
        this.logger.warn('Failed to send directive to Brainstem', {
          helixId: directive.targetHelixId,
          error: error instanceof Error ? error.message : String(error),
        })
      }
    }

    // Record intervention
    const intervention: CorpusIntervention = {
      targetHelixId: directive.targetHelixId,
      directive: directive.message,
      urgency: directive.urgency,
      issuedAt: Date.now(),
      sweepNumber: this.state.sweepCount,
      acknowledged: false,
    }
    this.state.interventions.push(intervention)

    // Post to blackboard
    this.postToBlackboard(
      'decisions',
      `Intervention for ${directive.targetHelixId} [${directive.urgency}]: ${directive.message}`,
      'corpus-intervention'
    )

    // Emit event
    this.emitEvent('corpus:intervention', intervention)
  }

  /**
   * Build spawn evaluation prompt.
   */
  private buildSpawnEvaluationPrompt(request: {
    helixId: string
    template: string
    goal: string
    depth: number
    reason: string
  }): string {
    const branches = this.tree.getAllBranches()
    const activeBranches = branches.filter((b) => b.status === 'active').length

    return `I am the Corpus — evaluating a spawn request.

Constellation goal: ${this.deps.goal}
Current active branches: ${activeBranches}
Maximum allowed depth: ${this.config.maxDepth}

Spawn Request:
- Requesting Helix: ${request.helixId}
- Template: ${request.template}
- Proposed Goal: ${request.goal}
- Proposed Depth: ${request.depth}
- Reason: ${request.reason}

Evaluate this request considering:
1. Resource constraints (too many active branches?)
2. Depth limits (would exceed maxDepth?)
3. Goal alignment (does it serve the constellation goal?)
4. Necessity (is spawning actually needed?)

Respond with:
DECISION: APPROVED or REJECTED
REASON: <explanation>
SUGGESTED_TEMPLATE: <template name if different> (optional)
SUGGESTED_GOAL: <refined goal> (optional)`
  }

  /**
   * Parse spawn decision from LLM response.
   */
  private parseSpawnDecision(
    content: string,
    request: {
      helixId: string
      template: string
      goal: string
      depth: number
      reason: string
    }
  ): SpawnDecision {
    const decisionMatch = content.match(/DECISION:\s*(APPROVED|REJECTED)/i)
    const reasonMatch = content.match(/REASON:\s*(.+)/im)
    const templateMatch = content.match(/SUGGESTED_TEMPLATE:\s*(.+)/i)
    const goalMatch = content.match(/SUGGESTED_GOAL:\s*(.+)/i)

    const approved = decisionMatch?.[1]?.toUpperCase() === 'APPROVED'

    return {
      approved,
      reason: reasonMatch?.[1]?.trim() ?? 'No reason provided',
      suggestedTemplate: templateMatch?.[1]?.trim(),
      suggestedGoal: goalMatch?.[1]?.trim(),
      evaluatedAt: Date.now(),
      request,
    }
  }

  /**
   * Emit an event to the event bus.
   */
  private emitEvent(type: string, data: unknown): void {
    if (this.deps.eventBus) {
      this.deps.eventBus
        .emit({ type, data, timestamp: Date.now() } as any)
        .catch((err) => {
          this.logger.warn('Failed to emit event', { type, error: err })
        })
    }
  }

  /**
   * Post to blackboard.
   */
  private postToBlackboard(
    channel: 'findings' | 'concerns' | 'decisions',
    content: string,
    author: string
  ): void {
    if (this.deps.blackboard) {
      try {
        this.deps.blackboard.post(channel, {
          author,
          content,
          timestamp: Date.now(),
        })
      } catch (error) {
        this.logger.warn('Failed to post to blackboard', {
          channel,
          error: error instanceof Error ? error.message : String(error),
        })
      }
    }
  }
}

/**
 * Factory function to create a Corpus instance.
 */
export function createCorpus(
  tree: ICorpusTree,
  deps: CorpusDeps,
  config?: Partial<CorpusConfig>
): Corpus {
  return new Corpus(tree, deps, config)
}
