/**
 * Corpus Types (vendor stub)
 *
 * Faithful type surface for the Constellation-level cognitive organizer,
 * extracted from CassiCore `core/intelligence/constellation/corpus-types.ts`.
 * Consumed by helix (type-only): brainstem.ts, brainstem-types.ts,
 * brainstem-tools.ts, brainstem-mini-helix.ts.
 *
 * Only the types helix imports are reproduced here (import type). Supporting
 * cross-module types (GuidanceUrgency, BrainstemAnnotation, WorkUnitAnnotation,
 * DetectedPattern) are declared as minimal local versions so the stub is
 * self-contained and typechecks standalone.
 */

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
 */
export type CorpusBranchStatus =
  | 'active'
  | 'completed'
  | 'cancelled'
  | 'failed'

/**
 * Interface for the shared Corpus tree data structure.
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

/**
 * Branch Digest — A compact, Brainstem-generated summary of a Helix's
 * current state. Published to the shared tree so peer Helixes can read
 * each other's progress without parsing raw annotations.
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
 * can read and contribute to.
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

/**
 * Strategy Retrospective — recorded when a Brainstem changes its approach.
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
 * demonstrated. Elevated to constellation-level knowledge.
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
 * measured outcome.
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
}

/**
 * A directive from the Corpus to a child Helix's Brainstem.
 *
 * The Brainstem receives this and converts it to a PendingGuidance,
 * delivering it to Unity through its normal escalation model.
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
 */
export type CorpusDirectiveType =
  | 'guidance'
  | 'redirect'
  | 'throttle'
  | 'priority-shift'
  | 'cancel'
  | 'context-inject'

/**
 * Pattern types that emerge across multiple Helix branches.
 */
export type CrossHelixPatternType =
  | 'conflict'
  | 'redundancy'
  | 'divergence'
  | 'convergence'
  | 'asymmetric-progress'
  | 'cascade-failure'
  | 'resource-imbalance'

// ---------------------------------------------------------------------------
// Minimal local supporting types (cross-module, declared here for
// self-containment). These match the shapes helix consumes from the
// constellation `helix/brainstem-types.js` module.
// ---------------------------------------------------------------------------

/** Guidance urgency level — determines injection method. */
export type GuidanceUrgency =
  | 'low'
  | 'medium'
  | 'high'
  | 'critical'

/** Work unit classification. */
export type WorkUnitAnnotation =
  | 'exploration'
  | 'research'
  | 'implementation'
  | 'testing'
  | 'revision'
  | 'drift'

/** Detected pathological pattern. */
export type DetectedPattern =
  | 'none'
  | 'paralysis'
  | 'drift'
  | 'convergence'
  | 'stalling'

/**
 * A single scored annotation produced by the Brainstem LLM.
 */
export interface BrainstemAnnotation {
  /** ID of the work unit being annotated */
  workUnitId: string
  /** Composite quality score (0-1) */
  score: number
  /** Work unit classification */
  annotation: WorkUnitAnnotation
  /** Synthesized reviewer dialectic */
  synthesis: string
  /** Detected pathological pattern */
  pattern: DetectedPattern
  /** Guidance for Unity, or null if no guidance needed */
  guidance: string | null
  /** Urgency level */
  guidanceUrgency: GuidanceUrgency
  /** Human-readable note */
  trainingNote: string
  /** Axon step this annotation maps to */
  axonStep: number
  /** Timestamp when created */
  timestamp: number
  /** Goal alignment: 0=off-target, 1=directly advancing the goal */
  goalAlignment: number
  /** Novelty: 0=re-reading known content, 1=entirely new insight */
  novelty: number
  /** Progress: 0=no measurable progress, 1=significant concrete advancement */
  progress: number
  /** Discoveries made in this step */
  discoveries: string[]
  /** Decisions made in this step with rationale */
  decisions: string[]
  /** Current working hypothesis */
  hypothesis: string
  /** Concrete outputs produced */
  outputs: string[]
  /** Active blockers or obstacles encountered */
  blockers: string[]
  /** Planned next steps */
  nextSteps: string[]
  /** Knowledge delta vs. the previous step */
  knowledgeDelta: string
}
