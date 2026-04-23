/**
 * Helix Type Definitions
 *
 * Core types for the inverted-pyramid agent pattern.
 * One worker (Unity) at the base, two concurrent reviewers (Yang + Yin) above,
 * and a Brainstem serving as cognitive organizer.
 *
 * Communication topology:
 *   Unity <-> Reviewers: WorkStream (work units, nudges)
 *   Yang  <-> Yin:       DialecticChannel (findings, challenges, concessions)
 *   Brainstem -> Unity:  Guidance injection, annotations, pattern detection
 *
 * Named after the double helix trail of binary stars — Unity is the barycenter,
 * Yang and Yin are the orbiting stars, Brainstem is the cognitive organizer.
 */

import type { ConvergencePoint, UnresolvedTension } from './dialectic-channel.js'
import type { Blackboard } from '../flux-team/blackboard.js'
import type { DyadRole } from './work-types.js'
import type { UnityStatusThresholds } from './work-stream.js'
import type { GlobalWorkspace } from '../workspace/index.js'
import type { AutoReportSection } from './brainstem-types.js'


/** Helix uses a subset of DyadRole — unity (worker) + yang/yin (reviewers). Mentor deprecated in favor of Brainstem. */
export type HelixRole = Extract<DyadRole, 'unity' | 'yang' | 'yin'>


/** Unique identifier for a posture instance (e.g. "helix-unity-a3f"). */
export type PostureId = string


/**
 * Preset definition for a Helix session — seeds the initial posture roster and
 * toggles brain-integration features. Full topology lives in the HelixConductor
 * (Phase B). For Phase A the flag on HelixProjectOpts is sufficient; this
 * type is the forward-compatible shape presets will take.
 */
export interface HelixPreset {
  name: string
  brainIntegration: boolean
  reviewerMode?: 'passive' | 'active'
  postures?: Array<{ role: HelixRole; roleId?: string; priority?: number }>
}


export interface HelixProjectOpts {
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
  /** Override artifact namespace for file sharing (set by parent orchestrator) */
  artifactNamespace?: string
  /** Override session type for tool context */
  sessionType?: 'dyad' | 'lumen' | 'flux' | 'helix' | 'standalone'
  /** Team ID when running inside a FluxTeam */
  teamId?: string
  /**
   * Configurable thresholds for UnityStatus proactive signals.
   * When exceeded, reviewers automatically receive status updates about Unity's progress.
   * Defaults: 10 iterations, 60 seconds, 5 repeated tool calls.
   */
  unityStatusThresholds?: UnityStatusThresholds
  /**
   * Override the model used for all postures (unity, yang, yin).
   * When set, bypasses the ModelDirective and fallback chain.
   */
  modelOverride?: { provider: string; model: string }
  /**
   * Phase A feature flag. When true, each posture is wrapped in a
   * PostureModule and publishes CognitiveSignals into the GlobalWorkspace
   * alongside its existing WorkStream / DialecticChannel writes (dual-publish).
   * Requires `globalWorkspace` to be set; no-op otherwise. Default false.
   */
  brainIntegration?: boolean
  /**
   * The brain's GlobalWorkspace instance. When absent, brain-integration
   * features are disabled silently.
   */
  globalWorkspace?: GlobalWorkspace
  /**
   * Optional telemetry sink for session + signal metrics and spans.
   * Created fresh if brainIntegration is on and this is unset.
   */
  telemetry?: import('./helix-telemetry.js').HelixTelemetry
}


export interface HelixCompletionStatus {
  complete: boolean
  unityStatus: 'completed' | 'errored' | 'timeout' | 'not-started'
  yangStatus: 'completed' | 'errored' | 'timeout' | 'not-started'
  yinStatus: 'completed' | 'errored' | 'timeout' | 'not-started'
  mentorStatus: 'completed' | 'errored' | 'timeout' | 'not-started'
  degraded: boolean
  reason?: string
}


export interface HelixPosture {
  name: HelixRole
  systemPrompt: string
  temperature: number
  slotName: string
  toolAccess: 'read-only' | 'read-only+memory' | 'full'
  maxIterations: number
  /**
   * Pineal facet scope for system-prompt assembly + post-turn reinforcement.
   * Format `helix:{role}` when brainIntegration is on. When absent, the
   * posture uses universal facets only. See `pineal/injection.ts`.
   */
  pinealScope?: string
}


export interface HelixPostureResult {
  conclusion: string
  confidence: number
  keyPoints: string[]
  iterationCount: number
  toolCallCount: number
  tokensUsed: number
  durationMs: number
  error?: string
  /** Unity only: work units produced */
  workUnitsProduced?: number
  /** Reviewer only: nudges sent to Unity */
  nudgesSent?: number
  /** Reviewer only: findings shared */
  findingsShared?: number
  /** Reviewer only: challenges made */
  challengesMade?: number
  /** Reviewer only: concessions made */
  concessionsMade?: number
  /** Mentor only: recommendation from synthesis (proceed/stop/revise) */
  recommendation?: string
  /** Mentor only: remaining risks from synthesis */
  remainingRisks?: string[]
}


export interface HelixResult {
  /** Unity's summary of work done */
  unitySummary?: string
  /** Yang reviewer's summary */
  yangSummary?: string
  /** Yin reviewer's summary */
  yinSummary?: string
  /** Mentor's synthesis */
  mentorSynthesis?: string
  /** Mentor's recommendation */
  mentorRecommendation?: 'proceed' | 'proceed-with-caution' | 'revise' | 'reject'
  /** Mentor's confidence */
  mentorConfidence?: number

  unityConclusion: string
  yangConclusion: string
  yinConclusion: string
  mentorConclusion: string

  /** Points where Yang and Yin reviewers reached agreement */
  convergencePoints: ConvergencePoint[]
  /** Unresolved disagreements between reviewers */
  unresolvedTensions: UnresolvedTension[]

  unityKeyPoints?: string[]
  yangKeyPoints?: string[]
  yinKeyPoints?: string[]
  mentorKeyFindings?: string[]
  mentorRemainingRisks?: string[]
  unityConfidence?: number
  yangConfidence?: number
  yinConfidence?: number

  /** Quality score derived from reviewer convergence and Unity confidence */
  qualityScore?: number
  remainingIssues?: string[]

  /** Files modified during the session (by Unity) */
  filesModified?: Array<{ path: string; action: string; summary: string }>

  tokensUsed: { unity: number; yang: number; yin: number; mentor: number }
  iterationCounts: { unity: number; yang: number; yin: number; mentor: number }
  toolCallCounts: { unity: number; yang: number; yin: number; mentor: number }

  /** Dialectic communication statistics (Yang <-> Yin reviewers) */
  dialecticStats: {
    findings: number
    challenges: number
    concessions: number
    convergencePoints: number
    unresolvedChallenges: number
  }

  /** Pipeline-level aggregated stats */
  pipelineStats: {
    workUnitsProduced: number
    nudgesSent: number
    nudgesAcknowledged: number
  }

  durationMs: number
  error?: string
  completionStatus: HelixCompletionStatus

  /** Brainstem-synthesized auto report sections (canonical in focused profiles). */
  autoReport?: AutoReportSection[]

  /** Consolidated real-time metrics from HelixCoordinator */
  metrics?: import('./helix-metrics.js').HelixMetricsSnapshot

  /** Brainstem cognitive organizer result (replaces/supersedes mentor) */
  brainstem?: import('./brainstem-types.js').BrainstemResult

  /** Incremental report built by all postures */
  report?: import('../../../types/flux-team.js').Report
  /** Blackboard snapshot at completion */
  blackboard?: import('../../../types/flux-team.js').BlackboardState
}
