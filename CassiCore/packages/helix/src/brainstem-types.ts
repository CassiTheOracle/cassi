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
import type { CorpusDirective } from '../constellation/corpus-types.js'

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
  /** Consecutive off-goal iterations before detecting drift. Default: 4 */
  driftThreshold: number
  /** Whether to post annotations to blackboard. Default: true */
  postToBlackboard: boolean
  /** Whether to persist to training warehouse on completion. Default: true */
  persistTrainingData: boolean
  /** Whether Brainstem is enabled. Default: true */
  enabled: boolean
}

export const DEFAULT_BRAINSTEM_CONFIG: BrainstemConfig = {
  modelTier: 'balanced',
  maxTokens: 400,
  timeoutMs: 8_000,
  idlePollMs: 10_000,
  guidanceCooldownIterations: 2,
  paralysisThreshold: 3,
  driftThreshold: 4,
  postToBlackboard: true,
  persistTrainingData: true,
  enabled: true,
}

// ─── Annotation Types ─────────────────────────────────────────────────────

/** Work unit classification produced by Brainstem scoring */
export type WorkUnitAnnotation =
  | 'exploration'     // reading, searching, gathering context
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
  /** Quality score (0-1) with reasoning */
  score: number
  /** Work unit classification */
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
}

// ─── State ────────────────────────────────────────────────────────────────

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
  }
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
}

/**
 * Minimal blackboard interface for Brainstem posting.
 * Avoids importing the full Blackboard class — any object with a
 * compatible `post()` method satisfies this contract.
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
