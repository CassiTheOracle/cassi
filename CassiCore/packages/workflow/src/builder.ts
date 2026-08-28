/**
 * Workflow Builder — fluent API for composing workflow definitions.
 *
 * Usage:
 *   const wf = createWorkflow({ id: 'my-pipeline' })
 *     .then(step1)
 *     .parallel([step2a, step2b])
 *     .branch([ [condition, stepA], [condition, stepB] ])
 *     .foreach(step3, { concurrency: 5 })
 *     .dountil(step4, condition)
 *     .commit()
 */

import type {
  WorkflowStep,
  WorkflowDefinition,
  WorkflowNode,
  StepNode,
  ParallelNode,
  BranchNode,
  ForeachNode,
  DoUntilNode,
  DoWhileNode,
  ListenNode,
  SubworkflowNode,
  StateMachineNode,
  StateDefinition,
  TransitionDefinition,
  TransitionGuard,
  TransitionAction,
  RetryPolicy,
  StepContext,
} from '@cassicore/foundation'

// createStep — factory for individual steps

export interface CreateStepOptions<TInput = unknown, TOutput = unknown> {
  id: string
  description?: string
  execute: (ctx: StepContext<TInput>) => Promise<TOutput>
  retry?: RetryPolicy
  timeoutMs?: number
}

export function createStep<TInput = unknown, TOutput = unknown>(
  opts: CreateStepOptions<TInput, TOutput>,
): WorkflowStep<TInput, TOutput> {
  return {
    id: opts.id,
    description: opts.description,
    execute: opts.execute,
    retry: opts.retry,
    timeoutMs: opts.timeoutMs,
  }
}

// WorkflowBuilder — fluent chain that accumulates nodes

let nodeCounter = 0
function nextNodeId(prefix: string): string {
  return `${prefix}_${++nodeCounter}`
}

/** Reset the counter (for testing). */
export function _resetNodeCounter(): void {
  nodeCounter = 0
}

export interface CreateWorkflowOptions {
  id: string
  description?: string
}

export function createWorkflow(opts: CreateWorkflowOptions): WorkflowBuilder {
  return new WorkflowBuilder(opts.id, opts.description)
}

export class WorkflowBuilder {
  private readonly workflowId: string
  private readonly description?: string
  private readonly nodes: WorkflowNode[] = []

  constructor(id: string, description?: string) {
    this.workflowId = id
    this.description = description
  }

  // Step-based control flow (Layer 1)

  /** Append a sequential step. */
  then(stepOrWorkflow: WorkflowStep | WorkflowDefinition | WorkflowBuilder): this {
    if (stepOrWorkflow instanceof WorkflowBuilder) {
      const def = stepOrWorkflow.commit()
      this.nodes.push({ id: nextNodeId('sub'), kind: 'subworkflow', workflow: def } as SubworkflowNode)
    } else if ('nodes' in stepOrWorkflow && 'entryNodeId' in stepOrWorkflow) {
      this.nodes.push({ id: nextNodeId('sub'), kind: 'subworkflow', workflow: stepOrWorkflow } as SubworkflowNode)
    } else {
      this.nodes.push({ id: nextNodeId('step'), kind: 'step', step: stepOrWorkflow } as StepNode)
    }
    return this
  }

  /** Execute multiple steps/workflows in parallel, collecting results. */
  parallel(
    branches: Array<WorkflowStep | WorkflowDefinition | WorkflowBuilder>,
    opts?: { merge?: 'array' | 'object' | ((results: unknown[]) => unknown) },
  ): this {
    const branchNodes: WorkflowNode[][] = branches.map((b) => {
      if (b instanceof WorkflowBuilder) {
        const def = b.commit()
        return [{ id: nextNodeId('sub'), kind: 'subworkflow', workflow: def } as SubworkflowNode]
      } else if ('nodes' in b && 'entryNodeId' in b) {
        return [{ id: nextNodeId('sub'), kind: 'subworkflow', workflow: b } as SubworkflowNode]
      } else {
        return [{ id: nextNodeId('step'), kind: 'step', step: b } as StepNode]
      }
    })

    this.nodes.push({
      id: nextNodeId('par'),
      kind: 'parallel',
      branches: branchNodes,
      merge: opts?.merge,
    } as ParallelNode)

    return this
  }

  /** Conditional branching: evaluate conditions in order, take the first match. */
  branch(
    routes: Array<[
      condition: (input: unknown) => boolean | Promise<boolean>,
      target: WorkflowStep | WorkflowDefinition | WorkflowBuilder,
    ]>,
    fallback?: WorkflowStep | WorkflowDefinition | WorkflowBuilder,
  ): this {
    const routeNodes = routes.map(([condition, target]) => ({
      condition,
      nodes: this.toNodeArray(target),
    }))

    const node: BranchNode = {
      id: nextNodeId('branch'),
      kind: 'branch',
      routes: routeNodes,
      fallback: fallback ? this.toNodeArray(fallback) : undefined,
    }

    this.nodes.push(node)
    return this
  }

  /** Iterate over a collection, executing a step for each item. */
  foreach(
    step: WorkflowStep | WorkflowDefinition | WorkflowBuilder,
    opts?: {
      getItems?: (input: unknown) => unknown[] | Promise<unknown[]>
      concurrency?: number
    },
  ): this {
    this.nodes.push({
      id: nextNodeId('each'),
      kind: 'foreach',
      body: this.toNodeArray(step),
      getItems: opts?.getItems,
      concurrency: opts?.concurrency,
    } as ForeachNode)
    return this
  }

  /** Loop: execute body, check condition after. Exit when condition returns true. */
  dountil(
    body: WorkflowStep | WorkflowDefinition | WorkflowBuilder,
    condition: (input: unknown, iterationCount: number) => boolean | Promise<boolean>,
    opts?: { maxIterations?: number },
  ): this {
    this.nodes.push({
      id: nextNodeId('dountil'),
      kind: 'dountil',
      body: this.toNodeArray(body),
      condition,
      maxIterations: opts?.maxIterations,
    } as DoUntilNode)
    return this
  }

  /** Loop: execute body, check condition after. Continue while condition returns true. */
  dowhile(
    body: WorkflowStep | WorkflowDefinition | WorkflowBuilder,
    condition: (input: unknown, iterationCount: number) => boolean | Promise<boolean>,
    opts?: { maxIterations?: number },
  ): this {
    this.nodes.push({
      id: nextNodeId('dowhile'),
      kind: 'dowhile',
      body: this.toNodeArray(body),
      condition,
      maxIterations: opts?.maxIterations,
    } as DoWhileNode)
    return this
  }

  // Event-driven reactive (Layer 3)

  /**
   * Add a reactive listener that waits for events on the specified channels.
   * When an event is received, the handler step executes with the event data as input.
   *
   * The listener blocks workflow execution until an event is received (or timeout).
   * Use this for event-driven coordination between steps.
   *
   * Example:
   *   createWorkflow({ id: 'reactive' })
   *     .then(step1)  // emits to 'data-ready' channel via ctx.emit()
   *     .listen({
   *       channels: ['data-ready'],
   *       handler: createStep({ id: 'process', execute: async (ctx) => { ... } }),
   *       timeoutMs: 30000,
   *     })
   *     .then(step2)
   *     .commit()
   */
  listen(opts: {
    channels: string | string[]
    handler: WorkflowStep
    once?: boolean
    maxFires?: number
    timeoutMs?: number
  }): this {
    const channels = Array.isArray(opts.channels) ? opts.channels : [opts.channels]

    this.nodes.push({
      id: nextNodeId('listen'),
      kind: 'listen',
      channels,
      handler: opts.handler,
      once: opts.once,
      maxFires: opts.maxFires,
      timeoutMs: opts.timeoutMs,
    } as ListenNode)

    return this
  }

  // State machine (Layer 2)

  /**
   * Add a state machine node that executes a graph of named states with transitions.
   * Supports cycles, guard conditions, transition actions, and event-based transitions.
   *
   * Use StateMachineBuilder for a fluent definition, or pass a raw StateMachineNode config.
   *
   * Example:
   *   createWorkflow({ id: 'approval' })
   *     .stateMachine(
   *       createStateMachine('approval-flow')
   *         .state('draft', { initial: true, onEnter: draftStep })
   *           .transition('review', { guard: (input) => input.ready })
   *           .transition('cancelled')
   *         .state('review', { onEnter: reviewStep })
   *           .transition('approved', { guard: (input) => input.approved })
   *           .transition('draft', { guard: (input) => input.needsRevision })
   *         .state('approved', { final: true, onEnter: notifyStep })
   *         .state('cancelled', { final: true })
   *     )
   *     .then(postProcessStep)
   *     .commit()
   */
  stateMachine(
    builder: StateMachineBuilder,
    opts?: { maxTransitions?: number; timeoutMs?: number },
  ): this {
    const smNode = builder.build()

    if (opts?.maxTransitions !== undefined) {
      smNode.maxTransitions = opts.maxTransitions
    }
    if (opts?.timeoutMs !== undefined) {
      smNode.timeoutMs = opts.timeoutMs
    }

    this.nodes.push(smNode)
    return this
  }

  // Compile

  /** Compile the builder into a frozen WorkflowDefinition. */
  commit(): WorkflowDefinition {
    if (this.nodes.length === 0) {
      throw new Error(`Workflow "${this.workflowId}" has no nodes`)
    }

    // WHY: Build an explicit edge map so the engine can walk the DAG without
    // the builder's implicit ordering assumptions
    const edges = new Map<string, string[]>()
    for (let i = 0; i < this.nodes.length - 1; i++) {
      edges.set(this.nodes[i].id, [this.nodes[i + 1].id])
    }
    // Last node has no outgoing edges
    edges.set(this.nodes[this.nodes.length - 1].id, [])

    return {
      id: this.workflowId,
      description: this.description,
      nodes: [...this.nodes],
      edges,
      entryNodeId: this.nodes[0].id,
      exitNodeId: this.nodes[this.nodes.length - 1].id,
    }
  }

  // Internal helpers

  private toNodeArray(target: WorkflowStep | WorkflowDefinition | WorkflowBuilder): WorkflowNode[] {
    if (target instanceof WorkflowBuilder) {
      const def = target.commit()
      return [{ id: nextNodeId('sub'), kind: 'subworkflow', workflow: def } as SubworkflowNode]
    } else if ('nodes' in target && 'entryNodeId' in target) {
      return [{ id: nextNodeId('sub'), kind: 'subworkflow', workflow: target } as SubworkflowNode]
    } else {
      return [{ id: nextNodeId('step'), kind: 'step', step: target } as StepNode]
    }
  }
}

// StateMachineBuilder — fluent API for defining state machines

interface PendingState {
  name: string
  initial: boolean
  final: boolean
  onEnter?: WorkflowStep
  transitions: TransitionDefinition[]
}

/** Factory function for creating a StateMachineBuilder. */
export function createStateMachine(id: string): StateMachineBuilder {
  return new StateMachineBuilder(id)
}

export class StateMachineBuilder {
  private readonly machineId: string
  private readonly pendingStates: PendingState[] = []
  private currentState: PendingState | null = null

  constructor(id: string) {
    this.machineId = id
  }

  /**
   * Define a state. Subsequent .transition() calls add outgoing edges from this state.
   * Options:
   *   initial — mark as the start state (exactly one required)
   *   final — mark as a terminal state (at least one required)
   *   onEnter — step to execute when entering this state
   */
  state(
    name: string,
    opts?: { initial?: boolean; final?: boolean; onEnter?: WorkflowStep },
  ): this {
    // Finalize the previous state
    if (this.currentState) {
      this.pendingStates.push(this.currentState)
    }

    this.currentState = {
      name,
      initial: opts?.initial ?? false,
      final: opts?.final ?? false,
      onEnter: opts?.onEnter,
      transitions: [],
    }

    return this
  }

  /**
   * Add a transition from the current state to a target state.
   * Options:
   *   guard — condition function (transition fires only if true)
   *   action — side-effect function (runs during transition, output becomes next input)
   *   event — event channel name (transition waits for this event)
   */
  transition(
    target: string,
    opts?: {
      guard?: TransitionGuard
      action?: TransitionAction
      event?: string
    },
  ): this {
    if (!this.currentState) {
      throw new Error('StateMachineBuilder: call .state() before .transition()')
    }

    this.currentState.transitions.push({
      target,
      guard: opts?.guard,
      action: opts?.action,
      event: opts?.event,
    })

    return this
  }

  /** Compile the builder into a StateMachineNode. */
  build(): StateMachineNode {
    // Finalize the last state
    if (this.currentState) {
      this.pendingStates.push(this.currentState)
      this.currentState = null
    }

    if (this.pendingStates.length === 0) {
      throw new Error(`StateMachine "${this.machineId}": no states defined`)
    }

    const initialStates = this.pendingStates.filter((s) => s.initial)
    if (initialStates.length === 0) {
      throw new Error(`StateMachine "${this.machineId}": no initial state defined`)
    }
    if (initialStates.length > 1) {
      throw new Error(
        `StateMachine "${this.machineId}": multiple initial states: ${initialStates.map((s) => s.name).join(', ')}`,
      )
    }

    const finalStates = this.pendingStates.filter((s) => s.final)
    if (finalStates.length === 0) {
      throw new Error(`StateMachine "${this.machineId}": no final state defined`)
    }

    // Validate all transition targets exist
    const stateNames = new Set(this.pendingStates.map((s) => s.name))
    for (const state of this.pendingStates) {
      for (const t of state.transitions) {
        if (!stateNames.has(t.target)) {
          throw new Error(
            `StateMachine "${this.machineId}": state "${state.name}" has transition to unknown state "${t.target}"`,
          )
        }
      }
    }

    const states: StateDefinition[] = this.pendingStates.map((s) => ({
      name: s.name,
      initial: s.initial || undefined,
      final: s.final || undefined,
      onEnter: s.onEnter,
      transitions: s.transitions,
    }))

    return {
      id: nextNodeId('sm'),
      kind: 'statemachine',
      states,
    }
  }
}
