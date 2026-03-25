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
  description: 'Multi-agent orchestration — Lumen (analysis), Dyad (implementation), Helix (review), Flux (teams). Use type+action to select operation.',
  inputSchema: {
    type: 'object',
    properties: {
      type: {
        type: 'string',
        enum: ['lumen', 'dyad', 'helix', 'flux'],
        description: 'Agent system type: lumen (dialectic analysis), dyad (pipeline implementation), helix (inverted-pyramid review), flux (team orchestration)',
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
      return await executeLumenAgentTool(baseUrl, action, restArgs, logger, heartbeat);
    case 'dyad':
      return await executeDyadAgentTool(baseUrl, action, restArgs, logger, heartbeat);
    case 'helix':
      return await executeHelixAgentTool(baseUrl, action, restArgs, logger, heartbeat);
    case 'flux':
      return await executeFluxAgentTool(baseUrl, action, restArgs, logger, heartbeat);
    default:
      throw new Error(`Unknown agent type: ${type}`);
  }
}

/**
 * Execute Lumen-specific agent actions
 */
async function executeLumenAgentTool(
  baseUrl: string,
  action: string,
  args: any,
  logger: ILogger,
  heartbeat?: () => void
): Promise<any> {
  const toolName = `lumen_${action}`;

  // Map consolidated action to legacy tool name
  const validLumenTools = new Set([
    'lumen_project', 'lumen_status', 'lumen_cancel', 'lumen_health',
    'lumen_jobs', 'lumen_watch', 'lumen_sessions', 'lumen_messages',
    'lumen_tool_calls', 'lumen_events', 'lumen_postures', 'lumen_progress',
    'lumen_blackboard',
  ]);

  if (!validLumenTools.has(toolName)) {
    throw new Error(`Unknown Lumen action: ${action}`);
  }

  return await executeLumenTool(baseUrl, toolName, args, logger, heartbeat);
}

/**
 * Execute Dyad-specific agent actions
 */
async function executeDyadAgentTool(
  baseUrl: string,
  action: string,
  args: any,
  logger: ILogger,
  heartbeat?: () => void
): Promise<any> {
  const toolName = `dyad_${action}`;

  // Map consolidated action to legacy tool name
  const validDyadTools = new Set([
    'dyad_project', 'dyad_status', 'dyad_cancel', 'dyad_health',
    'dyad_jobs', 'dyad_watch', 'dyad_sessions', 'dyad_messages',
    'dyad_tool_calls', 'dyad_events', 'dyad_postures', 'dyad_progress',
    'dyad_blackboard',
  ]);

  if (!validDyadTools.has(toolName)) {
    throw new Error(`Unknown Dyad action: ${action}`);
  }

  return await executeDyadTool(baseUrl, toolName, args, logger, heartbeat);
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
 */
export function getAgentTool(): typeof AGENT_TOOL {
  return AGENT_TOOL;
}
