/**
 * ScenarioRunner — executes a WorkflowScenario against a WorkflowBackend.
 *
 * This is the core verification engine. It interprets scenario steps,
 * runs actions against the backend, evaluates assertions, and produces
 * structured results. Works with any backend (live daemon or vitest harness).
 */

import type { EventType } from '@cassicore/foundation'
import type { EventTraceCollector, EventMatcher } from './event-trace.js'
import type { StateSnapshot } from './state-snapshot.js'
import type {
  WorkflowScenario,
  WorkflowBackend,
  ScenarioResult,
  StepResult,
  AssertionResult,
  StepAssertion,
  TurnResult,
} from './scenario-types.js'

export class ScenarioRunner {
  constructor(private backend: WorkflowBackend) {}

  /** Run a full scenario and return structured results */
  async run(scenario: WorkflowScenario): Promise<ScenarioResult> {
    const startTime = Date.now()
    const sessionId = await this.backend.createSession(scenario.setup?.sessionConfig)
    const snapshots = new Map<string, StateSnapshot>()
    const steps: StepResult[] = []
    let lastTurnResult: TurnResult | undefined

    try {
      for (let i = 0; i < scenario.steps.length; i++) {
        const step = scenario.steps[i]
        const stepStart = Date.now()
        const assertions: AssertionResult[] = []

        // Execute action
        const action = step.action
        if (action.type === 'turn') {
          lastTurnResult = await this.backend.executeTurn(sessionId, action.message)
        } else if (action.type === 'wait') {
          await new Promise(r => setTimeout(r, action.ms))
        } else if (action.type === 'snapshot') {
          const snap = await this.backend.snapshot(sessionId)
          snapshots.set(action.label, snap)
        } else if (action.type === 'inject-event') {
          // Inject is only supported by in-process backends; live backends skip
          // (The backend interface could be extended with an optional injectEvent method)
        }

        // Evaluate assertions
        if (step.assertions) {
          for (const assertion of step.assertions) {
            const result = await this.evaluateAssertion(assertion, {
              trace: this.backend.trace,
              snapshots,
              lastTurnResult,
              sessionId,
            })
            assertions.push(result)
          }
        }

        steps.push({
          index: i,
          label: step.label,
          passed: assertions.every(a => a.passed),
          durationMs: Date.now() - stepStart,
          assertions,
        })

        // Fail fast — stop on first failed step
        if (!steps[steps.length - 1].passed) break
      }
    } finally {
      // Always clean up
      await this.backend.teardown()
    }

    const trace = this.backend.trace
    const eventTypes = Array.from(new Set(trace.dump().map(e => e.type)))

    return {
      scenario: scenario.name,
      passed: steps.every(s => s.passed),
      durationMs: Date.now() - startTime,
      sessionId,
      steps,
      trace: {
        eventCount: trace.length,
        eventTypes,
      },
    }
  }


  private async evaluateAssertion(
    assertion: StepAssertion,
    ctx: {
      trace: EventTraceCollector
      snapshots: Map<string, StateSnapshot>
      lastTurnResult?: TurnResult
      sessionId: string
    },
  ): Promise<AssertionResult> {
    try {
      switch (assertion.type) {
        case 'event-emitted': {
          ctx.trace.assertContains({ type: assertion.event, has: assertion.has })
          return ok(assertion.type, `Found event "${assertion.event}"`)
        }

        case 'event-sequence': {
          const matchers: EventMatcher[] = assertion.events.map(e =>
            typeof e === 'string' ? { type: e as EventType } : { type: e.type as EventType, has: e.has }
          )
          ctx.trace.assertSequence(matchers)
          return ok(assertion.type, `Sequence verified (${assertion.events.length} events)`)
        }

        case 'no-event': {
          ctx.trace.assertNoEvent(assertion.event)
          return ok(assertion.type, `No "${assertion.event}" events found`)
        }

        case 'event-count': {
          const count = ctx.trace.count(assertion.event)
          if (assertion.exact !== undefined && count !== assertion.exact) {
            return fail(assertion.type, `Expected exactly ${assertion.exact} "${assertion.event}" events, got ${count}`)
          }
          if (assertion.min !== undefined && count < assertion.min) {
            return fail(assertion.type, `Expected >= ${assertion.min} "${assertion.event}" events, got ${count}`)
          }
          if (assertion.max !== undefined && count > assertion.max) {
            return fail(assertion.type, `Expected <= ${assertion.max} "${assertion.event}" events, got ${count}`)
          }
          return ok(assertion.type, `Event count for "${assertion.event}": ${count}`)
        }

        case 'session-state': {
          const snap = await this.backend.snapshot(ctx.sessionId)
          const actual = snap.get(`session.${assertion.path}`)

          if (assertion.equals !== undefined) {
            if (actual !== assertion.equals) {
              return fail(assertion.type, `session.${assertion.path}: expected ${JSON.stringify(assertion.equals)}, got ${JSON.stringify(actual)}`)
            }
          }
          if (assertion.greaterThan !== undefined) {
            if (typeof actual !== 'number' || actual <= assertion.greaterThan) {
              return fail(assertion.type, `session.${assertion.path}: expected > ${assertion.greaterThan}, got ${JSON.stringify(actual)}`)
            }
          }
          if (assertion.lessThan !== undefined) {
            if (typeof actual !== 'number' || actual >= assertion.lessThan) {
              return fail(assertion.type, `session.${assertion.path}: expected < ${assertion.lessThan}, got ${JSON.stringify(actual)}`)
            }
          }
          if (assertion.contains !== undefined) {
            if (typeof actual !== 'string' || !actual.includes(assertion.contains)) {
              return fail(assertion.type, `session.${assertion.path}: expected to contain "${assertion.contains}", got ${JSON.stringify(actual)}`)
            }
          }
          return ok(assertion.type, `session.${assertion.path} = ${JSON.stringify(actual)}`)
        }

        case 'snapshot-diff': {
          const before = ctx.snapshots.get(assertion.fromLabel)
          if (!before) {
            return fail(assertion.type, `Snapshot "${assertion.fromLabel}" not found — was a snapshot step run before this?`)
          }
          const after = await this.backend.snapshot(ctx.sessionId)
          const d = before.diff(after)

          if (assertion.changed) {
            for (const path of assertion.changed) {
              const isChanged = d.changed.some(c => c.path === path) || d.added.includes(path)
              if (!isChanged) {
                return fail(assertion.type, `Expected "${path}" to change but it did not`)
              }
            }
          }
          if (assertion.unchanged) {
            for (const path of assertion.unchanged) {
              const isChanged = d.changed.some(c => c.path === path) || d.added.includes(path) || d.removed.includes(path)
              if (isChanged) {
                return fail(assertion.type, `Expected "${path}" to be unchanged but it changed`)
              }
            }
          }
          return ok(assertion.type, `Diff verified against "${assertion.fromLabel}"`)
        }

        case 'response-contains': {
          if (!ctx.lastTurnResult) {
            return fail(assertion.type, 'No turn result available')
          }
          if (!ctx.lastTurnResult.response.includes(assertion.text)) {
            return fail(assertion.type, `Response does not contain "${assertion.text}"`)
          }
          return ok(assertion.type, `Response contains "${assertion.text}"`)
        }

        case 'response-matches': {
          if (!ctx.lastTurnResult) {
            return fail(assertion.type, 'No turn result available')
          }
          const regex = new RegExp(assertion.pattern)
          if (!regex.test(ctx.lastTurnResult.response)) {
            return fail(assertion.type, `Response does not match /${assertion.pattern}/`)
          }
          return ok(assertion.type, `Response matches /${assertion.pattern}/`)
        }

        case 'custom': {
          await assertion.check(ctx)
          return ok(assertion.type, `Custom assertion "${assertion.name}" passed`)
        }

        default:
          return fail('unknown', `Unknown assertion type: ${(assertion as any).type}`)
      }
    } catch (err) {
      return fail(assertion.type, String(err instanceof Error ? err.message : err))
    }
  }
}


/**
 * @dep callers: admin-config.api.test.ts (tests/e2e/admin-config.api.test.ts), admin-health.api.test.ts (tests/e2e/admin-health.api.test.ts), evaluateAssertion (src/testing/verification/scenario-runner.ts)
 * @dep module: Verification
 * @dep risk: LOW | 3 callers, 0 flows, 1 module
 */

function ok(type: string, detail: string): AssertionResult {
  return { type, passed: true, detail }
}

/**
 * @dep callers: evaluateAssertion (src/testing/verification/scenario-runner.ts), logsCommand (src/cli/commands/boot.ts), handleBootCommand (src/cli/commands/boot.ts), handleModelCommand (src/cli/commands/model.ts) [+20]
 * @dep module: Runtime
 * @dep risk: CRITICAL | 26 callers, 0 flows, 1 module
 */

function fail(type: string, detail: string): AssertionResult {
  return { type, passed: false, detail }
}
