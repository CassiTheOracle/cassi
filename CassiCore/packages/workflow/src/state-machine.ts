/**
 * StateMachineExecutor — runs a state machine definition within a workflow.
 *
 * The executor loops through states by evaluating transitions:
 *   1. Enter a state (run onEnter step if defined)
 *   2. Evaluate outgoing transitions in order
 *   3. First transition whose guard passes (or has no guard) fires
 *   4. Run the transition's action (if any), then move to target state
 *   5. Repeat until a final state is reached or limits are hit
 *
 * Event-based transitions integrate with WorkflowEventBus: if a transition
 * has an `event` channel, the executor waits for that event before evaluating
 * the guard. Non-event transitions evaluate immediately.
 */

import type {
  StateMachineNode,
  StateDefinition,
  TransitionDefinition,
  WorkflowRun,
  StepContext,
  StepTrace,
  WorkflowState,
} from '../../types/workflow.js'
import type { ILogger, IEventBus } from '../../types/interfaces.js'
import type { WorkflowEventBus } from './events.js'

export interface StateMachineExecutorConfig {
  logger: ILogger
  eventBus: IEventBus
  buildContext: (input: unknown, run: WorkflowRun, nodeId: string) => StepContext
  workflowEventBus?: WorkflowEventBus
}

export interface StateMachineResult {
  /** The final state name. */
  finalState: string
  /** Output from the final state's onEnter step (or last transition action). */
  output: unknown
  /** Total number of transitions taken. */
  transitionCount: number
  /** Ordered list of state names visited. */
  stateHistory: string[]
}

/** Internal result from evaluateTransitions — carries event data for event-based transitions. */
interface TransitionMatch {
  transition: TransitionDefinition
  /** If the transition was event-based, the data from the event. */
  eventData?: unknown
}

export class StateMachineExecutor {
  private readonly logger: ILogger
  private readonly eventBus: IEventBus
  private readonly buildContext: (input: unknown, run: WorkflowRun, nodeId: string) => StepContext
  private readonly workflowEventBus?: WorkflowEventBus

  constructor(config: StateMachineExecutorConfig) {
    this.logger = config.logger.child('state-machine')
    this.eventBus = config.eventBus
    this.buildContext = config.buildContext
    this.workflowEventBus = config.workflowEventBus
  }

  async execute(
    node: StateMachineNode,
    input: unknown,
    run: WorkflowRun,
  ): Promise<StateMachineResult> {
    const stateMap = this.buildStateMap(node)
    const maxTransitions = node.maxTransitions ?? 100
    const timeoutMs = node.timeoutMs ?? 300_000

    // Find initial state
    const initialState = node.states.find((s) => s.initial)
    if (!initialState) {
      throw new Error(`State machine "${node.id}": no initial state defined`)
    }

    // Validate at least one final state exists
    const hasFinal = node.states.some((s) => s.final)
    if (!hasFinal) {
      throw new Error(`State machine "${node.id}": no final state defined`)
    }

    const trace: StepTrace = {
      nodeId: node.id,
      kind: 'statemachine',
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
      kind: 'statemachine',
      attempt: 0,
      timestamp: new Date(),
    })

    const startTime = Date.now()
    let currentState = initialState
    let currentInput = input
    let transitionCount = 0
    const stateHistory: string[] = [currentState.name]

    try {
      while (!currentState.final) {
        // Check transition limit
        if (transitionCount >= maxTransitions) {
          throw new Error(
            `State machine "${node.id}": hit max transitions (${maxTransitions}) ` +
            `at state "${currentState.name}"`,
          )
        }

        // Check timeout
        if (timeoutMs > 0 && Date.now() - startTime > timeoutMs) {
          throw new Error(
            `State machine "${node.id}": timed out after ${timeoutMs}ms ` +
            `at state "${currentState.name}"`,
          )
        }

        // Execute onEnter step if defined
        if (currentState.onEnter) {
          const ctx = this.buildContext(currentInput, run, `${node.id}.${currentState.name}`)
          currentInput = await currentState.onEnter.execute(ctx)
        }

        // Evaluate transitions
        const match = await this.evaluateTransitions(
          currentState,
          currentInput,
          run.state,
          timeoutMs > 0 ? Math.max(0, timeoutMs - (Date.now() - startTime)) : 0,
        )

        if (!match) {
          throw new Error(
            `State machine "${node.id}": no valid transition from state "${currentState.name}" ` +
            `(deadlock — all guards failed and no fallback)`,
          )
        }

        // WHY: For event-based transitions, the transition action should receive
        // the event data instead of the current input, enabling data flow from
        // events through the state machine.
        if (match.transition.action) {
          const actionInput = match.eventData !== undefined ? match.eventData : currentInput
          currentInput = await match.transition.action(actionInput, run.state)
        } else if (match.eventData !== undefined) {
          // WHY: Even without an action, event data should flow through
          currentInput = match.eventData
        }

        // Move to target state
        const targetState = stateMap.get(match.transition.target)
        if (!targetState) {
          throw new Error(
            `State machine "${node.id}": transition targets unknown state "${match.transition.target}"`,
          )
        }

        transitionCount++
        currentState = targetState
        stateHistory.push(currentState.name)

        this.logger.debug('State transition', {
          machineId: node.id,
          from: stateHistory[stateHistory.length - 2],
          to: currentState.name,
          transitionCount,
        })
      }

      // Execute final state's onEnter if defined
      if (currentState.onEnter) {
        const ctx = this.buildContext(currentInput, run, `${node.id}.${currentState.name}`)
        currentInput = await currentState.onEnter.execute(ctx)
      }

      trace.status = 'completed'
      trace.output = currentInput
      trace.endedAt = new Date()
      trace.durationMs = trace.endedAt.getTime() - trace.startedAt.getTime()

      await this.eventBus.emit({
        type: 'workflow:step:completed',
        runId: run.runId,
        workflowId: run.workflowId,
        nodeId: node.id,
        kind: 'statemachine',
        durationMs: trace.durationMs,
        timestamp: new Date(),
      })

      return {
        finalState: currentState.name,
        output: currentInput,
        transitionCount,
        stateHistory,
      }
    } catch (err) {
      trace.status = 'failed'
      trace.error = String(err)
      trace.endedAt = new Date()
      trace.durationMs = trace.endedAt.getTime() - trace.startedAt.getTime()

      await this.eventBus.emit({
        type: 'workflow:step:failed',
        runId: run.runId,
        workflowId: run.workflowId,
        nodeId: node.id,
        kind: 'statemachine',
        error: String(err),
        attempt: 0,
        willRetry: false,
        timestamp: new Date(),
      })

      throw err
    }
  }

  /** Evaluate transitions in order. First matching (guard passes or no guard) wins. */
  private async evaluateTransitions(
    state: StateDefinition,
    input: unknown,
    workflowState: WorkflowState,
    remainingTimeoutMs: number,
  ): Promise<TransitionMatch | undefined> {
    for (const transition of state.transitions) {
      // Skip event-based transitions in synchronous evaluation
      if (transition.event) continue

      if (!transition.guard) {
        return { transition }
      }

      const passes = await transition.guard(input, workflowState)
      if (passes) {
        return { transition }
      }
    }

    // Check event-based transitions if no immediate transition matched
    if (this.workflowEventBus) {
      const eventTransitions = state.transitions.filter((t) => t.event)
      if (eventTransitions.length > 0) {
        return this.waitForEventTransition(eventTransitions, input, workflowState, remainingTimeoutMs)
      }
    }

    return undefined
  }

  /** Wait for an event that matches one of the event-based transitions. */
  private async waitForEventTransition(
    transitions: TransitionDefinition[],
    input: unknown,
    workflowState: WorkflowState,
    remainingTimeoutMs: number,
  ): Promise<TransitionMatch | undefined> {
    if (!this.workflowEventBus) return undefined

    const channels = transitions
      .map((t) => t.event!)
      .filter((ch, i, arr) => arr.indexOf(ch) === i)

    const effectiveTimeout = remainingTimeoutMs > 0 ? remainingTimeoutMs : 60_000
    const event = await this.workflowEventBus.waitFor(channels, { timeoutMs: effectiveTimeout })

    // Find the matching transition for this event
    for (const transition of transitions) {
      if (transition.event !== event.channel) continue

      if (!transition.guard) return { transition, eventData: event.data }

      const passes = await transition.guard(event.data, workflowState)
      if (passes) return { transition, eventData: event.data }
    }

    return undefined
  }

  private buildStateMap(node: StateMachineNode): Map<string, StateDefinition> {
    const map = new Map<string, StateDefinition>()
    for (const state of node.states) {
      if (map.has(state.name)) {
        throw new Error(`State machine "${node.id}": duplicate state name "${state.name}"`)
      }
      map.set(state.name, state)
    }
    return map
  }
}
