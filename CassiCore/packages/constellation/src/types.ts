/**
 * Constellation Type Definitions
 *
 * A self-organizing, recursively composable multi-agent system where Helix
 * is the atomic organizational unit. A Constellation is a tree of Helix
 * instances that dynamically compose, communicate, and self-organize
 * through three layers of shared Blackboards.
 *
 * Key principles:
 *   - Helix is the atom — any number of FlexPostures running concurrently
 *   - Three-layer Blackboard: local (per-Helix), linked (parent↔child), constellation-wide
 *   - Fully dynamic postures: Unity/Yang/Yin/Mentor are presets, not structure
 *   - Approval-gated recursion: depth ≤ 1 auto-approved, depth > 1 needs parent approval
 *   - Warm sessions: each posture gets a long-lived session ID for Copilot SDK efficiency
 *   - DroneSwarm integration: research requests spawn tool-using drone swarms
 *
 * Named after multiple Helix "stars" forming dynamic patterns — extending
 * the stellar metaphor (Helix = double helix of binary stars).
 */

import type { ConvergencePoint, UnresolvedTension } from '../lumen/dialectic-channel.js'
import type { BlackboardState, Report } from '../../../types/flux-team.js'


// FlexPosture — The atomic unit of agency

/**
 * Tool access levels for postures.
 *
 * - `full`: All tools including write/edit/shell
 * - `read-only`: Only read_file, grep, glob, etc.
 * - `read-only+memory`: Read tools + memory search/store
 * - `none`: No tool access (pure dialectic/communication agent)
 */
export type ToolAccessLevel = 'full' | 'read-only' | 'read-only+memory' | 'none'

/**
 * WorkStream participation mode for a posture.
 *
 * - `producer`: Posts work units (like Unity — the implementer)
 * - `consumer`: Reads work units and sends nudges (like Yang/Yin reviewers)
 * - `both`: Can produce and consume (rare — used for hybrid roles)
 */
export type WorkStreamMode = 'producer' | 'consumer' | 'both'

/**
 * FlexPosture — A fully dynamic, composable agent definition.
 *
 * This replaces the fixed HelixRole ('unity' | 'yang' | 'yin' | 'mentor')
 * with an open-ended posture system. Unity/Yang/Yin/Mentor become presets
 * rather than structural constraints.
 *
 * A posture is just: name + instruction + tool access + channel config.
 * The agent figures out the rest.
 */
export interface FlexPosture {
  /**
   * Unique name within this Helix instance.
   * Examples: 'unity', 'yang', 'researcher-alpha', 'code-reviewer', 'observer-1'
   */
  name: string

  /**
   * Brief instruction describing what this posture does.
   * This is the ONLY behavioral guidance — keep it focused.
   * The system provides infrastructure; the posture decides how to use it.
   */
  instruction: string

  /**
   * Optional energetic direction — inherits base identity from posture-store.
   * When set, the posture gets the corresponding base system prompt
   * (expansive/contractive/unifying) layered under the instruction.
   */
  energy?: 'yang' | 'yin' | 'unity'

  /** Tool access level. */
  toolAccess: ToolAccessLevel

  /** Communication channel participation. */
  channels: {
    /**
     * WorkStream role: how this posture interacts with the work stream.
     * - 'producer': posts work units (implementer role)
     * - 'consumer': reads work units, sends nudges (reviewer role)
     * - 'both': can produce and consume
     * - undefined: no WorkStream participation
     */
    workStream?: WorkStreamMode

    /**
     * Whether this posture participates in the DialecticChannel.
     * Dialectic postures can: share_finding, challenge, concede, signal_conclusion.
     */
    dialectic?: boolean

    /**
     * Whether this posture can read/write the Constellation-wide Blackboard.
     * Default: true if not specified.
     */
    constellationBoard?: boolean
  }

  /**
   * Model routing slot name.
   * Default: `constellation.{helixId}.{posture.name}`
   * Used to route to specific models via the ModelDirective system.
   */
  slotName?: string

  /** Max iterations for this posture's agent loop. Default: 100. */
  maxIterations?: number

  /** Temperature override. Default: 0.7 for yang/unity, 0.35 for yin. */
  temperature?: number

  /** Can this posture spawn new child Helix instances? */
  canSpawnHelix?: boolean

  /** Can this posture spawn drone swarms for research? */
  canSpawnDrones?: boolean

  /**
   * Can this posture read the parent Helix's local Blackboard?
   * Only meaningful for postures in child Helixes.
   */
  canReadParentBoard?: boolean
}


// Helix Configuration

/** Preset template names for quick Helix configuration. */
export type ConstellationTemplate =
  | 'standard'       // Unity + Yang + Yin + Mentor (classic Helix)
  | 'research'       // Unity + Yang + Yin + Mentor + 2 Researchers
  | 'implementation' // 2 Unities + Yang + Yin + Mentor (heavy build)
  | 'review'         // Unity + 2 Yangs + 2 Yins + Mentor (heavy review)
  | 'minimal'        // Unity + single Reviewer (lightweight)

/**
 * Configuration for creating a single Helix node in the Constellation.
 */
export interface ConstellationHelixConfig {
  /** Goal for this Helix — what it should accomplish. */
  goal: string

  /** Additional context or constraints. */
  context?: string

  /**
   * Postures to instantiate.
   * If empty/undefined AND no template specified, uses 'standard' template.
   */
  postures?: FlexPosture[]

  /** Use a preset template instead of custom postures. */
  template?: ConstellationTemplate

  /** Maximum duration for this Helix. Default: 600_000 (10 min). */
  timeoutMs?: number

  /**
   * Working directory override for this Helix.
   * When set (e.g., by worktree isolation), all tool execution uses this
   * directory instead of the main project root.
   */
  workingDir?: string

  /**
   * Tool filter for this Helix.
   * When set, restricts the tools available to this branch beyond the
   * posture-level restrictions.
   */
  toolFilter?: {
    /** Tool names to allow (whitelist). If set, only these tools are available. */
    allow?: string[]
    /** Tool names to deny (blacklist). These tools are removed even if the posture allows them. */
    deny?: string[]
  }

  /**
   * Parent Helix ID.
   * Set automatically by the spawn system — do not set manually.
   */
  parentId?: string

  /**
   * Depth in the Constellation tree.
   * Set automatically: root = 0, children = parent.depth + 1.
   */
  depth?: number
}


// Constellation Node — A Helix in the tree

/** Status of a Helix node. */
export type ConstellationNodeStatus =
  | 'pending'     // Created but not yet started
  | 'running'     // Actively running postures
  | 'completed'   // All postures finished successfully
  | 'degraded'    // Completed but one or more postures errored
  | 'failed'      // A critical posture failed
  | 'cancelled'   // Cancelled by parent or orchestrator

/**
 * Result from a single posture's execution.
 */
export interface ConstellationPostureResult {
  /** Posture name. */
  name: string

  /** Final conclusion/output from this posture. */
  conclusion: string

  /** Confidence score (0–1). */
  confidence: number

  /** Key points from this posture's work. */
  keyPoints: string[]

  /** Number of agent loop iterations completed. */
  iterationCount: number

  /** Number of tool calls made. */
  toolCallCount: number

  /** Total tokens consumed. */
  tokensUsed: number

  /** Duration in milliseconds. */
  durationMs: number

  /** Error message if the posture failed. */
  error?: string
}

/**
 * Represents a single Helix instance within the Constellation tree.
 * Tracks lifecycle, children, and per-posture results.
 */
export interface ConstellationNode {
  /** Unique Helix ID. Format: `constellation:{constellationId}:helix:{index}` */
  helixId: string

  /** The config used to create this node. */
  config: ConstellationHelixConfig

  /** Parent Helix ID (undefined for root). */
  parentId?: string

  /** IDs of child Helix instances spawned by this node. */
  childIds: string[]

  /** Depth in the tree. Root = 0. */
  depth: number

  /** Current status. */
  status: ConstellationNodeStatus

  /** Unix timestamp when this node started. */
  startedAt?: number

  /** Unix timestamp when this node completed. */
  completedAt?: number

  /** Total tokens consumed across all postures in this node. */
  tokensUsed: number

  /** Per-posture results (populated as postures complete). */
  postureResults: Map<string, ConstellationPostureResult>
}


// Session ID Conventions (Warm Sessions)
//
// Warm sessions stay alive based on their session ID. Using the same
// session ID re-enters the same context, preserving conversation
// history for Copilot SDK efficiency.
//
// Convention:
//   Constellation: `constellation:{id}`
//   Helix node:    `constellation:{id}:helix:{index}`
//   Posture:       `constellation:{id}:helix:{index}:{postureName}`
//
// These are stable, reusable, and human-readable.

/** Generate a constellation-level session ID. */
export function constellationSessionId(constellationId: string): string {
  return `constellation:${constellationId}`
}

/** Generate a helix-node-level session ID. */
export function helixSessionId(constellationId: string, helixIndex: number): string {
  return `constellation:${constellationId}:helix:${helixIndex}`
}

/** Generate a posture-level session ID (the warm session for each agent). */
export function postureSessionId(constellationId: string, helixIndex: number, postureName: string): string {
  return `constellation:${constellationId}:helix:${helixIndex}:${postureName}`
}


// Spawn Requests — Approval-gated child creation

/** Status of a spawn request. */
export type SpawnRequestStatus = 'pending' | 'approved' | 'rejected'

/**
 * A request from a posture to spawn a new child Helix.
 *
 * Spawn gate rules:
 *   - depth ≤ 1: auto-approved (budget check only)
 *   - depth > 1: requires approval from parent's Mentor or root orchestrator
 */
export interface SpawnRequest {
  /** Unique request ID. */
  requestId: string

  /** ID of the Helix whose posture is requesting the spawn. */
  requestingHelixId: string

  /** Name of the posture making the request. */
  requestingPosture: string

  /**
   * Depth at which the child would be created.
   * This is the requesting Helix's depth + 1.
   */
  targetDepth: number

  /** Goal for the child Helix. */
  goal: string

  /** Additional context for the child. */
  context?: string

  /** Custom postures for the child (overrides template). */
  postures?: FlexPosture[]

  /** Preset template for the child (used if postures not specified). */
  template?: ConstellationTemplate

  /** Current status of this request. */
  status: SpawnRequestStatus

  /** Who approved/rejected (posture name or 'auto'). */
  decidedBy?: string

  /** Reason for rejection (if rejected). */
  rejectionReason?: string

  /** Unix timestamp of the request. */
  timestamp: number

  /** Unix timestamp of the decision. */
  decidedAt?: number
}


// Constellation Result — Overall output

/**
 * The result of a complete Constellation execution.
 */
export interface ConstellationResult {
  /** ID of the Constellation. */
  constellationId: string

  /** The root Helix's ID. */
  rootHelixId: string

  /** All Helix nodes in the tree, keyed by helixId. */
  nodes: Map<string, ConstellationNode>

  /** Snapshot of the Constellation-wide Blackboard. */
  constellationBlackboard: BlackboardState

  /** Total tokens consumed across all nodes and postures. */
  totalTokensUsed: number

  /** Total duration of the Constellation run (wall clock). */
  totalDurationMs: number

  /** Final synthesis/recommendation from the root Helix's Mentor. */
  synthesis?: string

  /** Mentor's recommendation (proceed/stop/revise). */
  recommendation?: string

  /** Mentor's confidence in the overall result. */
  confidence?: number

  /** Root Helix's report. */
  report?: Report

  /** Root Helix's Blackboard snapshot. */
  rootBlackboard?: BlackboardState

  /** Dialectic stats from the root Helix. */
  dialecticStats?: {
    findings: number
    challenges: number
    concessions: number
    convergencePoints: number
    unresolvedChallenges: number
  }

  /** All spawn requests made during execution. */
  spawnRequests: SpawnRequest[]

  /** Corpus result — cross-Helix reasoning tree and strategic analysis. */
  corpus?: import('./corpus-types.js').CorpusResult

  /** Decomposition tracker snapshot — task lifecycle and accuracy tracking. */
  decompositionTracker?: import('./decomposition-tracker.js').DecompositionSnapshot

  /** Error message if the Constellation failed. */
  error?: string
}


// Constellation Project Options — Entry point

/**
 * Options for starting a Constellation run.
 * This is the public-facing API — what the user/tool caller provides.
 */
export interface ConstellationProjectOpts {
  /** The overall goal for the Constellation. */
  goal: string

  /** Additional context or constraints. */
  context?: string

  /**
   * Parent session ID for Phase Zero context distillation.
   * When provided, the root Helix is briefed with context from the parent conversation.
   */
  parentSessionId?: string

  /**
   * Custom postures for the root Helix.
   * If not provided, uses `template` (default: 'standard').
   */
  postures?: FlexPosture[]

  /** Preset template for the root Helix. Default: 'standard'. */
  template?: ConstellationTemplate

  /** Maximum Helix depth allowed. Default: 4. */
  maxDepth?: number

  /** Maximum total Helix nodes allowed. Default: 16. */
  maxNodes?: number

  /** Overall timeout for the Constellation. Default: 1_200_000 (20 min). */
  timeoutMs?: number

  /** Per-Helix timeout. Default: 600_000 (10 min). */
  helixTimeoutMs?: number

  /** Optional session ID. Default: auto-generated. */
  sessionId?: string

  /** Optional job ID for tracking. */
  jobId?: string
}


// Blackboard Bridge Configuration

/**
 * Configuration for a BlackboardBridge linking a parent and child Helix.
 *
 * Bridges auto-forward:
 *   - Child findings → Parent findings (tagged [child:{childId}])
 *   - Child concerns (priority ≥ high) → Parent concerns (escalation)
 *   - Parent decisions (tagged for:{childId}) → Child requests
 *   - Child completion → Parent findings (final report)
 */
export interface BlackboardBridgeConfig {
  /** Parent Helix ID. */
  parentHelixId: string

  /** Child Helix ID. */
  childHelixId: string

  /** Whether to forward ALL child findings or only high-priority ones. Default: true (all). */
  forwardAllFindings?: boolean

  /** Minimum priority for concern escalation. Default: 'high'. */
  escalationPriority?: 'low' | 'medium' | 'high'
}


// Event Types — For the EventBus

/** Events emitted by the Constellation system. */
export type ConstellationEventType =
  | 'constellation:started'
  | 'constellation:completed'
  | 'constellation:failed'
  | 'constellation:helix:started'
  | 'constellation:helix:completed'
  | 'constellation:helix:failed'
  | 'constellation:posture:started'
  | 'constellation:posture:completed'
  | 'constellation:posture:failed'
  | 'constellation:spawn:requested'
  | 'constellation:spawn:approved'
  | 'constellation:spawn:rejected'
  | 'constellation:bridge:created'
  | 'constellation:drone:dispatched'
  | 'constellation:drone:completed'
