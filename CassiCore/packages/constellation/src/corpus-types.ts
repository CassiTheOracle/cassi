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
  pushAnnotation(helixId: string, annotation: BrainstemAnnotation): void

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
}


// ── Tree Snapshot (for Cassi / progress reporting) ────────────────

export interface CorpusTreeSnapshot {
  branches: CorpusBranchSnapshot[]
  totalSteps: number
  activeBranches: number
  snapshotAt: number
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
}


// ═══════════════════════════════════════════════════════════════════
// Corpus Processed State — The Corpus's own organized view
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

  /** Rolling average of recent scores (last 5 annotations) */
  rollingScore: number

  /** Full score trajectory for trend analysis */
  scoreTrajectory: number[]

  /** Most frequent annotation type in recent steps */
  dominantPattern: WorkUnitAnnotation | 'none'

  /** Files this Helix has modified (for conflict detection) */
  filesModified: Set<string>

  /** Consecutive steps with declining scores */
  decliningScoreStreak: number

  /** When this branch last had activity */
  lastActivityAt: number

  /** Whether an auto-spawn has already been triggered for this branch */
  autoSpawnTriggered?: boolean
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

export interface CorpusConfig {
  /** Model tier for Corpus LLM loop. Default: 'balanced' */
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
}

export const DEFAULT_CORPUS_CONFIG: CorpusConfig = {
  modelTier: 'balanced',
  maxTokens: 800,
  timeoutMs: 15_000,
  idlePollMs: 2_000,
  llmAnalysisThreshold: 3,
  maxBranches: 16,
  maxDepth: 4,
  interventionCooldownSweeps: 3,
  strugglingScoreThreshold: 0.4,
  decliningScoreThreshold: 3,
  postToBlackboard: true,
  enabled: true,
  autoSpawnInterventionThreshold: 5,
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
  }>
  /** Cross-Helix patterns detected during the run */
  crossPatterns: CrossHelixPattern[]
  /** Interventions sent to child Brainstems */
  interventions: CorpusIntervention[]
  /** Spawn decisions made */
  spawnDecisions: SpawnDecision[]
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
