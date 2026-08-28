/**
 * Plan Tool Definitions — Meta-tools for structured planning on the Blackboard.
 *
 * These tools are handled inline by LumenPostureRunner (not via ToolExecutor).
 * They wrap PlanHandler operations and provide the LLM-facing interface
 * for building structured plans during FluxTeam execution.
 *
 * Two tool sets:
 * - ALL_POSTURES_PLAN_TOOLS: submit steps, view plan (available to Yang, Yin, Executive)
 * - EXECUTIVE_PLAN_TOOLS: approve, reject, update, finalize (Executive only)
 */

import type { CompletionOpts } from '@cassicore/foundation'

type ToolSchema = NonNullable<CompletionOpts['tools']>[number]

// All-Posture Plan Tools (Yang, Yin, Executive)

export const PLAN_SUBMIT_STEP_TOOL: ToolSchema = {
  name: 'plan_submit_step',
  description:
    'Submit a new step to the plan. Steps start as "proposed" and must be approved by the Executive. ' +
    'Use this to propose concrete, actionable implementation steps based on your investigation. ' +
    'Be specific about what needs to be done, which files/modules are involved, and the expected outcome.',
  input_schema: {
    type: 'object',
    properties: {
      title: {
        type: 'string',
        description: 'Short, descriptive title for the step (e.g., "Parallelize intelligence module init").',
      },
      description: {
        type: 'string',
        description: 'Detailed description of what this step entails, including specific files, functions, and expected changes.',
      },
      order: {
        type: 'number',
        description: 'Execution order (lower = earlier). Steps with the same order can run in parallel.',
      },
      priority: {
        type: 'string',
        enum: ['high', 'medium', 'low'],
        description: 'Priority level. Default: medium.',
      },
      dependencies: {
        type: 'array',
        items: { type: 'string' },
        description: 'IDs of steps that must complete before this one can start.',
      },
      tags: {
        type: 'array',
        items: { type: 'string' },
        description: 'Tags for categorization (e.g., file paths, module names, risk levels).',
      },
    },
    required: ['title', 'description'],
  },
}

export const PLAN_VIEW_TOOL: ToolSchema = {
  name: 'plan_view',
  description:
    'View the current plan with all steps and their statuses. ' +
    'Call this to see what has been proposed, approved, rejected, or completed.',
  input_schema: {
    type: 'object',
    properties: {},
  },
}

// Executive-Only Plan Tools

export const PLAN_APPROVE_STEP_TOOL: ToolSchema = {
  name: 'plan_approve_step',
  description:
    'Approve a proposed plan step. Only the Executive can approve steps. ' +
    'Review the step carefully — approved steps will guide implementation.',
  input_schema: {
    type: 'object',
    properties: {
      step_id: {
        type: 'string',
        description: 'The ID of the step to approve (e.g., "step-a1b2c3d4").',
      },
    },
    required: ['step_id'],
  },
}

export const PLAN_REJECT_STEP_TOOL: ToolSchema = {
  name: 'plan_reject_step',
  description:
    'Reject a proposed plan step with a reason. Only the Executive can reject steps. ' +
    'Provide a clear explanation so the proposer can revise or submit an alternative.',
  input_schema: {
    type: 'object',
    properties: {
      step_id: {
        type: 'string',
        description: 'The ID of the step to reject.',
      },
      reason: {
        type: 'string',
        description: 'Why this step is being rejected — be specific so the agent can improve.',
      },
    },
    required: ['step_id', 'reason'],
  },
}

export const PLAN_UPDATE_STEP_TOOL: ToolSchema = {
  name: 'plan_update_step',
  description:
    'Update fields of an existing plan step. Only the Executive can update steps. ' +
    'Use this to refine descriptions, reorder steps, change priority, or update status.',
  input_schema: {
    type: 'object',
    properties: {
      step_id: {
        type: 'string',
        description: 'The ID of the step to update.',
      },
      title: {
        type: 'string',
        description: 'New title for the step.',
      },
      description: {
        type: 'string',
        description: 'New description for the step.',
      },
      order: {
        type: 'number',
        description: 'New execution order.',
      },
      priority: {
        type: 'string',
        enum: ['high', 'medium', 'low'],
        description: 'New priority level.',
      },
      status: {
        type: 'string',
        enum: ['proposed', 'approved', 'rejected', 'in_progress', 'completed', 'blocked'],
        description: 'New status for the step.',
      },
      dependencies: {
        type: 'array',
        items: { type: 'string' },
        description: 'Updated dependency step IDs.',
      },
      tags: {
        type: 'array',
        items: { type: 'string' },
        description: 'Updated tags.',
      },
      outcome: {
        type: 'string',
        description: 'Outcome text (typically set when marking a step as completed).',
      },
    },
    required: ['step_id'],
  },
}

export const PLAN_FINALIZE_TOOL: ToolSchema = {
  name: 'plan_finalize',
  description:
    'Finalize the plan. Only the Executive can finalize. ' +
    'Call this when the plan is ready for implementation (status: "approved"), ' +
    'when all steps are done (status: "completed"), or to abandon the plan (status: "abandoned"). ' +
    'Provide a summary of the plan and any important notes for implementers.',
  input_schema: {
    type: 'object',
    properties: {
      status: {
        type: 'string',
        enum: ['approved', 'completed', 'abandoned'],
        description: 'Final plan status. Use "approved" for research teams (plan ready to be followed), "completed" for implementation teams (work done).',
      },
      summary: {
        type: 'string',
        description: 'Summary of the plan — key decisions, rationale, implementation notes, and any caveats.',
      },
    },
    required: ['status'],
  },
}

// Tool Set Exports

/**
 * Plan tools available to all postures (Yang, Yin, Executive).
 */
export const ALL_POSTURES_PLAN_TOOLS: ToolSchema[] = [
  PLAN_SUBMIT_STEP_TOOL,
  PLAN_VIEW_TOOL,
]

/**
 * Plan tools available only to the Executive posture.
 */
export const EXECUTIVE_PLAN_TOOLS: ToolSchema[] = [
  PLAN_APPROVE_STEP_TOOL,
  PLAN_REJECT_STEP_TOOL,
  PLAN_UPDATE_STEP_TOOL,
  PLAN_FINALIZE_TOOL,
]

/**
 * Get plan tool schemas for a given posture.
 *
 * @param posture - The posture requesting tools
 * @returns Array of tool schemas for that posture
 */
export function getPlanToolSchemas(posture: 'yang' | 'yin' | 'executive' | 'mentor'): ToolSchema[] {
  if (posture === 'executive') {
    return [...ALL_POSTURES_PLAN_TOOLS, ...EXECUTIVE_PLAN_TOOLS]
  }
  return [...ALL_POSTURES_PLAN_TOOLS]
}

/**
 * Set of all plan meta-tool names for routing checks.
 */
export const PLAN_META_TOOL_NAMES = new Set([
  'plan_submit_step',
  'plan_view',
  'plan_approve_step',
  'plan_reject_step',
  'plan_update_step',
  'plan_finalize',
])

/**
 * Check if a tool name is a plan meta-tool (handled inline, not via ToolExecutor).
 * @dep callers: plan-handler.test.ts (tests/flux-team/plan-handler.test.ts), processToolCalls (core/intelligence/lumen/lumen-posture-runner.ts), buildToolSchemas (core/intelligence/lumen/lumen-posture-runner.ts)
 * @dep calls: has
 * @dep module: Lumen
 * @dep risk: LOW | 3 callers, 0 flows, 1 module
 */
export function isPlanMetaTool(name: string): boolean {
  return PLAN_META_TOOL_NAMES.has(name)
}
