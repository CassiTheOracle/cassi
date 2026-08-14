/**
 * Blackboard Tools — Meta-tool schemas and routing for all Blackboard boards.
 *
 * Provides:
 *   1. Tool schema definitions for every Blackboard board:
 *      - Channels (findings, concerns, decisions, artifacts, requests)
 *      - Scratchpad (key-value with TTL)
 *      - Artifacts (file path tracking)
 *      - Tool log (read-only)
 *      - Report (curated incremental report — unified replacement for DialecticChannel/WorkStream report)
 *      - Plan (structured execution plan — replacement for PlanHandler)
 *
 *   2. `handleBlackboardToolCall()` — routes any Blackboard tool call to the correct
 *      Blackboard method, enforcing role-based access control for plan approval tools.
 *
 * Usage in agent sessions:
 *   const result = handleBlackboardToolCall(blackboard, toolName, input, postureOrRole)
 *
 * Access control:
 *   - All boards: equal access for all postures/roles
 *   - Plan approval (plan_approve_step, plan_reject_step, plan_update_step, plan_finalize):
 *     restricted to 'executive' (Lumen) and 'apex' (Dyad)
 *
 * Backward compatibility:
 *   - Re-exports ALL_POSTURES_PLAN_TOOLS, EXECUTIVE_PLAN_TOOLS, getPlanToolSchemas
 *     with same signatures as the legacy plan-tools.ts
 *   - Re-exports REPORT_TOOLS, REPORT_TOOL_NAMES with same signatures as report-tools.ts
 *   These legacy exports will be removed in a future cleanup pass.
 */

import type { CompletionOpts } from '@cassicore/foundation'
import type { Blackboard } from './blackboard.js'
import { createHash } from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { COMMIT_CHANGES_TOOL, handleCommitChanges } from './vendor/core/intelligence/shared-tools/commit-tool.js'

type ToolSchema = NonNullable<CompletionOpts['tools']>[number]

const MAX_PERSIST_SIZE = 5 * 1024 * 1024
const SENSITIVE_PATTERNS = [/\.env$/i, /credentials\./i, /secret/i, /\.key$/i, /\.pem$/i, /password/i]

function tryPersistArtifact(
  _blackboard: Blackboard,
  _filePath: string,
  _author: string,
  _notes?: string,
): { uri?: string; error?: string } {
  // FileArtifactStore removed — blackboard-level artifact persistence is a no-op.
  // Flux-team is itself deprecated; keeping this stub only to avoid breaking
  // callers within the deprecated subsystem until those go too.
  return { error: 'Artifact persistence removed' }
}

// Channel Tools

const BB_POST_TOOL: ToolSchema = {
  name: 'bb_post',
  description:
    'Post a structured entry to a shared Blackboard channel. Channels are the primary ' +
    'communication medium — use them to record key findings, concerns, decisions, file ' +
    'artifacts, and coordination requests that should be visible to all agents. ' +
    'All postures and roles have equal read/write access to all channels.',
  input_schema: {
    type: 'object',
    properties: {
      channel: {
        type: 'string',
        enum: ['findings', 'concerns', 'decisions', 'artifacts', 'requests', 'bugs'],
        description:
          'findings: discoveries and observations | ' +
          'concerns: risks, issues, blockers | ' +
          'decisions: choices made or rationale | ' +
          'artifacts: file paths and produced outputs | ' +
          'requests: coordination asks to other agents | ' +
          'bugs: bugs noticed during work for later triage',
      },
      content: {
        type: 'string',
        description: 'The main entry content. Be specific and actionable.',
      },
      tags: {
        type: 'array',
        items: { type: 'string' },
        description: 'Optional tags for filtering (e.g., file paths, module names, severity).',
      },
      priority: {
        type: 'string',
        enum: ['high', 'medium', 'low'],
        description: 'Entry priority. Default: medium.',
      },
      structured: {
        type: 'object',
        description: 'Optional structured metadata (any JSON object) for machine consumption.',
        additionalProperties: true,
      },
    },
    required: ['channel', 'content'],
  },
}

const BB_READ_TOOL: ToolSchema = {
  name: 'bb_read',
  description:
    'Read recent entries from a specific Blackboard channel. ' +
    'Use this to catch up on what other agents have posted.',
  input_schema: {
    type: 'object',
    properties: {
      channel: {
        type: 'string',
        enum: ['findings', 'concerns', 'decisions', 'artifacts', 'requests', 'bugs'],
        description: 'The channel to read.',
      },
      limit: {
        type: 'number',
        description: 'Maximum number of entries to return. Default: 20.',
      },
      since: {
        type: 'number',
        description: 'Only return entries added after this Unix timestamp (ms). Optional.',
      },
    },
    required: ['channel'],
  },
}

const BB_READ_ALL_TOOL: ToolSchema = {
  name: 'bb_read_all',
  description:
    'Read a snapshot of all Blackboard channels in one call. ' +
    'Returns the most recent entries from each channel — useful for orientation ' +
    'at session start or when checking overall workspace state.',
  input_schema: {
    type: 'object',
    properties: {
      limit_per_channel: {
        type: 'number',
        description: 'Max entries per channel. Default: 10.',
      },
    },
    required: [],
  },
}

// Scratchpad Tools

const BB_SCRATCH_SET_TOOL: ToolSchema = {
  name: 'bb_scratch_set',
  description:
    'Write a value to the shared scratchpad (key-value store with TTL). ' +
    'Use for temporary notes, intermediate results, or state you want other postures to see. ' +
    'Entries expire after 30 minutes by default.',
  input_schema: {
    type: 'object',
    properties: {
      key: {
        type: 'string',
        description: 'Scratchpad key. Convention: "<author>:<purpose>" e.g. "yang:explored-paths".',
      },
      value: {
        type: 'string',
        description: 'Value to store (string; use JSON.stringify for complex objects).',
      },
      ttl_ms: {
        type: 'number',
        description: 'Custom TTL in milliseconds. Default: 1800000 (30 minutes).',
      },
    },
    required: ['key', 'value'],
  },
}

const BB_SCRATCH_GET_TOOL: ToolSchema = {
  name: 'bb_scratch_get',
  description:
    'Read a value from the shared scratchpad. Returns null if the key does not exist or has expired.',
  input_schema: {
    type: 'object',
    properties: {
      key: {
        type: 'string',
        description: 'The scratchpad key to read.',
      },
    },
    required: ['key'],
  },
}

const BB_SCRATCH_LIST_TOOL: ToolSchema = {
  name: 'bb_scratch_list',
  description:
    'List all active (non-expired) scratchpad keys, with their author, size, and remaining TTL.',
  input_schema: {
    type: 'object',
    properties: {},
    required: [],
  },
}

// Artifact Tracking Tools

const BB_TRACK_ARTIFACT_TOOL: ToolSchema = {
  name: 'bb_track_artifact',
  description:
    'Register a file artifact produced or modified by this agent. ' +
    'Use this to leave a record of every file you create, edit, or delete ' +
    'so other agents and the final report can reference your work.',
  input_schema: {
    type: 'object',
    properties: {
      path: {
        type: 'string',
        description: 'Absolute or relative path to the file.',
      },
      operation: {
        type: 'string',
        enum: ['created', 'modified', 'deleted', 'read'],
        description: 'What was done to the file.',
      },
      notes: {
        type: 'string',
        description: 'Brief description of what changed and why. Optional.',
      },
      tool_call_id: {
        type: 'string',
        description: 'The tool call ID that produced this artifact. Optional.',
      },
    },
    required: ['path', 'operation'],
  },
}

const BB_GET_ARTIFACTS_TOOL: ToolSchema = {
  name: 'bb_get_artifacts',
  description:
    'List all artifact records on the Blackboard — every file that has been ' +
    'created, modified, or deleted during this session.',
  input_schema: {
    type: 'object',
    properties: {
      filter_operation: {
        type: 'string',
        enum: ['created', 'modified', 'deleted', 'read'],
        description: 'Only return artifacts with this operation type. Optional.',
      },
    },
    required: [],
  },
}

// Tool Log Tool

const BB_TOOL_LOG_TOOL: ToolSchema = {
  name: 'bb_tool_log',
  description:
    'Read the most recent tool execution records from the Blackboard tool log. ' +
    'Useful for Apex/Executive oversight — see what tools have been run, ' +
    'their durations, and whether they succeeded.',
  input_schema: {
    type: 'object',
    properties: {
      limit: {
        type: 'number',
        description: 'Maximum number of log records to return. Default: 20.',
      },
      filter_role: {
        type: 'string',
        description: 'Only show records from this role/posture. Optional.',
      },
    },
    required: [],
  },
}

const BB_SEARCH_TOOL: ToolSchema = {
  name: 'bb_search',
  description:
    'Search across all Blackboard boards (channels, scratchpad, tool log, artifacts, plan, report) ' +
    'with a regex pattern. Returns results grouped by board type with per-board cursor-based pagination. ' +
    'Use this for discovery — find where a concept, file, or author appears across the workspace.',
  input_schema: {
    type: 'object',
    properties: {
      pattern: {
        type: 'string',
        description:
          'Regex pattern to match (case-insensitive). Matches against board-specific fields: ' +
          'channels (content, author, tags), scratchpad (key, value), tool log (tool, nodeId), ' +
          'artifacts (path, author), plan (title, description, tags), report (title, content, author). ' +
          'Max 200 characters.',
      },
      boards: {
        type: 'array',
        items: {
          type: 'string',
          enum: ['channel', 'scratchpad', 'toolLog', 'artifact', 'plan', 'report'],
        },
        description: 'Board types to search. Default: all boards.',
      },
      limit_per_board: {
        type: 'number',
        description: 'Maximum items per board. Default: 50.',
      },
      cursor: {
        type: 'string',
        description: 'Opaque cursor from a previous result for pagination. Pass back the cursor from the last response to get the next page.',
      },
      author: {
        type: 'string',
        description: 'Filter by author across all boards. Optional.',
      },
      since: {
        type: 'number',
        description: 'Only items created at or after this Unix timestamp (ms). Optional.',
      },
      until: {
        type: 'number',
        description: 'Only items created at or before this Unix timestamp (ms). Optional.',
      },
    },
    required: ['pattern'],
  },
}

const BB_SEARCH_CHANNEL_TOOL: ToolSchema = {
  name: 'bb_search_channel',
  description:
    'Search channel entries with regex pattern matching and cursor-based pagination. ' +
    'More powerful than bb_read — supports regex, author/tag/priority/date filters, and stable pagination.',
  input_schema: {
    type: 'object',
    properties: {
      pattern: {
        type: 'string',
        description: 'Regex pattern to match against content, author, and tags. Case-insensitive. Max 200 chars.',
      },
      channel: {
        type: 'string',
        enum: ['findings', 'concerns', 'decisions', 'artifacts', 'requests', 'bugs'],
        description: 'Specific channel to search. If omitted, searches all channels.',
      },
      cursor: {
        type: 'string',
        description: 'Opaque cursor from a previous result for pagination.',
      },
      limit: {
        type: 'number',
        description: 'Maximum items per page. Default: 50.',
      },
      author: {
        type: 'string',
        description: 'Filter by author.',
      },
      tags: {
        type: 'array',
        items: { type: 'string' },
        description: 'Filter by tags (entry must have ALL specified tags).',
      },
      min_priority: {
        type: 'number',
        description: 'Minimum priority (0=low, 1=medium, 2=high).',
      },
      max_priority: {
        type: 'number',
        description: 'Maximum priority.',
      },
      since: {
        type: 'number',
        description: 'Only items created at or after this Unix timestamp (ms).',
      },
      until: {
        type: 'number',
        description: 'Only items created at or before this Unix timestamp (ms).',
      },
    },
    required: [],
  },
}

const BB_SEARCH_REPORT_TOOL: ToolSchema = {
  name: 'bb_search_report',
  description:
    'Search report sections with regex pattern matching and cursor-based pagination. ' +
    'More powerful than report_view — supports regex, type/status/author/date filters.',
  input_schema: {
    type: 'object',
    properties: {
      pattern: {
        type: 'string',
        description: 'Regex pattern to match against title, content, and author. Case-insensitive.',
      },
      cursor: {
        type: 'string',
        description: 'Opaque cursor from a previous result for pagination.',
      },
      limit: {
        type: 'number',
        description: 'Maximum items per page. Default: 50.',
      },
      type: {
        type: 'string',
        enum: ['finding', 'concern', 'recommendation', 'evidence', 'open-question', 'decision', 'note'],
        description: 'Filter by section type.',
      },
      status: {
        type: 'string',
        enum: ['draft', 'active', 'superseded'],
        description: 'Filter by section status.',
      },
      author: {
        type: 'string',
        description: 'Filter by author.',
      },
      since: {
        type: 'number',
        description: 'Only items created at or after this Unix timestamp (ms).',
      },
    },
    required: [],
  },
}

const BB_SEARCH_PLAN_TOOL: ToolSchema = {
  name: 'bb_search_plan',
  description:
    'Search plan steps with regex pattern matching and cursor-based pagination. ' +
    'Supports status/assignee/priority/date filters.',
  input_schema: {
    type: 'object',
    properties: {
      pattern: {
        type: 'string',
        description: 'Regex pattern to match against title, description, and tags. Case-insensitive.',
      },
      cursor: {
        type: 'string',
        description: 'Opaque cursor from a previous result for pagination.',
      },
      limit: {
        type: 'number',
        description: 'Maximum items per page. Default: 50.',
      },
      status: {
        type: 'string',
        enum: ['proposed', 'approved', 'in-progress', 'completed', 'rejected', 'blocked', 'deferred'],
        description: 'Filter by step status.',
      },
      assignee: {
        type: 'string',
        description: 'Filter by assignee.',
      },
      priority: {
        type: 'string',
        enum: ['high', 'medium', 'low'],
        description: 'Filter by step priority.',
      },
      since: {
        type: 'number',
        description: 'Only items created at or after this Unix timestamp (ms).',
      },
    },
    required: [],
  },
}

// Report Tools (re-exported with same names for drop-in replacement)

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
        description: 'Only show sections by this author (yang, yin, executive, apex). Optional.',
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
    'thread count, unresolved concerns, and coverage score. Useful for the Executive/Apex to ' +
    'assess completeness before synthesis.',
  input_schema: {
    type: 'object',
    properties: {},
    required: [],
  },
}

// Plan Tools (re-exported with same names for drop-in replacement)

export const PLAN_SUBMIT_STEP_TOOL: ToolSchema = {
  name: 'plan_submit_step',
  description:
    'Submit a new step to the plan. Steps start as "proposed" and must be approved by the Executive/Apex. ' +
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

export const PLAN_APPROVE_STEP_TOOL: ToolSchema = {
  name: 'plan_approve_step',
  description:
    'Approve a proposed plan step. Only the Executive (Lumen) or Apex (Dyad) can approve steps. ' +
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
    'Reject a proposed plan step with a reason. Only the Executive (Lumen) or Apex (Dyad) can reject steps. ' +
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
    'Update fields of an existing plan step. Only the Executive (Lumen) or Apex (Dyad) can update steps. ' +
    'Use this to refine descriptions, reorder steps, change priority, or update status.',
  input_schema: {
    type: 'object',
    properties: {
      step_id: { type: 'string', description: 'The ID of the step to update.' },
      title: { type: 'string', description: 'New title for the step.' },
      description: { type: 'string', description: 'New description for the step.' },
      order: { type: 'number', description: 'New execution order.' },
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
    'Finalize the plan. Only the Executive (Lumen) or Apex (Dyad) can finalize. ' +
    'Call this when the plan is ready for implementation (status: "approved"), ' +
    'when all steps are done (status: "completed"), or to abandon the plan (status: "abandoned"). ' +
    'Provide a summary of the plan and any important notes for implementers.',
  input_schema: {
    type: 'object',
    properties: {
      status: {
        type: 'string',
        enum: ['approved', 'completed', 'abandoned'],
        description: 'Final plan status.',
      },
      summary: {
        type: 'string',
        description: 'Summary of the plan — key decisions, rationale, implementation notes, and caveats.',
      },
    },
    required: ['status'],
  },
}

// Work-claiming plan tools

export const PLAN_CLAIM_STEP_TOOL: ToolSchema = {
  name: 'plan_claim_step',
  description:
    'Claim an approved plan step for execution. Claiming transitions the step to "in_progress" and ' +
    'assigns you as the owner. Only approved, unassigned steps can be claimed. ' +
    'Use plan_view first to see available steps, then claim the one you want to work on.',
  input_schema: {
    type: 'object',
    properties: {
      step_id: {
        type: 'string',
        description: 'The ID of the step to claim (e.g., "step-a1b2c3d4").',
      },
    },
    required: ['step_id'],
  },
}

export const PLAN_RELEASE_STEP_TOOL: ToolSchema = {
  name: 'plan_release_step',
  description:
    'Release a previously claimed plan step, making it available for others. ' +
    'The step reverts to "approved" with no assignee. You can only release steps you have claimed.',
  input_schema: {
    type: 'object',
    properties: {
      step_id: {
        type: 'string',
        description: 'The ID of the step to release.',
      },
    },
    required: ['step_id'],
  },
}

export const PLAN_REPORT_PROGRESS_TOOL: ToolSchema = {
  name: 'plan_report_progress',
  description:
    'Report progress on a claimed plan step. This acts as a heartbeat — steps without recent ' +
    'progress reports may be automatically released for other agents. ' +
    'Optionally provide a progress description to keep others informed.',
  input_schema: {
    type: 'object',
    properties: {
      step_id: {
        type: 'string',
        description: 'The ID of the step to report progress on.',
      },
      progress: {
        type: 'string',
        description: 'Description of progress made so far.',
      },
    },
    required: ['step_id'],
  },
}

// Tool Name Sets

/** All channel tool names */
const CHANNEL_TOOL_NAMES = new Set(['bb_post', 'bb_read', 'bb_read_all'])

/** All scratchpad tool names */
const SCRATCHPAD_TOOL_NAMES = new Set(['bb_scratch_set', 'bb_scratch_get', 'bb_scratch_list'])

/** All artifact tool names */
const ARTIFACT_TOOL_NAMES = new Set(['bb_track_artifact', 'bb_get_artifacts'])

/** All report tool names */
export const REPORT_TOOL_NAMES = new Set([
  'report_add_section',
  'report_view',
  'report_revise_section',
  'report_promote',
  'report_discard',
  'report_metrics',
])

/** All plan tool names */
const ALL_PLAN_TOOL_NAMES = new Set([
  'plan_submit_step',
  'plan_view',
  'plan_approve_step',
  'plan_reject_step',
  'plan_update_step',
  'plan_finalize',
  'plan_claim_step',
  'plan_release_step',
  'plan_report_progress',
])

/** Plan tools restricted to Executive / Apex only */
const GATED_PLAN_TOOL_NAMES = new Set([
  'plan_approve_step',
  'plan_reject_step',
  'plan_update_step',
  'plan_finalize',
])

/**
 * All Blackboard meta-tool names.
 * Used for inline routing — tool calls matching these names are handled directly
 * by the agent session rather than being dispatched to the ToolExecutor.
 */
export const BLACKBOARD_TOOL_NAMES = new Set([
  ...CHANNEL_TOOL_NAMES,
  ...SCRATCHPAD_TOOL_NAMES,
  ...ARTIFACT_TOOL_NAMES,
  'bb_tool_log',
  'bb_search',
  'bb_search_channel',
  'bb_search_report',
  'bb_search_plan',
  ...REPORT_TOOL_NAMES,
  ...ALL_PLAN_TOOL_NAMES,
  'commit_changes',
])

/**
 * Check if a tool name is a Blackboard meta-tool.
 * @dep callers: buildToolSchemas (core/intelligence/lumen/lumen-posture-runner.ts), processToolCalls (core/intelligence/lumen/lumen-posture-runner.ts), processToolCalls (core/intelligence/helix/helix-posture-runner.ts), buildToolSchemas (core/intelligence/helix/helix-posture-runner.ts), processToolCalls (core/intelligence/dyad/dyad-posture-runner.ts)
 * @dep calls: has
 * @dep flows: Run → IsBlackboardMetaTool (3/3)
 * @dep module: Lumen
 * @dep risk: MEDIUM | 5 callers, 1 flow, 1 module
 */
export function isBlackboardMetaTool(name: string): boolean {
  return BLACKBOARD_TOOL_NAMES.has(name)
}

// Tool Schema Sets

/** Channel + scratchpad + artifact + tool-log tools — available to all postures/roles */
const BOARD_TOOLS_ALL: ToolSchema[] = [
  BB_POST_TOOL,
  BB_READ_TOOL,
  BB_READ_ALL_TOOL,
  BB_SCRATCH_SET_TOOL,
  BB_SCRATCH_GET_TOOL,
  BB_SCRATCH_LIST_TOOL,
  BB_TRACK_ARTIFACT_TOOL,
  BB_GET_ARTIFACTS_TOOL,
  BB_TOOL_LOG_TOOL,
  BB_SEARCH_TOOL,
  BB_SEARCH_CHANNEL_TOOL,
  BB_SEARCH_REPORT_TOOL,
  BB_SEARCH_PLAN_TOOL,
  COMMIT_CHANGES_TOOL,
]

/** All report tools — available to all postures/roles */
export const REPORT_TOOLS: ToolSchema[] = [
  REPORT_ADD_SECTION_TOOL,
  REPORT_VIEW_TOOL,
  REPORT_REVISE_SECTION_TOOL,
  REPORT_PROMOTE_TOOL,
  REPORT_DISCARD_TOOL,
  REPORT_METRICS_TOOL,
]

/** Plan tools available to all postures/roles */
export const ALL_POSTURES_PLAN_TOOLS: ToolSchema[] = [
  PLAN_SUBMIT_STEP_TOOL,
  PLAN_VIEW_TOOL,
  PLAN_CLAIM_STEP_TOOL,
  PLAN_RELEASE_STEP_TOOL,
  PLAN_REPORT_PROGRESS_TOOL,
]

/** Plan tools available only to Executive (Lumen) / Apex (Dyad) */
export const EXECUTIVE_PLAN_TOOLS: ToolSchema[] = [
  PLAN_APPROVE_STEP_TOOL,
  PLAN_REJECT_STEP_TOOL,
  PLAN_UPDATE_STEP_TOOL,
  PLAN_FINALIZE_TOOL,
]

/**
 * Get the full set of Blackboard tool schemas for a posture/role.
 *
 * @param posture - The posture or role name (e.g. 'yang', 'yin', 'executive', 'apex')
 * @returns Array of tool schemas for that posture
 * @dep callers: buildToolSchemas (core/intelligence/lumen/lumen-posture-runner.ts), buildToolSchemas (core/intelligence/dyad/dyad-posture-runner.ts), getBlackboardSchemas (core/intelligence/cassi-agent/base-posture-runner.ts)
 * @dep flows: RunAsWorker → GetBlackboardToolSchemas (3/3), RunAsMentor → GetBlackboardToolSchemas (4/4), RunAsReviewer → GetBlackboardToolSchemas (4/4) [+1]
 * @dep module: Lumen
 * @dep risk: MEDIUM | 3 callers, 4 flows, 1 module
 */
export function getBlackboardToolSchemas(posture: string): ToolSchema[] {
  const isGated = posture === 'executive' || posture === 'apex'
  return [
    ...BOARD_TOOLS_ALL,
    ...REPORT_TOOLS,
    ...ALL_POSTURES_PLAN_TOOLS,
    ...(isGated ? EXECUTIVE_PLAN_TOOLS : []),
  ]
}

/**
 * Get plan tool schemas for a posture — backward-compatible alias.
 *
 * @deprecated Prefer `getBlackboardToolSchemas(posture)`. This alias will be
 *   removed in a future cleanup pass when plan-tools.ts is deleted.
 */
export function getPlanToolSchemas(posture: 'yang' | 'yin' | 'executive'): ToolSchema[] {
  if (posture === 'executive') {
    return [...ALL_POSTURES_PLAN_TOOLS, ...EXECUTIVE_PLAN_TOOLS]
  }
  return [...ALL_POSTURES_PLAN_TOOLS]
}

/**
 * Set of all plan meta-tool names — backward-compatible alias.
 *
 * @deprecated Prefer `BLACKBOARD_TOOL_NAMES`. This will be removed with plan-tools.ts.
 */
export const PLAN_META_TOOL_NAMES = ALL_PLAN_TOOL_NAMES

/**
 * Check if a tool name is a plan meta-tool — backward-compatible alias.
 *
 * @deprecated Prefer `isBlackboardMetaTool`. This will be removed with plan-tools.ts.
 */
export function isPlanMetaTool(name: string): boolean {
  return ALL_PLAN_TOOL_NAMES.has(name)
}

// Routing — handleBlackboardToolCall

/**
 * Route a Blackboard tool call to the appropriate Blackboard method.
 *
 * This is the single dispatch function used by both LumenPostureRunner and
 * DyadPostureRunner. It enforces role-based access control for plan approval
 * tools (restricted to 'executive' and 'apex').
 *
 * @param blackboard - The Blackboard instance for this session
 * @param name - Tool name (must be in BLACKBOARD_TOOL_NAMES)
 * @param input - Parsed tool input from the LLM
 * @param posture - Calling posture/role (e.g. 'yang', 'yin', 'executive', 'apex')
 * @returns String result to return to the LLM
 * @dep callers: processToolCalls (core/intelligence/lumen/lumen-posture-runner.ts), processToolCalls (core/intelligence/dyad/dyad-posture-runner.ts), processBlackboardCalls (core/intelligence/cassi-agent/base-posture-runner.ts)
 * @dep calls: handleBbSearchPlan, handleBbSearchReport, handleBbSearchChannel, handleBbSearch, handlePlanReportProgress [+25]
 * @dep flows: ProcessToolCalls → GetArtifacts (2/4), ProcessToolCalls → GetAllScratchpad (2/4), ProcessToolCalls → PriorityNum (2/4)
 * @dep module: Flux-team
 * @dep risk: MEDIUM | 3 callers, 3 flows, 1 module
 */
export function handleBlackboardToolCall(
  blackboard: Blackboard,
  name: string,
  input: Record<string, unknown>,
  posture: string,
): string {
  try {
    if (GATED_PLAN_TOOL_NAMES.has(name) && posture !== 'executive' && posture !== 'apex') {
      return JSON.stringify({
        error: `Tool '${name}' is restricted to the Executive (Lumen) or Apex (Dyad) role. You (${posture}) can use plan_submit_step and plan_view.`,
      })
    }

    if (name === 'bb_post') return handleBbPost(blackboard, input, posture)
    if (name === 'bb_read') return handleBbRead(blackboard, input)
    if (name === 'bb_read_all') return handleBbReadAll(blackboard, input)

    if (name === 'bb_scratch_set') return handleScratchSet(blackboard, input, posture)
    if (name === 'bb_scratch_get') return handleScratchGet(blackboard, input)
    if (name === 'bb_scratch_list') return handleScratchList(blackboard)

    if (name === 'bb_track_artifact') return handleTrackArtifact(blackboard, input, posture)
    if (name === 'bb_get_artifacts') return handleGetArtifacts(blackboard, input)

    if (name === 'bb_tool_log') return handleToolLog(blackboard, input)

    if (name === 'bb_search') return handleBbSearch(blackboard, input)
    if (name === 'bb_search_channel') return handleBbSearchChannel(blackboard, input)
    if (name === 'bb_search_report') return handleBbSearchReport(blackboard, input)
    if (name === 'bb_search_plan') return handleBbSearchPlan(blackboard, input)

    if (name === 'report_add_section') return handleReportAddSection(blackboard, input, posture)
    if (name === 'report_view') return handleReportView(blackboard, input)
    if (name === 'report_revise_section') return handleReportReviseSection(blackboard, input)
    if (name === 'report_promote') return handleReportPromote(blackboard, input)
    if (name === 'report_discard') return handleReportDiscard(blackboard, input)
    if (name === 'report_metrics') return handleReportMetrics(blackboard)

    if (name === 'plan_submit_step') return handlePlanSubmitStep(blackboard, input, posture)
    if (name === 'plan_view') return handlePlanView(blackboard)
    if (name === 'plan_approve_step') return handlePlanApproveStep(blackboard, input)
    if (name === 'plan_reject_step') return handlePlanRejectStep(blackboard, input)
    if (name === 'plan_update_step') return handlePlanUpdateStep(blackboard, input)
    if (name === 'plan_finalize') return handlePlanFinalize(blackboard, input, posture)
    if (name === 'plan_claim_step') return handlePlanClaimStep(blackboard, input, posture)
    if (name === 'plan_release_step') return handlePlanReleaseStep(blackboard, input, posture)
    if (name === 'plan_report_progress') return handlePlanReportProgress(blackboard, input, posture)

    // Commit tool (shared)
    if (name === 'commit_changes') return handleCommitChanges(input)

    return JSON.stringify({ error: `Unknown Blackboard tool: ${name}` })
  } catch (err) {
    return JSON.stringify({ error: String(err) })
  }
}

// Channel Implementations

type ChannelName = 'findings' | 'concerns' | 'decisions' | 'artifacts' | 'requests' | 'bugs'
const VALID_CHANNELS = new Set<ChannelName>(['findings', 'concerns', 'decisions', 'artifacts', 'requests', 'bugs'])

/** Map priority string to numeric priority for Blackboard.post() */
/**
 * @dep callers: handleBbPost (core/intelligence/flux-team/blackboard-tools.ts)
 * @dep flows: ProcessToolCalls → PriorityNum (4/4)
 * @dep module: Unknown
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */

function priorityNum(p: unknown): number {
  if (p === 'high') return 2
  if (p === 'low') return 0
  return 1 // 'medium' is default
}

/**
 * @dep callers: handleBlackboardToolCall (core/intelligence/flux-team/blackboard-tools.ts)
 * @dep calls: priorityNum, has
 * @dep flows: ProcessToolCalls → PriorityNum (3/4)
 * @dep module: Flux-team
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */

function handleBbPost(blackboard: Blackboard, input: Record<string, unknown>, author: string): string {
  const channel = String(input.channel ?? '') as ChannelName
  if (!VALID_CHANNELS.has(channel)) {
    return JSON.stringify({ error: `Invalid channel: ${channel}. Must be one of: ${[...VALID_CHANNELS].join(', ')}` })
  }
  const content = String(input.content ?? '')
  if (!content) return JSON.stringify({ error: 'content is required.' })

  const tags = Array.isArray(input.tags) ? input.tags.map(String) : []
  const structured = input.structured && typeof input.structured === 'object' && !Array.isArray(input.structured)
    ? (input.structured as Record<string, unknown>)
    : undefined

  const entry = blackboard.post(channel, {
    author,
    content,
    tags,
    priority: priorityNum(input.priority),
    structured,
  })

  return JSON.stringify({
    success: true,
    id: entry.id,
    channel,
    message: `Posted to ${channel} as entry ${entry.id}.`,
  })
}

function handleBbRead(blackboard: Blackboard, input: Record<string, unknown>): string {
  const channel = String(input.channel ?? '') as ChannelName
  if (!VALID_CHANNELS.has(channel)) {
    return JSON.stringify({ error: `Invalid channel: ${channel}.` })
  }
  const limit = typeof input.limit === 'number' ? input.limit : 20
  const since = typeof input.since === 'number' ? input.since : undefined

  let entries = blackboard.read(channel, limit)
  if (since) entries = entries.filter(e => e.timestamp > since)

  if (entries.length === 0) return `No entries in ${channel}${since ? ' since the specified time' : ''}.`

  const lines = entries.map(e => {
    const tags = e.tags.length ? ` [${e.tags.join(', ')}]` : ''
    const struct = e.structured ? `\n  Data: ${JSON.stringify(e.structured)}` : ''
    return `[${e.id}] ${e.author} (priority:${e.priority}${tags}):\n  ${e.content}${struct}`
  })
  return `## ${channel} (${entries.length} entries)\n${lines.join('\n\n')}`
}

/**
 * @dep callers: handleBlackboardToolCall (core/intelligence/flux-team/blackboard-tools.ts)
 * @dep calls: getArtifacts, getAllScratchpad
 * @dep flows: ProcessToolCalls → GetArtifacts (3/4), ProcessToolCalls → GetAllScratchpad (3/4)
 * @dep module: Flux-team
 * @dep risk: LOW | 1 caller, 2 flows, 1 module
 */

function handleBbReadAll(blackboard: Blackboard, input: Record<string, unknown>): string {
  const limitPerChannel = typeof input.limit_per_channel === 'number' ? input.limit_per_channel : 10
  const channels: ChannelName[] = ['findings', 'concerns', 'decisions', 'artifacts', 'requests', 'bugs']
  const parts: string[] = ['## Blackboard Snapshot']

  for (const ch of channels) {
    const entries = blackboard.read(ch, limitPerChannel)
    parts.push(`\n### ${ch} (${entries.length} recent)`)
    if (entries.length === 0) {
      parts.push('  (empty)')
    } else {
      for (const e of entries) {
        const tags = e.tags.length ? ` [${e.tags.join(', ')}]` : ''
        parts.push(`  [${e.id}] ${e.author}${tags}: ${e.content.slice(0, 120)}${e.content.length > 120 ? '...' : ''}`)
      }
    }
  }

  // Scratchpad active keys
  const scratchMap = blackboard.getAllScratchpad()
  const scratchKeys = Array.from(scratchMap.keys())
  parts.push(`\n### scratchpad (${scratchKeys.length} active keys)`)
  if (scratchKeys.length > 0) parts.push('  ' + scratchKeys.join(', '))

  // Artifact count
  const artifacts = blackboard.getArtifacts()
  parts.push(`\n### artifacts (${artifacts.length} tracked)`)

  return parts.join('\n')
}

// Scratchpad Implementations

function handleScratchSet(blackboard: Blackboard, input: Record<string, unknown>, author: string): string {
  const key = String(input.key ?? '')
  const value = String(input.value ?? '')
  if (!key) return JSON.stringify({ error: 'key is required.' })
  const ttl = typeof input.ttl_ms === 'number' ? input.ttl_ms : undefined
  blackboard.setScratchpad(key, value, author, ttl)
  return JSON.stringify({ success: true, key, message: `Scratchpad key "${key}" set.` })
}

function handleScratchGet(blackboard: Blackboard, input: Record<string, unknown>): string {
  const key = String(input.key ?? '')
  if (!key) return JSON.stringify({ error: 'key is required.' })
  const value = blackboard.getScratchpad(key)
  if (value === undefined) return JSON.stringify({ key, value: null, message: `Key "${key}" not found or expired.` })
  return JSON.stringify({ key, value })
}

function handleScratchList(blackboard: Blackboard): string {
  const scratchMap = blackboard.getAllScratchpad()
  const keys = Array.from(scratchMap.keys())
  if (keys.length === 0) return 'Scratchpad is empty.'
  return `## Scratchpad (${keys.length} active keys)\n${keys.map(k => `  - ${k}`).join('\n')}`
}

// Artifact Implementations

function handleTrackArtifact(blackboard: Blackboard, input: Record<string, unknown>, author: string): string {
  const filePath = String(input.path ?? '')
  const opStr = String(input.operation ?? 'modified')
  if (!filePath) return JSON.stringify({ error: 'path is required.' })

  const validOps = new Set(['created', 'modified', 'deleted'])
  // 'read' is accepted from LLM input but normalized to 'modified' since ArtifactEntry only supports 3 ops
  const operation = (validOps.has(opStr) ? opStr : 'modified') as 'created' | 'modified' | 'deleted'

  blackboard.addArtifact({ path: filePath, operation, author })

  // If notes provided, also post to artifacts channel for visibility
  const notes = input.notes ? String(input.notes) : undefined
  if (notes) {
    blackboard.post('artifacts', {
      author,
      content: `${operation.toUpperCase()} ${filePath} — ${notes}`,
      tags: [operation, 'artifact'],
      priority: 0,
    })
  }

  let persistResult: { uri?: string; error?: string } | undefined
  if ((operation === 'created' || operation === 'modified') && blackboard.getAutoPersistEnabled()) {
    persistResult = tryPersistArtifact(blackboard, filePath, author, notes)
  }

  return JSON.stringify({
    success: true,
    path: filePath,
    operation,
    message: `Artifact tracked: ${operation} ${filePath}`,
    ...(persistResult?.uri ? { persisted: true, uri: persistResult.uri } : {}),
    ...(persistResult?.error ? { persistWarning: persistResult.error } : {}),
  })
}

function handleGetArtifacts(blackboard: Blackboard, input: Record<string, unknown>): string {
  const filterOp = input.filter_operation ? String(input.filter_operation) : undefined
  let artifacts = blackboard.getArtifacts()
  if (filterOp) artifacts = artifacts.filter(a => a.operation === filterOp)

  if (artifacts.length === 0) return 'No artifacts tracked yet.'

  const lines = artifacts.map(a => `  ${a.operation.toUpperCase()} ${a.path} (by ${a.author})`)
  return `## Artifacts (${artifacts.length})\n${lines.join('\n')}`
}

// Tool Log Implementation

function handleToolLog(blackboard: Blackboard, input: Record<string, unknown>): string {
  const limit = typeof input.limit === 'number' ? input.limit : 20
  const filterRole = input.filter_role ? String(input.filter_role) : undefined

  let records = blackboard.getToolLog(limit)
  if (filterRole) records = records.filter(r => r.nodeId === filterRole)

  if (records.length === 0) return 'No tool log records.'

  const lines = records.map(r => {
    const dur = r.durationMs != null ? ` (${r.durationMs}ms)` : ''
    const err = r.isError ? ' [ERROR]' : ''
    return `  [${r.nodeId}] ${r.tool}${dur}${err}`
  })
  return `## Tool Log (${records.length} records)\n${lines.join('\n')}`
}

// Report Implementations

function handleReportAddSection(blackboard: Blackboard, input: Record<string, unknown>, author: string): string {
  const type = String(input.type ?? 'note') as import('@cassicore/foundation').ReportSectionType
  const title = String(input.title ?? '').slice(0, 80)
  const content = String(input.content ?? '')
  const confidence = typeof input.confidence === 'number' ? input.confidence : undefined
  const references = Array.isArray(input.references) ? input.references.map(String) : undefined
  const threadId = input.threadId ? String(input.threadId) : undefined
  const respondsTo = input.respondsTo ? String(input.respondsTo) : undefined
  const challenges = input.challenges ? String(input.challenges) : undefined
  const supports = input.supports ? String(input.supports) : undefined

  const section = blackboard.addReportSection({
    type,
    title,
    content,
    author,
    confidence,
    references,
    threadId,
    respondsTo,
    challenges,
    supports,
  })

  return `Section added to report as [${section.id}]: "${title}" (${type}, active)`
}

function handleReportView(blackboard: Blackboard, input: Record<string, unknown>): string {
  const sections = blackboard.getReportView({
    filterType: input.filter_type ? String(input.filter_type) : undefined,
    filterAuthor: input.filter_author ? String(input.filter_author) : undefined,
    filterStatus: input.filter_status ? String(input.filter_status) : undefined,
    since: typeof input.since === 'number' ? input.since : undefined,
  })

  if (sections.length === 0) return 'No sections match the filter criteria.'

  const parts: string[] = [`## Report (${sections.length} sections)`]

  const byType = new Map<string, typeof sections>()
  for (const s of sections) {
    if (!byType.has(s.type)) byType.set(s.type, [])
    byType.get(s.type)!.push(s)
  }

  for (const [type, typeSections] of byType) {
    parts.push(`\n### ${type.charAt(0).toUpperCase() + type.slice(1)}s`)
    for (const s of typeSections) {
      const status = s.status !== 'active' ? ` [${s.status.toUpperCase()}]` : ''
      const conf = s.confidence != null ? ` (conf: ${s.confidence})` : ''
      const thread = s.threadId ? ` [thread: ${s.threadId}]` : ''
      const refs = s.references?.length ? `\n    Refs: ${s.references.join(', ')}` : ''
      parts.push(`- [${s.id}]${status} **${s.title}** — ${s.author}${conf}${thread}\n    ${s.content}${refs}`)
    }
  }

  return parts.join('\n')
}

function handleReportReviseSection(blackboard: Blackboard, input: Record<string, unknown>): string {
  const sectionId = String(input.section_id ?? '')
  const content = String(input.content ?? '')
  const reason = input.reason ? String(input.reason) : undefined

  const revised = blackboard.reviseReportSection(sectionId, content, reason)
  if (!revised) return `Section [${sectionId}] not found or cannot be revised.`
  return `Section [${sectionId}] revised — new section [${revised.id}] created, original marked superseded.`
}

function handleReportPromote(blackboard: Blackboard, input: Record<string, unknown>): string {
  const sectionId = String(input.section_id ?? '')
  const ok = blackboard.promoteReportSection(sectionId)
  if (!ok) return `Section [${sectionId}] not found or is not a draft.`
  return `Section [${sectionId}] promoted from draft to active.`
}

function handleReportDiscard(blackboard: Blackboard, input: Record<string, unknown>): string {
  const sectionId = String(input.section_id ?? '')
  const ok = blackboard.discardReportSection(sectionId)
  if (!ok) return `Section [${sectionId}] not found or is not a draft (only drafts can be discarded).`
  return `Draft section [${sectionId}] discarded.`
}

function handleReportMetrics(blackboard: Blackboard): string {
  const m = blackboard.getReportMetrics()
  return [
    '## Report Quality Metrics',
    `Active: ${m.activeSections} | Drafts: ${m.draftSections} | Total: ${m.totalSections}`,
    `Avg confidence: ${m.avgConfidence} | Coverage score: ${m.coverageScore}`,
    `Threads: ${m.threadCount} | Unresolved concerns: ${m.unresolvedConcerns}`,
    `By type: ${JSON.stringify(m.byType)}`,
    `By author: ${JSON.stringify(m.byAuthor)}`,
  ].join('\n')
}

// Plan Implementations

function handlePlanSubmitStep(blackboard: Blackboard, input: Record<string, unknown>, author: string): string {
  const title = String(input.title ?? '')
  const description = String(input.description ?? '')
  if (!title || !description) {
    return JSON.stringify({ error: 'Both title and description are required.' })
  }

  const plan = blackboard.getPlan()
  const nextOrder = plan && plan.steps.length > 0
    ? Math.max(...plan.steps.map(s => s.order)) + 1
    : 1
  const order = typeof input.order === 'number' ? input.order : nextOrder
  const priority = (['high', 'medium', 'low'] as const).includes(input.priority as any)
    ? (input.priority as 'high' | 'medium' | 'low')
    : 'medium'
  const dependencies = Array.isArray(input.dependencies) ? input.dependencies.map(String) : []
  const tags = Array.isArray(input.tags) ? input.tags.map(String) : []

  const step = blackboard.submitPlanStep({ title, description, author, order, dependencies, priority, tags })

  return JSON.stringify({
    success: true,
    step: formatStep(step),
    message: `Step "${title}" submitted as proposed. The Executive/Apex will review it.`,
  })
}

function handlePlanView(blackboard: Blackboard): string {
  const plan = blackboard.getPlan()
  if (!plan) return JSON.stringify({ plan: null, message: 'No plan has been initialized yet.' })

  // Run stall detection on view so agents see an up-to-date picture
  const reclaimed = blackboard.reclaimStalledWork()

  const result: Record<string, unknown> = { plan: formatPlan(plan) }
  if (reclaimed > 0) {
    result.notice = `${reclaimed} stalled step(s) were automatically released and are now available.`
  }

  return JSON.stringify(result)
}

function handlePlanApproveStep(blackboard: Blackboard, input: Record<string, unknown>): string {
  const stepId = String(input.step_id ?? input.stepId ?? '')
  if (!stepId) return JSON.stringify({ error: 'step_id is required.' })
  const step = blackboard.updatePlanStep(stepId, { status: 'approved' })
  if (!step) return JSON.stringify({ error: `Step not found: ${stepId}` })
  return JSON.stringify({ success: true, step: formatStep(step), message: `Step "${step.title}" approved.` })
}

function handlePlanRejectStep(blackboard: Blackboard, input: Record<string, unknown>): string {
  const stepId = String(input.step_id ?? input.stepId ?? '')
  const reason = String(input.reason ?? '')
  if (!stepId) return JSON.stringify({ error: 'step_id is required.' })
  if (!reason) return JSON.stringify({ error: 'reason is required when rejecting a step.' })
  const step = blackboard.updatePlanStep(stepId, { status: 'rejected', rejectionReason: reason })
  if (!step) return JSON.stringify({ error: `Step not found: ${stepId}` })
  return JSON.stringify({ success: true, step: formatStep(step), message: `Step "${step.title}" rejected: ${reason}` })
}

function handlePlanUpdateStep(blackboard: Blackboard, input: Record<string, unknown>): string {
  const stepId = String(input.step_id ?? input.stepId ?? '')
  if (!stepId) return JSON.stringify({ error: 'step_id is required.' })

  const update: Record<string, unknown> = {}
  if (input.title !== undefined) update.title = String(input.title)
  if (input.description !== undefined) update.description = String(input.description)
  if (input.order !== undefined) update.order = Number(input.order)
  if (input.priority !== undefined) update.priority = String(input.priority)
  if (input.status !== undefined) update.status = String(input.status)
  if (input.dependencies !== undefined) update.dependencies = Array.isArray(input.dependencies) ? input.dependencies.map(String) : []
  if (input.tags !== undefined) update.tags = Array.isArray(input.tags) ? input.tags.map(String) : []
  if (input.outcome !== undefined) update.outcome = String(input.outcome)

  if (Object.keys(update).length === 0) {
    return JSON.stringify({ error: 'No fields to update. Provide at least one field besides step_id.' })
  }

  const step = blackboard.updatePlanStep(stepId, update as any)
  if (!step) return JSON.stringify({ error: `Step not found: ${stepId}` })
  return JSON.stringify({ success: true, step: formatStep(step), message: `Step "${step.title}" updated.` })
}

function handlePlanFinalize(blackboard: Blackboard, input: Record<string, unknown>, approver: string): string {
  const status = String(input.status ?? 'approved') as 'approved' | 'completed' | 'abandoned'
  const validStatuses = ['approved', 'completed', 'abandoned']
  if (!validStatuses.includes(status)) {
    return JSON.stringify({ error: `Invalid status: ${status}. Must be one of: ${validStatuses.join(', ')}` })
  }
  const summary = input.summary ? String(input.summary) : undefined
  const plan = blackboard.finalizePlan(status, approver, summary)
  if (!plan) return JSON.stringify({ error: 'No plan exists to finalize.' })
  return JSON.stringify({ success: true, plan: formatPlan(plan), message: `Plan finalized as '${status}'.` })
}

// Work-claiming plan implementations

function handlePlanClaimStep(blackboard: Blackboard, input: Record<string, unknown>, posture: string): string {
  const stepId = String(input.step_id ?? input.stepId ?? '')
  if (!stepId) return JSON.stringify({ error: 'step_id is required.' })

  const step = blackboard.claimPlanStep(stepId, posture)
  if (!step) {
    const plan = blackboard.getPlan()
    const existing = plan?.steps.find(s => s.id === stepId)
    if (!existing) return JSON.stringify({ error: `Step not found: ${stepId}` })
    if (existing.status !== 'approved') {
      return JSON.stringify({ error: `Step "${existing.title}" cannot be claimed — status is "${existing.status}" (must be "approved").` })
    }
    if (existing.assignee) {
      return JSON.stringify({ error: `Step "${existing.title}" is already claimed by "${existing.assignee}".` })
    }
    return JSON.stringify({ error: `Cannot claim step "${existing.title}".` })
  }

  return JSON.stringify({
    success: true,
    step: formatStep(step),
    message: `Step "${step.title}" claimed by ${posture}. You are now responsible for completing it. Use plan_report_progress to send heartbeats.`,
  })
}

function handlePlanReleaseStep(blackboard: Blackboard, input: Record<string, unknown>, posture: string): string {
  const stepId = String(input.step_id ?? input.stepId ?? '')
  if (!stepId) return JSON.stringify({ error: 'step_id is required.' })

  const plan = blackboard.getPlan()
  const existing = plan?.steps.find(s => s.id === stepId)
  if (!existing) return JSON.stringify({ error: `Step not found: ${stepId}` })

  if (existing.assignee && existing.assignee !== posture) {
    return JSON.stringify({ error: `Step "${existing.title}" is claimed by "${existing.assignee}" — only the assignee can release it.` })
  }

  const ok = blackboard.releasePlanStep(stepId, posture)
  if (!ok) {
    return JSON.stringify({ error: `Cannot release step "${existing.title}" — it is not in-progress or not assigned to you.` })
  }

  return JSON.stringify({
    success: true,
    message: `Step "${existing.title}" released and is now available for others to claim.`,
  })
}

function handlePlanReportProgress(blackboard: Blackboard, input: Record<string, unknown>, posture: string): string {
  const stepId = String(input.step_id ?? input.stepId ?? '')
  if (!stepId) return JSON.stringify({ error: 'step_id is required.' })

  const progress = input.progress ? String(input.progress) : undefined
  const step = blackboard.reportPlanStepProgress(stepId, posture, progress)
  if (!step) {
    const plan = blackboard.getPlan()
    const existing = plan?.steps.find(s => s.id === stepId)
    if (!existing) return JSON.stringify({ error: `Step not found: ${stepId}` })
    if (existing.assignee !== posture) {
      return JSON.stringify({ error: `Step "${existing.title}" is not assigned to you (assigned to: ${existing.assignee ?? 'nobody'}).` })
    }
    return JSON.stringify({ error: `Cannot report progress on step "${existing.title}" — it is not in-progress.` })
  }

  return JSON.stringify({
    success: true,
    step: formatStep(step),
    message: `Progress reported on "${step.title}".${progress ? ` Progress: ${progress}` : ''}`,
  })
}

// Plan Formatting Helpers

/**
 * @dep callers: handlePlanSubmitStep (core/intelligence/flux-team/blackboard-tools.ts), handlePlanApproveStep (core/intelligence/flux-team/blackboard-tools.ts), handlePlanRejectStep (core/intelligence/flux-team/blackboard-tools.ts), handlePlanUpdateStep (core/intelligence/flux-team/blackboard-tools.ts), handlePlanClaimStep (core/intelligence/flux-team/blackboard-tools.ts) [+1]
 * @dep module: Flux-team
 * @dep risk: MEDIUM | 6 callers, 0 flows, 1 module
 */

function formatStep(step: import('@cassicore/foundation').PlanStep): Record<string, unknown> {
  const result: Record<string, unknown> = {
    id: step.id,
    title: step.title,
    description: step.description,
    status: step.status,
    author: step.author,
    order: step.order,
    priority: step.priority,
    dependencies: step.dependencies,
    tags: step.tags,
    outcome: step.outcome,
    rejectionReason: step.rejectionReason,
  }

  // Include work-claiming fields when present
  if (step.assignee) result.assignee = step.assignee
  if (step.claimedAt) result.claimedAt = step.claimedAt
  if (step.lastActivityAt) result.lastActivityAt = step.lastActivityAt

  return result
}

/**
 * @dep callers: handlePlanView (core/intelligence/flux-team/blackboard-tools.ts), handlePlanFinalize (core/intelligence/flux-team/blackboard-tools.ts)
 * @dep module: Flux-team
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function formatPlan(plan: import('@cassicore/foundation').Plan): Record<string, unknown> {
  const sortedSteps = [...plan.steps].sort((a, b) => a.order - b.order)
  const available = plan.steps.filter(s => s.status === 'approved' && !s.assignee).length
  const claimed = plan.steps.filter(s => s.status === 'in_progress' && s.assignee).length

  return {
    id: plan.id,
    goal: plan.goal,
    status: plan.status,
    summary: plan.summary,
    approvedBy: plan.approvedBy,
    stepCount: plan.steps.length,
    steps: sortedSteps.map(formatStep),
    statusBreakdown: {
      proposed: plan.steps.filter(s => s.status === 'proposed').length,
      approved: plan.steps.filter(s => s.status === 'approved').length,
      rejected: plan.steps.filter(s => s.status === 'rejected').length,
      in_progress: plan.steps.filter(s => s.status === 'in_progress').length,
      completed: plan.steps.filter(s => s.status === 'completed').length,
      blocked: plan.steps.filter(s => s.status === 'blocked').length,
    },
    workQueue: {
      available,
      claimed,
    },
  }
}


function handleBbSearch(blackboard: Blackboard, input: Record<string, unknown>): string {
  const pattern = String(input.pattern ?? '')
  if (!pattern) return JSON.stringify({ error: 'pattern is required.' })

  const boards = Array.isArray(input.boards)
    ? input.boards.map(String) as import('@cassicore/foundation').SearchableBoard[]
    : undefined
  const limitPerBoard = typeof input.limit_per_board === 'number' ? input.limit_per_board : undefined
  const cursor = typeof input.cursor === 'string' ? input.cursor : undefined
  const author = typeof input.author === 'string' ? input.author : undefined
  const since = typeof input.since === 'number' ? input.since : undefined
  const until = typeof input.until === 'number' ? input.until : undefined

  const result = blackboard.searchAll({
    pattern,
    boards,
    limitPerBoard,
    cursor,
    author,
    since,
    until,
  })

  return JSON.stringify(result)
}

function handleBbSearchChannel(blackboard: Blackboard, input: Record<string, unknown>): string {
  const channel = typeof input.channel === 'string'
    ? input.channel as import('@cassicore/foundation').BlackboardChannel
    : undefined
  const pattern = typeof input.pattern === 'string' ? input.pattern : undefined
  const cursor = typeof input.cursor === 'string' ? input.cursor : undefined
  const limit = typeof input.limit === 'number' ? input.limit : undefined
  const author = typeof input.author === 'string' ? input.author : undefined
  const tags = Array.isArray(input.tags) ? input.tags.map(String) : undefined
  const minPriority = typeof input.min_priority === 'number' ? input.min_priority : undefined
  const maxPriority = typeof input.max_priority === 'number' ? input.max_priority : undefined
  const since = typeof input.since === 'number' ? input.since : undefined
  const until = typeof input.until === 'number' ? input.until : undefined

  const result = blackboard.searchChannel({
    channel,
    pattern,
    cursor,
    limit,
    author,
    tags,
    minPriority,
    maxPriority,
    since,
    until,
  })

  return JSON.stringify(result)
}

function handleBbSearchReport(blackboard: Blackboard, input: Record<string, unknown>): string {
  const pattern = typeof input.pattern === 'string' ? input.pattern : undefined
  const cursor = typeof input.cursor === 'string' ? input.cursor : undefined
  const limit = typeof input.limit === 'number' ? input.limit : undefined
  const type = typeof input.type === 'string'
    ? input.type as import('@cassicore/foundation').ReportSectionType
    : undefined
  const status = typeof input.status === 'string'
    ? input.status as import('@cassicore/foundation').ReportSectionStatus
    : undefined
  const author = typeof input.author === 'string' ? input.author : undefined
  const since = typeof input.since === 'number' ? input.since : undefined

  const result = blackboard.searchReport({
    pattern,
    cursor,
    limit,
    type,
    status,
    author,
    since,
  })

  return JSON.stringify(result)
}

function handleBbSearchPlan(blackboard: Blackboard, input: Record<string, unknown>): string {
  const pattern = typeof input.pattern === 'string' ? input.pattern : undefined
  const cursor = typeof input.cursor === 'string' ? input.cursor : undefined
  const limit = typeof input.limit === 'number' ? input.limit : undefined
  const status = typeof input.status === 'string'
    ? input.status as import('@cassicore/foundation').PlanStepStatus
    : undefined
  const assignee = typeof input.assignee === 'string' ? input.assignee : undefined
  const priority = typeof input.priority === 'string'
    ? input.priority as 'high' | 'medium' | 'low'
    : undefined
  const since = typeof input.since === 'number' ? input.since : undefined

  const result = blackboard.searchPlan({
    pattern,
    cursor,
    limit,
    status,
    assignee,
    priority,
    since,
  })

  return JSON.stringify(result)
}
