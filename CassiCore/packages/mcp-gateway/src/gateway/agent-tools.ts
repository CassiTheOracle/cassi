#!/usr/bin/env node
/**
 * Agent Tools Module — Consolidated Multi-Agent Orchestration
 *
 * Merges ALL multi-agent tools into a single cassi_agent tool with type+action parameters.
 *
 * Types:
 *   - lumen: Dialectic analysis (Yang/Yin/Executive)
 *   - dyad: Pipeline implementation (Yang/Yin/Apex)
 *   - helix: Inverted-pyramid review (Unity/Yang/Yin)
 *   - flux: Team orchestration (multi-cell teams)
 *
 * Actions (vary by type):
 *   - Common: project, status, health, jobs, watch, cancel, sessions, messages, tool_calls, events, postures, progress, blackboard
 *   - Flux-specific: inspect, run, team, steer, approve, reject, pause, resume, checkpoints, tree, change_model
 */

import type { ILogger } from '../../types/interfaces.js';

// Import existing handlers from internal modules
import {
  executeLumenTool,
} from './lumen-tools.js';

import {
  executeDyadTool,
} from './dyad-tools.js';

import {
  executeHelixTool,
} from './helix-tools.js';

import {
  executeConstellationTool,
} from './constellation-tools.js';

import {
  executeFluxTeamTool,
  executeFluxRun,
  executeFluxInspect,
  executeFluxWatch,
} from './flux-tools.js';

/**
 * Consolidated agent tool definition
 */
export const AGENT_TOOL = {
  name: 'agent',
  description: 'Multi-agent orchestration — Lumen (analysis), Dyad (implementation), Helix (review), Flux (teams), Constellation (multi-Helix tree with Corpus). Use type+action to select operation.\n\nUse this tool when you need to delegate work to multi-agent systems. For most multi-step coding or research tasks, use type=constellation with action=project — it spawns and coordinates a tree of Helix sessions via a Corpus organizer. Use type=helix for single-session worker+reviewer tasks, type=lumen for 3-model dialectic analysis, type=dyad for pipeline implementation, and type=flux for team orchestration.\n\nCommon patterns: constellation/project (start coordinated multi-agent work), constellation/watch (block until done), constellation/steer (redirect in-progress work), helix/project (single Helix session), flux/run (autonomous team with checkpoints).',
  inputSchema: {
    type: 'object',
    properties: {
      type: {
        type: 'string',
        enum: ['lumen', 'dyad', 'helix', 'flux', 'constellation'],
        description: 'Agent system type: lumen (dialectic analysis), dyad (pipeline implementation), helix (inverted-pyramid review), flux (team orchestration), constellation (multi-Helix tree with Corpus organizer)',
      },
      action: {
        type: 'string',
        enum: [
          // Common actions across all types
          'project', 'status', 'health', 'jobs', 'watch', 'cancel',
          'sessions', 'messages', 'tool_calls', 'events', 'postures',
          'progress', 'blackboard',
          // Flux-specific actions
          'inspect', 'run', 'team', 'steer', 'approve', 'reject',
          'pause', 'resume', 'checkpoints', 'tree', 'change_model',
          // External Corpus Protocol actions (Constellation only)
          'corpus_assume', 'corpus_release', 'corpus_snapshot',
          'corpus_state', 'corpus_directive', 'corpus_spawn_decide',
          'corpus_synthesis',
          // Constellation analysis actions
          'audit_trail',
        ],
        description: 'Operation to perform within the selected agent system',
      },
      // Lumen/Dyad/Helix common params
      goal: {
        type: 'string',
        description: 'Goal or task description (for project action)',
      },
      context: {
        type: 'string',
        description: 'Additional context or constraints',
      },
      sessionId: {
        type: 'string',
        description: 'Session ID for operations targeting a specific session',
      },
      jobId: {
        type: 'string',
        description: 'Job ID for status/cancel operations',
      },
      parentSessionId: {
        type: 'string',
        description: 'Parent session ID for Phase Zero context distillation',
      },
      // Dyad-specific params
      taskType: {
        type: 'string',
        enum: ['implementation', 'analysis', 'refactor', 'auto'],
        description: 'Hint for Dyad Yin behavior',
      },
      // Flux-specific params
      teamId: {
        type: 'string',
        description: 'Team ID for Flux operations',
      },
      teamAction: {
        type: 'string',
        enum: ['start', 'pause', 'resume', 'cancel', 'steer', 'approve', 'reject', 'tree', 'checkpoints', 'change_model'],
        description: 'Sub-action for flux team operations',
      },
      checkpointPolicy: {
        type: 'string',
        enum: ['interactive', 'auto-approve', 'timeout-degrade'],
        description: 'Checkpoint approval policy for flux_run',
      },
      maxRuntimeSecs: {
        type: 'number',
        description: 'Maximum runtime in seconds for flux_run',
      },
      checkpointTimeoutSecs: {
        type: 'number',
        description: 'Timeout before auto-degrading interactive policy',
      },
      budget: {
        type: 'object',
        description: 'Budget constraints for flux_run',
      },
      roles: {
        type: 'object',
        description: 'Role configuration for flux team start',
      },
      provider: {
        type: 'string',
        description: 'Provider ID for flux team start',
      },
      useFluxTeam: {
        type: 'boolean',
        description: 'Use FluxTeam engine instead of TriadTeam',
      },
      useLumen: {
        type: 'boolean',
        description: 'Include Lumen dialectic analysis in flux_run',
      },
      name: {
        type: 'string',
        description: 'Team name for flux_run',
      },
      message: {
        type: 'string',
        description: 'Message for flux steer/approve/reject actions',
      },
      checkpointId: {
        type: 'string',
        description: 'Checkpoint ID for approve/reject actions',
      },
      includeEvents: {
        type: 'boolean',
        description: 'Include events in flux inspect',
      },
      includeLive: {
        type: 'boolean',
        description: 'Include live cell data in flux inspect',
      },
      timeoutSecs: {
        type: 'number',
        description: 'Timeout for watch operations',
      },
      interestingOnly: {
        type: 'boolean',
        description: 'Filter to significant events only in watch',
      },
      // Shared query params
      posture: {
        type: 'string',
        description: 'Filter by posture (e.g., yang, yin, executive)',
      },
      limit: {
        type: 'number',
        description: 'Limit number of results',
      },
      since: {
        type: 'string',
        description: 'Timestamp filter (ISO 8601)',
      },
      // External Corpus Protocol params (Constellation only)
      agentId: {
        type: 'string',
        description: 'Agent identifier for corpus_assume (for attribution and audit)',
      },
      heartbeatTimeoutMs: {
        type: 'number',
        description: 'Inactivity timeout in ms before auto-releasing Corpus. Default: 300000',
      },
      targetHelixId: {
        type: 'string',
        description: 'Target Helix branch ID for corpus_directive',
      },
      directiveType: {
        type: 'string',
        enum: ['guidance', 'redirect', 'throttle', 'priority-shift', 'cancel', 'context-inject'],
        description: 'Directive type for corpus_directive',
      },
      requestId: {
        type: 'string',
        description: 'Spawn request ID for corpus_spawn_decide',
      },
      approved: {
        type: 'boolean',
        description: 'Whether to approve a spawn request (for corpus_spawn_decide)',
      },
      reason: {
        type: 'string',
        description: 'Reason for spawn decision or Corpus release',
      },
      modifiedGoal: {
        type: 'string',
        description: 'Modified goal for an approved spawn (optional, for corpus_spawn_decide)',
      },
      content: {
        type: 'string',
        description: 'Content for corpus_directive or corpus_synthesis',
      },
      urgency: {
        type: 'string',
        enum: ['low', 'medium', 'high', 'critical'],
        description: 'Urgency level for corpus_directive',
      },
    },
    required: ['type', 'action'],
  },
};

/**
 * Tool name for routing
 */
export const AGENT_TOOL_NAME = 'agent';

/**
 * Execute the consolidated agent tool
 *
 * @param baseUrl - CassiCore base URL
 * @param args - Tool arguments including type and action
 * @param logger - Logger instance
 * @param heartbeat - Optional heartbeat callback for watch operations
 */
export async function executeAgentTool(
  baseUrl: string,
  args: any,
  logger: ILogger,
  heartbeat?: () => void
): Promise<any> {
  const { type, action, ...restArgs } = args;

  if (!type || !action) {
    throw new Error('Missing required parameters: type and action');
  }

  logger.info('Executing agent tool', { type, action, args: restArgs });

  switch (type) {
    case 'lumen':
    case 'dyad':
    case 'helix':
      return await executeHelixAgentTool(baseUrl, action, restArgs, logger, heartbeat);
    case 'constellation':
      return await executeConstellationAgentTool(baseUrl, action, restArgs, logger, heartbeat);
    case 'flux':
      return await executeFluxAgentTool(baseUrl, action, restArgs, logger, heartbeat);
    default:
      throw new Error(`Unknown agent type: ${type}`);
  }
}

/**
 * Execute Helix-specific agent actions
 */
async function executeHelixAgentTool(
  baseUrl: string,
  action: string,
  args: any,
  logger: ILogger,
  heartbeat?: () => void
): Promise<any> {
  const toolName = `helix_${action}`;

  // Map consolidated action to legacy tool name
  const validHelixTools = new Set([
    'helix_project', 'helix_status', 'helix_cancel', 'helix_health',
    'helix_jobs', 'helix_watch', 'helix_sessions', 'helix_messages',
    'helix_tool_calls', 'helix_events', 'helix_postures', 'helix_progress',
    'helix_blackboard',
  ]);

  if (!validHelixTools.has(toolName)) {
    throw new Error(`Unknown Helix action: ${action}`);
  }

  return await executeHelixTool(baseUrl, toolName, args, logger, heartbeat);
}

/**
 * Execute Constellation-specific agent actions
 */
async function executeConstellationAgentTool(
  baseUrl: string,
  action: string,
  args: any,
  logger: ILogger,
  heartbeat?: () => void
): Promise<any> {
  const toolName = `constellation_${action}`;

  const validConstellationTools = new Set([
    'constellation_project', 'constellation_status', 'constellation_cancel',
    'constellation_jobs', 'constellation_sessions', 'constellation_watch',
    'constellation_progress', 'constellation_tree', 'constellation_topology', 'constellation_steer',
    'constellation_blackboard', 'constellation_analyze',
    // External Corpus Protocol
    'constellation_corpus_assume', 'constellation_corpus_release',
    'constellation_corpus_snapshot', 'constellation_corpus_state',
    'constellation_corpus_directive',     'constellation_corpus_spawn_decide',
    'constellation_corpus_synthesis',
    'constellation_audit_trail',
  ]);

  if (!validConstellationTools.has(toolName)) {
    throw new Error(`Unknown Constellation action: ${action}`);
  }

  // HOW: Remap agent-tool param names to constellation-tool param names
  // for External Corpus Protocol actions
  const remappedArgs = { ...args }
  if (action === 'corpus_directive' && remappedArgs.directiveType) {
    remappedArgs.type = remappedArgs.directiveType
    delete remappedArgs.directiveType
  }

  return await executeConstellationTool(baseUrl, toolName, remappedArgs, logger, heartbeat);
}

/**
 * Execute Flux-specific agent actions
 */
async function executeFluxAgentTool(
  baseUrl: string,
  action: string,
  args: any,
  logger: ILogger,
  heartbeat?: () => void
): Promise<any> {
  switch (action) {
    case 'run':
      return await executeFluxRun(baseUrl, args, logger, heartbeat);
    case 'inspect':
      return await executeFluxInspect(baseUrl, args, logger);
    case 'watch':
      return await executeFluxWatch(baseUrl, args, logger, heartbeat);
    case 'team':
    case 'steer':
    case 'approve':
    case 'reject':
    case 'pause':
    case 'resume':
    case 'cancel':
    case 'checkpoints':
    case 'tree':
    case 'change_model': {
      // Map action to teamAction if not explicitly provided
      const teamArgs = {
        ...args,
        action: args.teamAction || action,
      };
      return await executeFluxTeamTool(baseUrl, teamArgs, logger);
    }
    default:
      throw new Error(`Unknown Flux action: ${action}`);
  }
}

/**
 * Get the consolidated agent tool definition
 * @dep callers: getAllTools (mcp/cassicore-gateway.ts)
 * @dep flows: Start → GetAgentTool (4/4)
 * @dep module: Unknown
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */
export function getAgentTool(): typeof AGENT_TOOL {
  return AGENT_TOOL;
}
