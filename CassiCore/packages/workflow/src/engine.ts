/**
 * WorkflowEngine — executes compiled WorkflowDefinitions.
 *
 * Walks the node list sequentially, handling each node kind:
 *   step       → execute the step function
 *   parallel   → fan-out with Promise.all, fan-in with merge
 *   branch     → evaluate conditions, take first match
 *   foreach    → iterate with optional concurrency
 *   dountil    → loop until condition is true
 *   dowhile    → loop while condition is true
 *   subworkflow → recurse into a nested workflow definition
 *
 * Emits workflow:* events on the EventBus throughout execution.
 * Supports suspend/resume for human-in-the-loop workflows.
 */

import { randomUUID } from 'node:crypto'
import type {
  WorkflowDefinition,
  WorkflowNode,
  StepNode,
  ParallelNode,
  BranchNode,
  ForeachNode,
  DoUntilNode,
  DoWhileNode,
  SubworkflowNode,
  ListenNode,
  StateMachineNode,
  WorkflowRun,
  WorkflowState,
  StepTrace,
  WorkflowEngineConfig,
  StepContext,
  WorkflowStep,
  IWorkflowStore,
} from '../../types/workflow.js'
import type { ILogger, IEventBus } from '../../types/interfaces.js'
import { WorkflowEventBus } from './events.js'
import { StateMachineExecutor } from './state-machine.js'

// SuspendSignal — thrown by ctx.suspend() to pause workflow execution

export class SuspendSignal extends Error {
  readonly reason: string
  readonly nodeId: string
  constructor(reason: string, nodeId: string) {
    super(`Workflow suspended: ${reason}`)
    this.name = 'SuspendSignal'
    this.reason = reason
    this.nodeId = nodeId
  }
}

// WHY: instanceof fails across ESM module boundaries when the class comes from
// a different compilation unit. Use duck-typing instead.
function isSuspendSignal(err: unknown): err is SuspendSignal {
  return (
    typeof err === 'object' &&
    err !== null &&
    'name' in err &&
    (err as { name: string }).name === 'SuspendSignal' &&
    'reason' in err &&
    'nodeId' in err
  )
}

// Engine

export class WorkflowEngine {
  private readonly logger: ILogger
  private readonly eventBus: IEventBus
  private readonly defaultStepTimeoutMs: number
  private readonly store?: IWorkflowStore
  private readonly runs = new Map<string, WorkflowRun>()
  private readonly eventBuses = new Map<string, WorkflowEventBus>()

  constructor(config: WorkflowEngineConfig) {
    this.logger = config.logger.child('workflow-engine')
    this.eventBus = config.eventBus
    this.defaultStepTimeoutMs = config.defaultStepTimeoutMs ?? 300_000
    this.store = config.store
  }

  // Public API

  /** Execute a workflow definition with the given input. Returns the completed run. */
  async execute(
    definition: WorkflowDefinition,
    input: unknown = {},
    opts?: { runId?: string; initialState?: WorkflowState },
  ): Promise<WorkflowRun> {
    const runId = opts?.runId ?? randomUUID()
    const run: WorkflowRun = {
      runId,
      workflowId: definition.id,
      status: 'running',
      state: opts?.initialState ?? {},
      input,
      trace: [],
      startedAt: new Date(),
    }

    this.runs.set(runId, run)
    this.eventBuses.set(runId, new WorkflowEventBus(this.logger))
    this.persist(run)

    await this.eventBus.emit({
      type: 'workflow:started',
      runId,
      workflowId: definition.id,
      input,
      timestamp: new Date(),
    })

    try {
      const output = await this.executeNodes(definition.nodes, input, run)
      run.status = 'completed'
      run.output = output
      run.endedAt = new Date()
      run.durationMs = run.endedAt.getTime() - run.startedAt.getTime()

      await this.eventBus.emit({
        type: 'workflow:completed',
        runId,
        workflowId: definition.id,
        output,
        durationMs: run.durationMs,
        stepsExecuted: run.trace.length,
        timestamp: new Date(),
      })

      this.logger.info('Workflow completed', {
        runId,
        workflowId: definition.id,
        durationMs: run.durationMs,
        steps: run.trace.length,
      })

      this.persist(run)
      return run
    } catch (err) {
      if (isSuspendSignal(err)) {
        run.status = 'suspended'
        run.suspendedAtNodeId = err.nodeId
        run.suspendReason = err.reason

        await this.eventBus.emit({
          type: 'workflow:suspended',
          runId,
          workflowId: definition.id,
          reason: err.reason,
          suspendedAtNodeId: err.nodeId,
          timestamp: new Date(),
        })

        this.logger.info('Workflow suspended', {
          runId,
          workflowId: definition.id,
          reason: err.reason,
          nodeId: err.nodeId,
        })

        this.persist(run)
        return run
      }

      run.status = 'failed'
      run.error = String(err)
      run.endedAt = new Date()
      run.durationMs = run.endedAt.getTime() - run.startedAt.getTime()

      await this.eventBus.emit({
        type: 'workflow:failed',
        runId,
        workflowId: definition.id,
        error: String(err),
        failedNodeId: run.currentNodeId,
        durationMs: run.durationMs,
        timestamp: new Date(),
      })

      this.logger.error('Workflow failed', {
        runId,
        workflowId: definition.id,
        error: String(err),
        nodeId: run.currentNodeId,
      })

      this.persist(run)
      return run
    }
  }

  /** Cancel a running workflow. */
  async cancel(runId: string, reason: string): Promise<void> {
    const run = this.runs.get(runId)
    if (!run || (run.status !== 'running' && run.status !== 'suspended')) return

    run.status = 'cancelled'
    run.error = `Cancelled: ${reason}`
    run.endedAt = new Date()
    run.durationMs = run.endedAt.getTime() - run.startedAt.getTime()

    await this.eventBus.emit({
      type: 'workflow:cancelled',
      runId,
      workflowId: run.workflowId,
      reason,
      timestamp: new Date(),
    })

    this.persist(run)
  }

  /** Get a run by its id (checks in-memory first, then store). */
  getRun(runId: string): WorkflowRun | undefined {
    return this.runs.get(runId) ?? this.store?.load(runId)
  }

  /** List all tracked runs. */
  listRuns(): WorkflowRun[] {
    return [...this.runs.values()]
  }

  /**
   * Resume a suspended workflow from where it left off.
   *
   * The caller must provide the same workflow definition that was originally executed,
   * plus optional resumeInput that replaces the suspended step's input.
   */
  async resume(
    definition: WorkflowDefinition,
    runId: string,
    resumeInput?: unknown,
  ): Promise<WorkflowRun> {
    // Load from in-memory or store
    let run = this.runs.get(runId) ?? this.store?.load(runId)
    if (!run) throw new Error(`Workflow run "${runId}" not found`)
    if (run.status !== 'suspended') throw new Error(`Workflow run "${runId}" is not suspended (status: ${run.status})`)
    if (!run.suspendedAtNodeId) throw new Error(`Workflow run "${runId}" has no suspended node id`)

    const suspendedNodeId = run.suspendedAtNodeId

    // Find the index of the suspended node
    const nodeIdx = definition.nodes.findIndex((n) => n.id === suspendedNodeId)
    if (nodeIdx === -1) {
      throw new Error(`Suspended node "${suspendedNodeId}" not found in workflow definition "${definition.id}"`)
    }

    // Clear suspend state
    run.status = 'running'
    run.suspendedAtNodeId = undefined
    run.suspendReason = undefined
    this.runs.set(runId, run)
    if (!this.eventBuses.has(runId)) {
      this.eventBuses.set(runId, new WorkflowEventBus(this.logger))
    }
    this.persist(run)

    await this.eventBus.emit({
      type: 'workflow:resumed',
      runId,
      workflowId: definition.id,
      resumedAtNodeId: suspendedNodeId,
      timestamp: new Date(),
    })

    try {
      // Resume from the suspended node onwards
      const remainingNodes = definition.nodes.slice(nodeIdx)
      const input = resumeInput !== undefined ? resumeInput : run.input
      const output = await this.executeNodes(remainingNodes, input, run)

      run.status = 'completed'
      run.output = output
      run.endedAt = new Date()
      run.durationMs = run.endedAt.getTime() - run.startedAt.getTime()

      await this.eventBus.emit({
        type: 'workflow:completed',
        runId,
        workflowId: definition.id,
        output,
        durationMs: run.durationMs,
        stepsExecuted: run.trace.length,
        timestamp: new Date(),
      })

      this.persist(run)
      return run
    } catch (err) {
      if (isSuspendSignal(err)) {
        run.status = 'suspended'
        run.suspendedAtNodeId = err.nodeId
        run.suspendReason = err.reason
        this.persist(run)

        await this.eventBus.emit({
          type: 'workflow:suspended',
          runId,
          workflowId: definition.id,
          reason: err.reason,
          suspendedAtNodeId: err.nodeId,
          timestamp: new Date(),
        })

        return run
      }

      run.status = 'failed'
      run.error = String(err)
      run.endedAt = new Date()
      run.durationMs = run.endedAt.getTime() - run.startedAt.getTime()
      this.persist(run)

      await this.eventBus.emit({
        type: 'workflow:failed',
        runId,
        workflowId: definition.id,
        error: String(err),
        failedNodeId: run.currentNodeId,
        durationMs: run.durationMs,
        timestamp: new Date(),
      })

      return run
    }
  }

  // Internal: node execution dispatch

  private async executeNodes(
    nodes: WorkflowNode[],
    input: unknown,
    run: WorkflowRun,
  ): Promise<unknown> {
    let currentInput = input

    for (const node of nodes) {
      run.currentNodeId = node.id
      currentInput = await this.executeNode(node, currentInput, run)
    }

    return currentInput
  }

  private async executeNode(
    node: WorkflowNode,
    input: unknown,
    run: WorkflowRun,
  ): Promise<unknown> {
    switch (node.kind) {
      case 'step':
        return this.executeStepNode(node as StepNode, input, run)
      case 'parallel':
        return this.executeParallelNode(node as ParallelNode, input, run)
      case 'branch':
        return this.executeBranchNode(node as BranchNode, input, run)
      case 'foreach':
        return this.executeForeachNode(node as ForeachNode, input, run)
      case 'dountil':
        return this.executeDoUntilNode(node as DoUntilNode, input, run)
      case 'dowhile':
        return this.executeDoWhileNode(node as DoWhileNode, input, run)
      case 'subworkflow':
        return this.executeSubworkflowNode(node as SubworkflowNode, input, run)
      case 'listen':
        return this.executeListenNode(node as ListenNode, input, run)
      case 'statemachine':
        return this.executeStateMachineNode(node as StateMachineNode, input, run)
      default:
        throw new Error(`Unknown node kind: ${(node as WorkflowNode).kind}`)
    }
  }

  // Step execution (with retry + timeout)

  private async executeStepNode(
    node: StepNode,
    input: unknown,
    run: WorkflowRun,
  ): Promise<unknown> {
    const step = node.step
    const maxAttempts = (step.retry?.maxAttempts ?? 0) + 1
    const timeoutMs = step.timeoutMs ?? this.defaultStepTimeoutMs
    let lastError: unknown

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      const trace: StepTrace = {
        nodeId: node.id,
        stepId: step.id,
        kind: 'step',
        status: 'running',
        input,
        attempt,
        startedAt: new Date(),
      }
      run.trace.push(trace)

      await this.eventBus.emit({
        type: 'workflow:step:started',
        runId: run.runId,
        workflowId: run.workflowId,
        nodeId: node.id,
        stepId: step.id,
        kind: 'step',
        attempt,
        timestamp: new Date(),
      })

      try {
        const ctx = this.buildContext(input, run, node.id)
        const result = await this.withTimeout(step.execute(ctx), timeoutMs, step.id)

        trace.status = 'completed'
        trace.output = result
        trace.endedAt = new Date()
        trace.durationMs = trace.endedAt.getTime() - trace.startedAt.getTime()

        await this.eventBus.emit({
          type: 'workflow:step:completed',
          runId: run.runId,
          workflowId: run.workflowId,
          nodeId: node.id,
          stepId: step.id,
          kind: 'step',
          durationMs: trace.durationMs,
          timestamp: new Date(),
        })

        return result
      } catch (err) {
        // Suspend signals propagate without retry
        if (isSuspendSignal(err)) throw err

        lastError = err
        trace.status = attempt < maxAttempts - 1 ? 'retrying' : 'failed'
        trace.error = String(err)
        trace.endedAt = new Date()
        trace.durationMs = trace.endedAt.getTime() - trace.startedAt.getTime()

        const willRetry = attempt < maxAttempts - 1

        await this.eventBus.emit({
          type: 'workflow:step:failed',
          runId: run.runId,
          workflowId: run.workflowId,
          nodeId: node.id,
          stepId: step.id,
          kind: 'step',
          error: String(err),
          attempt,
          willRetry,
          timestamp: new Date(),
        })

        if (willRetry && step.retry) {
          const delay = this.computeRetryDelay(attempt, step.retry)
          await this.eventBus.emit({
            type: 'workflow:step:retrying',
            runId: run.runId,
            workflowId: run.workflowId,
            nodeId: node.id,
            stepId: step.id,
            attempt: attempt + 1,
            delayMs: delay,
            timestamp: new Date(),
          })
          await this.sleep(delay)
        }
      }
    }

    throw lastError
  }

  // Parallel

  private async executeParallelNode(
    node: ParallelNode,
    input: unknown,
    run: WorkflowRun,
  ): Promise<unknown> {
    const trace: StepTrace = {
      nodeId: node.id,
      kind: 'parallel',
      status: 'running',
      input,
      attempt: 0,
      startedAt: new Date(),
    }
    run.trace.push(trace)

    await this.eventBus.emit({
      type: 'workflow:step:started',
      runId: run.runId,
      workflowId: run.workflowId,
      nodeId: node.id,
      kind: 'parallel',
      attempt: 0,
      timestamp: new Date(),
    })

    try {
      const results = await Promise.all(
        node.branches.map((branchNodes) => this.executeNodes(branchNodes, input, run)),
      )

      let merged: unknown
      if (typeof node.merge === 'function') {
        merged = node.merge(results)
      } else if (node.merge === 'object') {
        merged = Object.assign({}, ...results.map((r) => (typeof r === 'object' && r !== null ? r : {})))
      } else {
        merged = results
      }

      trace.status = 'completed'
      trace.output = merged
      trace.endedAt = new Date()
      trace.durationMs = trace.endedAt.getTime() - trace.startedAt.getTime()

      await this.eventBus.emit({
        type: 'workflow:step:completed',
        runId: run.runId,
        workflowId: run.workflowId,
        nodeId: node.id,
        kind: 'parallel',
        durationMs: trace.durationMs,
        timestamp: new Date(),
      })

      return merged
    } catch (err) {
      trace.status = 'failed'
      trace.error = String(err)
      trace.endedAt = new Date()
      trace.durationMs = trace.endedAt.getTime() - trace.startedAt.getTime()
      throw err
    }
  }

  // Branch (conditional)

  private async executeBranchNode(
    node: BranchNode,
    input: unknown,
    run: WorkflowRun,
  ): Promise<unknown> {
    const trace: StepTrace = {
      nodeId: node.id,
      kind: 'branch',
      status: 'running',
      input,
      attempt: 0,
      startedAt: new Date(),
    }
    run.trace.push(trace)

    await this.eventBus.emit({
      type: 'workflow:step:started',
      runId: run.runId,
      workflowId: run.workflowId,
      nodeId: node.id,
      kind: 'branch',
      attempt: 0,
      timestamp: new Date(),
    })

    try {
      for (const route of node.routes) {
        const matches = await route.condition(input)
        if (matches) {
          const result = await this.executeNodes(route.nodes, input, run)
          trace.status = 'completed'
          trace.output = result
          trace.endedAt = new Date()
          trace.durationMs = trace.endedAt.getTime() - trace.startedAt.getTime()

          await this.eventBus.emit({
            type: 'workflow:step:completed',
            runId: run.runId,
            workflowId: run.workflowId,
            nodeId: node.id,
            kind: 'branch',
            durationMs: trace.durationMs,
            timestamp: new Date(),
          })

          return result
        }
      }

      // No condition matched — use fallback or pass input through
      if (node.fallback) {
        const result = await this.executeNodes(node.fallback, input, run)
        trace.status = 'completed'
        trace.output = result
        trace.endedAt = new Date()
        trace.durationMs = trace.endedAt.getTime() - trace.startedAt.getTime()

        await this.eventBus.emit({
          type: 'workflow:step:completed',
          runId: run.runId,
          workflowId: run.workflowId,
          nodeId: node.id,
          kind: 'branch',
          durationMs: trace.durationMs,
          timestamp: new Date(),
        })

        return result
      }

      // No match, no fallback: pass input through
      trace.status = 'completed'
      trace.output = input
      trace.endedAt = new Date()
      trace.durationMs = trace.endedAt.getTime() - trace.startedAt.getTime()

      await this.eventBus.emit({
        type: 'workflow:step:completed',
        runId: run.runId,
        workflowId: run.workflowId,
        nodeId: node.id,
        kind: 'branch',
        durationMs: trace.durationMs,
        timestamp: new Date(),
      })

      return input
    } catch (err) {
      trace.status = 'failed'
      trace.error = String(err)
      trace.endedAt = new Date()
      trace.durationMs = trace.endedAt.getTime() - trace.startedAt.getTime()
      throw err
    }
  }

  // Foreach

  private async executeForeachNode(
    node: ForeachNode,
    input: unknown,
    run: WorkflowRun,
  ): Promise<unknown> {
    const trace: StepTrace = {
      nodeId: node.id,
      kind: 'foreach',
      status: 'running',
      input,
      attempt: 0,
      startedAt: new Date(),
    }
    run.trace.push(trace)

    await this.eventBus.emit({
      type: 'workflow:step:started',
      runId: run.runId,
      workflowId: run.workflowId,
      nodeId: node.id,
      kind: 'foreach',
      attempt: 0,
      timestamp: new Date(),
    })

    try {
      const items = node.getItems ? await node.getItems(input) : (input as unknown[])
      if (!Array.isArray(items)) {
        throw new Error(`foreach node "${node.id}": input is not iterable (got ${typeof items})`)
      }

      const concurrency = node.concurrency ?? 1
      const results: unknown[] = []

      if (concurrency <= 1) {
        // Sequential
        for (const item of items) {
          const result = await this.executeNodes(node.body, item, run)
          results.push(result)
        }
      } else {
        // Concurrent with limited parallelism
        const pool: Promise<void>[] = []
        let idx = 0

        const processItem = async (item: unknown, resultIdx: number): Promise<void> => {
          results[resultIdx] = await this.executeNodes(node.body, item, run)
        }

        for (const item of items) {
          const currentIdx = idx++
          const task = processItem(item, currentIdx)
          pool.push(task)

          if (pool.length >= concurrency) {
            await Promise.race(pool)
            // Remove settled promises
            const settled = pool.filter((p) => {
              let resolved = false
              p.then(() => { resolved = true }, () => { resolved = true })
              return resolved
            })
            for (const s of settled) {
              pool.splice(pool.indexOf(s), 1)
            }
          }
        }
        await Promise.all(pool)
      }

      trace.status = 'completed'
      trace.output = results
      trace.endedAt = new Date()
      trace.durationMs = trace.endedAt.getTime() - trace.startedAt.getTime()

      await this.eventBus.emit({
        type: 'workflow:step:completed',
        runId: run.runId,
        workflowId: run.workflowId,
        nodeId: node.id,
        kind: 'foreach',
        durationMs: trace.durationMs,
        timestamp: new Date(),
      })

      return results
    } catch (err) {
      trace.status = 'failed'
      trace.error = String(err)
      trace.endedAt = new Date()
      trace.durationMs = trace.endedAt.getTime() - trace.startedAt.getTime()
      throw err
    }
  }

  // DoUntil

  private async executeDoUntilNode(
    node: DoUntilNode,
    input: unknown,
    run: WorkflowRun,
  ): Promise<unknown> {
    const maxIterations = node.maxIterations ?? 10
    let currentInput = input
    let iteration = 0

    const trace: StepTrace = {
      nodeId: node.id,
      kind: 'dountil',
      status: 'running',
      input,
      attempt: 0,
      startedAt: new Date(),
    }
    run.trace.push(trace)

    await this.eventBus.emit({
      type: 'workflow:step:started',
      runId: run.runId,
      workflowId: run.workflowId,
      nodeId: node.id,
      kind: 'dountil',
      attempt: 0,
      timestamp: new Date(),
    })

    try {
      do {
        currentInput = await this.executeNodes(node.body, currentInput, run)
        iteration++

        const shouldStop = await node.condition(currentInput, iteration)
        if (shouldStop) break

        if (iteration >= maxIterations) {
          this.logger.warn('DoUntil hit max iterations', { nodeId: node.id, maxIterations })
          break
        }
      } while (true)

      trace.status = 'completed'
      trace.output = currentInput
      trace.endedAt = new Date()
      trace.durationMs = trace.endedAt.getTime() - trace.startedAt.getTime()

      await this.eventBus.emit({
        type: 'workflow:step:completed',
        runId: run.runId,
        workflowId: run.workflowId,
        nodeId: node.id,
        kind: 'dountil',
        durationMs: trace.durationMs,
        timestamp: new Date(),
      })

      return currentInput
    } catch (err) {
      trace.status = 'failed'
      trace.error = String(err)
      trace.endedAt = new Date()
      trace.durationMs = trace.endedAt.getTime() - trace.startedAt.getTime()
      throw err
    }
  }

  // DoWhile

  private async executeDoWhileNode(
    node: DoWhileNode,
    input: unknown,
    run: WorkflowRun,
  ): Promise<unknown> {
    const maxIterations = node.maxIterations ?? 10
    let currentInput = input
    let iteration = 0

    const trace: StepTrace = {
      nodeId: node.id,
      kind: 'dowhile',
      status: 'running',
      input,
      attempt: 0,
      startedAt: new Date(),
    }
    run.trace.push(trace)

    await this.eventBus.emit({
      type: 'workflow:step:started',
      runId: run.runId,
      workflowId: run.workflowId,
      nodeId: node.id,
      kind: 'dowhile',
      attempt: 0,
      timestamp: new Date(),
    })

    try {
      do {
        currentInput = await this.executeNodes(node.body, currentInput, run)
        iteration++

        const shouldContinue = await node.condition(currentInput, iteration)
        if (!shouldContinue) break

        if (iteration >= maxIterations) {
          this.logger.warn('DoWhile hit max iterations', { nodeId: node.id, maxIterations })
          break
        }
      } while (true)

      trace.status = 'completed'
      trace.output = currentInput
      trace.endedAt = new Date()
      trace.durationMs = trace.endedAt.getTime() - trace.startedAt.getTime()

      await this.eventBus.emit({
        type: 'workflow:step:completed',
        runId: run.runId,
        workflowId: run.workflowId,
        nodeId: node.id,
        kind: 'dowhile',
        durationMs: trace.durationMs,
        timestamp: new Date(),
      })

      return currentInput
    } catch (err) {
      trace.status = 'failed'
      trace.error = String(err)
      trace.endedAt = new Date()
      trace.durationMs = trace.endedAt.getTime() - trace.startedAt.getTime()
      throw err
    }
  }

  // Subworkflow

  private async executeSubworkflowNode(
    node: SubworkflowNode,
    input: unknown,
    run: WorkflowRun,
  ): Promise<unknown> {
    // Subworkflows reuse the parent run context (same trace, same state)
    return this.executeNodes(node.workflow.nodes, input, run)
  }

  // Listen (event-driven reactive)

  private async executeListenNode(
    node: ListenNode,
    input: unknown,
    run: WorkflowRun,
  ): Promise<unknown> {
    const trace: StepTrace = {
      nodeId: node.id,
      stepId: node.handler.id,
      kind: 'listen',
      status: 'running',
      input,
      attempt: 0,
      startedAt: new Date(),
    }
    run.trace.push(trace)

    await this.eventBus.emit({
      type: 'workflow:step:started',
      runId: run.runId,
      workflowId: run.workflowId,
      nodeId: node.id,
      stepId: node.handler.id,
      kind: 'listen',
      attempt: 0,
      timestamp: new Date(),
    })

    try {
      const wfEventBus = this.eventBuses.get(run.runId)
      if (!wfEventBus) {
        throw new Error(`No workflow event bus for run "${run.runId}"`)
      }

      const timeoutMs = node.timeoutMs ?? 60_000

      // Wait for an event on any of the specified channels
      const event = await wfEventBus.waitFor(node.channels, {
        timeoutMs,
      })

      // Execute the handler step with the event data as input
      const ctx = this.buildContext(event.data, run, node.id)
      const result = await node.handler.execute(ctx)

      trace.status = 'completed'
      trace.output = result
      trace.endedAt = new Date()
      trace.durationMs = trace.endedAt.getTime() - trace.startedAt.getTime()

      await this.eventBus.emit({
        type: 'workflow:step:completed',
        runId: run.runId,
        workflowId: run.workflowId,
        nodeId: node.id,
        stepId: node.handler.id,
        kind: 'listen',
        durationMs: trace.durationMs,
        timestamp: new Date(),
      })

      return result
    } catch (err) {
      if (isSuspendSignal(err)) throw err

      trace.status = 'failed'
      trace.error = String(err)
      trace.endedAt = new Date()
      trace.durationMs = trace.endedAt.getTime() - trace.startedAt.getTime()

      await this.eventBus.emit({
        type: 'workflow:step:failed',
        runId: run.runId,
        workflowId: run.workflowId,
        nodeId: node.id,
        stepId: node.handler.id,
        kind: 'listen',
        error: String(err),
        attempt: 0,
        willRetry: false,
        timestamp: new Date(),
      })

      throw err
    }
  }

  // State machine (graph-based)

  private async executeStateMachineNode(
    node: StateMachineNode,
    input: unknown,
    run: WorkflowRun,
  ): Promise<unknown> {
    const wfEventBus = this.eventBuses.get(run.runId)
    const executor = new StateMachineExecutor({
      logger: this.logger,
      eventBus: this.eventBus,
      buildContext: (stepInput, stepRun, nodeId) => this.buildContext(stepInput, stepRun, nodeId),
      workflowEventBus: wfEventBus,
    })

    const result = await executor.execute(node, input, run)
    return result.output
  }

  // Helpers

  private buildContext(input: unknown, run: WorkflowRun, nodeId: string): StepContext {
    const wfEventBus = this.eventBuses.get(run.runId)

    return {
      input,
      state: run.state,
      setState: (patch: Record<string, unknown>) => {
        Object.assign(run.state, patch)
      },
      logger: this.logger.child(nodeId),
      eventBus: this.eventBus,
      emit: (channel: string, data: unknown) => {
        // WHY: Feed into the WorkflowEventBus so ListenNodes can react
        if (wfEventBus) {
          wfEventBus.emit(channel, data, nodeId)
        }
      },
      suspend: (reason: string): never => {
        throw new SuspendSignal(reason, nodeId)
      },
      runId: run.runId,
      workflowId: run.workflowId,
      attempt: 0,
    }
  }

  private async withTimeout<T>(promise: Promise<T>, timeoutMs: number, label: string): Promise<T> {
    if (timeoutMs <= 0) return promise

    return new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => {
        reject(new Error(`Step "${label}" timed out after ${timeoutMs}ms`))
      }, timeoutMs)

      promise
        .then((result) => {
          clearTimeout(timer)
          resolve(result)
        })
        .catch((err) => {
          clearTimeout(timer)
          reject(err)
        })
    })
  }

  private computeRetryDelay(attempt: number, policy: NonNullable<WorkflowStep['retry']>): number {
    const base = policy.delayMs ?? 1000
    const multiplier = policy.backoffMultiplier ?? 2
    const maxDelay = policy.maxDelayMs ?? 30_000
    const delay = Math.min(base * Math.pow(multiplier, attempt), maxDelay)
    return delay
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms))
  }

  /** Persist a run to the store if one is configured. */
  private persist(run: WorkflowRun): void {
    if (!this.store) return
    try {
      this.store.save(run)
    } catch (err) {
      this.logger.warn('Failed to persist workflow run', {
        runId: run.runId,
        error: String(err),
      })
    }
  }
}
