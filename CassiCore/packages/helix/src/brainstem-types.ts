/**
 * Brainstem Types — Cognitive Organizer for Helix Sessions
 *
 * The Brainstem replaces the Mentor. It runs its own async LLM loop
 * (background tier) to:
 *   1. Automatically maintain Unity's axon tree from work units
 *   2. Score and annotate every work unit
 *   3. Detect pathological patterns (paralysis, drift, stalling)
 *   4. Synthesize reviewer dialectic into actionable guidance
 *   5. Produce training data (scored annotations)
 *
 * Topology:
 *   Unity (top) → work units → Brainstem (middle) → reviewers (bottom)
 *   Brainstem → guidance injection → Unity  [only for safety-net triggers by default]
 *   Brainstem → digest publication → Corpus [always; includes self-org signals]
 *   Reviewers → dialectic → Brainstem → synthesis → Unity
 *
 * Default guidance mode is 'safety-net-only': the Brainstem only injects
 * guidance for wall-clock budget limits and stagnation. All other guidance
 * authority belongs to the Corpus, which acts on BranchDigest.selfOrgSignals
 * published here instead.
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


/**
 * Guidance operating mode for the Brainstem.
 *
 * - 'full': Brainstem generates and injects guidance on every work unit,
 *   heartbeat, and self-org adjustment. Legacy mode.
 *
 * - 'safety-net-only': Brainstem only fires guidance for wall-clock budget
 *   limits and stagnation (score < threshold for many steps). All other
 *   guidance authority is delegated to the Corpus. Self-org adjustments are
 *   published as signals on the digest instead of being injected directly.
 *   Default mode.
 *
 * - 'tree-only': Brainstem produces no guidance whatsoever. Purely a
 *   thought-tree organizer. Use only when Corpus cadence is 'active' and
 *   stagnation recovery is handled externally.
 */
export type BrainstemGuidanceMode = 'full' | 'safety-net-only' | 'tree-only'

export interface BrainstemConfig {
  /** Model tier for Brainstem LLM loop. Default: 'background' */
  modelTier: string
  /** Max tokens per Brainstem LLM call. Default: 6000 */
  maxTokens: number
  /** Timeout for each Brainstem LLM call in milliseconds. Default: 30000 */
  timeoutMs: number
  /** Idle poll interval in milliseconds when no work units arrive. Default: 10000 */
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
  /** Rolling average score below which stagnation fires. Default: 0.4 */
  stagnationScoreThreshold: number
  /** Max consecutive explorations before forced implementation transition. Default: 15 */
  maxExplorationSteps: number
  /** Soft wall-clock limit in milliseconds — injects 'finish up soon' guidance. Default: 90 min */
  wallClockBudgetMs: number
  /** Hard wall-clock limit in milliseconds — injects 'stop now' guidance. Default: 120 min */
  wallClockHardLimitMs: number
  /** Whether to post annotations to blackboard. Default: true */
  postToBlackboard: boolean
  /** Whether to persist to training warehouse on completion. Default: true */
  persistTrainingData: boolean
  /** Whether Brainstem is enabled. Default: true */
  enabled: boolean
  /** Interval in milliseconds between time-based heartbeat annotations when idle. Default: 90_000 */
  heartbeatIntervalMs: number
  /** Accumulated stream-token count before triggering a long-reasoning heartbeat. Default: 2000 */
  longReasoningTokenThreshold: number
  /** Guidance operating mode. Default: 'full' */
  guidanceMode: BrainstemGuidanceMode
  /** Minimum work units before deciding to activate reviewers. Default: 3 */
  reviewerActivationThreshold: number
  /** If true, Brainstem can defer reviewer activation for simple tasks */
  lazyReviewerSpawning: boolean
  /** Max tokens a reviewer can consume without producing a finding before termination. Default: 200000 */
  maxTokensPerFinding?: number
}

/** Action to take for a reviewer based on efficiency evaluation */
export type ReviewerAction = 'continue' | 'warn' | 'terminate'

export const DEFAULT_BRAINSTEM_CONFIG: BrainstemConfig = {
  modelTier: 'background',
  maxTokens: 6_000,
  timeoutMs: 30_000,
  idlePollMs: 15_000,
  guidanceCooldownIterations: 2,
  paralysisThreshold: 3,
  paralysisScoreThreshold: 0.6,
  driftThreshold: 4,
  stagnationStepThreshold: 10,
  stagnationScoreThreshold: 0.4,
  maxExplorationSteps: 15,
  // 90 minutes soft wall-clock budget
  wallClockBudgetMs: 90 * 60 * 1000,
  // 120 minutes hard wall-clock limit
  wallClockHardLimitMs: 120 * 60 * 1000,
  postToBlackboard: true,
  persistTrainingData: true,
  enabled: true,
  heartbeatIntervalMs: 90_000,
  longReasoningTokenThreshold: 2_000,
  guidanceMode: 'full',
  reviewerActivationThreshold: 3,
  lazyReviewerSpawning: true,
  maxTokensPerFinding: 200_000,
}


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

/**
 * A guidance proposal that requires dual-reviewer approval before reaching Unity.
 *
 * WHY: Brainstem guidance was historically too frequent and distracting for Unity.
 * Routing guidance through both reviewers ensures only consensus-approved guidance
 * reaches the builder, while giving reviewers a concrete productive role.
 */
export interface GuidanceProposal {
  /** Unique proposal ID */
  id: string
  /** Guidance text from Brainstem */
  text: string
  /** Original urgency level from Brainstem */
  urgency: GuidanceUrgency
  /** What triggered this guidance — pattern name or event description */
  triggeredBy: string
  /** Brainstem axon step when this was generated */
  fromStep: number
  /** Timestamp when created */
  timestamp: number
  /** Reviewer votes — both must approve for guidance to reach Unity */
  votes: {
    yang: GuidanceVote | null
    yin: GuidanceVote | null
  }
  /** Current approval status */
  status: 'pending' | 'approved' | 'rejected' | 'expired'
  /** Iteration counter for timeout — auto-approves after N iterations without vote */
  iterationsSinceCreated: number
}

export interface GuidanceVote {
  /** Whether the reviewer approved the guidance */
  approved: boolean
  /** Rationale for the vote */
  reason: string
  /** Timestamp when vote was cast */
  timestamp: number
}

/**
 * A single scored annotation produced by the Brainstem LLM.
 */
export interface BrainstemAnnotation {
  /** ID of the work unit being annotated */
  workUnitId: string
  /** Composite quality score (0-1) — weighted average of dimensional scores */
  score: number
  /** Work unit classification — used for logging, display, and training data */
  annotation: WorkUnitAnnotation
  /** Synthesized reviewer dialectic, or empty if no new dialectic emerged */
  synthesis: string
  /** Detected pathological pattern */
  pattern: DetectedPattern
  /** Guidance for Unity, or null if no guidance needed */
  guidance: string | null
  /** Urgency level — determines injection method */
  guidanceUrgency: GuidanceUrgency
  /** Human-readable note for training data */
  trainingNote: string
  /** Axon step this annotation maps to */
  axonStep: number
  /** Timestamp when created */
  timestamp: number

  /** Goal alignment: 0=completely off-target, 1=directly advancing the goal */
  goalAlignment: number
  /** Novelty: 0=re-reading known content, 1=entirely new insight */
  novelty: number
  /** Progress: 0=no measurable progress, 1=significant concrete advancement */
  progress: number

  /** Discoveries made in this step */
  discoveries: string[]
  /** Decisions made in this step with rationale */
  decisions: string[]
  /** Current working hypothesis about how to achieve the goal */
  hypothesis: string
  /** Concrete outputs produced — files written, tests run, etc. */
  outputs: string[]
  /** Active blockers or obstacles encountered */
  blockers: string[]
  /** Planned next steps */
  nextSteps: string[]
  /** Knowledge delta — what changed in understanding vs. the previous step */
  knowledgeDelta: string
}


/**
 * Running cognitive model maintained by the Brainstem across all steps.
 *
 * HOW: Accumulates discoveries, decisions, and current state throughout a session.
 * The Corpus reads this to understand what a branch knows without replaying the
 * entire history.
 */
export interface CognitiveModel {
  /** Current working hypothesis about how to achieve the goal */
  currentHypothesis: string
  /** All discoveries made so far, ordered newest last */
  allDiscoveries: string[]
  /** All decisions made so far, ordered newest last */
  allDecisions: string[]
  /** Currently active blockers — resolved ones are removed */
  pendingBlockers: string[]
  /** Recent concrete outputs — files written, tests run, etc. */
  recentOutputs: string[]
  /** Planned next steps from the latest annotation */
  currentNextSteps: string[]
  /** Axon step at which the hypothesis was last updated */
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



/**
 * Brainstem's internal running state.
 */
export interface BrainstemState {
  /** All annotations produced this session */
  annotations: BrainstemAnnotation[]
  /** Score history for trajectory analysis */
  qualityTrajectory: number[]
  /** Consecutive exploration-only iterations — used for paralysis detection */
  consecutiveExplorations: number
  /** Consecutive drift iterations — used for drift detection */
  consecutiveDrifts: number
  /** Last axon step that included guidance injection */
  lastGuidanceStep: number
  /** Total guidance injections this session */
  totalGuidanceCount: number
  /** Total pattern detections this session */
  totalPatternDetections: number
  /** Current axon step counter */
  currentAxonStep: number
  /** Total work units processed */
  workUnitsProcessed: number
  /** Whether the stagnation pattern has already fired — one-shot flag */
  stagnationFired: boolean
  /** Whether the soft wall-clock budget guidance has already fired — one-shot flag */
  wallClockBudgetFired: boolean
  /** Whether the hard wall-clock limit guidance has already fired — one-shot flag */
  wallClockHardLimitFired: boolean
  /** Timestamp of last stream activity event */
  lastStreamActivityAt: number
  /** Tokens accumulated in the current step from streaming */
  streamTokensThisStep: number
  /** Count of long reasoning sequences without tool use */
  longReasoningCount: number
  /** Running cognitive model — accumulated knowledge state across all steps */
  cognitiveModel: CognitiveModel
  /** Flag set when Unity posts a significant Blackboard entry — triggers next heartbeat */
  pendingBlackboardTrigger: boolean
  /** Tokens consumed by each reviewer posture */
  reviewerTokens: { yang: number, yin: number }
  /** Findings produced by each reviewer */
  reviewerFindings: { yang: number, yin: number }
}

/**
 * @dep callers: constructor (core/intelligence/helix/brainstem.ts), constructor (core/intelligence/helix/brainstem-mini-helix.ts)
 * @dep calls: createInitialCognitiveModel
 * @dep module: Unknown
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function createInitialBrainstemState(): BrainstemState {
  return {
    annotations: [],
    qualityTrajectory: [],
    consecutiveExplorations: 0,
    consecutiveDrifts: 0,
    // WHY: -1 ensures first guidance always fires
    lastGuidanceStep: -1,
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
    reviewerTokens: { yang: 0, yin: 0 },
    reviewerFindings: { yang: 0, yin: 0 },
  }
}


/**
 * A structured message from Unity to the Brainstem.
 */
export interface UnityReport {
  /** Type of report — phase_change=state transition, blocker=obstacle, question=uncertainty, progress=status update, completion=done */
  type: 'phase_change' | 'blocker' | 'question' | 'progress' | 'completion'
  /** Human-readable message text */
  message: string
  /** Optional structured context data */
  context?: Record<string, unknown>
  /** Timestamp when reported */
  timestamp: number
  /** Iteration number when reported */
  iteration: number
}


/**
 * A pending guidance item waiting to be injected into Unity's loop.
 */
export interface PendingGuidance {
  /** Guidance text to inject into Unity */
  text: string
  /** Urgency level — determines injection method (low=tool result, high=user message, critical=blocking) */
  urgency: GuidanceUrgency
  /** Axon step that produced this guidance */
  fromStep: number
  /** Pathological pattern that triggered this guidance, or 'none' if routine */
  triggeredBy: DetectedPattern
  /** Timestamp when created */
  timestamp: number
}


/**
 * Minimal LLM interface for Brainstem — same pattern as Synapse.
 */
export interface BrainstemLLM {
  /**
   * Complete a prompt using the background tier model.
   */
  complete(opts: {
    /** Prompt text to complete */
    prompt: string
    /** Model tier to use (default: 'background') */
    modelTier: string
    /** Max tokens for response */
    maxTokens: number
    /** Timeout in milliseconds */
    timeoutMs: number
  }): Promise<{ content: string; truncated: boolean }>
}


export interface BrainstemDeps {
  /** LLM client for Brainstem completions */
  llm: BrainstemLLM
  /** Logger instance */
  logger: ILogger
  /** Session goal — used for drift detection and alignment scoring */
  goal: string
  /** Session ID for event attribution */
  sessionId: string
  /** Event bus for emitting brainstem events to the cognitive feed */
  eventBus?: IEventBus
  /** Blackboard for posting annotations */
  blackboard?: BrainstemBlackboard
  /** Corpus tree to push annotations into — only present in Constellation mode */
  corpusTree?: ICorpusTree
  /** This Helix's ID in the Constellation — for Corpus tree branch identification */
  helixId?: string
  /** Callback to request spawning a child Helix — only in Constellation mode */
  onSpawnRequest?: (request: { goal: string; context?: string; template?: string }) => void
  /** Dialectic channel for processing edit proposals from Yang/Yin reviewers */
  dialecticChannel?: import('../../intelligence/lumen/dialectic-channel.js').DialecticChannel
  /** Tool executor for applying approved edits */
  toolExecutor?: import('../../tools/executor.js').ToolExecutor
  /** Read-only file access for validating paths and grounding guidance — returns null if file not found */
  readFile?: (path: string) => Promise<string | null>
  /** ContextChunkIndex for Unity — allows brainstem to pin/evict/score context chunks */
  unityChunkIndex?: import('./context-chunk-index.js').ContextChunkIndex


  /**
   * Shared tree reader for peer awareness in Constellation mode.
   *
   * HOW: Brainstems use this to read peer digests, shared topics, elevated
   * patterns, and to publish their own digests and topic contributions —
   * enabling stigmergic self-organization without the Corpus as relay.
   */
  sharedTree?: SharedTreeReader

  /**
   * Callback to escalate to the Corpus when self-organization cannot resolve
   * an issue. Only present in Constellation mode.
   */
  escalateToCorpus?: (reason: string, context: Record<string, unknown>) => void

  /**
   * Callback to persist training signals to the ConstellationStore.
   * Called when an annotation is processed.
   */
  persistTrainingSignal?: (annotation: BrainstemAnnotation) => Promise<void>
}

/**
 * SharedTreeReader — the interface a Brainstem uses to participate in
 * the Shared Thought Tree for stigmergic self-organization.
 *
 * HOW: This is the Brainstem's view of the constellation. It enables:
 * - Reading peer digests and topics for awareness
 * - Publishing its own digest and topic contributions
 * - Recording retrospectives and effectiveness measurements
 * - Accessing the pattern library for proven strategies
 *
 * WHY no artificial token caps: With 128k context windows, full awareness
 * of all branches is affordable within a 16k working budget.
 */
export interface SharedTreeReader {
  /** Get all peer digests — excludes the calling Helix's own digest */
  getPeerDigests(): BranchDigest[]

  /** Get peer digests filtered by relevance to the calling Helix */
  getRelevantDigests(): BranchDigest[]

  /** Find topics relevant to the given files and goal keywords */
  findRelatedTopics(files: string[], goalKeywords: string[]): TopicNode[]

  /** Get all topics in the tree */
  getAllTopics(): TopicNode[]

  /** Get the constellation's elevated pattern library */
  getElevatedPatterns(): ElevatedPattern[]

  /** Get all strategy retrospectives for learning from other branches */
  getAllRetrospectives(): StrategyRetrospective[]

  /** Get effectiveness stats by adjustment type — shows what works */
  getEffectivenessStats(): Map<string, { total: number; effective: number; avgImprovement: number }>


  /** Publish or update this Helix's digest */
  updateDigest(digest: BranchDigest): void

  /**
   * Lightweight update — sets only the liveStreamSnippet on an existing digest.
   *
   * HOW: Called on every Unity stream chunk. Pure in-memory, no computation.
   * No-op if no digest exists yet.
   */
  updateLiveStreamSnippet(snippet: string): void

  /** Create a new shared topic node. Returns the topic ID. */
  createTopic(name: string, contribution: TopicContribution): string

  /** Add a contribution to an existing topic */
  contributeTopic(topicId: string, contribution: TopicContribution): void

  /** Record a strategy retrospective */
  recordRetrospective(retrospective: StrategyRetrospective): void

  /** Record an effectiveness measurement */
  recordEffectiveness(record: EffectivenessRecord): void
}

/**
 * Minimal blackboard interface for Brainstem posting and reading.
 *
 * HOW: Avoids importing the full Blackboard class — any object with compatible
 * methods satisfies this contract.
 */
export interface BrainstemBlackboard {
  /**
   * Post an entry to a channel.
   */
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
  /**
   * Read recent entries from a channel for inclusion in the brainstem prompt.
   */
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


export interface BrainstemResult {
  /** All scored annotations produced by the Brainstem */
  annotations: BrainstemAnnotation[]
  /** Quality score trajectory across all steps */
  qualityTrajectory: number[]
  /** Total number of pathological patterns detected */
  patternDetections: number
  /** Total number of guidance injections into Unity */
  guidanceInjections: number
  /** Average quality score across all annotations */
  averageScore: number
  /** Number of axon steps created */
  axonSteps: number
  /** Duration the Brainstem was active, in milliseconds */
  durationMs: number
}
