/**
 * Locus Types — Global Workspace Layer for Constellation
 *
 * The Locus is the Constellation's capacity-limited attentional workspace,
 * inspired by Global Workspace Theory (GWT). It implements the transition
 * from "unconscious" local branch processing to "conscious" global awareness.
 *
 * Naming philosophy (two layers):
 *   Structural layer (brain anatomy): Locus, Focus/Foci
 *   Emergent layer (energy, fire, light): Spark, Kindle, Radiance, Luminance
 *
 * The GWT cycle: Spark → Kindle → Radiate
 *   1. Branches produce Sparks (proposals for workspace access)
 *   2. Sparks are scored by Luminance (composite salience)
 *   3. High-luminance sparks Kindle — they become Foci in the Locus
 *   4. Kindled content Radiates to all branches (global broadcast)
 *   5. Dim sparks stay local to their branch (unconscious processing)
 *
 * Named after the locus coeruleus — the brainstem nucleus that modulates
 * attention and arousal across the entire cortex.
 */

import type { BranchDigest, CrossHelixPattern, BranchAssessment } from '../corpus-types.js'
import type { LocusMemoryStats } from './memory-types.js'


// Sparks — Proposals from branches competing for workspace access

/**
 * What kind of content a Spark carries.
 * Determines base urgency weighting in luminance scoring.
 */
export type SparkType =
  | 'discovery'      // Novel finding from a branch
  | 'blocker'        // Something blocking progress
  | 'decision'       // A strategic decision with cross-branch implications
  | 'tension'        // A conflict or contradiction between branches
  | 'convergence'    // Multiple branches arriving at the same conclusion
  | 'breakthrough'   // Significant quality-score jump in a branch

/**
 * A Spark is a proposal from a Helix branch competing for Locus access.
 * Before the kindling threshold, it's just a spark — local, unconscious.
 */
export interface Spark {
  sparkId: string
  /** Which branch produced this spark */
  sourceHelixId: string
  /** The content being proposed for global awareness */
  content: string
  /** What kind of content this is */
  type: SparkType
  /** Composite salience score determining competition outcome */
  luminance: LuminanceScore
  /** When this spark was generated */
  sparkedAt: number
  /** Source branch state at spark time (for context) */
  sourceGoal: string
  /** Files relevant to this spark */
  relevantFiles: string[]
}


// Luminance — Composite salience score

/**
 * Luminance is how "bright" a spark is — how strongly it competes
 * for workspace access. Higher luminance = more likely to kindle.
 *
 * The components mirror the phenomenological model:
 *   - novelty: how surprising/new (expanding awareness)
 *   - urgency: how time-sensitive (compressive focus)
 *   - crossRelevance: how many branches benefit (spatial/topology signal)
 *   - qualityDelta: branch trajectory (emotional valence)
 */
export interface LuminanceScore {
  /** 0-1: How new or surprising is this content? */
  novelty: number
  /** 0-1: How time-sensitive? Blockers score high, routine findings low */
  urgency: number
  /** 0-1: How many other branches would benefit? Uses topology distances */
  crossRelevance: number
  /** -1 to 1: Branch quality trajectory at spark time (rising = positive) */
  qualityDelta: number
  /** Weighted combination — the actual competition score */
  composite: number
}

/**
 * Weights for luminance component scoring.
 */
export interface LuminanceWeights {
  novelty: number
  urgency: number
  crossRelevance: number
  qualityDelta: number
}


// Foci — Workspace slots

/**
 * A Focus is a single slot in the Locus workspace.
 * The Locus has a fixed number of Foci (capacity limit).
 * Each Focus either holds a kindled Spark or is empty.
 */
export interface Focus {
  /** Slot index (0 to foci-1) */
  slotIndex: number
  /** The Spark currently occupying this focus, or null if empty */
  spark: Spark | null
  /** When this focus was last occupied */
  occupiedSince: number | null
  /** How many sweeps this focus has held the same content */
  occupancyTicks: number
  /** The sparkId that was eclipsed (displaced) when this focus was last filled */
  eclipsedSparkId?: string
}


// Kindling Events — When a spark crosses threshold

/**
 * A KindlingEvent records a spark entering the Locus workspace.
 * This is the GWT "ignition" — the transition from unconscious to conscious.
 */
export interface KindlingEvent {
  eventId: string
  /** The spark that kindled */
  spark: Spark
  /** Which focus slot it entered */
  slotIndex: number
  /** Whether this spark displaced an existing occupant */
  eclipse: EclipseEvent | null
  /** The luminance score at kindling time */
  kindlingLuminance: number
  timestamp: number
}

/**
 * An EclipseEvent records when a new focus displaces an existing one.
 * The new spark's light eclipses the old one's.
 */
export interface EclipseEvent {
  /** The spark that was displaced */
  eclipsedSpark: Spark
  /** The spark that displaced it */
  eclipsingSpark: Spark
  /** Luminance differential (positive = eclipser was brighter) */
  luminanceDelta: number
  /** How many sweeps the eclipsed spark had been in the focus */
  occupancyAtEclipse: number
}


// Radiance — Global broadcast events

/**
 * A RadianceEvent records kindled content being broadcast to all branches.
 * This is GWT's "global broadcast" — workspace content radiating outward.
 */
export interface RadianceEvent {
  radianceId: string
  /** The kindling event that triggered this broadcast */
  source: KindlingEvent
  /** Formatted content that was broadcast */
  content: string
  /** All Helix IDs that received the broadcast */
  recipients: string[]
  /** Topology distances from source to each recipient (for training data) */
  recipientDistances: Record<string, number>
  timestamp: number
}

/**
 * How a branch responded to a radiance broadcast.
 * Tracked over subsequent sweeps to measure broadcast effectiveness.
 */
export interface RadianceResponse {
  /** Which branch responded */
  helixId: string
  /** The radiance event being responded to */
  radianceId: string
  /** What the branch did with the broadcast */
  responseType: RadianceResponseType
  /** Evidence: what changed in the branch after the broadcast */
  evidence: string
  /** Sweeps between broadcast and detected response */
  responseDelay: number
  timestamp: number
}

/**
 * How a branch responded to a broadcast.
 *   incorporated: Branch changed behavior or findings based on broadcast
 *   noted: Branch acknowledged but didn't change behavior
 *   ignored: No detectable response
 *   contradicted: Branch produced findings that contradict the broadcast
 */
export type RadianceResponseType =
  | 'incorporated'
  | 'noted'
  | 'ignored'
  | 'contradicted'


// Locus Snapshot — Full state for Corpus consumption and training data

/**
 * Complete Locus state snapshot, consumed by the Corpus and training pipeline.
 */
export interface LocusSnapshot {
  /** Current state of all foci */
  foci: Focus[]
  /** Recent kindling events (last N) */
  recentKindlings: KindlingEvent[]
  /** Recent radiance events (last N) */
  recentRadiances: RadianceEvent[]
  /** Recent responses to radiance events */
  recentResponses: RadianceResponse[]
  /** Total sparks processed across the Locus lifetime */
  totalSparksProcessed: number
  /** Total kindling events (sparks that made it into the workspace) */
  totalKindlings: number
  /** Total radiance events (broadcasts sent) */
  totalRadiances: number
  /** Kindling rate: kindlings / total sparks (selectivity measure) */
  kindlingRate: number
  /** Memory stats: accumulated experiential learning across constellations */
  memory?: LocusMemoryStats
  /** When this snapshot was taken */
  snapshotAt: number
}


// Configuration

/**
 * Full configuration for the Locus module.
 */
export interface LocusConfig {
  /** Number of focus slots (workspace capacity). Default: 5 */
  foci: number
  /**
   * Minimum luminance score for a spark to compete for a focus.
   * Below this threshold, the spark stays "dim" — unconscious, local.
   * Default: 0.3
   */
  kindlingThreshold: number
  /**
   * Maximum sweeps a focus occupant persists before natural decay.
   * Occupants that exceed this lose effective luminance, making them
   * easier to eclipse. Default: 10
   */
  maxOccupancyTicks: number
  /**
   * Hysteresis margin for eclipse. A new spark must exceed the
   * weakest occupant by at least this margin to displace it.
   * Prevents oscillation between similar-luminance sparks.
   * Default: 0.05
   */
  eclipseMargin: number
  /** Luminance component weights */
  luminanceWeights: LuminanceWeights
  /** Whether the Locus is enabled. Default: true */
  enabled: boolean
  /** Maximum events to keep in history (for snapshots/training). Default: 100 */
  maxEventHistory: number
}

export const DEFAULT_LUMINANCE_WEIGHTS: LuminanceWeights = {
  novelty: 0.3,
  urgency: 0.25,
  crossRelevance: 0.25,
  qualityDelta: 0.2,
}

export const DEFAULT_LOCUS_CONFIG: LocusConfig = {
  foci: 5,
  kindlingThreshold: 0.3,
  maxOccupancyTicks: 10,
  eclipseMargin: 0.05,
  luminanceWeights: DEFAULT_LUMINANCE_WEIGHTS,
  enabled: true,
  maxEventHistory: 100,
}


// Dependency interfaces

/**
 * Topology accessor for cross-relevance scoring.
 * The Locus reads topology distances to determine how many branches
 * would benefit from a spark's content.
 */
export interface LocusTopologyAccessor {
  /** Get distance between two Helixes (lower = more related) */
  getDistance(helixIdA: string, helixIdB: string): number
  /** Get similarity between two Helixes (0-1, higher = more similar) */
  getSimilarity(helixIdA: string, helixIdB: string): number
}

/**
 * Guidance injection function — how the Locus delivers broadcasts.
 * Same signature as the Corpus's existing injectGuidance mechanism.
 */
export type GuidanceInjector = (
  helixId: string,
  content: string,
  urgency: 'low' | 'medium' | 'high' | 'critical',
) => void
