/**
 * Helix Tool Definitions — Meta-tools for inter-posture communication.
 *
 * Helix has two communication channels:
 *   - WorkStream: Unity <-> Reviewers (work units, nudges)
 *   - DialecticChannel: Yang <-> Yin reviewers (findings, challenges, concessions)
 *
 * Three tool sets:
 *   - UNITY_TOOLS: acknowledge_nudge, signal_done (worker)
 *   - REVIEWER_TOOLS: share_finding, challenge, concede, send_nudge, signal_conclusion (reviewers)
 *
 * Reuses existing tool definitions from Lumen (dialectic) and Dyad (work stream)
 * where the semantics are identical.
 */

import type { CompletionOpts } from '../../../types/runtime.js'

type ToolSchema = NonNullable<CompletionOpts['tools']>[number]


// ─── Unity Tools (Worker) ──────────────────────────────────────────────────

export const ACKNOWLEDGE_NUDGE_TOOL: ToolSchema = {
  name: 'acknowledge_nudge',
  description:
    'Acknowledge a nudge from a reviewer (Yang or Yin). High-severity nudges BLOCK you until acknowledged. ' +
    'Provide a brief acknowledgment message confirming you understand and will address it.',
  input_schema: {
    type: 'object',
    properties: {
      nudge_id: {
        type: 'string',
        description: 'The ID of the nudge to acknowledge (e.g., "n-1").',
      },
      message: {
        type: 'string',
        description: 'Your acknowledgment message — confirm you understand and will address the nudge.',
      },
    },
    required: ['nudge_id', 'message'],
  },
}

export const SIGNAL_DONE_TOOL: ToolSchema = {
  name: 'signal_done',
  description:
    'Signal that you have completed your work. This opens a final review window for the reviewers. ' +
    'They may send blocking nudges during this window if they find critical issues. ' +
    'Provide your conclusion, confidence, and key points.',
  input_schema: {
    type: 'object',
    properties: {
      conclusion: {
        type: 'string',
        description: 'Your final conclusion — summarize what you accomplished.',
      },
      confidence: {
        type: 'number',
        description: 'Your confidence level (0.0 = speculative, 1.0 = certain).',
      },
      key_points: {
        type: 'array',
        items: { type: 'string' },
        description: 'Key points from your work (1-5 items).',
      },
    },
    required: ['conclusion', 'confidence', 'key_points'],
  },
}

/** Core Unity meta-tools */
export const UNITY_TOOLS: ToolSchema[] = [
  ACKNOWLEDGE_NUDGE_TOOL,
  SIGNAL_DONE_TOOL,
]


// ─── Unity → Brainstem Messaging ───────────────────────────────────────────

export const REPORT_TO_BRAINSTEM_TOOL: ToolSchema = {
  name: 'report_to_brainstem',
  description:
    'Send a structured message to the Brainstem (your supervisor). Use this to:\n' +
    '- Report phase transitions ("Starting Phase 2: SQLite store")\n' +
    '- Flag blockers ("Cannot write file — Serena not activated")\n' +
    '- Ask for guidance ("Should I implement X or Y?")\n' +
    '- Report completion of subtasks ("Phase 1 complete — 350 lines written")\n' +
    'The Brainstem reads these messages when evaluating your work and deciding guidance.',
  input_schema: {
    type: 'object',
    properties: {
      type: {
        type: 'string',
        enum: ['phase_change', 'blocker', 'question', 'progress', 'completion'],
        description: 'The type of report.',
      },
      message: {
        type: 'string',
        description: 'The content of your report — be specific about what happened or what you need.',
      },
      context: {
        type: 'object',
        description: 'Optional structured context (e.g., { phase: 2, filesWritten: 3, linesChanged: 350 }).',
      },
    },
    required: ['type', 'message'],
  },
}


// ─── Reviewer Tools (Yang + Yin) ───────────────────────────────────────────

// Dialectic tools — reuse from Lumen (identical semantics for reviewer debate)
import {
  SHARE_FINDING_TOOL,
  CHALLENGE_TOOL,
  CONCEDE_TOOL,
  REQUEST_INVESTIGATION_TOOL,
  SIGNAL_CONCLUSION_TOOL,
} from '../lumen/dialectic-tools.js'

export {
  SHARE_FINDING_TOOL,
  CHALLENGE_TOOL,
  CONCEDE_TOOL,
  REQUEST_INVESTIGATION_TOOL,
  SIGNAL_CONCLUSION_TOOL,
}

// Research streaming tools — lets reviewers post research findings to the blackboard
export const STREAM_RESEARCH_FINDING_TOOL: ToolSchema = {
  name: 'stream_research_finding',
  description:
    'Stream a research finding to the blackboard for shared visibility. Use this when you discover something ' +
    'during an investigation that all postures should see. This is the incremental version of share_finding ' +
    'for research-in-progress.',
  input_schema: {
    type: 'object',
    properties: {
      content: {
        type: 'string',
        description: 'The finding content — what you discovered.',
      },
      source: {
        type: 'string',
        description: 'Source reference — file path, URL, or line number.',
      },
      confidence: {
        type: 'number',
        description: 'Confidence score from 0.0 to 1.0.',
      },
    },
    required: ['content'],
  },
}

export const POST_RESEARCH_SIGNAL_TOOL: ToolSchema = {
  name: 'post_research_signal',
  description:
    'Post a dialectic signal discovered during research to the concerns channel. ' +
    'Use when your research reveals an edge case, assumption, tension, gap, or alternative. ' +
    'This makes the signal visible to all postures via the blackboard.',
  input_schema: {
    type: 'object',
    properties: {
      signal_type: {
        type: 'string',
        enum: ['edge_case', 'assumption', 'tension', 'gap', 'alternative'],
        description: 'The type of dialectic signal.',
      },
      content: {
        type: 'string',
        description: 'The signal content — what was discovered.',
      },
      references: {
        type: 'string',
        description: 'Comma-separated references (file paths, line numbers).',
      },
    },
    required: ['signal_type', 'content'],
  },
}

// Nudge tool — adapted from Dyad but with reviewer-to-Unity semantics
export const SEND_NUDGE_TOOL: ToolSchema = {
  name: 'send_nudge',
  description:
    'Send a nudge to Unity (the worker). Low-severity nudges are advisory (injected into Unity\'s next tool result). ' +
    'High-severity nudges BLOCK Unity until acknowledged — use sparingly for critical issues only.',
  input_schema: {
    type: 'object',
    properties: {
      severity: {
        type: 'string',
        enum: ['low', 'high'],
        description: 'Severity level: low=advisory (non-blocking), high=blocking (Unity must acknowledge).',
      },
      content: {
        type: 'string',
        description: 'The nudge content — advice, warning, or course-correction. Max 500 chars.',
      },
      work_unit_id: {
        type: 'string',
        description: 'The work unit ID this nudge relates to (e.g., "wu-3").',
      },
    },
    required: ['severity', 'content'],
  },
}

// Review progress tool — lets reviewers see Unity's progress
export const REVIEW_PROGRESS_TOOL: ToolSchema = {
  name: 'review_progress',
  description:
    'Get a live view of Unity\'s work progress — all work units, your dialectic state with the other reviewer, ' +
    'and whether Unity has signaled done. Call this to monitor the pipeline.',
  input_schema: {
    type: 'object',
    properties: {},
  },
}


// ─── Edit Proposal Tools (Yang/Yin) ──────────────────────────────────────

/**
 * propose_edit — Yang or Yin can propose a file edit through the dialectic.
 * The edit must be approved by the peer posture and then the Brainstem.
 */
export const PROPOSE_EDIT_TOOL: ToolSchema = {
  name: 'propose_edit',
  description:
    'Propose a file edit through the dialectic approval process. ' +
    'Your proposal will be reviewed by the other reviewer, then by the Brainstem before being applied. ' +
    'Use this when you identify a concrete change that should be made. ' +
    'Provide the exact old content to replace and the new content.',
  input_schema: {
    type: 'object',
    properties: {
      file_path: {
        type: 'string',
        description: 'The file path to edit (relative to project root).',
      },
      old_content: {
        type: 'string',
        description: 'The exact content to replace (must match exactly in the file).',
      },
      new_content: {
        type: 'string',
        description: 'The replacement content.',
      },
      reason: {
        type: 'string',
        description: 'Why this edit should be made — what problem it solves or improvement it brings.',
      },
    },
    required: ['file_path', 'old_content', 'new_content', 'reason'],
  },
}

/**
 * review_edit_proposal — Review a pending edit proposal from the other posture.
 */
export const REVIEW_EDIT_PROPOSAL_TOOL: ToolSchema = {
  name: 'review_edit_proposal',
  description:
    'Review a pending edit proposal from the other reviewer. ' +
    'Approve or reject the proposed file edit with a reason. ' +
    'If approved, the edit goes to the Brainstem for final approval before being applied.',
  input_schema: {
    type: 'object',
    properties: {
      proposal_id: {
        type: 'string',
        description: 'The ID of the edit proposal to review (e.g., "ep-1").',
      },
      approved: {
        type: 'boolean',
        description: 'Whether you approve this edit.',
      },
      reason: {
        type: 'string',
        description: 'Reason for your approval or rejection.',
      },
      suggested_changes: {
        type: 'string',
        description: 'Optional: suggest modifications to the proposed edit.',
      },
    },
    required: ['proposal_id', 'approved', 'reason'],
  },
}

/** Edit proposal tools available to Yang and Yin */
export const EDIT_PROPOSAL_TOOLS: ToolSchema[] = [
  PROPOSE_EDIT_TOOL,
  REVIEW_EDIT_PROPOSAL_TOOL,
]

/** All dialectic tools for reviewer debate (excluding signal_conclusion) */
export const REVIEWER_DIALECTIC_TOOLS: ToolSchema[] = [
  SHARE_FINDING_TOOL,
  CHALLENGE_TOOL,
  CONCEDE_TOOL,
  REQUEST_INVESTIGATION_TOOL,
  STREAM_RESEARCH_FINDING_TOOL,
  POST_RESEARCH_SIGNAL_TOOL,
]

/** Core reviewer meta-tools (dialectic + nudge + progress + conclusion) */
export const REVIEWER_TOOLS: ToolSchema[] = [
  ...REVIEWER_DIALECTIC_TOOLS,
  ...EDIT_PROPOSAL_TOOLS,
  SEND_NUDGE_TOOL,
  REVIEW_PROGRESS_TOOL,
  SIGNAL_CONCLUSION_TOOL,
]


// ─── Plan + Report + Blackboard Tools (shared) ────────────────────────────

import {
  ALL_POSTURES_PLAN_TOOLS,
  isPlanMetaTool,
} from '../lumen/plan-tools.js'

import {
  REPORT_TOOLS,
  REPORT_TOOL_NAMES,
} from '../lumen/report-tools.js'

import {
  MENTOR_TOOLS,
  MENTOR_TOOL_NAMES,
  isMentorMetaTool,
} from './helix-mentor-tools.js'

export { isPlanMetaTool, REPORT_TOOL_NAMES, MENTOR_TOOLS, MENTOR_TOOL_NAMES, isMentorMetaTool }

/** Plan tools available to all Helix postures */
export const HELIX_PLAN_TOOLS = ALL_POSTURES_PLAN_TOOLS

/** Report tools available to all Helix postures */
export const HELIX_REPORT_TOOLS = REPORT_TOOLS


// ─── Aggregate Tool Sets ──────────────────────────────────────────────────

/** All tools available to Unity (base set — plan/report tools added separately in buildToolSchemas) */
export const ALL_UNITY_TOOLS: ToolSchema[] = [
  ...UNITY_TOOLS,
  REPORT_TO_BRAINSTEM_TOOL,
]

/** All tools available to Yang reviewer (base set — plan/report tools added separately in buildToolSchemas) */
export const ALL_YANG_TOOLS: ToolSchema[] = [
  ...REVIEWER_TOOLS,
]

/** All tools available to Yin reviewer (base set — plan/report tools added separately in buildToolSchemas) */
export const ALL_YIN_TOOLS: ToolSchema[] = [
  ...REVIEWER_TOOLS,
]

/** All tools available to Mentor (moderator) (base set — plan/report tools added separately in buildToolSchemas) */
export const ALL_MENTOR_TOOLS: ToolSchema[] = [
  ...MENTOR_TOOLS,
  REVIEW_PROGRESS_TOOL,
]


// ─── Tool Name Sets ────────────────────────────────────────────────────────

export const UNITY_TOOL_NAMES = new Set([...UNITY_TOOLS.map(t => t.name), REPORT_TO_BRAINSTEM_TOOL.name])

export const REVIEWER_TOOL_NAMES = new Set(REVIEWER_TOOLS.map(t => t.name))

export const EDIT_PROPOSAL_TOOL_NAMES = new Set(EDIT_PROPOSAL_TOOLS.map(t => t.name))

/** All Helix meta-tool names (for routing in agent session) */
export const ALL_HELIX_META_TOOL_NAMES = new Set([
  ...UNITY_TOOL_NAMES,
  ...REVIEWER_TOOL_NAMES,
  ...MENTOR_TOOL_NAMES,
])


// ─── Routing Helpers ──────────────────────────────────────────────────────

/**
 * Check if a tool is a Helix meta-tool (handled inline, not via ToolExecutor).
 * When called with just a name, checks against all meta-tool names.
 * When called with a role, checks role-specific meta-tools.
 */
export function isHelixMetaTool(toolName: string, role?: 'unity' | 'yang' | 'yin' | 'mentor'): boolean {
  if (!role) return ALL_HELIX_META_TOOL_NAMES.has(toolName)
  if (role === 'unity') return UNITY_TOOL_NAMES.has(toolName)
  if (role === 'mentor') return MENTOR_TOOL_NAMES.has(toolName)
  return REVIEWER_TOOL_NAMES.has(toolName)
}

/**
 * Get tool schemas for a specific role.
 */
export function getHelixToolSchemas(role: 'unity' | 'yang' | 'yin' | 'mentor'): ToolSchema[] {
  switch (role) {
    case 'unity': return ALL_UNITY_TOOLS
    case 'yang': return ALL_YANG_TOOLS
    case 'yin': return ALL_YIN_TOOLS
    case 'mentor': return ALL_MENTOR_TOOLS
  }
}
