/**
 * Report Tool Definitions — Meta-tools for the Incremental Report system.
 *
 * These tools are handled inline by LumenPostureRunner (not via ToolExecutor).
 * They enable all postures (Yang, Yin, Executive) to collaboratively build
 * a curated report during the Lumen dialectic session.
 *
 * The report is the structured evidence document; the Executive's synthesis
 * is the narrative interpretation. Both persist in the final LumenResult.
 */

import type { CompletionOpts } from '@cassicore/foundation'

type ToolSchema = NonNullable<CompletionOpts['tools']>[number]

// Report Tools (available to all postures)

export const REPORT_ADD_SECTION_TOOL: ToolSchema = {
  name: 'report_add_section',
  description:
    'Add a curated section to the shared report. Use this for key insights that should ' +
    'shape the final synthesis — not every finding, only the significant ones. ' +
    'Ask yourself: "Would this change a decision?" If yes, add it to the report. ' +
    'Sections are created with status "active" and are immediately visible to all postures.',
  input_schema: {
    type: 'object',
    properties: {
      type: {
        type: 'string',
        enum: ['finding', 'concern', 'recommendation', 'evidence', 'open-question', 'decision', 'note'],
        description: 'Type of insight: finding (key discovery), concern (risk/tradeoff), recommendation (action), evidence (data), open-question (needs investigation), decision (resolved tension), note (context)',
      },
      title: {
        type: 'string',
        description: 'Short title for the section (max 80 chars)',
      },
      content: {
        type: 'string',
        description: 'Full content of the section — the curated insight text',
      },
      confidence: {
        type: 'number',
        description: 'Your confidence in this insight (0.0-1.0). Optional.',
      },
      references: {
        type: 'array',
        items: { type: 'string' },
        description: 'File paths, memory keys, or evidence references. Optional.',
      },
      threadId: {
        type: 'string',
        description: 'Thread ID to group related sections. Use the same threadId for a finding, its challenge, and the resolution. Optional.',
      },
      respondsTo: {
        type: 'string',
        description: 'Section ID this responds to. Optional.',
      },
      challenges: {
        type: 'string',
        description: 'Section ID this challenges. Optional.',
      },
      supports: {
        type: 'string',
        description: 'Section ID this supports. Optional.',
      },
    },
    required: ['type', 'title', 'content'],
  },
}

export const REPORT_VIEW_TOOL: ToolSchema = {
  name: 'report_view',
  description:
    'View the current report. Returns all active and draft sections, organized by type. ' +
    'Use filters to focus on specific types, authors, or recent changes. ' +
    'Call this to see what has been curated so far before adding new sections or during synthesis.',
  input_schema: {
    type: 'object',
    properties: {
      filter_type: {
        type: 'string',
        enum: ['finding', 'concern', 'recommendation', 'evidence', 'open-question', 'decision', 'note'],
        description: 'Only show sections of this type. Optional.',
      },
      filter_author: {
        type: 'string',
        description: 'Only show sections by this author (yang, yin, executive). Optional.',
      },
      filter_status: {
        type: 'string',
        enum: ['draft', 'active', 'superseded'],
        description: 'Only show sections with this status. Default shows active + draft.',
      },
      since: {
        type: 'number',
        description: 'Only show sections updated after this Unix timestamp (ms). Useful for seeing what changed since your last check. Optional.',
      },
    },
    required: [],
  },
}

export const REPORT_REVISE_SECTION_TOOL: ToolSchema = {
  name: 'report_revise_section',
  description:
    'Revise an existing report section. Creates a new active section that supersedes the original. ' +
    'The original remains in the report for audit trail but is marked superseded. ' +
    'Use this when a finding has been disproven, weakened, or needs updating.',
  input_schema: {
    type: 'object',
    properties: {
      section_id: {
        type: 'string',
        description: 'ID of the section to revise (e.g., "rs-1")',
      },
      content: {
        type: 'string',
        description: 'Updated content for the section',
      },
      reason: {
        type: 'string',
        description: 'Why the revision is needed. Optional.',
      },
    },
    required: ['section_id', 'content'],
  },
}

export const REPORT_PROMOTE_TOOL: ToolSchema = {
  name: 'report_promote',
  description:
    'Promote a draft section to active status. Auto-drafted sections (created from ' +
    'dialectic findings/challenges/concessions) start as drafts. Promote them to ' +
    'signal they are important enough for the final synthesis.',
  input_schema: {
    type: 'object',
    properties: {
      section_id: {
        type: 'string',
        description: 'ID of the draft section to promote (e.g., "rs-3")',
      },
    },
    required: ['section_id'],
  },
}

export const REPORT_DISCARD_TOOL: ToolSchema = {
  name: 'report_discard',
  description:
    'Discard a draft section. Only works on sections with status "draft". ' +
    'Use this to remove auto-drafted sections that are not significant enough for the report.',
  input_schema: {
    type: 'object',
    properties: {
      section_id: {
        type: 'string',
        description: 'ID of the draft section to discard (e.g., "rs-2")',
      },
    },
    required: ['section_id'],
  },
}

export const REPORT_METRICS_TOOL: ToolSchema = {
  name: 'report_metrics',
  description:
    'Get quality metrics for the report: section counts by type/author, average confidence, ' +
    'thread count, unresolved concerns, and coverage score. Useful for the Executive to ' +
    'assess completeness before synthesis.',
  input_schema: {
    type: 'object',
    properties: {},
    required: [],
  },
}

// Aggregate exports

/** All report tools — available to all postures */
export const REPORT_TOOLS: ToolSchema[] = [
  REPORT_ADD_SECTION_TOOL,
  REPORT_VIEW_TOOL,
  REPORT_REVISE_SECTION_TOOL,
  REPORT_PROMOTE_TOOL,
  REPORT_DISCARD_TOOL,
  REPORT_METRICS_TOOL,
]

/** Set of report tool names for routing in processToolCalls */
export const REPORT_TOOL_NAMES = new Set([
  'report_add_section',
  'report_view',
  'report_revise_section',
  'report_promote',
  'report_discard',
  'report_metrics',
])
