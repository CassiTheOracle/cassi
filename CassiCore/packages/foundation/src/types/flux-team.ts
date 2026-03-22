/**
 * FluxTeam Type Definitions
 *
 * Next-generation dynamic multi-agent team architecture. Replaces TriadTeam's
 * rigid Proposer→Critic→Executor pipeline with execution-mode-aware agents,
 * graph-based topologies, and learning-driven routing.
 *
 * Execution modes:
 *   - lumen: Three-agent dialectic (Yang/Yin/Executive) — for read-only and research tasks
 *   - dyad:  Three-agent refinement pipeline (Yang/Yin/Apex) — for action and write tasks
 *
 * Core concepts:
 *   - AgentGenome: Configurable agent blueprint with per-mode posture directives
 *   - Topology: Graph-based execution plan with conditional transitions
 *   - Blackboard: Enhanced shared workspace with channels and reactive subscriptions
 *   - OutcomeLedger: Learning store that records genome+topology performance
 */

// Agent Genomes

/**
 * Behavioral trait spectrum for an agent genome.
 * Values 0-1 shape the system prompt and Lumen posture directives.
 */
export interface AgentTraits {
  /** Creative/expansive thinking (high = Proposer-like divergent exploration) */
  divergent: number
  /** Critical/evaluative thinking (high = Critic-like convergent analysis) */
  convergent: number
  /** Action-oriented execution (high = Executor-like decisive implementation) */
  executive: number
}

/**
 * Lumen session configuration for a genome.
 * Controls how Yang/Yin/Executive behave when this genome is instantiated.
 * Used for read-only and research tasks.
 */
export interface GenomeLumenConfig {
  /** Directive for Yang posture (assertive/exploratory) */
  yangDirective: string
  /** Directive for Yin posture (cautious/evaluative) */
  yinDirective: string
  /** Directive for Executive posture (synthesis/decision) */
  executiveDirective: string
  /** Max dialectic iterations (default: 200) */
  maxIterations: number
  /** Stop when posture agreement >= threshold (0-1, default: 0.8) */
  convergenceThreshold: number
  /** Per-node timeout in ms (default: 300_000 = 5 min) */
  timeoutMs: number
}

/**
 * Dyad pipeline configuration for a genome.
 * Controls how Yang/Yin/Apex behave when this genome is instantiated.
 * Used for action and write tasks.
 */
export interface GenomeDyadConfig {
  /** Task type hint for the Dyad pipeline */
  taskType: 'implementation' | 'refactor' | 'analysis' | 'auto'
  /** Directive for Yang posture (worker — implements the change) — embedded in goal context */
  yangDirective: string
  /** Directive for Yin posture (refiner — reviews and improves) — embedded in goal context */
  yinDirective: string
  /** Directive for Apex posture (overseer — quality and coherence) — embedded in goal context */
  apexDirective: string
  /** Per-node timeout in ms (default: 1_800_000 = 30 min) */
  timeoutMs: number
}

/** Execution mode for a genome.
 *
 * - lumen: Three-agent dialectic (Yang/Yin/Executive). Best for read-only,
 *          research, analysis, planning, and security audits.
 * - dyad:  Three-agent refinement pipeline (Yang/Yin/Apex). Best for
 *          implementation, refactoring, integration, and write tasks.
 */
export type GenomeMode = 'lumen' | 'dyad'

/** Tool access level for an agent */
export type ToolAccessLevel = 'read' | 'read-test' | 'full'

/** Cost tier for model selection */
export type CostTier = 'free' | 'budget' | 'premium'

/** Built-in genome archetype identifiers */
export type GenomeArchetype =
  | 'explore'
  | 'build'
  | 'review'
  | 'secure'
  | 'plan'
  | 'integrate'
  | 'quick-fix'
  | 'quick-read'

/**
 * Model assignment for a genome.
 */
export interface GenomeModel {
  provider: string
  model: string
  thinking?: 'none' | 'low' | 'medium' | 'high'
}

/**
 * AgentGenome — Configurable agent blueprint.
 *
 * Replaces fixed Proposer/Critic/Executor roles with a flexible system
 * where agents are defined by traits, skills, and Lumen posture directives.
 */
export interface AgentGenome {
  /** Unique genome identifier */
  id: string
  /** Human-readable name (e.g., "TypeScript Explorer") */
  name: string
  /** Built-in archetype this genome is based on (if any) */
  archetype?: GenomeArchetype

  /** Execution mode: lumen (dialectic for research) or dyad (pipeline for write tasks) */
  mode: GenomeMode
  /** Behavioral traits (shape prompt generation) */
  traits: AgentTraits

  /** Lumen dialectic configuration (required when mode='lumen') */
  lumen?: GenomeLumenConfig
  /** Dyad pipeline configuration (required when mode='dyad') */
  dyad?: GenomeDyadConfig

  /** Domain proficiency scores (0-1): e.g., { typescript: 0.9, security: 0.7 } */
  skills: Record<string, number>
  /** Tool access level */
  toolAccess: ToolAccessLevel
  /** Model assignment */
  model: GenomeModel
  /** Cost tier preference */
  costTier: CostTier
}

// Execution Topologies

/** Node activation mode */
export type NodeActivation =
  | { type: 'sequential' }
  | { type: 'reactive'; watch: { channel: BlackboardChannel; tags?: string[] } }

/**
 * A node in the execution topology graph.
 * Each node represents an agent (Lumen dialectic session or Dyad pipeline) to execute.
 */
export interface TopologyNode {
  /** Unique node identifier within the topology */
  id: string
  /** Agent genome to use (ID reference or inline genome) */
  genome: string | AgentGenome
  /** Overrides for the genome (for specialization without creating a new genome) */
  overrides?: Partial<AgentGenome>
  /** Whether this node spawns parallel workers (for Star topology) */
  parallel?: boolean
  /** Node activation mode */
  activation?: NodeActivation
  /** Goal/instruction override for this specific node */
  goalOverride?: string
}

/**
 * Transition condition types for topology edges.
 */
export type TransitionCondition =
  | { type: 'always' }
  | { type: 'confidence'; min?: number; max?: number }
  | { type: 'blackboard'; channel: BlackboardChannel; key?: string; exists: boolean }
  | { type: 'tests-pass' }
  | { type: 'budget-remaining'; min: number }
  | { type: 'human-approval' }
  | { type: 'max-loops'; count: number; edgeKey?: string }
  | { type: 'custom'; evaluator: string }

/**
 * An edge in the execution topology graph.
 * Connects nodes with optional transition conditions.
 */
export interface TopologyEdge {
  /** Source node ID */
  from: string
  /** Target node ID (or 'END' for terminal edges) */
  to: string | 'END'
  /** Condition for traversing this edge */
  condition?: TransitionCondition
  /** Priority for edge selection when multiple edges from same node (lower = evaluated first) */
  priority?: number
}

/** Built-in topology template identifiers */
export type TopologyTemplate = 'solo' | 'dyad' | 'adaptive' | 'star' | 'secure' | 'ring'

/**
 * Execution topology — a directed graph of agent nodes with conditional transitions.
 */
export interface Topology {
  /** Unique topology identifier */
  id: string
  /** Human-readable name */
  name: string
  /** Template this topology is based on (if any) */
  template?: TopologyTemplate
  /** Nodes in the graph */
  nodes: TopologyNode[]
  /** Edges connecting nodes */
  edges: TopologyEdge[]
  /** Entry point node ID */
  entryNodeId: string
}

// Plan

/** Status of a plan step */
export type PlanStepStatus =
  | 'proposed'      // Submitted by an agent, awaiting Executive review
  | 'approved'      // Approved by Executive
  | 'rejected'      // Rejected by Executive (with reason)
  | 'in_progress'   // Actively being worked on
  | 'completed'     // Step finished successfully
  | 'blocked'       // Blocked by unmet dependencies

/** Overall plan status */
export type PlanStatus =
  | 'drafting'      // Steps being proposed and reviewed
  | 'approved'      // Plan finalized and ready for execution
  | 'executing'     // Plan actively being followed
  | 'completed'     // All steps done
  | 'abandoned'     // Plan discarded

/**
 * A single step in a structured plan.
 */
export interface PlanStep {
  /** Unique step identifier */
  id: string
  /** Short title for the step */
  title: string
  /** Detailed description of what this step entails */
  description: string
  /** Current status */
  status: PlanStepStatus
  /** Posture or node that proposed this step */
  author: string
  /** Execution order (lower = earlier) */
  order: number
  /** Step IDs this depends on */
  dependencies: string[]
  /** Priority level */
  priority: 'high' | 'medium' | 'low'
  /** Outcome text when completed */
  outcome?: string
  /** Reason for rejection (if rejected) */
  rejectionReason?: string
  /** Tags for categorization */
  tags: string[]
  /** When the step was created */
  createdAt: number
  /** When the step was last updated */
  updatedAt: number

  // Work-claiming fields

  /** Agent/posture that claimed this step for execution */
  assignee?: string
  /** When the step was claimed (ms since epoch) */
  claimedAt?: number
  /** Last heartbeat from the assignee (ms since epoch) — used for stall detection */
  lastActivityAt?: number
  /** Per-step stall timeout override in ms (default: 30 min from Blackboard) */
  stallTimeoutMs?: number
}

/**
 * A structured plan on the Blackboard.
 *
 * Plans are first-class objects managed by the Executive posture.
 * Any agent can propose steps, but only the Executive can approve,
 * reject, or finalize the plan.
 */
export interface Plan {
  /** Unique plan identifier */
  id: string
  /** The goal this plan addresses */
  goal: string
  /** Overall plan status */
  status: PlanStatus
  /** Ordered list of plan steps */
  steps: PlanStep[]
  /** When the plan was created */
  createdAt: number
  /** When the plan was last updated */
  updatedAt: number
  /** Who approved/finalized the plan */
  approvedBy?: string
  /** When the plan was approved/finalized */
  approvedAt?: number
  /** Summary notes about the plan */
  summary?: string
}

// Blackboard

/** Structured communication channels on the Blackboard */
export type BlackboardChannel =
  | 'findings'      // Discovery results from exploration nodes
  | 'concerns'      // Issues flagged by analysis/security nodes
  | 'decisions'     // Resolutions and action items
  | 'artifacts'     // File changes and produced outputs
  | 'requests'      // Requests for additional capabilities (DRTAG trigger)

/**
 * An entry posted to a Blackboard channel.
 */
export interface BlackboardEntry {
  /** Unique entry identifier */
  id: string
  /** Channel this entry belongs to */
  channel: BlackboardChannel
  /** Node ID that posted this entry */
  author: string
  /** Content text */
  content: string
  /** Optional structured data */
  structured?: Record<string, unknown>
  /** Priority (higher = more important, default: 0) */
  priority: number
  /** Tags for filtering and categorization */
  tags: string[]
  /** Timestamp of creation */
  timestamp: number
}

/**
 * File artifact tracking entry.
 */
export interface ArtifactEntry {
  /** File path (relative to workspace root) */
  path: string
  /** Operation performed */
  operation: 'created' | 'modified' | 'deleted'
  /** Node ID that created/modified this artifact */
  author: string
  /** Timestamp */
  timestamp: number
}

/**
 * Scratchpad entry with TTL support.
 */
export interface FluxScratchpadEntry {
  key: string
  value: string
  author: string
  createdAt: number
  ttlMs: number
}

/**
 * Tool execution record for the blackboard.
 */
export interface FluxToolRecord {
  /** Tool name */
  tool: string
  /** Node ID that executed the tool */
  nodeId: string
  /** Input parameters */
  params: Record<string, unknown>
  /** Result (truncated if large) */
  result: string
  /** Whether the tool call failed */
  isError: boolean
  /** Duration in milliseconds */
  durationMs: number
  /** Timestamp */
  timestamp: number
}

/**
 * Blackboard state snapshot for persistence/restore.
 */
export interface BlackboardState {
  id: string
  cellId: string
  channels: Record<BlackboardChannel, BlackboardEntry[]>
  scratchpad: Record<string, FluxScratchpadEntry>
  toolLog: FluxToolRecord[]
  artifacts: Record<string, ArtifactEntry>
  childResults: Record<string, FluxCellResult>
  parentContext: string
  /** Structured plan (optional — present when planning is active) */
  plan?: Plan
  /** Incremental report (optional — present when report is used) */
  report?: Report
  createdAt: number
  lastActivityAt: number
}

/**
 * Subscription for reactive blackboard watching.
 */
export interface BlackboardSubscription {
  id: string
  channel: BlackboardChannel
  tags?: string[]
  callback: (entry: BlackboardEntry) => void
}

// Task Analysis

/** Task complexity levels */
export type TaskComplexity = 'trivial' | 'medium' | 'complex' | 'critical'

/** Task scope estimation */
export type TaskScope = 'single-file' | 'multi-file' | 'cross-module'

/** Risk level assessment */
export type RiskLevel = 'low' | 'medium' | 'high'

/**
 * Task signature produced by the Task Analyzer.
 * Drives topology and genome selection.
 */
export interface TaskSignature {
  /** Detected domains (e.g., ['typescript', 'testing', 'react']) */
  domains: string[]
  /** Complexity assessment */
  complexity: TaskComplexity
  /** Risk level */
  riskLevel: RiskLevel
  /** Scope estimation */
  estimatedScope: TaskScope
  /** Estimated number of files mentioned or implied by the goal */
  estimatedFileCount: number
  /** File paths extracted from the goal/context text */
  detectedFiles: string[]
  /** Whether the task needs hierarchical decomposition */
  needsDecomposition: boolean
  /** Suggested topology template */
  suggestedTopology: TopologyTemplate
  /** Required tool access level */
  toolsNeeded: ToolAccessLevel
}

// Outcome Ledger

/**
 * Outcome record for a completed FluxCell execution.
 * Stored in the Outcome Ledger for learning.
 */
export interface OutcomeRecord {
  /** Unique record identifier */
  id: string
  /** Task signature at execution time */
  taskSignature: TaskSignature
  /** Topology template used */
  topology: string
  /** Per-node outcomes */
  nodeOutcomes: NodeOutcome[]
  /** Overall success/failure */
  overallSuccess: boolean
  /** Quality score (0-1) from automated or human assessment */
  overallQuality: number
  /** Total tokens consumed */
  totalTokens: number
  /** Total duration in ms */
  totalDurationMs: number
  /** Timestamp of completion */
  timestamp: number
}

/**
 * Per-node outcome within a FluxCell execution.
 */
export interface NodeOutcome {
  nodeId: string
  genomeId: string
  success: boolean
  /** Lumen confidence (from synthesis) or Dyad quality score (qualityScore/100) */
  confidence: number
  tokensUsed: number
  durationMs: number
}

/**
 * Routing recommendation from the Outcome Ledger.
 */
export interface RoutingRecommendation {
  /** Recommended topology template */
  topology: TopologyTemplate
  /** Recommended genomes for each node */
  genomes: Record<string, string>
  /** Confidence in this recommendation (0-1) */
  confidence: number
  /** Number of past outcomes informing this recommendation */
  evidence: number
}

// FluxCell

/** FluxCell execution status */
export type FluxCellStatus =
  | 'initializing'
  | 'analyzing'      // Task analyzer running
  | 'routing'        // Skill router selecting genomes/topology
  | 'executing'      // Topology engine running
  | 'synthesizing'   // Integrating results
  | 'completed'
  | 'failed'
  | 'degraded'
  | 'cancelled'
  | 'paused'

/** Node execution status within a topology */
export type FluxNodeStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'skipped'

/**
 * Live status of a node within the topology.
 */
export interface FluxNodeLiveStatus {
  nodeId: string
  status: FluxNodeStatus
  genomeId: string
  mode: GenomeMode
  /** Lumen confidence (if mode='lumen' and completed) */
  confidence?: number
  /** Current thinking/progress text */
  currentThinking?: string
  /** Tokens consumed so far */
  tokensUsed: number
  /** Duration so far in ms */
  durationMs: number
  /** Error message if failed */
  error?: string
  /** Timestamp of last status change */
  lastUpdated: number
}

/**
 * Live status of the entire FluxCell.
 */
export interface FluxCellLiveStatus {
  cellId: string
  status: FluxCellStatus
  topologyId: string
  /** Node execution states */
  nodes: Record<string, FluxNodeLiveStatus>
  /** Edges traversed so far */
  edgesTraversed: Array<{ from: string; to: string; condition?: string; timestamp: number }>
  /** Total tokens consumed */
  totalTokens: number
  /** Total duration so far */
  totalDurationMs: number
  /** Loop counts per edge (for max-loops tracking) */
  loopCounts: Record<string, number>
}

/**
 * Result of a completed FluxCell execution.
 */
export interface FluxCellResult {
  cellId: string
  success: boolean
  /** Final synthesis/output text */
  output: string
  /** Quality score (0-1) if assessed */
  quality?: number
  /** Node results in execution order */
  nodeResults: FluxNodeResult[]
  /** Total tokens consumed */
  totalTokens: number
  /** Total duration in ms */
  totalDurationMs: number
  /** Topology used */
  topologyId: string
  /** Artifacts produced */
  artifacts: ArtifactEntry[]
  /** Timestamp of completion */
  completedAt: number
  /** Error message if failed */
  error?: string
  /** Deliverable verification result */
  verification?: DeliverableVerification
  /** Incremental report produced by the dialectic session (if any) */
  report?: Report
}

/**
 * Result of post-execution deliverable verification.
 * Checks whether the cell's actual work matches the goal's expectations.
 */
export interface DeliverableVerification {
  /** Whether verification passed */
  passed: boolean
  /** Human-readable reason for pass/fail */
  reason: string
  /** File paths mentioned in the goal */
  filesExpected: string[]
  /** File paths actually modified (from git diff) */
  filesModified: string[]
  /** Percentage of expected files that were modified */
  coveragePercent: number
  /** Total tool calls executed across all nodes */
  totalToolCalls: number
  /** Whether any write/edit tools were called */
  hadWriteOperations: boolean
}

/**
 * Result from a single topology node.
 */
export interface FluxNodeResult {
  nodeId: string
  genomeId: string
  mode: GenomeMode
  success: boolean
  /** Output/synthesis from this node */
  output: string
  /**
   * Recommendation from the executing orchestrator.
   * - lumen nodes: derived from Executive synthesis
   * - dyad nodes: derived from Apex quality assessment
   */
  recommendation?: 'proceed' | 'reconsider' | 'abort'
  /**
   * Confidence from the executing orchestrator (0–1).
   * - lumen nodes: dialectic confidence from Executive
   * - dyad nodes: qualityScore / 100 from Apex
   */
  confidence?: number
  /** Tokens consumed */
  tokensUsed: number
  /** Duration in ms */
  durationMs: number
  /** Tool calls made */
  toolCallCount: number
  /** Error if failed */
  error?: string
}

// FluxTeam Configuration

/**
 * Configuration for automatic goal decomposition into sub-cells.
 *
 * WHY: Flux Teams failed to scale because the root cell never spawned
 * sub-cells autonomously. The orchestrator needs to proactively decompose
 * large goals (e.g., 253-file comment fixes) into parallel sub-cells
 * based on TaskAnalyzer signals.
 */
export interface DecompositionConfig {
  /** Enable auto-decomposition (default: true) */
  enabled: boolean
  /** Decompose when estimated file count exceeds this threshold (default: 10) */
  fileThreshold: number
  /** Maximum sub-cells to spawn (respects budget.maxCells) */
  maxSubCells: number
  /** Files per sub-cell batch (default: 5; 0 = auto-calculate) */
  filesPerBatch: number
  /** Group files by directory prefix for locality (default: true) */
  groupByPrefix: boolean
}

/**
 * Configuration for detecting and intervening when cells stall.
 *
 * WHY: In a live test, a single cell consumed 6.4M tokens over 11 minutes
 * without writing a single file. Progress steering detects this "analysis
 * paralysis" pattern and intervenes before budget is wasted.
 */
export interface ProgressSteeringConfig {
  /** Enable progress-based steering (default: true) */
  enabled: boolean
  /** Token threshold without edits before intervention (default: 200_000) */
  tokenThresholdWithoutEdits: number
  /** Time in ms without file edits before intervention (default: 120_000) */
  timeWithoutEditsMs: number
  /** Maximum node iterations with zero edits before intervention (default: 3) */
  maxIterationsWithoutProgress: number
  /** Intervention mode when stall detected */
  interventionMode: 'inject-guidance' | 'fail-cell' | 'escalate'
}

/**
 * Configuration for token budget gates.
 *
 * WHY: Cells that consume excessive tokens relative to their output
 * (e.g., 6.4M tokens with 0 file edits) waste resources. Token gates
 * enforce efficiency by checking the tokens-to-edits ratio.
 */
export interface TokenBudgetGateConfig {
  /** Enable token budget gates (default: true) */
  enabled: boolean
  /** Maximum tokens per file edit before gate triggers (default: 200_000) */
  maxTokensPerEdit: number
  /** Maximum tokens consumed with zero edits before gate triggers (default: 500_000) */
  maxTokensWithoutAnyEdit: number
}

/**
 * Sub-cell specification for decomposed goals.
 */
export interface SubCellSpec {
  /** Sub-cell identifier */
  id: string
  /** Batch of file paths this sub-cell should process */
  files: string[]
  /** Derived goal description for this sub-cell */
  goal: string
  /** Parent cell ID */
  parentCellId: string
  /** Batch index (0-based) */
  batchIndex: number
  /** Total number of batches */
  totalBatches: number
}

/**
 * Progress snapshot captured during cell execution.
 * Used by progress steering and token budget gates.
 */
export interface ProgressSnapshot {
  /** Total tokens consumed so far */
  tokensConsumed: number
  /** Tokens consumed since the last file edit */
  tokensSinceLastEdit: number
  /** Time in ms since the last file edit */
  timeSinceLastEditMs: number
  /** Number of file edits made so far */
  editsCount: number
  /** Number of completed node iterations */
  iterationsCompleted: number
  /** Iterations since the last file edit */
  iterationsSinceLastEdit: number
  /** Timestamp of this snapshot */
  timestamp: number
}

/**
 * Budget constraints for a FluxTeam.
 */
export interface FluxTeamBudget {
  /** Maximum total tokens (0 = unlimited) */
  maxTokens: number
  /** Maximum number of FluxCells (default: 20) */
  maxCells: number
  /** Maximum topology depth for hierarchical decomposition (default: 3) */
  maxDepth: number
  /** Maximum total duration in ms (default: 4 hours) */
  maxDurationMs: number
  /** Maximum tool iterations per node (default: 50) */
  maxToolIterationsPerNode: number

  /** Auto-decomposition configuration */
  decomposition?: Partial<DecompositionConfig>
  /** Progress-based steering configuration */
  progressSteering?: Partial<ProgressSteeringConfig>
  /** Token budget gate configuration */
  tokenGates?: Partial<TokenBudgetGateConfig>
}

/**
 * FluxTeam configuration for creating a new team.
 */
export interface FluxTeamConfig {
  /** Optional team identifier for pre-scoped routing and shell UX */
  teamId?: string
  /** Goal description */
  goal: string
  /** Additional context */
  context?: string
  /** Parent session ID for Phase Zero context distillation */
  parentSessionId?: string

  /**
   * @deprecated Use the model_directive tool to set routing before creating teams.
   * Provider/model are no longer used — routing is controlled by ModelDirective scopes.
   */
  provider?: string
  /**
   * @deprecated Use the model_directive tool to set routing before creating teams.
   * Provider/model are no longer used — routing is controlled by ModelDirective scopes.
   */
  model?: string

  /** Explicit topology to use (overrides Task Analyzer) */
  topology?: TopologyTemplate | Topology
  /** Explicit genome overrides per node */
  genomes?: Record<string, string | AgentGenome>

  /** Budget constraints */
  budget?: Partial<FluxTeamBudget>

  /** Enable human checkpoints */
  checkpoint?: boolean
  /** Feature flag: use FluxTeam (vs TriadTeam fallback) */
  useFluxTeam?: boolean
}

/**
 * FluxTeam session state.
 */
export interface FluxTeamSession {
  id: string
  status: FluxTeamStatus
  config: FluxTeamConfig
  budget: FluxTeamBudget
  rootCellId: string
  cells: Map<string, FluxCellInfo>
  taskSignature?: TaskSignature
  routingRecommendation?: RoutingRecommendation
  createdAt: number
  startedAt?: number
  completedAt?: number
  finalResult?: string
  /** Last error message — set when status transitions to 'failed' */
  lastError?: string
  eventLog: FluxTeamEvent[]
  interruptReason?: string
  interruptedAt?: number
}

/** FluxTeam status */
export type FluxTeamStatus =
  | 'created'
  | 'analyzing'
  | 'routing'
  | 'starting'    // Cell created, async execution about to begin
  | 'running'
  | 'paused'
  | 'completed'
  | 'failed'
  | 'cancelled'

/**
 * Summary info for a cell within a FluxTeam.
 */
export interface FluxCellInfo {
  cellId: string
  status: FluxCellStatus
  topologyId: string
  goal: string
  parentCellId?: string
  childCellIds: string[]
  depth: number
  tokensUsed: number
  result?: FluxCellResult
  error?: string
  createdAt: number
  completedAt?: number
}

/**
 * Event log entry for FluxTeam operations.
 */
export interface FluxTeamEvent {
  id: string
  teamId: string
  type: FluxTeamEventType
  entityId: string
  message: string
  data?: Record<string, unknown>
  timestamp: number
}

/** Event types for FluxTeam operations */
export type FluxTeamEventType =
  | 'team:created'
  | 'team:started'
  | 'team:completed'
  | 'team:failed'
  | 'team:paused'
  | 'team:resumed'
  | 'team:cancelled'
  | 'team:checkpoint'
  | 'cell:created'
  | 'cell:started'
  | 'cell:completed'
  | 'cell:failed'
  | 'cell:degraded'
  | 'node:started'
  | 'node:completed'
  | 'node:failed'
  | 'node:skipped'
  | 'edge:traversed'
  | 'topology:selected'
  | 'genome:selected'
  | 'genome:generated'
  | 'blackboard:entry'
  | 'outcome:recorded'

// Topology Degradation

/**
 * Fallback chain for topology degradation.
 * When a topology fails, fall back to simpler topologies.
 */
export interface TopologyFallbackChain {
  /** Ordered list of topologies to try (first = most complex) */
  chain: TopologyTemplate[]
}

/** Default fallback chain: ring → adaptive → dyad → solo */
export const DEFAULT_FALLBACK_CHAIN: TopologyFallbackChain = {
  chain: ['ring', 'adaptive', 'dyad', 'solo'],
}

// Incremental Report System

/**
 * Section types for the incremental report.
 * Each type represents a different kind of curated insight.
 */
export type ReportSectionType =
  | 'finding'          // Key discovery with evidence
  | 'concern'          // Risk, tradeoff, or negative consequence
  | 'recommendation'   // Suggested course of action
  | 'evidence'         // Supporting data (file references, test results)
  | 'open-question'    // Something needing further investigation
  | 'decision'         // Resolution of a tension or tradeoff
  | 'note'             // Context, historical reference, moderation observation

/**
 * Section lifecycle status.
 * Auto-drafted sections start as 'draft', manual additions as 'active'.
 */
export type ReportSectionStatus = 'draft' | 'active' | 'superseded'

/**
 * A single section of the incremental report.
 * Sections are the atomic units of curated insight.
 */
export interface ReportSection {
  /** Unique section identifier */
  id: string
  /** Type of insight */
  type: ReportSectionType
  /** Lifecycle status */
  status: ReportSectionStatus
  /** Section title */
  title: string
  /** Section content (curated insight text) */
  content: string
  /** Author posture name (yang/yin/executive) */
  author: string
  /** Author confidence in this insight (0-1) */
  confidence?: number
  /** File paths, memory keys, or other evidence references */
  references?: string[]
  /** Thread ID grouping related sections across postures */
  threadId?: string
  /** Section ID this responds to */
  respondsTo?: string
  /** Section ID this challenges */
  challenges?: string
  /** Section ID this supports */
  supports?: string
  /** Section ID this revision supersedes */
  supersedes?: string
  /** True if a newer revision exists */
  superseded?: boolean
  /** Sensitivity classification for blackboard sync */
  sensitivity?: 'public' | 'internal' | 'secret'
  /** Creation timestamp */
  createdAt: number
  /** Last update timestamp */
  updatedAt: number
}

/**
 * The incremental report — a curated document built collaboratively
 * by all three postures during a Lumen session.
 */
export interface Report {
  /** Unique report identifier */
  id: string
  /** Goal the report is for */
  goal: string
  /** All sections (including superseded ones for audit trail) */
  sections: ReportSection[]
  /** Template name if a task-specific template was used */
  template?: string
  /** Creation timestamp */
  createdAt: number
  /** Last update timestamp */
  updatedAt: number
}

/**
 * Quality metrics for a report, calculated on demand.
 */
export interface ReportQualityMetrics {
  /** Total sections (all statuses) */
  totalSections: number
  /** Sections with status 'active' */
  activeSections: number
  /** Sections with status 'draft' */
  draftSections: number
  /** Count by section type */
  byType: Partial<Record<ReportSectionType, number>>
  /** Count by author */
  byAuthor: Record<string, number>
  /** Average confidence across active sections */
  avgConfidence: number
  /** Number of distinct threads */
  threadCount: number
  /** Concerns without a linked decision or resolution */
  unresolvedConcerns: number
  /** Coverage score (0-1): type diversity relative to ideal distribution */
  coverageScore: number
}
