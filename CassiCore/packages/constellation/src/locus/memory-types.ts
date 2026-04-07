/**
 * Locus Memory Types — Persistent experiential learning across Constellations
 *
 * The Locus Memory is the persistence layer of the GWT attention cycle.
 * Three integration points form a feedback loop:
 *
 *   1. Write gate:   When a spark kindles, a provisional memory is created
 *   2. Luminance:    When scoring sparks, existing memories modulate novelty
 *   3. Radiance:     When branches respond to broadcasts, memory confidence updates
 *
 * Where all three overlap — a spark that kindles, gets incorporated by branches,
 * AND relates to existing memory — that's the highest-confidence knowledge.
 *
 * Memories persist across constellation sessions. Each constellation contributes
 * to shared accumulated experience, like a developer who "just knows" things
 * about a codebase after working in it long enough.
 */

import type { SparkType } from './locus-types.js'


/**
 * A single memory entry in the Locus Memory store.
 *
 * Lifecycle:  provisional → confirmed → consolidated  (or → invalidated)
 *   provisional:  freshly written from a kindling event
 *   confirmed:    at least one branch incorporation has boosted confidence
 *   consolidated: survived a full constellation run with positive confidence
 *   invalidated:  contradictions drove confidence below threshold
 */
export interface LocusMemoryEntry {
  id: string
  /** The actual remembered content (from the kindled spark) */
  content: string
  /** What kind of content this memory carries (mirrors SparkType) */
  memoryType: SparkType
  /** Current confidence level (0-1). Updated by radiance responses. */
  confidence: number
  /** Original luminance score when this memory was created */
  luminance: number
  /** Current lifecycle phase */
  phase: MemoryPhase
  /** Which constellation session created this memory */
  originSessionId: string
  /** Which Helix branch produced the original spark */
  sourceHelixId: string
  /** Goal of the source branch at memory creation time */
  sourceGoal: string
  /** Files that were relevant when the memory was created */
  relevantFiles: string[]
  /** Number of times branches incorporated related broadcasts */
  confirmations: number
  /** Number of times branches contradicted related broadcasts */
  contradictions: number
  /** Total times this memory modulated a luminance score */
  recallCount: number
  /** When this memory was created */
  createdAt: number
  /** Last time this memory was recalled for luminance scoring */
  lastRecalledAt: number | null
  /** Last time confidence was updated (by radiance response) */
  lastUpdatedAt: number
}

export type MemoryPhase =
  | 'provisional'
  | 'confirmed'
  | 'consolidated'
  | 'invalidated'


/**
 * How a radiance response should update memory.
 */
export interface MemoryFeedback {
  memoryId: string
  radianceId: string
  helixId: string
  feedbackType: MemoryFeedbackType
  evidence: string
  timestamp: number
}

export type MemoryFeedbackType =
  | 'confirmation'     // Branch incorporated — boost confidence
  | 'contradiction'    // Branch contradicted — reduce confidence
  | 'neutral'          // Branch noted/ignored — slight decay


/**
 * Result of a memory recall during luminance scoring.
 * Tells the KindlingEngine how to modulate the spark's novelty.
 */
export interface MemoryRecall {
  /** The memory that was recalled */
  memory: LocusMemoryEntry
  /** How strongly this memory relates to the spark (0-1) */
  relevance: number
  /** Novelty modulation: negative = reduces novelty (memory confirms),
   *  positive = boosts novelty (memory contradicts, creating tension) */
  noveltyModulation: number
}


/**
 * Configuration for memory behavior.
 */
export interface LocusMemoryConfig {
  /** Whether memory is enabled. Default: true */
  enabled: boolean
  /** Maximum memories to keep (oldest invalidated pruned first). Default: 500 */
  maxMemories: number
  /** Confidence below which memories are invalidated. Default: 0.15 */
  invalidationThreshold: number
  /** Confidence boost per branch incorporation. Default: 0.08 */
  confirmationBoost: number
  /** Confidence penalty per branch contradiction. Default: 0.15 */
  contradictionPenalty: number
  /** Confidence decay per sweep when not recalled. Default: 0.002 */
  idleDecay: number
  /** Minimum content similarity (0-1) for matching. Default: 0.3 */
  matchThreshold: number
  /** Maximum memories to recall per spark during scoring. Default: 3 */
  maxRecallsPerSpark: number
  /** Novelty reduction when a confirming memory is found. Default: 0.2 */
  confirmingNoveltyReduction: number
  /** Novelty boost when a contradicting memory is found. Default: 0.15 */
  contradictingNoveltyBoost: number
}

export const DEFAULT_MEMORY_CONFIG: LocusMemoryConfig = {
  enabled: true,
  maxMemories: 500,
  invalidationThreshold: 0.15,
  confirmationBoost: 0.08,
  contradictionPenalty: 0.15,
  idleDecay: 0.002,
  matchThreshold: 0.3,
  maxRecallsPerSpark: 3,
  confirmingNoveltyReduction: 0.2,
  contradictingNoveltyBoost: 0.15,
}


/**
 * Stats for memory snapshot / training data export.
 */
export interface LocusMemoryStats {
  totalMemories: number
  byPhase: Record<MemoryPhase, number>
  byType: Record<string, number>
  avgConfidence: number
  totalRecalls: number
  totalConfirmations: number
  totalContradictions: number
}
