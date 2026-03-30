/**
 * Brainstem Types — Cognitive Organizer for Helix Sessions
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
import type { CognitiveSignal } from '../thought-observer.js'
import type { ICorpusTree } from '../constellation/corpus-types.js'
import type {
  CorpusDirective,
  BranchDigest,
  TopicNode,
  TopicContribution,
  StrategyRetrospective,
  ElevatedPattern,
  EffectivenessRecord,
} from '../constellation/corpus-types.js'

// ─── Configuration ────────────────────────────────────────────────────────

export interface BrainstemConfig {
  /** Model tier for Brainstem LLM loop. Default: 'balanced' */
  modelTier: string
  /** Max tokens per Brainstem LLM call. Default: 400 */
  maxTokens: number
  /** Timeout for each Brainstem LLM call in ms. Default: 8000 */
  timeoutMs: number
  /** Idle poll interval in ms when no work units arrive. Default: 10000 */
  idlePollMs: number
  /** Minimum iterations between guidance injections. Default: 2 */
  guidanceCooldownIterations: number
  /** Consecutive read-only iterations before detecting paralysis. Default: 3 */
  paralysisThreshold: number
  /** Score threshold below which exploration counts toward paralysis. Default: 0.6 */
  paralysisScoreThreshold: number
  /** Consecutive off-goal iterations before detecting drift. Default: 4 */
  driftThreshold: number
  /** Steps before stagnation detector activates. Default: 10 */
  stagnationStepThreshold: number
  /** Rolling avg score below which stagnation fires. Default: 0.4 */
  stagnationScoreThreshold: number
  /** Max consecutive explorations before forced implementation transition. Default: 15 */
  maxExplorationSteps: number
  /** Soft wall-clock limit in ms. At this point, inject 'finish up soon' guidance. Default: 90 min */
  wallClockBudgetMs: number
  /** Hard wall-clock limit in ms. At this point, inject 'stop now' guidance. Default: 120 min */
  wallClockHardLimitMs: number
  /** Whether to post annotations to blackboard. Default: true */
  postToBlackboard: boolean
  /** Whether to persist to training warehouse on completion. Default: true */
  persistTrainingData: boolean
  /** Whether Brainstem is enabled. Default: true */
  enabled: boolean
  /** Interval in ms between time-based heartbeat annotations when idle (default: 30_000) */
  heartbeatIntervalMs: number
  /** Accumulated stream-token count before triggering a long-reasoning heartbeat (default: 2000) */
  longReasoningTokenThreshold: number
}

export const DEFAULT_BRAINSTEM_CONFIG: BrainstemConfig = {
  modelTier: 'balanced',
  maxTokens: 1500,
  timeoutMs: 8_000,
  idlePollMs: 10_000,
  guidanceCooldownIterations: 2,
  paralysisThreshold: 3,
  paralysisScoreThreshold: 0.6,
  driftThreshold: 4,
  stagnationStepThreshold: 10,
  stagnationScoreThreshold: 0.4,
  maxExplorationSteps: 15,
  wallClockBudgetMs: 90 * 60 * 1000,      // 90 minutes
  wallClockHardLimitMs: 120 * 60 * 1000,  // 120 minutes
  postToBlackboard: true,
  persistTrainingData: true,
  enabled: true,
  heartbeatIntervalMs: 30_000,
  longReasoningTokenThreshold: 2_000,
}

// ─── Annotation Types ─────────────────────────────────────────────────────

/** Work unit classification produced by Brainstem scoring */
export type WorkUnitAnnotation =
  | 'exploration'     // reading, searching, gathering context
  | 'research'        // deep investigation, cross-referencing, hypothesis testing
  | 'implementation'  // writing code, creating files
  | 'testing'         // running tests, verification
  | 'revision'        // fixing based on feedback
  | 'drift'           // off-goal or unfocused activity

/** Pathological pattern detected by Brainstem */
export type DetectedPattern =
  | 'none'            // healthy progress
  | 'paralysis'       // reading without writing (exploration trap)
  | 'drift'           // diverging from the goal
  | 'convergence'     // reviewers agree on something important
  | 'stalling'        // repeating similar actions without progress

/** Guidance urgency level — determines injection method */
export type GuidanceUrgency =
  | 'low'       // inject into tool results (zero extra LLM calls)
  | 'medium'    // inject into tool results with emphasis
  | 'high'      // inject as user message (costs one LLM round-trip)
  | 'critical'  // inject as user message + mark as blocking

/** A single scored annotation produced by the Brainstem LLM */
export interface BrainstemAnnotation {
  /** Which work unit this annotates */
  workUnitId: string
  /** Composite quality score (0-1) — weighted average of dimensional scores */
  score: number
  /** Work unit classification (kept for logging/display/training) */
  annotation: WorkUnitAnnotation
  /** Synthesized reviewer dialectic (or empty if no new dialectic) */
  synthesis: string
  /** Detected pathological pattern */
  pattern: DetectedPattern
  /** Guidance for Unity (null if no guidance needed) */
  guidance: string | null
  /** Urgency of guidance (determines injection method) */
  guidanceUrgency: GuidanceUrgency
  /** Human-readable note for training data */
  trainingNote: string
  /** Which axon step this maps to */
  axonStep: number
  /** Timestamp */
  timestamp: number

  // ─── Dimensional Scores (0-1 each) ────────────────────────────────
  /** How aligned is this work with the branch's goal? 0=completely off-target, 1=directly advancing the goal */
  goalAlignment: number
  /** How much new information or capability did this step produce? 0=re-reading known content, 1=entirely new insight */
  novelty: number
  /** How much closer is the branch to completion? 0=no measurable progress, 1=significant concrete advancement */
  progress: number

  // ─── Rich Semantic Fields (populated from ###FIELDNAME blocks) ────
  /** Things discovered or learned in this step */
  discoveries: string[]
  /** Decisions made in this step and their rationale */
  decisions: string[]
  /** Current working hypothesis about how to achieve the goal */
  hypothesis: string
  /** Concrete outputs produced (files written, tests run, etc.) */
  outputs: string[]
  /** Active blockers or obstacles encountered */
  blockers: string[]
  /** What's planned for the next steps */
  nextSteps: string[]
  /** What changed in understanding vs. the previous step */
  knowledgeDelta: string
}

// ─── Cognitive Model ──────────────────────────────────────────────────────

/**
 * Running cognitive model maintained by the Brainstem across all steps.
 * Accumulates discoveries, decisions, and current state throughout a session.
 * This is what the Corpus reads when it wants to understand what a branch knows.
 */
export interface CognitiveModel {
  /** Current working hypothesis about how to achieve the goal */
  currentHypothesis: string
  /** All discoveries made so far, newest last */
  allDiscoveries: string[]
  /** All decisions made so far, newest last */
  allDecisions: string[]
  /** Currently active blockers (resolved ones are removed) */
  pendingBlockers: string[]
  /** Recent concrete outputs (files written, tests run, etc.) */
  recentOutputs: string[]
  /** What I plan to do in the next steps (from latest annotation) */
  currentNextSteps: string[]
  /** Step at which the hypothesis was last updated */
  hypothesisUpdatedAtStep: number
}

export function createInitialCognitiveModel(): CognitiveModel {
  return {
    currentHypothesis: '',
    allDiscoveries: [],
    allDecisions: [],
    pendingBlockers: [],
    recentOutputs: [],
    currentNextSteps: [],
    hypothesisUpdatedAtStep: -1,
  }
}



/** Brainstem's internal running state */
export interface BrainstemState {
  /** All annotations produced this session */
  annotations: BrainstemAnnotation[]
  /** Score history for trajectory analysis */
  qualityTrajectory: number[]
  /** Consecutive exploration-only iterations (pattern detection) */
  consecutiveExplorations: number
  /** Consecutive drift iterations */
  consecutiveDrifts: number
  /** Last axon step that included guidance */
  lastGuidanceStep: number
  /** Total guidance injections this session */
  totalGuidanceCount: number
  /** Total pattern detections this session */
  totalPatternDetections: number
  /** Current axon step counter */
  currentAxonStep: number
  /** Work units processed count */
  workUnitsProcessed: number
  /** Whether the stagnation pattern has already fired (one-shot) */
  stagnationFired: boolean
  /** Whether the soft wall-clock budget guidance has already fired (one-shot) */
  wallClockBudgetFired: boolean
  /** Whether the hard wall-clock limit guidance has already fired (one-shot) */
  wallClockHardLimitFired: boolean
  /** Last time we received a stream activity event */
  lastStreamActivityAt: number
  /** Tokens accumulated in the current step from streaming */
  streamTokensThisStep: number
  /** Count of long reasoning sequences without tool use */
  longReasoningCount: number
  /** Running cognitive model — accumulated knowledge state across all steps */
  cognitiveModel: CognitiveModel
  /** Flag set when Unity posts a significant Blackboard entry, triggers next heartbeat */
  pendingBlackboardTrigger: boolean
}

export function createInitialBrainstemState(): BrainstemState {
  return {
    annotations: [],
    qualityTrajectory: [],
    consecutiveExplorations: 0,
    consecutiveDrifts: 0,
    lastGuidanceStep: -1, // -1 ensures first guidance always fires
    totalGuidanceCount: 0,
    totalPatternDetections: 0,
    currentAxonStep: 0,
    workUnitsProcessed: 0,
    stagnationFired: false,
    wallClockBudgetFired: false,
    wallClockHardLimitFired: false,
    lastStreamActivityAt: 0,
    streamTokensThisStep: 0,
    longReasoningCount: 0,
    cognitiveModel: createInitialCognitiveModel(),
    pendingBlackboardTrigger: false,
  }
}

// ─── Unity Reports ───────────────────────────────────────────────────────

/** A structured message from Unity to the Brainstem */
export interface UnityReport {
  type: 'phase_change' | 'blocker' | 'question' | 'progress' | 'completion'
  message: string
  context?: Record<string, unknown>
  timestamp: number
  iteration: number
}

// ─── Guidance Queue ───────────────────────────────────────────────────────

/** A pending guidance item waiting to be injected into Unity's loop */
export interface PendingGuidance {
  /** The guidance text to inject */
  text: string
  /** Urgency determines injection method */
  urgency: GuidanceUrgency
  /** Which axon step produced this guidance */
  fromStep: number
  /** Pattern that triggered this guidance (if any) */
  triggeredBy: DetectedPattern
  /** Timestamp */
  timestamp: number
}

// ─── LLM Adapter ─────────────────────────────────────────────────────────

/** Minimal LLM interface for Brainstem (same pattern as Synapse) */
export interface BrainstemLLM {
  complete(opts: {
    prompt: string
    modelTier: string
    maxTokens: number
    timeoutMs: number
  }): Promise<{ content: string; truncated: boolean }>
}

// ─── Dependencies ─────────────────────────────────────────────────────────

export interface BrainstemDeps {
  llm: BrainstemLLM
  logger: ILogger
  /** The session's goal — used for drift detection */
  goal: string
  /** Session ID for event attribution */
  sessionId: string
  /** Optional event bus for emitting brainstem events to the cognitive feed */
  eventBus?: IEventBus
  /** Optional blackboard for posting annotations */
  blackboard?: BrainstemBlackboard
  /** Corpus tree to push annotations into (only in Constellation mode) */
  corpusTree?: ICorpusTree
  /** This Helix's ID in the Constellation (for Corpus tree branch identification) */
  helixId?: string
  /** Callback to request spawning a child Helix (only in Constellation mode) */
  onSpawnRequest?: (request: { goal: string; context?: string; template?: string }) => void
  /** Dialectic channel for processing edit proposals from Yang/Yin */
  dialecticChannel?: import('../../intelligence/lumen/dialectic-channel.js').DialecticChannel
  /** Tool executor for applying approved edits */
  toolExecutor?: import('../../tools/executor.js').ToolExecutor
  /** Read-only file access for validating paths and grounding guidance. Returns null if file not found. */
  readFile?: (path: string) => Promise<string | null>
  /** ContextChunkIndex for Unity — allows brainstem to pin/evict/score context chunks */
  unityChunkIndex?: import('./context-chunk-index.js').ContextChunkIndex

  // ── Shared Thought Tree (Constellation self-organization) ──────

  /**
   * Shared tree reader — provides peer awareness without the Corpus as relay.
   * Only present in Constellation mode. Brainstems use this to read peer
   * digests, shared topics, elevated patterns, and to publish their own
   * digests and topic contributions.
   */
  sharedTree?: SharedTreeReader

  /**
   * Callback to escalate to the Corpus when self-organization can't resolve
   * something. Only present in Constellation mode.
   */
  escalateToCorpus?: (reason: string, context: Record<string, unknown>) => void
}

/**
 * SharedTreeReader — the interface a Brainstem uses to participate in
 * the Shared Thought Tree for stigmergic self-organization.
 *
 * This is the Brainstem's view of the constellation. It can:
 * - Read peer digests and topics for awareness
 * - Publish its own digest and topic contributions
 * - Record retrospectives and effectiveness measurements
 * - Access the pattern library for proven strategies
 *
 * No artificial token caps — with 128k context windows, full awareness
 * of all branches is affordable within a 16k working budget.
 */
export interface SharedTreeReader {
  // ── Read operations (peer awareness) ──────────────────────────

  /** Get all peer digests (excludes the calling Helix's own). */
  getPeerDigests(): BranchDigest[]

  /** Get peer digests filtered by relevance to the calling Helix. */
  getRelevantDigests(): BranchDigest[]

  /** Find topics relevant to the given files and keywords. */
  findRelatedTopics(files: string[], goalKeywords: string[]): TopicNode[]

  /** Get all topics in the tree. */
  getAllTopics(): TopicNode[]

  /** Get the constellation's elevated pattern library. */
  getElevatedPatterns(): ElevatedPattern[]

  /** Get all strategy retrospectives (for learning from others). */
  getAllRetrospectives(): StrategyRetrospective[]

  /** Get effectiveness stats by adjustment type (what works?). */
  getEffectivenessStats(): Map<string, { total: number; effective: number; avgImprovement: number }>

  // ── Write operations (publish state) ──────────────────────────

  /** Publish or update this Helix's digest. */
  updateDigest(digest: BranchDigest): void

  /**
   * Lightweight update — sets only the liveStreamSnippet on an existing digest.
   * Called on every Unity stream chunk. Pure in-memory, no computation.
   * No-op if no digest exists yet.
   */
  updateLiveStreamSnippet(snippet: string): void

  /** Create a new shared topic node. Returns the topic ID. */
  createTopic(name: string, contribution: TopicContribution): string

  /** Add a contribution to an existing topic. */
  contributeTopic(topicId: string, contribution: TopicContribution): void

  /** Record a strategy retrospective. */
  recordRetrospective(retrospective: StrategyRetrospective): void

  /** Record an effectiveness measurement. */
  recordEffectiveness(record: EffectivenessRecord): void
}

/**
 * Minimal blackboard interface for Brainstem posting and reading.
 * Avoids importing the full Blackboard class — any object with compatible
 * methods satisfies this contract.
 */
export interface BrainstemBlackboard {
  post(
    channel: 'findings' | 'concerns',
    entry: {
      author: string
      content: string
      structured?: Record<string, unknown>
      priority?: number
      tags?: string[]
    },
  ): unknown
  /** Read recent entries from a channel for inclusion in the brainstem prompt */
  read(
    channel: 'findings' | 'concerns' | 'decisions' | 'artifacts' | 'requests',
    limit?: number,
  ): Array<{ id: string; channel: string; content: string; author: string; priority: number; tags: string[]; timestamp: number }>
  /** Get the current plan, if any */
  getPlan?(): {
    goal: string
    status: string
    steps: Array<{ title: string; description: string; status: string; order: number }>
  } | null
  /** Get the current report, if any */
  getReport?(): {
    sections: Array<{ type: string; title: string; content: string; author?: string; status?: string }>
  } | null
}

// ─── Result (included in HelixResult) ─────────────────────────────────────

export interface BrainstemResult {
  /** All scored annotations */
  annotations: BrainstemAnnotation[]
  /** Quality score trajectory */
  qualityTrajectory: number[]
  /** Total pattern detections */
  patternDetections: number
  /** Total guidance injections */
  guidanceInjections: number
  /** Average quality score */
  averageScore: number
  /** Axon steps created */
  axonSteps: number
  /** Duration the Brainstem was active (ms) */
  durationMs: number
}
