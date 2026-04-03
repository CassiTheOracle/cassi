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
  SubworkflowNode,
  RetryPolicy,
  StepContext,
} from '../../types/workflow.js'

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
