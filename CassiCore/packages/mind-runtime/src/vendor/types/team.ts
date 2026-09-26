/**
 * Team System Types — Autonomous multi-agent team coordination.
 *
 * Defines the recursive goal tree, team sessions, budgets, and configuration
 * for CassiCore's autonomous team architecture. Teams are hierarchical:
 * a coordinator decomposes goals into sub-tasks, spawns specialist agents,
 * and can recursively spawn sub-coordinators for complex sub-goals.
 *
 * Key types:
 * - GoalNode: recursive tree node representing a goal or sub-goal
 * - TeamSession: tracks an entire team's lifecycle
 * - TeamBudget: shared resource limits across the tree
 * - TeamConfig: configuration for team behavior
 */

// Team types - no external type imports needed


export type GoalStatus =
  | 'pending'       // Not yet started
  | 'in_progress'   // Being worked on
  | 'completed'     // Successfully finished
  | 'failed'        // Failed (with error)
  | 'blocked'       // Waiting on dependency or human input
  | 'cancelled'     // Cancelled by coordinator or supervisor

export interface GoalResult {
  /** Summary of what was accomplished */
  summary: string
  /** Detailed output/artifacts if any */
  output?: string
  /** Token cost for this specific goal */
  tokensUsed: number
  /** Wall-clock duration in ms */
  durationMs: number
  /** Error message if status is 'failed' */
  error?: string
}

/**
 * GoalNode — Recursive tree node in the goal decomposition tree.
 *
 * The root goal is the team's top-level objective. Coordinators decompose
 * it into child goals (sub-tasks), which may themselves be decomposed
 * further by sub-coordinators. Leaf goals are assigned to specialist agents.
 */
export interface GoalNode {
  /** Unique identifier */
  id: string
  /** Parent goal ID (undefined for root) */
  parentId?: string
  /** Human-readable title */
  title: string
  /** Detailed description of what needs to be done */
  description: string
  /** Current status */
  status: GoalStatus
  /** Depth in the tree (root = 0) */
  depth: number
  /** IDs of child goals (empty for leaf nodes) */
  children: string[]
  /** IDs of goals that must complete before this one can start */
  dependencies: string[]
  /** Agent ID assigned to this goal (set when an agent picks it up) */
  assignedAgentId?: string
  /** Role hint for the agent that should handle this goal */
  roleHint?: string
  /** Result when completed or failed */
  result?: GoalResult
  /** Priority within siblings (higher = more important, default 0) */
  priority: number
  /** Timestamps */
  createdAt: number
  startedAt?: number
  completedAt?: number
  /** Metadata for custom extensions */
  metadata?: Record<string, unknown>
}


/**
 * TeamBudget — Shared resource limits for the entire team tree.
 *
 * All agents in a team share these limits. The TeamOrchestrator enforces
 * them across the tree. When any limit is hit, the team pauses for
 * supervisor approval or auto-stops.
 */
export interface TeamBudget {
  /** Maximum total tokens across all agents (default: 2_000_000) */
  maxTokens: number
  /** Maximum number of agents spawned (including sub-coordinators) */
  maxAgents: number
  /** Maximum depth of the goal tree (default: 3) */
  maxDepth: number
  /** Maximum total wall-clock time in ms (default: 2 hours) */
  maxDurationMs: number
  /** Maximum iterations per individual agent loop */
  maxIterationsPerAgent: number

  /** Tokens used so far across all agents */
  tokensUsed: number
  /** Number of agents spawned so far */
  agentsSpawned: number
  /** Estimated cost in USD */
  estimatedCostUsd: number
  /** Time the team started */
  startedAt: number
}


export type CheckpointMode =
  | 'none'          // No checkpoints — fully autonomous
  | 'cassi'         // Cassi-as-supervisor: pause and notify user's active session
  | 'human'         // Human review: pause and wait for human approval

/**
 * TeamConfig — Configuration for a team session.
 */
export interface TeamConfig {
  /** Display name for the team */
  name?: string
  /** The top-level goal description */
  goal: string
  /** Budget constraints */
  budget?: Partial<Omit<TeamBudget, 'tokensUsed' | 'agentsSpawned' | 'estimatedCostUsd' | 'startedAt'>>
  /** Checkpoint configuration */
  checkpoint: {
    /** When to create checkpoints */
    mode: CheckpointMode
    /** Session ID of the supervisor (for 'cassi' mode) */
    supervisorSessionId?: string
    /** Auto-approve timeout in ms (default: 5 min). If supervisor doesn't respond, auto-approve. */
    autoApproveTimeoutMs?: number
    /** Trigger checkpoints at these budget thresholds (% of max) */
    budgetThresholds?: number[]
    /** Trigger checkpoint every N completed goals */
    completedGoalsInterval?: number
  }
  /** Default provider/model for agents (can be overridden per role) */
  defaultProvider?: { model?: string; providerId?: string; thinking?: string }
  /** Role-specific provider overrides */
  roleProviders?: Record<string, { model?: string; providerId?: string; thinking?: string }>
  /** Whether agents may perform destructive operations */
  allowDestructive?: boolean
  /**
   * External team — wraps an OpenCode subagent rather than spawning CassiCore internal agents.
   * When true, createTeam() skips coordinator spawning and autonomous loop.
   * The team lifecycle is driven by subagent_start/subagent_end events from the plugin.
   */
  external?: boolean
  /**
   * The OpenCode session ID of the external subagent being wrapped.
   * Only set when external === true.
   */
  externalSessionId?: string
  /**
   * The OpenCode parent session ID that spawned the external subagent.
   * Only set when external === true.
   */
  externalParentSessionId?: string
  /** Metadata for custom extensions */
  metadata?: Record<string, unknown>
}


export type TeamStatus =
  | 'initializing'  // Team is being set up
  | 'running'       // Actively processing goals
  | 'paused'        // Paused (checkpoint, user request, or budget limit)
  | 'completed'     // All goals completed successfully
  | 'failed'        // Team failed (unrecoverable error or budget exceeded)
  | 'cancelled'     // Cancelled by user or supervisor

/**
 * TeamSession — Tracks the full lifecycle of an autonomous team.
 *
 * This is the top-level entity. It owns the goal tree, budget,
 * configuration, and references to all participating agents.
 */
export interface TeamSession {
  /** Unique team ID */
  id: string
  /** Current status */
  status: TeamStatus
  /** Configuration */
  config: TeamConfig
  /** Shared budget (live-updated) */
  budget: TeamBudget
  /** The root goal ID in the goal tree */
  rootGoalId: string
  /** All goals in the tree, keyed by ID */
  goals: Record<string, GoalNode>
  /** Agent ID of the root coordinator */
  coordinatorAgentId?: string
  /** Session ID of the coordinator agent */
  coordinatorSessionId?: string
  /** All agent IDs participating in this team */
  agentIds: string[]
  /** Mapping: agentId → goalId they're working on */
  agentGoalMap: Record<string, string>
  /** Timestamps */
  createdAt: number
  startedAt?: number
  completedAt?: number
  /** Final synthesized result (set when team completes) */
  finalResult?: string
  /**
   * External team flag — mirrors config.external.
   * When true, this team wraps an OpenCode subagent (no internal coordinator/agents).
   */
  external?: boolean
  /**
   * The OpenCode session ID of the external subagent.
   * Only set when external === true.
   */
  externalSessionId?: string
  /**
   * The OpenCode parent session ID that spawned the external subagent.
   * Only set when external === true.
   */
  externalParentSessionId?: string
  /** History of team-level events for audit trail */
  eventLog: TeamEventLogEntry[]
}


export type TeamEventType =
  | 'team:created'
  | 'team:started'
  | 'team:paused'
  | 'team:resumed'
  | 'team:completed'
  | 'team:failed'
  | 'team:cancelled'
  | 'team:checkpoint'
  | 'team:checkpoint:approved'
  | 'team:checkpoint:rejected'
  | 'team:checkpoint:auto_approved'
  | 'team:budget:warning'
  | 'team:budget:exceeded'
  | 'goal:created'
  | 'goal:started'
  | 'goal:completed'
  | 'goal:failed'
  | 'goal:blocked'
  | 'goal:delegated'
  | 'agent:spawned'
  | 'agent:completed'
  | 'agent:failed'

/**
 * TeamEventLogEntry — Audit log entry for team-level events.
 */
export interface TeamEventLogEntry {
  type: TeamEventType
  timestamp: number
  /** ID of the entity this event relates to (team, goal, or agent) */
  entityId: string
  /** Human-readable message */
  message: string
  /** Additional structured data */
  data?: Record<string, unknown>
}


export type CheckpointStatus =
  | 'pending'       // Waiting for supervisor response
  | 'approved'      // Supervisor approved — team continues
  | 'rejected'      // Supervisor rejected — team stops or revises
  | 'auto_approved' // Timed out — auto-approved per config

/**
 * TeamCheckpoint — Represents a pause point where the supervisor
 * evaluates team progress and decides whether to continue.
 */
export interface TeamCheckpoint {
  /** Unique checkpoint ID */
  id: string
  /** Team ID */
  teamId: string
  /** Why this checkpoint was triggered */
  trigger: 'budget_threshold' | 'completed_goals' | 'manual' | 'error' | 'depth_limit'
  /** Current team status snapshot */
  status: CheckpointStatus
  /** Summary of progress so far */
  progressSummary: string
  /** Goals completed so far */
  completedGoals: number
  /** Total goals in tree */
  totalGoals: number
  /** Budget usage snapshot */
  budgetSnapshot: {
    tokensUsed: number
    maxTokens: number
    agentsSpawned: number
    maxAgents: number
    elapsedMs: number
    maxDurationMs: number
    estimatedCostUsd: number
  }
  /** Supervisor's response (if any) */
  supervisorResponse?: {
    action: 'approve' | 'reject' | 'steer'
    message?: string
    /** For 'steer': revised instructions or priority changes */
    adjustments?: Record<string, unknown>
  }
  /** Timestamps */
  createdAt: number
  resolvedAt?: number
}


/**
 * AgentDecision — Structured decision emitted by an autonomous agent
 * at the end of each iteration. Parsed from <decision> tags in LLM output.
 */
export type AgentDecision =
  | { action: 'continue'; reason?: string }
  | { action: 'complete'; result: string; reason?: string }
  | { action: 'delegate'; delegateTo: string; delegateTask: string; reason?: string }
  | { action: 'blocked'; reason: string }
