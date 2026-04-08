/**
 * Dialectic Tool Definitions — Meta-tools for inter-posture communication.
 *
 * These tools are handled inline by LumenPostureRunner (not via ToolExecutor).
 * They wrap DialecticChannel operations and provide the LLM-facing interface
 * for real-time dialectic communication between Yang, Yin, and Executive.
 *
 * Three tool sets:
 * - YANG_YIN_TOOLS: shared between Yang and Yin postures (dialectic debate tools)
 * - EXECUTIVE_TOOLS: Executive-only moderation and synthesis tools
 * - CONCLUSION_TOOL: shared signal_conclusion (with hard-gate for Yang/Yin)
 */

import type { CompletionOpts } from '../../../types/runtime.js'

type ToolSchema = NonNullable<CompletionOpts['tools']>[number]

// Yang/Yin Dialectic Tools

export const SHARE_FINDING_TOOL: ToolSchema = {
  name: 'share_finding',
  description:
    'Share a finding with the other specialist. They will see it appended to their next tool result. ' +
    'Use this to communicate discoveries, evidence, and analysis. Be specific and cite evidence.',
  input_schema: {
    type: 'object',
    properties: {
      finding: {
        type: 'string',
        description: 'What you found — be specific and cite evidence (file paths, line numbers, reasoning).',
      },
      evidence: {
        type: 'string',
        description: 'Supporting evidence for this finding.',
      },
      tags: {
        type: 'array',
        items: { type: 'string' },
        description: 'Tags for categorization — use file paths, concept names, or keywords.',
      },
    },
    required: ['finding'],
  },
}

export const CHALLENGE_TOOL: ToolSchema = {
  name: 'challenge',
  description:
    'Challenge a specific finding from the other specialist. ' +
    'You MUST address all challenges directed at your findings before you can conclude. ' +
    'Provide a clear counter-argument with evidence.',
  input_schema: {
    type: 'object',
    properties: {
      finding_id: {
        type: 'string',
        description: 'The ID of the finding to challenge (e.g., "f3"). Visible in messages from the other specialist.',
      },
      counterargument: {
        type: 'string',
        description: 'Your counter-argument explaining why this finding is wrong or incomplete.',
      },
      evidence: {
        type: 'string',
        description: 'Supporting evidence for your counter-argument.',
      },
    },
    required: ['finding_id', 'counterargument'],
  },
}

export const CONCEDE_TOOL: ToolSchema = {
  name: 'concede',
  description:
    'Acknowledge that the other specialist\'s challenge is valid. ' +
    'This resolves the tension and creates a convergence point — both of you now agree. ' +
    'Conceding is a sign of intellectual honesty, not weakness.',
  input_schema: {
    type: 'object',
    properties: {
      challenge_id: {
        type: 'string',
        description: 'The challenge ID to concede (e.g., "c1").',
      },
      reason: {
        type: 'string',
        description: 'Why you concede — what evidence or argument convinced you.',
      },
    },
    required: ['challenge_id'],
  },
}

export const REQUEST_INVESTIGATION_TOOL: ToolSchema = {
  name: 'request_investigation',
  description:
    'Ask the other specialist to investigate a specific area. ' +
    'Use when you find something in their analytical domain that needs their perspective.',
  input_schema: {
    type: 'object',
    properties: {
      area: {
        type: 'string',
        description: 'What to investigate — file path, concept, module, or specific question.',
      },
      reason: {
        type: 'string',
        description: 'Why this needs their attention — what you found that triggered this request.',
      },
    },
    required: ['area', 'reason'],
  },
}

/** All Yang/Yin dialectic tools (excluding signal_conclusion) */
export const YANG_YIN_DIALECTIC_TOOLS: ToolSchema[] = [
  SHARE_FINDING_TOOL,
  CHALLENGE_TOOL,
  CONCEDE_TOOL,
  REQUEST_INVESTIGATION_TOOL,
]

// Executive Moderation Tools

export const INJECT_CONTEXT_TOOL: ToolSchema = {
  name: 'inject_context',
  description:
    'Push relevant context to Yang and/or Yin — memories, past decisions, historical outcomes. ' +
    'They will see it appended to their next tool result as "[context]". ' +
    'Only inject genuinely relevant information. Do NOT take sides.',
  input_schema: {
    type: 'object',
    properties: {
      target: {
        type: 'string',
        enum: ['yang', 'yin', 'both'],
        description: 'Which specialist(s) should receive this context.',
      },
      content: {
        type: 'string',
        description: 'The context to inject — be specific and cite sources.',
      },
      source: {
        type: 'string',
        description: 'Where this context came from (e.g., "archive entry #42", "memory search: auth patterns").',
      },
    },
    required: ['target', 'content'],
  },
}

export const INJECT_STEERING_TOOL: ToolSchema = {
  name: 'inject_steering',
  description:
    'Suggest an investigation direction to Yang and/or Yin. Advisory only — they decide whether to follow. ' +
    'They will see it appended to their next tool result as "[suggestion]". ' +
    'Use this when you spot gaps or when one specialist is missing something.',
  input_schema: {
    type: 'object',
    properties: {
      target: {
        type: 'string',
        enum: ['yang', 'yin', 'both'],
        description: 'Which specialist(s) should receive this suggestion.',
      },
      instruction: {
        type: 'string',
        description: 'The investigation direction or area to look at.',
      },
      reason: {
        type: 'string',
        description: 'Why this investigation is valuable — what gap or oversight prompted it.',
      },
    },
    required: ['target', 'instruction'],
  },
}

export const REVIEW_DIALECTIC_LOG_TOOL: ToolSchema = {
  name: 'review_dialectic_log',
  description:
    'Get a live view of the full dialectic — all findings, challenges, concessions, investigation requests, ' +
    'plus whether Yang and Yin have concluded. Call this frequently to monitor the debate.',
  input_schema: {
    type: 'object',
    properties: {},
  },
}

/** All Executive moderation tools (excluding signal_conclusion) */
export const EXECUTIVE_MODERATION_TOOLS: ToolSchema[] = [
  INJECT_CONTEXT_TOOL,
  INJECT_STEERING_TOOL,
  REVIEW_DIALECTIC_LOG_TOOL,
]

// Signal Conclusion (shared, but gated differently per posture)

export const SIGNAL_CONCLUSION_TOOL: ToolSchema = {
  name: 'signal_conclusion',
  description:
    'Signal your final conclusion for this analysis. ' +
    'For Yang/Yin: BLOCKED if you have unresolved challenges — you must concede or provide counter-evidence first. ' +
    'For Executive: BLOCKED until both Yang and Yin have concluded.',
  input_schema: {
    type: 'object',
    properties: {
      conclusion: {
        type: 'string',
        description: 'Your final conclusion, assessment, or synthesis.',
      },
      confidence: {
        type: 'number',
        description: 'Confidence level (0.0 = speculative, 1.0 = certain).',
      },
      key_points: {
        type: 'array',
        items: { type: 'string' },
        description: 'Key points from your analysis (1-5 items).',
      },
      recommendation: {
        type: 'string',
        enum: ['proceed', 'reconsider', 'abort'],
        description: 'Executive only: final recommendation.',
      },
    },
    required: ['conclusion'],
  },
}

// Meta-Tool Name Sets (for inline handling in LumenPostureRunner)

export const YANG_YIN_META_TOOL_NAMES = new Set([
  'share_finding',
  'challenge',
  'concede',
  'request_investigation',
  'signal_conclusion',
])

export const EXECUTIVE_META_TOOL_NAMES = new Set([
  'inject_context',
  'inject_steering',
  'review_dialectic_log',
  'signal_conclusion',
])

/**
 * Check if a tool name is a dialectic meta-tool (handled inline, not via ToolExecutor).
 * @dep callers: lumen.test.ts (tests/lumen.test.ts), processToolCalls (core/intelligence/lumen/lumen-posture-runner.ts), buildToolSchemas (core/intelligence/lumen/lumen-posture-runner.ts)
 * @dep calls: has
 * @dep flows: Run → IsDialecticMetaTool (3/3)
 * @dep module: Lumen
 * @dep risk: LOW | 3 callers, 1 flow, 1 module
 */
export function isDialecticMetaTool(name: string, posture: 'yang' | 'yin' | 'executive' | 'mentor'): boolean {
  if (posture === 'executive') return EXECUTIVE_META_TOOL_NAMES.has(name)
  // Mentor uses Yang/Yin dialectic tools (findings, challenges, concessions)
  return YANG_YIN_META_TOOL_NAMES.has(name)
}
