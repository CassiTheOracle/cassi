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
 * Complexity mapping (per-subtask):
 *   - 'flat' / unset   → emit one helixBranch step. One Helix runs the subtask
 *                        end-to-end. Today's behavior.
 *   - 'multi-phase'    → expand into a featureImplementation subworkflow
 *                        (design → implement → review). Each phase is its own
 *                        Helix; HelixResult.conclusion auto-feeds the next
 *                        phase's goal builder. Reserved for substantial
 *                        subtasks (the decomposer's content validator already
 *                        rejected ones that don't meet the cost-discipline
 *                        gate, so by the time we see 'multi-phase' here it's
 *                        legitimate).
 *
 * Single-subtask decompositions are emitted as a single then() — the
 * parallel() wrapper would add a node layer for no behavioural reason.
 */

import { createWorkflow } from './vendor/workflow/builder.js'
import { helixBranch, type IHelixRunner } from './vendor/workflow/steps.js'
import { featureImplementation } from './vendor/workflow/templates.js'
import type { WorkflowDefinition, WorkflowStep } from './vendor/types/workflow.js'
import type { ILogger } from './vendor/types/interfaces.js'
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

function packContext(subtask: GoalSubTask): string | undefined {
  const parts: string[] = []
  if (subtask.context) parts.push(subtask.context)
  if (subtask.relevantFiles && subtask.relevantFiles.length > 0) {
    parts.push(`Relevant files: ${subtask.relevantFiles.join(', ')}`)
  }
  return parts.length > 0 ? parts.join('\n\n') : undefined
}

function buildSubtaskStep(
  subtask: GoalSubTask,
  index: number,
  runner: IHelixRunner,
  timeoutMs: number,
): WorkflowStep | WorkflowDefinition {
  const id = `subtask-${index + 1}`

  if (subtask.complexity === 'multi-phase') {
    return featureImplementation({
      id: `${id}-feature`,
      feature: subtask.goal,
      includeTests: false,
      includeReview: true,
      stepTimeoutMs: timeoutMs,
      runner,
    })
  }

  return helixBranch({
    id,
    description: `Subtask ${index + 1} (priority ${subtask.priority}): ${subtask.goal.slice(0, 60)}`,
    goal: subtask.goal,
    context: packContext(subtask),
    template: toBranchTemplate(subtask.template),
    runner,
    timeoutMs,
  })
}
