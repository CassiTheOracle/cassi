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
} from './corpus-types.js'
import { ESCALATION_DEFAULTS } from './corpus-types.js'
import type { SpawnRequest, ConstellationTemplate } from './types.js'
import {
  DEFAULT_CORPUS_CONFIG,
  createInitialProcessedState,
} from './corpus-types.js'
import type { BrainstemAnnotation, WorkUnitAnnotation, DetectedPattern, GuidanceUrgency } from '../helix/brainstem-types.js'
import {
  executeCorpusTool,
  buildCorpusSystemPrompt,
  getCorpusToolDefinitions,
} from './corpus-tools.js'
import type { CorpusToolContext, ToolCallResult } from './corpus-tools.js'

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

  // LLM health tracking
  private llmHealthy = true
  private llmFailureCount = 0
  private static readonly LLM_FAILURE_THRESHOLD = 2 // Mark unhealthy after 2 consecutive failures

  // Timing
  private startTime = 0

  // Counter for LLM analysis triggering
  private newStepsSinceLLM = 0

  // Safety-net mode: tracks when the last LLM analysis ran
  private lastAnalysisSweep = 0
  // Escalation queue: reasons from Brainstems that self-org can't resolve
  private escalationQueue: Array<{ reason: string; context: Record<string, unknown> }> = []

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
      avgGoalAlignment: ba.avgGoalAlignment,
      avgNovelty: ba.avgNovelty,
      avgProgress: ba.avgProgress,
      escalationLevel: ba.escalationLevel,
      ignoredDirectiveStreak: ba.ignoredDirectiveStreak,
    }))

    return {
      tree: this.tree.getSnapshot(),
      branchAssessments: assessments,
      crossPatterns: [...this.state.crossPatterns],
      interventions: [...this.state.interventions],
      spawnDecisions: [...this.state.spawnDecisions],
      sweepCount: this.state.sweepCount,
      llmHealthy: this.llmHealthy,
      llmFailureCount: this.llmFailureCount,
      durationMs: this.startTime > 0 ? Date.now() - this.startTime : 0,
    }
  }

  /**
   * Check if Corpus LLM is healthy (able to make strategic decisions)
   */
  isLLMHealthy(): boolean {
    return this.llmHealthy
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
          // Idle poll
          await this.sleep(this.config.idlePollMs)
          continue
        }

        // Process new steps
        this.processNewSteps()

        // Evaluate escalation for all active branches
        this.evaluateAllEscalations()

        // Detect cross-branch patterns
        const newPatterns = this.detectCrossPatterns()

        // Run LLM analysis if needed
        if (newPatterns.length > 0 || this.shouldRunLLMAnalysis()) {
          await this.runLLMAnalysis(newPatterns)
        }

        // Auto-spawn check: if a branch has received many interventions
        // without improvement, decompose its goal via spawn
        this.checkAutoSpawn()

        // Mediate cross-Helix dialectic if tensions have accumulated
        this.mediateCrossHelixDialectic()

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
      avgGoalAlignment: 0.5,
      avgNovelty: 0.5,
      avgProgress: 0.3,
      directiveHistory: [],
      escalationLevel: 0,
      ignoredDirectiveStreak: 0,
      lowProgressStreak: 0,
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

    // ─── Dimensional Score Averages (rolling last 5) ───────────────
    const recentSteps = branch.steps.slice(-5)
    if (recentSteps.length > 0) {
      assessment.avgGoalAlignment = recentSteps.reduce((s, st) => s + (st.annotation.goalAlignment ?? 0.5), 0) / recentSteps.length
      assessment.avgNovelty = recentSteps.reduce((s, st) => s + (st.annotation.novelty ?? 0.5), 0) / recentSteps.length
      assessment.avgProgress = recentSteps.reduce((s, st) => s + (st.annotation.progress ?? 0.3), 0) / recentSteps.length
    }

    // ─── Low-Progress Streak Tracking ─────────────────────────────
    // Count consecutive steps where progress is below the escalation threshold.
    // Uses the template's threshold, falling back to 0.12 (standard default).
    const thresholds = this.getEscalationThresholds(branch.helixId)
    const latestAnnotation = newSteps[newSteps.length - 1]?.annotation
    if (latestAnnotation && (latestAnnotation.progress ?? 0.3) < thresholds.minProgressThreshold) {
      assessment.lowProgressStreak++
    } else {
      assessment.lowProgressStreak = 0
    }

    // ─── Directive Behavioral Change Detection ────────────────────
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

    // De-duplicate against existing patterns (tight 15s window to avoid spam)
    const now = Date.now()
    const newPatterns: CrossHelixPattern[] = []
    for (const pattern of patterns) {
      const isDuplicate = this.state.crossPatterns.some(
        (existing) =>
          existing.type === pattern.type &&
          existing.helixIds.length === pattern.helixIds.length &&
          existing.helixIds.every((id) => pattern.helixIds.includes(id)) &&
          now - existing.detectedAt < 15000 // Within 15 seconds (was 60s — caused 31+ dupes)
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

    // Prune old patterns to prevent unbounded growth (keep last 50)
    if (this.state.crossPatterns.length > 50) {
      this.state.crossPatterns = this.state.crossPatterns.slice(-50)
    }

    return newPatterns
  }

  /**
   * Check if we should run LLM analysis
   */
  private shouldRunLLMAnalysis(): boolean {
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
    const systemPrompt = buildCorpusSystemPrompt(
      this.deps.goal,
      this.state,
      this.tree,
      newPatterns
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

    const toolDefs = getCorpusToolDefinitions()

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

    try {
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
      const response = await this.deps.llm.complete({
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

        const result = executeCorpusTool(call.name, call.args, ctx)
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

      // Reset failure tracking on success
      if (!this.llmHealthy) {
        this.logger.info('Corpus LLM recovered after previous failures', {
          previousFailures: this.llmFailureCount,
        })
      }
      this.llmHealthy = true
      this.llmFailureCount = 0
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
      const response = await this.deps.llm.complete({
        prompt,
        modelTier: this.config.modelTier,
        maxTokens: this.config.maxTokens,
        timeoutMs: this.config.timeoutMs,
      })

      this.parseAndApplyLLMResponse(response.content)
      this.newStepsSinceLLM = 0

      // Reset failure tracking on success
      if (!this.llmHealthy) {
        this.logger.info('Corpus LLM recovered after previous failures', {
          previousFailures: this.llmFailureCount,
        })
      }
      this.llmHealthy = true
      this.llmFailureCount = 0
    } catch (error) {
      this.handleLLMFailure(error)
    }
  }

  /**
   * Common error handling for LLM failures.
   */
  private handleLLMFailure(error: unknown): void {
    this.llmFailureCount++
    const errorMsg = error instanceof Error ? error.message : String(error)

    if (this.llmFailureCount >= Corpus.LLM_FAILURE_THRESHOLD && this.llmHealthy) {
      // Mark unhealthy and emit critical event
      this.llmHealthy = false
      this.logger.error('Corpus LLM is unhealthy — constellation running without strategic oversight', {
        error: errorMsg,
        failureCount: this.llmFailureCount,
        sweepCount: this.state.sweepCount,
      })
      this.emitEvent('corpus:unhealthy', {
        reason: 'llm_failure',
        error: errorMsg,
        failureCount: this.llmFailureCount,
        message: 'Corpus LLM failed repeatedly. Constellation Helix branches are running without strategic planning, intervention, or spawn decisions.',
      })
    } else {
      this.logger.warn('Corpus LLM analysis failed, continuing loop', {
        error: errorMsg,
        failureCount: this.llmFailureCount,
        threshold: Corpus.LLM_FAILURE_THRESHOLD,
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

    return `I am the strategic organizer of this Constellation. My goal: ${this.deps.goal}. I oversee ${branches.length} branches, analyzing cross-branch patterns and making spawn/intervention decisions.

## Branch Assessments
${branchDetails}${patternDetails}${dialecticSection}${interventionHistorySection}${spawnHistorySection}

## Task
Provide strategic assessment:

ASSESSMENT: <brief assessment of overall constellation health>
INTERVENTION[helixId]: <directive type:guidance|redirect|throttle|priority-shift|cancel>:<urgency:low|medium|high|critical>:<first-person guidance text> (or NONE)
SPAWN[parentHelixId]: <goal for new sub-branch> (or NONE)
SYNTHESIS: <strategic synthesis, or NONE>

Guidelines:
- ASSESSMENT: Summarize the health of all branches and any concerning patterns
- INTERVENTION: Only if a specific branch needs steering. Use helixId from above. Write guidance in first person ("I should..." not "Do X").
- SPAWN: Request a new sub-branch when:
  (a) A branch reveals a sub-problem that would benefit from dedicated, parallel investigation
  (b) A branch has received 3+ interventions without meaningful improvement (avgScore still declining)
  (c) The goal naturally decomposes into independent sub-problems that could run concurrently
  Use the parentHelixId of the branch that surfaced the need. Each spawn should have a focused, specific goal. NONE if no spawn needed.
- SYNTHESIS: Strategic insights for the Constellation level, or NONE if routine
- Review "My Previous Interventions" — avoid repeating the same intervention if it didn't work. Escalate instead.
- Be concise — this runs in a tight loop`
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
      const type = this.normalizeDirectiveType(rawType)
      const urgency = this.normalizeUrgency(rawUrgency)

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

  /** Normalize a directive type string to a valid CorpusDirectiveType */
  private normalizeDirectiveType(raw: string): CorpusDirectiveType | null {
    const map: Record<string, CorpusDirectiveType> = {
      'guidance': 'guidance',
      'guide': 'guidance',
      'suggest': 'guidance',
      'redirect': 'redirect',
      'refocus': 'redirect',
      'change': 'redirect',
      'throttle': 'throttle',
      'slow': 'throttle',
      'priority-shift': 'priority-shift',
      'priority': 'priority-shift',
      'prioritize': 'priority-shift',
      'cancel': 'cancel',
      'stop': 'cancel',
      'abort': 'cancel',
    }
    return map[raw] ?? null
  }

  /** Normalize an urgency string to a valid GuidanceUrgency */
  private normalizeUrgency(raw: string): GuidanceUrgency | null {
    const map: Record<string, GuidanceUrgency> = {
      'low': 'low',
      'medium': 'medium',
      'med': 'medium',
      'moderate': 'medium',
      'high': 'high',
      'critical': 'critical',
      'urgent': 'critical',
    }
    return map[raw] ?? null
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

      // ─── Record directive for behavioral tracking ──────────────
      const assessment = this.state.branchAssessments.get(directive.targetHelixId)
      if (assessment) {
        const branch = this.tree.getBranch(directive.targetHelixId)
        const currentStep = branch ? branch.steps.length : 0
        const latestAnnotation = branch?.steps[branch.steps.length - 1]?.annotation
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

    // ─── Directive-failure signal ─────────────────────────────────
    const directiveSignal = assessment.ignoredDirectiveStreak >= thresholds.directiveFailuresForEscalation

    // ─── Metric-based signal ─────────────────────────────────────
    const metricSignal = assessment.lowProgressStreak >= thresholds.lowProgressStepsForEscalation
      || (assessment.rollingScore < thresholds.lowScoreThreshold
          && assessment.scoreTrajectory.length >= thresholds.lowScoreStepsForEscalation)

    // ─── Combined escalation logic ───────────────────────────────
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
  private evaluateAllEscalations(): void {
    for (const [helixId, assessment] of this.state.branchAssessments) {
      // Skip completed/failed branches
      if (assessment.status === 'completed' || assessment.status === 'failed') continue

      const newLevel = this.evaluateEscalation(assessment)
      if (newLevel === null) continue

      // Act on the escalation level
      switch (newLevel) {
        case 1:
          // Level 1: Send guidance directive (soft)
          this.sendDirective({
            targetHelixId: helixId,
            type: 'guidance',
            urgency: 'medium',
            text: `Branch ${helixId} is underperforming. Please refocus on the goal and produce concrete output.`,
            reason: `Escalation to level 1: ignored=${assessment.ignoredDirectiveStreak} directives, lowProgress=${assessment.lowProgressStreak} steps`,
            timestamp: Date.now(),
            fromPattern: 'asymmetric-progress',
          })
          break

        case 2:
          // Level 2: Send critical redirect (hard)
          this.sendDirective({
            targetHelixId: helixId,
            type: 'redirect',
            urgency: 'critical',
            text: `Branch ${helixId} has ignored multiple directives and metrics are declining. ` +
              `You must change approach immediately: narrow scope, switch strategy, or conclude with current findings.`,
            reason: `Escalation to level 2: ignored=${assessment.ignoredDirectiveStreak} directives, lowProgress=${assessment.lowProgressStreak} steps`,
            timestamp: Date.now(),
            fromPattern: 'cascade-failure',
          })
          break

        case 3:
          // Level 3: Cancel the branch
          this.logger.warn('Escalation level 3: cancelling branch', { helixId })
          this.sendDirective({
            targetHelixId: helixId,
            type: 'cancel',
            urgency: 'critical',
            text: `Branch ${helixId} has reached escalation level 3. Cancelling due to sustained non-response to directives and declining metrics.`,
            reason: `Escalation to level 3: ignored=${assessment.ignoredDirectiveStreak} directives, score=${assessment.rollingScore.toFixed(2)}`,
            timestamp: Date.now(),
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
    const prompt = `I am evaluating a spawn request for this Constellation.

## Current Tree State
Active branches: ${branches.length}
Total steps: ${this.tree.totalStepCount()}

## Spawn Request
Requesting branch: ${request.requestingHelixId}
Proposed Goal: ${request.goal}
Proposed Template: ${request.template ?? 'standard'}
Target Depth: ${request.targetDepth}

## Task
Evaluate this spawn request:

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
      this.llmFailureCount++
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
