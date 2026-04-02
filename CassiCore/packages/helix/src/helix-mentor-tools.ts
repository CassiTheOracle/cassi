/**
 * Helix Mentor Tools — Meta-tools for the Mentor (dialectic moderator) posture.
 *
 * The Mentor observes the Yang↔Yin dialectic, steers when stuck,
 * forces conclusions when stalled, and produces the final synthesis.
 *
 * Four tool categories:
 *   - Steering: inject guidance into the dialectic
 *   - Moderation: force conclusion, flag non-compliance
 *   - Research orchestration: dispatch deeper investigation
 *   - Synthesis: produce the final integrated summary
 */

import type { CompletionOpts } from '../../../types/runtime.js'

type ToolSchema = NonNullable<CompletionOpts['tools']>[number]



export const MENTOR_STEER_TOOL: ToolSchema = {
  name: 'mentor_steer',
  description:
    'Inject a steering directive into the dialectic. Posts to the blackboard requests channel ' +
    'for shared visibility. Use when reviewers are going off-track, missing key aspects, ' +
    'or when you want to redirect their focus. This is advisory — not forced.',
  input_schema: {
    type: 'object',
    properties: {
      directive: {
        type: 'string',
        description: 'The steering directive — what should reviewers focus on or change.',
      },
      target: {
        type: 'string',
        enum: ['both', 'yang', 'yin', 'unity'],
        description: 'Who this directive targets. Default: both reviewers.',
      },
      priority: {
        type: 'string',
        enum: ['low', 'medium', 'high'],
        description: 'Urgency of the steering. High = should be addressed immediately.',
      },
    },
    required: ['directive'],
  },
}

export const MENTOR_FLAG_TOOL: ToolSchema = {
  name: 'mentor_flag',
  description:
    'Flag an issue discovered by observing the dialectic. Posts to the concerns channel. ' +
    'Use when you notice: circular arguments, missed edge cases, incorrect assumptions, ' +
    'or when one posture is dominating unfairly.',
  input_schema: {
    type: 'object',
    properties: {
      issue: {
        type: 'string',
        description: 'Description of the issue observed in the dialectic.',
      },
      issue_type: {
        type: 'string',
        enum: ['circular_argument', 'missed_point', 'incorrect_assumption', 'dominance', 'stall', 'scope_creep'],
        description: 'Category of the issue.',
      },
    },
    required: ['issue', 'issue_type'],
  },
}



export const MENTOR_FORCE_CONCLUSION_TOOL: ToolSchema = {
  name: 'mentor_force_conclusion',
  description:
    'Force the dialectic toward conclusion when reviewers are stalled or going in circles. ' +
    'Summarize the current state of agreement/disagreement and ask both sides to converge. ' +
    'This posts a high-priority decision to the blackboard and sends a nudge to Unity.',
  input_schema: {
    type: 'object',
    properties: {
      summary: {
        type: 'string',
        description: 'Summary of the current dialectic state — what is agreed, what is contested.',
      },
      recommendation: {
        type: 'string',
        description: 'Your recommended path forward based on the dialectic.',
      },
      confidence: {
        type: 'number',
        description: 'Your confidence in the recommendation (0.0-1.0).',
      },
    },
    required: ['summary', 'recommendation', 'confidence'],
  },
}

export const MENTOR_DISPATCH_RESEARCH_TOOL: ToolSchema = {
  name: 'mentor_dispatch_research',
  description:
    'Dispatch a focused research mission for Yang or Yin. Use when the dialectic needs '
    + 'deeper evidence, source confirmation, or structured investigation before converging.',
  input_schema: {
    type: 'object',
    properties: {
      query: {
        type: 'string',
        description: 'The concrete research mission to investigate.',
      },
      target: {
        type: 'string',
        enum: ['yang', 'yin', 'both'],
        description: 'Which reviewer(s) should receive and use the research results.',
      },
      rationale: {
        type: 'string',
        description: 'Why this research matters to the current dialectic.',
      },
      priority: {
        type: 'string',
        enum: ['low', 'medium', 'high'],
        description: 'Urgency of the research task.',
      },
    },
    required: ['query', 'target'],
  },
}



export const MENTOR_SYNTHESIZE_TOOL: ToolSchema = {
  name: 'mentor_synthesize',
  description:
    'Produce the final synthesis of the Helix session. Integrates Unity\'s work output, ' +
    'Yang\'s strengths analysis, Yin\'s risk analysis, and dialectic convergence points ' +
    'into a coherent conclusion. This is the Mentor\'s primary deliverable.',
  input_schema: {
    type: 'object',
    properties: {
      synthesis: {
        type: 'string',
        description: 'The integrated synthesis — combines all posture perspectives into a coherent whole.',
      },
      recommendation: {
        type: 'string',
        enum: ['proceed', 'proceed-with-caution', 'revise', 'reject'],
        description: 'Overall recommendation based on the synthesis.',
      },
      confidence: {
        type: 'number',
        description: 'Confidence in the synthesis (0.0-1.0).',
      },
      key_findings: {
        type: 'array',
        items: { type: 'string' },
        description: 'Top findings from the session (1-5 items).',
      },
      remaining_risks: {
        type: 'array',
        items: { type: 'string' },
        description: 'Unresolved risks or tensions (0-5 items).',
      },
    },
    required: ['synthesis', 'recommendation', 'confidence'],
  },
}



/** All Mentor meta-tools */
export const MENTOR_TOOLS: ToolSchema[] = [
  MENTOR_STEER_TOOL,
  MENTOR_FLAG_TOOL,
  MENTOR_FORCE_CONCLUSION_TOOL,
  MENTOR_DISPATCH_RESEARCH_TOOL,
  MENTOR_SYNTHESIZE_TOOL,
]

/** Mentor tool names for routing */
export const MENTOR_TOOL_NAMES = new Set(MENTOR_TOOLS.map(t => t.name))

/** Check if a tool is a Mentor meta-tool */
export function isMentorMetaTool(toolName: string): boolean {
  return MENTOR_TOOL_NAMES.has(toolName)
}
