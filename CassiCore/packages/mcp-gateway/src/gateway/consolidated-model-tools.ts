#!/usr/bin/env node
/**
 * Consolidated Model Tools Module
 *
 * Renames and consolidates model_directive into cassi_model with action parameter:
 * - set, get, clear
 */

import { executeModelDirectiveTool } from './model-directive-tools.js';
import type { ILogger } from '../../types/interfaces.js';

/**
 * Consolidated model tool definition
 */
export const MODEL_CONSOLIDATED_TOOL = {
  name: 'model',
  description: 'Model/provider routing for LLM operations. Control which provider+model is used with layered scopes (next, next-job, session, job, default).',
  inputSchema: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: ['set', 'get', 'clear'],
        description: 'Model operation to perform',
      },
      // set params
      scope: {
        type: 'string',
        enum: ['next', 'next-job', 'session', 'job', 'default'],
        description: 'Scope for model routing: next (one-shot), next-job (per-slot), session (all jobs), job (specific team), default (persisted)',
      },
      tier: {
        type: 'string',
        enum: ['fast', 'swift', 'standard', 'balanced', 'premium', 'background'],
        description: 'Named tier shortcut (fast, swift, standard, balanced, premium, background)',
      },
      provider: {
        type: 'string',
        description: 'Explicit provider ID (e.g., "anthropic", "openai")',
      },
      model: {
        type: 'string',
        description: 'Explicit model name',
      },
      // job scope param
      jobId: {
        type: 'string',
        description: 'Job/session ID for job scope',
      },
      // clear params
      all: {
        type: 'boolean',
        description: 'Clear all scopes (default false)',
      },
    },
    required: ['action'],
  },
};

/**
 * Tool name for routing
 */
export const MODEL_CONSOLIDATED_TOOL_NAME = 'model';

/**
 * Execute the consolidated model tool
 *
 * @param baseUrl - CassiCore base URL
 * @param args - Tool arguments including action
 * @param logger - Logger instance
 */
export async function executeModelConsolidatedTool(
  baseUrl: string,
  args: any,
  logger: ILogger
): Promise<any> {
  const { action, ...restArgs } = args;

  if (!action) {
    throw new Error('Missing required parameter: action');
  }

  logger.info('Executing consolidated model tool', { action, args: restArgs });

  // Map action to legacy tool format
  const toolArgs = {
    ...restArgs,
    action,
  };

  return await executeModelDirectiveTool(baseUrl, 'model_directive', toolArgs, logger);
}

/**
 * Get the consolidated model tool definition
 */
export function getModelConsolidatedTool(): typeof MODEL_CONSOLIDATED_TOOL {
  return MODEL_CONSOLIDATED_TOOL;
}
