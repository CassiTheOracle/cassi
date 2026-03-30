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
} from './corpus-types.js'
import { ESCALATION_DEFAULTS, BRANCH_BUDGET_DEFAULTS } from './corpus-types.js'
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

  // ── Proactive Behavior State ──────────────────────────────────
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

        // ── Proactive: Budget tracking ──────────────────────────────
        this.trackBudgets()

        // ── Proactive: Discovery routing ────────────────────────────
        if (this.config.proactive.enableDiscoveryRouting) {
          this.routeDiscoveries()
        }

        // Evaluate escalation for all active branches
        this.evaluateAllEscalations()

        // ── Proactive: Re-decomposition evaluation ──────────────────
        if (this.config.proactive.enableReDecomposition) {
          await this.evaluateReDecomposition()
        }

        // ── Proactive: Parallel acceleration ────────────────────────
        if (this.config.proactive.enableParallelAcceleration) {
          await this.evaluateParallelAcceleration()
        }

        // ── Proactive: Context injection for struggling branches ────
        if (this.config.proactive.enableContextInjection) {
          await this.evaluateContextInjection()
        }

        // ── Proactive: Quality gates for completed branches ─────────
        if (this.config.proactive.enableQualityGates) {
          await this.runQualityGates()
        }

        // ── Proactive: Research caching for completed research branches ─
        if (this.config.proactive.enableResearchCaching) {
          this.buildResearchDigests()
        }

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
        if (digest?.currentNextSteps && digest.currentNextSteps.length > 0) {
          lines.push(`Planned next steps:`)
          for (const ns of digest.currentNextSteps.slice(0, 3)) lines.push(`  - ${ns}`)
        }
        if (digest?.recentOutputs && digest.recentOutputs.length > 0) {
          lines.push(`Recent outputs: ${digest.recentOutputs.slice(-3).join(', ')}`)
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

    return `I am the strategic organizer of this Constellation. My goal: ${this.deps.goal}. I oversee ${branches.length} active threads, each thinking in parallel. I synthesize their knowledge, detect patterns, provide specific guidance, and spawn new threads when gaps emerge.

## Active Threads
${branchDetails}${patternDetails}${dialecticSection}${interventionHistorySection}${spawnHistorySection}

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


  // ═══════════════════════════════════════════════════════════════════
  // PROACTIVE BEHAVIORS — Budget, Discovery, Re-decomposition, etc.
  // ═══════════════════════════════════════════════════════════════════


  // ── 1. Branch Budget Tracking ─────────────────────────────────────

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


  // ── 2. Discovery Routing (Push + Broadcast) ───────────────────────

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
              .flatMap(tc => this.extractFilePaths(tc.args))
              .filter(Boolean),
            timestamp: Date.now(),
            deliveredTo: new Set([branch.helixId]),
          }

          this.discoveries.set(discoveryId, discovery)
          this.discoveryCounter++

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


  // ── 3. Mid-Flight Re-Decomposition ────────────────────────────────

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


  // ── 4. Direct Injection (Pause-Inject-Resume) ─────────────────────

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


  // ── 5. Research Caching — Build digests from completed research branches ─

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
              .flatMap(tc => this.extractFilePaths(tc.args))
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


  // ── 6. Quality Gates — Verify branch output before accepting completion ─

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


  // ── 7. Parallel Acceleration — Split productive branches ──────────

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


  // ── 8. Strategic Context Injection ────────────────────────────────

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
        .flatMap(tc => this.extractFilePaths(tc.args))
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


  // ── 9. Full Trajectory Context Builder (256k window) ──────────────

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


  // ── Helper: Extract file paths from tool call args ────────────────

  /**
   * Extract file paths from tool call arguments.
   * Handles various argument formats (JSON string, object, etc.)
   */
  private extractFilePaths(args: string | Record<string, unknown> | unknown): string[] {
    const paths: string[] = []

    try {
      const obj = typeof args === 'string' ? JSON.parse(args) : args
      if (!obj || typeof obj !== 'object') return paths

      const record = obj as Record<string, unknown>

      // Common path field names
      for (const key of ['path', 'relative_path', 'filePath', 'file_path', 'file']) {
        if (typeof record[key] === 'string' && record[key]) {
          paths.push(record[key] as string)
        }
      }
    } catch {
      // Not parseable — ignore
    }

    return paths
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
