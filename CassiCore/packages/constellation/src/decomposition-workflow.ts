/**
 * decomposition-workflow — translate a GoalDecomposition into a WorkflowDefinition.
 *
 * Pure function. No I/O. The Constellation pipeline calls this after fastDecompose()
 * returns, then hands the result to WorkflowEngine.execute(). The engine carries
 * cancellation, persistence, resumption, and trace; we get those uniformly without
 * the pipeline reimplementing them.
 *
 * Strategy mapping:
 *   - 'parallel'    → all subtasks run as branches of a single parallel() node
 *   - 'sequential'  → subtasks chain via then(); helixBranch auto-feeds each
 *                     previous conclusion/synthesis/filesModified into the next
 *                     step's context (see core/workflow/steps.ts:393-403)
 *   - 'tree'        → degrades to parallel with a logger.warn until the
 *                     decomposition schema actually carries dependsOn edges.
 *
 * Single-subtask decompositions are emitted as a single then(helixBranch) — the
 * parallel() wrapper would add a node layer for no behavioural reason.
 */

import { createWorkflow } from '../../workflow/builder.js'
import { helixBranch, type IHelixRunner } from '../../workflow/steps.js'
import type { WorkflowDefinition } from '../../../types/workflow.js'
import type { ILogger } from '../../../types/interfaces.js'
import type { GoalDecomposition, GoalSubTask } from './corpus-types.js'

export interface DecompositionToWorkflowOpts {
  /** Stable id used to derive the workflow id (typically the constellation session id). */
  baseId: string
  /** Helix runner adapter — produced via createHelixRunnerAdapter(). */
  runner: IHelixRunner
  /** Optional logger for tree-degradation warnings. */
  logger?: Pick<ILogger, 'warn'>
  /** Per-subtask timeout in ms. Default 600_000 (10 min). */
  subtaskTimeoutMs?: number
}

const DEFAULT_TIMEOUT_MS = 600_000

export function decompositionToWorkflow(
  decomp: GoalDecomposition,
  opts: DecompositionToWorkflowOpts,
): WorkflowDefinition {
  if (!decomp.subTasks || decomp.subTasks.length === 0) {
    throw new Error('decompositionToWorkflow: decomposition has no subTasks')
  }

  const builder = createWorkflow({
    id: `${opts.baseId}-decomposition`,
    description: `Decomposition workflow for: ${decomp.originalGoal.slice(0, 100)}`,
  })

  const branches = decomp.subTasks.map((st, i) =>
    buildSubtaskStep(st, i, opts.runner, opts.subtaskTimeoutMs ?? DEFAULT_TIMEOUT_MS),
  )

  let strategy = decomp.strategy
  if (strategy === 'tree') {
    opts.logger?.warn?.(
      'decompositionToWorkflow: tree strategy not yet supported; degrading to parallel',
      { baseId: opts.baseId, subTaskCount: decomp.subTasks.length },
    )
    strategy = 'parallel'
  }

  if (branches.length === 1) {
    builder.then(branches[0])
  } else if (strategy === 'sequential') {
    for (const b of branches) builder.then(b)
  } else {
    builder.parallel(branches)
  }

  return builder.commit()
}

type HelixBranchTemplate = 'standard' | 'research' | 'implementation' | 'review' | 'minimal'

function toBranchTemplate(t: GoalSubTask['template']): HelixBranchTemplate {
  if (t === 'meditation' || t === undefined) return 'standard'
  return t
}

function buildSubtaskStep(
  subtask: GoalSubTask,
  index: number,
  runner: IHelixRunner,
  timeoutMs: number,
): ReturnType<typeof helixBranch> {
  const id = `subtask-${index + 1}`
  const contextParts: string[] = []
  if (subtask.context) contextParts.push(subtask.context)
  if (subtask.relevantFiles && subtask.relevantFiles.length > 0) {
    contextParts.push(`Relevant files: ${subtask.relevantFiles.join(', ')}`)
  }
  const context = contextParts.length > 0 ? contextParts.join('\n\n') : undefined

  return helixBranch({
    id,
    description: `Subtask ${index + 1} (priority ${subtask.priority}): ${subtask.goal.slice(0, 60)}`,
    goal: subtask.goal,
    context,
    template: toBranchTemplate(subtask.template),
    runner,
    timeoutMs,
  })
}
