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


// ═══════════════════════════════════════════════════════════════════
// Corpus Tree — The shared reasoning structure
// ═══════════════════════════════════════════════════════════════════

/**
 * A single step in a Corpus branch.
 * Each step is one BrainstemAnnotation pushed by a child Helix's Brainstem.
 */
export interface CorpusStep {
  /** The annotation from the child Brainstem */
  annotation: BrainstemAnnotation
  /** When this step was pushed to the tree */
  pushedAt: number
  /** Tool calls from the work unit (name + truncated args) — for Corpus observability */
  toolCalls?: Array<{ name: string; args: string }>
}

/**
 * A branch in the Corpus tree — one per Helix in the Constellation.
 * Brainstems push annotations into their branch as they score work units.
 */
export interface CorpusBranch {
  /** The Helix this branch tracks */
  helixId: string
  /** What this Helix is working on */
  goal: string
  /** Depth in the Constellation tree (root = 0) */
  depth: number
  /** Parent Helix ID (undefined for root) */
  parentId?: string
  /** Annotation steps pushed by the Helix's Brainstem */
  steps: CorpusStep[]
  /** Branch lifecycle status */
  status: CorpusBranchStatus
  /** When this branch was registered */
  createdAt: number
  /** When this branch was closed (completed/cancelled/failed) */
  closedAt?: number
}

/** Branch lifecycle status */
export type CorpusBranchStatus =
  | 'active'      // Helix is running, Brainstem is pushing annotations
  | 'completed'   // Helix finished successfully
  | 'cancelled'   // Helix was cancelled (by Corpus or externally)
  | 'failed'      // Helix failed

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

  // ── Shared Thought Tree extensions ────────────────────────────────

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
}


// ── Tree Snapshot (for Cassi / progress reporting) ────────────────

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
  /** Branch digest if available (Shared Thought Tree) */
  digest?: BranchDigest
}


// ═══════════════════════════════════════════════════════════════════
// Shared Thought Tree — Self-Organizing Constellation
// ═══════════════════════════════════════════════════════════════════

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
  /** Which Helix produced this digest */
  helixId: string
  /** Full goal for this branch */
  goalSummary: string
  /** Current approach pattern */
  approach: BranchApproach
  /** Estimated progress (0-1) based on score trajectory and pattern shifts */
  progress: number
  /** Files being actively modified (from recent annotations) */
  filesActive: string[]
  /** Top findings from high-score annotations (score > 0.7) */
  keyFindings: string[]
  /** Blockers — from annotations with pattern 'stuck'/'paralysis' or low scores */
  blockers: string[]
  /** Strategy description — what the Helix is currently trying to do */
  currentStrategy: string
  /** Rolling quality score */
  rollingScore: number
  /** Total work units processed */
  workUnitsProcessed: number
  /** When this digest was last updated */
  updatedAt: number
  /** Why the approach last changed (if it did) — feeds self-awareness */
  lastApproachChangeReason?: string

  // ─── Cognitive Model Fields ────────────────────────────────────────
  /** Current working hypothesis about how to achieve the goal */
  currentHypothesis?: string
  /** All discoveries accumulated across all steps */
  allDiscoveries?: string[]
  /** All decisions made so far */
  allDecisions?: string[]
  /** Planned next steps from the most recent annotation */
  currentNextSteps?: string[]
  /** Recent concrete outputs (files created, tests run, etc.) */
  recentOutputs?: string[]
  /**
   * Live stream snippet — the most recent partial LLM output being generated
   * in the current active iteration. Updated on every stream event (not just
   * work units), so the Corpus always sees what this thread is currently writing.
   * Absent if the thread is idle or between iterations.
   */
  liveStreamSnippet?: string
}

/**
 * Approach patterns for a Helix branch.
 * Extends WorkUnitAnnotation with higher-level strategic patterns.
 */
export type BranchApproach =
  | 'exploration'      // reading, searching, gathering context
  | 'research'         // deep investigation, cross-referencing, hypothesis testing
  | 'implementation'   // writing code, creating files
  | 'testing'          // running tests, verification
  | 'debugging'        // fixing failures, tracing errors
  | 'revision'         // iterating based on feedback
  | 'coordinating'     // adjusting based on peer state (self-organization active)

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
  /** Auto-generated topic ID */
  id: string
  /** Human-readable topic name (e.g. "authentication middleware") */
  name: string
  /** Contributions from multiple Helixes */
  contributions: TopicContribution[]
  /** Whether contributions contain conflicting approaches */
  tensionFlag: boolean
  /** Description of the tension (if any) */
  tensionDescription?: string
  /** Files most relevant to this topic */
  relatedFiles: string[]
  /** When this topic was first created */
  createdAt: number
  /** Which Helix created it */
  createdBy: string
  /** When any Helix last contributed */
  lastContributionAt: number
}

/**
 * A single contribution to a shared topic node.
 */
export interface TopicContribution {
  /** Which Helix contributed this */
  helixId: string
  /** The actual insight, finding, or observation */
  content: string
  /** Approach the contributing Helix was using */
  approach: BranchApproach
  /** Files related to this contribution */
  files: string[]
  /** Quality score of the work unit that produced this insight */
  score: number
  /** When this was contributed */
  timestamp: number
}


// ═══════════════════════════════════════════════════════════════════
// Self-Awareness — Retrospectives, Effectiveness, Pattern Library
// ═══════════════════════════════════════════════════════════════════

/**
 * Strategy Retrospective — recorded when a Brainstem changes its approach.
 * Answers "why did I change?" — builds a log of what worked and what didn't,
 * enabling self-improvement across the constellation.
 */
export interface StrategyRetrospective {
  /** Which Helix recorded this */
  helixId: string
  /** Previous approach */
  fromApproach: BranchApproach
  /** New approach */
  toApproach: BranchApproach
  /** Why the change was made */
  reason: string
  /** What triggered the change (self-org rule, corpus directive, score decline, etc.) */
  trigger: RetrospectiveTrigger
  /** Quality score at the time of change */
  scoreAtChange: number
  /** Quality score N steps after change (filled in later for effectiveness tracking) */
  scoreAfterChange?: number
  /** Number of steps after which scoreAfterChange was measured */
  stepsAfterMeasured?: number
  /** Whether this change improved things (filled in by effectiveness tracking) */
  wasEffective?: boolean
  /** When this retrospective was recorded */
  timestamp: number
}

/** What triggered a strategy change */
export type RetrospectiveTrigger =
  | 'self-organization'  // peer state in the tree caused a redirect
  | 'corpus-directive'   // the Corpus sent a directive
  | 'score-decline'      // quality scores dropped
  | 'pattern-detected'   // a pathological pattern was detected locally
  | 'topic-tension'      // a shared topic showed conflicting approaches
  | 'peer-convergence'   // multiple peers converged on a different approach
  | 'goal-refinement'    // narrowed focus to avoid overlap with a peer
  | 'manual'             // explicit user or external steering

/**
 * Elevated Pattern — a successful strategy that a completed branch
 * demonstrated. Elevated to constellation-level knowledge so other
 * branches (current and future) can learn from it.
 *
 * The pattern library is the constellation's long-term memory.
 */
export interface ElevatedPattern {
  /** Auto-generated pattern ID */
  id: string
  /** Which Helix demonstrated this pattern */
  sourceHelixId: string
  /** What approach worked */
  approach: BranchApproach
  /** Description of the successful strategy */
  description: string
  /** What goal/context this pattern applies to */
  applicableContext: string
  /** Quality score the source branch achieved */
  achievedScore: number
  /** Files/modules this pattern is relevant to */
  relevantFiles: string[]
  /** Retrospectives that support this pattern (evidence chain) */
  supportingRetrospectives: string[]
  /** When this pattern was elevated */
  elevatedAt: number
  /** How many branches have referenced this pattern */
  referenceCount: number
}

/**
 * Self-organization adjustment — produced by a Brainstem's selfOrganize()
 * method after reading the shared tree. Feeds into the guidance queue.
 */
export interface SelfOrgAdjustment {
  /** What kind of adjustment */
  type: SelfOrgAdjustmentType
  /** Human-readable description */
  description: string
  /** Evidence from the tree that triggered this */
  evidence: string
  /** Source: which peer digest or topic triggered this */
  sourceHelixId?: string
  sourceTopicId?: string
  /** Dampening counter — must reach threshold before taking effect */
  dampeningCount: number
  /** The threshold needed before this adjustment activates */
  dampeningThreshold: number
  /** When this was first generated */
  firstGeneratedAt: number
  /** When this was last confirmed (dampening tick) */
  lastConfirmedAt: number
}

/** Types of self-organization adjustments */
export type SelfOrgAdjustmentType =
  | 'file-avoidance'       // back off files a peer is editing
  | 'finding-incorporation' // pull a peer's finding into local context
  | 'approach-redirect'    // change approach based on peer success
  | 'goal-refinement'      // narrow focus to reduce overlap with peer
  | 'tension-flag'         // flag conflicting approach for resolution
  | 'pattern-adoption'     // adopt an elevated pattern from the library
  | 'peer-assist'          // offer findings to a struggling peer via topic

/**
 * Effectiveness tracking entry — links a self-org adjustment to its
 * measured outcome. This is how the constellation learns what works.
 */
export interface EffectivenessRecord {
  /** Which adjustment was applied */
  adjustmentType: SelfOrgAdjustmentType
  /** Which Helix applied it */
  helixId: string
  /** Score before the adjustment */
  scoreBefore: number
  /** Score after the adjustment (measured N steps later) */
  scoreAfter: number
  /** Steps between measurement points */
  stepsDelta: number
  /** Net score change */
  improvement: number
  /** Was this considered effective? (improvement > 0) */
  effective: boolean
  /** When measured */
  measuredAt: number
}


// ═══════════════════════════════════════════════════════════════════
// Extended Tree Snapshot — includes shared thought tree state
// ═══════════════════════════════════════════════════════════════════

export interface CorpusTreeSnapshot {
  branches: CorpusBranchSnapshot[]
  totalSteps: number
  activeBranches: number
  snapshotAt: number
  /** All branch digests (Shared Thought Tree) */
  digests: BranchDigest[]
  /** All shared topic nodes */
  topics: TopicNode[]
  /** Strategy retrospectives across the constellation */
  retrospectives: StrategyRetrospective[]
  /** Elevated patterns (constellation knowledge) */
  elevatedPatterns: ElevatedPattern[]
  /** Effectiveness records for self-organization tracking */
  effectivenessRecords: EffectivenessRecord[]
}
// ═══════════════════════════════════════════════════════════════════

/**
 * The Corpus's internal processed state.
 * Built by analyzing the shared tree. Brainstem pushes are treated as raw
 * input that the Corpus organizes into its own strategic understanding.
 */
export interface CorpusProcessedState {
  /** Per-branch cursor — the last step index the Corpus has analyzed */
  cursors: Map<string, number>

  /** Corpus's assessment of each branch */
  branchAssessments: Map<string, BranchAssessment>

  /** Cross-branch patterns detected */
  crossPatterns: CrossHelixPattern[]

  /** Interventions sent to child Brainstems */
  interventions: CorpusIntervention[]

  /** Spawn decisions made */
  spawnDecisions: SpawnDecision[]

  /** How many sweep cycles the Corpus has completed */
  sweepCount: number

  /** Last time the Corpus completed a sweep */
  lastSweepAt: number
}

/**
 * The Corpus's assessment of a single branch.
 * Updated each sweep as new annotations arrive.
 */
export interface BranchAssessment {
  /** Which Helix this assesses */
  helixId: string

  /** Corpus's view of this branch's health */
  status: BranchHealthStatus

  /** Rolling average of recent composite scores (last 5 annotations) */
  rollingScore: number

  /** Full score trajectory for trend analysis */
  scoreTrajectory: number[]

  /** Most frequent annotation type in recent steps */
  dominantPattern: WorkUnitAnnotation | 'none'

  /** File paths this Helix has modified (extracted from tool calls, for conflict detection) */
  filesModified: Set<string>

  /** Consecutive steps with declining scores */
  decliningScoreStreak: number

  /** When this branch last had activity */
  lastActivityAt: number

  /** Whether an auto-spawn has already been triggered for this branch */
  autoSpawnTriggered?: boolean

  // ─── Dimensional Score Averages (rolling last 5) ───────────────
  /** Rolling average goal alignment */
  avgGoalAlignment: number
  /** Rolling average novelty */
  avgNovelty: number
  /** Rolling average progress */
  avgProgress: number

  // ─── Directive Tracking ────────────────────────────────────────
  /** History of directives sent to this branch */
  directiveHistory: DirectiveRecord[]
  /** Current escalation level for this branch */
  escalationLevel: EscalationLevel
  /** Count of consecutive ignored directives */
  ignoredDirectiveStreak: number
  /** Steps with below-threshold progress (for metric-only escalation) */
  lowProgressStreak: number

  // ─── Branch Budget ─────────────────────────────────────────────
  /** Budget allocated to this branch */
  budget?: BranchBudget

  // ─── Discovery & Context ──────────────────────────────────────
  /** Discoveries this branch has made (extracted from annotations) */
  discoveries: string[]
  /** Context injections this branch has received */
  contextInjectionsReceived: number
  /** Whether this branch's research digest has been built */
  researchDigestBuilt: boolean
}

/** Branch health as assessed by the Corpus (distinct from CorpusBranchStatus) */
export type BranchHealthStatus =
  | 'productive'   // Healthy progress, good scores
  | 'active'       // Running but not yet assessed
  | 'struggling'   // Scores declining or patterns detected
  | 'stuck'        // No progress for extended period
  | 'drifting'     // Off-goal based on annotation patterns
  | 'completed'    // Branch closed successfully
  | 'failed'       // Branch closed with failure

/**
 * @dep callers: constructor (core/intelligence/constellation/corpus.ts), constructor (core/intelligence/constellation/corpus-mini-helix.ts)
 * @dep module: Unknown
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function createInitialProcessedState(): CorpusProcessedState {
  return {
    cursors: new Map(),
    branchAssessments: new Map(),
    crossPatterns: [],
    interventions: [],
    spawnDecisions: [],
    sweepCount: 0,
    lastSweepAt: 0,
  }
}


// ═══════════════════════════════════════════════════════════════════
// Cross-Helix Patterns — Only the Corpus can detect these
// ═══════════════════════════════════════════════════════════════════

/**
 * Pattern types that emerge across multiple Helix branches.
 * Individual Brainstems can't see these — they require the Corpus's
 * cross-branch view.
 */
export type CrossHelixPatternType =
  | 'conflict'              // Two Helixes modifying the same files
  | 'redundancy'            // Two Helixes doing similar work (similar annotations)
  | 'divergence'            // Helixes drifting in different directions from the goal
  | 'convergence'           // Multiple Helixes converging on the same conclusion
  | 'asymmetric-progress'   // One Helix stuck while siblings are productive
  | 'cascade-failure'       // Multiple Helixes failing in sequence
  | 'resource-imbalance'    // One Helix consuming disproportionate steps/time

/**
 * A cross-Helix pattern detected by the Corpus.
 */
export interface CrossHelixPattern {
  /** What kind of cross-Helix pattern */
  type: CrossHelixPatternType
  /** Which Helixes are involved */
  helixIds: string[]
  /** How urgent is this */
  severity: GuidanceUrgency
  /** Human-readable description */
  description: string
  /** Suggested action (from algorithmic detection or LLM) */
  suggestedAction?: string
  /** When this pattern was first detected */
  detectedAt: number
  /** Whether the Corpus has already acted on this pattern */
  actedUpon: boolean
}


// ═══════════════════════════════════════════════════════════════════
// Corpus Interventions — Brainstem-mediated steering
// ═══════════════════════════════════════════════════════════════════

/**
 * A directive from the Corpus to a child Helix's Brainstem.
 *
 * The Brainstem receives this and converts it to a PendingGuidance,
 * delivering it to Unity through its normal escalation model
 * (low/medium → tool results, high/critical → user message).
 */
export interface CorpusDirective {
  /** Which Helix to steer */
  targetHelixId: string
  /** What kind of intervention */
  type: CorpusDirectiveType
  /** How urgent */
  urgency: GuidanceUrgency
  /** Why the Corpus is intervening */
  reason: string
  /** The guidance content to deliver */
  text: string
  /** Which cross-Helix pattern triggered this (if any) */
  fromPattern?: CrossHelixPatternType
  /** When this directive was issued */
  timestamp: number
}

/** Types of Corpus directives to child Brainstems */
export type CorpusDirectiveType =
  | 'guidance'        // Strategic suggestion
  | 'redirect'        // Change approach or focus
  | 'throttle'        // Slow down (resource management)
  | 'priority-shift'  // Change priority relative to siblings
  | 'cancel'          // Stop this Helix
  | 'context-inject'  // Inject file content into posture context (text = filePath)

/**
 * Tracks a single directive's lifecycle — from issuance through behavioral verification.
 * The Corpus watches 3 post-directive annotations to determine if behavior changed.
 */
export interface DirectiveRecord {
  /** The directive that was sent */
  directive: CorpusDirective
  /** Annotation step at which the directive was sent */
  sentAtStep: number
  /** The dimensional scores at the time the directive was sent */
  scoreAtSend: { goalAlignment: number; novelty: number; progress: number }
  /** Post-directive annotation snapshots (up to 3) for behavioral change detection */
  postDirectiveScores: Array<{ goalAlignment: number; novelty: number; progress: number; annotation: string }>
  /** Whether the directive produced a behavioral change */
  outcome: 'pending' | 'effective' | 'ignored'
  /** When the outcome was determined */
  evaluatedAt?: number
}

/**
 * Escalation level — determines the force of Corpus intervention.
 * Level progresses based on combined directive-failure + metric signals.
 */
export type EscalationLevel = 0 | 1 | 2 | 3 | 4

/**
 * Template-configurable escalation thresholds.
 * Different templates (research, implementation, etc.) tolerate different
 * amounts of low-progress work before escalating.
 */
export interface EscalationThresholds {
  /** Ignored directives before escalating to next level */
  directiveFailuresForEscalation: number
  /** Composite score below which a branch is 'concerning' */
  lowScoreThreshold: number
  /** Steps with below-threshold scores before escalating (metric-only) */
  lowScoreStepsForEscalation: number
  /** Minimum progress dimension score — below this for N steps triggers concern */
  minProgressThreshold: number
  /** Steps with below-threshold progress before escalating */
  lowProgressStepsForEscalation: number
}

/** Default escalation thresholds per template type */
export const ESCALATION_DEFAULTS: Record<string, EscalationThresholds> = {
  /** Research: very tolerant of reading without writing */
  research: {
    directiveFailuresForEscalation: 4,
    lowScoreThreshold: 0.25,
    lowScoreStepsForEscalation: 12,
    minProgressThreshold: 0.1,
    lowProgressStepsForEscalation: 15,
  },
  /** Implementation: expects output sooner */
  implementation: {
    directiveFailuresForEscalation: 2,
    lowScoreThreshold: 0.3,
    lowScoreStepsForEscalation: 8,
    minProgressThreshold: 0.15,
    lowProgressStepsForEscalation: 10,
  },
  /** Standard: balanced defaults */
  standard: {
    directiveFailuresForEscalation: 3,
    lowScoreThreshold: 0.3,
    lowScoreStepsForEscalation: 10,
    minProgressThreshold: 0.12,
    lowProgressStepsForEscalation: 12,
  },
  /** Minimal: tight expectations */
  minimal: {
    directiveFailuresForEscalation: 2,
    lowScoreThreshold: 0.35,
    lowScoreStepsForEscalation: 6,
    minProgressThreshold: 0.2,
    lowProgressStepsForEscalation: 8,
  },
  /** Review: tolerant — reviews involve lots of reading */
  review: {
    directiveFailuresForEscalation: 4,
    lowScoreThreshold: 0.25,
    lowScoreStepsForEscalation: 12,
    minProgressThreshold: 0.1,
    lowProgressStepsForEscalation: 15,
  },
}


// ═══════════════════════════════════════════════════════════════════
// Spawn Decisions — LLM-evaluated spawn gating
// ═══════════════════════════════════════════════════════════════════

/**
 * A spawn decision made by the Corpus.
 * Every spawn request is evaluated by the Corpus's own LLM,
 * considering current tree state, resource budget, and existing work.
 */
export interface SpawnDecision {
  /** ID of the spawn request being evaluated */
  requestId: string
  /** Which Helix requested the spawn */
  requestingHelixId: string
  /** What the child would work on */
  goal: string
  /** Was it approved? */
  approved: boolean
  /** LLM's reasoning for the decision */
  reason: string
  /** Corpus may suggest a different template */
  suggestedTemplate?: ConstellationTemplate
  /** Corpus may refine the goal */
  suggestedGoal?: string
  /** When the decision was made */
  evaluatedAt: number
}


// ═══════════════════════════════════════════════════════════════════
// Corpus Configuration
// ═══════════════════════════════════════════════════════════════════

// ═══════════════════════════════════════════════════════════════════
// Corpus Proactive Capabilities — Config for new behaviors
// ═══════════════════════════════════════════════════════════════════

/** Extended Corpus config for proactive behaviors */
export interface CorpusProactiveConfig {
  /** Enable mid-flight re-decomposition */
  enableReDecomposition: boolean
  /** Enable quality gates on branch completion */
  enableQualityGates: boolean
  /** Enable cross-branch discovery routing */
  enableDiscoveryRouting: boolean
  /** Enable parallel acceleration (score-triggered splits) */
  enableParallelAcceleration: boolean
  /** Enable strategic context injection for struggling branches */
  enableContextInjection: boolean
  /** Enable research digest caching and injection */
  enableResearchCaching: boolean
  /** Enable direct injection (pause-inject-resume) for critical interventions */
  enableDirectInjection: boolean
  /** Minimum consecutive high-score steps before considering parallel split */
  parallelSplitMinStreak: number
  /** Minimum composite score to qualify for parallel split */
  parallelSplitMinScore: number
  /** Steps a branch must be struggling before context injection triggers */
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


// ═══════════════════════════════════════════════════════════════════
// Corpus Config
// ═══════════════════════════════════════════════════════════════════

export interface CorpusConfig {
  /** Model tier for Corpus LLM loop. Default: 'qwenMax' */
  modelTier: string
  /** Max tokens per Corpus LLM call. Default: 800 */
  maxTokens: number
  /** Timeout for each Corpus LLM call in ms. Default: 15_000 */
  timeoutMs: number
  /** Idle poll interval in ms when no new annotations arrive. Default: 2_000 */
  idlePollMs: number
  /** Minimum new steps before triggering an LLM analysis (saves budget). Default: 3 */
  llmAnalysisThreshold: number
  /** Maximum branches (Helixes) in the tree. Default: 16 */
  maxBranches: number
  /** Maximum depth in the tree. Default: 4 */
  maxDepth: number
  /** Minimum sweeps between interventions to the same Helix. Default: 3 */
  interventionCooldownSweeps: number
  /** Score below which a branch is flagged as struggling. Default: 0.4 */
  strugglingScoreThreshold: number
  /** Consecutive declining-score steps before flagging. Default: 3 */
  decliningScoreThreshold: number
  /** Whether to post summaries to the constellation blackboard. Default: true */
  postToBlackboard: boolean
  /** Whether the Corpus is enabled. Default: true */
  enabled: boolean
  /** Interventions before auto-spawning a decomposition branch. Default: 5 */
  autoSpawnInterventionThreshold: number

  // ── Safety-Net Cadence (Shared Thought Tree mode) ─────────

  /**
   * Corpus operating cadence. Default: 'safety-net'
   *
   * - 'active': Legacy mode — Corpus runs LLM analysis on every sweep
   *   with new steps. Full directive authority exercised proactively.
   *
   * - 'safety-net': Self-organizing mode — Corpus runs LLM analysis
   *   only when pathological patterns are detected or escalations arrive.
   *   Routine coordination is handled by Brainstem self-organization
   *   through the Shared Thought Tree.
   */
  cadence: CorpusCadence

  /**
   * In safety-net mode, minimum sweeps between LLM analyses even when
   * pathology is detected. Prevents rapid-fire LLM calls. Default: 3
   */
  safetyNetMinSweepsBetweenAnalysis: number

  /**
   * Whether to use tool-based analysis (structured tool calls) instead
   * of the legacy prompt/parse approach. Default: true
   */
  useToolBasedAnalysis: boolean

  /**
   * Maximum tool calls per Corpus analysis cycle. Prevents runaway
   * tool loops. Default: 10
   */
  maxToolCallsPerCycle: number

  /**
   * Proactive behavior configuration. Controls which proactive
   * capabilities are enabled and their thresholds.
   */
  proactive: CorpusProactiveConfig
}

/** Corpus operating cadence */
export type CorpusCadence = 'active' | 'safety-net'

export const DEFAULT_CORPUS_CONFIG: CorpusConfig = {
  modelTier: 'qwenMax',
  maxTokens: 800,
  timeoutMs: 90_000,
  idlePollMs: 10_000,
  llmAnalysisThreshold: 3,
  maxBranches: 16,
  maxDepth: 4,
  interventionCooldownSweeps: 3,
  strugglingScoreThreshold: 0.4,
  decliningScoreThreshold: 3,
  postToBlackboard: true,
  enabled: true,
  autoSpawnInterventionThreshold: 5,
  cadence: 'safety-net',
  safetyNetMinSweepsBetweenAnalysis: 3,
  useToolBasedAnalysis: true,
  maxToolCallsPerCycle: 10,
  proactive: DEFAULT_PROACTIVE_CONFIG,
}


// ═══════════════════════════════════════════════════════════════════
// Corpus Dependencies
// ═══════════════════════════════════════════════════════════════════

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
  /** LLM adapter for the Corpus's own analysis loop */
  llm: CorpusLLM
  /** Logger */
  logger: ILogger
  /** The constellation's overall goal */
  goal: string
  /** Constellation ID for event attribution */
  constellationId: string
  /** Optional event bus for emitting corpus events */
  eventBus?: IEventBus
  /** Optional blackboard for posting summaries */
  blackboard?: CorpusBlackboard
  /** Callback to submit a spawn request to the pipeline queue */
  onSpawnRequest?: (request: { goal: string; context?: string; template?: string; requestingHelixId: string }) => void
  /** Optional cross-Helix dialectic for inter-branch communication */
  crossHelixDialectic?: import('./cross-helix-dialectic.js').CrossHelixDialectic
  /** Read-only file access for validating paths in spawn goals and interventions. Returns null if file not found. */
  readFile?: (path: string) => Promise<string | null>

  // ── Proactive Capability Hooks ────────────────────────────────

  /**
   * Launch a new Helix branch from the Corpus (for re-decomposition and parallel splits).
   * Returns the helixId of the launched branch.
   */
  launchHelix?: (goal: string, context: string | undefined, template: ConstellationTemplate | undefined) => Promise<string>

  /**
   * Pause a running Helix session (for direct injection).
   * Returns true if the session was successfully paused.
   */
  pauseHelix?: (helixId: string) => boolean

  /**
   * Resume a paused Helix session.
   */
  resumeHelix?: (helixId: string) => void

  /**
   * Kill a running Helix session (for re-decomposition, over-budget).
   */
  killHelix?: (helixId: string) => void

  /**
   * Inject a system message directly into a Helix session's guidance queue.
   * This bypasses the normal Brainstem directive flow.
   */
  injectGuidance?: (helixId: string, content: string, urgency: import('../helix/brainstem-types.js').GuidanceUrgency) => void

  /**
   * Run a shell command (for quality gates: tsc, tests).
   * Returns { exitCode, stdout, stderr }.
   */
  runCommand?: (command: string, timeoutMs?: number) => Promise<{ exitCode: number; stdout: string; stderr: string }>

  /**
   * Get template for a given helix (to determine budget defaults).
   */
  getHelixTemplate?: (helixId: string) => ConstellationTemplate | undefined

  /**
   * Optional callback to persist Corpus events to the ConstellationStore.
   * Decouples the Corpus from direct store dependency while enabling
   * event audit trails for sweeps, patterns, interventions, and health changes.
   */
  persistEvent?: (type: string, entity: string | null, message: string, data?: unknown) => void
}

/**
 * Minimal blackboard interface for Corpus posting.
 * Same shape as BrainstemBlackboard — any compatible object satisfies this.
 */
export interface CorpusBlackboard {
  post(
    channel: 'findings' | 'concerns' | 'decisions',
    entry: {
      author: string
      content: string
      structured?: Record<string, unknown>
      priority?: number
      tags?: string[]
    },
  ): unknown
}


// ═══════════════════════════════════════════════════════════════════
// Corpus Result — Included in ConstellationResult
// ═══════════════════════════════════════════════════════════════════

/**
 * The Corpus's final result, summarizing its reasoning across all branches.
 */
export interface CorpusResult {
  /** Full tree snapshot at completion */
  tree: CorpusTreeSnapshot
  /** Branch assessments */
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
  /** Cross-Helix patterns detected during the run */
  crossPatterns: CrossHelixPattern[]
  /** Interventions sent to child Brainstems */
  interventions: CorpusIntervention[]
  /** Spawn decisions made */
  spawnDecisions: SpawnDecision[]
  /** Re-decompositions triggered mid-flight */
  reDecompositions: ReDecompositionRequest[]
  /** Quality gate results for completed branches */
  qualityGateResults: Array<{ helixId: string; result: QualityGateResult }>
  /** Discoveries routed across branches */
  discoveryCount: number
  /** Direct injections performed */
  directInjections: DirectInjection[]
  /** Research digests built from completed research branches */
  researchDigests: ResearchDigest[]
  /** Parallel splits triggered */
  parallelSplits: ParallelSplitRequest[]
  /** Context injections performed */
  contextInjections: ContextInjection[]
  /** How many sweep cycles completed */
  sweepCount: number
  /** Whether the Corpus LLM is healthy (able to make strategic decisions) */
  llmHealthy: boolean
  /** Number of consecutive LLM failures */
  llmFailureCount: number
  /** How long the Corpus was active */
  durationMs: number
}

/**
 * Record of an intervention the Corpus made.
 * Extends CorpusDirective with outcome tracking.
 */
export interface CorpusIntervention extends CorpusDirective {
  /** Whether the target Brainstem acknowledged receipt */
  acknowledged: boolean
  /** Which sweep cycle produced this intervention */
  sweepNumber: number
}


// ═══════════════════════════════════════════════════════════════════
// Goal Decomposition — Pre-flight planning via a planning Helix
// ═══════════════════════════════════════════════════════════════════

/**
 * Result of Corpus goal decomposition.
 * Produced by a short-lived planning Helix that analyzes the goal
 * and breaks it into concrete sub-tasks.
 */
export interface GoalDecomposition {
  /** Whether decomposition was performed (false = simple goal, passed through) */
  decomposed: boolean
  /** The original goal */
  originalGoal: string
  /** Sub-tasks to execute (each becomes a Helix) */
  subTasks: GoalSubTask[]
  /** Execution strategy: how sub-tasks should be scheduled */
  strategy: 'sequential' | 'parallel' | 'tree'
  /** Context discovered during planning that should be shared with all sub-tasks */
  sharedContext?: string
  /** How long decomposition took */
  durationMs: number
}

/**
 * A single sub-task from goal decomposition.
 */
export interface GoalSubTask {
  /** Focused goal for this sub-task */
  goal: string
  /** Additional context specific to this sub-task */
  context?: string
  /** Suggested template for the Helix */
  template?: ConstellationTemplate
  /** Relative priority (higher = more important, default 1) */
  priority: number
  /** File paths that this sub-task needs to read (validated by planning Helix) */
  relevantFiles?: string[]
  /** Suggested step budget from decomposer (overrides template default) */
  budgetSteps?: number
}


// ═══════════════════════════════════════════════════════════════════
// Branch Budgets — Step + time constraints per branch
// ═══════════════════════════════════════════════════════════════════

/**
 * Budget allocated to a branch. Corpus tracks consumption and escalates
 * when budget is consumed without proportional output.
 */
export interface BranchBudget {
  /** Maximum steps this branch should take */
  maxSteps: number
  /** Maximum wall-clock time in milliseconds */
  maxTimeMs: number
  /** Steps consumed so far */
  consumedSteps: number
  /** Time consumed so far (set during evaluation) */
  consumedTimeMs: number
  /** When this branch started */
  startedAt: number
  /** Source of the budget (decomposer suggestion or template default) */
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


// ═══════════════════════════════════════════════════════════════════
// Quality Gates — Verify branch output before accepting completion
// ═══════════════════════════════════════════════════════════════════

/** Result of running quality gates on a completed branch */
export interface QualityGateResult {
  /** Whether all gates passed */
  passed: boolean
  /** Individual gate outcomes */
  gates: QualityGateCheck[]
  /** Time spent running gates */
  durationMs: number
}

export interface QualityGateCheck {
  /** Gate name */
  name: 'files_exist' | 'type_check' | 'tests' | 'placeholder_scan'
  /** Whether this gate passed */
  passed: boolean
  /** Human-readable details */
  details: string
  /** Files that failed this gate */
  failedFiles?: string[]
}


// ═══════════════════════════════════════════════════════════════════
// Re-decomposition — Mid-flight branch splitting
// ═══════════════════════════════════════════════════════════════════

/** Request from Corpus LLM to re-decompose a branch mid-flight */
export interface ReDecompositionRequest {
  /** Branch being split */
  sourceHelixId: string
  /** Rationale from the LLM */
  reason: string
  /** New sub-tasks to spawn */
  newSubTasks: GoalSubTask[]
  /** Whether to kill the source branch (vs. redirect it to a narrower scope) */
  killSource: boolean
  /** Narrowed goal for the source branch if not killed */
  narrowedGoal?: string
}


// ═══════════════════════════════════════════════════════════════════
// Discovery Routing — Cross-branch knowledge sharing
// ═══════════════════════════════════════════════════════════════════

/** A discovery made by a branch that may be useful to others */
export interface DiscoveryEntry {
  /** ID for dedup */
  id: string
  /** Branch that made the discovery */
  sourceHelixId: string
  /** What was discovered (from Brainstem annotation) */
  content: string
  /** Type of discovery */
  type: 'architecture' | 'file_location' | 'pattern' | 'constraint' | 'decision'
  /** File paths relevant to this discovery */
  relatedFiles: string[]
  /** When discovered */
  timestamp: number
  /** Which branches have received this discovery */
  deliveredTo: Set<string>
}


// ═══════════════════════════════════════════════════════════════════
// Direct Injection — Pause-inject-resume for critical interventions
// ═══════════════════════════════════════════════════════════════════

/** A direct injection bypassing the Brainstem guidance queue */
export interface DirectInjection {
  /** Target Helix session */
  targetHelixId: string
  /** Message to inject as system context */
  message: string
  /** Urgency level */
  urgency: 'critical' | 'high' | 'normal'
  /** Whether the session was paused for injection */
  paused: boolean
  /** When injection happened */
  timestamp: number
  /** How long the session was paused (ms) */
  pauseDurationMs?: number
}


// ═══════════════════════════════════════════════════════════════════
// Research Digest — Cached findings from completed research branches
// ═══════════════════════════════════════════════════════════════════

/** Full digest of a completed research branch's findings */
export interface ResearchDigest {
  /** Branch that produced this digest */
  sourceHelixId: string
  /** Goal that was researched */
  goal: string
  /** All annotations from the branch */
  annotations: Array<{
    step: number
    type: string
    summary: string
    scores: { goalAlignment: number; novelty: number; progress: number }
  }>
  /** Key discoveries extracted from annotations */
  discoveries: string[]
  /** File paths that were read/explored */
  filesExplored: string[]
  /** File paths that were modified */
  filesModified: string[]
  /** Architecture notes / patterns identified */
  architectureNotes: string[]
  /** The branch's final conclusion/summary */
  conclusion: string
  /** When this digest was created */
  createdAt: number
}


// ═══════════════════════════════════════════════════════════════════
// Parallel Split — Score-triggered branch acceleration
// ═══════════════════════════════════════════════════════════════════

/** Request to split a productive branch into parallel sub-branches */
export interface ParallelSplitRequest {
  /** Branch being split */
  sourceHelixId: string
  /** Rationale from LLM */
  reason: string
  /** New parallel sub-tasks */
  newSubTasks: GoalSubTask[]
  /** Narrowed goal for the original branch (continues with reduced scope) */
  continuedGoal: string
}


// ═══════════════════════════════════════════════════════════════════
// Strategic Context Injection — Help struggling branches find their way
// ═══════════════════════════════════════════════════════════════════

/** Context injection from Corpus to a struggling branch */
export interface ContextInjection {
  /** Target branch */
  targetHelixId: string
  /** Source of context */
  source: 'code_intelligence' | 'file_read' | 'research_digest' | 'cross_branch'
  /** The context content injected */
  content: string
  /** Why this context was injected */
  reason: string
  /** Token count of injected content */
  tokenEstimate: number
  /** When injected */
  timestamp: number
}


// ═══════════════════════════════════════════════════════════════════
// Memory Injection Types — Branch-level Memory Continuity
// ═══════════════════════════════════════════════════════════════════

/**
 * Memory context injected into a Helix branch at startup.
 * Provides past-run continuity for new branches.
 */
export interface BranchMemoryContext {
  /** Helix ID this context is for */
  helixId?: string
  /** Goal of the branch */
  goal?: string
  /** Search query used to find memories */
  searchQuery?: string
  /** Retrieved memory entries, ranked by relevance */
  memories: InjectedMemory[]
  /** Total relevant memories found (may exceed injected count) */
  totalFound?: number
  /** Total available memories (alias for totalFound) */
  totalAvailable?: number
  /** When memory injection occurred */
  injectedAt: number
}

/**
 * A single memory entry injected into a branch.
 */
export interface InjectedMemory {
  /** Memory content */
  content: string
  /** Relevance score (0-1) */
  relevance: number
  /** Memory type/category */
  type: string
  /** When the memory was originally created (epoch ms) */
  createdAt: number
  /** Optional tags */
  tags?: string[]
  /** Whether this memory is pinned */
  pinned?: boolean
  /** Importance score */
  importance?: number
}
