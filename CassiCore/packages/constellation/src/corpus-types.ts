/**
 * Corpus Types — Constellation-Level Cognitive Organizer
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
  BrainstemAnnotation,
  DetectedPattern,
  GuidanceUrgency,
  WorkUnitAnnotation,
} from '../helix/brainstem-types.js'
import type { FlexPosture, ConstellationTemplate } from './types.js'
import type { WorkflowDefinition, WorkflowRun } from '../../../types/workflow.js'


// Corpus Tree — The shared reasoning structure

/**
 * A single step in a Corpus branch.
 * Each step is one BrainstemAnnotation pushed by a child Helix's Brainstem.
 */
export interface CorpusStep {
  annotation: BrainstemAnnotation
  pushedAt: number
  toolCalls?: Array<{ name: string; args: string }>
}

/**
 * A branch in the Corpus tree — one per Helix in the Constellation.
 * Brainstems push annotations into their branch as they score work units.
 */
export interface CorpusBranch {
  helixId: string
  goal: string
  depth: number
  parentId?: string
  steps: CorpusStep[]
  status: CorpusBranchStatus
  createdAt: number
  closedAt?: number
}

/**
 * Branch lifecycle status.
 *
 * WHY: 'active' means the Helix is running and pushing annotations.
 * The other three are terminal states that close the branch.
 */
export type CorpusBranchStatus =
  | 'active'
  | 'completed'
  | 'cancelled'
  | 'failed'

/**
 * Interface for the shared Corpus tree data structure.
 *
 * Brainstems write to it (pushAnnotation). The Corpus and Cassi read from it.
 * The tree is the single source of truth for what every Helix is doing.
 */
export interface ICorpusTree {
  /** Push an annotation into a Helix's branch. Creates branch if needed. */
  pushAnnotation(helixId: string, annotation: BrainstemAnnotation, toolCalls?: Array<{ name: string; args: string }>): void

  /** Register a new branch when a Helix starts. */
  registerBranch(helixId: string, goal: string, depth: number, parentId?: string): void

  /** Mark a branch as completed/cancelled/failed. */
  closeBranch(helixId: string, status: 'completed' | 'cancelled' | 'failed'): void

  /** Read a single branch. */
  getBranch(helixId: string): CorpusBranch | undefined

  /** Read all branches. */
  getAllBranches(): CorpusBranch[]

  /** Count unprocessed steps across all branches (relative to given cursors). */
  pendingStepCount(cursors: Map<string, number>): number

  /** Serializable snapshot of the full tree for progress reporting. */
  getSnapshot(): CorpusTreeSnapshot

  /** Total steps across all branches. */
  totalStepCount(): number

  /** Number of active branches. */
  activeBranchCount(): number


  /** Update a branch's digest (compact summary of its current state). */
  updateDigest(helixId: string, digest: BranchDigest): void

  /** Get all digests except the caller's own, for peer awareness. */
  getDigestsExcluding(helixId: string): BranchDigest[]

  /** Get all digests for all branches (including inactive). */
  getAllDigests(): BranchDigest[]

  /** Get the digest for a specific branch, if one exists. */
  getDigestFor(helixId: string): BranchDigest | undefined

  /**
   * Lightweight update — sets only the liveStreamSnippet on an existing digest.
   * Called on every Unity stream event. Pure in-memory update, no LLM work.
   * No-op if no digest exists yet for this branch.
   */
  updateLiveStreamSnippet(helixId: string, snippet: string): void

  /** Get digests filtered by relevance (file overlap, goal similarity). No artificial truncation. */
  getRelevantDigests(helixId: string): BranchDigest[]

  /** Create a new shared topic node. Returns the topic ID. */
  createTopic(name: string, createdBy: string, contribution: TopicContribution): string

  /** Add a contribution to an existing topic. */
  contributeTopic(topicId: string, contribution: TopicContribution): void

  /** Find topics relevant to a set of files and goal keywords. */
  findRelatedTopics(files: string[], goalKeywords: string[]): TopicNode[]

  /** Get all topic nodes. */
  getAllTopics(): TopicNode[]

  /** Record a strategy retrospective (why an approach changed). */
  recordRetrospective(helixId: string, retrospective: StrategyRetrospective): void

  /** Get all retrospectives across the constellation. */
  getAllRetrospectives(): StrategyRetrospective[]

  /** Elevate a successful pattern to the constellation-level pattern library. */
  elevatePattern(pattern: ElevatedPattern): void

  /** Get all elevated patterns (constellation-level knowledge). */
  getElevatedPatterns(): ElevatedPattern[]

  /** Record an effectiveness measurement for an intervention or self-org adjustment. */
  recordEffectiveness(record: EffectivenessRecord): void

  /** Get all effectiveness records. */
  getEffectivenessRecords(): EffectivenessRecord[]
}



export interface CorpusBranchSnapshot {
  helixId: string
  goal: string
  depth: number
  parentId?: string
  status: CorpusBranchStatus
  stepCount: number
  latestScore?: number
  latestAnnotation?: WorkUnitAnnotation
  latestPattern?: DetectedPattern
  averageScore: number
  createdAt: number
  closedAt?: number
  digest?: BranchDigest
}


// Shared Thought Tree — Self-Organizing Constellation

/**
 * Branch Digest — A compact, Brainstem-generated summary of a Helix's
 * current state. Published to the shared tree so peer Helixes can read
 * each other's progress without parsing raw annotations.
 *
 * Brainstems auto-generate digests every N work units. No LLM call —
 * purely local aggregation from existing annotation data.
 *
 * With 128k context windows, we can afford full untruncated digests
 * for all branches. Budget target: ~16k total for tree awareness.
 */
export interface BranchDigest {
  helixId: string
  goalSummary: string
  approach: BranchApproach
  progress: number
  filesActive: string[]
  keyFindings: string[]
  blockers: string[]
  currentStrategy: string
  rollingScore: number
  workUnitsProcessed: number
  updatedAt: number
  lastApproachChangeReason?: string

  currentHypothesis?: string
  allDiscoveries?: string[]
  allDecisions?: string[]
  currentNextSteps?: string[]
  recentOutputs?: string[]
  liveStreamSnippet?: string
  selfOrgSignals?: Array<{
    type: string
    description: string
    evidence: string
  }>
  currentBlockers?: Array<{
    description: string
    detectedAt: number
    severity: 'low' | 'medium' | 'high' | 'critical'
    relatedFiles?: string[]
  }>
  confidenceLevel?: {
    score: number
    trend: 'rising' | 'stable' | 'falling'
    factors: string[]
    updatedAt: number
  }
  estimatedTimeToCompletion?: {
    minutes: number
    confidence: number
    basedOnSteps: number
    updatedAt: number
  }
}

/**
 * Approach patterns for a Helix branch.
 *
 * WHY: These are higher-level than WorkUnitAnnotation patterns — they describe
 * strategic mode, not just what the LLM did in one turn. The Corpus uses these
 * to detect cross-branch patterns (redundancy, convergence, etc.).
 */
export type BranchApproach =
  | 'exploration'
  | 'research'
  | 'implementation'
  | 'testing'
  | 'debugging'
  | 'revision'
  | 'coordinating'

/**
 * Shared topic node — emergent cross-cutting concerns that any Helix
 * can read and contribute to. Topics are auto-created by Brainstems
 * when they detect shared files, related goals, or cross-cutting insights.
 *
 * This is the stigmergic coordination mechanism: Helixes modify the
 * shared environment (topics), and other Helixes react to those
 * modifications, creating emergent order without explicit messaging.
 */
export interface TopicNode {
  id: string
  name: string
  contributions: TopicContribution[]
  tensionFlag: boolean
  tensionDescription?: string
  relatedFiles: string[]
  createdAt: number
  createdBy: string
  lastContributionAt: number
}

/**
 * A single contribution to a shared topic node.
 */
export interface TopicContribution {
  helixId: string
  content: string
  approach: BranchApproach
  files: string[]
  score: number
  timestamp: number
}


// Self-Awareness — Retrospectives, Effectiveness, Pattern Library

/**
 * Strategy Retrospective — recorded when a Brainstem changes its approach.
 * Answers "why did I change?" — builds a log of what worked and what didn't,
 * enabling self-improvement across the constellation.
 */
export interface StrategyRetrospective {
  helixId: string
  fromApproach: BranchApproach
  toApproach: BranchApproach
  reason: string
  trigger: RetrospectiveTrigger
  scoreAtChange: number
  scoreAfterChange?: number
  stepsAfterMeasured?: number
  wasEffective?: boolean
  timestamp: number
}

/**
 * What triggered a strategy change.
 *
 * WHY: These distinguish between internal triggers (score-decline, pattern-detected)
 * and social triggers (self-organization, corpus-directive, peer-convergence).
 * This matters for learning which coordination mechanisms work best.
 */
export type RetrospectiveTrigger =
  | 'self-organization'
  | 'corpus-directive'
  | 'score-decline'
  | 'pattern-detected'
  | 'topic-tension'
  | 'peer-convergence'
  | 'goal-refinement'
  | 'manual'

/**
 * Elevated Pattern — a successful strategy that a completed branch
 * demonstrated. Elevated to constellation-level knowledge so other
 * branches (current and future) can learn from it.
 *
 * The pattern library is the constellation's long-term memory.
 */
export interface ElevatedPattern {
  id: string
  sourceHelixId: string
  approach: BranchApproach
  description: string
  applicableContext: string
  achievedScore: number
  relevantFiles: string[]
  supportingRetrospectives: string[]
  elevatedAt: number
  referenceCount: number
}

/**
 * Self-organization adjustment — produced by a Brainstem's selfOrganize()
 * method after reading the shared tree. Feeds into the guidance queue.
 *
 * HOW: Dampening prevents overreaction to transient peer state. The adjustment
 * must be confirmed N times (across sweeps) before it fires. This implements
 * a simple hysteresis loop.
 */
export interface SelfOrgAdjustment {
  type: SelfOrgAdjustmentType
  description: string
  evidence: string
  sourceHelixId?: string
  sourceTopicId?: string
  dampeningCount: number
  dampeningThreshold: number
  firstGeneratedAt: number
  lastConfirmedAt: number
}

/**
 * Types of self-organization adjustments.
 *
 * WHY: These are the coordination primitives. file-avoidance prevents conflicts,
 * finding-incorporation enables knowledge transfer, approach-redirect enables
 * peer learning, goal-refinement reduces redundancy, tension-flag surfaces
 * conflicts for Corpus resolution.
 */
export type SelfOrgAdjustmentType =
  | 'file-avoidance'
  | 'finding-incorporation'
  | 'approach-redirect'
  | 'goal-refinement'
  | 'tension-flag'
  | 'pattern-adoption'
  | 'peer-assist'

/**
 * Effectiveness tracking entry — links a self-org adjustment to its
 * measured outcome. This is how the constellation learns what works.
 */
export interface EffectivenessRecord {
  adjustmentType: SelfOrgAdjustmentType
  helixId: string
  scoreBefore: number
  scoreAfter: number
  stepsDelta: number
  improvement: number
  effective: boolean
  measuredAt: number
  timeToResolutionMs?: number
  qualityMetrics?: {
    codeQualityDelta?: number
    testCoverageDelta?: number
    documentationDelta?: number
  }
  branchSatisfaction?: {
    score: number
    comment?: string
    wouldRecommend: boolean
  }
  constellationImpact?: {
    helpedBranches: string[]
    hinderedBranches: string[]
    netImpact: 'positive' | 'neutral' | 'negative'
  }
}


// Extended Tree Snapshot — includes shared thought tree state

export interface CorpusTreeSnapshot {
  branches: CorpusBranchSnapshot[]
  totalSteps: number
  activeBranches: number
  snapshotAt: number
  digests: BranchDigest[]
  topics: TopicNode[]
  retrospectives: StrategyRetrospective[]
  elevatedPatterns: ElevatedPattern[]
  effectivenessRecords: EffectivenessRecord[]
  /** Topology spatial state — positions, links, clusters. Present when topology is enabled. */
  topology?: import('./topology/topology-types.js').SerializableTopologySnapshot
}

/**
 * The Corpus's internal processed state.
 * Built by analyzing the shared tree. Brainstem pushes are treated as raw
 * input that the Corpus organizes into its own strategic understanding.
 */
// Dual-Ledger Planning (Magentic-One pattern)
// WHY: Separating planning state (what to do) from execution state (what's been done)
// enables the Corpus to reason about gaps between plans and reality, detect stalls
// earlier, and provide more targeted directives.

/** Task Ledger — what needs to be done (planning state) */
export interface TaskLedger {
  /** The top-level goal for this Constellation */
  goal: string
  /** Known facts discovered during execution */
  facts: LedgerFact[]
  /** Hypotheses/guesses that need verification */
  guesses: LedgerGuess[]
  /** Open questions that might affect the plan */
  openQuestions: LedgerQuestion[]
  /** Last time the task ledger was updated */
  lastUpdatedAt: number
}

/** A discovered fact in the Task Ledger */
export interface LedgerFact {
  id: string
  content: string
  source: string       // helixId or 'corpus' or 'user'
  discoveredAt: number
  /** Which task/guess this fact relates to (if any) */
  relatedTaskId?: string
}

/** A hypothesis in the Task Ledger that needs verification */
export interface LedgerGuess {
  id: string
  content: string
  source: string
  createdAt: number
  /** 'unverified' | 'confirmed' | 'refuted' */
  status: 'unverified' | 'confirmed' | 'refuted'
  verifiedAt?: number
  verifiedBy?: string  // helixId
}

/** An open question in the Task Ledger */
export interface LedgerQuestion {
  id: string
  content: string
  source: string
  askedAt: number
  /** null if unanswered */
  answer?: string
  answeredAt?: number
  answeredBy?: string
}

/** Progress Ledger — what has been done (execution state) */
export interface ProgressLedger {
  /** Completed tasks with outcomes */
  completed: LedgerTask[]
  /** Tasks currently being worked on */
  inProgress: LedgerTask[]
  /** Tasks that are blocked */
  blocked: LedgerTask[]
  /** Next tasks to pick up */
  nextUp: LedgerTask[]
  /** Last time the progress ledger was updated */
  lastUpdatedAt: number
}

/** A task entry in the Progress Ledger */
export interface LedgerTask {
  id: string
  description: string
  /** Which branch is working on this (null if unassigned) */
  assignedBranch?: string
  createdAt: number
  completedAt?: number
  /** Brief outcome description (set on completion) */
  outcome?: string
  /** Reason for blockage (set when blocked) */
  blockReason?: string
  /** Priority: higher = more important */
  priority: number
}

export interface CorpusProcessedState {
  cursors: Map<string, number>
  branchAssessments: Map<string, BranchAssessment>
  crossPatterns: CrossHelixPattern[]
  interventions: CorpusIntervention[]
  spawnDecisions: SpawnDecision[]
  sweepCount: number
  lastSweepAt: number
  annotationTimestamps: number[]
  /** Dual-ledger planning state (Magentic-One pattern) */
  taskLedger: TaskLedger
  progressLedger: ProgressLedger
}

/**
 * The Corpus's assessment of a single branch.
 * Updated each sweep as new annotations arrive.
 */
export interface BranchAssessment {
  helixId: string
  status: BranchHealthStatus
  rollingScore: number
  scoreTrajectory: number[]
  dominantPattern: WorkUnitAnnotation | 'none'
  filesModified: Set<string>
  decliningScoreStreak: number
  lastActivityAt: number
  autoSpawnTriggered?: boolean
  avgGoalAlignment: number
  avgNovelty: number
  avgProgress: number
  directiveHistory: DirectiveRecord[]
  escalationLevel: EscalationLevel
  ignoredDirectiveStreak: number
  lowProgressStreak: number
  budget?: BranchBudget
  discoveries: string[]
  contextInjectionsReceived: number
  researchDigestBuilt: boolean
}

/**
 * Branch health as assessed by the Corpus (distinct from CorpusBranchStatus).
 *
 * WHY: CorpusBranchStatus is lifecycle (active/completed/failed). BranchHealthStatus
 * is the Corpus's real-time assessment of how well the branch is doing.
 * 'struggling'/'stuck'/'drifting' trigger different intervention strategies.
 */
export type BranchHealthStatus =
  | 'productive'
  | 'active'
  | 'struggling'
  | 'stuck'
  | 'drifting'
  | 'completed'
  | 'failed'

/**
 * @dep callers: constructor (core/intelligence/constellation/corpus-mini-helix.ts), constructor (core/intelligence/constellation/corpus.ts), createState (tests/corpus-strategy.test.ts)
 * @dep calls: now
 * @dep module: Constellation
 * @dep risk: LOW | 3 callers, 0 flows, 1 module
 */

export function createInitialProcessedState(goal?: string): CorpusProcessedState {
  const now = Date.now()
  return {
    cursors: new Map(),
    branchAssessments: new Map(),
    crossPatterns: [],
    interventions: [],
    spawnDecisions: [],
    sweepCount: 0,
    lastSweepAt: 0,
    annotationTimestamps: [],
    taskLedger: {
      goal: goal || '',
      facts: [],
      guesses: [],
      openQuestions: [],
      lastUpdatedAt: now,
    },
    progressLedger: {
      completed: [],
      inProgress: [],
      blocked: [],
      nextUp: [],
      lastUpdatedAt: now,
    },
  }
}


// Cross-Helix Patterns — Only the Corpus can detect these

/**
 * Pattern types that emerge across multiple Helix branches.
 * Individual Brainstems can't see these — they require the Corpus's
 * cross-branch view.
 */
export type CrossHelixPatternType =
  | 'conflict'
  | 'redundancy'
  | 'divergence'
  | 'convergence'
  | 'asymmetric-progress'
  | 'cascade-failure'
  | 'resource-imbalance'

/**
 * A cross-Helix pattern detected by the Corpus.
 */
export interface CrossHelixPattern {
  type: CrossHelixPatternType
  helixIds: string[]
  severity: GuidanceUrgency
  description: string
  suggestedAction?: string
  detectedAt: number
  actedUpon: boolean
}


// Corpus Strategies — Workflow-dispatched coordination

/**
 * Context provided to a strategy when it builds its workflow.
 *
 * WHY: Strategies need access to the pattern that triggered them, the current
 * Corpus state (branch assessments, budgets, discoveries), and runtime
 * handles to send directives and spawn branches. Passing an explicit context
 * object keeps strategies decoupled from the Corpus class itself.
 */
export interface StrategyContext {
  /** The pattern that triggered this strategy. */
  pattern: CrossHelixPattern
  /** Current processed state (assessments, budgets, discoveries). */
  state: CorpusProcessedState
  /** The Corpus tree for branch/step inspection. */
  tree: ICorpusTree
  /** Parent Constellation session id for attribution. */
  constellationId: string
  /** Logger scoped to this strategy run. */
  logger: ILogger
}

/**
 * A registerable coordination strategy.
 *
 * WHY: The Corpus async loop detects cross-branch patterns (conflict,
 * asymmetric-progress, etc.) but today acts on them with inline imperative
 * code. CorpusStrategy extracts that logic into composable, testable
 * workflow definitions that the workflow engine executes.
 *
 * The strategy decides (a) whether it matches a pattern and (b) what
 * workflow to run in response. The Corpus dispatches the workflow and
 * tracks its lifecycle.
 */
export interface CorpusStrategy {
  /** Unique strategy identifier. */
  id: string
  /** Human-readable description. */
  description: string
  /** Which pattern types this strategy handles. */
  patternTypes: CrossHelixPatternType[]
  /**
   * Evaluate whether this strategy should activate for the given pattern.
   * Called only when patternTypes includes the pattern's type.
   * Return true to dispatch the strategy's workflow.
   */
  matches(pattern: CrossHelixPattern, state: CorpusProcessedState): boolean
  /**
   * Build the workflow definition for this specific activation.
   * The returned workflow is executed by the workflow engine.
   */
  createWorkflow(context: StrategyContext): WorkflowDefinition
  /** Priority when multiple strategies match (higher = preferred). Default: 0. */
  priority: number
}

/**
 * Tracks an active strategy workflow dispatched by the Corpus.
 */
export interface ActiveStrategyRun {
  /** Workflow run id from the engine. */
  runId: string
  /** Which strategy was dispatched. */
  strategyId: string
  /** The pattern that triggered the strategy. */
  pattern: CrossHelixPattern
  /** When the strategy was dispatched. */
  startedAt: number
  /** Populated when the run completes or fails. */
  result?: WorkflowRun
}


// Corpus Interventions — Brainstem-mediated steering

/**
 * A directive from the Corpus to a child Helix's Brainstem.
 *
 * The Brainstem receives this and converts it to a PendingGuidance,
 * delivering it to Unity through its normal escalation model
 * (low/medium → tool results, high/critical → user message).
 */
export interface CorpusDirective {
  targetHelixId: string
  type: CorpusDirectiveType
  urgency: GuidanceUrgency
  reason: string
  text: string
  fromPattern?: CrossHelixPatternType
  timestamp: number
  /** Enforcement: maximum iterations remaining before forced conclusion */
  maxIterationsRemaining?: number
  /** Enforcement: required behavioral action on next iteration */
  requiredAction?: 'narrow_scope' | 'switch_strategy' | 'conclude' | 'produce_output'
}

/**
 * Types of Corpus directives to child Brainstems.
 *
 * WHY: These are ordered by intrusiveness. 'guidance' is a suggestion.
 * 'redirect' changes approach. 'throttle' manages resources. 'cancel'
 * terminates the branch. 'context-inject' bypasses the guidance queue
 * for critical information.
 */
export type CorpusDirectiveType =
  | 'guidance'
  | 'redirect'
  | 'throttle'
  | 'priority-shift'
  | 'cancel'
  | 'context-inject'

/**
 * Tracks a single directive's lifecycle — from issuance through behavioral verification.
 * The Corpus watches 3 post-directive annotations to determine if behavior changed.
 */
export interface DirectiveRecord {
  directive: CorpusDirective
  sentAtStep: number
  scoreAtSend: { goalAlignment: number; novelty: number; progress: number }
  postDirectiveScores: Array<{ goalAlignment: number; novelty: number; progress: number; annotation: string }>
  outcome: 'pending' | 'effective' | 'ignored'
  evaluatedAt?: number
}

/**
 * Escalation level — determines the force of Corpus intervention.
 * Level progresses based on combined directive-failure + metric signals.
 *
 * HOW: Level 0 = no intervention. Level 4 = cancel the branch.
 * Each level adds more aggressive steering.
 */
export type EscalationLevel = 0 | 1 | 2 | 3 | 4

/**
 * Template-configurable escalation thresholds.
 * Different templates (research, implementation, etc.) tolerate different
 * amounts of low-progress work before escalating.
 */
export interface EscalationThresholds {
  directiveFailuresForEscalation: number
  lowScoreThreshold: number
  lowScoreStepsForEscalation: number
  minProgressThreshold: number
  lowProgressStepsForEscalation: number
}

/** Default escalation thresholds per template type */
export const ESCALATION_DEFAULTS: Record<string, EscalationThresholds> = {
  research: {
    directiveFailuresForEscalation: 4,
    lowScoreThreshold: 0.25,
    lowScoreStepsForEscalation: 12,
    minProgressThreshold: 0.1,
    lowProgressStepsForEscalation: 15,
  },
  implementation: {
    directiveFailuresForEscalation: 2,
    lowScoreThreshold: 0.3,
    lowScoreStepsForEscalation: 8,
    minProgressThreshold: 0.15,
    lowProgressStepsForEscalation: 10,
  },
  standard: {
    directiveFailuresForEscalation: 3,
    lowScoreThreshold: 0.3,
    lowScoreStepsForEscalation: 10,
    minProgressThreshold: 0.12,
    lowProgressStepsForEscalation: 12,
  },
  minimal: {
    directiveFailuresForEscalation: 2,
    lowScoreThreshold: 0.35,
    lowScoreStepsForEscalation: 6,
    minProgressThreshold: 0.2,
    lowProgressStepsForEscalation: 8,
  },
  review: {
    directiveFailuresForEscalation: 4,
    lowScoreThreshold: 0.25,
    lowScoreStepsForEscalation: 12,
    minProgressThreshold: 0.1,
    lowProgressStepsForEscalation: 15,
  },
}


// Spawn Decisions — LLM-evaluated spawn gating

/**
 * A spawn decision made by the Corpus.
 * Every spawn request is evaluated by the Corpus's own LLM,
 * considering current tree state, resource budget, and existing work.
 */
export interface SpawnDecision {
  requestId: string
  requestingHelixId: string
  goal: string
  approved: boolean
  reason: string
  suggestedTemplate?: ConstellationTemplate
  suggestedGoal?: string
  evaluatedAt: number
}


// Corpus Configuration

export interface CorpusProactiveConfig {
  enableReDecomposition: boolean
  enableQualityGates: boolean
  enableDiscoveryRouting: boolean
  enableParallelAcceleration: boolean
  enableContextInjection: boolean
  enableResearchCaching: boolean
  enableDirectInjection: boolean
  parallelSplitMinStreak: number
  parallelSplitMinScore: number
  contextInjectionAfterSteps: number
}

/** Default proactive config */
export const DEFAULT_PROACTIVE_CONFIG: CorpusProactiveConfig = {
  enableReDecomposition: true,
  enableQualityGates: true,
  enableDiscoveryRouting: true,
  enableParallelAcceleration: true,
  enableContextInjection: true,
  enableResearchCaching: true,
  enableDirectInjection: true,
  parallelSplitMinStreak: 3,
  parallelSplitMinScore: 0.65,
  contextInjectionAfterSteps: 5,
}


/**
 * Adaptive cadence configuration for dynamic poll interval adjustment.
 * Corpus adjusts its poll interval based on:
 * - Number of active branches
 * - Rate of new annotations
 * - Escalation queue length
 * - LLM health (consecutive failures)
 */
export interface AdaptiveCadenceConfig {
  basePollMs: number
  minPollMs: number
  maxPollMs: number
  branchThreshold: number
  annotationRateThreshold: number
  escalationThreshold: number
  failureThreshold: number
}

export const DEFAULT_ADAPTIVE_CADENCE_CONFIG: AdaptiveCadenceConfig = {
  basePollMs: 10_000,
  minPollMs: 2_000,
  maxPollMs: 30_000,
  branchThreshold: 4,
  annotationRateThreshold: 0.5,
  escalationThreshold: 3,
  failureThreshold: 2,
}

/**
 * Corpus configuration.
 *
 * WHY: The cadence field controls whether the Corpus runs proactively ('active')
 * or reactively ('safety-net'). In safety-net mode, the Brainstem's self-organization
 * handles routine coordination; the Corpus only intervenes for pathological patterns.
 */
export interface CorpusConfig {
  modelTier: string
  maxTokens: number
  timeoutMs: number
  idlePollMs: number
  llmAnalysisThreshold: number
  maxBranches: number
  maxDepth: number
  interventionCooldownSweeps: number
  strugglingScoreThreshold: number
  decliningScoreThreshold: number
  postToBlackboard: boolean
  enabled: boolean
  autoSpawnInterventionThreshold: number
  cadence: CorpusCadence
  safetyNetMinSweepsBetweenAnalysis: number
  useToolBasedAnalysis: boolean
  maxToolCallsPerCycle: number
  proactive: CorpusProactiveConfig
  adaptiveCadence: AdaptiveCadenceConfig
}

/**
 * Corpus operating cadence.
 *
 * WHY: 'active' is the legacy proactive mode. 'safety-net' delegates routine
 * coordination to Brainstem self-organization, reserving Corpus LLM analysis
 * for pathological patterns and escalations.
 */
export type CorpusCadence = 'active' | 'safety-net'

export const DEFAULT_CORPUS_CONFIG: CorpusConfig = {
  modelTier: 'sonnet',
  maxTokens: 16_000,
  timeoutMs: 90_000,
  idlePollMs: 10_000,
  llmAnalysisThreshold: 2,
  maxBranches: 16,
  maxDepth: 4,
  interventionCooldownSweeps: 3,
  strugglingScoreThreshold: 0.4,
  decliningScoreThreshold: 3,
  postToBlackboard: true,
  enabled: true,
  autoSpawnInterventionThreshold: 5,
  cadence: 'active',
  safetyNetMinSweepsBetweenAnalysis: 3,
  useToolBasedAnalysis: true,
  maxToolCallsPerCycle: 10,
  proactive: DEFAULT_PROACTIVE_CONFIG,
  adaptiveCadence: DEFAULT_ADAPTIVE_CADENCE_CONFIG,
}


/** Minimal LLM interface for Corpus (same shape as BrainstemLLM) */
export interface CorpusLLM {
  complete(opts: {
    prompt: string
    modelTier: string
    maxTokens: number
    timeoutMs: number
  }): Promise<{ content: string; truncated: boolean }>
}

export interface CorpusDeps {
  llm: CorpusLLM
  logger: ILogger
  goal: string
  constellationId: string
  eventBus?: IEventBus
  blackboard?: CorpusBlackboard
  onSpawnRequest?: (request: { goal: string; context?: string; template?: string; requestingHelixId: string }) => void
  crossHelixDialectic?: import('./cross-helix-dialectic.js').CrossHelixDialectic
  readFile?: (path: string) => Promise<string | null>
  launchHelix?: (goal: string, context: string | undefined, template: ConstellationTemplate | undefined) => Promise<string>
  pauseHelix?: (helixId: string) => boolean
  resumeHelix?: (helixId: string) => void
  killHelix?: (helixId: string) => void
  injectGuidance?: (helixId: string, content: string, urgency: import('../helix/brainstem-types.js').GuidanceUrgency) => void
  runCommand?: (command: string, timeoutMs?: number) => Promise<{ exitCode: number; stdout: string; stderr: string }>
  /** Meditation mode — Corpus observes silently as Cassi, never sends directives */
  meditationMode?: boolean
  /** Meditation style — controls tool set and Corpus prompt tone */
  meditationStyle?: 'passive' | 'active' | 'focused'
  /** MnemicField for meditation Corpus tools */
  mnemicField?: import('../mnemic-field/index.js').MnemicField
  /** Memory system for meditation insight storage */
  memory?: import('../../../types/intelligence.js').IMemory
  getHelixTemplate?: (helixId: string) => ConstellationTemplate | undefined
  persistEvent?: (type: string, entity: string | null, message: string, data?: unknown) => void
  store?: import('./constellation-store.js').ConstellationStore
  decompositionTracker?: import('./decomposition-tracker.js').DecompositionTracker
  topology?: import('./topology/topology-graph.js').TopologyGraph
  /** When true, the CorpusMiniHelix handles strategic LLM analysis — skip internal LLM calls */
  miniHelixActive?: boolean
}

/**
 * Minimal blackboard interface for Corpus posting.
 * Same shape as BrainstemBlackboard — any compatible object satisfies this.
 */
export interface CorpusBlackboard {
  post(
    channel: 'findings' | 'concerns' | 'decisions' | 'bugs',
    entry: {
      author: string
      content: string
      structured?: Record<string, unknown>
      priority?: number
      tags?: string[]
    },
  ): unknown
}


// Corpus Result — Included in ConstellationResult

/**
 * The Corpus's final result, summarizing its reasoning across all branches.
 */
export interface CorpusResult {
  tree: CorpusTreeSnapshot
  branchAssessments: Array<{
    helixId: string
    status: BranchHealthStatus
    rollingScore: number
    dominantPattern: string
    avgGoalAlignment?: number
    avgNovelty?: number
    avgProgress?: number
    escalationLevel?: EscalationLevel
    ignoredDirectiveStreak?: number
    budgetConsumedSteps?: number
    budgetMaxSteps?: number
  }>
  crossPatterns: CrossHelixPattern[]
  interventions: CorpusIntervention[]
  spawnDecisions: SpawnDecision[]
  reDecompositions: ReDecompositionRequest[]
  qualityGateResults: Array<{ helixId: string; result: QualityGateResult }>
  discoveryCount: number
  directInjections: DirectInjection[]
  researchDigests: ResearchDigest[]
  parallelSplits: ParallelSplitRequest[]
  contextInjections: ContextInjection[]
  sweepCount: number
  llmHealthy: boolean
  llmFailureCount: number
  durationMs: number
  /** Dual-ledger final state (post-mortem analysis) */
  taskLedger?: TaskLedger
  progressLedger?: ProgressLedger
  /** Locus (Global Workspace) snapshot — attention layer state */
  locusSnapshot?: import('./locus/locus-types.js').LocusSnapshot
}

/**
 * Record of an intervention the Corpus made.
 * Extends CorpusDirective with outcome tracking.
 */
export interface CorpusIntervention extends CorpusDirective {
  acknowledged: boolean
  sweepNumber: number
}


// Goal Decomposition — Pre-flight planning via a planning Helix

/**
 * Result of Corpus goal decomposition.
 * Produced by a short-lived planning Helix that analyzes the goal
 * and breaks it into concrete sub-tasks.
 */
export interface GoalDecomposition {
  decomposed: boolean
  originalGoal: string
  subTasks: GoalSubTask[]
  strategy: 'sequential' | 'parallel' | 'tree'
  sharedContext?: string
  durationMs: number
}

/**
 * A single sub-task from goal decomposition.
 */
export interface GoalSubTask {
  goal: string
  context?: string
  template?: ConstellationTemplate
  priority: number
  relevantFiles?: string[]
  budgetSteps?: number
}


// Branch Budgets — Step + time constraints per branch

/**
 * Budget allocated to a branch. Corpus tracks consumption and escalates
 * when budget is consumed without proportional output.
 */
export interface BranchBudget {
  maxSteps: number
  maxTimeMs: number
  consumedSteps: number
  consumedTimeMs: number
  startedAt: number
  source: 'decomposer' | 'template'
}

/** Default budgets per template type */
export const BRANCH_BUDGET_DEFAULTS: Record<string, { maxSteps: number; maxTimeMs: number }> = {
  research:       { maxSteps: 25, maxTimeMs: 10 * 60_000 },
  implementation: { maxSteps: 40, maxTimeMs: 15 * 60_000 },
  standard:       { maxSteps: 30, maxTimeMs: 12 * 60_000 },
  minimal:        { maxSteps: 15, maxTimeMs: 5 * 60_000 },
  review:         { maxSteps: 20, maxTimeMs: 8 * 60_000 },
}


// Quality Gates — Verify branch output before accepting completion

/** Result of running quality gates on a completed branch */
export interface QualityGateResult {
  passed: boolean
  gates: QualityGateCheck[]
  durationMs: number
}

export interface QualityGateCheck {
  name: 'files_exist' | 'type_check' | 'tests' | 'placeholder_scan'
  passed: boolean
  details: string
  failedFiles?: string[]
}


// Re-decomposition — Mid-flight branch splitting

/** Request from Corpus LLM to re-decompose a branch mid-flight */
export interface ReDecompositionRequest {
  sourceHelixId: string
  reason: string
  newSubTasks: GoalSubTask[]
  killSource: boolean
  narrowedGoal?: string
}


// Discovery Routing — Cross-branch knowledge sharing

/** A discovery made by a branch that may be useful to others */
export interface DiscoveryEntry {
  id: string
  sourceHelixId: string
  content: string
  type: 'architecture' | 'file_location' | 'pattern' | 'constraint' | 'decision'
  relatedFiles: string[]
  timestamp: number
  deliveredTo: Set<string>
}


// Direct Injection — Pause-inject-resume for critical interventions

/** A direct injection bypassing the Brainstem guidance queue */
export interface DirectInjection {
  targetHelixId: string
  message: string
  urgency: 'critical' | 'high' | 'normal'
  paused: boolean
  timestamp: number
  pauseDurationMs?: number
}


// Research Digest — Cached findings from completed research branches

/** Full digest of a completed research branch's findings */
export interface ResearchDigest {
  sourceHelixId: string
  goal: string
  annotations: Array<{
    step: number
    type: string
    summary: string
    scores: { goalAlignment: number; novelty: number; progress: number }
  }>
  discoveries: string[]
  filesExplored: string[]
  filesModified: string[]
  architectureNotes: string[]
  conclusion: string
  createdAt: number
}


// Parallel Split — Score-triggered branch acceleration

/** Request to split a productive branch into parallel sub-branches */
export interface ParallelSplitRequest {
  sourceHelixId: string
  reason: string
  newSubTasks: GoalSubTask[]
  continuedGoal: string
}


// Strategic Context Injection — Help struggling branches find their way

/** Context injection from Corpus to a struggling branch */
export interface ContextInjection {
  targetHelixId: string
  source: 'code_intelligence' | 'file_read' | 'research_digest' | 'cross_branch'
  content: string
  reason: string
  tokenEstimate: number
  timestamp: number
}


// External Corpus Protocol — Allow external agents to assume Corpus role

/**
 * State tracking for an external agent that has assumed the Corpus role.
 * When an external agent assumes Corpus, the internal LLM loop pauses
 * and all Corpus decisions are routed through MCP tool calls from the
 * external agent instead.
 *
 * WHY: This enables any MCP-connected agent (including humans via TUI,
 * external orchestrators, or more powerful models) to act as the strategic
 * overseer of a Constellation, using CassiCore's infrastructure while
 * providing their own decision-making.
 */
export interface ExternalCorpusState {
  /** Whether an external agent currently holds the Corpus role */
  assumed: boolean
  /** Identifier of the external agent holding the lock */
  agentId: string | null
  /** When the assumption was granted */
  assumedAt: number | null
  /** Last action timestamp — used for heartbeat timeout */
  lastActionAt: number | null
  /** Maximum inactivity before auto-release (ms) */
  heartbeatTimeoutMs: number
  /** Spawn requests queued for external decision */
  pendingSpawnRequests: PendingExternalSpawnRequest[]
}

/**
 * A spawn request queued for external Corpus decision.
 * When the internal Corpus is suspended, spawn requests accumulate here
 * instead of being auto-evaluated by the LLM.
 */
export interface PendingExternalSpawnRequest {
  requestId: string
  requestingHelixId: string
  goal: string
  context?: string
  template?: string
  targetDepth: number
  queuedAt: number
}

/**
 * Full state snapshot for an external Corpus agent.
 * Combines tree state, branch assessments, patterns, and pending decisions
 * into a single response.
 */
export interface ExternalCorpusSnapshot {
  tree: CorpusTreeSnapshot
  branchAssessments: Array<{
    helixId: string
    status: BranchHealthStatus
    rollingScore: number
    dominantPattern: string
    avgGoalAlignment?: number
    avgNovelty?: number
    avgProgress?: number
    escalationLevel?: EscalationLevel
    ignoredDirectiveStreak?: number
    budgetConsumedSteps?: number
    budgetMaxSteps?: number
  }>
  crossPatterns: CrossHelixPattern[]
  pendingSpawnRequests: PendingExternalSpawnRequest[]
  recentInterventions: CorpusIntervention[]
  sweepCount: number
  goal: string
  /** Dual-ledger planning state — visible to external orchestrators */
  taskLedger?: TaskLedger
  progressLedger?: ProgressLedger
  /** Locus (Global Workspace) snapshot — attention and memory state */
  locusSnapshot?: import('./locus/locus-types.js').LocusSnapshot
}

/** Default heartbeat timeout: 5 minutes of inactivity triggers auto-release */
export const DEFAULT_EXTERNAL_CORPUS_HEARTBEAT_MS = 300_000

/**
 * @dep callers: release (core/intelligence/constellation/corpus.ts), constructor (core/intelligence/constellation/corpus.ts)
 * @dep module: Constellation
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function createInitialExternalCorpusState(): ExternalCorpusState {
  return {
    assumed: false,
    agentId: null,
    assumedAt: null,
    lastActionAt: null,
    heartbeatTimeoutMs: DEFAULT_EXTERNAL_CORPUS_HEARTBEAT_MS,
    pendingSpawnRequests: [],
  }
}


// Memory Injection Types — Branch-level Memory Continuity

/**
 * Memory context injected into a Helix branch at startup.
 * Provides past-run continuity for new branches.
 */
export interface BranchMemoryContext {
  helixId?: string
  goal?: string
  searchQuery?: string
  memories: InjectedMemory[]
  totalFound?: number
  totalAvailable?: number
  injectedAt: number
}

/**
 * A single memory entry injected into a branch.
 */
export interface InjectedMemory {
  content: string
  relevance: number
  type: string
  createdAt: number
  tags?: string[]
  pinned?: boolean
  importance?: number
}
