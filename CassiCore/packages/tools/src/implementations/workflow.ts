/**
 * Workflow Tool — agent-facing interface for the workflow system.
 *
 * Agents use this tool to list, run, resume, check status, and cancel workflows.
 * Workflow definitions are registered in a WorkflowRegistry; this tool exposes
 * them as executable actions.
 *
 * Actions:
 *   - list: List all registered workflow definitions
 *   - run: Execute a workflow by id with input
 *   - status: Check the status of a running/completed workflow run
 *   - resume: Resume a suspended workflow with optional new input
 *   - cancel: Cancel a running or suspended workflow
 *   - runs: List recent workflow runs with optional filters
 */

import type { ToolDefinition, ToolHandler, ToolExecutionContext } from '../types.js'
import type { WorkflowDefinition, IWorkflowStore } from '../../../types/workflow.js'
import type { WorkflowEngine } from '../../workflow/engine.js'

export const workflowDefinition: ToolDefinition = {
  name: 'workflow',
  description:
    'Agent workflow system — list, run, resume, and manage multi-step workflows.\n\n' +
    'Actions:\n' +
    '- list: List all registered workflow definitions available to run\n' +
    '- run: Execute a workflow by id with input data\n' +
    '- status: Check the status of a workflow run by runId\n' +
    '- resume: Resume a suspended workflow with optional new input\n' +
    '- cancel: Cancel a running or suspended workflow\n' +
    '- runs: List recent workflow runs with optional status/workflowId filters',
  parameters: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: ['list', 'run', 'status', 'resume', 'cancel', 'runs'],
        description: 'Action to perform',
      },
      workflowId: {
        type: 'string',
        description: 'Workflow definition id (for "run" and "resume")',
      },
      runId: {
        type: 'string',
        description: 'Workflow run id (for "status", "resume", "cancel")',
      },
      input: {
        type: 'string',
        description: 'JSON-encoded input data for "run" or "resume"',
      },
      status: {
        type: 'string',
        enum: ['pending', 'running', 'completed', 'failed', 'suspended', 'cancelled'],
        description: 'Filter runs by status (for "runs" action)',
      },
      limit: {
        type: 'string',
        description: 'Maximum number of results to return (for "runs" action, default: 20)',
      },
    },
    required: ['action'],
  },
  timeoutMs: 600_000,
  category: 'coordination',
  readOnly: false,
  backend: 'cassi',
  capability: 'workflow.management',
  requiredPermission: 'read-only',
}

/**
 * Create the workflow tool handler.
 *
 * Needs:
 *   - WorkflowEngine instance (for executing and managing runs)
 *   - A registry of workflow definitions (for listing and looking up by id)
 *   - Optionally a store (for loading persisted runs)
 */
export function makeWorkflowHandler(deps: {
  getEngine: () => WorkflowEngine | null
  getDefinitions: () => Map<string, WorkflowDefinition>
  getStore: () => IWorkflowStore | null
}): ToolHandler {
  return async (input: Record<string, unknown>, ctx: ToolExecutionContext): Promise<string> => {
    const engine = deps.getEngine()
    if (!engine) {
      return JSON.stringify({
        error: 'Workflow engine not initialized. The daemon may still be starting.',
      })
    }

    const action = input.action as string

    switch (action) {
      // list: Show all registered workflow definitions
      case 'list': {
        const definitions = deps.getDefinitions()
        const list = [...definitions.values()].map((def) => ({
          id: def.id,
          description: def.description ?? '(no description)',
          nodeCount: def.nodes.length,
          nodeKinds: def.nodes.map((n) => n.kind),
        }))

        return JSON.stringify({
          workflows: list,
          count: list.length,
        })
      }

      // run: Execute a workflow
      case 'run': {
        const workflowId = input.workflowId as string
        if (!workflowId) {
          return JSON.stringify({ error: 'workflowId is required for the "run" action' })
        }

        const definitions = deps.getDefinitions()
        const definition = definitions.get(workflowId)
        if (!definition) {
          return JSON.stringify({
            error: `Workflow "${workflowId}" not found. Available: ${[...definitions.keys()].join(', ') || '(none)'}`,
          })
        }

        let parsedInput: unknown = {}
        if (input.input) {
          try {
            parsedInput = JSON.parse(input.input as string)
          } catch {
            return JSON.stringify({ error: 'Failed to parse input JSON' })
          }
        }

        ctx.logger.info('Starting workflow via tool', { workflowId, sessionId: ctx.sessionId })

        const run = await engine.execute(definition, parsedInput)

        return JSON.stringify({
          runId: run.runId,
          workflowId: run.workflowId,
          status: run.status,
          output: run.output,
          error: run.error,
          durationMs: run.durationMs,
          stepsExecuted: run.trace.length,
          suspendReason: run.suspendReason,
        })
      }

      // status: Check a run's status
      case 'status': {
        const runId = input.runId as string
        if (!runId) {
          return JSON.stringify({ error: 'runId is required for the "status" action' })
        }

        const run = engine.getRun(runId)
        if (!run) {
          return JSON.stringify({ error: `Workflow run "${runId}" not found` })
        }

        return JSON.stringify({
          runId: run.runId,
          workflowId: run.workflowId,
          status: run.status,
          output: run.output,
          error: run.error,
          currentNodeId: run.currentNodeId,
          suspendedAtNodeId: run.suspendedAtNodeId,
          suspendReason: run.suspendReason,
          durationMs: run.durationMs,
          stepsExecuted: run.trace.length,
          trace: run.trace.map((t) => ({
            nodeId: t.nodeId,
            stepId: t.stepId,
            kind: t.kind,
            status: t.status,
            durationMs: t.durationMs,
            error: t.error,
          })),
          startedAt: run.startedAt.toISOString(),
          endedAt: run.endedAt?.toISOString(),
        })
      }

      // resume: Resume a suspended workflow
      case 'resume': {
        const runId = input.runId as string
        const workflowId = input.workflowId as string

        if (!runId) {
          return JSON.stringify({ error: 'runId is required for the "resume" action' })
        }
        if (!workflowId) {
          return JSON.stringify({ error: 'workflowId is required for the "resume" action (to look up the definition)' })
        }

        const definitions = deps.getDefinitions()
        const definition = definitions.get(workflowId)
        if (!definition) {
          return JSON.stringify({ error: `Workflow "${workflowId}" not found` })
        }

        let resumeInput: unknown | undefined
        if (input.input) {
          try {
            resumeInput = JSON.parse(input.input as string)
          } catch {
            return JSON.stringify({ error: 'Failed to parse resume input JSON' })
          }
        }

        ctx.logger.info('Resuming workflow via tool', { runId, workflowId })

        try {
          const run = await engine.resume(definition, runId, resumeInput)

          return JSON.stringify({
            runId: run.runId,
            workflowId: run.workflowId,
            status: run.status,
            output: run.output,
            error: run.error,
            durationMs: run.durationMs,
            stepsExecuted: run.trace.length,
            suspendReason: run.suspendReason,
          })
        } catch (err) {
          return JSON.stringify({ error: String(err) })
        }
      }

      // cancel: Cancel a running/suspended workflow
      case 'cancel': {
        const runId = input.runId as string
        if (!runId) {
          return JSON.stringify({ error: 'runId is required for the "cancel" action' })
        }

        const reason = (input.input as string) ?? 'Cancelled via workflow tool'

        try {
          await engine.cancel(runId, reason)
          const run = engine.getRun(runId)
          return JSON.stringify({
            runId,
            status: run?.status ?? 'unknown',
            message: 'Workflow cancelled',
          })
        } catch (err) {
          return JSON.stringify({ error: String(err) })
        }
      }

      // runs: List recent workflow runs
      case 'runs': {
        const store = deps.getStore()
        const statusFilter = input.status as string | undefined
        const workflowIdFilter = input.workflowId as string | undefined
        const limit = parseInt(input.limit as string ?? '20', 10)

        // Prefer store for comprehensive history; fall back to engine's in-memory runs
        if (store) {
          const runs = store.list({
            status: statusFilter as any,
            workflowId: workflowIdFilter,
            limit,
          })
          return JSON.stringify({
            runs: runs.map((r) => ({
              runId: r.runId,
              workflowId: r.workflowId,
              status: r.status,
              durationMs: r.durationMs,
              stepsExecuted: r.trace.length,
              suspendReason: r.suspendReason,
              error: r.error,
              startedAt: r.startedAt.toISOString(),
              endedAt: r.endedAt?.toISOString(),
            })),
            count: runs.length,
            source: 'store',
          })
        }

        // Fallback: in-memory only
        let runs = engine.listRuns()
        if (statusFilter) {
          runs = runs.filter((r) => r.status === statusFilter)
        }
        if (workflowIdFilter) {
          runs = runs.filter((r) => r.workflowId === workflowIdFilter)
        }

        return JSON.stringify({
          runs: runs.slice(0, limit).map((r) => ({
            runId: r.runId,
            workflowId: r.workflowId,
            status: r.status,
            durationMs: r.durationMs,
            stepsExecuted: r.trace.length,
            suspendReason: r.suspendReason,
            error: r.error,
            startedAt: r.startedAt.toISOString(),
            endedAt: r.endedAt?.toISOString(),
          })),
          count: Math.min(runs.length, limit),
          source: 'memory',
        })
      }

      default:
        return JSON.stringify({
          error: `Unknown action: "${action}". Available: list, run, status, resume, cancel, runs`,
        })
    }
  }
}
