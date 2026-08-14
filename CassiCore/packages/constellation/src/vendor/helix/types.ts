/**
 * Helix Type Definitions
 *
 * Core types for the three-posture collaborative agent pattern.
 * Three equally capable postures (Unity, Yang, Yin) collaborating,
 * with a Brainstem serving as cognitive organizer.
 *
 * Communication topology:
 *   Postures <-> Postures: WorkStream (work units, nudges)
 *   Yang  <-> Yin:         DialecticChannel (findings, challenges, concessions)
 *   Brainstem -> Postures: Guidance injection, annotations, pattern detection
 *
 * Named after the double helix trail of binary stars.
 */

import type { ConvergencePoint, UnresolvedTension } from './dialectic-channel.js'
// REMOVED: Blackboard import — deprecated. Now uses LaminaField + GlobalWorkspace
// import type { Blackboard } from '../flux-team/blackboard.js'
import type { DyadRole } from './work-types.js'
import type { UnityStatusThresholds } from './work-stream.js'
import type { GlobalWorkspace } from '../workspace/index.js'
import type { AutoReportSection, BrainstemResult } from './brainstem-types.js'
import type { HelixTelemetry } from './helix-telemetry.js'
import type { HelixMetricsSnapshot } from './helix-metrics.js'
import type { Report } from '../types/flux-team.js'


/**
 * Polyphonic Postures — Trait vector type system for continuous posture space.
 *
 * Replaces categorical role assignments with 8-dimensional trait vectors.
 * Each axis ranges 0–1, representing a continuum of cognitive stance.
 *
 * Trait axes (named for brain regions / cognitive functions):
 *   dorsolateral:  executive control, planning, metacognition (0=reactive, 1=deliberate)
 *   ventromedial:  value alignment, welfare, ethics (0=amoral, 1=ethically-grounded)
 *   amygdala:      emotional intensity, urgency (0=calm, 1=urgent)
 *   hippocampus:   episodic memory, context recall (0=amnesic, 1=context-rich)
 *   anterior:      divergent thinking, creativity (0=convergent, 1=divergent)
 *   posterior:     analytical rigor, precision (0=heuristic, 1=analytical)
 *   insular:       self-awareness, metacognition (0=oblivious, 1=self-reflective)
 *   accumbens:     reward sensitivity, risk appetite (0=risk-averse, 1=risk-seeking)
 *
 * Trait vectors enable:
 *   - Continuous posture space (not just unity/yang/yin)
 *   - Dynamic prompt weighting based on trait values
 *   - Credibility scoring via trait distance in GlobalWorkspace
 *   - Evolutionary posture adjustment via feedback
 */


/**
 * 8-dimensional trait vector representing a cognitive posture.
 *
 * All values are in [0, 1]. The vector represents a point in the 8-dimensional
 * cognitive posture space defined by the axes below.
 */
export interface TraitVector {
  structural: number     // Organization: 0=ad-hoc, 1=structured
  pragmatic: number      // Pragmatism: 0=exploratory, 1=pragmatic
  generative: number     // Creativity: 0=conservative, 1=generative
  analytical: number     // Rigor: 0=heuristic, 1=analytical
  collaborative: number  // Dialectic: 0=autonomous, 1=collaborative
  adaptive: number       // Flexibility: 0=rigid, 1=adaptive
  decisive: number       // Decisiveness: 0=indecisive, 1=decisive
  focused: number        // Focus: 0=scattered, 1=focused
}

/**
 * Attention state for a Helix session — a point on S¹⁵³⁵ tracking what
 * the session is currently focused on. Updated per turn via slerp toward
 * the context embedding, with exponential decay for forgetting.
 *
 * Lives on the same unit hypersphere as engram gate embeddings.
 */
export interface AttentionState {
  /** Current attention vector on the unit hypersphere (1536-dim, L2-normalized). */
  embedding: Float32Array
  /** Timestamp of last update (epoch ms). */
  updatedAt: number
  /** Half-life in turns for exponential decay (shorter = faster forgetting). */
  halfLifeTurns: number
  /** Momentum: slerp interpolation weight per update. Small (0.05) = sticky. */
  momentum: number
}

/**
 * Derive attention parameters from a TraitVector.
 *
 * Maps the 8-dim trait space to attention configuration:
 *   focused → attentionRadius   (narrow/focused vs broad/scattered)
 *   adaptive → momentum          (sticky/rigid vs fluid/flexible)
 *   generative → capacity        (conservative vs broad)
 *   focused → halfLifeTurns      (short vs long retention)
 */
export function traitToAttentionParams(traits: TraitVector): {
  attentionRadius: number     // cosSim threshold for "attended" engrams
  momentum: number            // slerp interpolation weight per update
  halfLifeTurns: number       // turns before attention decays by 50%
  capacity: number            // max engrams in attended set
} {
  return {
    attentionRadius: 0.55 + traits.focused * 0.35,   // [0.55 .. 0.90]
    momentum: 0.02 + (1 - traits.adaptive) * 0.10,   // [0.02 .. 0.12]
    halfLifeTurns: 5 + traits.focused * 15,           // [5 .. 20] turns
    capacity: 20 + traits.generative * 80,            // [20 .. 100]
  }
}


/**
 * Array of trait axis names for iteration (C-POLY-1).
 */
export const TRAIT_AXES: (keyof TraitVector)[] = [
  'structural',
  'pragmatic',
  'generative',
  'analytical',
  'collaborative',
  'adaptive',
  'decisive',
  'focused',
]


/**
 * Predefined trait vectors for standard postures.
 *
 * These map the categorical unity/yang/yin system onto the
 * continuous trait space, preserving existing behavior while
 * enabling gradual evolution.
 */
export const UNITY_PRESET: TraitVector = {
  structural: 0.80,     // Well-organized
  pragmatic: 0.85,      // Ship it
  generative: 0.65,     // Moderate creativity
  analytical: 0.75,     // Good rigor
  collaborative: 0.70,  // Balanced dialectic
  adaptive: 0.70,       // Reasonably flexible
  decisive: 0.65,       // Balanced decision-making
  focused: 0.75,        // Good depth
}

export const YANG_PRESET: TraitVector = {
  structural: 0.60,     // Some organization
  pragmatic: 0.90,      // Very pragmatic
  generative: 0.90,     // Highly creative
  analytical: 0.40,     // Less rigorous
  collaborative: 0.80,  // Strong dialectic
  adaptive: 0.85,       // Very flexible
  decisive: 0.90,       // Bold decisions
  focused: 0.55,        // Breadth over depth
}

export const YIN_PRESET: TraitVector = {
  structural: 0.95,     // Very organized
  pragmatic: 0.70,      // Pragmatic but thorough
  generative: 0.40,     // Conservative
  analytical: 0.95,     // Very rigorous
  collaborative: 0.60,  // Autonomous but respectful
  adaptive: 0.50,       // More deliberate
  decisive: 0.50,       // Careful decisions
  focused: 0.95,        // Very deep
}


/**
 * Compute Euclidean distance between two trait vectors.
 *
 * Used for:
 *   - Credibility scoring in GlobalWorkspace (closer = more credible)
 *   - Posture similarity detection
 *   - Trajectory tracking for posture evolution
 *
 * Distance is in [0, sqrt(8)] ≈ [0, 2.83].
 */
export function traitDistance(a: TraitVector, b: TraitVector): number {
  const sq = (x: number) => x * x
  return Math.sqrt(
    sq(a.structural - b.structural) +
    sq(a.pragmatic - b.pragmatic) +
    sq(a.generative - b.generative) +
    sq(a.analytical - b.analytical) +
    sq(a.collaborative - b.collaborative) +
    sq(a.adaptive - b.adaptive) +
    sq(a.decisive - b.decisive) +
    sq(a.focused - b.focused)
  )
}


/** Helix uses three equally capable postures (unity, yang, yin). Mentor deprecated in favor of Brainstem. */
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
   * REMOVED: blackboard and blackboardId deprecated.
   * Session state is now managed via LaminaField + GlobalWorkspace.
   */
  /** @deprecated Use contextSources in brainstemDeps instead */
  blackboard?: any
  /** @deprecated No longer used */
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
  telemetry?: HelixTelemetry
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
  /**
   * Trait vector for polyphonic posture space.
   * When absent, defaults to the preset for the posture name.
   * Enables continuous posture transitions and trait-based credibility.
   */
  traitVector?: TraitVector
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
  metrics?: HelixMetricsSnapshot

  /** Brainstem cognitive organizer result (replaces/supersedes mentor) */
  brainstem?: BrainstemResult

  /** Incremental report built by all postures */
  report?: Report
  /** Blackboard snapshot at completion */
  /** Session state snapshot at completion (replaces deprecated Blackboard) */
  sessionState?: { plan: unknown; report: unknown }
}
