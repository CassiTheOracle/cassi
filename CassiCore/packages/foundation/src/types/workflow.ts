/**
 * Agent Workflow System — shared type definitions.
 *
 * Three-layer hybrid design:
 *   Layer 1: Step-based workflows (.then/.parallel/.branch/.foreach/.dountil/.dowhile)
 *   Layer 2: Graph / state machine (cycles, conditional edges)
 *   Layer 3: Event-driven reactive workflows (listen/emit patterns)
 *
 * Steps are the atomic unit. Workflows compose steps with control flow.
 * The WorkflowEngine executes workflows, tracking state and emitting events.
 */

import type { IEventBus, ILogger } from './interfaces.js'

// Step primitives

/** Typed execution context available to every step. */
export interface StepContext<TInput = unknown> {
  /** Input data from the previous step (or workflow input for the first step). */
  input: TInput
  /** Shared mutable state bag that persists across the entire workflow run. */
  state: WorkflowState
  /** Patch shared workflow state (shallow-merged). */
  setState: (patch: Record<string, unknown>) => void
  /** Scoped logger for this step. */
  logger: ILogger
  /** Event bus for emitting / subscribing to CassiCore events. */
  eventBus: IEventBus
  /** Emit a workflow-scoped event that @listen steps can react to. */
  emit: (channel: string, data: unknown) => void
  /** Suspend the workflow for external input (human-in-the-loop). Throws SuspendSignal. */
  suspend: (reason: string) => never
  /** The workflow run this step belongs to. */
  runId: string
  /** The workflow definition id. */
  workflowId: string
  /** Current retry attempt (0-based). Only > 0 when retries are configured. */
  attempt: number
}

/** A single unit of work with typed input and output. */
export interface WorkflowStep<TInput = unknown, TOutput = unknown> {
  /** Unique step id within its workflow. */
  id: string
  /** Human-readable description (shown in traces). */
  description?: string
  /** The execution function. Receives typed context, returns typed output. */
  execute: (ctx: StepContext<TInput>) => Promise<TOutput>
  /** Optional retry policy for this step. */
  retry?: RetryPolicy
  /** Optional timeout in ms for this step. */
  timeoutMs?: number
}

export interface RetryPolicy {
  /** Maximum number of retry attempts (default: 0 = no retries). */
  maxAttempts: number
  /** Base delay in ms between retries (default: 1000). */
  delayMs?: number
  /** Backoff multiplier (default: 2). */
  backoffMultiplier?: number
  /** Maximum delay cap in ms (default: 30000). */
  maxDelayMs?: number
  /** Only retry on these error types (default: retry on all). */
  retryOn?: Array<string | RegExp>
}

// Workflow definition

/** A compiled workflow definition ready for execution. */
export interface WorkflowDefinition {
  /** Unique workflow id. */
  id: string
  /** Human-readable description. */
  description?: string
  /** The compiled execution plan (internal DAG of nodes). */
  nodes: WorkflowNode[]
  /** Adjacency list: nodeId → list of successor nodeIds. */
  edges: Map<string, string[]>
  /** The entry node id. */
  entryNodeId: string
  /** The exit node id (may be synthetic). */
  exitNodeId: string
}

// Workflow node types (internal execution plan)

export type WorkflowNodeKind =
  | 'step'       // execute a single step
  | 'parallel'   // fan-out, execute N children concurrently, fan-in
  | 'branch'     // conditional routing
  | 'foreach'    // iterate over a collection
  | 'dountil'    // loop until condition is true
  | 'dowhile'    // loop while condition is true
  | 'subworkflow' // nested workflow execution
  | 'listen'     // event-driven reactive listener
  | 'statemachine' // graph-based state machine with cycles

export interface WorkflowNodeBase {
  id: string
  kind: WorkflowNodeKind
}

export interface StepNode extends WorkflowNodeBase {
  kind: 'step'
  step: WorkflowStep
}

export interface ParallelNode extends WorkflowNodeBase {
  kind: 'parallel'
  branches: WorkflowNode[][]
  /** How to merge parallel results. Default: array of results in branch order. */
  merge?: 'array' | 'object' | ((results: unknown[]) => unknown)
}

export interface BranchNode extends WorkflowNodeBase {
  kind: 'branch'
  routes: Array<{
    condition: (input: unknown) => boolean | Promise<boolean>
    nodes: WorkflowNode[]
  }>
  /** Optional fallback branch if no condition matches. */
  fallback?: WorkflowNode[]
}

export interface ForeachNode extends WorkflowNodeBase {
  kind: 'foreach'
  /** Step or sub-workflow to execute for each item. */
  body: WorkflowNode[]
  /** Extract the iterable from the input. Default: input itself (must be array). */
  getItems?: (input: unknown) => unknown[] | Promise<unknown[]>
  /** Maximum concurrent iterations (default: 1 = sequential). */
  concurrency?: number
}

export interface DoUntilNode extends WorkflowNodeBase {
  kind: 'dountil'
  body: WorkflowNode[]
  /** Condition checked AFTER each iteration. Loop exits when true. */
  condition: (input: unknown, iterationCount: number) => boolean | Promise<boolean>
  /** Safety cap on iterations (default: 10). */
  maxIterations?: number
}

export interface DoWhileNode extends WorkflowNodeBase {
  kind: 'dowhile'
  body: WorkflowNode[]
  /** Condition checked AFTER each iteration. Loop continues while true. */
  condition: (input: unknown, iterationCount: number) => boolean | Promise<boolean>
  /** Safety cap on iterations (default: 10). */
  maxIterations?: number
}

export interface SubworkflowNode extends WorkflowNodeBase {
  kind: 'subworkflow'
  workflow: WorkflowDefinition
}

export interface ListenNode extends WorkflowNodeBase {
  kind: 'listen'
  /** Channel(s) to listen on. */
  channels: string[]
  /** Handler invoked when any channel fires. Receives event data as input. */
  handler: WorkflowStep
  /** If true, listener fires only once per channel (default: false). */
  once?: boolean
  /** Maximum number of times to fire across all channels (default: unlimited). */
  maxFires?: number
  /** Timeout waiting for events in ms (default: 60000). 0 = no timeout. */
  timeoutMs?: number
}

// State machine types (Layer 2)

/** Guard function: evaluates whether a transition should fire. */
export type TransitionGuard = (input: unknown, state: WorkflowState) => boolean | Promise<boolean>

/** Action function: runs side effects during a transition (before entering next state). */
export type TransitionAction = (input: unknown, state: WorkflowState) => unknown | Promise<unknown>

/** A single state within a state machine. */
export interface StateDefinition {
  /** Unique state name within this machine. */
  name: string
  /** If true, this is the initial state. Exactly one required per machine. */
  initial?: boolean
  /** If true, reaching this state terminates the machine. At least one required. */
  final?: boolean
  /** Step to execute upon entering this state. Receives previous transition output as input. */
  onEnter?: WorkflowStep
  /** Outgoing transitions from this state, evaluated in order. */
  transitions: TransitionDefinition[]
}

/** A directed edge between two states. */
export interface TransitionDefinition {
  /** Target state name. */
  target: string
  /** Optional guard: transition only fires when guard returns true. */
  guard?: TransitionGuard
  /** Optional action: runs during the transition, output becomes the next state's input. */
  action?: TransitionAction
  /** Optional event channel: transition fires only when this event is received. */
  event?: string
}

/** A state machine node embeddable in a workflow. */
export interface StateMachineNode extends WorkflowNodeBase {
  kind: 'statemachine'
  /** All states in the machine. */
  states: StateDefinition[]
  /** Maximum total transitions before forced termination (safety cap, default: 100). */
  maxTransitions?: number
  /** Timeout for the entire machine execution in ms (default: 300000). 0 = no timeout. */
  timeoutMs?: number
}

export type WorkflowNode =
  | StepNode
  | ParallelNode
  | BranchNode
  | ForeachNode
  | DoUntilNode
  | DoWhileNode
  | SubworkflowNode
  | ListenNode
  | StateMachineNode

// Workflow state and execution

/** Shared mutable state bag that persists across the entire workflow run. */
export type WorkflowState = Record<string, unknown>

export type WorkflowRunStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'suspended'
  | 'cancelled'

export interface WorkflowRun {
  /** Unique run id. */
  runId: string
  /** The workflow definition id. */
  workflowId: string
  /** Current status. */
  status: WorkflowRunStatus
  /** Shared state bag. */
  state: WorkflowState
  /** The initial input to the workflow. */
  input: unknown
  /** The final output (set on completion). */
  output?: unknown
  /** Error message (set on failure). */
  error?: string
  /** Node id where the workflow is currently executing. */
  currentNodeId?: string
  /** Node id where the workflow suspended (for resume). */
  suspendedAtNodeId?: string
  /** Reason for suspension. */
  suspendReason?: string
  /** Step execution history. */
  trace: StepTrace[]
  /** When the run started. */
  startedAt: Date
  /** When the run ended (completed/failed/cancelled). */
  endedAt?: Date
  /** Total duration in ms. */
  durationMs?: number
}

export interface StepTrace {
  nodeId: string
  stepId?: string
  kind: WorkflowNodeKind
  status: 'running' | 'completed' | 'failed' | 'skipped' | 'retrying'
  input?: unknown
  output?: unknown
  error?: string
  attempt: number
  startedAt: Date
  endedAt?: Date
  durationMs?: number
}

// Engine configuration

export interface WorkflowEngineConfig {
  /** Logger instance. */
  logger: ILogger
  /** Event bus for emitting workflow events. */
  eventBus: IEventBus
  /** Default timeout per step in ms (default: 300000 = 5 min). */
  defaultStepTimeoutMs?: number
  /** Maximum parallel concurrency across all workflows (default: 10). */
  maxConcurrency?: number
  /** Optional persistence store. When provided, runs are saved at lifecycle boundaries. */
  store?: IWorkflowStore
}

// Persistence interface

/** Persistence backend for workflow runs. */
export interface IWorkflowStore {
  save(run: WorkflowRun): void
  load(runId: string): WorkflowRun | undefined
  list(opts?: { status?: WorkflowRunStatus; workflowId?: string; limit?: number }): WorkflowRun[]
  listSuspended(): WorkflowRun[]
  delete(runId: string): boolean
  close(): void
}

// Suspend signal (thrown by ctx.suspend())

// WHY: SuspendSignal is re-exported from core/workflow/engine.ts as a runtime
// value. This interface defines the shape for type-checking.
export interface ISuspendSignal {
  readonly name: 'SuspendSignal'
  readonly reason: string
  readonly nodeId: string
  readonly message: string
}

// Event-driven reactive layer (Layer 3)

/** A listener that reacts to workflow-scoped events. */
export interface WorkflowListener {
  /** Channel name to listen on. */
  channel: string
  /** Handler invoked when the channel receives data. */
  handler: (data: unknown, ctx: StepContext) => Promise<unknown>
}

// Workflow registry

/** Registry of compiled workflow definitions available for execution. */
export interface IWorkflowRegistry {
  register(workflow: WorkflowDefinition): void
  get(workflowId: string): WorkflowDefinition | undefined
  list(): WorkflowDefinition[]
  remove(workflowId: string): boolean
}

// Workflow definition storage

/** Metadata for a stored workflow definition. */
export interface StoredWorkflowDefinition {
  /** Unique definition id (matches workflowId). */
  id: string
  /** Human-readable name. */
  name: string
  /** Semantic version string (e.g. "1.0.0"). */
  version: string
  /** Optional description. */
  description?: string
  /** Tags for categorization and discovery. */
  tags: string[]
  /** Serialized node graph (structure only — no function references). */
  nodeGraph: SerializedNodeGraph
  /** ISO timestamp of creation. */
  createdAt: string
  /** ISO timestamp of last update. */
  updatedAt: string
  /** Whether this definition is enabled. */
  enabled: boolean
}

/** Serializable representation of a workflow's node graph (structure only). */
export interface SerializedNodeGraph {
  entryNodeId: string
  /** Serializable node metadata (node IDs, kinds, connections, config). */
  nodes: SerializedNode[]
}

/** A serialized node (structure without function references). */
export interface SerializedNode {
  id: string
  kind: WorkflowNodeKind
  /** Step IDs referenced by this node (for resolving from a step registry). */
  stepIds: string[]
  /** Child node IDs (for parallel, branch, etc.). */
  children: string[]
  /** Additional config (maxIterations, timeoutMs, channels, state names, etc.). */
  config: Record<string, unknown>
}

/** Persistence backend for workflow definitions. */
export interface IWorkflowDefinitionStore {
  save(definition: StoredWorkflowDefinition): void
  load(id: string): StoredWorkflowDefinition | undefined
  loadVersion(id: string, version: string): StoredWorkflowDefinition | undefined
  list(opts?: { tag?: string; enabled?: boolean; limit?: number }): StoredWorkflowDefinition[]
  listVersions(id: string): StoredWorkflowDefinition[]
  delete(id: string, version?: string): boolean
  close(): void
}
