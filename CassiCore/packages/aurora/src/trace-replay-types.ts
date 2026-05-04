/**
 * Trace Replay Types (B3) — Reasoning trace similarity and quality scoring.
 *
 * B3 turns Aurora's reasoning log from audit-only into a generative resource:
 * past productive reasoning traces can be retrieved by similarity and used to
 * warm-start new tasks. This file defines the types for similarity scoring,
 * quality assessment, and replay configuration.
 *
 * See: docs/design/aurora-reasoning-trace-replay.md
 */

import type { ReasoningRecord, ReasoningShift } from './types.js'



/**
 * Weights for the composite similarity function.
 * Each axis contributes to the final similarity score (0..1).
 */
export interface SimilarityWeights {
  /** Jaccard overlap of extracted concepts. Default: 0.4 */
  conceptOverlap: number
  /** Text embedding distance (cosine). Default: 0.3 — falls back to trigram overlap when no embeddings */
  textSimilarity: number
  /** Euclidean proximity in (valence, arousal) space. Default: 0.15 */
  affectProximity: number
  /** Overlap of active composition labels. Default: 0.15 */
  compositionOverlap: number
}

export const DEFAULT_SIMILARITY_WEIGHTS: SimilarityWeights = {
  conceptOverlap: 0.4,
  textSimilarity: 0.3,
  affectProximity: 0.15,
  compositionOverlap: 0.15,
}



/**
 * Post-hoc quality assessment of a reasoning trace.
 * Quality is independent of similarity — it measures how well the thinking *went*.
 */
export interface TraceQuality {
  /** coherence + integration + (1 − thrash). Range 0..1 */
  internal: number
  /** Did affect end in a better state than it started? Range 0..1 */
  affectTrajectory: number
  /** External corrective signal heuristic. Range 0..1, default 0.5 (neutral) */
  externalFeedback: number
  /** Weighted composite. Range 0..1 */
  composite: number
  /** When this quality was computed. Null = not yet scored. */
  computedAt: string | null
}

/**
 * Weights for the composite quality score.
 */
export interface QualityWeights {
  internal: number
  affectTrajectory: number
  externalFeedback: number
}

export const DEFAULT_QUALITY_WEIGHTS: QualityWeights = {
  internal: 0.5,
  affectTrajectory: 0.3,
  externalFeedback: 0.2,
}



/**
 * The current turn context, used to find similar past traces.
 */
export interface TraceQueryContext {
  /** Current reasoning text (or excerpt). */
  text: string
  /** Concepts extracted from current reasoning. */
  conceptsExtracted: string[]
  /** Current affect (valence, arousal). */
  affect: { valence: number; arousal: number } | null
  /** Currently active compositions (empty if B1 not landed). */
  activeCompositions: string[]
}

/**
 * Query for retrieving similar traces.
 */
export interface TraceRetrievalQuery {
  /** The current turn context to match against. */
  current: TraceQueryContext
  /** Override default similarity weights. */
  weights?: Partial<SimilarityWeights>
  /** How many results to return. Default: 5 */
  topK: number
  /** Minimum quality score for returned traces. Default: 0 (no floor) */
  qualityFloor?: number
  /** Only consider records observed within this many ms. Default: all. */
  windowMs?: number
}

/**
 * A ranked trace returned from retrieval.
 */
export interface RankedTrace {
  /** The original reasoning record. */
  record: ReasoningRecord
  /** Composite similarity score (0..1). */
  similarity: number
  /** Per-axis similarity breakdown. */
  signalBreakdown: {
    conceptOverlap: number
    textSimilarity: number
    affectProximity: number
    compositionOverlap: number
  }
  /** Quality score (null = not yet scored, treated as 0.5). */
  quality: TraceQuality | null
}



/**
 * Mode A: render the trace as context in the next projection.
 */
export interface ContextReplayOptions {
  /** Max characters for the replay section in projection. Default: 600 */
  budgetChars?: number
  /** Which sections to include. Default: all. */
  sections?: Array<'summary' | 'trajectory' | 'concepts' | 'composition'>
}

/**
 * Mode B: pre-warm system state from a prior trace.
 * Manual-only — never auto-triggered (B3.W2).
 */
export interface StateReplayOptions {
  /** Reactivate the trace's activated nodes in claustrum. Default: true */
  reactivateNodes?: boolean
  /** Apply affect bias toward the trace's productive-phase affect. Default: true */
  applyAffectBias?: boolean
  /** Invoke the composition active during the trace's productive phase. Default: false */
  invokeComposition?: boolean
  /** How many turns the pre-warming effect lasts. Default: 3 */
  ttlTurns?: number
}

/**
 * A scheduled replay (pending for next turn).
 */
export interface ScheduledReplay {
  trace: RankedTrace
  mode: 'context' | 'state'
  options: ContextReplayOptions | StateReplayOptions
}



export interface TraceReplayConfig {
  /** Enable trace replay retrieval. Default: true */
  enabled: boolean
  /** Enable auto context replay when similarity > threshold. Default: false */
  autoReplayEnabled: boolean
  /** Minimum similarity to trigger auto-replay. Default: 0.6 */
  autoReplaySimilarityThreshold: number
  /** Minimum quality to trigger auto-replay. Default: 0.7 */
  autoReplayQualityThreshold: number
  /** How often (in turns) to run background quality scoring. Default: 10 */
  qualityScoringInterval: number
  /** Minimum age in turns before a record gets quality-scored. Default: 5 */
  qualityScoringMinAge: number
  /** Hard-filter: records with valence < this AND arousal > 0.7 are ineligible. Default: -0.5 */
  distressValenceFloor: number
  /** Default similarity weights (can be overridden per query). */
  similarityWeights: SimilarityWeights
  /** Default quality weights. */
  qualityWeights: QualityWeights
}

export const DEFAULT_TRACE_REPLAY_CONFIG: TraceReplayConfig = {
  enabled: true,
  autoReplayEnabled: false,
  autoReplaySimilarityThreshold: 0.6,
  autoReplayQualityThreshold: 0.7,
  qualityScoringInterval: 10,
  qualityScoringMinAge: 5,
  distressValenceFloor: -0.5,
  similarityWeights: DEFAULT_SIMILARITY_WEIGHTS,
  qualityWeights: DEFAULT_QUALITY_WEIGHTS,
}
