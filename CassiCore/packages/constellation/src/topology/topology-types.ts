/**
 * Topology Graph Types — Spatial Coordination Layer for Helix Sessions
 *
 * Helix sessions occupy positions in a 2D space. Gravity-based forces
 * (driven by LLM embedding similarity) pull similar sessions together.
 * When sessions are close enough, they link — sharing Brainstem context
 * at progressively deeper levels.
 *
 * Design decisions:
 *   - Embedding source: LLM embeddings (semantic goal/findings vectors)
 *   - Update frequency: On digest update (event-driven, not polling)
 *   - Brainstem merge: Progressive (shallow digest sharing → deep tool context)
 *   - Repulsion: Passive drift (dissimilar sessions don't attract, no active push)
 *   - Cluster lifecycle: Reversible with hysteresis (links dissolve if similarity drops)
 *   - Visualization: Corpus-only (no TUI rendering initially)
 */

import type { BranchDigest, BranchApproach } from '../corpus-types.js'

// Position & Velocity

/**
 * 2D position of a Helix session in the topology space.
 *
 * HOW: Initial placement is derived from the goal embedding projected to 2D.
 * Subsequent updates apply gravity forces each tick (on digest update).
 * Coordinates are unitless — only relative distances matter.
 */
export interface HelixPosition {
  helixId: string
  x: number
  y: number
  /** Velocity components — momentum from previous ticks */
  vx: number
  vy: number
}

/**
 * Snapshot of a Helix's state relevant to gravity calculations.
 * Built from BranchDigest data + embeddings.
 */
export interface HelixTopologyState {
  helixId: string
  position: HelixPosition
  /** Goal embedding vector (from LLM embedding service) */
  goalEmbedding: number[] | null
  /** Findings embedding vector (from LLM embedding of key findings) */
  findingsEmbedding: number[] | null
  /** Active files — used for Jaccard overlap calculation */
  filesActive: string[]
  /** Current approach — same-approach pairs get bonus attraction */
  approach: BranchApproach
  /** Whether this Helix is still active */
  active: boolean
  /** Last time this state was updated */
  updatedAt: number
}


// Gravity Configuration

/**
 * Weights for the gravity force components.
 * Each source contributes to the total attractive force between two Helixes.
 * All weights should sum to approximately 1.0 for normalized force output.
 */
export interface GravityWeights {
  /** Weight for goal embedding cosine similarity */
  goalSimilarity: number
  /** Weight for findings embedding cosine similarity */
  findingsSimilarity: number
  /** Weight for Jaccard file overlap */
  fileOverlap: number
  /** Bonus weight when both Helixes share the same BranchApproach */
  approachAlignment: number
}

/**
 * Full gravity engine configuration.
 */
export interface GravityConfig {
  /** Force component weights */
  weights: GravityWeights
  /**
   * Friction coefficient (0-1). Applied to velocity each tick to prevent
   * unbounded acceleration. 0 = no friction (dangerous), 1 = full stop each tick.
   * Recommended: 0.3-0.5
   */
  friction: number
  /**
   * Force multiplier. Scales the raw similarity-based force before applying
   * to velocity. Higher = faster convergence, less stability.
   */
  forceScale: number
  /**
   * Minimum distance to prevent division-by-zero in force calculations.
   * Also prevents positions from collapsing to the same point.
   */
  minDistance: number
  /**
   * Maximum velocity magnitude per tick. Prevents wild position jumps.
   */
  maxVelocity: number
  /**
   * Repulsion strength. Applies an inverse-square repulsive force between
   * all pairs to prevent spatial collapse. Without this, attraction-only
   * physics causes all nodes to converge into a single clump regardless
   * of semantic distance.
   *
   * HOW: Net force = attraction(similarity/dist) - repulsion(strength/dist^2).
   * High-similarity pairs settle close (attraction > repulsion).
   * Low-similarity pairs settle far apart (repulsion > attraction).
   * Recommended: 0.1-0.3
   */
  repulsionStrength: number
}


// Links

/**
 * A link between two Helix sessions in the topology.
 *
 * Links form when sessions are close enough (below linkThreshold) and
 * dissolve when they drift apart (above unlinkThreshold, with hysteresis).
 *
 * HOW: Linked sessions share Brainstem context. The merge depth starts
 * shallow (digest sharing) and deepens as the link stabilizes.
 */
export interface TopologyLink {
  /** First Helix in the link (alphabetically ordered for uniqueness) */
  helixIdA: string
  /** Second Helix in the link */
  helixIdB: string
  /** Current distance between the two positions */
  distance: number
  /** Composite similarity score that created this link */
  similarity: number
  /** When this link was first established */
  createdAt: number
  /** Current merge depth level */
  mergeDepth: MergeDepth
  /** Number of consecutive ticks this link has been stable (below link threshold) */
  stabilityTicks: number
}

/**
 * Merge depth levels for linked Helix sessions.
 *
 * Progressive merge: starts shallow, deepens with stability.
 *   - shallow: Linked sessions see each other's digests in real-time
 *   - medium: Shared tool context (file locks, cache)
 *   - deep: Joint planning and coordinated execution
 */
export type MergeDepth = 'shallow' | 'medium' | 'deep'


// Link Configuration

/**
 * Configuration for link formation and dissolution.
 */
export interface LinkConfig {
  /**
   * Distance threshold for forming a new link.
   * When distance drops below this, a link is created.
   */
  linkThreshold: number
  /**
   * Distance threshold for dissolving an existing link.
   * Must be > linkThreshold to create hysteresis band.
   * When distance rises above this, the link is dissolved.
   */
  unlinkThreshold: number
  /**
   * Minimum composite similarity (0-1) required to form a new link.
   * Prevents linking spatially close but semantically unrelated nodes.
   * Set to 0 to disable (distance-only linking).
   * Recommended: 0.4-0.6
   */
  minLinkSimilarity: number
  /**
   * Number of stable ticks before promoting from shallow to medium merge.
   */
  mediumMergeStabilityTicks: number
  /**
   * Number of stable ticks before promoting from medium to deep merge.
   */
  deepMergeStabilityTicks: number
}


// Clusters

/**
 * A cluster of linked Helix sessions.
 *
 * Clusters are transitive: if A links to B and B links to C,
 * then {A, B, C} form a single cluster. Clusters share a unified
 * Brainstem view at the depth of their weakest link.
 */
export interface TopologyCluster {
  /** Stable cluster ID (persists across ticks if membership doesn't change) */
  clusterId: string
  /** Helix IDs in this cluster */
  members: string[]
  /** Links that form this cluster */
  links: TopologyLink[]
  /** Effective merge depth — minimum across all links in the cluster */
  effectiveMergeDepth: MergeDepth
  /** Average internal distance (lower = tighter cluster) */
  averageInternalDistance: number
  /** Stability score (0-1): fraction of ticks this cluster has existed unchanged */
  stabilityScore: number
  /** When this cluster first formed (with current membership) */
  formedAt: number
  /** Number of ticks this cluster has existed with current membership */
  ticksStable: number
}


// TopologyGraph Configuration

/**
 * Full configuration for the TopologyGraph module.
 */
export interface TopologyGraphConfig {
  /** Gravity engine settings */
  gravity: GravityConfig
  /** Link formation/dissolution settings */
  links: LinkConfig
  /** Whether the topology graph is enabled */
  enabled: boolean
}


// Snapshot for Corpus consumption

/**
 * Complete topology state snapshot, consumed by the Corpus reasoning loop.
 * The Corpus reads this as an additional signal alongside BranchAssessments
 * and CrossHelixPatterns.
 */
export interface TopologySnapshot {
  /** All Helix positions */
  positions: HelixPosition[]
  /** All active links */
  links: TopologyLink[]
  /** All detected clusters */
  clusters: TopologyCluster[]
  /** Pairwise distance matrix (helixId → helixId → distance) */
  distances: Map<string, Map<string, number>>
  /** Number of topology ticks processed */
  tickCount: number
  /** When this snapshot was taken */
  snapshotAt: number
}


// Defaults

export const DEFAULT_GRAVITY_WEIGHTS: GravityWeights = {
  goalSimilarity: 0.4,
  findingsSimilarity: 0.3,
  fileOverlap: 0.2,
  approachAlignment: 0.1,
}

export const DEFAULT_GRAVITY_CONFIG: GravityConfig = {
  weights: DEFAULT_GRAVITY_WEIGHTS,
  friction: 0.4,
  forceScale: 0.5,
  minDistance: 0.01,
  maxVelocity: 2.0,
  repulsionStrength: 0.15,
}

export const DEFAULT_LINK_CONFIG: LinkConfig = {
  linkThreshold: 1.5,
  unlinkThreshold: 2.5,
  minLinkSimilarity: 0.45,
  mediumMergeStabilityTicks: 5,
  deepMergeStabilityTicks: 15,
}

export const DEFAULT_TOPOLOGY_CONFIG: TopologyGraphConfig = {
  gravity: DEFAULT_GRAVITY_CONFIG,
  links: DEFAULT_LINK_CONFIG,
  enabled: true,
}
