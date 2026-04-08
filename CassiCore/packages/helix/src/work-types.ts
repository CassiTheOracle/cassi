/**
 * Dyad Type Definitions
 *
 * Core types for the three-agent collaborative pipeline system.
 * Dyad postures work in a streaming pipeline: Yang creates, Yin refines, Apex oversees.
 */

import type { Blackboard } from '../flux-team/blackboard.js'


export type DyadRole = 'yang' | 'yin' | 'apex' | 'unity'


/** Hint for Yin's behavior adaptation based on the task type */
export type DyadTaskType = 'implementation' | 'analysis' | 'refactor' | 'auto'


export interface DyadProjectOpts {
  goal: string
  context?: string
  /** Parent session ID for Phase Zero context distillation */
  parentSessionId?: string
  maxIterations?: number
  timeoutMs?: number
  sessionId?: string
  jobId?: string
  toolAccessOverride?: 'read-only' | 'read-only+memory' | 'full'
  /**
   * Hint for what kind of task this is, affecting Yin's behavior:
   * - 'implementation': Yang writes code, Yin refines files (default behavior)
   * - 'analysis': Yang investigates/reports, Yin evaluates reasoning quality
   * - 'refactor': Yang restructures code, Yin verifies correctness
   * - 'auto': Yin decides based on Yang's work units (default)
   */
  taskType?: DyadTaskType
  /**
   * Shared Blackboard for this session.
   * When provided, passed directly to all postures — no new Blackboard is created.
   * When absent, a fresh Blackboard is auto-created by the pipeline.
   */
  blackboard?: Blackboard
  /**
   * If no blackboard is provided, use this ID when auto-creating one.
   * Defaults to sessionId when absent.
   */
  blackboardId?: string
  /**
   * Override artifact namespace for file sharing.
   * When set by a parent orchestrator (e.g. FluxTeam), overrides the default `dyad:{sessionId}`.
   */
  artifactNamespace?: string
  /**
   * Override session type for tool context.
   */
  sessionType?: 'dyad' | 'lumen' | 'flux' | 'helix' | 'standalone'
  /**
   * Team ID (set when running inside a FluxTeam).
   */
  teamId?: string
}


export interface DyadCompletionStatus {
  complete: boolean
  yangStatus: 'completed' | 'errored' | 'timeout' | 'not-started'
  yinStatus: 'completed' | 'errored' | 'timeout' | 'not-started'
  apexStatus: 'completed' | 'errored' | 'timeout' | 'not-started'
  degraded: boolean
  reason?: string
}


export interface ToolCallSummary {
  name: string
  callId?: string
  input: Record<string, unknown>
}

export interface ToolResultSummary {
  callId?: string
  content: string
  isError?: boolean
  durationMs?: number
}

export interface WorkUnit {
  id: string
  iteration: number
  reasoning: string
  toolCalls: ToolCallSummary[]
  toolResults: ToolResultSummary[]
  filesModified: FileChange[]
  timestamp: number
  /** Set by Yin via markWorkUnitProcessed() */
  processed?: boolean
}

export interface FileChange {
  path: string
  action: 'created' | 'modified' | 'deleted'
  summary: string
}


export type NudgeSeverity = 'low' | 'high'

export interface Nudge {
  id: string
  from: DyadRole | 'apex'
  to: DyadRole
  severity: NudgeSeverity
  content: string
  workUnitId?: string
  timestamp: number
  acknowledged: boolean
  /** Set by WorkStream — which Yang iteration this was posted at */
  yangIteration?: number
  /** Whether this nudge is blocking Yang */
  blocking?: boolean
}

export interface NudgeAck {
  nudgeId: string
  acknowledgedBy: DyadRole
  message: string
  timestamp: number
}


export interface Refinement {
  id: string
  workUnitId: string
  description: string
  filesModified: FileChange[]
  timestamp: number
}


export interface Research {
  id: string
  from: 'apex'
  target?: 'yang' | 'yin' | 'both'
  topic: string
  findings: string
  sources?: string[]
  timestamp: number
}

export interface Guidance {
  id: string
  from: 'apex' | 'yang' | 'yin'
  direction: string
  rationale: string
  target?: 'yang' | 'yin' | 'both'
  timestamp: number
}


export interface QualityAssessment {
  overallScore: number
  /** Alias for overallScore used in some contexts */  score?: number
  strengths: string[]
  weaknesses: string[]
  remainingIssues: string[]
  recommendations: string[]
  assessment: string
  timestamp: number
}

// Field names match work-stream.ts accessors (e.g. msg.workUnit, msg.nudge)

export interface WorkUnitMessage {
  type: 'work_unit'
  workUnit: WorkUnit
  timestamp: number
}

export interface RefinementMessage {
  type: 'refinement'
  refinement: Refinement
  timestamp: number
}

export interface NudgeMessage {
  type: 'nudge'
  nudge: Nudge
  timestamp: number
}

export interface NudgeAckMessage {
  type: 'nudge_ack'
  ack: NudgeAck
  timestamp: number
}

export interface ResearchMessage {
  type: 'research'
  research: Research
  timestamp: number
}

export interface GuidanceMessage {
  type: 'guidance'
  guidance: Guidance
  timestamp: number
}

export interface QualityAssessmentMessage {
  type: 'quality_assessment'
  assessment: QualityAssessment
  timestamp: number
}

export type WorkStreamMessage =
  | WorkUnitMessage
  | RefinementMessage
  | NudgeMessage
  | NudgeAckMessage
  | ResearchMessage
  | GuidanceMessage
  | QualityAssessmentMessage


export interface CurationFocus {
  filePath?: string
  files?: string[]
  directory?: string
  module?: string
}

export interface CuratedContext {
  workUnits: Array<{
    workUnit: WorkUnit
    relevance: number
    includeMode: 'full' | 'summary' | 'dropped'
    content?: 'full' | 'summarized'
    summary?: string
  }>
  activeNudges: Nudge[]
  activeRefinements: Refinement[]
  apexGuidance: Guidance[]
  droppedCount: number
  totalRelevanceScore: number
  estimatedTokens?: number
}


export interface DyadPosture {
  name: DyadRole
  systemPrompt: string
  temperature: number
  slotName: string
  toolAccess: 'read-only' | 'read-only+memory' | 'full'
  maxIterations: number
}


export interface PostureSessionResult {
  conclusion: string
  confidence: number
  keyPoints: string[]
  iterationCount: number
  toolCallCount: number
  tokensUsed: number
  durationMs: number
  error?: string
  // Added metrics for consistency
  workUnitsProduced?: number
  refinementsMade?: number
  nudgesSent?: number
  qualityScore?: number
}


export interface DyadResult {
  /** Yang's overall summary of work done */
  yangSummary?: string
  /** Yin's overall summary of refinements */
  yinSummary?: string
  /** Apex's overall summary and assessment */
  apexSummary?: string
  yangConclusion: string
  yinConclusion: string
  qualityAssessment: QualityAssessment | string
  qualityScore: number
  remainingIssues: string[]
  workUnitsProduced: number
  refinementsMade: number
  /** Alias for refinementsMade */
  refinementsCount?: number
  nudgesSent: number
  nudgesAcknowledged?: number
  convergenceScore: number
  /** Files modified during the session */
  filesModified?: FileChange[]
  yangKeyPoints?: string[]
  yinKeyPoints?: string[]
  yangConfidence?: number
  yinConfidence?: number
  tokensUsed: { yang: number; yin: number; apex: number }
  iterationCounts: { yang: number; yin: number; apex: number }
  toolCallCounts: { yang: number; yin: number; apex: number }
  pipelineStats: {
    workUnitsProduced: number
    refinementsMade: number
    nudgesSent: number
    nudgesAcknowledged: number
    researchInjected: number
    guidanceProvided: number
  }
  durationMs: number
  error?: string
  completionStatus: DyadCompletionStatus
  /**
   * Incremental report built by all postures during the session.
   * Only present when a Blackboard was wired.
   */
  report?: import('../../../types/flux-team.js').Report
  /**
   * Snapshot of the Blackboard state at session completion.
   * Contains all channels, scratchpad, plan, report, and artifact data.
   */
  blackboard?: import('../../../types/flux-team.js').BlackboardState
}
